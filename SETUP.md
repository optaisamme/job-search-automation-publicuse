# Setup Guide (no coding needed)

This tool searches public job listings every week, checks each job against your rules
(location, salary, required experience and certifications), checks that the application
link works, and posts the results to you. It runs for free on GitHub's computers, so your
own computer does not need to be on. Everything is edited on the GitHub website.

## What you need

1. A free GitHub account: https://github.com/signup
2. About 30 minutes for first-time setup.

## Step 1: Make your own copy

1. Open the shared project page (the link you were given).
2. Click the green **Use this template** button, then **Create a new repository**.
   (If you don't see that button, ask the person who shared it to give you access.)
3. Name it, for example, `my-job-search`.
4. Choose **Private** so your profile stays private.
5. Click **Create repository**.

Every file you edit has **EDIT_ME** at the start of its name. Do not edit other files.
The [config folder page](config) lists them.

## Step 2: Set your search rules (EDIT ME file 1, required)

`config/EDIT_ME_1_job_search_settings.toml` starts empty: no titles, no filters. You fill in the blanks: type
between the quotes `""` or the brackets `[]` on lines that do NOT start with `#`.
Lines starting with `#` are notes and examples; you never need to edit them.

A list is typed as items in quotes, separated by commas, inside brackets:
`["Salesforce Administrator", "Salesforce Admin"]`

1. In your new repository, open the `config` folder, then `EDIT_ME_1_job_search_settings.toml`.
2. Click the pencil icon (Edit).
3. **Required, section 1:** in "Job title group 1", type a name and at least one title:

```toml
name = "Salesforce Administrator"
track = "A"
titles = ["Salesforce Administrator", "Salesforce Admin"]
description_must_mention_one_of = []
```

   Use groups 2 and 3 for other kinds of jobs, or leave them empty.
4. Optional, each off until you fill it in:
   a. Section 2: your state (rejects jobs that exclude it).
   b. Section 3: salary minimums (`0` = no minimum).
   c. Section 4: words the description must mention, title words to skip, and the
      certification check.
   d. Section 5: requirement rules. Fill in a rule's name and terms, then change
      `on = "no"` to `on = "yes"`:

```toml
name = "Security clearance"
on = "yes"
terms = ["security clearance", "TS/SCI"]
reject_when = "mentioned"
```

      `reject_when = "required"` rejects a job only when it REQUIRES prior experience
      with a term; `"mentioned"` rejects it whenever a term appears.
   e. Section 6: search words (leave empty to search for your job titles).
5. Click **Commit changes** (green button), then **Commit changes** again.
6. The first step of every run ("Check settings files") lists exactly what is ON and
   OFF. If no job titles are set, the run stops there and says so.

## Step 3: Add your experience (EDIT ME file 2, optional)

`config/EDIT_ME_2_my_experience.toml` also starts empty, with examples as notes.

1. Open `config/EDIT_ME_2_my_experience.toml` and click the pencil icon.
2. For each skill you have, copy the example block to the bottom of the file, remove
   the `# ` marks, and fill in the skill, the words a job posting might use for it, and
   where you did it.
3. Include only things you have actually done. Do not add phone, email or address.
4. Commit changes.

Your profile never rejects a job. It is only used to explain how well each job fits you
and which requirements are not yet in your profile. It can stay empty.

## Step 4: Turn on the weekly run and run your first search

Follow **[HOW_TO_RUN_A_SEARCH_NOW.md](HOW_TO_RUN_A_SEARCH_NOW.md)** once. Enabling the
workflow there (its Step 3) also turns on the automatic weekly run. Use the same guide
any time you want results without waiting for the weekly run.

## Step 5: Where to see your results

1. **Matching jobs and near misses** appear under the **Issues** tab at the top of your
   repository, in posts titled **"Job search results: …"**:
   a. **Matching jobs**: pass every rule, with salary, location, fit notes and the
      application link.
   b. **Near misses**: failed exactly one rule, with the reason.
2. **Email copies:** click **Watch** (top right of your repository), then **All Activity**.
   GitHub then emails you each new results post.
3. **Every job checked**, including those that did not match and why, is in the file
   `reports/latest.md` (open the `reports` folder in your repository).
4. **Whether a run worked:** the **Actions** tab. Green check = worked; red X = click it,
   then the red step, to read what to fix.
5. The **first run** posts one "Job search results (first run)" post listing the jobs that
   already match when you start, plus near misses. After that, each job is posted only
   once. A week with nothing new posts nothing (the report is still updated).

## Step 6: Optional changes

1. **Change the day or time (EDIT ME file 3):** edit
   `.github/workflows/EDIT_ME_3_weekly_schedule.yml`, the line
   `cron: "47 13 * * 5"`. The format is `minute hour * * day-of-week`, in UTC time
   (Mountain Time is UTC minus 7 in winter, minus 6 in summer; day 5 = Friday).
   Example: `"0 15 * * 1"` = Mondays 15:00 UTC.
2. **More job sources (free):**
   a. USAJOBS (federal jobs): request a key at https://developer.usajobs.gov
   b. Adzuna: register at https://developer.adzuna.com
   c. Add them in your repository: **Settings**, **Secrets and variables**, **Actions**,
      **New repository secret**, with the names `USAJOBS_API_KEY`, `USAJOBS_EMAIL`,
      `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`.

## When you change your settings later

1. Edit the EDIT_ME file and commit. Changes take effect on the next run (weekly, or start
   one now with [HOW_TO_RUN_A_SEARCH_NOW.md](HOW_TO_RUN_A_SEARCH_NOW.md)).
2. Jobs still listed online are re-checked: a job that now passes is posted as
   **NEWLY VERIFIED**; one that now fails moves to **Rejected** in the report. Jobs
   already posted are never posted again.
3. To start over completely, delete `data/jobs.sqlite`; the next run is treated as a first
   run again.

## What it does not do

1. It never applies to jobs or contacts employers.
2. It does not read LinkedIn, Indeed, Glassdoor, ZipRecruiter or Built In (their terms do
   not allow automated access). Links from those sites can't be checked automatically.
3. Without Claude, it does not run its own web searches. It uses the job boards of the
   employers it already knows, Remotive, Remote OK, Himalayas, and any optional API keys.
4. Results come from text rules. When a posting is unclear, the job is marked "Needs
   Verification" rather than guessed, so read each posting yourself before applying.

## Running it on your own computer instead (optional)

1. Install Python 3.11 or newer: https://www.python.org/downloads/
2. Download your repository (green **Code** button, **Download ZIP**) and unzip it.
3. Open a terminal in that folder and run:

```bash
python3 -m jobsearch check
```

```bash
python3 -m jobsearch run
```

4. Results are written to `reports/latest.md` and `reports/latest.html`.
