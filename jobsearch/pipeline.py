"""End-to-end run: discover -> title-match -> resolve employer posting -> hard filters ->
verify application route -> classify -> persist/dedupe -> newness -> outbox -> report."""
from __future__ import annotations

import json
import re
import logging
import shutil
import tempfile
import tomllib
from dataclasses import asdict
from pathlib import Path

from .adapters.aggregators import RemotiveAdapter, RemoteOKAdapter, HimalayasAdapter, AdzunaAdapter, UsaJobsAdapter
from .adapters.ats import AtsWatchlistAdapter, FETCHERS
from .adapters.base import SourceStatus
from .adapters.leads import LeadsAdapter
from .classify import evaluate_posting, decide
from .http import HttpClient
from .models import RawPosting, Verification, QUALIFIED, REJECTED, NEEDS_VERIFICATION
from .notify import build_payload
from .store import Store, norm_key, now_iso
from .text import content_hash
from .titles import TitleMatcher
from . import report as reportmod
from . import verify as verifymod

log = logging.getLogger("jobsearch.pipeline")

ADAPTERS = {  # order matters: leads first so newly discovered boards are scanned in the same run
    "web_search_leads": LeadsAdapter, "ats_watchlist": AtsWatchlistAdapter, "remotive": RemotiveAdapter,
    "remoteok": RemoteOKAdapter, "himalayas": HimalayasAdapter, "adzuna": AdzunaAdapter, "usajobs": UsaJobsAdapter,
}


SETTINGS_DIR = "EDIT_ME_JOB_SEARCH_SETTINGS"   # the folder people edit


def load_config(root: Path) -> tuple[dict, dict]:
    """Load search configuration. EDIT_ME_JOB_SEARCH_SETTINGS/EDIT_ME_1_job_search_settings.toml (plain language), when present,
    overrides the hard-filter criteria, job titles and search keywords in jobsearch/advanced_settings.toml."""
    from . import criteria
    cfg = root / SETTINGS_DIR if (root / SETTINGS_DIR).exists() else root / "config"   # "config" = older copies/tests
    adv = cfg / "search_profile.toml"           # optional local override (developers)
    if not adv.exists():
        adv = Path(__file__).with_name("advanced_settings.toml")  # built-in defaults; not edited by users
    with open(adv, "rb") as f:
        prof = tomllib.load(f)
    ep = cfg / "EDIT_ME_2_my_experience.toml"
    if not ep.exists():
        ep = cfg / "experience_profile.toml"
    exp = {}
    if ep.exists():
        with open(ep, "rb") as f:
            exp = tomllib.load(f)
    sp = cfg / "EDIT_ME_1_job_search_settings.toml"
    if not sp.exists():
        sp = cfg / "settings.toml"
    if sp.exists():
        with open(sp, "rb") as f:
            settings = tomllib.load(f)
        criteria.configure(criteria.from_settings(settings), base=criteria.NEUTRAL)
        groups = [g for g in ((settings.get("job_titles") or {}).get("group") or []) if any(t.strip() for t in g.get("titles", []))]
        # With a settings file, only what the user wrote is used: no built-in titles or filters.
        prof["titles"] = [{"track": (g.get("track") or "").strip(), "family": (g.get("name") or "").strip() or f"Group {i}",
                           "plain_titles": [t for t in g.get("titles", []) if t.strip()],
                           "require_any": g.get("description_must_mention_one_of", []), "include": []}
                          for i, g in enumerate(groups, 1)]
        flt = settings.get("filters") or {}
        prof["title_rules"] = {"must_mention": list(flt.get("description_must_mention", [])),
                               "exclude_plain": list(flt.get("exclude_titles_containing", []))}
        kw = list((settings.get("search") or {}).get("keywords") or [])
        if not kw:  # default: search for the titles themselves
            kw = [t for g in groups for t in g.get("titles", [])]
        prof.setdefault("search", {})["queries"] = kw
    else:
        criteria.configure(None)
    return prof, exp


def load_boards(root: Path) -> dict:
    p = root / "data/boards.json"
    return json.loads(p.read_text()) if p.exists() else {}


def save_boards(root: Path, boards: dict, added: list[dict]):
    changed = False
    for b in added:
        lst = boards.setdefault(b["ats"], [])
        if not any(x["board"] == b["board"] for x in lst):
            lst.append({"board": b["board"], "employer": b.get("employer"), "added": now_iso()})
            changed = True
    if changed:
        (root / "data").mkdir(exist_ok=True)
        (root / "data/boards.json").write_text(json.dumps(boards, indent=2, sort_keys=True))
    return changed


def _record(p: RawPosting, match: dict, ev: dict, ver: Verification | None, status: str, reasons: list[str]) -> dict:
    rules = [r.to_dict() for r in ev["rules"]]
    sal = next(r for r in ev["rules"] if r.rule == "salary")
    loc = next(r for r in ev["rules"] if r.rule == "location")
    cert = next(r for r in ev["rules"] if r.rule == "certifications")
    srcs = [p.source_url] + p.extra.get("third_party_sources", [])
    if p.extra.get("discovered_via"):
        srcs.append(p.extra["discovered_via"])
    return {
        "employer": p.employer, "title": p.title, "track": match["track"], "family": match["family"],
        "norm_key": norm_key(p.employer, p.title, p.location_text), "ats": p.ats, "ats_board": p.ats_board,
        "ats_job_id": p.ats_job_id, "requisition_id": p.requisition_id, "canonical_url": p.canonical_url,
        "apply_url": (ver.apply_url if ver and ver.status == "verified" else None) or p.apply_url,
        "apply_route": ver.apply_route if ver else None,
        "source_urls": [u for u in dict.fromkeys(srcs) if u], "sources": [p.source],
        "location_text": p.location_text, "last_verified": ver.checked_at if ver else None,
        "published_date": p.published_date, "status": status, "reasons": reasons, "rules": rules,
        "verification": ver.to_dict() if ver else None, "fit": ev["fit"], "cert_conditions": cert.data.get("post_hire", []),
        "salary": {"outcome": sal.outcome, "reason": sal.reason, **sal.data},
        "location": {"outcome": loc.outcome, "reason": loc.reason, **{k: v for k, v in loc.data.items() if k != "travel"}},
        "travel": loc.data.get("travel", []),
        "content_hash": content_hash(p.title, p.description_text),
        "authoritative": int(ev["authoritative"]),
        "compensation_type": sal.data.get("compensation_type"),
    }


def run(root: Path, db_path: Path, dry_run: bool = False, sources: list[str] | None = None,
        use_renderer: bool = True, client: HttpClient | None = None, fixtures: bool = False,
        report_dir: Path | None = None) -> dict:
    prof, exp = load_config(root)
    boards = load_boards(root)
    hc = prof["http"]
    client = client or HttpClient(hc["user_agent"], hc["min_interval_seconds"], hc["max_retries"], hc["timeout_seconds"], hc["respect_robots_for_html"])
    matcher = TitleMatcher(prof)

    work_db = db_path
    tmpdir = None
    if dry_run:
        tmpdir = tempfile.mkdtemp(prefix="jobsearch-dry-")
        work_db = Path(tmpdir) / "jobs.sqlite"
        if db_path.exists():
            shutil.copy(db_path, work_db)
    store = Store(work_db)
    run_id = store.start_run("dry_run" if dry_run else ("fixtures" if fixtures else "live"))
    was_baseline_done = store.baseline_done()

    ctx = {"queries": prof["search"]["queries"], "boards": boards, "title_matcher": matcher,
           "leads_path": str(root / "data/leads.json")}
    statuses: list[SourceStatus] = []
    raw: list[RawPosting] = []
    for name in (sources or list(ADAPTERS)):
        st = SourceStatus(name)
        ad = ADAPTERS[name](client, ctx)
        got = ad.run(st)
        st.fetched = len(got)
        statuses.append(st)
        raw.extend(got)

    # title match (pre-screen on discovery content)
    matched: list[tuple[RawPosting, dict]] = []
    for p in raw:
        m = matcher.match(p.title, p.description_text)
        if m:
            matched.append((p, m))
            for st in statuses:
                if st.name == p.source or (st.name == "ats_watchlist" and p.source in FETCHERS) or (st.name == "web_search_leads" and p.source in ("lead", "employer_page")):
                    st.matched += 1
                    break

    errors: list[str] = [f"{s.name}: {s.detail}" for s in statuses if s.state in ("error",)] + [e for s in statuses for e in s.errors]
    counts = {"discovered": len(raw), "title_matched": len(matched), "qualified": 0, "needs_verification": 0, "rejected": 0,
              "closed": 0, "new_jobs": 0, "notifications_queued": 0}
    seen_ids: set[int] = set()
    new_boards: list[dict] = list(ctx.get("boards_added", []))

    for p, m in matched:
        try:
            p = verifymod.resolve_employer_posting(client, p)
        except Exception as e:  # noqa: BLE001
            errors.append(f"resolve {p.source_url}: {e}")
        if p.extra.get("new_board"):
            new_boards.append(p.extra["new_board"])
        if (p.ats_board or "").lower() in {b.lower() for b in prof.get("sources", {}).get("intermediary_boards", [])}:
            p.authoritative = False
            p.extra["intermediary"] = True
        m2 = matcher.match(p.title, p.description_text) or m
        if p.extra.get("closed"):
            ev = evaluate_posting(p, exp)
            ver = Verification("closed", final_url=p.source_url, detail=p.extra.get("lead_note", "closed"), checked_at=now_iso())
            rec = _record(p, m2, ev, ver, "Closed", [f"closed: {ver.detail}"])
            jid, _ = store.upsert(rec, run_id)
            store.mark_closed(jid, f"closed: {ver.detail}")
            m_lookup = re.search(r"employer lookup for job (\d+)", str(p.extra.get("found_via") or ""))
            if m_lookup:
                old_id = int(m_lookup.group(1))
                old = store.job(old_id)
                if old is not None and (old_id == jid or old["closed_at"] is None):
                    store.mark_closed(old_id, "the employer's own posting is closed (found by employer lookup)")
            counts["closed"] += 1
            seen_ids.add(jid)
            continue
        thin = len(p.description_text.strip()) < 300
        ev = evaluate_posting(p, exp)
        if thin:
            # No usable posting text (e.g. job-board link not fetched): never reject on absent evidence.
            for r in ev["rules"]:
                if r.outcome == "fail":
                    r.outcome, r.reason = "unclear", "posting text unavailable; " + r.reason
        if not ev["authoritative"]:
            for r in ev["rules"]:
                if r.outcome == "fail":
                    r.reason += " (per third-party listing; employer posting not confirmed)"
        prelim = [r for r in ev["rules"] if r.outcome == "fail"]
        others_pass = all(r.outcome == "pass" for r in ev["rules"] if r not in prelim)
        ver = None
        # Verify when nothing failed, or when exactly one rule failed and the rest passed
        # (needed to tell whether the job is a one-criterion near miss).
        if not prelim or (len(prelim) == 1 and others_pass):
            try:
                ver = verifymod.verify(client, p, use_renderer=use_renderer)
            except Exception as e:  # noqa: BLE001
                ver = Verification("error", detail=str(e), checked_at=now_iso())
                errors.append(f"verify {p.canonical_url or p.source_url}: {e}")
            # If the verified page is the employer posting and the discovery copy was third-party,
            # re-run filters on the employer's own text.
            if ver.status == "verified" and not ev["authoritative"] and ver.apply_route != "third_party" and ver.page_text:
                ev = evaluate_posting(p, exp, text_override=ver.page_text, authoritative_override=True)
        if ver is not None and ver.status == "closed":
            status, reasons = "Closed", [f"closed: {ver.detail}"]
        else:
            status, reasons = decide(ev["rules"], ver, ev["authoritative"])
        rec = _record(p, m2, ev, ver, status, reasons)
        jid, change = store.upsert(rec, run_id)
        if store.job(jid)["closed_at"]:
            seen_ids.add(jid)
            continue  # replaced or closed by the employer's own posting
        m_lookup = re.search(r"employer lookup for job (\d+)", str(p.extra.get("found_via") or ""))
        if m_lookup and p.authoritative and int(m_lookup.group(1)) != jid:
            old_id = int(m_lookup.group(1))
            old = store.job(old_id)
            if old is not None and old["closed_at"] is None:
                store.mark_closed(old_id, f"replaced by the employer's own posting (job #{jid})")
                for n in store.db.execute("SELECT id FROM notifications WHERE job_id=? AND status IN ('pending','failed','held')", (old_id,)).fetchall():
                    store.mark_notification(n["id"], "cancelled", error=f"replaced by employer posting job #{jid}")
        if status == "Closed":
            store.mark_closed(jid, reasons[0])
            counts["closed"] += 1
            for n in store.db.execute("SELECT id FROM notifications WHERE job_id=? AND status IN ('pending','failed')", (jid,)).fetchall():
                store.mark_notification(n["id"], "cancelled", error="job closed before delivery")
        seen_ids.add(jid)
        if change == "new":
            counts["new_jobs"] += 1
        key = {QUALIFIED: "qualified", NEEDS_VERIFICATION: "needs_verification", REJECTED: "rejected"}.get(status)
        if key:
            counts[key] += 1

        # ---- near misses: exactly one criterion failed or unresolved, all others passed
        if status in (REJECTED, NEEDS_VERIFICATION):
            issues = [f"{r.rule}: {r.reason}" for r in ev["rules"] if r.outcome != "pass"]
            if ver is None or ver.status != "verified":
                issues.append(verifymod.plain_link_reason(ver))
            if len(issues) == 1:
                row = store.job(jid)
                link = (ver.final_url if ver and ver.final_url else None) or row["canonical_url"] or row["apply_url"] \
                    or (json.loads(row["sources"] and row["source_urls"] or "[]") or [None])[0]
                payload = {"job_id": jid, "title": row["title"], "employer": row["employer"], "link": link,
                           "status": status, "reasons": issues}
                if store.queue_notification(jid, "near_miss", payload, run_id):
                    counts["near_misses_queued"] = counts.get("near_misses_queued", 0) + 1

        # ---- newness / notifications
        if status == QUALIFIED:
            # an unsent near-miss notice is superseded by the qualified alert
            store.db.execute("UPDATE notifications SET status='cancelled', last_error='superseded: job now qualifies' "
                             "WHERE job_id=? AND kind='near_miss' AND status IN ('pending','failed')", (jid,))
            row = store.job(jid)
            if row["first_qualified"] is None:
                store.db.execute("UPDATE jobs SET first_qualified=? WHERE id=?", (now_iso(), jid))
            payload = build_payload(store.job(jid))
            prior = store.db.execute("SELECT id, status FROM notifications WHERE job_id=? AND kind != 'near_miss'", (jid,)).fetchall()
            if prior:
                # never notify twice; a held (failed pre-send check) alert is re-queued once it verifies again
                for n in prior:
                    if n["status"] == "held":
                        store.db.execute("UPDATE notifications SET status='pending', payload=? WHERE id=?", (json.dumps(payload), n["id"]))
                        counts["notifications_queued"] += 1
                continue
            if not was_baseline_done:  # first successful run = silent baseline
                store.queue_notification(jid, "baseline", payload, run_id, status="suppressed_baseline")
                store.db.execute("UPDATE jobs SET baseline=1 WHERE id=?", (jid,))
            elif store.repost_chain_notified(jid):
                store.queue_notification(jid, "repost", payload, run_id, status="suppressed_baseline")
            else:
                kind = "new" if change == "new" else "newly_verified"
                if store.queue_notification(jid, kind, payload, run_id):
                    counts["notifications_queued"] += 1

    # previously-active ATS jobs not seen this run: re-check via official API
    for row in store.jobs("closed_at IS NULL AND ats IS NOT NULL AND status IN ('Qualified','Needs Verification')"):
        if row["id"] in seen_ids or row["ats"] not in FETCHERS:
            continue
        try:
            live = FETCHERS[row["ats"]](client, row["ats_board"], row["ats_job_id"], row["employer"])
            if live is None:
                store.mark_closed(row["id"], "no longer returned by official ATS API")
                counts["closed"] += 1
                for n in store.db.execute("SELECT id FROM notifications WHERE job_id=? AND status IN ('pending','failed')", (row["id"],)):
                    store.mark_notification(n["id"], "cancelled", error="job closed before delivery")
        except Exception as e:  # noqa: BLE001
            errors.append(f"recheck job {row['id']}: {e}")

    # A run counts as successful (and can become the baseline) only if at least one
    # source actually returned listings; all-blocked or empty runs never set the baseline.
    success = any(s.state == "ok" and s.fetched > 0 for s in statuses)
    is_baseline = success and not was_baseline_done
    store.commit()
    src_dicts = [asdict(s) for s in statuses]
    store.finish_run(run_id, success, is_baseline, counts, src_dicts, errors[:100])
    if not dry_run:
        save_boards(root, boards, new_boards)
    run_info = {"run_id": run_id, "started_at": now_iso(), "mode": "dry_run" if dry_run else ("fixtures" if fixtures else "live"),
                "is_baseline": is_baseline, "sources": src_dicts, "errors": errors, "counts": counts, "fixtures": fixtures,
                "new_boards": new_boards}
    rdir = report_dir or (root / ("out/practice-run" if dry_run else "out"))
    rp = reportmod.build(store, run_info, rdir, "Initial Job Search Report (baseline)" if is_baseline else "Job Search Report")
    run_info["report"] = str(rp)
    store.db.close()
    if tmpdir:
        shutil.rmtree(tmpdir, ignore_errors=True)
    return run_info


def prepare_outbox(root: Path, db_path: Path, client: HttpClient | None = None, use_renderer: bool = True) -> dict:
    """Re-verify every pending notification's application link immediately before sending.
    Jobs failing re-verification are held (not sent) and moved to Needs Verification."""
    prof, _ = load_config(root)
    hc = prof["http"]
    client = client or HttpClient(hc["user_agent"], hc["min_interval_seconds"], hc["max_retries"], hc["timeout_seconds"], hc["respect_robots_for_html"])
    store = Store(db_path)
    items, ids, held = [], [], []
    near, near_ids = [], []
    # First run: jobs that already matched were recorded silently (baseline). Post them once,
    # together, as "initial results" so the user can see them; never again afterwards.
    first_run = store.db.execute("SELECT * FROM notifications WHERE kind='baseline' AND status='suppressed_baseline' "
                                 "AND channel IS NULL ORDER BY id").fetchall()
    for n in list(store.pending_notifications()) + list(first_run):
        row = store.job(n["job_id"])
        if n["kind"] == "near_miss":
            # Near misses are informational: no pre-send verification; skip if the job has since closed.
            if row["closed_at"]:
                store.mark_notification(n["id"], "cancelled", error="job closed before sharing")
                continue
            near.append(json.loads(n["payload"]))
            near_ids.append(n["id"])
            continue
        p = RawPosting(source=(json.loads(row["sources"] or "[]") or ["db"])[0], source_url=row["canonical_url"] or "",
                       employer=row["employer"], title=row["title"], description_text="", ats=row["ats"],
                       ats_board=row["ats_board"], ats_job_id=row["ats_job_id"], canonical_url=row["canonical_url"],
                       apply_url=row["apply_url"], authoritative=bool(row["authoritative"]))
        ver = verifymod.verify(client, p, use_renderer=use_renderer)
        if ver.status != "verified":
            reason = "Checked again just before posting: " + verifymod.plain_link_reason(ver)
            store.mark_notification(n["id"], "held", error=reason)
            new_status = "Closed" if ver.status == "closed" else NEEDS_VERIFICATION
            store.db.execute("UPDATE jobs SET status=?, reasons=?, verification=?, last_verified=? WHERE id=?",
                             (new_status, json.dumps([reason]), json.dumps(ver.to_dict()), ver.checked_at, row["id"]))
            if ver.status == "closed":
                store.db.execute("UPDATE jobs SET closed_at=? WHERE id=?", (now_iso(), row["id"]))
            held.append({"notification_id": n["id"], "job_id": row["id"], "reason": reason})
            continue
        store.db.execute("UPDATE jobs SET last_verified=?, verification=?, apply_url=? WHERE id=?",
                         (ver.checked_at, json.dumps(ver.to_dict()), ver.apply_url, row["id"]))
        payload = build_payload(store.job(row["id"]))
        items.append((n["kind"], payload))
        ids.append(n["id"])
    store.commit()
    from .notify import render_digest
    out = {"notification_ids": ids + near_ids, "held": held,
           "draft": render_digest(items, near) if (items or near) else None}
    store.db.close()
    return out
