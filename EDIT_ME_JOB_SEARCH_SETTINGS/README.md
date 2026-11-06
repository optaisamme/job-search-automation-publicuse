# START HERE: the files you edit

**Easiest: answer the setup questionnaire instead of editing these files.** In your copy, open
[the questionnaire](../../../issues/new/choose) (**Issues** tab, **New issue**,
**Job search setup**), answer the questions and click **Create**. It fills in files 1
and 2 for you and replies with what changed.

Every file you are meant to edit has **EDIT_ME** at the start of its name.
Do not edit any other file.

| Step | File | Required? | What it controls |
|---|---|---|---|
| 1 | [`EDIT_ME_1_job_search_settings.toml`](EDIT_ME_1_job_search_settings.toml) | **Yes** (job titles) | Which jobs are found and which are rejected: job titles, remote only or not (on to start), your state, salary, certifications, your own rules, companies to watch, skills-based matching (starts off) |
| 2 | [`EDIT_ME_2_my_experience.toml`](EDIT_ME_2_my_experience.toml) | No | Your skills, used to explain how well each job fits you. Never rejects a job. Also used by skills-based matching (file 1, section 8) |
| 3 | [`../.github/workflows/EDIT_ME_3_weekly_schedule.yml`](../.github/workflows/EDIT_ME_3_weekly_schedule.yml) | No: you no longer need to edit it | Runs the searches. Automatic weekly searches (start **OFF**) and their day are set in file 1, section 9, or in the questionnaire |

## How to edit a file

1. Click the file name above.
2. Click the **pencil icon** at the top right of the file.
3. Type only on lines that do **not** start with `#`, between the quotes `""` or the
   brackets `[]`. Lines starting with `#` are notes and examples.
4. A list is typed as items in quotes, separated by commas, inside brackets:
   `["Salesforce Administrator", "Salesforce Admin"]`
5. Click **Commit changes** (green button), then **Commit changes** again to save.

## Minimum setup (5 minutes)

In file 1, section 1, "Job title group 1", type at least one job title:

```toml
titles = ["Salesforce Administrator", "Salesforce Admin"]
```

Save. That is enough to start. Everything else is optional and **off** until you fill it in.

## Where to see your results

Open the **[JOB_SEARCH_RESULTS](../JOB_SEARCH_RESULTS)** folder. Its main page shows your latest
results, followed by one numbered, dated report per search:

1. Jobs that match all your rules, with **Apply** links.
2. Near misses: jobs that did not meet one of your rules, and which rule.
3. Jobs whose link could not be checked, with a **Find employer posting** link.
4. Jobs that need checking: jobs that failed no rule but did not say enough to be sure.
5. Popular job boards to search yourself: one-click searches for your job titles.
6. Companies checked every search.

## What happens after you save

1. Changes are used on the **next run**: the weekly run (if you turned it on), or right away if you start one
   yourself in your own copy (step-by-step: [HOW_TO_RUN_A_SEARCH_NOW.md](../HOW_TO_RUN_A_SEARCH_NOW.md)).
2. The first step of each run, **Check settings files**, lists exactly what is **ON** and
   **OFF**. If something is typed wrong, or no job title is filled in, the run stops there
   and says what to fix. Click the red X on the Actions tab to read the message.
3. Results are saved in the **JOB_SEARCH_RESULTS** folder.
4. Jobs still listed online are re-checked every run against your current settings:
   a. A job that now passes because of your change is shown as **Newly verified (seen before)**.
   b. A job that now fails one rule is listed under Near Misses in the next report. Jobs that
      fail 2 or more rules are only counted in the totals.
   c. A job already shown as new is never shown as new again.
5. The first successful search lists every job that already matches, marked "Already listed
   when you started". Later searches mark only new jobs as new.

## Starting over

To forget all jobs seen so far (for example after changing your search completely),
delete the file `data/jobs.sqlite` (open it, click the **...** menu, **Delete file**,
commit). The next run is treated as a first run again.
