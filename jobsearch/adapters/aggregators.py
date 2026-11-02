"""Discovery sources with documented public/free APIs. Their content is third-party
(authoritative=False) except USAJOBS, which is the official federal posting system.
Results must be confirmed on the employer/ATS posting before they can qualify."""
from __future__ import annotations

import os
import urllib.parse

from ..models import RawPosting
from ..text import html_to_text
from .base import Adapter, SourceStatus


class RemotiveAdapter(Adapter):
    # https://remotive.com/api-documentation — please link back to Remotive; low request volume.
    name = "remotive"

    def search(self, status: SourceStatus) -> list[RawPosting]:
        out, seen = [], set()
        for q in self.ctx["queries"][:6]:
            r = self.client.get("https://remotive.com/api/remote-jobs?" + urllib.parse.urlencode({"search": q, "limit": 100}))
            if r.status >= 400:
                status.errors.append(f"query {q!r}: HTTP {r.status}")
                continue
            for j in r.json().get("jobs", []):
                if j.get("id") in seen:
                    continue
                seen.add(j.get("id"))
                out.append(RawPosting(
                    source="remotive", source_url=j.get("url", ""), employer=j.get("company_name", ""), title=j.get("title", ""),
                    description_text=html_to_text(j.get("description")) + (f"\nSalary: {j.get('salary')}" if j.get("salary") else ""),
                    location_text=j.get("candidate_required_location", ""), apply_url=j.get("url"),
                    workplace_type="remote", employment_type=j.get("job_type"),
                    extra={"third_party_salary": j.get("salary"), "third_party_published": j.get("publication_date")},
                ))
        return out


class RemoteOKAdapter(Adapter):
    # https://remoteok.com/api — terms require attribution/link back to Remote OK.
    name = "remoteok"

    def search(self, status: SourceStatus) -> list[RawPosting]:
        r = self.client.get("https://remoteok.com/api")
        if r.status >= 400:
            raise RuntimeError(f"HTTP {r.status}")
        out = []
        for j in r.json()[1:]:
            if not isinstance(j, dict):
                continue
            out.append(RawPosting(
                source="remoteok", source_url=j.get("url", ""), employer=j.get("company", ""), title=j.get("position", ""),
                description_text=html_to_text(j.get("description")), location_text=j.get("location", ""),
                workplace_type="remote", apply_url=j.get("apply_url"),
                extra={"third_party_salary": [j.get("salary_min"), j.get("salary_max")], "third_party_published": j.get("date")},
            ))
        return out


class HimalayasAdapter(Adapter):
    # https://himalayas.app/api — search returns 20 per page (?page=N); the browse feed pages by ?cursor=.
    name = "himalayas"
    SEARCH_PAGES = 5     # per search word: up to 100 jobs
    BROWSE_PAGES = 10    # newest jobs regardless of search words: up to 200 jobs

    def _posting(self, j: dict) -> RawPosting:
        return RawPosting(
            source="himalayas", source_url=j.get("guid") or "", employer=j.get("companyName", ""), title=j.get("title", ""),
            description_text=html_to_text(j.get("description")),
            location_text="; ".join(j.get("locationRestrictions") or []), workplace_type="remote",
            apply_url=j.get("applicationLink"), employment_type=j.get("employmentType"),
            structured_salaries=([{"min": j.get("minSalary"), "max": j.get("maxSalary"), "interval": "year",
                                   "context": f"Himalayas listing salary {j.get('currency') or ''} {j.get('minSalary')}-{j.get('maxSalary')}"}]
                                 if j.get("minSalary") and j.get("maxSalary") and (j.get("currency") or "USD") == "USD"
                                 and (j.get("salaryPeriod") or "annual") == "annual" else []),
            extra={"third_party_salary": [j.get("minSalary"), j.get("maxSalary")], "third_party_published": j.get("pubDate"),
                   "expiry": j.get("expiryDate")},
        )

    def search(self, status: SourceStatus) -> list[RawPosting]:
        out, seen = [], set()

        def add(jobs):
            for j in jobs:
                gid = j.get("guid") or j.get("applicationLink")
                if gid and gid not in seen:
                    seen.add(gid)
                    out.append(self._posting(j))

        for q in self.ctx["queries"][:6]:
            for page in range(1, self.SEARCH_PAGES + 1):
                r = self.client.get("https://himalayas.app/jobs/api/search?" + urllib.parse.urlencode({"q": q, "country": "US", "page": page}))
                if r.status >= 400:
                    status.errors.append(f"query {q!r} page {page}: HTTP {r.status}")
                    break
                jobs = r.json().get("jobs", [])
                add(jobs)
                if len(jobs) < 20:
                    break
        cursor = None
        for _ in range(self.BROWSE_PAGES):
            r = self.client.get("https://himalayas.app/jobs/api?" + urllib.parse.urlencode({"limit": 20, **({"cursor": cursor} if cursor else {})}))
            if r.status >= 400:
                status.errors.append(f"newest jobs feed: HTTP {r.status}")
                break
            d = r.json()
            add(d.get("jobs", []))
            cursor = d.get("nextCursor")
            if not cursor:
                break
        return out


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


class TheMuseAdapter(Adapter):
    # https://www.themuse.com/developers/api/v2 — public jobs API, all job types; no key needed at low volume.
    # Not searchable by keyword, so the newest jobs are collected and matched to your titles here.
    name = "themuse"
    PAGES = 20   # 20 jobs per page: newest 400

    def search(self, status: SourceStatus) -> list[RawPosting]:
        from ..criteria import CRITERIA
        remote = CRITERIA.get("remote_only", True)
        out, seen = [], set()
        for page in range(1, self.PAGES + 1):
            params = [("page", page)] + ([("location", "Flexible / Remote")] if remote else [])
            r = self.client.get("https://www.themuse.com/api/public/jobs?" + urllib.parse.urlencode(params))
            if r.status >= 400:
                status.errors.append(f"page {page}: HTTP {r.status}")
                break
            d = r.json()
            for j in d.get("results", []):
                if j.get("id") in seen:
                    continue
                seen.add(j.get("id"))
                locs = [l.get("name", "") for l in j.get("locations") or []]
                url = (j.get("refs") or {}).get("landing_page", "")
                out.append(RawPosting(
                    source="themuse", source_url=url, employer=(j.get("company") or {}).get("name", ""), title=j.get("name", ""),
                    description_text=html_to_text(j.get("contents")), location_text="; ".join(locs), apply_url=url,
                    workplace_type="remote" if locs and all(l == "Flexible / Remote" for l in locs) else None,
                    extra={"third_party_published": j.get("publication_date")},
                ))
            if page >= (d.get("page_count") or 0):
                break
        return out


class JobicyAdapter(Adapter):
    # https://jobicy.com/jobs-rss-feed — free remote-jobs API. Jobicy asks to be credited with a link
    # and for apply buttons to go to the original job URL (results link to each Jobicy job page).
    name = "jobicy"

    def search(self, status: SourceStatus) -> list[RawPosting]:
        r = self.client.get("https://jobicy.com/api/v2/remote-jobs?" + urllib.parse.urlencode({"count": 100, "geo": "usa"}))
        if r.status >= 400:
            raise RuntimeError(f"HTTP {r.status}")
        out = []
        for j in r.json().get("jobs", []):
            lo, hi = _num(j.get("salaryMin")), _num(j.get("salaryMax"))
            yearly = (j.get("salaryPeriod") or "") == "yearly" and (j.get("salaryCurrency") or "USD") == "USD"
            out.append(RawPosting(
                source="jobicy", source_url=j.get("url", ""), employer=j.get("companyName", ""), title=j.get("jobTitle", ""),
                description_text=html_to_text(j.get("jobDescription")), location_text=j.get("jobGeo", ""),
                workplace_type="remote", apply_url=j.get("url"),
                employment_type=", ".join(j.get("jobType") or []) or None,
                structured_salaries=([{"min": lo, "max": hi, "interval": "year", "context": f"Jobicy listing salary USD {lo:,.0f}-{hi:,.0f}"}]
                                     if yearly and lo and hi else []),
                extra={"third_party_salary": [lo, hi], "third_party_published": j.get("pubDate")},
            ))
        return out


class WeWorkRemotelyAdapter(Adapter):
    # https://weworkremotely.com/remote-job-rss-feed — public RSS feed of the newest remote jobs, all categories.
    name = "weworkremotely"

    def search(self, status: SourceStatus) -> list[RawPosting]:
        import xml.etree.ElementTree as ET
        r = self.client.get("https://weworkremotely.com/remote-jobs.rss")
        if r.status >= 400:
            raise RuntimeError(f"HTTP {r.status}")
        out = []
        for it in ET.fromstring(r.body).findall("./channel/item"):
            f = {c.tag.split("}")[-1]: (c.text or "").strip() for c in it}
            company, _, title = f.get("title", "").partition(": ")
            if not title:
                company, title = "", f.get("title", "")
            where = "; ".join(x for x in (f.get("region"), f.get("country"), f.get("state")) if x)
            out.append(RawPosting(
                source="weworkremotely", source_url=f.get("link", ""), employer=company.strip(), title=title.strip(),
                description_text=html_to_text(f.get("description")), location_text=where, workplace_type="remote",
                apply_url=f.get("link"), employment_type=f.get("type") or None,
                extra={"third_party_published": f.get("pubDate"), "expiry": f.get("expires_at")},
            ))
        return out


class WorkingNomadsAdapter(Adapter):
    # https://www.workingnomads.com/api/exposed_jobs/ — public feed of the newest remote jobs.
    name = "workingnomads"

    def search(self, status: SourceStatus) -> list[RawPosting]:
        r = self.client.get("https://www.workingnomads.com/api/exposed_jobs/")
        if r.status >= 400:
            raise RuntimeError(f"HTTP {r.status}")
        out = []
        for j in r.json():
            out.append(RawPosting(
                source="workingnomads", source_url=j.get("url", ""), employer=j.get("company_name", ""), title=j.get("title", ""),
                description_text=html_to_text(j.get("description")), location_text=j.get("location", ""),
                workplace_type="remote", apply_url=j.get("url"),
                extra={"third_party_published": j.get("pub_date")},
            ))
        return out


class JobspressoAdapter(Adapter):
    # https://jobspresso.co — public RSS feed of the newest hand-checked remote jobs.
    name = "jobspresso"

    def search(self, status: SourceStatus) -> list[RawPosting]:
        import html as _html
        import re as _re
        import xml.etree.ElementTree as ET
        r = self.client.get("https://jobspresso.co/feed/?post_type=job_listing")
        if r.status >= 400:
            raise RuntimeError(f"HTTP {r.status}")
        out = []
        for it in ET.fromstring(r.body).findall("./channel/item"):
            f = {c.tag.split("}")[-1]: (c.text or "").strip() for c in it}
            # creator looks like "Figma<br>⚲&nbsp;United States": company, then location
            parts = [x.strip(" \u26b2\xa0") for x in _re.split(r"<br\s*/?>", _html.unescape(f.get("creator", "")))]
            out.append(RawPosting(
                source="jobspresso", source_url=f.get("link", ""), employer=parts[0] if parts else "", title=f.get("title", ""),
                description_text=html_to_text(f.get("encoded") or f.get("description")),
                location_text=parts[1] if len(parts) > 1 else "", workplace_type="remote", apply_url=f.get("link"),
                extra={"third_party_published": f.get("pubDate")},
            ))
        return out


class JoobleAdapter(Adapter):
    # https://jooble.org/api/about — free key (request on that page). Jooble collects jobs from many job sites.
    # Request format: POST https://jooble.org/api/<key> with {"keywords": ..., "location": ...}.
    name = "jooble"
    env_keys = ("JOOBLE_API_KEY",)

    def search(self, status: SourceStatus) -> list[RawPosting]:
        from ..criteria import CRITERIA
        out, seen = [], set()
        url = "https://jooble.org/api/" + os.environ["JOOBLE_API_KEY"].strip()
        remote = CRITERIA.get("remote_only", True)
        where = "Remote" if remote else (CRITERIA.get("home_state") or "United States")
        for q in self.ctx["queries"][:8]:
            for page in (1, 2):
                r = self.client.post_json(url, {"keywords": q, "location": where, "page": str(page)})
                if r.status >= 400:
                    status.errors.append(f"query {q!r}: HTTP {r.status}")
                    break
                jobs = (r.json() or {}).get("jobs") or []
                for j in jobs:
                    jid = j.get("id") or j.get("link")
                    if not jid or jid in seen:
                        continue
                    seen.add(jid)
                    typ = (j.get("type") or "")
                    out.append(RawPosting(
                        source="jooble", source_url=j.get("link", ""), employer=j.get("company", ""), title=" ".join(html_to_text(j.get("title")).split()),
                        description_text=html_to_text(j.get("snippet")) + (f"\nSalary: {j.get('salary')}" if j.get("salary") else ""),
                        location_text=j.get("location", ""), apply_url=j.get("link"),
                        workplace_type="remote" if "remote" in (j.get("location") or "").lower() else None,
                        employment_type=typ or None,
                        extra={"third_party_salary": j.get("salary"), "third_party_published": j.get("updated"),
                               "found_on": j.get("source")},
                    ))
                if len(jobs) < 20:
                    break
        return out


class ReliefWebAdapter(Adapter):
    # https://apidoc.reliefweb.int — UN OCHA's humanitarian and nonprofit job board. Free, but requests must
    # carry an approved "appname" (request one at https://apidoc.reliefweb.int/parameters#appname).
    name = "reliefweb"
    env_keys = ("RELIEFWEB_APPNAME",)

    def search(self, status: SourceStatus) -> list[RawPosting]:
        out, seen = [], set()
        app = os.environ["RELIEFWEB_APPNAME"].strip()
        for q in self.ctx["queries"][:6]:
            params = [("appname", app), ("profile", "full"), ("limit", 50), ("sort[]", "date.created:desc"),
                      ("query[value]", q), ("query[fields][]", "title")]
            r = self.client.get("https://api.reliefweb.int/v2/jobs?" + urllib.parse.urlencode(params))
            if r.status >= 400:
                status.errors.append(f"query {q!r}: HTTP {r.status}")
                continue
            for item in (r.json() or {}).get("data") or []:
                f = item.get("fields") or {}
                url = f.get("url") or f.get("url_alias") or ""
                if not url or url in seen:
                    continue
                seen.add(url)
                orgs = [x.get("name", "") for x in f.get("source") or [] if isinstance(x, dict)]
                countries = [x.get("name", "") for x in f.get("country") or [] if isinstance(x, dict)]
                date = f.get("date") or {}
                out.append(RawPosting(
                    source="reliefweb", source_url=url, employer=orgs[0] if orgs else "", title=f.get("title", ""),
                    description_text=html_to_text(f.get("body-html") or f.get("body")),
                    location_text="; ".join(countries), apply_url=url,
                    extra={"third_party_published": date.get("created"), "close_date": date.get("closing")},
                ))
        return out


class AdzunaAdapter(Adapter):
    # https://developer.adzuna.com — free key. Salary may be model-predicted: never used.
    name = "adzuna"
    env_keys = ("ADZUNA_APP_ID", "ADZUNA_APP_KEY")

    def search(self, status: SourceStatus) -> list[RawPosting]:
        out, seen = [], set()
        for q in self.ctx["queries"][:8]:
            params = {"app_id": os.environ["ADZUNA_APP_ID"], "app_key": os.environ["ADZUNA_APP_KEY"], "what": q + (" remote" if __import__("jobsearch.criteria", fromlist=["CRITERIA"]).CRITERIA.get("remote_only", True) else ""),
                      "results_per_page": 50, "content-type": "application/json", "max_days_old": 30}
            r = self.client.get("https://api.adzuna.com/v1/api/jobs/us/search/1?" + urllib.parse.urlencode(params))
            if r.status >= 400:
                status.errors.append(f"query {q!r}: HTTP {r.status}")
                continue
            for j in r.json().get("results", []):
                if j.get("id") in seen:
                    continue
                seen.add(j.get("id"))
                out.append(RawPosting(
                    source="adzuna", source_url=j.get("redirect_url", ""), employer=(j.get("company") or {}).get("display_name", ""),
                    title=j.get("title", ""), description_text=html_to_text(j.get("description")),
                    location_text=(j.get("location") or {}).get("display_name", ""),
                    extra={"third_party_salary": [j.get("salary_min"), j.get("salary_max")], "salary_is_predicted": j.get("salary_is_predicted")},
                ))
        return out


class UsaJobsAdapter(Adapter):
    # https://developer.usajobs.gov — free API key; official federal postings (authoritative).
    name = "usajobs"
    kind = "official"
    authoritative = True
    env_keys = ("USAJOBS_API_KEY", "USAJOBS_EMAIL")

    def search(self, status: SourceStatus) -> list[RawPosting]:
        h = {"Host": "data.usajobs.gov", "Authorization-Key": os.environ["USAJOBS_API_KEY"]}
        out, seen = [], set()
        for q in self.ctx["queries"][:5]:
            from ..criteria import CRITERIA
            params = {"Keyword": q, "ResultsPerPage": 100}
            if CRITERIA.get("remote_only", True):
                params["RemoteIndicator"] = "True"
            url = "https://data.usajobs.gov/api/search?" + urllib.parse.urlencode(params)
            r = self.client.get(url, headers={**h, "User-Agent": os.environ["USAJOBS_EMAIL"]})
            if r.status >= 400:
                status.errors.append(f"query {q!r}: HTTP {r.status}")
                continue
            items = (r.json().get("SearchResult") or {}).get("SearchResultItems") or []
            for it in items:
                d = it.get("MatchedObjectDescriptor") or {}
                pid = d.get("PositionID") or d.get("PositionURI")
                if pid in seen:
                    continue
                seen.add(pid)
                det = (d.get("UserArea") or {}).get("Details") or {}
                text = "\n".join(filter(None, [
                    det.get("JobSummary"), "Duties:", "\n".join(det.get("MajorDuties") or []),
                    "Qualifications:", d.get("QualificationSummary"), det.get("Education"), det.get("Requirements"),
                    "Remote: " + str(det.get("RemoteIndicator")), "Telework: " + str(det.get("TeleworkEligible")),
                ]))
                bands = []
                for rem in d.get("PositionRemuneration") or []:
                    code = (rem.get("RateIntervalCode") or "").upper()
                    try:
                        bands.append({"min": float(rem["MinimumRange"]), "max": float(rem["MaximumRange"]),
                                      "interval": "year" if code in ("PA", "PER YEAR") else code.lower(),
                                      "context": f"USAJOBS remuneration {rem.get('MinimumRange')}-{rem.get('MaximumRange')} {rem.get('Description') or code}"})
                    except (KeyError, ValueError):
                        pass
                locs = [l.get("LocationName", "") for l in d.get("PositionLocation") or []]
                apply = (d.get("ApplyURI") or [None])[0]
                out.append(RawPosting(
                    source="usajobs", source_url=d.get("PositionURI", ""), employer=d.get("OrganizationName", ""),
                    title=d.get("PositionTitle", ""), description_text=text, location_text="; ".join(locs),
                    authoritative=True, ats="usajobs", ats_job_id=d.get("PositionID"), requisition_id=d.get("PositionID"),
                    canonical_url=d.get("PositionURI"), apply_url=apply, structured_salaries=bands,
                    workplace_type="remote" if det.get("RemoteIndicator") in (True, "True", "true") else None,
                    published_date=d.get("PublicationStartDate"),
                    extra={"close_date": d.get("ApplicationCloseDate")},
                ))
        return out
