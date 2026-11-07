"""The setup questionnaire: GitHub issue-form answers -> settings files."""
import importlib.util
import pathlib
import shutil
import tomllib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("q", ROOT / "scripts/apply_questionnaire.py")
q = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q)

SETTINGS = (ROOT / "EDIT_ME_JOB_SEARCH_SETTINGS/EDIT_ME_1_job_search_settings.toml").read_text()
EXPERIENCE = (ROOT / "EDIT_ME_JOB_SEARCH_SETTINGS/EDIT_ME_2_my_experience.toml").read_text()


def form(**answers):
    """Issue text the way GitHub writes a submitted issue form."""
    by_key = {v: k for k, v in q.LABELS.items()}
    parts = []
    for key in q.LABELS.values():
        parts += [f"### {by_key[key]}", "", answers.get(key, "_No response_"), ""]
    return "\n".join(parts)


def test_form_labels_match_the_script():
    import yaml
    f = yaml.safe_load(open(ROOT / ".github/ISSUE_TEMPLATE/job_search_setup.yml"))
    labels = [b["attributes"]["label"] for b in f["body"] if b["type"] != "markdown"]
    assert set(labels) == set(q.LABELS) and len(labels) == len(q.LABELS)


def test_full_answers_update_both_files():
    body = form(titles_1="Program Manager\nProgram Director\nData Analyst",
                remote_only="No, also hybrid and on-site jobs in my state", state="New Mexico", state_abbreviation="nm",
                cities="Albuquerque\nSanta Fe", min_single="$100,000", min_range_start="90000", range_end_above="100000",
                skip_titles="Intern\nMajor Gifts", cert_check="Yes", certs_allowed="CPR",
                companies="https://job-boards.greenhouse.io/examplecompany",
                skills_on="On", skills_keywords="Salesforce\nNPSP", skills_rule="At least one keyword must appear",
                skills_min="3", my_skills="Reports and dashboards: report, dashboard\nData cleanup: data quality, dedup",
                years="4", certs_held="CPR", weekly="On", weekly_day="Monday", run_now="Yes")
    answers = q.parse_issue_body(body)
    s, e, changes, extras = q.apply(answers, SETTINGS, EXPERIENCE)
    st, ex = tomllib.loads(s), tomllib.loads(e)
    g = st["job_titles"]["group"]
    assert g[0]["titles"] == ["Program Manager", "Program Director", "Data Analyst"] and g[1]["titles"] == [] and g[2]["titles"] == []
    w = st["where_you_live"]
    assert (w["remote_only"], w["state"], w["state_abbreviation"], w["cities"]) == ("no", "New Mexico", "NM", ["Albuquerque", "Santa Fe"])
    assert st["salary"] == {"minimum_single_salary": 100000, "minimum_range_start": 90000, "range_end_must_be_above": 100000}
    assert st["filters"]["exclude_titles_containing"] == ["Intern", "Major Gifts"] and st["filters"]["check_certifications"] == "yes"
    assert st["companies_to_watch"]["job_page_links"] == ["https://job-boards.greenhouse.io/examplecompany"]
    assert st["skills_matching"] == {"on": "yes", "required_keywords": ["Salesforce", "NPSP"],
                                     "required_keywords_rule": "any", "minimum_skills_matched": 3}
    assert st["automatic_weekly_search"] == {"on": "yes", "day": "Monday"}
    assert ex["tenure"]["years_of_experience"] == 4 and ex["tenure"]["certifications_held"] == ["CPR"]
    assert [k["name"] for k in ex["skills"]] == ["Reports and dashboards", "Data cleanup"]
    assert ex["skills"][1]["keywords"] == ["data quality", "dedup"]
    assert extras["run_now"] and len(changes) >= 15
    assert "# 1. JOB TITLES TO LOOK FOR" in s or "JOB TITLES TO LOOK FOR" in s      # notes and examples are kept


def test_blank_keeps_and_none_clears():
    s1, e1, _, _ = q.apply(q.parse_issue_body(form(titles_1="Program Manager", skip_titles="Intern", state="Utah")), SETTINGS, EXPERIENCE)
    s2, _, changes, _ = q.apply(q.parse_issue_body(form(titles_1="Program Manager", skip_titles="none")), s1, e1)
    st = tomllib.loads(s2)
    assert st["where_you_live"]["state"] == "Utah"                     # blank: kept
    assert st["filters"]["exclude_titles_containing"] == []            # none: cleared
    assert any(c.startswith("Title words to skip: cleared") for c in changes)


@pytest.mark.parametrize("answers,problem", [
    ({"titles_1": "X", "min_single": "about 90k"}, "type a number only"),
    ({"titles_1": "X", "state_abbreviation": "New Mexico"}, "two letters"),
    ({"titles_1": "X", "companies": "https://www.example.com/careers"}, "not company job pages"),
])
def test_bad_answers_are_explained(answers, problem):
    with pytest.raises(q.AnswerProblem, match=problem):
        q.apply(q.parse_issue_body(form(**answers)), SETTINGS, EXPERIENCE)


def test_answers_are_only_ever_quoted_values():
    s, _, _, _ = q.apply(q.parse_issue_body(form(titles_1='Analyst"]\n[evil]\nx = 1')), SETTINGS, EXPERIENCE)
    st = tomllib.loads(s)
    assert "evil" not in st and st["job_titles"]["group"][0]["titles"] == ['Analyst"]', "[evil]", "x = 1"]


def test_only_owner_or_collaborator_can_change_settings(tmp_path, monkeypatch):
    for d in ("EDIT_ME_JOB_SEARCH_SETTINGS", "jobsearch", "scripts"):
        shutil.copytree(ROOT / d, tmp_path / d)
    monkeypatch.setattr(q, "ROOT", tmp_path)
    monkeypatch.setattr(q, "SETTINGS", tmp_path / "EDIT_ME_JOB_SEARCH_SETTINGS/EDIT_ME_1_job_search_settings.toml")
    monkeypatch.setattr(q, "EXPERIENCE", tmp_path / "EDIT_ME_JOB_SEARCH_SETTINGS/EDIT_ME_2_my_experience.toml")
    monkeypatch.setattr(q, "OUT", tmp_path / "out")
    monkeypatch.setenv("ISSUE_BODY", form(titles_1="Program Manager"))
    monkeypatch.setenv("AUTHOR_ASSOCIATION", "NONE")
    q.main()
    assert "can only be changed by its owner" in (tmp_path / "out/questionnaire_reply.md").read_text()
    assert q.SETTINGS.read_text() == SETTINGS
    monkeypatch.setenv("AUTHOR_ASSOCIATION", "OWNER")
    q.main()
    assert (tmp_path / "out/questionnaire_ok.txt").read_text() == "yes"
    assert tomllib.loads(q.SETTINGS.read_text())["job_titles"]["group"][0]["titles"] == ["Program Manager"]
    assert "Your settings are saved" in (tmp_path / "out/questionnaire_reply.md").read_text()
    monkeypatch.setenv("IS_TEMPLATE", "true")                      # the shared template is never changed
    before = q.SETTINGS.read_text()
    q.main()
    assert q.SETTINGS.read_text() == before and "shared template" in (tmp_path / "out/questionnaire_reply.md").read_text()
    monkeypatch.setenv("IS_TEMPLATE", "")
    monkeypatch.setenv("GITHUB_REPOSITORY", "optaisamme/job-search-automation-publicuse")
    q.main()
    assert q.SETTINGS.read_text() == before


def test_text_box_answers_in_code_blocks_are_read():
    body = "### Job titles to look for\n\n```text\nProgram Manager\nProgram Director\n```\n\n### Your state\n\nUtah\n"
    a = q.parse_issue_body(body)
    assert a["titles_1"] == "Program Manager\nProgram Director" and a["state"] == "Utah"


def test_search_size_choice_is_saved_and_recommended_is_the_default():
    import yaml
    f = yaml.safe_load(open(ROOT / ".github/ISSUE_TEMPLATE/job_search_setup.yml"))
    dd = next(b for b in f["body"] if b["attributes"].get("label") == "How many jobs to look through")
    assert dd["attributes"]["default"] == 0 and dd["attributes"]["options"][0].startswith("Recommended")
    assert "recommend keeping" in yaml.safe_dump(f).lower()
    # the recommended choice equals the numbers the settings file starts with and the search uses by default
    from jobsearch.adapters.aggregators import SEARCH_SIZE_DEFAULTS
    assert q.SEARCH_SIZES["recommended"] == SEARCH_SIZE_DEFAULTS == tomllib.loads(SETTINGS)["search_size"]
    s, _, changes, _ = q.apply(q.parse_issue_body(form(titles_1="Data Analyst", search_size=dd["attributes"]["options"][1])),
                               SETTINGS, EXPERIENCE)
    assert tomllib.loads(s)["search_size"] == q.SEARCH_SIZES["fewer"]
    assert any(c.startswith("How many jobs to look through: Fewer") for c in changes)
    # an older copy without section 10 gets it added
    old = SETTINGS[:SETTINGS.index("[search_size]")]
    s, _, _, _ = q.apply(q.parse_issue_body(form(search_size="More (slower)")), old, EXPERIENCE)
    assert tomllib.loads(s)["search_size"] == q.SEARCH_SIZES["more"]
    with pytest.raises(q.AnswerProblem):
        q.apply(q.parse_issue_body(form(search_size="Huge")), SETTINGS, EXPERIENCE)


def test_search_size_numbers_are_kept_within_limits():
    from jobsearch.adapters.aggregators import search_size, _pages
    sz = search_size({"search_size": {"newest_jobs_per_site": 999999, "jobs_per_search_word": 1, "jobicy_max_jobs": "x"}})
    assert sz == {"newest_jobs_per_site": 5000, "jobs_per_search_word": 20, "jobicy_max_jobs": 5000}
    assert (_pages(1000, 20), _pages(30, 20), _pages(5000, 100)) == (50, 2, 50)


def test_older_question_labels_are_still_read():
    a = q.parse_issue_body("### Skills-based matching\n\nOn\n\n### More job titles: a second kind of job\n\nData Analyst\n")
    assert a == {"skills_on": "On"}          # old title boxes are ignored; one box for all titles now


def test_unanswered_dropdowns_keep_settings():
    """GitHub writes "None" for a dropdown left unanswered (seen in a real copy on 2026-11-07)."""
    import yaml
    f = yaml.safe_load(open(ROOT / ".github/ISSUE_TEMPLATE/job_search_setup.yml"))
    dropdown_keys = {q.LABELS[b["attributes"]["label"]] for b in f["body"] if b["type"] == "dropdown"}
    assert dropdown_keys == q.DROPDOWNS
    body = form(titles_1="Abortion Advocate\nDomestic Violence Advocate", remote_only="None", cert_check="None",
                skills_on="None", skills_rule="None", weekly="None", weekly_day="None", run_now="Yes")
    s, _, changes, extras = q.apply(q.parse_issue_body(body), SETTINGS, EXPERIENCE)
    st, before = tomllib.loads(s), tomllib.loads(SETTINGS)
    assert st["job_titles"]["group"][0]["titles"] == ["Abortion Advocate", "Domestic Violence Advocate"]
    assert st["where_you_live"] == before["where_you_live"] and st["automatic_weekly_search"] == before["automatic_weekly_search"]
    assert st["filters"]["check_certifications"] == before["filters"]["check_certifications"]
    assert extras["run_now"]
    # typing "none" in a text box still clears a list
    s2, _, _, _ = q.apply(q.parse_issue_body(form(skip_titles="none")), s, EXPERIENCE)
    assert tomllib.loads(s2)["filters"]["exclude_titles_containing"] == []


def test_start_search_links_to_the_running_search(tmp_path, monkeypatch):
    from datetime import datetime, timezone
    monkeypatch.setattr(q, "OUT", tmp_path)
    monkeypatch.setenv("GITHUB_REPOSITORY", "someone/my-job-search")
    calls = []

    def fake_api(method, path, payload=None):
        calls.append((method, path, payload))
        if method == "POST":
            return {}
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return {"workflow_runs": [{"created_at": now, "html_url": "https://github.com/someone/my-job-search/actions/runs/7"}]}
    monkeypatch.setattr(q, "_api", fake_api)
    assert q.start_search(wait_seconds=0) == 0
    assert calls[0] == ("POST", "actions/workflows/run_job_search.yml/dispatches", {"ref": "main"})
    msg = (tmp_path / "questionnaire_search.md").read_text()
    assert "[open the running search](https://github.com/someone/my-job-search/actions/runs/7)" in msg


def test_start_search_failure_says_why_and_how_to_start_it(tmp_path, monkeypatch):
    import io, urllib.error
    monkeypatch.setattr(q, "OUT", tmp_path)
    monkeypatch.setenv("GITHUB_REPOSITORY", "someone/my-job-search")

    def fake_api(method, path, payload=None):
        raise urllib.error.HTTPError("u", 403, "Forbidden", {}, io.BytesIO(b'{"message": "Resource not accessible by integration"}'))
    monkeypatch.setattr(q, "_api", fake_api)
    assert q.start_search(wait_seconds=0) == 1
    msg = (tmp_path / "questionnaire_search.md").read_text()
    assert "could not be started automatically" in msg and "403: Resource not accessible by integration" in msg
    assert "https://github.com/someone/my-job-search/actions/workflows/run_job_search.yml" in msg


def test_workflows_point_at_files_that_exist():
    import re
    wf = ROOT / ".github/workflows"
    q_wf = (wf / "apply_setup_questionnaire.yml").read_text()
    assert (wf / q.WORKFLOW_FILE).exists()
    assert q_wf.index("name: Start a search") < q_wf.index("name: Reply on the issue")   # the reply can link to it
    for f in wf.glob("*.yml"):
        for script in re.findall(r"python (scripts/\S+\.py)", f.read_text()):
            assert (ROOT / script).exists(), (f.name, script)
    for doc in ("README.md", "HOW_TO_RUN_A_SEARCH_NOW.md", "JOB_SEARCH_RESULTS/README.md", "jobsearch/results_folder.py"):
        for name in re.findall(r"actions/workflows/([\w.-]+\.yml)", (ROOT / doc).read_text()):
            assert (wf / name).exists(), (doc, name)
