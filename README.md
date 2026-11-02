# Job Search Automation

A weekly job search that checks public job listings against **your** rules and posts the
results to you on GitHub. No coding needed.

## START HERE

1. **First time?** Follow **[SETUP.md](SETUP.md)** (about 30 minutes): make your own copy,
   fill in your settings, turn on the weekly run.
2. **Want to run a search right now?** Follow
   **[HOW_TO_RUN_A_SEARCH_NOW.md](HOW_TO_RUN_A_SEARCH_NOW.md)** (step by step, 1 minute to start).
3. **Changing your search later?** Open the **[config](config)** folder. Its page explains
   each file you can edit.

## WHERE TO SEE YOUR RESULTS

| What | Where | When |
|---|---|---|
| **Matching jobs** (pass all your rules) and **near misses** (failed exactly one rule, with the reason) | The **[Issues](../../issues)** tab at the top of this repository. Each run that finds something new adds one post titled **"Job search results: …"** | After each run (weekly, or when you click Run workflow) |
| **Email copies** of those posts | Your email inbox | Turn on once: click **Watch** (top right of the repository), choose **All Activity** |
| **Everything checked**, including jobs that did not match and why | The file **[reports/latest.md](reports/latest.md)** in this repository | Updated by every run |
| **Whether a run worked** | The **[Actions](../../actions)** tab: green check = worked, red X = click it to read what to fix | Every run |

Notes:

1. The **first run** posts one "Job search results (first run)" post listing the jobs that
   already match when you start, plus near misses. After that, each job appears only once.
2. If a run finds nothing new, nothing is posted that week; `reports/latest.md` is still
   updated.

## What you can edit

Only files whose names start with **EDIT_ME**. Everything else runs the automation; do not
edit it.

| Step | File | Required? | What it controls |
|---|---|---|---|
| 1 | [`config/EDIT_ME_1_job_search_settings.toml`](config/EDIT_ME_1_job_search_settings.toml) | **Yes**: at least one job title | Which jobs are found and which are rejected: job titles, your state, salary, certifications, your own rules |
| 2 | [`config/EDIT_ME_2_my_experience.toml`](config/EDIT_ME_2_my_experience.toml) | No | Your skills, used to explain how well each job fits you. Never rejects a job |
| 3 | [`.github/workflows/EDIT_ME_3_weekly_schedule.yml`](.github/workflows/EDIT_ME_3_weekly_schedule.yml) | No | Day and time of the weekly search (default: Fridays) |

Both settings files start **empty**: nothing is searched or filtered until you fill them in.

## How to edit a file

1. Click the file name above.
2. Click the **pencil icon** at the top right.
3. Type only on lines that do **not** start with `#`, between the quotes `""` or brackets
   `[]`. Lines starting with `#` are notes and examples.
4. A list is typed as items in quotes, separated by commas, inside brackets:
   `["Salesforce Administrator", "Salesforce Admin"]`
5. Click **Commit changes** (green button), then **Commit changes** again.

## How the automation works

Each run (weekly, or any time you start one: see [HOW_TO_RUN_A_SEARCH_NOW.md](HOW_TO_RUN_A_SEARCH_NOW.md)):

1. **Check settings.** Reads your EDIT_ME files and lists what is **ON** and **OFF**. If a
   file has a typing mistake, or no job title is filled in, the run stops here and says
   what to fix.
2. **Collect jobs.** Gathers public listings from employer job boards it has learned about
   (Greenhouse, Lever, Ashby, SmartRecruiters), Remotive, Remote OK and Himalayas, plus
   USAJOBS and Adzuna if you add their free keys (see SETUP.md).
3. **Match titles.** Keeps jobs whose titles match your job title groups.
4. **Apply your rules.** Each job is checked against the rules you turned on: fully remote,
   your state, salary, certifications, your own requirement rules. Unclear postings are
   marked **Needs Verification** instead of guessed.
5. **Check the link.** Confirms the application link works and still points to that job.
6. **Compare with your experience.** Lists matching skills and requirements not yet in
   your profile.
7. **Post results** under the **[Issues](../../issues)** tab:
   a. **New qualifying jobs**: passed every rule.
   b. **Near misses**: failed exactly one rule, with the reason.
   Each job is posted only once.
8. **Save a full report** to `reports/latest.md`, including rejected jobs and why.

## What happens when you edit

1. Your changes take effect on the **next run**.
2. Jobs still listed online are re-checked against your new settings:
   a. A job that now passes is posted as **NEWLY VERIFIED**.
   b. A job that now fails moves to **Rejected** in the report.
   c. A job already posted to you is never posted again.
3. Editing your experience only changes the fit notes in future results.
4. The first successful run posts all jobs that already match in one
   "Job search results (first run)" post. Later runs post only new jobs. To start over
   completely, delete `data/jobs.sqlite`; the next run is treated as a first run again.

## Files you do not edit

| Folder or file | What it is |
|---|---|
| `data/`, `reports/` | Saved jobs and reports, updated automatically by each run |
| `jobsearch/` | The program, including `jobsearch/advanced_settings.toml` (built-in defaults) |
| `scripts/`, `tests/` | Posting results to GitHub, and automated checks of the program |

## Safety

Never applies for jobs or contacts employers. Treats all job pages as untrusted data.
Respects robots.txt and rate limits, and does not bypass logins or CAPTCHAs. LinkedIn,
Indeed, Glassdoor, ZipRecruiter and Built In are not accessed.

## For developers

```bash
python3 -m pytest -q
```

```bash
python3 -m jobsearch check
```

```bash
python3 -m jobsearch run --dry-run
```
