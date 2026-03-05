"""Calculate integrated microampere-hours from Solardaten CSV.

Reads a CSV with a time column and one or more current columns (detected
by name heuristics). Negative values are ignored. Sampling intervals are
used to convert per-sample current values into µA·h (integral). By
default the script assumes values are already in microampere (µA);
pass `--unit A` to treat values as amperes (will convert to µA).

Usage:
  python calculate_uA.py Solardaten625.csv

Outputs a small summary to stdout.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
import re
import sys

import pandas as pd


def find_time_column(df: pd.DataFrame) -> str | None:
    for c in df.columns:
        if "time" in c.lower() or re.search(r"datum|date|zeit", c, flags=re.IGNORECASE):
            return c
    return None


def detect_current_columns(df: pd.DataFrame) -> list[str]:
    candidates: list[str] = []
    for c in df.columns:
        lower = c.lower()
        # name-based heuristics for current columns
        if re.search(r"current|strom|amp|milliamp|microamp|µa|ua", lower):
            candidates.append(c)
            continue
        # columns named like 'xxx_A' or ending with '_a', '_ua', '_ma'
        if re.search(r"(_a$)|(_ua$)|(_ma$)", lower):
            candidates.append(c)
            continue
    return candidates


def compute_uah(df: pd.DataFrame, cols: list[str], unit: str = "uA") -> dict[str, float]:
    """Return dict of integrated microampere-hours per column and total.

    - Negative values are ignored.
    - Sampling intervals are taken from the datetime index; the first row
      uses the median delta as an estimate.
    - `unit` may be 'uA' (default) or 'A'. If 'A', values are converted
      to µA by multiplying by 1e6.
    """
    # ensure datetime index
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("DataFrame must have a DatetimeIndex")

    # per-row durations in seconds
    diffs = df.index.to_series().diff().dt.total_seconds()
    median = float(diffs.median(skipna=True) or 60.0)
    diffs = diffs.fillna(median).clip(lower=0.0)
    hours = diffs / 3600.0

    results: dict[str, float] = {}
    for c in cols:
        vals = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
        vals = vals.clip(lower=0.0)  # ignore negative values

        # heuristic per-column unit scaling: if values are small, assume they
        # are in A or mA and convert to µA; otherwise assume µA already
        abs_max = float(vals.abs().max(skipna=True) or 0.0)
        if unit.lower() in ("a", "amp", "amps"):
            scale = 1e6
        else:
            if abs_max > 0 and abs_max < 1e-3:
                scale = 1e6
            elif abs_max > 0 and abs_max < 1:
                scale = 1e3
            else:
                scale = 1.0

        vals_uA = vals * scale
        total_uAh = (vals_uA * hours).sum()
        results[c] = float(total_uAh)

    results["_total"] = sum(results.values())
    # total hours covered (for average calculation)
    total_hours = hours.sum()
    results["_hours"] = float(total_hours)
    results["_average_uA"] = float(results["_total"] / total_hours) if total_hours > 0 else 0.0
    return results


def load_csv(path: Path) -> pd.DataFrame:
    # Read InfluxDB-exported CSVs (skip commented metadata lines starting with '#')
    try:
        df = pd.read_csv(path, comment="#", low_memory=False)
    except Exception as exc:
        raise RuntimeError(f"Failed to read CSV '{path}': {exc}")

    if df.empty:
        raise RuntimeError(f"CSV file '{path}' contains no data after parsing")

    time_col = find_time_column(df)
    if time_col is None:
        raise RuntimeError("Could not find a time column in CSV")

    # parse time column
    try:
        df[time_col] = pd.to_datetime(df[time_col], utc=True, errors="coerce")
    except Exception:
        df[time_col] = pd.to_datetime(df[time_col], errors="coerce")

    df = df[~df[time_col].isna()]
    df = df.set_index(time_col)
    df = df.sort_index()

    # If CSV is in Influx "long" format with _field/_value columns, pivot to wide
    working = df.reset_index()
    index_name = df.index.name or time_col
    if "_field" in working.columns and "_value" in working.columns:
        pivot = working.pivot_table(index=index_name, columns="_field", values="_value")
        pivot = pivot.apply(pd.to_numeric, errors="coerce")
        pivot = pivot.sort_index()
        return pivot

    # otherwise return numeric columns only
    numeric = df.select_dtypes(include=["number"]).copy()
    if numeric.shape[1] == 0:
        raise RuntimeError("No numeric data fields found in CSV")
    return numeric


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compute µA·h from Solardaten CSV")
    parser.add_argument("file", type=Path, nargs="?", default=Path("Solardaten625.csv"), help="CSV file")
    parser.add_argument("--unit", choices=("uA", "A"), default="uA", help="Unit of current columns (default: uA)")
    parser.add_argument("--start", type=str, default=None)
    parser.add_argument("--end", type=str, default=None)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(level=(logging.WARNING if args.quiet else logging.INFO), format="%(levelname)s: %(message)s")

    if not args.file.exists():
        logging.error("File not found: %s", args.file)
        return 2

    try:
        df = load_csv(args.file)
    except Exception as exc:
        logging.error("Failed to load CSV: %s", exc)
        return 3

    if args.start:
        try:
            start_ts = pd.to_datetime(args.start, utc=True)
            df = df[df.index >= start_ts]
        except Exception as exc:
            logging.error("Invalid --start: %s", exc)
            return 4
    if args.end:
        try:
            end_ts = pd.to_datetime(args.end, utc=True)
            df = df[df.index <= end_ts]
        except Exception as exc:
            logging.error("Invalid --end: %s", exc)
            return 4

    cols = detect_current_columns(df)
    if not cols:
        logging.error("No current-like columns detected in file")
        return 5

    results = compute_uah(df, cols, unit=args.unit)

    for c in cols:
        logging.info("%s: %.3f µA·h", c, results.get(c, 0.0))
    logging.info("Total µA·h: %.3f", results["_total"])
    logging.info("Total hours: %.3f h", results["_hours"])
    logging.info("Average current: %.3f µA", results["_average_uA"])

    # print a compact summary to stdout as well
    print(f"Total µA·h: {results['_total']:.3f}")
    print(f"Total hours: {results['_hours']:.3f}")
    print(f"Average µA: {results['_average_uA']:.3f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
