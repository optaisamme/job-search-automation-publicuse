"""Write RESULTS.md: one page showing what the job search currently has for you.

Rewritten after every run, whether or not anything new was found:
  * jobs that currently pass all rules (with application links),
  * near misses (failed exactly one rule) that are still listed,
  * what was new in the last run,
  * where everything else is.
Also appended to the GitHub Actions run page when run inside GitHub Actions.
"""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
import sys  # noqa: E402
sys.path.insert(0, str(ROOT))


def _j(v, default):
    try:
        return json.loads(v) if v else default
    except (TypeError, ValueError):
        return default


def _rule(rules, name):
    for r in rules or []:
        if r.get("rule") == name:
            return r.get("reason", "")
    return ""


def build() -> str:
    dbp = ROOT / "data/jobs.sqlite"
    if not dbp.exists():
        return "# Job search results\n\nNo search has run yet.\n"
    db = sqlite3.connect(dbp)
    db.row_factory = sqlite3.Row
    last = db.execute("SELECT * FROM runs WHERE finished_at IS NOT NULL ORDER BY id DESC LIMIT 1").fetchone()
    qualified = db.execute("SELECT * FROM jobs WHERE status='Qualified' AND closed_at IS NULL ORDER BY first_seen DESC").fetchall()
    near = db.execute(
        "SELECT j.*, n.payload AS npayload FROM notifications n JOIN jobs j ON j.id=n.job_id "
        "WHERE n.kind='near_miss' AND j.closed_at IS NULL AND j.status!='Qualified' ORDER BY n.id DESC").fetchall()
    out_path = ROOT / "out/outbox.json"
    outbox = _j(out_path.read_text(), {}) if out_path.exists() else {}
    issue_url = (ROOT / "out/issue_url.txt").read_text().strip() if (ROOT / "out/issue_url.txt").exists() else ""

    L = ["# Job search results", ""]
    if last:
        c = _j(last["counts"], {})
        L += [f"**Last search:** {last['finished_at']} UTC. Checked {c.get('discovered', 0)} listings; "
              f"{c.get('title_matched', 0)} matched your job titles.", ""]
    L += ["## New in the last search", ""]
    draft = outbox.get("draft")
    if draft:
        L.append(f"**{draft['subject']}**" + (f" (posted: {issue_url})" if issue_url else ""))
        L += ["", "```text", draft["body"], "```", ""]
    else:
        L += ["Nothing new in the last search. The jobs below were already reported earlier.", ""]

    L += [f"## Jobs that currently match all your rules ({len(qualified)})", ""]
    if qualified:
        L += ["| Job | Company | Salary | Location | Apply | First seen |", "|---|---|---|---|---|---|"]
        for r in qualified:
            ver = _j(r["verification"], {}) or {}
            link = ver.get("apply_url") or r["apply_url"] or r["canonical_url"] or ""
            route = " (third-party)" if ver.get("apply_route") == "third_party" else ""
            sal = _rule(_j(r["rules"], []), "salary").replace("|", "/")
            L.append(f"| {r['title']} | {r['employer']} | {sal} | {(r['location_text'] or '').replace('|', '/')} | "
                     f"[Apply]({link}){route} | {(r['first_seen'] or '')[:10]} |")
    else:
        L.append("None right now.")
    L += ["", f"## Near misses still listed: failed exactly one rule ({len(near)})", ""]
    if near:
        L += ["| Job | Company | Why it didn't match | Link |", "|---|---|---|---|"]
        for r in near:
            p = _j(r["npayload"], {})
            why = "; ".join(p.get("reasons", [])).replace("|", "/")
            link = p.get("link") or r["canonical_url"] or ""
            L.append(f"| {r['title']} | {r['employer']} | {why} | [Link]({link}) |")
    else:
        L.append("None right now.")
    from jobsearch.lookup import needs_employer_posting
    look = needs_employer_posting(db)
    L += ["", f"## Jobs whose link could not be checked automatically ({len(look)})", "",
          "These come from job sites that block automated checks, or only from a third-party site. "
          "The automation does not get around those blocks. Use **Find employer posting** to search for the "
          "same job on the employer's own website, then apply there.", ""]
    if look:
        L += ["| Job | Company | Listing found | Find the employer's posting |", "|---|---|---|---|"]
        for x in look:
            L.append(f"| {x['title']} | {x['employer']} | [Listing]({x['current_link']}) | "
                     f"[Find employer posting]({x['search_link']}) |")
    else:
        L.append("None right now.")
    L += ["", "## Everything else", "",
          "Every job checked in the last search, including those that did not match and why, is in "
          "[reports/latest.md](reports/latest.md).", ""]
    return "\n".join(L)


def main() -> int:
    text = build()
    (ROOT / "RESULTS.md").write_text(text)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as f:
            base = f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/{os.environ.get('GITHUB_REPOSITORY', '')}/blob/main/"
            f.write(text.replace("](reports/", "](" + base + "reports/")
                    + f"\n\nFull results page: {base}RESULTS.md\n")
    print("Wrote RESULTS.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
