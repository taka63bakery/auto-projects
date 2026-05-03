#!/usr/bin/env python3
"""
Convert discovered jobs CSV into targets CSV format for outreach generation.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def to_contact_channel(remote_signal: str) -> str:
    signal = (remote_signal or "").lower()
    if "hybrid" in signal:
        return "linkedin"
    return "email"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build outreach targets from discovered jobs CSV.")
    parser.add_argument("--input", required=True, help="Path to discovered_jobs.csv")
    parser.add_argument("--output", required=True, help="Path to targets CSV output")
    parser.add_argument(
        "--top-n",
        type=int,
        default=40,
        help="Maximum number of rows to keep (already sorted by fit upstream).",
    )
    parser.add_argument(
        "--min-priority",
        default="medium",
        choices=["low", "medium", "high"],
        help="Minimum priority to include.",
    )
    args = parser.parse_args()

    priority_order = {"low": 1, "medium": 2, "high": 3}
    min_rank = priority_order[args.min_priority]

    input_path = Path(args.input)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with input_path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    filtered = []
    for row in rows:
        prio = (row.get("priority") or "low").lower()
        if priority_order.get(prio, 1) < min_rank:
            continue
        filtered.append(row)

    # Keep top N from already-ranked discovery output.
    filtered = filtered[: args.top_n]

    output_rows = []
    for row in filtered:
        output_rows.append(
            {
                "company": row.get("company", ""),
                "role_title": row.get("role_title", ""),
                "job_url": row.get("url", ""),
                "location": row.get("location", ""),
                "hiring_manager": "",
                "contact_channel": to_contact_channel(row.get("remote_signal", "")),
                "job_description_snippet": row.get("snippet", ""),
                "priority": row.get("priority", "medium"),
            }
        )

    fieldnames = [
        "company",
        "role_title",
        "job_url",
        "location",
        "hiring_manager",
        "contact_channel",
        "job_description_snippet",
        "priority",
    ]

    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in output_rows:
            writer.writerow(row)

    print(f"Built {len(output_rows)} target rows -> {output_path}")


if __name__ == "__main__":
    main()
