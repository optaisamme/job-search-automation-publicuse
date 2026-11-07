"""'Your settings for this search': the settings a search used, shown at the top of its report."""
from __future__ import annotations

from pathlib import Path

# Relative to JOB_SEARCH_RESULTS/REPORT_*.md on github.com: the questionnaire list in this copy
CHANGE_LINK = "../../../issues/new/choose"


def _list(items) -> str:
    items = [str(x) for x in (items or []) if str(x).strip()]
    return ", ".join(items) if items else "none"


def rows(root: Path, prof: dict, exp: dict) -> list[list[str]]:
    """[setting, value] pairs, in the order of the setup questionnaire."""
    import tomllib
    from .criteria import CRITERIA as C
    from .pipeline import SETTINGS_DIR, watched_boards
    from .titles import TitleMatcher
    from .adapters.aggregators import search_size, SEARCH_SIZE_DEFAULTS
    try:
        settings = tomllib.load(open(Path(root) / SETTINGS_DIR / "EDIT_ME_1_job_search_settings.toml", "rb"))
    except (OSError, ValueError):
        settings = {}
    out = []
    titles = prof.get("titles", [])
    for t in titles:
        out.append([f"Job titles ({t['family']})" if len(titles) > 1 else "Job titles", _list(t.get("plain_titles"))])
    if not prof.get("titles"):
        out.append(["Job titles", "none"])
    out.append(["Remote jobs only?", "Yes" if C.get("remote_only", True) else "No, also hybrid and on-site jobs in my state"])
    out.append(["Your state", f"{C['home_state']} ({C.get('home_state_abbr') or '-'})" if C.get("home_state") else "not set"])
    if not C.get("remote_only", True):
        out.append(["Cities where you could work on site", _list(C.get("home_cities"))])
    money = lambda n: f"${n:,}" if n else "no minimum"
    out.append(["Lowest single salary", money(C.get("single_min", 0))])
    out.append(["Lowest start of a salary range", money(C.get("range_lower_min", 0))])
    out.append(["A salary range must end above", money(C.get("range_upper_gt", 0))])
    tr = prof.get("title_rules", {})
    out.append(["Title words to skip", _list(tr.get("exclude_plain"))])
    out.append(["Words the job description must mention", _list(tr.get("must_mention"))])
    out.append(["Check certification requirements?", "Yes" if C.get("cert_filter_on", True) else "No"])
    if C.get("cert_filter_on", True):
        out.append(["Certifications you have, or could get before being hired", _list(C.get("allowed_prehire_certs"))])
    out.append(["Employers to skip", _list((prof.get("employer_rules") or {}).get("exclude"))])
    for r in C.get("custom_rules", []):
        out.append([f"Your rule \"{r['name']}\"", ("on" if r.get("on", True) else "off") + f": {_list(r['terms'])}"])
    out.append(["Your skills", _list(s.get("name") for s in exp.get("skills", []))])
    ten = exp.get("tenure", {}) or {}
    out.append(["Years of experience in your field", str(ten.get("years_of_experience") or "not set")])
    out.append(["Certifications you hold", _list(ten.get("certifications_held"))])
    watched, _ = watched_boards(prof)
    out.append(["Companies to watch", _list(b["board"] for b in watched)])
    out.append(["Skills-based matching", TitleMatcher(prof, exp.get("skills", [])).skills.summary()])
    kw = (settings.get("search") or {}).get("keywords") or []
    if kw:
        out.append(["Search words", _list(kw)])
    sz = search_size({"search_size": settings.get("search_size") or {}})
    out.append(["How many jobs to look through",
                ("Recommended: " if sz == SEARCH_SIZE_DEFAULTS else "")
                + f"{sz['newest_jobs_per_site']:,} newest jobs per site, {sz['jobs_per_search_word']:,} for each job title, "
                  f"Jobicy up to {sz['jobicy_max_jobs']:,}"])
    wk = settings.get("automatic_weekly_search") or {}
    on = str(wk.get("on", "no")).strip().lower() in ("yes", "y", "true", "on", "1")
    out.append(["Automatic weekly searches", f"On, every {str(wk.get('day', 'Friday')).capitalize()}" if on else "Off"])
    return out


def section(pairs: list[list[str]] | None, link: str = CHANGE_LINK) -> list[str]:
    if not pairs:
        return []
    cell = lambda x: str(x).replace("|", "/").replace("\n", " ")
    L = ["## Your settings for this search", "", f"[click here to change these settings]({link})", "",
         "| Setting | Your answer |", "|---|---|"]
    L += [f"| {cell(k)} | {cell(v)} |" for k, v in pairs]
    return L + [""]
