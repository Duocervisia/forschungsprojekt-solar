("""Batteriespannung über die Zeit aus batterylog.txt plotten.

Verwendung:
	python batterylog-plotter.py [--file PFAD] [--save-only]

Erstellt `battery_voltage.png` im gleichen Ordner und zeigt das Diagramm an
es sei denn, `--save-only` wird angegeben.
""")

from __future__ import annotations

import argparse
import os
import re
from datetime import datetime
from typing import List

import matplotlib.pyplot as plt
import matplotlib.dates as mdates


def parse_timestamp(s: str) -> datetime:
	s = s.strip()
	# Expect formats like 2025-10-23T06:47:41.379Z or without fractional seconds
	for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
		try:
			return datetime.strptime(s, fmt)
		except ValueError:
			continue
	# Fallback: try to strip trailing Z and use fromisoformat
	if s.endswith("Z"):
		s2 = s[:-1]
		try:
			return datetime.fromisoformat(s2)
		except Exception:
			pass
	raise ValueError(f"Unbekanntes Zeitstempelformat: {s}")


def parse_voltage(field: str) -> float:
	# field examples: '4.05v - 84%' or '4.05v - 84%, 0.8360512' (we expect the v part)
	m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*[vV]", field)
	if m:
		return float(m.group(1))
	# fallback: first float in string
	m2 = re.search(r"([0-9]+(?:\.[0-9]+)?)", field)
	if m2:
		return float(m2.group(1))
	raise ValueError(f"Keine Spannung im Feld gefunden: {field}")


def read_log(path: str) -> tuple[List[datetime], List[float]]:
	times: List[datetime] = []
	volts: List[float] = []
	with open(path, "r", encoding="utf-8") as f:
		for ln in f:
			ln = ln.strip()
			if not ln:
				continue
			parts = ln.split(",")
			if len(parts) < 3:
				continue
			ts_raw = parts[0].strip()
			voltage_field = parts[2].strip()
			try:
				ts = parse_timestamp(ts_raw)
				v = parse_voltage(voltage_field)
			except Exception:
				continue
			times.append(ts)
			volts.append(v)
	return times, volts


def plot(times: List[datetime], volts: List[float], outpath: str, show: bool = True) -> None:
	if not times:
		raise SystemExit("Keine Daten aus der Logdatei geparst.")
	# publication-style settings
	plt.rcParams.update({
		"font.family": "serif",
		"font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
		"font.size": 10,
		"axes.labelsize": 10,
		"axes.titlesize": 11,
		"xtick.labelsize": 9,
		"ytick.labelsize": 9,
		"figure.dpi": 300,
	})
	fig, ax = plt.subplots(figsize=(6.5, 3))
	# smaller, crisper markers and thinner line for paper
	ax.plot(times, volts, color="black", marker="o", markersize=3, markeredgewidth=0.4, linestyle="-", linewidth=0.8)
	ax.set_xlabel("Zeit")
	ax.set_ylabel("Spannung (V)")
	# set y-axis to a larger span from 3.2 V up to 4.2 V
	ax.set_ylim(3.2, 4.2)
	# ax.set_title("Batteriespannung über die Zeit")
	ax.grid(True, alpha=0.4)
	# format dates
	locator = mdates.AutoDateLocator()
	formatter = mdates.ConciseDateFormatter(locator)
	ax.xaxis.set_major_locator(locator)
	ax.xaxis.set_major_formatter(formatter)
	fig.autofmt_xdate()
	plt.tight_layout()
	# save high-resolution PNG and PDF for inclusion in papers
	fig.savefig(outpath, dpi=300)
	pdf_out = os.path.splitext(outpath)[0] + ".pdf"
	fig.savefig(pdf_out, dpi=300)
	if show:
		plt.show()


def main() -> None:
	p = argparse.ArgumentParser(description="Plot battery voltage from a log file")
	p.add_argument("--file", "-f", default="batterylog.txt", help="path to batterylog.txt")
	p.add_argument("--save-only", action="store_true", help="save plot but do not show GUI")
	grp = p.add_mutually_exclusive_group()
	grp.add_argument("--daily", action="store_true", help="aggregate one value per calendar day and place marker at midday")
	grp.add_argument("--weekly", action="store_true", help="aggregate one value per ISO week and place marker at Wednesday midday")
	args = p.parse_args()
	path = args.file
	if not os.path.isabs(path):
		# assume relative to this script
		base = os.path.dirname(__file__)
		path = os.path.join(base, path)
	times, volts = read_log(path)
	if args.daily or args.weekly:
		# aggregate by calendar date or ISO week; place marker at midday
		from collections import defaultdict

		if args.daily:
			# Use ISO date strings as keys to avoid subtle date-object issues
			sums: dict[str, float] = {}
			counts: dict[str, int] = {}
			for t, v in zip(times, volts):
				key = t.date().isoformat()
				sums[key] = sums.get(key, 0.0) + v
				counts[key] = counts.get(key, 0) + 1
			agg: list[tuple[datetime, float]] = []
			for key in sorted(sums.keys()):
				d = datetime.fromisoformat(key).date()
				mean_v = sums[key] / counts[key]
				agg.append((datetime(d.year, d.month, d.day, 12, 0), mean_v))
			if agg:
				times = [t for t, _ in agg]
				volts = [v for _, v in agg]
			else:
				times, volts = [], []
			print(f"Aggregated {len(times)} day(s) from {sum(counts.values())} sample(s)")

		else:  # args.weekly
			# Key by ISO year-week
			sums: dict[str, float] = {}
			counts: dict[str, int] = {}
			for t, v in zip(times, volts):
				iso = t.isocalendar()
				# iso: (year, week, weekday)
				key = f"{iso[0]}-W{iso[1]:02d}"
				sums[key] = sums.get(key, 0.0) + v
				counts[key] = counts.get(key, 0) + 1
			agg: list[tuple[datetime, float]] = []
			for key in sorted(sums.keys()):
				year_s, week_s = key.split("-W")
				year = int(year_s)
				week = int(week_s)
				# place marker at Wednesday (ISO weekday 3) at 12:00
				mid = datetime.fromisocalendar(year, week, 3).replace(hour=12, minute=0, second=0, microsecond=0)
				mean_v = sums[key] / counts[key]
				agg.append((mid, mean_v))
			if agg:
				times = [t for t, _ in agg]
				volts = [v for _, v in agg]
			else:
				times, volts = [], []
			print(f"Aggregated {len(times)} week(s) from {sum(counts.values())} sample(s)")
	outpath = os.path.join(os.path.dirname(path), "battery_voltage.png")
	plot(times, volts, outpath, show=not args.save_only)
	print(f"Saved plot to: {outpath}")


if __name__ == "__main__":
	main()

