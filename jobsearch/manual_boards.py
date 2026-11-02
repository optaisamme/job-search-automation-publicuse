"""Popular job boards this tool may not search automatically (no public API, sign-in required,
or terms that forbid automated access). The results page lists one-click search links for them,
built from your job titles, so you can open each search yourself."""
from __future__ import annotations

import json
import urllib.parse

q = urllib.parse.quote_plus

# (name, what it is, link builder taking (title, remote_only))
BOARDS = [
    ("LinkedIn", "largest professional network",
     lambda t, r: f"https://www.linkedin.com/jobs/search/?keywords={q(t)}" + ("&f_WT=2" if r else "")),
    ("Indeed", "largest job search site",
     lambda t, r: f"https://www.indeed.com/jobs?q={q(t)}" + ("&l=Remote" if r else "")),
    ("Google Jobs", "jobs collected from many sites",
     lambda t, r: f"https://www.google.com/search?q={q(t + (' remote' if r else '') + ' jobs')}&ibp=htl;jobs"),
    ("Glassdoor", "jobs plus company reviews and salaries",
     lambda t, r: f"https://www.glassdoor.com/Job/jobs.htm?sc.keyword={q(t)}"),
    ("ZipRecruiter", "large job search site",
     lambda t, r: f"https://www.ziprecruiter.com/jobs-search?search={q(t)}" + ("&location=Remote" if r else "")),
    ("HiringCafe", "jobs collected from company career pages",
     lambda t, r: "https://hiring.cafe/?searchState=" + q(json.dumps({"searchQuery": t}))),
    ("Idealist", "nonprofit and social-impact jobs",
     lambda t, r: f"https://www.idealist.org/en/jobs?q={q(t)}"),
    ("DiversityJobs", "jobs at employers focused on diversity and inclusion",
     lambda t, r: f"https://diversityjobs.com/candidate/job_search/quick/results?keyword={q(t)}" + ("&location=remote" if r else "")),
    ("Remote100k", "remote jobs paying $100k or more (no keyword search: opens its US remote jobs list)",
     lambda t, r: "https://remote100k.com/remote-jobs/usa"),
    ("Green Jobs Board", "climate and environmental jobs",
     lambda t, r: f"https://www.greenjobsboard.us/jobs?search={q(t)}"),
    ("HigherEdJobs", "jobs at colleges and universities",
     lambda t, r: f"https://www.higheredjobs.com/search/advanced_action.cfm?Keyword={q(t)}"),
    ("Tech Jobs for Good", "tech jobs at mission-driven organizations",
     lambda t, r: f"https://techjobsforgood.com/jobs/?q={q(t)}"),
    ("Handshake", "jobs for students and recent graduates (sign in with your school account)",
     lambda t, r: f"https://app.joinhandshake.com/stu/postings?query={q(t)}"),
    ("Built In", "tech and startup jobs",
     lambda t, r: f"https://builtin.com/jobs?search={q(t)}"),
    ("Dice", "technology jobs",
     lambda t, r: f"https://www.dice.com/jobs?q={q(t)}"),
]


def section(titles: list[str], remote_only: bool) -> list[str]:
    """Markdown lines: one row per board, one link per job title (up to 3 titles)."""
    titles = [t for t in dict.fromkeys(t.strip() for t in titles) if t][:3]
    L = ["## Popular job boards to search yourself", "",
         "These boards cannot be searched by this tool (no public data feed, sign-in required, or their "
         "terms do not allow automated searching). Each link opens that board's search for one of your "
         "job titles. Open them yourself, as often as you like.", ""]
    if not titles:
        return L + ["Add a job title in settings section 1 to get links here.", ""]
    L += ["| Job board | What it is | " + " | ".join(f"Search: {t.replace('|', '/')}" for t in titles) + " |",
          "|---|---|" + "---|" * len(titles)]
    for name, what, link in BOARDS:
        L.append(f"| {name} | {what} | " + " | ".join(f"[Open]({link(t, remote_only)})" for t in titles) + " |")
    return L + [""]
