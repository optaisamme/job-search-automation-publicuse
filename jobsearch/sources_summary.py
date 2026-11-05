"""'Where this search looked': every job site and source used in a run, and the exact web search
(Tavily) criteria. Built from the run record saved in data/jobs.sqlite."""
from __future__ import annotations

SITES = [  # (source name in the run record, name shown, what it searches)
    ("websearch", "Web search (Tavily)", "the whole web for each job title (criteria below)"),
    ("web_search_leads", "Web search leads (Claude)", "job links found by the Friday Claude web search"),
    ("ats_watchlist", "Company careers pages", "every open job at the companies listed below "
                                               "(Greenhouse, Lever, Ashby, SmartRecruiters)"),
    ("remotive", "Remotive", "remote jobs, searched by your job titles"),
    ("remoteok", "Remote OK", "its newest remote jobs (about 100)"),
    ("himalayas", "Himalayas", "remote jobs: up to 100 per job title, plus about 200 of its newest jobs"),
    ("themuse", "The Muse", "its newest 400 remote jobs, all fields"),
    ("jobicy", "Jobicy", "its newest 100 US remote jobs"),
    ("weworkremotely", "We Work Remotely", "its newest 100 remote jobs, all categories"),
    ("workingnomads", "Working Nomads", "its newest remote jobs"),
    ("jobspresso", "Jobspresso", "its newest hand-checked remote jobs"),
    ("hackernews", "Hacker News: Who is hiring?", "this month's hiring thread (mostly tech jobs)"),
]


def _worked(s: dict) -> str:
    st = s.get("state")
    return {"ok": "Yes", "needs_credentials": "Off: no key", "blocked": "No: the site blocked the request",
            "not_run": "Not run"}.get(st, "No: error")


def _cell(x) -> str:
    return str(x if x is not None else "").replace("|", "/").replace("\n", " ")


def section(sources: list[dict]) -> list[str]:
    by = {s.get("name"): s for s in sources or []}
    companies = (by.get("ats_watchlist") or {}).get("companies")
    L = ["## Where this search looked", "",
         "Every job site and source used in the last search, and how many listings each gave.", "",
         "| Job site | What it searches | Searched this time? | Listings looked at | Matched your job titles |",
         "|---|---|---|---|---|"]
    known = [n for n, _, _ in SITES]
    for name, shown, what in SITES:
        s = by.get(name)
        if s is None:
            continue
        L.append(f"| {shown} | {what} | {_worked(s)} | {s.get('fetched', 0)} | {s.get('matched', 0)} |")
    for name, s in by.items():   # any source not described above
        if name not in known:
            L.append(f"| {_cell(name)} |  | {_worked(s)} | {s.get('fetched', 0)} | {s.get('matched', 0)} |")
    if companies is not None:
        L += ["", f"**Company careers pages read ({len(companies)}):** "
              + (", ".join(_cell(c) for c in sorted(companies, key=str.lower)) if companies else "none yet") + "."]
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
