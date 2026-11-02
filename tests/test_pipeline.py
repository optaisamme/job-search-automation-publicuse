"""Pipeline, verification, dedupe, newness and notification tests (TEST FIXTURES only)."""
import json

from jobsearch import pipeline, verify
from jobsearch.models import RawPosting
from jobsearch.store import Store

from conftest import FakeClient, gh_job, setup_board, job_page, GOOD_DESC


def run(root, client, sources=("ats_watchlist",)):
    return pipeline.run(root, root / "data/jobs.sqlite", sources=list(sources), use_renderer=False, client=client, fixtures=True)


def notifs(root):
    st = Store(root / "data/jobs.sqlite")
    return [dict(r) for r in st.db.execute("SELECT * FROM notifications ORDER BY id")]


def jobs(root):
    st = Store(root / "data/jobs.sqlite")
    return [dict(r) for r in st.db.execute("SELECT * FROM jobs ORDER BY id")]


# ---------------------------------------------------------------- verification
def test_verified_job_qualifies(root):
    c = FakeClient()
    setup_board(c, [gh_job(1, "Salesforce Administrator")])
    info = run(root, c)
    j = jobs(root)[0]
    assert j["status"] == "Qualified", j["reasons"]
    assert json.loads(j["verification"])["apply_route"] == "employer_ats"
    assert info["is_baseline"]


def test_closed_job_detected_via_ats_api(root):
    c = FakeClient()
    job = gh_job(1, "Salesforce Administrator")
    setup_board(c, [job])
    del c.routes["https://boards-api.greenhouse.io/v1/boards/acme/jobs/1?pay_transparency=true"]
    p = RawPosting("greenhouse", job["absolute_url"], "Acme Nonprofit", job["title"], "", ats="greenhouse",
                   ats_board="acme", ats_job_id="1", canonical_url=job["absolute_url"], apply_url=job["absolute_url"], authoritative=True)
    assert verify.verify(c, p, use_renderer=False).status == "closed"


def test_misleading_http_200_closed_page(root):
    c = FakeClient()
    c.set("https://careers.example.org/jobs/77", job_page("Salesforce Administrator", "Example Org", apply=False, closed=True))
    p = RawPosting("employer_page", "x", "Example Org", "Salesforce Administrator", "", canonical_url="https://careers.example.org/jobs/77",
                   apply_url="https://careers.example.org/jobs/77", authoritative=True)
    v = verify.verify(c, p, use_renderer=False)
    assert v.http_status == 200 and v.status == "closed"


def test_generic_careers_redirect(root):
    c = FakeClient()
    c.set("https://example.org/jobs/77", "<html><title>Careers</title><body>Join our team! See open roles.</body></html>",
          final_url="https://example.org/careers")
    p = RawPosting("employer_page", "x", "Example Org", "Salesforce Administrator", "", canonical_url="https://example.org/jobs/77",
                   apply_url="https://example.org/jobs/77", authoritative=True)
    v = verify.verify(c, p, use_renderer=False)
    assert v.status == "generic" and v.final_url == "https://example.org/careers"


def test_redirect_to_different_job(root):
    c = FakeClient()
    c.set("https://job-boards.greenhouse.io/acme/jobs/5", job_page("Data Engineer", "Acme"),
          final_url="https://job-boards.greenhouse.io/acme/jobs/9")
    p = RawPosting("employer_page", "x", "Acme", "Salesforce Administrator", "", canonical_url="https://job-boards.greenhouse.io/acme/jobs/5",
                   apply_url="https://job-boards.greenhouse.io/acme/jobs/5", authoritative=True)
    assert verify.verify(c, p, use_renderer=False).status == "mismatch"


def test_page_without_apply_route_not_verified(root):
    c = FakeClient()
    c.set("https://example.org/jobs/1", job_page("Salesforce Administrator", "Example Org", apply=False))
    p = RawPosting("employer_page", "x", "Example Org", "Salesforce Administrator", "", canonical_url="https://example.org/jobs/1",
                   apply_url="https://example.org/jobs/1", authoritative=True)
    assert verify.verify(c, p, use_renderer=False).status == "unverified"


def test_third_party_listing_with_working_link_qualifies_labeled(root):
    c = FakeClient()
    url = "https://remotive.com/remote-jobs/x/salesforce-administrator-9"
    c.set("https://remotive.com/api/remote-jobs?search=Salesforce+Administrator&limit=100", {"jobs": [{
        "id": 9, "url": url, "title": "Salesforce Administrator",
        "company_name": "Unknown Co", "candidate_required_location": "USA", "description": GOOD_DESC}]})
    c.set(url, job_page("Salesforce Administrator", "Unknown Co"))
    run(root, c, sources=("remotive",))
    j = jobs(root)[0]
    assert j["status"] == "Qualified"
    assert json.loads(j["verification"])["apply_route"] == "third_party"


def test_third_party_listing_with_dead_link_needs_verification(root):
    c = FakeClient()
    c.set("https://remotive.com/api/remote-jobs?search=Salesforce+Administrator&limit=100", {"jobs": [{
        "id": 9, "url": "https://www.linkedin.com/jobs/view/1", "title": "Salesforce Administrator",
        "company_name": "Unknown Co", "candidate_required_location": "USA", "description": GOOD_DESC}]})
    run(root, c, sources=("remotive",))
    assert jobs(root)[0]["status"] == "Needs Verification"
    assert not any("linkedin.com" in u for u in c.calls)


# ---------------------------------------------------------------- dedupe
def test_duplicate_across_boards(root):
    c = FakeClient()
    job = gh_job(1, "Salesforce Administrator")
    setup_board(c, [job])
    c.set("https://remotive.com/api/remote-jobs?search=Salesforce+Administrator&limit=100", {"jobs": [{
        "id": 9, "url": "https://remotive.com/remote-jobs/x/salesforce-administrator-9", "title": "Salesforce Administrator",
        "company_name": "Acme Nonprofit", "candidate_required_location": "USA", "description": GOOD_DESC}]})
    c.set("https://remoteok.com/api", [{"legal": "notice"}, {
        "id": 3, "url": "https://remoteok.com/remote-jobs/3", "company": "Acme Nonprofit", "position": "Sr. Salesforce Administrator",
        "description": GOOD_DESC, "location": "USA", "apply_url": job["absolute_url"]}])
    run(root, c, sources=("ats_watchlist", "remotive", "remoteok"))
    js = jobs(root)
    gh = [j for j in js if j["ats_job_id"] == "1"]
    assert len(gh) == 1
    srcs = json.loads(gh[0]["source_urls"])
    assert any("remoteok.com" in s for s in srcs)  # third-party copy merged into the employer record


# ---------------------------------------------------------------- baseline / newness
def test_baseline_suppresses_alerts_and_repeat_suppression(root):
    c = FakeClient()
    setup_board(c, [gh_job(1, "Salesforce Administrator")])
    run(root, c)
    n = notifs(root)
    assert len(n) == 1 and n[0]["status"] == "suppressed_baseline"
    run(root, c)
    assert len(notifs(root)) == 1  # no repeat


def test_new_job_after_baseline_queued_once(root):
    c = FakeClient()
    setup_board(c, [gh_job(1, "Salesforce Administrator")])
    run(root, c)
    setup_board(c, [gh_job(1, "Salesforce Administrator"), gh_job(2, "Salesforce Business Systems Analyst")])
    info = run(root, c)
    assert info["counts"]["notifications_queued"] == 1
    pend = [x for x in notifs(root) if x["status"] == "pending"]
    assert len(pend) == 1 and pend[0]["kind"] == "new"
    run(root, c)
    assert len([x for x in notifs(root) if x["status"] == "pending"]) == 1


def test_minor_edit_not_new(root):
    c = FakeClient()
    setup_board(c, [gh_job(1, "Salesforce Administrator")])
    run(root, c)
    setup_board(c, [gh_job(1, "Salesforce Administrator", desc=GOOD_DESC + "<p>Updated 2026-10-15.</p>")])
    run(root, c)
    assert len(jobs(root)) == 1 and len(notifs(root)) == 1


def test_newly_verified_label(root):
    c = FakeClient()
    nosal = GOOD_DESC.replace("<p>The base salary range for this role is $95,000 - $115,000.</p>", "")
    setup_board(c, [gh_job(1, "Salesforce Administrator", desc=nosal)])
    run(root, c)
    assert jobs(root)[0]["status"] == "Needs Verification"
    setup_board(c, [gh_job(1, "Salesforce Administrator")])
    run(root, c)
    n = [x for x in notifs(root) if x["status"] == "pending"]
    assert jobs(root)[0]["status"] == "Qualified"
    assert len(n) == 1 and n[0]["kind"] == "newly_verified"


def test_repost_with_new_id_after_notified_is_suppressed(root):
    c = FakeClient()
    setup_board(c, [gh_job(1, "Salesforce Administrator")])
    run(root, c)  # baseline (counts as notified)
    setup_board(c, [gh_job(5, "Salesforce Administrator", req="R-200")])
    del c.routes["https://boards-api.greenhouse.io/v1/boards/acme/jobs/1?pay_transparency=true"]
    run(root, c)
    js = jobs(root)
    new = [j for j in js if j["ats_job_id"] == "5"][0]
    assert new["repost_of"] is not None and "Possible repost" in new["repost_note"]
    assert not [x for x in notifs(root) if x["status"] == "pending"]
    old = [j for j in js if j["ats_job_id"] == "1"][0]
    assert old["closed_at"] is not None


def test_repost_of_unnotified_job_is_flagged_not_hidden(root):
    c = FakeClient()
    setup_board(c, [gh_job(1, "Salesforce Administrator")])
    run(root, c)
    setup_board(c, [gh_job(1, "Salesforce Administrator"), gh_job(2, "Salesforce Business Systems Analyst")])
    run(root, c)  # job 2 queued as new
    setup_board(c, [gh_job(1, "Salesforce Administrator"), gh_job(8, "Salesforce Business Systems Analyst")])
    del c.routes["https://boards-api.greenhouse.io/v1/boards/acme/jobs/2?pay_transparency=true"]
    run(root, c)
    j8 = [j for j in jobs(root) if j["ats_job_id"] == "8"][0]
    assert j8["repost_of"] is not None
    n = notifs(root)
    # job 2's undelivered alert is cancelled (closed); job 8 alert carries the repost note
    assert [x for x in n if x["job_id"] == j8["id"]][0]["status"] == "pending"
    assert "Possible repost" in json.loads([x for x in n if x["job_id"] == j8["id"]][0]["payload"])["repost_note"]


# ---------------------------------------------------------------- delivery retries
def _publish_first_run(root, c):
    out = pipeline.prepare_outbox(root, root / "data/jobs.sqlite", client=c, use_renderer=False)
    st = Store(root / "data/jobs.sqlite")
    for nid in out["notification_ids"]:
        st.mark_notification(nid, "delivered", channel="github_issue", ref="1")
    return out


def test_first_run_matches_posted_once_as_initial_results(root):
    c = FakeClient()
    setup_board(c, [gh_job(1, "Salesforce Administrator")])
    run(root, c)
    out = _publish_first_run(root, c)
    assert out["draft"]["subject"].startswith("Job search results (first run): 1 matching job")
    assert "INITIAL RESULTS" in out["draft"]["body"]
    run(root, c)
    assert pipeline.prepare_outbox(root, root / "data/jobs.sqlite", client=c, use_renderer=False)["draft"] is None


def test_notification_retry_without_duplicates(root):
    c = FakeClient()
    setup_board(c, [gh_job(1, "Salesforce Administrator")])
    run(root, c)
    _publish_first_run(root, c)
    setup_board(c, [gh_job(1, "Salesforce Administrator"), gh_job(2, "Salesforce Business Systems Analyst")])
    run(root, c)
    out = pipeline.prepare_outbox(root, root / "data/jobs.sqlite", client=c, use_renderer=False)
    assert len(out["notification_ids"]) == 1 and out["draft"]["subject"].startswith("Job search results: 1 matching job")
    nid = out["notification_ids"][0]
    st = Store(root / "data/jobs.sqlite")
    st.mark_notification(nid, "failed", error="gmail 500")
    out2 = pipeline.prepare_outbox(root, root / "data/jobs.sqlite", client=c, use_renderer=False)
    assert out2["notification_ids"] == [nid]  # retried
    st.mark_notification(nid, "delivered", channel="gmail_draft", ref="draft-1")
    st.mark_notification(nid, "delivered", channel="gmail_draft", ref="draft-1")  # idempotent
    out3 = pipeline.prepare_outbox(root, root / "data/jobs.sqlite", client=c, use_renderer=False)
    assert out3["notification_ids"] == [] and out3["draft"] is None
    import pytest
    with pytest.raises(ValueError):
        st.mark_notification(nid, "failed")
    run(root, c)
    assert len(notifs(root)) == 2  # still one baseline + one delivered


def test_presend_reverification_holds_closed_job(root):
    c = FakeClient()
    setup_board(c, [gh_job(1, "Salesforce Administrator")])
    run(root, c)
    _publish_first_run(root, c)
    setup_board(c, [gh_job(1, "Salesforce Administrator"), gh_job(2, "Salesforce Business Systems Analyst")])
    run(root, c)
    c.set("https://job-boards.greenhouse.io/acme/jobs/2", job_page("Salesforce Business Systems Analyst", "Acme Nonprofit", apply=False, closed=True))
    out = pipeline.prepare_outbox(root, root / "data/jobs.sqlite", client=c, use_renderer=False)
    assert out["notification_ids"] == [] and out["held"]


def test_dry_run_does_not_persist(root):
    c = FakeClient()
    setup_board(c, [gh_job(1, "Salesforce Administrator")])
    pipeline.run(root, root / "data/jobs.sqlite", dry_run=True, sources=["ats_watchlist"], use_renderer=False, client=c, fixtures=True)
    assert not (root / "data/jobs.sqlite").exists()
    assert (root / "out/practice-run/full_report.md").exists()


def test_report_sections(root):
    c = FakeClient()
    bad = GOOD_DESC.replace("$95,000 - $115,000", "$90,000 - $100,000")
    setup_board(c, [gh_job(1, "Salesforce Administrator"), gh_job(2, "Senior Salesforce Administrator", desc=bad)])
    info = run(root, c)
    md = open(info["report"]).read()
    for h in ("## Jobs that match all your rules", "## Jobs that need checking", "## Jobs that did not match", "## Where jobs were looked for", "TEST DATA"):
        assert h in md
    assert "upper $100,000 not > $100,000" in md


def test_all_blocked_run_is_not_baseline(root):
    c = FakeClient()  # every URL 404 / nothing returned
    (root / "data/boards.json").write_text("{}")
    info = run(root, c, sources=("ats_watchlist", "web_search_leads"))
    assert not info["is_baseline"]
    assert not Store(root / "data/jobs.sqlite").baseline_done()


def test_closed_lead_marked_closed_not_rejected(root):
    c = FakeClient()
    (root / "data/leads.json").write_text(json.dumps([{"url": "https://job-boards.greenhouse.io/acme/jobs/404", "title": "Salesforce Administrator", "employer": "Acme Nonprofit"}]))
    c.set("https://boards-api.greenhouse.io/v1/boards/acme/jobs?content=true", {"jobs": []})
    run(root, c, sources=("web_search_leads", "ats_watchlist"))
    j = jobs(root)[0]
    assert j["status"] == "Closed" and j["closed_at"]


def test_job_board_lead_without_text_is_not_rejected(root):
    c = FakeClient()
    (root / "data/leads.json").write_text(json.dumps([{"url": "https://www.linkedin.com/jobs/view/123", "title": "Salesforce Administrator", "employer": "Acme Nonprofit"}]))
    run(root, c, sources=("web_search_leads",))
    j = jobs(root)[0]
    assert j["status"] == "Needs Verification"
    assert "linkedin.com/jobs/view/123" not in " ".join(c.calls)  # job board never fetched


def test_dedupe_ignores_location_label_differences(root):
    c = FakeClient()
    job = gh_job(1, "Salesforce Administrator")
    setup_board(c, [job])
    c.set("https://remotive.com/api/remote-jobs?search=Salesforce+Administrator&limit=100", {"jobs": [{
        "id": 9, "url": "https://remotive.com/remote-jobs/x/9", "title": "Salesforce Administrator",
        "company_name": "Acme Nonprofit", "candidate_required_location": "United States", "description": GOOD_DESC}]})
    run(root, c, sources=("ats_watchlist", "remotive"))
    assert len(jobs(root)) == 1


def test_one_criterion_near_miss_shared_once(root):
    c = FakeClient()
    setup_board(c, [gh_job(1, "Salesforce Administrator")])
    run(root, c)  # baseline
    bad_salary = GOOD_DESC.replace("$95,000 - $115,000", "$90,000 - $100,000")
    two_fail = bad_salary.replace("anywhere in the United States", "in Canada").replace("Remote - US", "Remote - Canada")
    setup_board(c, [gh_job(1, "Salesforce Administrator"), gh_job(2, "Senior Salesforce Administrator", desc=bad_salary),
                    gh_job(3, "Salesforce Business Systems Analyst", desc=two_fail)])
    c.set("https://boards-api.greenhouse.io/v1/boards/acme/jobs/3?pay_transparency=true",
          dict(gh_job(3, "Salesforce Business Systems Analyst", desc=two_fail), location={"name": "Remote - Canada"}))
    run(root, c)
    out = pipeline.prepare_outbox(root, root / "data/jobs.sqlite", client=c, use_renderer=False)
    body = out["draft"]["body"]
    assert "NEAR MISSES" in body and "Senior Salesforce Administrator — Acme Nonprofit" in body
    assert "  • salary:" in body and "Salesforce Business Systems Analyst" not in body  # two failures: not a near miss
    st = Store(root / "data/jobs.sqlite")
    for nid in out["notification_ids"]:
        st.mark_notification(nid, "delivered", channel="chat", ref="t")
    run(root, c)
    out2 = pipeline.prepare_outbox(root, root / "data/jobs.sqlite", client=c, use_renderer=False)
    assert out2["draft"] is None  # not repeated


def test_near_miss_does_not_block_later_qualified_alert(root):
    c = FakeClient()
    setup_board(c, [gh_job(1, "Salesforce Administrator")])
    run(root, c)
    bad = GOOD_DESC.replace("$95,000 - $115,000", "$90,000 - $100,000")
    setup_board(c, [gh_job(1, "Salesforce Administrator"), gh_job(2, "Senior Salesforce Administrator", desc=bad)])
    run(root, c)
    out = pipeline.prepare_outbox(root, root / "data/jobs.sqlite", client=c, use_renderer=False)
    st = Store(root / "data/jobs.sqlite")
    for nid in out["notification_ids"]:
        st.mark_notification(nid, "delivered", channel="chat", ref="t")
    setup_board(c, [gh_job(1, "Salesforce Administrator"), gh_job(2, "Senior Salesforce Administrator")])
    run(root, c)
    out2 = pipeline.prepare_outbox(root, root / "data/jobs.sqlite", client=c, use_renderer=False)
    assert out2["draft"] and "NEWLY VERIFIED" in out2["draft"]["body"]


def test_results_folder_numbered_reports(root):
    from jobsearch import results_folder
    c = FakeClient()
    setup_board(c, [gh_job(1, "Salesforce Administrator")])
    run(root, c)
    out1 = results_folder.write(root)
    run(root, c)
    out2 = results_folder.write(root)
    folder = root / "JOB_SEARCH_RESULTS"
    names = sorted(p.name for p in folder.glob("REPORT_*.md"))
    assert len(names) == 2 and names[0].startswith("REPORT_001_") and names[1].startswith("REPORT_002_") and names[0].endswith("_UTC.md")
    index = (folder / "README.md").read_text()
    assert index.startswith("# JOB SEARCH RESULTS") and names[1] in index and "Salesforce Administrator" in index
    assert index.index(names[1]) < index.rindex(names[0])  # newest first
    rep = (folder / names[1]).read_text()
    assert "Every job checked in this search" in rep and "Jobs that match all your rules (1)" in rep


def test_plain_language_link_messages():
    from jobsearch.verify import plain_link_reason
    from jobsearch.models import Verification
    m = plain_link_reason(Verification("blocked", detail="HTTP 403 at https://himalayas.app/companies/x/jobs/y?utm_source=api"))
    assert "himalayas.app website does not allow automated checks" in m and "error 403" in m and "Open the link yourself" in m
    assert "HTTP 403 at" not in m
    assert "no longer exists" in plain_link_reason(Verification("closed", detail="HTTP 404"))


# ---------------------------------------------------------------- companies to watch (settings section 7)
def test_parse_board_link_variants():
    from jobsearch.adapters.ats import parse_board_link
    assert parse_board_link("https://job-boards.greenhouse.io/examplecompany") == ("greenhouse", "examplecompany")
    assert parse_board_link("https://boards.greenhouse.io/examplecompany/") == ("greenhouse", "examplecompany")
    assert parse_board_link("https://job-boards.greenhouse.io/examplecompany/jobs/123") == ("greenhouse", "examplecompany")
    assert parse_board_link("https://jobs.lever.co/another?team=x") == ("lever", "another")
    assert parse_board_link("https://jobs.ashbyhq.com/third") == ("ashby", "third")
    assert parse_board_link("https://jobs.smartrecruiters.com/Fourth") == ("smartrecruiters", "Fourth")
    assert parse_board_link("https://www.example.com/careers") is None


def test_watched_company_scanned_but_not_saved(root):
    (root / "data/boards.json").write_text("{}")
    s = root / "config/settings.toml"
    s.write_text(s.read_text() + '\n[companies_to_watch]\njob_page_links = ["https://job-boards.greenhouse.io/beta"]\n')
    c = FakeClient()
    setup_board(c, [gh_job(7, "Salesforce Administrator", board="beta")], board="beta", employer="Beta Org")
    run(root, c)
    assert [j["employer"] for j in jobs(root)] == ["Beta Org"]
    assert json.loads((root / "data/boards.json").read_text()) == {}


def test_check_reports_unknown_company_link(root, capsys):
    from jobsearch import cli
    s = root / "config/settings.toml"
    s.write_text(s.read_text() + '\n[companies_to_watch]\njob_page_links = ["https://www.example.com/careers"]\n')
    assert cli.main(["--root", str(root), "check"]) == 1
    assert "COMPANY LINK NOT UNDERSTOOD: https://www.example.com/careers" in capsys.readouterr().out


def test_results_page_lists_possible_matches(root):
    from jobsearch import results_folder
    c = FakeClient()
    setup_board(c, [gh_job(1, "Salesforce Administrator")])
    run(root, c)
    st = Store(root / "data/jobs.sqlite")
    st.db.execute("UPDATE jobs SET status='Needs Verification', reasons=?",
                  (json.dumps(["salary: no salary listed", "location: not clear which states"]),))
    st.db.commit()
    index = results_folder.write(root)["text"]
    assert "## Possible matches: check these yourself (1)" in index
    assert "salary: no salary listed; location: not clear which states" in index


def test_title_words_any_order():
    from jobsearch.titles import TitleMatcher
    m = TitleMatcher({"titles": [{"track": "", "family": "G1", "plain_titles": ["Data Analyst"], "require_any": []}]})
    assert m.match_title("Senior Data Analyst") and m.match_title("Analyst, Data Platform")
    assert not m.match_title("Data Analytics Lead") and not m.match_title("Data Engineer")


def test_new_job_sites_parse():
    from jobsearch.adapters.aggregators import TheMuseAdapter, JobicyAdapter, WeWorkRemotelyAdapter, WorkingNomadsAdapter
    from jobsearch.adapters.base import SourceStatus
    c = FakeClient()
    c.set("https://www.themuse.com/api/public/jobs?page=1&location=Flexible+%2F+Remote",
          {"page": 1, "page_count": 1, "results": [{"id": 1, "name": "Data Analyst", "contents": "<p>Remote</p>",
           "locations": [{"name": "Flexible / Remote"}], "company": {"name": "Muse Co"},
           "refs": {"landing_page": "https://www.themuse.com/jobs/museco/data-analyst"}}]})
    c.set("https://jobicy.com/api/v2/remote-jobs?count=100&geo=usa",
          {"jobs": [{"jobTitle": "Data Analyst", "companyName": "Jobicy Co", "url": "https://jobicy.com/jobs/1",
                     "jobDescription": "<p>x</p>", "jobGeo": "USA", "jobType": ["Full-Time"],
                     "salaryMin": 95000, "salaryMax": 115000, "salaryCurrency": "USD", "salaryPeriod": "yearly"}]})
    c.set("https://weworkremotely.com/remote-jobs.rss",
          "<rss><channel><item><title>WWR Co: Data Analyst</title><region>USA Only</region>"
          "<link>https://weworkremotely.com/remote-jobs/wwr-data-analyst</link><description>&lt;p&gt;x&lt;/p&gt;</description>"
          "</item></channel></rss>")
    c.set("https://www.workingnomads.com/api/exposed_jobs/",
          [{"url": "https://www.workingnomads.com/job/go/1/", "title": "Data Analyst", "company_name": "WN Co",
            "description": "<p>x</p>", "location": "USA"}])
    ctx = {"queries": []}
    got = {}
    for A in (TheMuseAdapter, JobicyAdapter, WeWorkRemotelyAdapter, WorkingNomadsAdapter):
        got[A.name] = A(c, ctx).search(SourceStatus(A.name))
    assert got["themuse"][0].employer == "Muse Co" and got["themuse"][0].workplace_type == "remote"
    assert got["jobicy"][0].structured_salaries[0]["min"] == 95000
    assert (got["weworkremotely"][0].employer, got["weworkremotely"][0].title) == ("WWR Co", "Data Analyst")
    assert got["workingnomads"][0].employer == "WN Co"


def test_himalayas_feed_listing_counts_when_site_blocks_checks():
    import time
    from jobsearch.verify import feed_listing
    from jobsearch.models import Verification
    blocked = Verification("blocked", final_url="https://himalayas.app/companies/x/jobs/y", detail="HTTP 403")
    p = RawPosting("himalayas", "https://himalayas.app/companies/x/jobs/y", "X", "Data Analyst", "",
                   apply_url="https://himalayas.app/companies/x/jobs/y", extra={"expiry": str(int(time.time()) + 86400)})
    v = feed_listing(p, blocked, "now")
    assert v.status == "verified" and v.apply_route == "third_party" and "link itself was not opened" in v.detail
    p.extra["expiry"] = str(int(time.time()) - 60)
    assert feed_listing(p, blocked, "now") is None            # closing date passed
    p.extra["expiry"] = None
    assert feed_listing(p, blocked, "now") is None            # no closing date
    other = RawPosting("remoteok", "u", "X", "Data Analyst", "", extra={"expiry": str(int(time.time()) + 86400)})
    assert feed_listing(other, blocked, "now") is None        # only Himalayas


def test_jobspresso_and_jooble_parse(monkeypatch):
    from jobsearch.adapters.aggregators import JobspressoAdapter, JoobleAdapter
    from jobsearch.adapters.base import SourceStatus
    c = FakeClient()
    c.set("https://jobspresso.co/feed/?post_type=job_listing",
          '<rss xmlns:dc="http://purl.org/dc/elements/1.1/"><channel><item><title>Data Analyst</title>'
          '<link>https://jobspresso.co/job/data-analyst</link><dc:creator>Figma&lt;br&gt;&#9906;&amp;nbsp;United States</dc:creator>'
          '<description>&lt;p&gt;x&lt;/p&gt;</description></item></channel></rss>')
    p = JobspressoAdapter(c, {"queries": []}).search(SourceStatus("jobspresso"))[0]
    assert (p.employer, p.location_text, p.title) == ("Figma", "United States", "Data Analyst")
    monkeypatch.setenv("JOOBLE_API_KEY", "k")
    c.set("https://jooble.org/api/k", {"totalCount": 1, "jobs": [{"id": 5, "title": "<b>Data</b> Analyst", "company": "J Co",
          "location": "Remote", "snippet": "x", "salary": "$100k", "link": "https://jooble.org/desc/5", "source": "example.com"}]})
    j = JoobleAdapter(c, {"queries": ["Data Analyst"]}).search(SourceStatus("jooble"))
    assert len(j) == 1 and j[0].title == "Data Analyst" and j[0].workplace_type == "remote"


def test_manual_board_links_use_job_titles():
    from jobsearch.manual_boards import section
    md = "\n".join(section(["Data Analyst", "Program Manager"], True))
    assert "https://www.linkedin.com/jobs/search/?keywords=Data+Analyst&f_WT=2" in md
    assert "https://www.idealist.org/en/jobs?q=Program+Manager" in md
    assert "Search: Data Analyst" in md and "Tech Jobs for Good" in md
    assert "https://diversityjobs.com/candidate/job_search/quick/results?keyword=Data+Analyst&location=remote" in md
    assert "https://www.greenjobsboard.us/jobs?search=Data+Analyst" in md and "HigherEdJobs" in md
    assert "Add a job title" in "\n".join(section([], True))


def test_reliefweb_parse(monkeypatch):
    from jobsearch.adapters.aggregators import ReliefWebAdapter
    from jobsearch.adapters.base import SourceStatus
    monkeypatch.setenv("RELIEFWEB_APPNAME", "app")
    c = FakeClient()
    url = ("https://api.reliefweb.int/v2/jobs?appname=app&profile=full&limit=50&sort%5B%5D=date.created%3Adesc"
           "&query%5Bvalue%5D=Program+Manager&query%5Bfields%5D%5B%5D=title")
    c.set(url, {"data": [{"id": "1", "fields": {"title": "Program Manager", "url": "https://reliefweb.int/job/1/pm",
                "body": "Remote, United States", "source": [{"name": "Example Relief"}], "country": [{"name": "United States of America"}],
                "date": {"created": "2026-11-01", "closing": "2026-12-01"}}}]})
    got = ReliefWebAdapter(c, {"queries": ["Program Manager"]}).search(SourceStatus("reliefweb"))
    assert len(got) == 1 and got[0].employer == "Example Relief" and got[0].extra["close_date"] == "2026-12-01"
