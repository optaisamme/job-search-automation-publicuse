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
    for h in ("## Jobs that match all your rules", "## Jobs that need checking", "## Jobs that did not match", "## Where this search looked", "TEST DATA"):
        assert h in md
    assert "ends at $100,000, not above $100,000" in md


def test_all_blocked_run_is_not_baseline(root):
    c = FakeClient()  # every URL 404 / nothing returned
    (root / "data/boards.json").write_text("{}")
    info = run(root, c, sources=("ats_watchlist",))
    assert not info["is_baseline"]
    assert not Store(root / "data/jobs.sqlite").baseline_done()


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
    assert "  • Salary:" in body and "Salesforce Business Systems Analyst" not in body  # two failures: not a near miss
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


def test_jobspresso_parse():
    from jobsearch.adapters.aggregators import JobspressoAdapter
    from jobsearch.adapters.base import SourceStatus
    c = FakeClient()
    c.set("https://jobspresso.co/feed/?post_type=job_listing",
          '<rss xmlns:dc="http://purl.org/dc/elements/1.1/"><channel><item><title>Data Analyst</title>'
          '<link>https://jobspresso.co/job/data-analyst</link><dc:creator>Figma&lt;br&gt;&#9906;&amp;nbsp;United States</dc:creator>'
          '<description>&lt;p&gt;x&lt;/p&gt;</description></item></channel></rss>')
    p = JobspressoAdapter(c, {"queries": []}).search(SourceStatus("jobspresso"))[0]
    assert (p.employer, p.location_text, p.title) == ("Figma", "United States", "Data Analyst")


def test_manual_board_links_use_job_titles():
    from jobsearch.manual_boards import section
    md = "\n".join(section(["Data Analyst", "Program Manager"], True))
    assert "https://www.linkedin.com/jobs/search/?keywords=Data+Analyst&f_WT=2" in md
    assert "https://www.idealist.org/en/jobs?q=Program+Manager" in md
    assert "https://reliefweb.int/jobs?search=Program+Manager" in md
    assert "Search: Data Analyst" in md and "Tech Jobs for Good" in md
    assert "https://diversityjobs.com/candidate/job_search/quick/results?keyword=Data+Analyst&location=remote" in md
    assert "https://www.greenjobsboard.us/jobs?search=Data+Analyst" in md and "HigherEdJobs" in md
    assert "https://remote100k.com/remote-jobs/usa" in md
    assert "Add a job title" in "\n".join(section([], True))


def test_manual_boards_grouped_and_use_state():
    from jobsearch.manual_boards import section, BOARDS
    md = "\n".join(section(["Program Manager"], False, "New Mexico"))
    assert len(BOARDS) == 32 and "### Students, early career, hourly and government" in md
    assert "find-jobs-results.aspx?keyword=Program+Manager&location=New+Mexico" in md
    assert "https://www.indeed.com/jobs?q=Program+Manager&l=New+Mexico" in md
    assert "https://wellfound.com/role/r/program-manager" in md


def test_hackernews_who_is_hiring_parse():
    from jobsearch.adapters.aggregators import HackerNewsHiringAdapter
    from jobsearch.adapters.base import SourceStatus
    from jobsearch.titles import TitleMatcher
    c = FakeClient()
    c.set("https://hn.algolia.com/api/v1/search_by_date?tags=story,author_whoishiring&hitsPerPage=10",
          {"hits": [{"objectID": "9", "title": "Ask HN: Who wants to be hired? (November 2026)"},
                    {"objectID": "8", "title": "Ask HN: Who is hiring? (November 2026)"}]})
    c.set("https://hn.algolia.com/api/v1/items/8", {"children": [
        {"id": 1, "text": 'Acme | Data Analyst | REMOTE (US) | Full-time<p>Apply: <a href="https://acme.example/jobs/1">here</a>'},
        {"id": 2, "text": "Just a comment"}]})
    m = TitleMatcher({"titles": [{"track": "", "family": "G", "plain_titles": ["Data Analyst"], "require_any": []}]})
    got = HackerNewsHiringAdapter(c, {"queries": [], "title_matcher": m}).search(SourceStatus("hackernews"))
    assert len(got) == 1 and (got[0].employer, got[0].title) == ("Acme", "Data Analyst")
    assert got[0].apply_url == "https://acme.example/jobs/1" and got[0].workplace_type == "remote"


def test_results_page_lists_companies_checked_every_search(root):
    from jobsearch import results_folder
    s = root / "config/settings.toml"
    s.write_text(s.read_text() + '\n[companies_to_watch]\njob_page_links = ["https://jobs.lever.co/betaorg"]\n')
    c = FakeClient()
    setup_board(c, [gh_job(1, "Salesforce Administrator")])
    run(root, c)
    index = results_folder.write(root)["text"]
    assert "## Companies checked every search" in index
    assert "| Acme Nonprofit | Greenhouse | found automatically |" in index
    assert "| betaorg | Lever | you added it (section 7) |" in index


def test_web_search_finds_job_and_remembers_company(root, monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")
    (root / "data/boards.json").write_text("{}")
    c = FakeClient()
    setup_board(c, [gh_job(1, "Salesforce Administrator")])
    c.set("https://api.tavily.com/search", {"results": [
        {"url": "https://job-boards.greenhouse.io/acme/jobs/1", "title": "Job Application for Salesforce Administrator at Acme Nonprofit",
         "content": "Remote within the United States. Salesforce administration."},
        {"url": "https://www.linkedin.com/jobs/view/1", "title": "Salesforce Administrator", "content": "x"}]})
    info = run(root, c, sources=("websearch", "ats_watchlist"))
    js = jobs(root)
    assert len(js) == 1 and js[0]["status"] == "Qualified", [(j["title"], j["status"], j["reasons"]) for j in js]
    assert js[0]["employer"] == "Acme Nonprofit"
    saved = json.loads((root / "data/boards.json").read_text())
    assert [b["board"] for b in saved.get("greenhouse", [])] == ["acme"]
    ws = next(s for s in info["sources"] if s["name"] == "websearch")
    assert ws["state"] == "ok" and "searches" in ws["detail"]


def test_web_search_off_without_key(root, monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    info = run(root, FakeClient(), sources=("websearch",))
    assert next(s for s in info["sources"] if s["name"] == "websearch")["state"] == "needs_credentials"


def test_web_search_result_titles():
    from jobsearch.adapters.websearch import _clean_title
    assert _clean_title("Job Application for Data Analyst at Acme", "https://job-boards.greenhouse.io/acme/jobs/1") == ("Data Analyst", "Acme")
    assert _clean_title("Acme - Data Analyst", "https://jobs.lever.co/acme/0b1c2d3e-0000-0000-0000-000000000000") == ("Data Analyst", "Acme")
    assert _clean_title("Data Analyst @ Acme", "https://jobs.ashbyhq.com/acme/x") == ("Data Analyst", "Acme")


def test_web_search_rejected_key_reported_as_error(root, monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-wrong")
    c = FakeClient()
    c.set("https://api.tavily.com/search", {"detail": {"error": "Unauthorized"}}, status=401)
    info = run(root, c, sources=("websearch",))
    ws = next(s for s in info["sources"] if s["name"] == "websearch")
    assert ws["state"] == "error" and "key was not accepted" in ws["detail"]


def test_web_search_skips_list_pages_and_cleans_titles():
    from jobsearch.adapters.websearch import _is_list_page, _clean_title
    assert _is_list_page("https://careers.labcorp.com/global/en/project-management-remote", "Project Management Remote Jobs")
    assert _is_list_page("https://jobs.apple.com/en-us/search?location=united-states-USA", "Search Jobs - United States")
    assert not _is_list_page("https://jobs.centene.com/us/en/jobs/1671643/program-manager-ii", "Program Manager II, Remote-CA | Centene Careers")
    assert _clean_title("Regional Program Manager - Myworkdayjobs.com", "https://jll.wd1.myworkdayjobs.com/x")[0] == "Regional Program Manager"


def test_agency_boards_never_saved(root):
    pipeline.save_boards(root, {}, [{"ats": "lever", "board": "jobgether", "employer": "Jobgether"},
                                    {"ats": "lever", "board": "betaorg", "employer": "Beta"}])
    saved = json.loads((root / "data/boards.json").read_text())
    assert [b["board"] for b in saved["lever"]] == ["betaorg"]


def test_browser_helper_gets_no_secrets(monkeypatch):
    from jobsearch.verify import render_env
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-secret")
    monkeypatch.setenv("GITHUB_TOKEN", "ghs-secret")
    env = render_env("job-search-automation/1.0")
    assert "TAVILY_API_KEY" not in env and "GITHUB_TOKEN" not in env
    assert env["JOBSEARCH_UA"] == "job-search-automation/1.0" and "PATH" in env


def test_issue_body_cannot_be_broken_out_of():
    import importlib.util, pathlib
    spec = importlib.util.spec_from_file_location("pub", pathlib.Path(__file__).parents[1] / "scripts/publish_github_issue.py")
    pub = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pub)
    body = pub.fenced("Data Analyst ```\n@someone ![x](https://example.com/x.png)")
    first = body.split("\n", 1)[0]
    assert first == "````text" and body.endswith("\n````")


def test_found_company_dropped_after_more_than_5_searches_without_match(root):
    (root / "data/boards.json").write_text(json.dumps({"greenhouse": [
        {"board": "acme", "employer": "Acme Nonprofit", "searches_without_match": 5},
        {"board": "quiet", "employer": "Quiet Co", "searches_without_match": 4}]}))
    c = FakeClient()
    setup_board(c, [gh_job(1, "Salesforce Administrator")])
    setup_board(c, [gh_job(2, "Office Manager", desc="<p>Run the front office. On site.</p>", board="quiet")], board="quiet", employer="Quiet Co")
    info = run(root, c)
    saved = {b["board"]: b["searches_without_match"] for b in json.loads((root / "data/boards.json").read_text())["greenhouse"]}
    assert saved == {"acme": 0, "quiet": 5}          # match resets; no match counts up
    run(root, c)
    saved = [b["board"] for b in json.loads((root / "data/boards.json").read_text())["greenhouse"]]
    assert saved == ["acme"]                           # 6th search in a row without a match: dropped


def test_section7_company_never_dropped(root):
    (root / "data/boards.json").write_text("{}")
    s = root / "config/settings.toml"
    s.write_text(s.read_text() + '\n[companies_to_watch]\njob_page_links = ["https://job-boards.greenhouse.io/quiet"]\n')
    c = FakeClient()
    setup_board(c, [gh_job(2, "Office Manager", desc="<p>Run the front office. On site.</p>", board="quiet")], board="quiet", employer="Quiet Co")
    for _ in range(7):
        run(root, c)
    assert json.loads((root / "data/boards.json").read_text()) == {}
    from jobsearch import pipeline as pl
    prof, _ = pl.load_config(root)
    assert [b["board"] for b in pl.watched_boards(prof)[0]] == ["quiet"]


def _load_publisher(root, monkeypatch, posted):
    import importlib.util, pathlib, io
    spec = importlib.util.spec_from_file_location("pub", pathlib.Path(__file__).parents[1] / "scripts/publish_github_issue.py")
    pub = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pub)
    monkeypatch.setattr(pub, "ROOT", root)
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.setenv("GITHUB_TOKEN", "t")

    class Resp(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def fake_urlopen(req, timeout=30):
        posted.append(json.loads(req.data))
        return Resp(json.dumps({"number": 7, "html_url": "https://github.com/owner/repo/issues/7"}).encode())
    monkeypatch.setattr(pub.urllib.request, "urlopen", fake_urlopen)
    return pub


def test_near_misses_are_not_posted_as_issues(root, monkeypatch):
    c = FakeClient()
    setup_board(c, [gh_job(1, "Salesforce Administrator")])
    run(root, c)  # baseline
    st = Store(root / "data/jobs.sqlite")
    first = pipeline.prepare_outbox(root, root / "data/jobs.sqlite", client=c, use_renderer=False)
    for nid in first["notification_ids"]:
        st.mark_notification(nid, "delivered", channel="test", ref="t")
    bad_salary = GOOD_DESC.replace("$95,000 - $115,000", "$90,000 - $100,000")
    setup_board(c, [gh_job(1, "Salesforce Administrator"), gh_job(2, "Senior Salesforce Administrator", desc=bad_salary)])
    run(root, c)
    out = pipeline.prepare_outbox(root, root / "data/jobs.sqlite", client=c, use_renderer=False)
    assert out["near_miss_ids"] and out["issue_draft"] is None
    (root / "out").mkdir(exist_ok=True)
    (root / "out/outbox.json").write_text(json.dumps(out))
    posted = []
    pub = _load_publisher(root, monkeypatch, posted)
    assert pub.main() == 0 and posted == []                     # near miss only: no issue
    st = Store(root / "data/jobs.sqlite")
    statuses = {r["status"] for r in st.db.execute("SELECT status FROM notifications WHERE kind='near_miss'")}
    assert statuses == {"delivered"}                            # shown on the results page instead
    # a new matching job: the issue lists it, without a near-miss section
    setup_board(c, [gh_job(1, "Salesforce Administrator"), gh_job(2, "Senior Salesforce Administrator", desc=bad_salary),
                    gh_job(3, "Salesforce Business Systems Analyst")])
    run(root, c)
    out = pipeline.prepare_outbox(root, root / "data/jobs.sqlite", client=c, use_renderer=False)
    (root / "out/outbox.json").write_text(json.dumps(out))
    assert pub.main() == 0 and len(posted) == 1
    assert "Salesforce Business Systems Analyst" in posted[0]["body"] and "NEAR MISSES" not in posted[0]["body"]


def test_results_tables_have_first_found_and_newest_first(root):
    from jobsearch import results_folder
    c = FakeClient()
    bad_salary = GOOD_DESC.replace("$95,000 - $115,000", "$90,000 - $100,000")
    setup_board(c, [gh_job(1, "Salesforce Administrator"), gh_job(2, "Salesforce Business Systems Analyst"),
                    gh_job(3, "Senior Salesforce Administrator", desc=bad_salary),
                    gh_job(4, "Lead Salesforce Administrator", desc=bad_salary)])
    run(root, c)
    st = Store(root / "data/jobs.sqlite")
    for title, day in [("Salesforce Administrator", "2026-10-01"), ("Salesforce Business Systems Analyst", "2026-10-05"),
                       ("Senior Salesforce Administrator", "2026-10-02"), ("Lead Salesforce Administrator", "2026-10-09")]:
        st.db.execute("UPDATE jobs SET first_seen=? WHERE title=?", (day + "T00:00:00+00:00", title))
    st.db.commit()
    index = results_folder.write(root)["text"]

    def table(heading):
        sec = index[index.index(heading):]
        sec = sec[:sec.find("\n## ", 3)]
        rows = [l for l in sec.splitlines() if l.startswith("|")]
        head = [x.strip() for x in rows[0].strip("|").split("|")]
        return head, [r.strip("|").split("|")[head.index("First found")].strip() for r in rows[2:]]

    head_q, q = table("## Jobs that match all your rules")
    head_n, n = table("## Near misses")
    assert "First found" in head_q and "First found" in head_n
    assert q == ["2026-10-05", "2026-10-01"] and n == ["2026-10-09", "2026-10-02"]


def test_report_lists_sites_and_web_search_criteria(root, monkeypatch):
    from jobsearch import results_folder
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")
    c = FakeClient()
    setup_board(c, [gh_job(1, "Salesforce Administrator")])
    c.set("https://api.tavily.com/search", {"results": [
        {"url": "https://job-boards.greenhouse.io/acme/jobs/1", "title": "Job Application for Salesforce Administrator at Acme Nonprofit",
         "content": "Remote within the United States."}]})
    info = run(root, c, sources=("websearch", "ats_watchlist", "remoteok"))
    md = open(info["report"]).read()
    for text in ("## Where this search looked", "| Web search (Tavily) |", "| Company careers pages |", "| Remote OK |",
                 "### Web search (Tavily) criteria", '"Salesforce Administrator" remote', "company careers pages",
                 "the wider web", "last 30 days", "Company careers pages read (1):** Acme Nonprofit"):
        assert text in md, text
    index = results_folder.write(root)["text"]
    assert "## Where this search looked" in index and '"Salesforce Administrator" remote' in index
    report = sorted((root / "JOB_SEARCH_RESULTS").glob("REPORT_*.md"))[-1].read_text()
    assert '"Salesforce Administrator" remote' in report      # each numbered report has its own criteria


def test_problems_are_plain_sentences():
    from jobsearch.plain_errors import plain_error
    msg = plain_error("web_search_leads: https://www.careerbuilder.com/job-details/x: AccessBlocked: HTTP 403 at https://www.careerbuilder.com/job-details/x")
    assert "careerbuilder.com refused automated access (error 403)" in msg and "AccessBlocked" not in msg
    assert msg.endswith("Page: https://www.careerbuilder.com/job-details/x")
    assert plain_error("remoteok: query 'Data Analyst': HTTP 404") == 'Remote OK, while searching for "Data Analyst": the page was not found (error 404).'


def test_needs_checking_list_is_one_short_row_per_job(root):
    c = FakeClient()
    no_salary = GOOD_DESC.replace("<p>The base salary range for this role is $95,000 - $115,000.</p>", "")
    setup_board(c, [gh_job(1, "Salesforce Administrator", desc=no_salary)])
    info = run(root, c)
    md = open(info["report"]).read()
    heading = "## Jobs that need checking" if "## Jobs that need checking" in md else "## Needs Verification"
    sec = md[md.index(heading):]
    sec = sec[:sec.find("\n## ", 3)]
    rows = [l for l in sec.splitlines() if l.startswith("| Salesforce Administrator")]
    assert len(rows) == 1 and "no salary listed" in rows[0] and "| [Open](" in rows[0]
    assert "From the posting" not in sec and "Fit with your experience" not in sec


def test_matching_jobs_are_one_short_row_per_job(root):
    c = FakeClient()
    setup_board(c, [gh_job(1, "Salesforce Administrator")])
    info = run(root, c)
    md = open(info["report"]).read()
    heading = "## Jobs that match all your rules" if "## Jobs that match all your rules" in md else "## Qualified matches"
    sec = md[md.index(heading):]
    sec = sec[:sec.find("\n## ", 3)]
    rows = [l for l in sec.splitlines() if l.startswith("| Salesforce Administrator")]
    assert len(rows) == 1 and "$95,000-$115,000" in rows[0] and "| [Open](" in rows[0]
    assert "From the posting" not in sec and "Result:" not in sec


def test_did_not_match_list_is_a_table(root):
    c = FakeClient()
    bad = GOOD_DESC.replace("$95,000 - $115,000", "$60,000 - $70,000")
    setup_board(c, [gh_job(1, "Salesforce Administrator", desc=bad)])
    info = run(root, c)
    md = open(info["report"]).read()
    sec = md[md.index("## Jobs that did not match"):]
    sec = sec[:sec.find("\n## ", 3)]
    assert "| Job | Company | Why it did not match | Link | First found |" in sec
    assert any(l.startswith("| Salesforce Administrator |") and "$60,000" in l for l in sec.splitlines())


def test_skills_matcher_rules():
    from jobsearch.skills_match import SkillsMatcher, SKILLS_FAMILY
    skills = [{"name": "NPSP", "keywords": ["npsp"]}, {"name": "Reports", "keywords": ["dashboard", "report"]},
              {"name": "Data quality", "keywords": ["data quality", "dedup"]}, {"name": "Training", "keywords": ["train"]}]
    text = "We run Salesforce with NPSP. Build dashboards, keep data quality high, train staff."
    m = SkillsMatcher({"on": "yes", "required_keywords": ["Salesforce", "NPSP"], "minimum_skills_matched": 3}, skills)
    hit = m.match("Development Operations Coordinator", text)
    assert hit and hit["family"] == SKILLS_FAMILY and len(hit["skills"]) >= 3
    assert m.match("Development Operations Coordinator", text.replace("NPSP", "")) is None      # "all": both keywords needed
    any_rule = SkillsMatcher({"on": "yes", "required_keywords": ["Salesforce", "NPSP"], "required_keywords_rule": "any",
                              "minimum_skills_matched": 2}, skills)
    assert any_rule.match("Coordinator", "Salesforce reports and dashboards; we train users") is not None
    assert SkillsMatcher({"on": "no", "required_keywords": ["Salesforce"]}, skills).match("X", text) is None   # off
    assert m.match("Coordinator", "Salesforce NPSP only") is None                                     # too few skills


def test_skills_match_is_kept_marked_and_listed_separately(root):
    import tomllib
    skills_text = "<p>We use Salesforce with NPSP. Build reports and dashboards, keep data quality high, run imports, and train staff.</p>"
    desc = GOOD_DESC.replace("<p>About the role</p>", "<p>About the role</p>" + skills_text)
    c = FakeClient()
    setup_board(c, [gh_job(1, "Development Operations Coordinator", desc=desc),
                    gh_job(2, "Account Executive", desc=desc)])
    _enable_skills_matching(root)
    info = run(root, c)
    js = {j["title"]: j for j in jobs(root)}
    assert "Account Executive" not in js or js["Account Executive"]["status"] != "Qualified"
    j = js["Development Operations Coordinator"]
    assert j["family"] == "Skills match (other titles)", j["family"]
    md = open(info["report"]).read()
    assert "Development Operations Coordinator" in md and "(skills match)" in md


def _enable_skills_matching(root):
    s = root / "config/settings.toml"
    s.write_text(s.read_text() + '\n[skills_matching]\non = "yes"\nrequired_keywords = ["Salesforce", "NPSP"]\n'
                 'required_keywords_rule = "all"\nminimum_skills_matched = 3\n'
                 '\n[filters]\nexclude_titles_containing = ["Account Executive"]\n')   # titles to skip still apply
    e = root / "config/experience_profile.toml"
    e.write_text(e.read_text() + "\n"
                 '[[skills]]\nname = "NPSP"\nkind = "demonstrated"\nkeywords = ["npsp"]\nevidence = "x"\n\n'
                 '[[skills]]\nname = "Reports"\nkind = "demonstrated"\nkeywords = ["report", "dashboard"]\nevidence = "x"\n\n'
                 '[[skills]]\nname = "Data quality"\nkind = "demonstrated"\nkeywords = ["data quality"]\nevidence = "x"\n\n'
                 '[[skills]]\nname = "Training"\nkind = "demonstrated"\nkeywords = ["train"]\nevidence = "x"\n')


def test_skills_matching_off_by_default_in_template():
    import tomllib, pathlib
    s = tomllib.load(open(pathlib.Path(__file__).parents[1] / "EDIT_ME_JOB_SEARCH_SETTINGS/EDIT_ME_1_job_search_settings.toml", "rb"))
    assert s["skills_matching"]["on"] == "no" and s["skills_matching"]["required_keywords"] == []
