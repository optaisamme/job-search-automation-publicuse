# START HERE: the files you edit

Every file you are meant to edit has **EDIT_ME** at the start of its name.
Do not edit any other file.

| Step | File | Required? | What it controls |
|---|---|---|---|
| 1 | [`EDIT_ME_1_job_search_settings.toml`](EDIT_ME_1_job_search_settings.toml) | **Yes** (job titles) | Which jobs are found and which are rejected: job titles, your state, salary, certifications, your own rules |
| 2 | [`EDIT_ME_2_my_experience.toml`](EDIT_ME_2_my_experience.toml) | No | Your skills, used to explain how well each job fits you. Never rejects a job |
| 3 | [`../.github/workflows/EDIT_ME_3_weekly_schedule.yml`](../.github/workflows/EDIT_ME_3_weekly_schedule.yml) | No | Day and time of the weekly search (default: Fridays) |

## How to edit a file

1. Click the file name above.
2. Click the **pencil icon** at the top right of the file.
3. Type only on lines that do **not** start with `#`, between the quotes `""` or the
   brackets `[]`. Lines starting with `#` are notes and examples.
4. A list is typed as items in quotes, separated by commas, inside brackets:
   `["Salesforce Administrator", "Salesforce Admin"]`
5. Click **Commit changes** (green button), then **Commit changes** again to save.

## Minimum setup (5 minutes)

In file 1, section 1, "Job title group 1", fill in a name and at least one title:

```toml
name = "Salesforce Administrator"
track = "A"
titles = ["Salesforce Administrator", "Salesforce Admin"]
```

Save. That is enough to start. Everything else is optional and **off** until you fill it in.

## Where to see your results

Open the **[JOB_SEARCH_RESULTS](../JOB_SEARCH_RESULTS)** folder. Its main page shows your latest
results (matching jobs, near misses, jobs whose link could not be checked), followed by one
numbered, dated report per search. New results are also posted under the **Issues** tab.

## What happens after you save

1. Changes are used on the **next run**: the weekly run, or right away if you start one
   yourself in your own copy (step-by-step: [HOW_TO_RUN_A_SEARCH_NOW.md](../HOW_TO_RUN_A_SEARCH_NOW.md)).
2. The first step of each run, **Check settings files**, lists exactly what is **ON** and
   **OFF**. If something is typed wrong, or no job title is filled in, the run stops there
   and says what to fix. Click the red X on the Actions tab to read the message.
3. Results are saved in the **JOB_SEARCH_RESULTS** folder, and anything new is also posted
   under the **Issues** tab.
4. Jobs still listed online are re-checked every run against your current settings:
   a. A job that now passes because of your change is posted as **NEWLY VERIFIED**.
   b. A job that now fails moves to the "did not match" part of the next report.
   c. A job already posted to you is never posted again.
5. The very first successful run posts all jobs that already match in one
   "Job search results (first run)" post. Later runs post only new jobs.

## Starting over

To forget all jobs seen so far (for example after changing your search completely),
delete the file `data/jobs.sqlite` (open it, click the **...** menu, **Delete file**,
commit). The next run is treated as a first run again.
