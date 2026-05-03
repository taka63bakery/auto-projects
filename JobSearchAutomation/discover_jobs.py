#!/usr/bin/env python3
"""
Discover jobs from public ATS APIs (Greenhouse + Lever), then filter/rank for fit.

Outputs a CSV you can triage quickly before strategic applications.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


USER_AGENT = "Mozilla/5.0 (compatible; JobDiscoveryBot/1.0)"


@dataclass
class JobRecord:
    company: str
    source: str
    role_title: str
    location: str
    remote_signal: str
    url: str
    snippet: str
    fit_score: int
    fit_breakdown: str
    priority: str


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def normalize(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip().lower()


def fetch_json(url: str) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def text_from_greenhouse_job(job: dict[str, Any]) -> str:
    content = job.get("content", "") or ""
    clean = re.sub(r"<[^>]+>", " ", content)
    return normalize(html.unescape(clean))


def text_from_lever_job(job: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("descriptionPlain", "description", "additionalPlain"):
        if isinstance(job.get(key), str):
            val = job[key]
            val = re.sub(r"<[^>]+>", " ", val)
            parts.append(html.unescape(val))
    lists = job.get("lists", [])
    if isinstance(lists, list):
        for item in lists:
            txt = item.get("text", "")
            if txt:
                parts.append(html.unescape(re.sub(r"<[^>]+>", " ", txt)))
    return normalize(" ".join(parts))


def compute_fit_score(text: str, profile: dict[str, Any]) -> tuple[int, dict[str, int]]:
    keywords = profile.get("skill_keywords", {})
    score = 0
    breakdown: dict[str, int] = {}
    for bucket, terms in keywords.items():
        bucket_hits = 0
        for term in terms:
            t = normalize(str(term))
            if t and t in text:
                bucket_hits += 1
        breakdown[bucket] = bucket_hits
        score += bucket_hits
    return score, breakdown


def remote_signal(location: str, text: str) -> str:
    haystack = normalize(location + " " + text)
    if "remote" in haystack and ("us" in haystack or "united states" in haystack):
        return "remote_us"
    if "remote" in haystack and "canada" in haystack:
        return "remote_canada"
    if "remote" in haystack and ("us or canada" in haystack or "u.s. or canada" in haystack):
        return "remote_us_canada"
    if "remote" in haystack:
        return "remote"
    if "hybrid" in haystack:
        return "hybrid"
    return "other"


def passes_location_filter(signal: str, location_mode: str) -> bool:
    if location_mode == "any":
        return True
    if location_mode == "remote_us_canada_hybrid":
        return signal in {
            "remote_us",
            "remote_canada",
            "remote_us_canada",
            "remote",
            "hybrid",
        }
    if location_mode == "remote_only":
        return signal in {"remote_us", "remote_canada", "remote_us_canada", "remote"}
    return True


def priority_from_score(score: int) -> str:
    if score >= 8:
        return "high"
    if score >= 4:
        return "medium"
    return "low"


def truncate(text: str, max_len: int = 280) -> str:
    text = text.strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def discover_greenhouse(
    board_tokens: list[str],
    profile: dict[str, Any],
    location_mode: str,
) -> list[JobRecord]:
    records: list[JobRecord] = []
    for token in board_tokens:
        token = token.strip()
        if not token:
            continue
        url = f"https://boards-api.greenhouse.io/v1/boards/{urllib.parse.quote(token)}/jobs?content=true"
        try:
            payload = fetch_json(url)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            print(f"[warn] Greenhouse fetch failed for {token}: {exc}", file=sys.stderr)
            continue

        for job in payload.get("jobs", []):
            title = job.get("title", "").strip()
            location = (job.get("location") or {}).get("name", "").strip()
            absolute_url = job.get("absolute_url", "").strip()
            company = token
            job_text = text_from_greenhouse_job(job)
            signal = remote_signal(location, job_text)
            if not passes_location_filter(signal, location_mode):
                continue
            fit, breakdown = compute_fit_score(normalize(title + " " + job_text), profile)
            records.append(
                JobRecord(
                    company=company,
                    source="greenhouse",
                    role_title=title,
                    location=location,
                    remote_signal=signal,
                    url=absolute_url,
                    snippet=truncate(job_text),
                    fit_score=fit,
                    fit_breakdown=json.dumps(breakdown, ensure_ascii=True),
                    priority=priority_from_score(fit),
                )
            )
    return records


def discover_lever(
    lever_sites: list[str],
    profile: dict[str, Any],
    location_mode: str,
) -> list[JobRecord]:
    records: list[JobRecord] = []
    for site in lever_sites:
        site = site.strip()
        if not site:
            continue
        url = f"https://api.lever.co/v0/postings/{urllib.parse.quote(site)}?mode=json"
        try:
            payload = fetch_json(url)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            print(f"[warn] Lever fetch failed for {site}: {exc}", file=sys.stderr)
            continue

        if not isinstance(payload, list):
            continue
        for job in payload:
            title = (job.get("text") or "").strip()
            categories = job.get("categories") or {}
            location = (categories.get("location") or "").strip()
            hosted = (job.get("hostedUrl") or "").strip()
            company = site
            job_text = text_from_lever_job(job)
            signal = remote_signal(location, job_text)
            if not passes_location_filter(signal, location_mode):
                continue
            fit, breakdown = compute_fit_score(normalize(title + " " + job_text), profile)
            records.append(
                JobRecord(
                    company=company,
                    source="lever",
                    role_title=title,
                    location=location,
                    remote_signal=signal,
                    url=hosted,
                    snippet=truncate(job_text),
                    fit_score=fit,
                    fit_breakdown=json.dumps(breakdown, ensure_ascii=True),
                    priority=priority_from_score(fit),
                )
            )
    return records


def filter_by_inclusion_terms(
    rows: list[JobRecord],
    include_terms: list[str],
    include_title_terms: list[str],
    exclude_title_terms: list[str],
    min_fit_score: int,
) -> list[JobRecord]:
    include_title = [normalize(t) for t in include_title_terms if normalize(t)]
    exclude_title = [normalize(t) for t in exclude_title_terms if normalize(t)]
    include = [normalize(t) for t in include_terms if normalize(t)]

    out: list[JobRecord] = []
    for row in rows:
        hay = normalize(f"{row.role_title} {row.snippet}")
        title = normalize(row.role_title)
        if row.fit_score < min_fit_score:
            continue
        if exclude_title and any(t in title for t in exclude_title):
            continue
        if include_title and not any(t in title for t in include_title):
            continue
        if include and not any(t in hay for t in include):
            continue
        out.append(row)
    return out


def cap_per_company(rows: list[JobRecord], max_per_company: int) -> list[JobRecord]:
    if max_per_company <= 0:
        return rows
    by_company: dict[str, int] = {}
    selected: list[JobRecord] = []
    for row in rows:
        count = by_company.get(row.company, 0)
        if count >= max_per_company:
            continue
        selected.append(row)
        by_company[row.company] = count + 1
    return selected


def write_csv(path: Path, rows: list[JobRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "company",
                "source",
                "role_title",
                "location",
                "remote_signal",
                "url",
                "snippet",
                "fit_score",
                "fit_breakdown",
                "priority",
            ],
        )
        writer.writeheader()
        for r in rows:
            writer.writerow(
                {
                    "company": r.company,
                    "source": r.source,
                    "role_title": r.role_title,
                    "location": r.location,
                    "remote_signal": r.remote_signal,
                    "url": r.url,
                    "snippet": r.snippet,
                    "fit_score": r.fit_score,
                    "fit_breakdown": r.fit_breakdown,
                    "priority": r.priority,
                }
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover jobs from ATS APIs.")
    parser.add_argument("--profile", required=True, help="Path to profile JSON.")
    parser.add_argument("--sources", required=True, help="Path to ATS sources JSON.")
    parser.add_argument(
        "--output",
        default="JobSearchAutomation/output/discovered_jobs.csv",
        help="Output CSV path.",
    )
    parser.add_argument(
        "--location-mode",
        default="remote_us_canada_hybrid",
        choices=["remote_us_canada_hybrid", "remote_only", "any"],
        help="Location filtering mode.",
    )
    parser.add_argument(
        "--min-fit-score",
        type=int,
        default=3,
        help="Minimum fit score to include.",
    )
    args = parser.parse_args()

    profile = load_json(Path(args.profile))
    sources = load_json(Path(args.sources))
    greenhouse_tokens = sources.get("greenhouse_boards", [])
    lever_sites = sources.get("lever_sites", [])
    include_terms = sources.get("include_terms", [])
    include_title_terms = sources.get("include_title_terms", [])
    exclude_title_terms = sources.get("exclude_title_terms", [])
    max_per_company = int(sources.get("max_per_company", 25))

    all_rows: list[JobRecord] = []
    all_rows.extend(discover_greenhouse(greenhouse_tokens, profile, args.location_mode))
    all_rows.extend(discover_lever(lever_sites, profile, args.location_mode))

    # Deduplicate by URL then by title+company
    dedup: dict[str, JobRecord] = {}
    for row in all_rows:
        key = row.url.strip() or f"{row.company}::{row.role_title}".lower()
        existing = dedup.get(key)
        if not existing or row.fit_score > existing.fit_score:
            dedup[key] = row
    rows = list(dedup.values())
    rows = filter_by_inclusion_terms(
        rows,
        include_terms,
        include_title_terms,
        exclude_title_terms,
        args.min_fit_score,
    )
    rows.sort(key=lambda r: r.fit_score, reverse=True)
    rows = cap_per_company(rows, max_per_company)

    out_path = Path(args.output)
    write_csv(out_path, rows)
    print(f"Discovered {len(rows)} jobs -> {out_path}")
    print("Next: copy top rows into targets CSV, then run generate_outreach.py")


if __name__ == "__main__":
    main()
