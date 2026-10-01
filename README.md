# Job Application Helper

A small, free, local-first command-line tool for organizing job applications and preparing a human-reviewed submission checklist. It works with any employer because it stores job links and your notes without depending on a specific job board.

**This is not an automatic application bot.** It does not scrape job boards, tailor resumes, fill employer forms, upload files, bypass CAPTCHA, or submit applications. You open the employer's page and complete the application yourself. Forms and questions differ by employer, and every answer should be checked before submission.

## Requirements

- Python 3.10 or newer
- macOS, Windows, or Linux
- No API key, account, browser extension, or third-party Python package

## Install

From a terminal:

```bash
git clone https://github.com/yeainshukla/job-application-helper.git
cd job-application-helper
python3 -m pip install .
jobapp init
```

On Windows, use `py -m pip install .` and then `jobapp init`. If the `jobapp` command is not on PATH, run it as `python3 -m jobapp.cli` from this folder.

The tool creates `~/.job-application-helper/profile.json` and `~/.job-application-helper/applications.csv` on your computer. They are outside the cloned repository and are not uploaded to GitHub. You can use another local directory with `--data-dir /path/to/private-folder` or set `JOBAPP_DATA_DIR`.

## Set up your profile

Open `~/.job-application-helper/profile.json` in a text editor and replace blank values with your own information. Keep optional or sensitive details out unless you personally want to use them. This profile is only read locally by the program.

The supported profile fields are:

| Field | Example |
|---|---|
| `full_name` | Your legal or application name |
| `preferred_name` | Name you want employers to use |
| `email`, `phone` | Your contact details |
| `city_region` | City and state/region |
| `linkedin_url`, `portfolio_url` | Public profile links |
| `work_authorization_summary` | Your own short summary, if useful |
| `requires_sponsorship` | `true`, `false`, or `null` if undecided/not applicable |
| `resume_path`, `cover_letter_path` | Optional local file paths; these files are never uploaded by this tool |

Review the profile for accuracy. It does not include EEO/demographic answers, passwords, or employer login information.

## Typical workflow

Add a job (quote values that contain spaces):

```bash
jobapp add --company "Example Company" --role "Software Engineer" \
  --url "https://jobs.example.com/role/123" \
  --resume "$HOME/Documents/resume.pdf"
```

List jobs and prepare a checklist for one:

```bash
jobapp list
jobapp prepare APP_ID
jobapp open APP_ID
```

After you submit on the employer's website, update the tracker:

```bash
jobapp status APP_ID submitted --follow-up 2026-10-15
jobapp list --status submitted
```

Valid statuses: `saved`, `preparing`, `submitted`, `interview`, `rejected`, `withdrawn`, `not_pursuing`.

## Privacy and safe use

- Your profile and tracker stay in your local data directory. The program has no network client and makes no HTTP requests.
- Do not add your profile, resumes, application tracker, screenshots, or employer account credentials to a public Git repository.
- The repository ignores common local data and document files, but `.gitignore` is not a security boundary. Check `git status` before every commit.
- The `prepare` command prints profile details to your terminal. Avoid screen-sharing or saving that output in a public log.
- You are responsible for the accuracy of your information and for reviewing employer questions, consent, work authorization, and attachments before submitting.

## Limitations

- It is a tracker and preparation checklist, not a job search engine or resume generator.
- It does not integrate with Greenhouse, Workday, Ashby, LinkedIn, or any other job platform.
- It cannot solve or bypass CAPTCHA, email verification, MFA, or account login.
- It does not decide legal/work authorization or demographic answers for you.
- The employer may change or close a job listing at any time.

## Development

The code uses only Python's standard library. Run locally without installation with:

```bash
python3 -m jobapp.cli --help
```

Contributions are welcome. Please do not commit personal application data, resumes, screenshots, credentials, or real applicants' contact details.

## License

MIT. See [LICENSE](LICENSE).
