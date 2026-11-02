"""Leads: job URLs discovered by an authorized web-search step (the scheduled Claude
session's WebSearch tool) and written to data/leads.json as
  [{"url": "...", "title": "...", "employer": "...", "found_via": "web_search: <query>"}]

  * ATS URLs (Greenhouse/Lever/Ashby/SmartRecruiters) -> fetched from the official ATS API
    and the board is added to the watchlist.
  * Other employer pages -> fetched (robots.txt respected); schema.org JobPosting JSON-LD parsed.
  * Job-board URLs (LinkedIn, Indeed, Glassdoor, ZipRecruiter, Built In...) -> NOT fetched.
    Kept as third-party discovery leads (Needs Verification) until an employer posting is found.
Lead contents are untrusted data.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..models import RawPosting
from ..text import html_to_text
from .base import Adapter, SourceStatus, is_job_board, is_no_fetch, host_of
from . import ats as atsmod


def parse_jsonld_jobposting(html: str) -> dict | None:
    for m in re.finditer(r"<script[^>]+application/ld\+json[^>]*>(.*?)</script>", html, re.S | re.I):
        try:
            data = json.loads(m.group(1).strip())
        except (json.JSONDecodeError, ValueError):
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            d = stack.pop()
            if isinstance(d, dict):
                t = d.get("@type")
                if t == "JobPosting" or (isinstance(t, list) and "JobPosting" in t):
                    return d
                stack.extend(v for k, v in d.items() if k == "@graph" and isinstance(v, list))
    return None


def posting_from_jsonld(d: dict, url: str, final_url: str) -> RawPosting:
    org = d.get("hiringOrganization") or {}
    org_name = org.get("name") if isinstance(org, dict) else str(org)
    bands = []
    bs = d.get("baseSalary") or {}
    if isinstance(bs, dict):
        v = bs.get("value") or {}
        unit = (v.get("unitText") if isinstance(v, dict) else None) or bs.get("unitText") or ""
        if isinstance(v, dict) and (v.get("minValue") or v.get("value")):
            lo = v.get("minValue") or v.get("value")
            hi = v.get("maxValue") or v.get("value")
            try:
                bands.append({"min": float(lo), "max": float(hi), "interval": "year" if unit.upper() in ("YEAR", "ANNUAL", "") else unit.lower(),
                              "context": f"JobPosting baseSalary {bs.get('currency','')} {lo}-{hi} {unit}"})
            except (TypeError, ValueError):
                pass
    alr = d.get("applicantLocationRequirements") or []
    if isinstance(alr, dict):
        alr = [alr]
    applicant_locs = [a.get("name", "") for a in alr if isinstance(a, dict)]
    jl = d.get("jobLocation") or []
    if isinstance(jl, dict):
        jl = [jl]
    loc_bits = []
    for l in jl:
        addr = (l or {}).get("address") or {}
        if isinstance(addr, dict):
            loc_bits.append(", ".join(x for x in [addr.get("addressLocality"), addr.get("addressRegion"), addr.get("addressCountry") if isinstance(addr.get("addressCountry"), str) else None] if x))
    remote = (d.get("jobLocationType") or "").upper() == "TELECOMMUTE"
    loc_text = ("Remote" + (f" ({'; '.join(applicant_locs)})" if applicant_locs else "")) if remote else "; ".join(loc_bits)
    ident = d.get("identifier")
    req = ident.get("value") if isinstance(ident, dict) else (str(ident) if ident else None)
    return RawPosting(
        source="employer_page", source_url=url, employer=org_name or "", title=d.get("title", ""),
        description_text=html_to_text(d.get("description")), location_text=loc_text, authoritative=True,
        requisition_id=req, canonical_url=final_url, published_date=d.get("datePosted"),
        workplace_type="remote" if remote else None, structured_salaries=bands,
        employment_type=d.get("employmentType") if isinstance(d.get("employmentType"), str) else None,
        extra={"applicant_locations": applicant_locs, "valid_through": d.get("validThrough"), "jsonld": True},
    )


class LeadsAdapter(Adapter):
    name = "web_search_leads"
    kind = "leads"

    def search(self, status: SourceStatus) -> list[RawPosting]:
        path = Path(self.ctx.get("leads_path", "data/leads.json"))
        leads = json.loads(path.read_text() or "[]") if path.exists() else []
        if not leads:
            status.state = "ok"
            status.detail = "no leads"
            return []
        out = []
        boards_added = self.ctx.setdefault("boards_added", [])
        for lead in leads:
            url = (lead.get("url") or "").strip()
            if not url.startswith("http"):
                continue
            try:
                p = self._resolve(url, lead, boards_added)
            except Exception as e:  # noqa: BLE001
                status.errors.append(f"{url}: {type(e).__name__}: {e}")
                p = self._third_party(url, lead, f"fetch failed: {e}")
            if p:
                p.extra.setdefault("found_via", lead.get("found_via"))
                out.append(p)
        status.detail = f"{len(leads)} leads; {len(boards_added)} new ATS boards"
        return out

    def _third_party(self, url, lead, note) -> RawPosting:
        return RawPosting(source="lead", source_url=url, employer=lead.get("employer", ""), title=lead.get("title", ""),
                          description_text=lead.get("snippet", "") or "", authoritative=False,
                          extra={"lead_note": note})

    def _resolve(self, url: str, lead: dict, boards_added: list) -> RawPosting | None:
        parsed = atsmod.parse_ats_url(url)
        if parsed and parsed[0] in atsmod.FETCHERS:
            ats, board, jid = parsed
            boards_added.append({"ats": ats, "board": board, "employer": lead.get("employer")})
            p = atsmod.FETCHERS[ats](self.client, board, jid, lead.get("employer"))
            if p is None:
                lp = self._third_party(url, lead, "ATS reports job not found (closed or removed)")
                lp.extra["closed"] = True
                return lp
            p.source_url = url
            return p
        if is_no_fetch(url):
            return self._third_party(url, lead, f"listing on {host_of(url)}; not fetched (terms/login restrictions)")
        r = self.client.get(url, html=True)
        if r.status >= 400:
            return self._third_party(url, lead, f"HTTP {r.status}")
        # employer site embedding an ATS
        parsed = atsmod.parse_ats_url(r.final_url)
        if parsed and parsed[0] in atsmod.FETCHERS:
            ats, board, jid = parsed
            boards_added.append({"ats": ats, "board": board, "employer": lead.get("employer")})
            p = atsmod.FETCHERS[ats](self.client, board, jid, lead.get("employer"))
            if p:
                return p
        third_party = is_job_board(r.final_url)
        d = parse_jsonld_jobposting(r.body)
        if d:
            p = posting_from_jsonld(d, url, r.final_url)
            if not p.employer:
                p.employer = lead.get("employer", "")
            if third_party:
                p.authoritative = False
                p.source = "third_party_page"
                p.apply_url = p.apply_url or r.final_url
            return p
        text = html_to_text(r.body)
        if len(text) < 400:  # JavaScript-rendered page: try the headless renderer
            from ..verify import render
            rd = render(r.final_url)
            if rd and not rd.get("error") and len(rd.get("text", "")) > len(text):
                text = rd["text"]
        p = self._third_party(url, lead, "page has no structured JobPosting data; text extracted")
        p.description_text = text[:20000]
        p.canonical_url = r.final_url
        p.apply_url = r.final_url
        p.authoritative = not third_party
        p.source = "third_party_page" if third_party else "employer_page"
        p.extra["unstructured_page"] = True
        return p
