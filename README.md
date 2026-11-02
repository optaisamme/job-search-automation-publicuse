# Job Search Automation

Every week, this tool looks through public job listings, keeps the jobs that fit **your**
rules (job titles, state, salary, and more), checks that each application link works, and
shows you the results. You set it up once on the GitHub website. No coding needed.

---

## Your 4 steps

| Step | What you do | Where | Time |
|---|---|---|---|
| **1. Make your own copy** | Copy this project into your own GitHub account | [SETUP.md](SETUP.md), Step 1 | 2 minutes |
| **2. Fill in your settings** | Type your job titles and rules into one file | [config](config) folder, file **EDIT_ME_1** | 10 minutes |
| **3. Run a search** | **Only after steps 1 and 2.** Click a button in **your copy** to start a search (it also runs by itself every Friday) | [HOW_TO_RUN_A_SEARCH_NOW.md](HOW_TO_RUN_A_SEARCH_NOW.md) | 1 minute to start, 10 to 20 minutes to finish |
| **4. Read your results** | Open the results folder | **[JOB_SEARCH_RESULTS](JOB_SEARCH_RESULTS)** folder | Any time |

Do the steps **in order**. A search cannot run until you have your own copy (step 1) and at
least one job title in your settings (step 2). First time? Start with **[SETUP.md](SETUP.md)**;
it walks you through steps 1 to 4.

---

## Where your results are

Open the **[JOB_SEARCH_RESULTS](JOB_SEARCH_RESULTS)** folder.

1. **The folder's main page** opens automatically and shows your **latest results**:
   a. **Jobs that match all your rules**, with an **Apply** link for each.
   b. **Near misses:** jobs that failed exactly one of your rules, and which rule.
   c. **Jobs whose link could not be checked**, with a link to find the employer's own posting.
2. **One report per search**, numbered and dated, for example
   `REPORT_001_2026-11-06_13-47_UTC.md`. The newest is listed first. Each report also lists
   every job checked in that search and why it did or did not match.

Also:

1. **Issues tab:** when a search finds something new, it adds a post titled
   "Job search results: …". To get these by email, click **Watch** (top right), then **All Activity**.
2. **Actions tab:** shows whether a search worked (green check) or needs a fix (red X).
   Click a finished search to see its results right on that page.

Times are in UTC. Mountain Time is UTC minus 7 hours in winter and minus 6 in summer.

---

## Files you can change

Only files whose names start with **EDIT_ME**. Do not change any other file.

| File | Do I have to? | What it changes |
|---|---|---|
| [`config/EDIT_ME_1_job_search_settings.toml`](config/EDIT_ME_1_job_search_settings.toml) | **Yes:** type at least one job title | Which jobs are found and which are left out: job titles, remote only or not, your state, salary, certifications, your own rules |
| [`config/EDIT_ME_2_my_experience.toml`](config/EDIT_ME_2_my_experience.toml) | No | Your skills, used to show how well each job fits you. It never removes a job |
| [`.github/workflows/EDIT_ME_3_weekly_schedule.yml`](.github/workflows/EDIT_ME_3_weekly_schedule.yml) | No | The day and time of the automatic weekly search (default: Fridays) |

Both settings files start **empty**: nothing is searched or filtered until you fill them in.

### How to change a file

1. Click the file name in the table above.
2. Click the **pencil icon** (top right of the file).
3. Type only on lines that do **not** start with `#`, between the quotes `""` or the
   brackets `[]`. Lines starting with `#` are notes and examples.
4. To type a list, put each item in quotes, with commas between, inside brackets:
   `["Salesforce Administrator", "Salesforce Admin"]`
5. Click the green **Commit changes** button, then **Commit changes** again to save.

### What happens after you change a setting

1. Your change is used in the **next search** (the Friday search, or one you start yourself).
2. Each search first checks your settings. If something is typed wrong, the search stops
   and tells you which line to fix.
3. Jobs found earlier are checked again with your new settings:
   a. A job that now fits is shown as **NEWLY VERIFIED**.
   b. A job that no longer fits moves to the "did not match" part of the report.
   c. A job already shown to you is never shown again as new.
4. To start completely fresh, delete the file `data/jobs.sqlite`. The next search starts over.

---

## Folders you can ignore

| Folder or file | What it is |
|---|---|
| `data/` | Jobs the tool has already seen. Updated automatically |
| `jobsearch/`, `scripts/`, `tests/` | The program itself |
| `SETUP.md`, `HOW_TO_RUN_A_SEARCH_NOW.md` | Guides (read them; no need to change them) |

---

## How a search works

1. **Checks your settings** and lists what is ON and OFF.
2. **Collects public job listings** from employer job pages it knows about (Greenhouse,
   Lever, Ashby, SmartRecruiters), Remotive, Remote OK and Himalayas. Optional: USAJOBS and
   Adzuna, if you add their free keys (see SETUP.md).
3. **Keeps jobs with your job titles.**
4. **Applies your rules**: remote only (on unless you turn it off), your state, salary,
   certifications, your own rules. When a
   posting is unclear, the job is marked **Needs Verification** instead of guessed.
5. **Checks the application link** to make sure the job is still open.
6. **Compares each job with your experience.**
7. **Saves the results** in [JOB_SEARCH_RESULTS](JOB_SEARCH_RESULTS) and posts anything new
   under **Issues**.

The tool never applies to jobs or contacts employers. It does not read LinkedIn, Indeed,
Glassdoor, ZipRecruiter or Built In, because their terms do not allow automated access.
It does not get around sites that block automated checks.

---

## For programmers

```bash
python3 -m pytest -q
```

```bash
python3 -m jobsearch check
```

```bash
python3 -m jobsearch run --dry-run
```
