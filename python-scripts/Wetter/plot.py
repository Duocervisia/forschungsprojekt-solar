"""Wetter-Plotter

Liest eine CSV/TXT mit Zeitstempel und erstellt einen gemeinsamen Plot
für Diffus- und Direktstrahlung. Unterstützt Angabe eines Zeitfensters
via `--start`/`--end` (pandas.to_datetime Formate).

Beispiel:
  python plot.py wetter.txt --start 2026-01-01 --end 2026-01-31 --outdir ../plots

Erwartete Spalten: Spaltennamen die 'diffus' und 'direct' (case-insensitive)
enthalten. Zeitspalte erkennt jede Spalte mit 'time' im Namen.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
import re
import sys

import matplotlib.pyplot as plt
import pandas as pd


def _sanitize_filename(name: str) -> str:
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    return name[:200]


def load_csv(path: Path) -> pd.DataFrame:
    # Some exported files (like the provided wetter.txt) contain a metadata
    # section before the CSV header. Find the first line that begins with
    # a time-like header (e.g. 'time,') and use that line's comma-separated
    # values as column names. Then read the CSV skipping the metadata and
    # the header line itself (the next line may contain units).
    header_row = None
    header_line = None
    next_line = None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for i, line in enumerate(fh):
                if re.match(r"^\s*time\b", line, flags=re.IGNORECASE):
                    header_row = i
                    header_line = line.rstrip("\n\r")
                    # read the immediate next line (units or sample) if available
                    next_line = fh.readline().rstrip("\n\r") if fh is not None else None
                    break
    except Exception as exc:
        raise RuntimeError(f"Failed to read file '{path}': {exc}")

    try:
        if header_line is not None:
            # derive column names from header_line and read remaining lines as data
            names = [h.strip() for h in header_line.split(",")]
            # if the next line looks like a units row (contains letters like 'W/m'), skip it too
            skip = header_row + 1
            if next_line and re.search(r"[A-Za-z]", next_line):
                skip = header_row + 2
            df = pd.read_csv(path, header=None, names=names, skiprows=skip)
        else:
            df = pd.read_csv(path, comment="#")
    except Exception as exc:
        raise RuntimeError(f"Failed to read CSV '{path}': {exc}")

    if df.empty:
        raise RuntimeError(f"CSV file '{path}' contains no data after parsing")

    time_cols = [c for c in df.columns if "time" in c.lower()]
    if not time_cols:
        raise RuntimeError("Could not find a time column (containing 'time') in CSV")

    time_col = time_cols[0]
    try:
        df[time_col] = pd.to_datetime(df[time_col], utc=True, errors="coerce")
    except Exception:
        df[time_col] = pd.to_datetime(df[time_col], errors="coerce")

    if df[time_col].isna().all():
        raise RuntimeError(f"Time column '{time_col}' could not be parsed as datetimes")

    # drop rows with invalid timestamps
    before = len(df)
    df = df[~df[time_col].isna()]
    after = len(df)
    if after < before:
        logging.info("Dropped %d rows with invalid timestamps", before - after)

    df = df.set_index(time_col)
    df = df.sort_index()

    # convert timezone-aware index to naive datetimes for matplotlib compatibility
    try:
        if getattr(df.index, "tz", None) is not None:
            df.index = df.index.tz_convert(None)
    except Exception:
        try:
            df.index = df.index.tz_localize(None)
        except Exception:
            pass

    return df


def find_columns(df: pd.DataFrame) -> tuple[str | None, str | None]:
    cols = list(df.columns)
    diffus = None
    direct_ = None
    for c in cols:
        lower = c.lower()
        if "diffus" in lower and diffus is None:
            diffus = c
        if ("direct" in lower or "direkt" in lower or "beam" in lower) and direct_ is None:
            direct_ = c
    return diffus, direct_  


def plot_radiation(df: pd.DataFrame, diffus_col: str, direct_col: str, outdir: Path, dpi: int = 150, show: bool = False) -> Path:
    outdir.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(12, 5))
    # use transparency and z-order so overlapping lines are readable
    ax.plot(df.index, df[diffus_col], label="Diffusstrahlung", linewidth=1, alpha=0.5, color="tab:blue", zorder=2)
    ax.plot(df.index, df[direct_col], label="Direktstrahlung", linewidth=1, alpha=0.5, color="tab:orange", zorder=3)
    # subtle filled area for direct to increase visual separation
    try:
        ax.fill_between(df.index, 0, df[direct_col], step=None, facecolor="tab:orange", alpha=0.06, zorder=1)
    except Exception:
        pass
    ax.set_xlabel("Zeitraum")
    ax.set_ylabel("Strahlung (W/m²)")
    # ax.set_title("Diffus und Direktstrahlung")
    ax.legend(framealpha=0.9, loc="upper left")
    fig.autofmt_xdate(rotation=25)
    fig.tight_layout()

    fname = _sanitize_filename("diffus_direct") + ".png"
    outpath = outdir / fname
    fig.savefig(outpath, dpi=dpi)

    if show:
        plt.show()
        plt.close(fig)
    else:
        plt.close(fig)

    return outpath


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Plot Diffuse and Direct radiation from CSV/TXT")
    parser.add_argument("file", type=Path, nargs="?", default=Path("wetter.txt"), help="Input CSV/TXT file")
    parser.add_argument("--outdir", type=Path, default=Path.cwd() / "plots", help="Output directory for PNG files")
    parser.add_argument("--start", type=str, default=None, help="Start datetime (inclusive)")
    parser.add_argument("--end", type=str, default=None, help="End datetime (inclusive)")
    parser.add_argument("--dpi", type=int, default=150, help="DPI for saved PNGs")
    parser.add_argument("--show", action="store_true", help="Also display the plot interactively")
    parser.add_argument("--quiet", action="store_true", help="Less verbose logging")
    args = parser.parse_args(argv)

    logging.basicConfig(level=(logging.WARNING if args.quiet else logging.INFO), format="%(levelname)s: %(message)s")

    if not args.file.exists():
        logging.error("Input file does not exist: %s", args.file)
        return 2

    try:
        df = load_csv(args.file)
    except Exception as exc:
        logging.error(str(exc))
        return 3

    # filter by start/end if provided
    if args.start or args.end:
        try:
            start_ts = pd.to_datetime(args.start, utc=True) if args.start else None
        except Exception as exc:
            logging.error("Invalid --start datetime: %s", exc)
            return 4
        try:
            end_ts = pd.to_datetime(args.end, utc=True) if args.end else None
        except Exception as exc:
            logging.error("Invalid --end datetime: %s", exc)
            return 4

        orig_len = len(df)
        if start_ts is not None:
            df = df[df.index >= start_ts]
        if end_ts is not None:
            df = df[df.index <= end_ts]
        if df.empty:
            logging.error("No data in the specified date range (start=%s, end=%s)", args.start, args.end)
            return 5
        logging.info("Filtered data by range: %s -> %s (%d -> %d rows)", args.start or "-", args.end or "-", orig_len, len(df))

    diffus_col, direct_col = find_columns(df)
    if diffus_col is None or direct_col is None:
        logging.error("Could not find required columns. Found diffus=%s, direct=%s", diffus_col, direct_col)
        return 6

    try:
        out = plot_radiation(df, diffus_col, direct_col, args.outdir, dpi=args.dpi, show=args.show)
    except Exception as exc:
        logging.error("Failed to create plot: %s", exc)
        return 7

    logging.info("Saved plot to %s", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
