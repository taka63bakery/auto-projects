# Job Search Outbound Automation

This kit automates your initial outreach drafting while keeping quality high.

## What It Does

- Ingests a CSV of target roles/companies.
- Scores each role description against your applied-AI fit keywords.
- Auto-generates:
  - `outreach_drafts.csv` (ranked by fit score)
  - `outreach_drafts.md` (easy-to-read message drafts)
  - `application_tracker.csv` (status workflow)
- Can auto-discover roles from public ATS APIs (Greenhouse + Lever) into a triage CSV.

It does **not** send messages automatically. That is intentional so you keep signal quality and avoid low-quality spam patterns.

## Files

- `generate_outreach.py` - draft generation engine
- `discover_jobs.py` - web job discovery (Greenhouse + Lever APIs)
- `profile.json` - your positioning and evidence bullets
- `targets_template.csv` - seed target list
- `sources_template.json` - companies/boards to scan

## Quick Start

1. Update `profile.json`:
   - set your real email + LinkedIn
   - tweak evidence bullets if needed
2. Copy `targets_template.csv` and add more roles.
3. Run:

```bash
python JobSearchAutomation/generate_outreach.py --profile JobSearchAutomation/profile.json --input JobSearchAutomation/targets_template.csv --outdir JobSearchAutomation/output
```

4. Open generated files:
   - `JobSearchAutomation/output/outreach_drafts.md`
   - `JobSearchAutomation/output/application_tracker.csv`

## Auto-Find Jobs From Web

Run:

```bash
python JobSearchAutomation/discover_jobs.py --profile JobSearchAutomation/profile.json --sources JobSearchAutomation/sources_template.json --output JobSearchAutomation/output/discovered_jobs.csv --location-mode remote_us_canada_hybrid --min-fit-score 3
```

This outputs `discovered_jobs.csv` with:
- source (`greenhouse` or `lever`)
- role title, company, location, URL
- remote signal (`remote_us`, `remote_canada`, `hybrid`, etc.)
- fit score and fit breakdown

Then triage and copy selected rows into `targets_template.csv`, and run `generate_outreach.py`.

## One-Command Local Pipeline

Run discovery + conversion + outreach generation in one shot:

```bash
python JobSearchAutomation/run_pipeline.py --profile JobSearchAutomation/profile.json --sources JobSearchAutomation/sources_template.json --outdir JobSearchAutomation/output --location-mode remote_us_canada_hybrid --min-fit-score 4 --top-n 50 --min-priority medium
```

This produces:
- `discovered_jobs.csv`
- `auto_targets.csv`
- `outreach_drafts.csv`
- `outreach_drafts.md`
- `application_tracker.csv`

## Free GitHub Hosting/Automation

This repo now includes a GitHub Actions workflow:
- `.github/workflows/job-search-pipeline.yml`

What it does:
- runs daily (and manually on demand)
- executes the full pipeline
- generates a competitive-fit daily digest
- emails the digest to `kageishota@gmail.com` (if SMTP secrets are configured)
- uploads outputs as an artifact called `job-search-output`

How to use:
1. Push this folder/repo to GitHub.
2. Open GitHub `Actions` tab.
3. Run `Job Search Pipeline` manually once to validate.
4. Download `job-search-output` artifact from each run.

### Email Setup (Required Once)

In GitHub repo settings, add these Actions secrets:
- `SMTP_SERVER` (example: `smtp.gmail.com`)
- `SMTP_PORT` (usually `587`)
- `SMTP_USERNAME` (your sending email)
- `SMTP_PASSWORD` (app password or SMTP password)
- `EMAIL_FROM` (optional sender address; defaults to `kageishota@gmail.com`)

For Gmail:
- enable 2FA on the sender account
- create an App Password
- use that app password as `SMTP_PASSWORD`

## Recommended Usage Model

- Send 10-20 first touches per batch.
- Manually review each message for 20-30 seconds before sending.
- Track replies and follow-ups in `application_tracker.csv`.
- Run daily with new targets.

## High-Conversion Process

- Prioritize rows with highest `fit_score`.
- Use LinkedIn DM for warm intros and email for direct manager outreach.
- Follow up once after 4-5 business days.
- Keep every message short and metric-driven.

## Next Upgrade (Optional)

If you want, extend this with:
- direct Greenhouse/Lever/Ashby job scrape ingestion
- automatic company research snippets
- one-click Gmail draft creation via API

