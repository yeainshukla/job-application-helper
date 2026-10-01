"""Human-confirmed browser-assisted form completion for common hosted ATS forms."""

from __future__ import annotations

import json
import csv
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

SUPPORTED_HOSTS = ("greenhouse.io", "ashbyhq.com", "lever.co")
SENSITIVE = ("gender", "race", "ethnicity", "veteran", "disability", "sexual orientation", "transgender", "citizenship", "itar", "export control", "conviction", "felony", "criminal")


def norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def find_value(label: str, profile: dict, explicit: dict) -> str | None:
    label_norm = norm(label)
    for saved_label, value in explicit.items():
        if value not in (None, "") and norm(str(saved_label)) == label_norm:
            return str(value)
    if any(token in label_norm for token in SENSITIVE):
        return None
    mappings = (
        (("preferred name", "preferred first name"), "preferred_name"),
        (("first name",), "first_name"), (("last name",), "last_name"), (("email",), "email"),
        (("phone", "mobile"), "phone"), (("linkedin",), "linkedin_url"),
        (("github",), "github_url"), (("portfolio", "personal website", "website url"), "portfolio_url"),
        (("city",), "city"), (("state",), "state"), (("zip", "postal code"), "zip_code"),
        (("street address", "address line 1"), "address_line1"),
        (("address line 2", "apartment", "suite"), "address_line2"),
        (("current company", "current employer", "most recent employer"), "current_company"),
        (("current title", "current job title"), "current_title"),
        (("work authorization",), "work_authorization"),
    )
    for terms, key in mappings:
        if any(term in label_norm for term in terms):
            value = profile.get(key)
            return str(value) if value not in (None, "") else None
    if "sponsor" in label_norm:
        value = profile.get("requires_sponsorship")
        return str(value) if value is not None else None
    return None


def inspect_and_fill(page, profile: dict, answers: dict, resume: str) -> list[dict]:
    fields = page.locator("input:not([type=hidden]):not([type=submit]):not([type=button]), textarea, select").evaluate_all(
        "els => els.map((e,i) => { const labels=[...e.labels||[]].map(x=>x.innerText).join(' '); "
        "const parent=e.closest('fieldset')||e.closest('[class*=field]')||e.parentElement; "
        "return {i,tag:e.tagName,type:e.type||'',name:e.name||'',id:e.id||'',label:(labels||e.getAttribute('aria-label')||parent?.innerText||e.placeholder||e.name||e.id||'').trim().slice(0,300)}; })"
    )
    results = []
    for item in fields:
        kind = item["type"].lower()
        label = item["label"]
        locator = page.locator("input:not([type=hidden]):not([type=submit]):not([type=button]), textarea, select").nth(item["i"])
        if kind == "file":
            if resume and any(word in norm(label) for word in ("resume", "cv")):
                try:
                    locator.set_input_files(resume)
                    results.append({"field": label, "action": "resume attached"})
                except Exception as exc:
                    results.append({"field": label, "action": f"manual attachment needed: {exc}"})
            else:
                results.append({"field": label, "action": "manual file selection required"})
            continue
        value = find_value(label, profile, answers)
        if value is None:
            if kind in ("radio", "checkbox", "select-one", "select-multiple"):
                results.append({"field": label, "action": "left for your review"})
            continue
        try:
            if item["tag"].lower() == "select":
                locator.select_option(label=value)
            elif kind in ("radio", "checkbox"):
                results.append({"field": label, "action": "left for your review; choose a custom answer in profile.answers if appropriate"})
                continue
            else:
                locator.fill(value)
            results.append({"field": label, "action": "filled from local profile; verify"})
        except Exception:
            results.append({"field": label, "action": "not auto-filled; review manually"})
    return results


def apply_to_job(data_dir: Path, app_id: str, submit: bool = False) -> None:
    profile_path = data_dir / "profile.json"
    results_path = data_dir / "search_results.json"
    if not profile_path.exists() or not results_path.exists():
        raise SystemExit("Run `jobapp init` and `jobapp search` first.")
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    config = json.loads((data_dir / "settings.json").read_text(encoding="utf-8"))
    jobs = json.loads(results_path.read_text(encoding="utf-8"))
    job = next((item for item in jobs if item.get("id") == app_id), None)
    if job is None:
        raise SystemExit(f"Job ID not found in latest search results: {app_id}")
    host = (urlparse(job["url"]).hostname or "").lower()
    if not any(host == suffix or host.endswith("." + suffix) for suffix in SUPPORTED_HOSTS):
        raise SystemExit("This ATS is not supported for browser assistance. Open the job link and apply manually.")
    resume = str(profile.get("resume_path") or "")
    answers = config.get("application_answers", {})
    print(f"\n{job['company']} — {job['role']}\n{job['url']}\nMatch score: {job['fit_score']}\n")
    print("A browser will open. You may need to log in or continue from the job details page.")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(accept_downloads=False)
        page = context.new_page()
        page.goto(job["url"], wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(1800)
        # If the form is behind an Apply button, open it. The click only navigates to the form.
        if not page.locator("input,textarea,select").count():
            for pattern in (re.compile(r"apply", re.I),):
                try:
                    page.get_by_role("link", name=pattern).first.click(timeout=2500)
                    break
                except Exception:
                    try:
                        page.get_by_role("button", name=pattern).first.click(timeout=2500)
                        break
                    except Exception:
                        pass
            page.wait_for_timeout(1400)
        filled = inspect_and_fill(page, profile, answers, resume)
        print("Fields prepared (review every answer in the open browser):")
        for item in filled:
            print(f"- {item['field'] or '[unlabeled field]'}: {item['action']}")
        print("\nDo not submit until you have personally reviewed every field and the attached resume.")
        if submit:
            choice = input("Type SUBMIT to click the form's submit button; anything else leaves it unsubmitted: ").strip()
            if choice == "SUBMIT":
                buttons = page.get_by_role("button", name=re.compile(r"submit application|submit my application|submit", re.I))
                if await_count(buttons) == 0:
                    print("No recognized submit button. Complete submission manually in the browser.")
                else:
                    buttons.last.click(timeout=5000)
                    page.wait_for_timeout(5000)
                    body = page.locator("body").inner_text(timeout=5000).lower()
                    success = any(term in body for term in ("application submitted", "successfully submitted", "thank you for applying", "thanks for applying", "application received"))
                    print("Submission confirmation detected." if success else "No clear confirmation detected. Verify the employer page and tracker manually.")
                    job["application_status"] = "submitted" if success else "confirmation_unverified"
                    job["application_checked_at"] = __import__("datetime").datetime.now().astimezone().isoformat(timespec="seconds")
                    results_path.write_text(json.dumps(jobs, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                    tracker = data_dir / "applications.csv"
                    if tracker.exists():
                        with tracker.open(newline="", encoding="utf-8") as f:
                            records = list(csv.DictReader(f))
                            columns = list(records[0]) if records else ["id", "created", "company", "role", "url", "status", "resume_path", "cover_letter_path", "follow_up_date", "notes"]
                        for row in records:
                            if row.get("id") == job["id"]:
                                row["status"] = "submitted" if success else "confirmation_unverified"
                                note = f"Submission confirmation {'detected' if success else 'not detected'} at {job['application_checked_at']}"
                                row["notes"] = "; ".join(x for x in (row.get("notes", ""), note) if x)
                        with tracker.open("w", newline="", encoding="utf-8") as f:
                            writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
                            writer.writeheader()
                            writer.writerows(records)
        else:
            print("Use `jobapp apply JOB_ID --submit` if you want the tool to click submit after confirmation.")
        input("Press Enter after reviewing the result to close the browser…")
        context.close()
        browser.close()


def await_count(locator) -> int:
    try:
        return locator.count()
    except Exception:
        return 0
