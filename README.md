# Job Application Helper

An open-source, local-first workflow to **search fresh job listings, rank them against your own preferences, prepare common application fields in a browser, and record the result**. Search includes public RemoteOK/Remotive feeds and any Greenhouse, Ashby, or Lever company boards you configure.

The public version is intentionally generic. It does not contain the original author's profile, answers, resume, old job list, or job-specific scripts. Each user supplies their own details locally.

## What it does

1. Fetches current listings from configured public job-board feeds and ATS company boards.
2. Filters by role keywords, age, optional location preferences and configurable exclusion terms; ranks by a simple, visible skills-overlap score.
3. Opens supported Greenhouse, Ashby, or Lever forms in a visible Chromium browser, fills common contact fields from your local profile, and attaches your local resume when it recognizes the resume upload field.
4. Leaves custom questions, demographic questions, consent, legal attestations, and uncertain fields for you to answer and inspect. You can optionally type `SUBMIT` in the terminal to click the form's submit button.
5. Looks for a confirmation phrase and records whether submission was confirmed or needs verification in your local search results.

**This is not a guaranteed one-click application bot.** Job feeds and application forms change. You must review every answer and confirm the resume before submission. Never rely on the tool's match score or sponsorship warning as a hiring, legal, or immigration determination.

## Requirements and install

- Python 3.10 or newer
- Internet access for searching current public job feeds
- Chromium for browser-assisted application preparation

```bash
git clone https://github.com/yeainshukla/job-application-helper.git
cd job-application-helper
python3 -m pip install .
python3 -m playwright install chromium
jobapp init
```

On Windows, use `py -m pip install .`, `py -m playwright install chromium`, and then `jobapp init`. If the `jobapp` command is not on PATH, run `python3 -m jobapp.cli` from this folder.

## Configure your private profile and searches

`jobapp init` creates files in `~/.job-application-helper/`:

- `profile.json`: your own contact details, work authorization summary, skills, and local resume path.
- `settings.json`: job feeds, role/location filters, exclusions, and optional exact-label answers for application forms.
- `applications.csv`: application tracking.
- `search_results.json`: latest search results and later confirmation status.

Edit these files in a text editor. Nothing in them belongs in a public commit.

### Profile example

```json
{
  "first_name": "Sam",
  "last_name": "Example",
  "preferred_name": "Sam",
  "email": "sam@example.com",
  "phone": "+1-555-0100",
  "city": "Seattle",
  "state": "Washington",
  "zip_code": "98101",
  "address_line1": "",
  "address_line2": "",
  "linkedin_url": "https://www.linkedin.com/in/example/",
  "github_url": "https://github.com/example",
  "portfolio_url": "https://example.com",
  "current_company": "Example Co",
  "current_title": "Software Engineer",
  "work_authorization": "Your own accurate answer",
  "requires_sponsorship": true,
  "resume_path": "/full/path/to/your/resume.pdf",
  "skills": ["Python", "TypeScript", "AWS", "PostgreSQL"]
}
```

Use your own truthful details; omit or leave fields blank when you do not want to store them. Demographic answers and passwords are not part of the profile.

### Search settings

RemoteOK and Remotive are queried by default with `search_preferences.search_queries`. For additional company listings, add the company's public ATS board slug under `job_sources`, for example:

```json
"job_sources": {
  "greenhouse": ["example-company"],
  "ashby": ["example-startup"],
  "lever": ["example-employer"]
}
```

`role_keywords` and `location_keywords` are configurable. Add terms to `exclude_keywords` to remove jobs whose title/description contains those terms. Set `sponsorship_required` to `true` to filter postings with common sponsorship/citizenship/export-control blocker phrases; this text scan is only a rough warning and can miss or misread requirements.

## Use it

Search latest matching jobs:

```bash
jobapp search
```

The command prints job IDs and match scores. Search output is saved locally to `search_results.json`. If no jobs appear, check internet access, configured board slugs, and your filters.

Prepare a form for one result. The browser opens and common fields are filled from your local profile. The command does not click Submit by default:

```bash
jobapp apply JOB_ID
```

To let the tool click the detected submit button after you inspect the form, use `--submit` and type `SUBMIT` at the terminal prompt:

```bash
jobapp apply JOB_ID --submit
```

If the form requires a login, CAPTCHA, verification code, unsupported question, or another manual step, complete it yourself in the browser. If no confirmation is detected, check the employer page and tracker; the tool will mark the result as unverified rather than claiming success.

Other commands:

```bash
jobapp list
jobapp status APP_ID submitted --follow-up 2026-10-15
jobapp --help
```

## Supported sources and limitations

- **Search:** public Greenhouse, Ashby, and Lever company board APIs for configured board slugs; RemoteOK and Remotive public remote-job feeds. It does not search every employer or job board on the internet, and board APIs can change or rate-limit requests.
- **Matching:** a lightweight title, recency, location, exclusion-keyword, and skill-overlap heuristic. It does not use an AI model, read your full resume, or understand nuanced qualifications.
- **Application preparation:** common fields on Greenhouse, Ashby, and Lever forms. Employer-specific questions and unusual controls need manual attention. Other ATS providers are unsupported by browser assistance.
- **Submission:** only after explicit per-job terminal confirmation when `--submit` is used. CAPTCHA, email/MFA checks, logins, and site restrictions remain manual. A success phrase is not a substitute for checking the employer's confirmation.
- **Resume tailoring:** not included; supply the resume you want to use for each application.

## Privacy and safe use

- Your profile, answers, resume path, tracker, and search results stay in your local data directory; they are not sent to this GitHub repository or to a Job Application Helper server.
- `jobapp search` makes requests to the selected public job feeds/ATS board APIs. It sends search query text to RemoteOK/Remotive and requested board slugs to configured ATS providers; it does not send your profile.
- When you use browser application preparation and choose to submit, the employer's website receives the data you entered and the attached documents, as part of your application.
- Before submission, personally review all fields, custom answers, consent, legal declarations, and files. Never let the tool guess sensitive or legally significant answers.
- Keep `~/.job-application-helper/` private. `.gitignore` helps avoid accidental commits but is not a security boundary. Check `git status` before pushing any changes.
- Do not attach real profiles, resumes, tracker exports, screenshots, credentials, or verification codes to public issues or pull requests.

## License

MIT. See [LICENSE](LICENSE).
