# How to run a search right now

You do not have to wait for the weekly run. You can start a search yourself at any time.
It takes about 10 to 20 minutes and runs on GitHub, so you can close the page while it works.

## Before you start: do these 2 things first

A search will **not** work until both are done:

| | Must be done first | How |
|---|---|---|
| ☐ | **1. You made your own copy** of this project, and you are signed in to GitHub. You cannot run a search in the original shared project. | [SETUP.md](SETUP.md), Step 1 |
| ☐ | **2. You typed at least one job title** in your copy's settings file, `EDIT_ME_JOB_SEARCH_SETTINGS/EDIT_ME_1_job_search_settings.toml`, section 1, and saved it. | [SETUP.md](SETUP.md), Step 2 |

If you skip step 2, the search stops right away with the message **"NO JOB TITLES SET YET"**.

## Steps

1. Go to **your copy** of the repository on github.com.
2. Near the top of the page, under the repository name, click the tab named **Actions**.
   (It has a small play-button icon.)
3. **First time only:** if you see a green button that says
   **"I understand my workflows, go ahead and enable them"**, click it.
4. On the left side of the page, under "All workflows", click **Weekly job search**.
5. On the right side, above the list of runs, click the button **Run workflow**.
   A small box opens.
6. In that box, leave "Use workflow from: Branch: main" as it is, and click the green
   **Run workflow** button.
7. Wait about 5 seconds, then refresh the page. A new line appears at the top of the list
   with a yellow circle (running).
8. When it finishes (10 to 20 minutes), the yellow circle becomes:
   a. **a green check mark:** the search worked. Go to "See the results" below.
   b. **a red X:** something needs fixing. Go to "If you see a red X" below.

## See the results

1. **Right away:** click the finished search (the line with the green check). Its results
   are shown on that page.
2. **Any time:** click the **Code** tab, then open the **JOB_SEARCH_RESULTS** folder. Its main
   page shows your latest results:
   a. jobs that match all your rules, with **Apply** links,
   b. near misses (failed exactly one rule) and the reason,
   c. jobs whose link could not be checked, with a **Find employer posting** link.
3. Below that is the list of reports, one per search, newest first, for example
   `REPORT_001_2026-11-06_13-47_UTC.md` (search number, date, time in UTC). Open one to see
   every job checked in that search and why it did or did not match.
4. **Issues tab:** when a search finds something new, it also adds a post titled
   **"Job search results: …"**. If nothing is new, no post is added, but the folder still
   gets a new report.

## If you see a red X

1. Click the line with the red X.
2. Click the step with the red X next to it (usually **Check settings files**).
3. Read the message. The most common ones:
   a. **"NO JOB TITLES SET YET"**: open `EDIT_ME_JOB_SEARCH_SETTINGS/EDIT_ME_1_job_search_settings.toml` and
      type at least one job title in section 1 (see [EDIT_ME_JOB_SEARCH_SETTINGS/README.md](EDIT_ME_JOB_SEARCH_SETTINGS/README.md)).
   b. **"SETTINGS PROBLEM: … line N"**: a typing mistake on that line of an EDIT_ME file,
      usually a missing quote `"`, comma `,` or bracket `]`. Fix it and save.
4. After fixing, start again from Step 2 above.

## If you don't see a "Run workflow" button

1. Make sure you are in **your own copy**, not the shared template. The repository name at
   the top left should start with your GitHub username.
2. Make sure you clicked **Weekly job search** on the left (Step 4).
3. If the Actions tab is missing, open **Settings** > **Actions** > **General**, choose
   **Allow all actions and reusable workflows**, click **Save**, and try again.
