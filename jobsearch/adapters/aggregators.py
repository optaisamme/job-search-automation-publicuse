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
    # https://himalayas.app/api
    name = "himalayas"

    def search(self, status: SourceStatus) -> list[RawPosting]:
        out, seen = [], set()
        for q in self.ctx["queries"][:6]:
            r = self.client.get("https://himalayas.app/jobs/api/search?" + urllib.parse.urlencode({"q": q, "country": "US"}))
            if r.status >= 400:
                status.errors.append(f"query {q!r}: HTTP {r.status}")
                continue
            for j in r.json().get("jobs", []):
                gid = j.get("guid") or j.get("applicationLink")
                if gid in seen:
                    continue
                seen.add(gid)
                out.append(RawPosting(
                    source="himalayas", source_url=j.get("guid") or "", employer=j.get("companyName", ""), title=j.get("title", ""),
                    description_text=html_to_text(j.get("description")),
                    location_text="; ".join(j.get("locationRestrictions") or []), workplace_type="remote",
                    apply_url=j.get("applicationLink"), employment_type=j.get("employmentType"),
                    structured_salaries=([{"min": j.get("minSalary"), "max": j.get("maxSalary"), "interval": "year",
                                           "context": f"Himalayas listing salary {j.get('currency') or ''} {j.get('minSalary')}-{j.get('maxSalary')}"}]
                                         if j.get("minSalary") and j.get("maxSalary") and (j.get("currency") or "USD") == "USD" else []),
                    extra={"third_party_salary": [j.get("minSalary"), j.get("maxSalary")], "third_party_published": j.get("pubDate"),
                           "expiry": j.get("expiryDate")},
                ))
        return out


class AdzunaAdapter(Adapter):
    # https://developer.adzuna.com — free key. Salary may be model-predicted: never used.
    name = "adzuna"
    env_keys = ("ADZUNA_APP_ID", "ADZUNA_APP_KEY")

    def search(self, status: SourceStatus) -> list[RawPosting]:
        out, seen = [], set()
        for q in self.ctx["queries"][:8]:
            params = {"app_id": os.environ["ADZUNA_APP_ID"], "app_key": os.environ["ADZUNA_APP_KEY"], "what": q + " remote",
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
            url = "https://data.usajobs.gov/api/search?" + urllib.parse.urlencode({"Keyword": q, "RemoteIndicator": "True", "ResultsPerPage": 100})
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
