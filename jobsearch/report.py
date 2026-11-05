"""Readable Markdown + HTML report: Qualified, Needs Verification, held hourly/contract,
Rejected examples, source coverage and limitations."""
from __future__ import annotations

import html
import json
from pathlib import Path

from .notify import _j

SOURCE_NOTES = {
    "LinkedIn, Indeed, Handshake, Idealist and 28 more": "Not searched automatically (no public data feed, sign-in "
    "required, blocked, or terms do not allow it). One-click searches for them are on the JOB_SEARCH_RESULTS page.",
}

def _rule(row, name):
    for r in _j(row, "rules", []) or []:
        if r["rule"] == name:
            return r
    return {}


def _ev(r, n=2):
    return " | ".join(f"\"{e['excerpt']}\"" + (f" ({e['url']})" if e.get("url") else "") for e in (r.get("evidence") or [])[:n])


OUTCOME = {"pass": "OK", "fail": "does not match", "unclear": "not clear"}


def _job_md(row, detail=True) -> str:
    ver = _j(row, "verification", {}) or {}
    fit = _j(row, "fit", {}) or {}
    reasons = _j(row, "reasons", []) or []
    out = []
    out.append(f"### {row['title']} — {row['employer']}")
    out.append(f"Job title group: {row['family']}" + (f" (track {row['track']})" if row["track"] else "") + "  ")
    status_txt = {"Qualified": "Matches all your rules", "Needs Verification": "Needs checking",
                  "Rejected": "Did not match", "Closed": "No longer open"}.get(row["status"], row["status"])
    out.append(f"Result: **{status_txt}**. " + "; ".join(reasons))
    route = ver.get("apply_route")
    route_txt = {"third_party": "on a third-party job site, not the employer's own site",
                 "employer_ats": "on the employer's own hiring system",
                 "employer_site": "on the employer's own website"}.get(route, "")
    link = ver.get("apply_url") or row["canonical_url"]
    from .verify import FEED_LISTED
    if ver.get("status") == "verified" and (ver.get("detail") or "").startswith(FEED_LISTED):
        out.append(f"Apply: {link} (on a third-party job site; link not checked: {ver['detail']})")
    elif ver.get("status") == "verified":
        out.append(f"Apply: {link} ({route_txt or 'link works'}; checked {(ver.get('checked_at') or '')[:16].replace('T', ' ')} UTC)")
    else:
        from .verify import plain_link_reason
        from .models import Verification
        v = Verification(**{k: x for k, x in ver.items() if k in Verification.__dataclass_fields__}) if ver else None
        out.append(f"Link: {link or 'none found'}. {plain_link_reason(v)}")
    srcs = _j(row, "source_urls", []) or []
    out.append(f"Found on: {', '.join(srcs[:4])}")
    posted = (row["published_date"] or "")[:10] or "date not given"
    out.append(f"Posted: {posted}; first found by this tool: {(row['first_seen'] or '')[:10]}; last seen: {(row['last_seen'] or '')[:10]}")
    if detail:
        for name in ("salary", "location", "certifications"):
            r = _rule(row, name)
            if r:
                out.append(f"{name.title()}: {OUTCOME.get(r['outcome'], r['outcome'])} ({r['reason']})" + (f"  \n  From the posting: {_ev(r)}" if r.get("evidence") else ""))
        for r in (_j(row, "rules", []) or []):
            if str(r.get("rule", "")).startswith("rule: "):  # user-defined requirement rules
                out.append(f"Your rule \"{r['rule'][6:]}\": {OUTCOME.get(r['outcome'], r['outcome'])} ({r['reason']})" + (f"  \n  From the posting: {_ev(r)}" if r.get("evidence") else ""))
        loc = _rule(row, "location").get("data", {})
        if loc.get("travel"):
            out.append(f"Travel: {'; '.join(loc['travel'])}")
        if fit:
            if fit.get("strong"):
                out.append("Fit with your experience: " + "; ".join(f"{s['skill']} (job: \"{s['job_excerpt']}\")" for s in fit["strong"][:5]))
            if fit.get("transferable"):
                out.append("Related experience: " + "; ".join(s["skill"] for s in fit["transferable"]))
            if fit.get("gaps"):
                out.append("Not in your experience file: " + "; ".join(g["skill"] + (" (required)" if g.get("required") else "") for g in fit["gaps"]))
            if fit.get("mandatory_unsupported"):
                out.append("Required items not in your experience file: " + " | ".join(fit["mandatory_unsupported"]))
        if row["repost_note"]:
            out.append(f"Posted again: {row['repost_note']}")
    return "  \n".join(out)



LINK_NOTE = {"blocked": "site blocks automated checks", "unverified": "not checked", "js_required": "page needs a browser",
             "error": "could not be opened", "generic": "goes to a general careers page",
             "mismatch": "goes to a different job", "closed": "looks closed"}
SHORTER = [("No employer-advertised salary found", "no salary listed"),
           (" (per third-party listing; employer posting not confirmed)", " (job site's copy)"),
           ("Remote, but country/state eligibility not stated", "remote, but which states can apply is not stated"),
           ("Remote, but New Mexico / state eligibility not explicitly stated", "remote, but which states can apply is not stated"),
           ("Salary seen only on a third-party source; not confirmed on employer posting", "salary only on a job site's copy"),
           ("posting content not confirmed on employer/ATS source", "Posting only seen on a job site"),
           ("Required vs preferred unclear for", "unclear whether required:")]
OLD_PREFIX = {"salary: ": "Salary: ", "location: ": "Location: ", "cloud: ": "Salesforce Cloud: ",
              "certifications: ": "Certifications: "}   # wording saved by searches before 2026-11-04
LINK_WORDS = ("application route:", "application link", "link not checked", "closed:", "no longer open:")


def _short(text: str, n: int = 100) -> str:
    import re
    for a, b in SHORTER:
        text = text.replace(a, b)
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= n else text[: n - 1].rstrip(" ,;(") + "…"


def _check_table(rows) -> list[str]:
    """Jobs that need checking: one short row each, easy to skim."""
    from .models import Verification
    from .verify import FEED_LISTED, plain_link_reason
    if not rows:
        return ["None.", ""]
    L = ["| Job | Company | What to check | Link | First found |", "|---|---|---|---|---|"]
    for r in rows:
        ver = _j(r, "verification", {}) or {}
        v = Verification(**{k: x for k, x in ver.items() if k in Verification.__dataclass_fields__}) if ver else None
        link_reason = plain_link_reason(v) if ver.get("status") != "verified" else None
        reasons = []
        for x in (_j(r, "reasons", []) or []):
            if x == link_reason or x.lower().startswith(LINK_WORDS):
                continue   # the Link column already says this
            for a, b in OLD_PREFIX.items():
                if x.startswith(a):
                    x = b + x[len(a):]
            reasons.append(_short(x))
        if link_reason:
            reasons.append("Check the job is still open")
        link = ver.get("apply_url") or r["canonical_url"] or ((_j(r, "source_urls", []) or [""])[0])
        if ver.get("status") == "verified":
            note = ("Himalayas listing, not opened" if (ver.get("detail") or "").startswith(FEED_LISTED)
                    else "job site" if ver.get("apply_route") == "third_party" else "employer's site")
        else:
            note = LINK_NOTE.get(ver.get("status"), "not checked")
        cell = lambda x: str(x or "").replace("|", "/").replace("\n", " ")
        L.append(f"| {cell(r['title'])} | {cell(r['employer'])} | {cell('; '.join(reasons))} | "
                 f"[Open]({link}) ({note}) | {(r['first_seen'] or '')[:10]} |")
    return L + [""]


def build(store, run_info: dict, out_dir: Path, title: str = "Job Search Report") -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = store.jobs("closed_at IS NULL")
    q = [r for r in rows if r["status"] == "Qualified"]
    held = [r for r in rows if r["status"] == "Needs Verification" and r["compensation_type"] in ("hourly", "contract")]
    nv = [r for r in rows if r["status"] == "Needs Verification" and r not in held]
    rej = [r for r in rows if r["status"] == "Rejected"]
    closed = store.jobs("closed_at IS NOT NULL")
    md = [f"# {title}", "",
          f"Search started: {(run_info.get('started_at') or '')[:16].replace('T', ' ')} UTC", ""]
    if run_info.get("fixtures"):
        md += ["**TEST DATA** (not live listings).", ""]
    md += [f"Totals: match all your rules {len(q)} | need checking {len(nv)} | hourly or contract {len(held)} | "
           f"did not match {len(rej)} | no longer open {len(closed)}",
           "", "## Jobs that match all your rules", ""]
    md += [_job_md(r) + "\n" for r in q] or ["None.", ""]
    md += ["## Jobs that need checking", ""]
    md += _check_table(nv)
    md += ["## Hourly or contract jobs", "",
           "Pay is listed per hour or per contract, so the yearly salary rule was not applied. Check the pay yourself.", ""]
    md += [_job_md(r, detail=False) + "\n" for r in held] or ["None.", ""]
    md += ["## Jobs that did not match, and why (up to 40)", ""]
    for i, r in enumerate(rej[:40], 1):
        reasons = "; ".join(_j(r, "reasons", []) or [])
        md.append(f"{i}. {r['title']}, {r['employer']}: {reasons} ({r['canonical_url'] or (_j(r,'source_urls',[]) or [''])[0]})")
    if not rej:
        md.append("None.")
    from .sources_summary import section as where_section
    md += [""] + where_section(run_info.get("sources", []))
    for k, v in SOURCE_NOTES.items():
        md.append(f"**{k}:** {v}")
    dropped = run_info.get("dropped_boards") or []
    if dropped:
        md += ["", "Companies no longer checked (no job matching your titles in more than 5 searches in a row): "
               + ", ".join(sorted(b.get("employer") or b["board"] for b in dropped)) + "."]
    md += ["", "Good to know:",
           "1. Only the job sites marked Yes above were searched. No tool finds every job.",
           "2. \"First found\" is when this tool first saw a job, not when the employer posted it.",
           "3. Rules are checked by reading the posting's text. When the wording is unclear, the job is put under "
           "\"need checking\" instead of guessed.",
           "4. The fit notes compare the posting with your experience file. A skill not listed there shows as \"not documented\"."]
    errs = run_info.get("errors") or []
    if errs:
        from .plain_errors import plain_error
        md += ["", "## Problems during this search", "",
               "These did not stop the search. Where a page is listed, you can open it yourself.", ""] + [f"{i}. {plain_error(e)}" for i, e in enumerate(errs[:30], 1)]
    text = "\n".join(md) + "\n"
    p = out_dir / "full_report.md"   # included in JOB_SEARCH_RESULTS/REPORT_*.md by results_folder.py
    p.write_text(text)
    return p


def _html(md: str, title: str) -> str:
    body = []
    for line in md.split("\n"):
        e = html.escape(line)
        if line.startswith("### "):
            body.append(f"<h3>{e[4:]}</h3>")
        elif line.startswith("## "):
            body.append(f"<h2>{e[3:]}</h2>")
        elif line.startswith("# "):
            body.append(f"<h1>{e[2:]}</h1>")
        elif line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if set("".join(cells)) <= set("-"):
                continue
            body.append("<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in cells) + "</tr>")
        elif line.strip():
            body.append(f"<p>{e}</p>")
    joined = "\n".join(body).replace("</p>\n<tr>", "</p>\n<table><tr>")
    joined = joined.replace("</tr>\n<p>", "</tr></table>\n<p>").replace("</tr>\n<h", "</tr></table>\n<h")
    css = ("body{font-family:system-ui,sans-serif;max-width:1000px;margin:24px auto;padding:0 16px;line-height:1.45;background:#fff;color:#111}"
           "h3{margin-top:22px}table{border-collapse:collapse;font-size:13px}td{border:1px solid #ccc;padding:4px 6px;vertical-align:top}"
           "@media (prefers-color-scheme: dark){body{background:#111;color:#eee}td{border-color:#444}}")
    return f"<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{html.escape(title)}</title><style>{css}</style></head><body>{joined}</body></html>"
