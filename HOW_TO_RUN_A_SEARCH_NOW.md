# How to run a search right now

You do not have to wait for the weekly run. You can start a search yourself at any time.
It takes about 10 to 20 minutes and runs on GitHub, so you can close the page while it works.

**Before you start:** you must be signed in to GitHub and be in **your own copy** of this
project (made with "Use this template" in [SETUP.md](SETUP.md), Step 1). You cannot run
searches in the original shared template.

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

1. Click the **Issues** tab (next to Actions, near the top of the page).
2. Open the newest post titled **"Job search results: …"**. It lists:
   a. **Matching jobs:** pass all your rules, with the application link.
   b. **Near misses:** failed exactly one of your rules, with the reason.
3. No new post? Then the search found no new matching jobs or near misses this time.
   Every job it checked, and why each did or did not match, is still in the file
   `reports/latest.md` (open the **Code** tab, then the `reports` folder).

## If you see a red X

1. Click the line with the red X.
2. Click the step with the red X next to it (usually **Check settings files**).
3. Read the message. The most common ones:
   a. **"NO JOB TITLES SET YET"**: open `config/EDIT_ME_1_job_search_settings.toml` and
      type at least one job title in section 1 (see [config/README.md](config/README.md)).
   b. **"SETTINGS PROBLEM: … line N"**: a typing mistake on that line of an EDIT_ME file,
      usually a missing quote `"`, comma `,` or bracket `]`. Fix it and save.
4. After fixing, start again from Step 2 above.

## If you don't see a "Run workflow" button

1. Make sure you are in **your own copy**, not the shared template. The repository name at
   the top left should start with your GitHub username.
2. Make sure you clicked **Weekly job search** on the left (Step 4).
3. If the Actions tab is missing, open **Settings** > **Actions** > **General**, choose
   **Allow all actions and reusable workflows**, click **Save**, and try again.
