"""'Where this search looked': every job site and source used in a run, and the exact web search
(Tavily) criteria. Built from the run record saved in data/jobs.sqlite."""
from __future__ import annotations

SITES = [  # (source name in the run record, name shown, what it searches)
    ("websearch", "Web search (Tavily)", "the whole web for each job title (criteria below)"),
    ("ats_watchlist", "Company careers pages", "every open job at the companies listed below "
                                               "(Greenhouse, Lever, Ashby, SmartRecruiters)"),
    ("remotive", "Remotive", "remote jobs, searched by your job titles"),
    ("remoteok", "Remote OK", "its newest remote jobs (about 100: all its feed gives)"),
    ("himalayas", "Himalayas", "remote jobs: up to 200 per search word, plus its newest 1,000"),
    ("themuse", "The Muse", "its newest 1,000 remote jobs, all fields"),
    ("jobicy", "Jobicy", "all of its US remote jobs"),
    ("weworkremotely", "We Work Remotely", "its newest 100 remote jobs, all categories (all its feed gives)"),
    ("hackernews", "Hacker News: Who is hiring?", "this month's hiring thread (mostly tech jobs)"),
]


REMOVED = {"adzuna", "usajobs", "jooble", "reliefweb", "web_search_leads", "workingnomads", "jobspresso"}   # sources this tool no longer uses


def _worked(s: dict) -> str:
    st = s.get("state")
    return {"ok": "Yes", "needs_credentials": "Off: no key", "blocked": "No: the site blocked the request",
            "not_run": "Not run"}.get(st, "No: error")


def _skills(s: dict) -> str:
    """Skills-based matches; searches before 2026-11-05 did not record them."""
    return str(s["skills_matched"]) if "skills_matched" in s else "not recorded"


def _cell(x) -> str:
    return str(x if x is not None else "").replace("|", "/").replace("\n", " ")


def section(sources: list[dict]) -> list[str]:
    by = {s.get("name"): s for s in sources or []}
    companies = (by.get("ats_watchlist") or {}).get("companies")
    L = ["## Where this search looked", "",
         "Every job site and source used in the last search, and how many listings each gave.", "",
         "| Job site | What it searches | Searched this time? | Listings looked at | Matched your job titles | Matched your skills |",
         "|---|---|---|---|---|---|"]
    known = [n for n, _, _ in SITES]
    for name, shown, what in SITES:
        s = by.get(name)
        if s is None:
            continue
        L.append(f"| {shown} | {what} | {_worked(s)} | {s.get('fetched', 0)} | {s.get('matched', 0)} | {_skills(s)} |")
    for name, s in by.items():   # any source not described above (removed sources are not shown)
        if name not in known and name not in REMOVED:
            L.append(f"| {_cell(name)} |  | {_worked(s)} | {s.get('fetched', 0)} | {s.get('matched', 0)} | {_skills(s)} |")
    if companies is not None:
        L += ["", f"**Company careers pages read ({len(companies)}):** "
              + (", ".join(_cell(c) for c in sorted(companies, key=str.lower)) if companies else "none yet") + "."]
    elif "ats_watchlist" in by:
        L += ["", "**Company careers pages read:** not recorded for this search (searches from 2026-11-05 on list them)."]
    L += ["", "### Web search (Tavily) criteria", ""]
    ws = by.get("websearch")
    if not ws:
        L.append("The web search is not part of this search.")
    elif ws.get("state") == "needs_credentials":
        L.append("Off this time: no Tavily key is set, so no web search was run.")
    else:
        from .adapters.websearch import CAREERS_DOMAINS, EXCLUDE_DOMAINS
        rows = ws.get("searches") or []
        if rows:
            L += ["| # | Search words | Where | Period | Up to | Results | Kept as jobs to check |",
                  "|---|---|---|---|---|---|---|"]
            for i, r in enumerate(rows, 1):
                L.append(f"| {i} | {_cell(r.get('words'))} | {_cell(r.get('where'))} | {_cell(r.get('period'))} | "
                         f"{r.get('max_results', '')} | {_cell(r.get('results', ''))} | {r.get('kept', '')} |")
        else:
            L.append(_cell(ws.get("detail")) or "No searches were recorded.")
        L += ["", "Company careers pages searched: " + ", ".join(CAREERS_DOMAINS) + ".", "",
              "Left out of the wider-web search (sites this tool does not open, sites it already reads "
              "directly, and sites that repost other sites' jobs): " + ", ".join(EXCLUDE_DOMAINS) + "."]
    return L + [""]


SOURCE_LABELS = {"greenhouse": "Company careers page (Greenhouse)", "lever": "Company careers page (Lever)",
                 "ashby": "Company careers page (Ashby)", "smartrecruiters": "Company careers page (SmartRecruiters)"}
HOST_LABELS = {"himalayas.app": "Himalayas", "remoteok.com": "Remote OK", "remotive.com": "Remotive",
               "themuse.com": "The Muse", "jobicy.com": "Jobicy", "weworkremotely.com": "We Work Remotely",
               "news.ycombinator.com": "Hacker News: Who is hiring?"}


def found_by(row) -> str:
    """The job site(s) or search that found a job, from its saved sources and listing links."""
    import json
    from urllib.parse import urlsplit
    site_names = {name: shown for name, shown, _ in SITES}

    def load(key):
        try:
            return json.loads(row[key] or "[]")
        except (KeyError, IndexError, TypeError, ValueError):
            return []

    names = []
    for s in load("sources"):
        label = SOURCE_LABELS.get(s) or site_names.get(s)
        if label and label not in names:
            names.append(label)
    for url in load("source_urls"):
        host = urlsplit(url or "").netloc.lower().removeprefix("www.")
        label = HOST_LABELS.get(host)
        if label and label not in names:
            names.append(label)
    if not names and "employer_page" in load("sources"):
        names.append("Employer's website (reached from another listing)")
    return ", ".join(names) or "not recorded"
