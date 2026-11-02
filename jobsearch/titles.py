"""Match a job title to one of the user's job title groups (EDIT_ME_JOB_SEARCH_SETTINGS/EDIT_ME_1_job_search_settings.toml)."""
from __future__ import annotations

import re


def _c(p: str) -> re.Pattern:
    return re.compile(p, re.I)


class TitleMatcher:
    def __init__(self, profile: dict):
        self.families = []
        for t in profile.get("titles", []):
            # all of the title's words, in any order: "Data Analyst" also finds "Analyst, Data" and "Senior Data Analyst"
            pats = [_c("".join(r"(?=.*\b" + re.escape(w) + r"(?!\w))" for w in pt.split()))
                    for pt in t.get("plain_titles", []) if pt.split()]
            if pats:
                self.families.append({"track": t["track"], "family": t["family"], "include": pats,
                                      "require_any": [w.lower() for w in t.get("require_any", [])]})
        tr = profile.get("title_rules", {})
        self.exclude = [_c(r"\b" + re.escape(w) + r"\b") for w in tr.get("exclude_plain", [])]
        self.must_mention = [w.lower() for w in tr.get("must_mention", [])]

    def match_title(self, title: str) -> bool:
        """Title-only pre-screen (before the job description is downloaded)."""
        t = re.sub(r"\s+", " ", title or "").strip()
        return bool(t) and not any(p.search(t) for p in self.exclude) and any(
            p.search(t) for f in self.families for p in f["include"])

    def match(self, title: str, text: str = "") -> dict | None:
        t = re.sub(r"\s+", " ", title or "").strip()
        if not t or any(p.search(t) for p in self.exclude):
            return None
        low_text = (text or "").lower()
        for f in self.families:
            if not any(p.search(t) for p in f["include"]):
                continue
            if self.must_mention and not any(w in (t.lower() + " " + low_text) for w in self.must_mention):
                continue
            if f["require_any"] and not any(w in low_text for w in f["require_any"]):
                continue
            return {"track": f["track"], "family": f["family"]}
        return None
