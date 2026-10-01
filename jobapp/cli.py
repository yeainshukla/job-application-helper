"""Command-line interface for a private, local job application tracker."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import uuid
import webbrowser
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

STATUSES = ("saved", "preparing", "submitted", "confirmation_unverified", "interview", "rejected", "withdrawn", "not_pursuing")
FIELDS = (
    "id", "created", "company", "role", "url", "status", "resume_path",
    "cover_letter_path", "follow_up_date", "notes",
)
PROFILE_TEMPLATE = {
    "full_name": "",
    "first_name": "",
    "last_name": "",
    "preferred_name": "",
    "email": "",
    "phone": "",
    "city": "",
    "state": "",
    "zip_code": "",
    "address_line1": "",
    "address_line2": "",
    "linkedin_url": "",
    "github_url": "",
    "portfolio_url": "",
    "current_company": "",
    "current_title": "",
    "work_authorization": "",
    "requires_sponsorship": None,
    "resume_path": "",
    "cover_letter_path": "",
    "skills": [],
}
SETTINGS_TEMPLATE = {
    "job_sources": {"greenhouse": [], "ashby": [], "lever": []},
    "search_preferences": {
        "role_keywords": ["software engineer", "software developer", "backend engineer", "full stack", "machine learning engineer", "data engineer", "platform engineer"],
        "location_keywords": [],
        "allow_location_mismatch": True,
        "posted_within_days": 14,
        "minimum_match_score": 0,
        "max_results": 100,
        "sponsorship_required": False,
        "include_public_remote_feeds": True,
        "search_queries": ["software engineer", "backend engineer", "machine learning engineer", "data engineer"],
    },
    "application_answers": {},
}


def default_data_dir() -> Path:
    override = os.environ.get("JOBAPP_DATA_DIR")
    return Path(override).expanduser() if override else Path.home() / ".job-application-helper"


def profile_path(data_dir: Path) -> Path:
    return data_dir / "profile.json"


def tracker_path(data_dir: Path) -> Path:
    return data_dir / "applications.csv"


def initialize(data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    if not profile_path(data_dir).exists():
        profile_path(data_dir).write_text(json.dumps(PROFILE_TEMPLATE, indent=2) + "\n", encoding="utf-8")
    if not tracker_path(data_dir).exists():
        with tracker_path(data_dir).open("w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=FIELDS).writeheader()
    settings_path = data_dir / "settings.json"
    if not settings_path.exists():
        settings_path.write_text(json.dumps(SETTINGS_TEMPLATE, indent=2) + "\n", encoding="utf-8")
    print(f"Initialized private application data in: {data_dir}")
    print(f"Edit your profile: {profile_path(data_dir)}")
    print(f"Edit search sources and preferences: {settings_path}")


def read_profile(data_dir: Path) -> dict:
    path = profile_path(data_dir)
    if not path.exists():
        raise SystemExit(f"Profile not found. Run `jobapp init` first (looked in {data_dir}).")
    try:
        profile = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(profile, dict):
        raise SystemExit(f"Profile must be a JSON object: {path}")
    return profile


def read_rows(data_dir: Path) -> list[dict[str, str]]:
    path = tracker_path(data_dir)
    if not path.exists():
        raise SystemExit(f"Tracker not found. Run `jobapp init` first (looked in {data_dir}).")
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_rows(data_dir: Path, rows: list[dict[str, str]]) -> None:
    with tracker_path(data_dir).open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def valid_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def command_add(args: argparse.Namespace) -> None:
    rows = read_rows(args.data_dir)
    if not valid_url(args.url):
        raise SystemExit("Job URL must start with http:// or https://")
    duplicate = next((r for r in rows if r.get("url") == args.url), None)
    if duplicate:
        print(f"Already tracked as {duplicate['id']}: {duplicate['company']} — {duplicate['role']}")
        return
    row = {
        "id": uuid.uuid4().hex[:8], "created": date.today().isoformat(),
        "company": args.company, "role": args.role, "url": args.url,
        "status": "saved", "resume_path": args.resume or "",
        "cover_letter_path": args.cover_letter or "",
        "follow_up_date": "", "notes": args.notes or "",
    }
    rows.append(row)
    write_rows(args.data_dir, rows)
    print(f"Added {row['id']}: {row['company']} — {row['role']}")


def command_list(args: argparse.Namespace) -> None:
    rows = read_rows(args.data_dir)
    if args.status:
        rows = [r for r in rows if r.get("status") == args.status]
    if not rows:
        print("No applications found.")
        return
    print(f"{'ID':8} {'STATUS':14} {'COMPANY':24} ROLE")
    for r in rows:
        print(f"{r.get('id','')[:8]:8} {r.get('status','')[:14]:14} {r.get('company','')[:24]:24} {r.get('role','')}")


def find_row(rows: list[dict[str, str]], app_id: str) -> dict[str, str]:
    row = next((r for r in rows if r.get("id") == app_id), None)
    if not row:
        raise SystemExit(f"Application ID not found: {app_id}")
    return row


def command_status(args: argparse.Namespace) -> None:
    rows = read_rows(args.data_dir)
    row = find_row(rows, args.id)
    row["status"] = args.status
    if args.follow_up:
        row["follow_up_date"] = args.follow_up
    if args.notes is not None:
        row["notes"] = args.notes
    write_rows(args.data_dir, rows)
    print(f"Updated {row['id']} to {row['status']}.")


def command_prepare(args: argparse.Namespace) -> None:
    profile = read_profile(args.data_dir)
    rows = read_rows(args.data_dir)
    row = find_row(rows, args.id)
    print(f"Application prep: {row['company']} — {row['role']} ({row['id']})")
    print(f"Job URL: {row['url']}")
    print("\nProfile details (review each field before using it):")
    for key, label in (
        ("full_name", "Full name"), ("preferred_name", "Preferred name"),
        ("email", "Email"), ("phone", "Phone"), ("city_region", "Location"),
        ("linkedin_url", "LinkedIn"), ("portfolio_url", "Portfolio"),
        ("work_authorization_summary", "Work authorization"),
        ("requires_sponsorship", "Requires sponsorship"),
    ):
        value = profile.get(key)
        print(f"- {label}: {value if value not in (None, '') else '[not provided]'}")
    print("\nFiles to attach yourself:")
    for label, key in (("Resume", "resume_path"), ("Cover letter", "cover_letter_path")):
        value = row.get(key) or profile.get(key)
        print(f"- {label}: {value or '[choose a file if required]'}")
    print("\nBefore submitting: verify job details, every answer, file attachments, consent, and employer-specific questions.")
    print("This checklist command does not fill or submit the employer form.")


def command_open(args: argparse.Namespace) -> None:
    rows = read_rows(args.data_dir)
    row = find_row(rows, args.id)
    opened = webbrowser.open(row["url"])
    print(f"Opened job page: {row['url']}" if opened else f"Open this job page: {row['url']}")
    print("Complete and submit the employer form yourself after reviewing every field.")


def command_search(args: argparse.Namespace) -> None:
    from .search import search_jobs

    profile = read_profile(args.data_dir)
    settings_path = args.data_dir / "settings.json"
    if not settings_path.exists():
        raise SystemExit("Settings not found. Run `jobapp init` first.")
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    results = search_jobs(args.data_dir, profile, settings)
    if not results:
        print("No matching recent jobs found. Add employer ATS board names to settings.json, or adjust search preferences.")
        return
    rows = read_rows(args.data_dir)
    known_urls = {row.get("url") for row in rows}
    for result in results:
        if result["url"] not in known_urls:
            rows.append({"id": result["id"], "created": date.today().isoformat(), "company": result["company"],
                         "role": result["role"], "url": result["url"], "status": "saved",
                         "resume_path": str(profile.get("resume_path") or ""), "cover_letter_path": "",
                         "follow_up_date": "", "notes": f"Found via {result['provider']}; match {result['fit_score']}%"})
    write_rows(args.data_dir, rows)
    print(f"Found {len(results)} recent matching jobs (saved to {args.data_dir / 'search_results.json'}):")
    print(f"{'ID':14} {'MATCH':>5} {'POSTED':12} {'COMPANY':24} ROLE")
    for row in results:
        print(f"{row['id']:14} {row['fit_score']:>4}% {row['posted_date']:12} {row['company'][:24]:24} {row['role']}")


def command_apply(args: argparse.Namespace) -> None:
    from .apply import apply_to_job

    apply_to_job(args.data_dir, args.id, submit=args.submit)


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jobapp", description="Private, local-first job application organizer")
    parser.add_argument("--data-dir", type=Path, default=default_data_dir(), help="Private data directory (default: ~/.job-application-helper)")
    commands = parser.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init", help="Create your private profile and application tracker")
    init.set_defaults(func=lambda a: initialize(a.data_dir))

    add = commands.add_parser("add", help="Track a job opening")
    add.add_argument("--company", required=True)
    add.add_argument("--role", required=True)
    add.add_argument("--url", required=True)
    add.add_argument("--resume", help="Local path to the resume you plan to use")
    add.add_argument("--cover-letter", help="Local path to the cover letter you plan to use")
    add.add_argument("--notes", help="Private notes stored only in your local tracker")
    add.set_defaults(func=command_add)

    listing = commands.add_parser("list", help="List tracked applications")
    listing.add_argument("--status", choices=STATUSES)
    listing.set_defaults(func=command_list)

    status = commands.add_parser("status", help="Update an application status")
    status.add_argument("id")
    status.add_argument("status", choices=STATUSES)
    status.add_argument("--follow-up", help="Follow-up date, e.g. 2026-10-15")
    status.add_argument("--notes", help="Replace private notes for this application")
    status.set_defaults(func=command_status)

    prep = commands.add_parser("prepare", help="Print your profile and a submission review checklist")
    prep.add_argument("id")
    prep.set_defaults(func=command_prepare)

    open_cmd = commands.add_parser("open", help="Open the employer job page in your browser")
    open_cmd.add_argument("id")
    open_cmd.set_defaults(func=command_open)

    search = commands.add_parser("search", help="Search recent Greenhouse, Ashby, and Lever listings and rank them")
    search.set_defaults(func=command_search)

    apply = commands.add_parser("apply", help="Open a matching ATS form and prepare profile fields for your review")
    apply.add_argument("id")
    apply.add_argument("--submit", action="store_true", help="Offer a final terminal confirmation before clicking Submit")
    apply.set_defaults(func=command_apply)
    return parser


def main() -> None:
    parser = make_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except (OSError, csv.Error) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
