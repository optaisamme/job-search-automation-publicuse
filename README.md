# Job Search Automation

Each time you start a search, this tool looks through public job listings, keeps the jobs that
fit **your** rules (job titles, state, salary, and more), checks that each application link
works, and shows you the results. You set it up once on the GitHub website. No coding needed.
Searches run only when you start one, unless you turn on automatic weekly searches.

## Why I built this

The search filters on sites like LinkedIn, Indeed and HiringCafe either did not let me narrow
my search the way I wanted, or did not search a wide enough variety of job boards. I built
this tool to meet the needs of the students I work with, and I am sharing it for anyone else
it can help.

**Already set up?** Open your copy, then click
**[START A SEARCH NOW](../../actions/workflows/EDIT_ME_3_weekly_schedule.yml)**, then click the
grey **Run workflow** button and the green **Run workflow** button.
[Picture of where to click](HOW_TO_RUN_A_SEARCH_NOW.md#the-picture-where-to-click)

---

## Your 4 steps

| Step | What you do | Where | Time |
|---|---|---|---|
| **1. Make your own copy** | Copy this project into your own GitHub account ([picture of where to click](SETUP.md#step-1-make-your-own-copy)) | [SETUP.md](SETUP.md), Step 1 | 2 minutes |
| **2. Fill in your settings** | Type your job titles and rules into one file | [EDIT_ME_JOB_SEARCH_SETTINGS](EDIT_ME_JOB_SEARCH_SETTINGS) folder, file **EDIT_ME_1** | 10 minutes |
| **3. Run a search** | **Only after steps 1 and 2.** In **your copy**: **Actions** tab, then **Run job search**, then **Run workflow** (twice). Automatic weekly searches start **off** (see below) | [HOW_TO_RUN_A_SEARCH_NOW.md](HOW_TO_RUN_A_SEARCH_NOW.md) | 1 minute to start, 10 to 20 minutes to finish |
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
   d. **Possible matches:** jobs that failed none of your rules but did not say enough to be
      sure (for example, no salary listed), with what to check.
   e. **Popular job boards to search yourself:** one-click searches for your job titles on 32
      boards, grouped by type: large job sites (LinkedIn, Indeed, Google Jobs and more);
      students, hourly and government (Handshake, CareerOneStop, USAJOBS, Snagajob, Upwork,
      AmeriCorps);
      nonprofit and international (Idealist, ReliefWeb, Chronicle of Philanthropy, Devex and
      more);
      diversity (DiversityJobs, PowerToFly and more); and tech and startups.
2. **One report per search**, numbered and dated, for example
   `REPORT_001_2026-11-06_13-47_UTC.md`. The newest is listed first. Each report also lists
   every job checked in that search and why it did or did not match.

Also:

1. **Issues tab:** when a search finds a new job that matches all your rules, it adds a post
   titled "Job search results: …". Near misses are not posted there; they are in the results
   folder. To get these by email, click **Watch** (top right), then **All Activity**.
2. **Actions tab:** shows whether a search worked (green check) or needs a fix (red X).
   Click a finished search to see its results right on that page.

Times are in UTC. Mountain Time is UTC minus 7 hours in winter and minus 6 in summer.

---

## Files you can change

Only files whose names start with **EDIT_ME**. Do not change any other file.

| File | Do I have to? | What it changes |
|---|---|---|
| [`EDIT_ME_JOB_SEARCH_SETTINGS/EDIT_ME_1_job_search_settings.toml`](EDIT_ME_JOB_SEARCH_SETTINGS/EDIT_ME_1_job_search_settings.toml) | **Yes:** type at least one job title | Which jobs are found and which are left out: job titles, remote only or not, your state, salary, certifications, your own rules, companies to watch, skills-based matching |
| [`EDIT_ME_JOB_SEARCH_SETTINGS/EDIT_ME_2_my_experience.toml`](EDIT_ME_JOB_SEARCH_SETTINGS/EDIT_ME_2_my_experience.toml) | No | Your skills, used to show how well each job fits you. It never removes a job. With skills-based matching on (file 1, section 8), it also finds jobs with other titles |
| [`.github/workflows/EDIT_ME_3_weekly_schedule.yml`](.github/workflows/EDIT_ME_3_weekly_schedule.yml) | No | **Automatic weekly searches. They start OFF.** To turn them on, change `AUTOMATIC_WEEKLY_SEARCH: "off"` to `"on"`. Also sets the day and time (default: Fridays) |

Both settings files start **empty**: nothing is searched or filtered until you fill them in.

**Also optional:** a free web search key. It is added in **Settings**, not in a file. See [Other optional edits: a free web search key](#other-optional-edits-a-free-web-search-key).

**Automatic weekly searches are OFF to start.** A search only runs when you start one
yourself. If you want a search to run by itself every week, open file 3 above
(`EDIT_ME_3_weekly_schedule.yml`) and change `AUTOMATIC_WEEKLY_SEARCH: "off"` to
`AUTOMATIC_WEEKLY_SEARCH: "on"`. The steps are written at the top of that file.

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

## Other optional edits: a free web search key

Without a key, every search already checks 9 job sites and company careers pages. Adding
one free key turns on a **web search**: for each of your job titles, the tool also searches
the whole web, including company careers pages, and finds jobs that are on no job site. It
also finds new companies to check. It is optional and stays off until you add the key.

| Service | What it adds | Where to get the free key | Secret name to add |
|---|---|---|---|
| **Tavily** (web search) | Searches the whole web for each of your job titles, including company careers pages | https://app.tavily.com: on the log-in page that opens, click **Sign up** (or continue with a Google, GitHub, LinkedIn or Microsoft account). After signing in, copy your API key from your Tavily account page (it starts with `tvly-`) | `TAVILY_API_KEY` |

**Free plan:** 1,000 web searches a month. This tool uses 2 web searches per job title, for
up to 4 titles, plus 2 for skills-based matching when it is on: at most 10 per search, about 45 a
month with weekly searches.

### How to add the key

1. Sign up at https://app.tavily.com and copy your API key (see the table).
2. Open **your copy** of this project on github.com.
3. Click **Settings** (top row of tabs, far right).
4. On the left, click **Secrets and variables**, then **Actions**.
5. Click the green **New repository secret** button.
6. In **Name**, type `TAVILY_API_KEY` exactly (capital letters and underscores included).
   In **Secret**, paste the key. Click **Add secret**.
7. Start a search. In the full report, the table "Where jobs were looked for" shows
   **Web search (Tavily): Yes** when it worked. "Off: needs a free key" means the secret is
   missing or its name is misspelled. "No: error" means the key was not accepted; check it
   and add it again.

The key is private: only you can see it, and it is never shown in results. To remove it,
open the same page and click the trash icon next to it.

**Boards that do not offer keys:** LinkedIn, Indeed, Handshake, Idealist and the other popular
boards on your results page offer no key for automated searching. Use the one-click search
links on the results page for those.

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
2. **Collects public job listings** from these job sites:
   a. **No setup needed:** Himalayas, The Muse, Remote OK, Jobicy, We Work Remotely, Working
      Nomads, Jobspresso, Remotive and Hacker News "Who is hiring?" (mostly tech jobs).
      Several send their newest jobs whatever your search words are, so each search looks at
      more than 1,000 listings.
   b. **Web search (free key, recommended, see SETUP.md Step 6):** searches the whole web for
      each of your job titles, finding jobs that are on no job site above. For each title it
      runs 2 searches: one across company careers pages (Greenhouse, Lever, Ashby,
      SmartRecruiters, Workday) and one across the rest of the web. Every result is checked
      like any other job.
   c. **Company careers pages**, only for companies whose careers page runs on Greenhouse,
      Lever, Ashby or SmartRecruiters. These are not searched as whole sites: the tool reads
      the careers page of one company at a time, and only for these companies:
      1. **Found automatically**, step by step:
         1. A job site lists a job whose title matches yours.
         2. The tool opens that job's apply link (the one the job site gives).
         3. If the link leads to a posting on a careers page that runs on one of those 4 systems,
            the tool uses the employer's own posting and remembers the company (in
            `data/boards.json`).
         4. From the next search on, it reads every job open on that company's careers page.
         5. With a web search key, companies are also remembered when the web search finds a
            matching job on their careers page; their whole careers page is read in the same search.
         6. Companies on other systems (for example Workday), and links a job site blocks (for
            example Himalayas), are not remembered.
         7. A remembered company is removed after more than 5 searches in a row with no job
            matching your titles. It comes back if a matching job shows up again. Companies you
            add in section 7 are never removed. The results page lists every remembered
            company under "Companies checked every search."
      2. **Companies you add** in settings section 7, "Companies to watch." Every search reads
         every job open on each company's careers page and keeps the ones with your job titles.
         Companies on other systems (for example Workday or iCIMS) cannot be added. If you leave
         section 7 empty, everything else above still runs.
3. **Keeps jobs with your job titles.** With skills-based matching on (settings section 8), it
   also keeps jobs with other titles whose listing has your required keywords and enough of
   your skills (from your experience file). Those are marked "(skills match)".
4. **Applies your rules**: remote only (on unless you turn it off), your state, salary,
   certifications, your own rules. When a
   posting is unclear, the job is marked **Needs Verification** instead of guessed.
5. **Checks the application link** to make sure the job is still open.
   Himalayas blocks automated link checks. A Himalayas job counts as open when Himalayas'
   own job feed listed it during the search and its closing date has not passed. These
   jobs are marked **"third-party site, link not checked."**
6. **Compares each job with your experience.**
7. **Saves the results** in [JOB_SEARCH_RESULTS](JOB_SEARCH_RESULTS) and posts new matching
   jobs under **Issues**.

The tool never applies to jobs or contacts employers. It does not search popular boards
such as LinkedIn, Indeed, Handshake or Idealist: they have no public data feed, require
signing in, block automated requests, or their terms do not allow automated searching.
Instead, the results page has **one-click search links** for 32 of these boards, built from
your job titles, so you can open those searches yourself.
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
