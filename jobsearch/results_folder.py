"""The JOB_SEARCH_RESULTS folder: where people read their results.

  JOB_SEARCH_RESULTS/README.md                       shown automatically when the folder is opened:
                                                     current matches, near misses, and a list of all reports
  JOB_SEARCH_RESULTS/REPORT_001_2026-11-06_13-47_UTC.md   one report per search, numbered, with date and time

Rewritten after every search, whether or not anything new was found.
"""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

FOLDER = "JOB_SEARCH_RESULTS"


def _j(v, default):
    try:
        return json.loads(v) if v else default
    except (TypeError, ValueError):
        return default


def _reason(rules, name):
    for r in rules or []:
        if r.get("rule") == name:
            return r.get("reason", "")
    return ""


def _cell(s) -> str:
    return str(s or "").replace("|", "/").replace("\n", " ")


def report_name(run_id: int, finished_at: str) -> str:
    stamp = (finished_at or "")[:16].replace("T", "_").replace(":", "-")
    return f"REPORT_{run_id:03d}_{stamp}_UTC.md"


def _current_sections(db) -> list[str]:
    from .lookup import needs_employer_posting
    qualified = db.execute("SELECT * FROM jobs WHERE status='Qualified' AND closed_at IS NULL ORDER BY first_seen DESC").fetchall()
    near = db.execute(
        "SELECT j.*, n.payload AS npayload FROM notifications n JOIN jobs j ON j.id=n.job_id "
        "WHERE n.kind='near_miss' AND j.closed_at IS NULL AND j.status!='Qualified' ORDER BY n.id DESC").fetchall()
    look = needs_employer_posting(db)
    L = [f"## Jobs that match all your rules ({len(qualified)})", ""]
    if qualified:
        L += ["| Job | Company | Salary | Location | Apply | First found |", "|---|---|---|---|---|---|"]
        for r in qualified:
            ver = _j(r["verification"], {}) or {}
            link = ver.get("apply_url") or r["apply_url"] or r["canonical_url"] or ""
            route = " (third-party site)" if ver.get("apply_route") == "third_party" else ""
            L.append(f"| {_cell(r['title'])} | {_cell(r['employer'])} | {_cell(_reason(_j(r['rules'], []), 'salary'))} | "
                     f"{_cell(r['location_text'])} | [Apply]({link}){route} | {(r['first_seen'] or '')[:10]} |")
    else:
        L.append("None right now.")
    L += ["", f"## Near misses: failed exactly one of your rules ({len(near)})", ""]
    if near:
        L += ["| Job | Company | Why it did not match | Link |", "|---|---|---|---|"]
        for r in near:
            p = _j(r["npayload"], {})
            L.append(f"| {_cell(r['title'])} | {_cell(r['employer'])} | {_cell('; '.join(_j(r['reasons'], []) or p.get('reasons', [])))} | "
                     f"[Link]({p.get('link') or r['canonical_url'] or ''}) |")
    else:
        L.append("None right now.")
    L += ["", f"## Jobs whose link could not be checked automatically ({len(look)})", "",
          "These come from job sites that block automated checks, or only from a third-party site. "
          "Use **Find employer posting** to search for the same job on the employer's own website, then apply there.", ""]
    if look:
        L += ["| Job | Company | Listing found | Find the employer's posting |", "|---|---|---|---|"]
        for x in look:
            L.append(f"| {_cell(x['title'])} | {_cell(x['employer'])} | [Listing]({x['current_link']}) | "
                     f"[Find employer posting]({x['search_link']}) |")
    else:
        L.append("None right now.")
    return L


def write(root: Path) -> dict:
    """Write this search's numbered report and the folder's README. Returns paths and text."""
    root = Path(root)
    folder = root / FOLDER
    folder.mkdir(exist_ok=True)
    dbp = root / "data/jobs.sqlite"
    if not dbp.exists():
        text = f"# {FOLDER.replace('_', ' ')}\n\nNo search has run yet. Your results appear here after your first search.\n"
        (folder / "README.md").write_text(text)
        return {"index": str(folder / "README.md"), "report": None, "text": text}
    db = sqlite3.connect(dbp)
    db.row_factory = sqlite3.Row
    last = db.execute("SELECT * FROM runs WHERE finished_at IS NOT NULL ORDER BY id DESC LIMIT 1").fetchone()
    outbox_p = root / "out/outbox.json"
    outbox = _j(outbox_p.read_text(), {}) if outbox_p.exists() else {}
    issue_url = (root / "out/issue_url.txt").read_text().strip() if (root / "out/issue_url.txt").exists() else ""
    current = _current_sections(db)

    report_file = None
    if last:
        c = _j(last["counts"], {})
        name = report_name(last["id"], last["finished_at"])
        R = [f"# REPORT {last['id']}: search run {last['finished_at'][:16].replace('T', ' ')} UTC", "",
             f"Checked {c.get('discovered', 0)} job listings; {c.get('title_matched', 0)} matched your job titles.", "",
             "## New in this search", ""]
        draft = outbox.get("draft")
        if draft:
            R.append(f"**{draft['subject']}**" + (f" (also posted: {issue_url})" if issue_url else ""))
            R += ["", "```text", draft["body"], "```", ""]
        else:
            R += ["Nothing new in this search. The jobs below were already reported earlier.", ""]
        R += current
        full_p = root / "out/full_report.md"
        if full_p.exists():
            full = full_p.read_text()
            full = re.sub(r"^# .*\n", "", full, count=1)
            full = re.sub(r"(?m)^### ", "#### ", full)
            full = re.sub(r"(?m)^## ", "### ", full)
            R += ["", "## Every job checked in this search, and why it did or did not match", "", full]
        report_file = folder / name
        report_file.write_text("\n".join(R) + "\n")

    reports = sorted(folder.glob("REPORT_*.md"), reverse=True)
    I = ["# JOB SEARCH RESULTS", "",
         "**This page shows your latest results.** It is updated after every search.", ""]
    if last:
        I += [f"**Latest search:** {last['finished_at'][:16].replace('T', ' ')} UTC. "
              f"Full details: [{reports[0].name}]({reports[0].name})" if reports else "", ""]
    I += current
    I += ["", "## All reports (newest first)", "",
          "Each search adds one numbered report with its date and time (UTC).", ""]
    I += [f"{i}. [{p.name}]({p.name})" for i, p in enumerate(reports, 1)] or ["None yet."]
    index = "\n".join(I) + "\n"
    (folder / "README.md").write_text(index)
    return {"index": str(folder / "README.md"), "report": str(report_file) if report_file else None, "text": index}
