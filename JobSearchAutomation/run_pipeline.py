#!/usr/bin/env python3
"""
Run end-to-end local pipeline:
1) discover jobs
2) convert to outreach targets
3) generate outreach drafts + tracker
"""

from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str]) -> None:
    print(f"[run] {' '.join(cmd)}")
    proc = subprocess.run(cmd)
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run job discovery + outreach pipeline.")
    parser.add_argument("--profile", default="JobSearchAutomation/profile.json")
    parser.add_argument("--sources", default="JobSearchAutomation/sources_template.json")
    parser.add_argument("--outdir", default="JobSearchAutomation/output")
    parser.add_argument("--location-mode", default="remote_us_canada_hybrid")
    parser.add_argument("--min-fit-score", type=int, default=3)
    parser.add_argument("--top-n", type=int, default=40)
    parser.add_argument("--min-priority", default="medium")
    parser.add_argument("--digest-top-n", type=int, default=20)
    parser.add_argument("--digest-min-competitive-score", type=int, default=14)
    args = parser.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    discovered = str(outdir / "discovered_jobs.csv")
    targets = str(outdir / "auto_targets.csv")
    digest_txt = str(outdir / "daily_digest.txt")
    digest_html = str(outdir / "daily_digest.html")
    date_label = dt.datetime.now(dt.UTC).strftime("%Y-%m-%d UTC")

    py = sys.executable
    run(
        [
            py,
            "JobSearchAutomation/discover_jobs.py",
            "--profile",
            args.profile,
            "--sources",
            args.sources,
            "--output",
            discovered,
            "--location-mode",
            args.location_mode,
            "--min-fit-score",
            str(args.min_fit_score),
        ]
    )
    run(
        [
            py,
            "JobSearchAutomation/build_targets_from_discovery.py",
            "--input",
            discovered,
            "--output",
            targets,
            "--top-n",
            str(args.top_n),
            "--min-priority",
            args.min_priority,
        ]
    )
    run(
        [
            py,
            "JobSearchAutomation/generate_outreach.py",
            "--profile",
            args.profile,
            "--input",
            targets,
            "--outdir",
            args.outdir,
        ]
    )
    run(
        [
            py,
            "JobSearchAutomation/generate_daily_digest.py",
            "--input",
            discovered,
            "--text-output",
            digest_txt,
            "--html-output",
            digest_html,
            "--top-n",
            str(args.digest_top_n),
            "--min-competitive-score",
            str(args.digest_min_competitive_score),
            "--date-label",
            date_label,
        ]
    )
    print(f"Pipeline complete. Review outputs in {outdir}")


if __name__ == "__main__":
    main()
