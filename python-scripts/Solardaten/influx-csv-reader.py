"""influx-csv-reader.py

Read an InfluxDB-exported CSV and create one time-series plot per numeric field.

Usage examples:
  python influx-csv-reader.py data.csv
  python influx-csv-reader.py data.csv --outdir plots --show

This script will:
 - read the CSV (skipping lines beginning with '#')
 - detect the time column (any column name containing 'time')
 - treat numeric columns as data fields and plot each separately
 - save PNG files to the output directory

Requirements: pandas, matplotlib
"""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
import re
import sys

import matplotlib.pyplot as plt
from matplotlib.ticker import ScalarFormatter
import pandas as pd


def _sanitize_filename(name: str) -> str:
	name = re.sub(r"[^A-Za-z0-9._-]", "_", name)
	return name[:200]


def load_influx_csv(path: Path) -> pd.DataFrame:
	# Use pandas to read CSV; Influx exported CSV often contains commented metadata lines
	# starting with '#'. pandas.read_csv(..., comment='#') will ignore those lines and
	# use the first non-comment line as the header.
	try:
		df = pd.read_csv(path, comment="#")
	except Exception as exc:
		raise RuntimeError(f"Failed to read CSV '{path}': {exc}")

	if df.empty:
		raise RuntimeError(f"CSV file '{path}' contains no data after parsing")

	# find time column (case-insensitive substring 'time')
	time_cols = [c for c in df.columns if "time" in c.lower()]
	if not time_cols:
		raise RuntimeError("Could not find a time column (containing 'time') in CSV")

	time_col = time_cols[0]
	# parse time column to datetime
	try:
		df[time_col] = pd.to_datetime(df[time_col], utc=True, errors="coerce")
	except Exception:
		df[time_col] = pd.to_datetime(df[time_col], errors="coerce")

	if df[time_col].isna().all():
		raise RuntimeError(f"Time column '{time_col}' could not be parsed as datetimes")

	df = df.set_index(time_col)
	# sort by index
	df = df.sort_index()
	return df


def plot_fields(df: pd.DataFrame, outdir: Path, show: bool = False, dpi: int = 150) -> list[Path]:
	outdir.mkdir(parents=True, exist_ok=True)
	# If CSV used Influx "wide" format with '_field' and '_value' columns,
	# pivot those into separate series columns keyed by the field name.
	working = df.reset_index()
	index_name = df.index.name or "time"
	if "_field" in working.columns and "_value" in working.columns:
		pivot = working.pivot_table(index=index_name, columns="_field", values="_value")
		data = pivot
	else:
		# otherwise, use numeric dtype columns from the dataframe (index already time)
		data = df.select_dtypes(include=["number"]) 

	# ensure numeric values (coerce non-numeric to NaN)
	data = data.apply(pd.to_numeric, errors="coerce")
	if data.shape[1] == 0:
		raise RuntimeError("No numeric data fields found to plot")

	saved_files: list[Path] = []
	open_figs = []
	for col in data.columns:
		# prepare series and display name; special-case 'current_A'
		series = data[col].copy()
		display_name = str(col)
		if col == "current_A":
			# detect unit scale heuristically and convert to µA
			abs_max = series.abs().max(skipna=True)
			if abs_max is None or pd.isna(abs_max) or abs_max == 0:
				scale = 1.0
			elif abs_max < 1e-3:
				# values in A (or smaller) -> A to µA
				scale = 1e6
			elif abs_max < 1:
				# values in mA -> mA to µA
				scale = 1e3
			else:
				# already large values (assume µA or higher) - do not scale
				scale = 1.0
			series = series * scale
			display_name = "Stromstärke in µA"

		fig, ax = plt.subplots(figsize=(10, 4))
		ax.plot(data.index, series, marker=None, linewidth=1)
		ax.set_ylabel(display_name)
		ax.set_xlabel("Zeitraum")
		# disable scientific offset notation and enforce plain formatting
		sf = ScalarFormatter(useMathText=False)
		sf.set_scientific(False)
		ax.yaxis.set_major_formatter(sf)
		# set y-range for current plots to 0..1000 µA when plotting current
		if col == "current_A":
			ax.set_ylim(-50, 1050)

		fig.autofmt_xdate(rotation=25)
		# use a filename-friendly form (replace micro sign with 'u')
		fname = _sanitize_filename(display_name.replace("µ", "u")) + ".png"
		outpath = outdir / fname
		fig.tight_layout()
		fig.savefig(outpath, dpi=dpi)
		saved_files.append(outpath)

		if show:
			# keep figure open for interactive viewing
			open_figs.append(fig)
		else:
			plt.close(fig)

	if show and open_figs:
		# show all open figures in interactive windows (blocking until closed)
		plt.show()
		# after windows closed, close figures to free memory
		for f in open_figs:
			plt.close(f)

	return saved_files


def main(argv: list[str] | None = None) -> int:
	parser = argparse.ArgumentParser(description="Read InfluxDB CSV and plot numeric fields")
	parser.add_argument("csv", type=Path, nargs='?', default=Path("Solardaten625.csv"),
						help="Path to InfluxDB-exported CSV file (defaults to 'query.csv')")
	parser.add_argument("--outdir", type=Path, default=Path.cwd() / "plots", help="Output directory for PNG files")
	parser.add_argument("--dpi", type=int, default=150, help="DPI for saved PNGs")
	parser.add_argument("--show", action="store_true", help="Also display the plots interactively")
	parser.add_argument("--quiet", action="store_true", help="Less verbose logging")
	parser.add_argument("--start", type=str, default="2026-01-27T00:00:00.0Z", help="Start datetime (inclusive). Any format accepted by pandas.to_datetime")
	parser.add_argument("--end", type=str, default="2026-01-28T00:00:00.0Z", help="End datetime (inclusive). Any format accepted by pandas.to_datetime")
	args = parser.parse_args(argv)

	logging.basicConfig(level=(logging.WARNING if args.quiet else logging.INFO), format="%(levelname)s: %(message)s")

	if not args.csv.exists():
		logging.error("CSV file does not exist: %s", args.csv)
		return 2
	else:
		logging.info("Using CSV file: %s", args.csv)

	try:
		df = load_influx_csv(args.csv)
	except Exception as exc:
		logging.error(str(exc))
		return 3

	# Optionally filter the dataframe by a provided date range
	if args.start or args.end:
		try:
			start_ts = pd.to_datetime(args.start, utc=True) if args.start else None
		except Exception as exc:
			logging.error("Invalid --start datetime: %s", exc)
			return 5
		try:
			end_ts = pd.to_datetime(args.end, utc=True) if args.end else None
		except Exception as exc:
			logging.error("Invalid --end datetime: %s", exc)
			return 5

		orig_len = len(df)
		if start_ts is not None:
			df = df[df.index >= start_ts]
		if end_ts is not None:
			df = df[df.index <= end_ts]
		if df.empty:
			logging.error("No data in the specified date range (start=%s, end=%s)", args.start, args.end)
			return 6
		logging.info("Filtered data by range: %s -> %s (%d -> %d rows)", args.start or "-", args.end or "-", orig_len, len(df))

	try:
		saved = plot_fields(df, args.outdir, show=args.show, dpi=args.dpi)
	except Exception as exc:
		logging.error("Failed to create plots: %s", exc)
		return 4

	logging.info("Saved %d plot(s) to %s", len(saved), args.outdir)
	return 0


if __name__ == "__main__":
	raise SystemExit(main())

