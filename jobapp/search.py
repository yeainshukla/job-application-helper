"""Fetch and rank recent listings from public Greenhouse, Ashby, and Lever boards."""

from __future__ import annotations

import html
import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path


def fetch_json(url: str) -> dict | list | None:
    request = urllib.request.Request(url, headers={"User-Agent": "JobApplicationHelper/0.1 (public job board APIs)"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            if response.status != 200:
                return None
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def plain(value: str | None) -> str:
    value = html.unescape(value or "")
    return re.sub(r"\s+", " ", re.sub(r"<[^>]*>", " ", value)).strip()


def parse_date(value: str | int | None) -> datetime | None:
    if not value:
        return None
    try:
        if isinstance(value, int):
            return datetime.fromtimestamp(value / 1000 if value > 10_000_000_000 else value, timezone.utc)
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed
    except (ValueError, OverflowError, OSError):
        return None


def configured_slugs(config: dict, provider: str) -> list[str]:
    value = (config.get("job_sources") or {}).get(provider, [])
    return [str(item).strip() for item in value if str(item).strip()]


def base_job(company: str, role: str, location: str, provider: str, posted: str, url: str, description: str) -> dict:
    return {"company": company, "role": role, "location": location, "provider": provider,
            "posted_at": posted, "url": url, "description": plain(description)}


def fetch_greenhouse(slug: str) -> list[dict]:
    data = fetch_json(f"https://boards-api.greenhouse.io/v1/boards/{urllib.parse.quote(slug)}/jobs?content=true")
    if not isinstance(data, dict):
        return []
    return [base_job(plain(row.get("company_name")) or slug, plain(row.get("title")),
                     plain((row.get("location") or {}).get("name")), "greenhouse",
                     row.get("first_published") or row.get("updated_at") or "", row.get("absolute_url", ""),
                     row.get("content", "")) for row in data.get("jobs", [])]


def fetch_ashby(slug: str) -> list[dict]:
    data = fetch_json(f"https://api.ashbyhq.com/posting-api/job-board/{urllib.parse.quote(slug)}")
    if not isinstance(data, dict):
        return []
    jobs = []
    for row in data.get("jobs", []):
        if not row.get("isListed", True):
            continue
        locations = [plain(row.get("location", ""))] + [plain(x) for x in row.get("secondaryLocations", [])]
        jobs.append(base_job(slug, plain(row.get("title")), "; ".join(x for x in locations if x),
                             "ashby", row.get("publishedAt", ""), row.get("applyUrl") or row.get("jobUrl", ""),
                             row.get("descriptionPlain") or row.get("descriptionHtml", "")))
    return jobs


def fetch_lever(slug: str) -> list[dict]:
    data = fetch_json(f"https://api.lever.co/v0/postings/{urllib.parse.quote(slug)}?mode=json")
    if not isinstance(data, list):
        return []
    jobs = []
    for row in data:
        categories = row.get("categories") or {}
        description = " ".join(row.get(key, "") or "" for key in ("descriptionPlain", "descriptionBodyPlain", "additionalPlain"))
        jobs.append(base_job(slug, plain(row.get("text")), plain(categories.get("location", "")),
                             "lever", row.get("createdAt", ""), row.get("applyUrl") or row.get("hostedUrl", ""), description))
    return jobs


def fetch_remote_feeds(queries: list[str]) -> list[dict]:
    jobs: list[dict] = []
    seen: set[str] = set()
    for query in queries[:12]:
        encoded = urllib.parse.quote(query)
        remotive = fetch_json(f"https://remotive.com/api/remote-jobs?search={encoded}")
        if isinstance(remotive, dict):
            for row in remotive.get("jobs", []):
                url = row.get("url", "")
                if url and url not in seen:
                    seen.add(url)
                    jobs.append(base_job(plain(row.get("company_name")), plain(row.get("title")),
                                         plain(row.get("candidate_required_location") or "Remote"), "remotive",
                                         row.get("publication_date", ""), url, row.get("description", "")))
    remoteok = fetch_json("https://remoteok.com/api")
    if isinstance(remoteok, list):
        for row in remoteok:
            if not isinstance(row, dict) or not row.get("position"):
                continue
            url = row.get("url") or row.get("apply_url", "")
            if not url or url in seen:
                continue
            seen.add(url)
            jobs.append(base_job(plain(row.get("company")), plain(row.get("position")),
                                 plain(row.get("location") or "Remote"), "remoteok", row.get("date", ""),
                                 url, row.get("description", "")))
    return jobs


def score(job: dict, profile: dict, prefs: dict) -> tuple[int, list[str], list[str]]:
    title = job["role"].lower()
    text = f"{title} {job['description']}".lower()
    role_terms = [str(x).lower() for x in prefs.get("role_keywords", []) if str(x).strip()]
    negative = [str(x).lower() for x in prefs.get("exclude_keywords", []) if str(x).strip()]
    if role_terms and not any(term in title for term in role_terms):
        return 0, [], ["title does not match configured role keywords"]
    blocked = [term for term in negative if term in text]
    if blocked:
        return 0, [], ["excluded keyword: " + ", ".join(blocked[:5])]
    skills = [str(x).lower() for x in profile.get("skills", []) if str(x).strip()]
    hits = [skill for skill in skills if skill in text]
    score_value = min(100, 50 + min(30, len(hits) * 5))
    location_terms = [str(x).lower() for x in prefs.get("location_keywords", []) if str(x).strip()]
    if location_terms:
        if any(term in job["location"].lower() for term in location_terms):
            score_value = min(100, score_value + 10)
        elif not prefs.get("allow_location_mismatch", False):
            return 0, hits, ["location does not match configured location keywords"]
    if prefs.get("sponsorship_required") and re.search(
        r"(will not|cannot|unable to|does not|no)\s+(provide\s+)?(future\s+)?visa sponsorship|without sponsorship|must be (a )?u\.?s\.? citizen|citizenship required|active (top secret |secret )?clearance|u\.?s\.? person status|itar",
        text,
    ):
        return 0, hits, ["possible sponsorship, citizenship, or export-control blocker; review manually"]
    return score_value, hits, []


def search_jobs(data_dir: Path, profile: dict, config: dict) -> list[dict]:
    prefs = config.get("search_preferences", {})
    days = max(1, int(prefs.get("posted_within_days", 14)))
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    limit = max(1, min(500, int(prefs.get("max_results", 100))))
    providers = (("greenhouse", fetch_greenhouse), ("ashby", fetch_ashby), ("lever", fetch_lever))
    raw: list[dict] = []
    for provider, fetcher in providers:
        for slug in configured_slugs(config, provider):
            raw.extend(fetcher(slug))
            time.sleep(0.15)
    if prefs.get("include_public_remote_feeds", True):
        raw.extend(fetch_remote_feeds([str(x) for x in prefs.get("search_queries", []) if str(x).strip()]))
    seen: set[str] = set()
    ranked = []
    for job in raw:
        if not job["url"] or not job["role"]:
            continue
        posted = parse_date(job["posted_at"])
        if posted and posted < cutoff:
            continue
        key = job["url"].split("?", 1)[0].rstrip("/").lower()
        if key in seen:
            continue
        seen.add(key)
        job_score, hits, reasons = score(job, profile, prefs)
        if job_score < int(prefs.get("minimum_match_score", 0)):
            continue
        job_id = hashlib.sha256(key.encode("utf-8")).hexdigest()[:10]
        job.update({"id": f"{job['provider']}-{job_id}",
                    "fit_score": job_score, "matching_skills": hits, "review_notes": reasons,
                    "posted_date": posted.date().isoformat() if posted else "unknown"})
        ranked.append(job)
    ranked.sort(key=lambda item: (-item["fit_score"], item["posted_date"] == "unknown",
                                 -(parse_date(item["posted_at"]).timestamp() if parse_date(item["posted_at"]) else 0)))
    ranked = ranked[:limit]
    target = data_dir / "search_results.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(ranked, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return ranked
