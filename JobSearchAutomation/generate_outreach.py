#!/usr/bin/env python3
"""
Generate personalized first-touch outreach drafts from a job/company target CSV.

This script does not send messages. It creates drafts so you can move quickly
without looking like bulk spam.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_SKILL_KEYWORDS = {
    "agent_systems": [
        "agent",
        "agentic",
        "workflow orchestration",
        "tool calling",
        "langchain",
        "langgraph",
        "multi-step",
    ],
    "production_ai": [
        "production",
        "reliability",
        "latency",
        "observability",
        "monitoring",
        "evaluation",
        "eval",
        "quality",
        "safety",
    ],
    "data_pipelines": [
        "pipeline",
        "ingestion",
        "classification",
        "ranking",
        "dedup",
        "embeddings",
        "vector",
        "rag",
    ],
    "security_intel": [
        "security",
        "threat",
        "trust",
        "safety",
        "risk",
        "intelligence",
        "incident",
        "compliance",
    ],
    "automation_ops": [
        "automation",
        "operational",
        "operations",
        "ci/cd",
        "github actions",
        "unattended",
        "efficiency",
    ],
}


@dataclass
class Evidence:
    text: str
    tags: list[str]


def load_profile(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def normalize_text(value: str) -> str:
    value = value.lower()
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def keyword_hits(text: str, keywords: list[str]) -> int:
    return sum(1 for kw in keywords if kw in text)


def compute_fit_score(text: str, profile: dict[str, Any]) -> tuple[int, dict[str, int]]:
    config = profile.get("skill_keywords", DEFAULT_SKILL_KEYWORDS)
    breakdown: dict[str, int] = {}
    score = 0
    for bucket, terms in config.items():
        hits = keyword_hits(text, [normalize_text(t) for t in terms])
        breakdown[bucket] = hits
        score += hits
    return score, breakdown


def select_evidence(
    fit_text: str,
    evidence_items: list[Evidence],
    max_items: int = 3,
) -> list[str]:
    scored: list[tuple[int, str]] = []
    for item in evidence_items:
        score = sum(1 for t in item.tags if t.lower() in fit_text)
        scored.append((score, item.text))
    scored.sort(key=lambda x: x[0], reverse=True)

    selected = [text for _, text in scored[:max_items] if text]
    if len(selected) < max_items:
        seen = set(selected)
        for item in evidence_items:
            if item.text not in seen:
                selected.append(item.text)
                seen.add(item.text)
            if len(selected) >= max_items:
                break
    return selected[:max_items]


def build_email(
    profile: dict[str, Any],
    row: dict[str, str],
    evidence_lines: list[str],
) -> tuple[str, str]:
    name = profile["name"]
    headline = profile["headline"]
    linkedin = profile.get("linkedin", "")
    email = profile.get("email", "")

    company = row.get("company", "").strip()
    role = row.get("role_title", "").strip()
    manager = row.get("hiring_manager", "").strip()
    manager_line = f"Hi {manager}," if manager else "Hi team,"

    subject = f"{name} | Applied AI builder fit for {company}"
    body = (
        f"{manager_line}\n\n"
        f"I am reaching out about the {role} opportunity at {company}. "
        f"I build production AI workflows that reduce analyst and operations load, "
        f"and your role looks tightly aligned with my background.\n\n"
        f"Relevant execution signal:\n"
        f"- {evidence_lines[0]}\n"
        f"- {evidence_lines[1]}\n"
        f"- {evidence_lines[2]}\n\n"
        f"I would value a short conversation to see if my profile matches your current priorities.\n\n"
        f"{name}\n"
        f"{headline}\n"
        f"{linkedin}\n"
        f"{email}\n"
    )
    return subject, body


def build_linkedin_dm(
    profile: dict[str, Any],
    row: dict[str, str],
    evidence_line: str,
) -> str:
    company = row.get("company", "").strip()
    role = row.get("role_title", "").strip()
    return (
        f"Hi - I am interested in the {role} role at {company}. "
        f"I have been building production AI automation systems with measurable impact "
        f"({evidence_line}). Would you be open to a brief chat about fit?"
    )


def read_targets(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_markdown(path: Path, rows: list[dict[str, str]]) -> None:
    lines: list[str] = ["# Outreach Drafts", ""]
    for i, row in enumerate(rows, start=1):
        lines.extend(
            [
                f"## {i}. {row.get('company', '')} - {row.get('role_title', '')}",
                "",
                f"- Fit score: **{row.get('fit_score', '')}**",
                f"- Job URL: {row.get('job_url', '')}",
                f"- Priority: {row.get('priority', '')}",
                "",
                "### Subject",
                "",
                row.get("subject", ""),
                "",
                "### Email Draft",
                "",
                "```text",
                row.get("email_body", ""),
                "```",
                "",
                "### LinkedIn DM Draft",
                "",
                "```text",
                row.get("linkedin_dm", ""),
                "```",
                "",
                "---",
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def build_tracker_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    tracker = []
    for row in rows:
        tracker.append(
            {
                "company": row.get("company", ""),
                "role_title": row.get("role_title", ""),
                "job_url": row.get("job_url", ""),
                "location": row.get("location", ""),
                "priority": row.get("priority", ""),
                "fit_score": row.get("fit_score", ""),
                "status": "not_sent",
                "last_touch_date": "",
                "next_action": "Send first-touch message",
                "notes": "",
            }
        )
    return tracker


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate outreach drafts from job targets CSV.")
    parser.add_argument("--profile", required=True, help="Path to profile JSON.")
    parser.add_argument("--input", required=True, help="Path to target jobs CSV.")
    parser.add_argument(
        "--outdir",
        default="JobSearchAutomation/output",
        help="Output directory for generated files.",
    )
    args = parser.parse_args()

    profile_path = Path(args.profile)
    input_path = Path(args.input)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    profile = load_profile(profile_path)
    evidence_items = [
        Evidence(text=item["text"], tags=item.get("tags", []))
        for item in profile.get("evidence", [])
    ]
    targets = read_targets(input_path)

    enriched_rows: list[dict[str, str]] = []
    for row in targets:
        fit_text = normalize_text(
            " ".join(
                [
                    row.get("role_title", ""),
                    row.get("job_description_snippet", ""),
                    row.get("company", ""),
                ]
            )
        )
        fit_score, breakdown = compute_fit_score(fit_text, profile)
        evidence_lines = select_evidence(fit_text, evidence_items, max_items=3)
        subject, email_body = build_email(profile, row, evidence_lines)
        linkedin_dm = build_linkedin_dm(profile, row, evidence_lines[0])

        output_row = dict(row)
        output_row["fit_score"] = str(fit_score)
        output_row["fit_breakdown"] = json.dumps(breakdown, ensure_ascii=True)
        output_row["subject"] = subject
        output_row["email_body"] = email_body
        output_row["linkedin_dm"] = linkedin_dm
        enriched_rows.append(output_row)

    enriched_rows.sort(key=lambda r: int(r.get("fit_score", "0")), reverse=True)

    draft_csv_path = outdir / "outreach_drafts.csv"
    markdown_path = outdir / "outreach_drafts.md"
    tracker_path = outdir / "application_tracker.csv"

    fieldnames = list(enriched_rows[0].keys()) if enriched_rows else [
        "company",
        "role_title",
        "job_url",
        "location",
        "hiring_manager",
        "contact_channel",
        "job_description_snippet",
        "priority",
        "fit_score",
        "fit_breakdown",
        "subject",
        "email_body",
        "linkedin_dm",
    ]

    write_csv(draft_csv_path, enriched_rows, fieldnames)
    write_markdown(markdown_path, enriched_rows)
    tracker_rows = build_tracker_rows(enriched_rows)
    tracker_fields = list(tracker_rows[0].keys()) if tracker_rows else [
        "company",
        "role_title",
        "job_url",
        "location",
        "priority",
        "fit_score",
        "status",
        "last_touch_date",
        "next_action",
        "notes",
    ]
    write_csv(tracker_path, tracker_rows, tracker_fields)

    print(f"Generated: {draft_csv_path}")
    print(f"Generated: {markdown_path}")
    print(f"Generated: {tracker_path}")
    print("Review drafts before sending to avoid low-quality bulk outreach.")


if __name__ == "__main__":
    main()
