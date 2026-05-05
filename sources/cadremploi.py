"""
Cadremploi scraper — HTML-based.
Cadremploi is the top French job board for cadre/manager roles.
Selectors may need tuning if the site updates its HTML structure — check
[cadremploi] log lines after first run to verify result counts.
"""
import re
import json
import hashlib
import requests
from datetime import datetime, timedelta, date as date_type
from typing import Iterator
from notifier import Job

BASE_URL = "https://www.cadremploi.fr/emploi/recherche"
JOB_BASE = "https://www.cadremploi.fr"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.cadremploi.fr/",
}


def fetch(
    keywords: list[str],
    office_locations: list[str],
    max_age_hours: int,
) -> Iterator[Job]:
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        print("[cadremploi] beautifulsoup4 not installed, skipping")
        return

    seen_ids: set[str] = set()
    cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)

    for keyword in keywords:
        # Remote jobs
        yield from _search(keyword, "France entière", is_remote=True,
                           cutoff=cutoff, seen_ids=seen_ids)
        # Office jobs
        for loc in office_locations:
            yield from _search(keyword, loc, is_remote=False,
                               cutoff=cutoff, seen_ids=seen_ids)


def _search(
    keyword: str,
    location: str,
    is_remote: bool,
    cutoff: datetime,
    seen_ids: set,
) -> Iterator[Job]:
    from bs4 import BeautifulSoup

    params = {
        "texte": keyword,
        "lieu": location,
        "rayon": "30" if not is_remote else "0",
        "typeContrat": "CDI,CDD",
    }
    if is_remote:
        params["teletravail"] = "1"

    try:
        r = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            print(f"[cadremploi] HTTP {r.status_code} for '{keyword}' @ {location}")
            return
        soup = BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        print(f"[cadremploi] request failed for '{keyword}': {e}")
        return

    # Try JSON-LD first (most reliable if present)
    jobs_from_ld = list(_parse_jsonld(soup, keyword, location, is_remote,
                                      cutoff, seen_ids))
    if jobs_from_ld:
        yield from jobs_from_ld
        return

    # Fallback: HTML card parsing
    yield from _parse_html(soup, keyword, location, is_remote, cutoff, seen_ids)


def _parse_jsonld(soup, keyword, location, is_remote, cutoff, seen_ids) -> Iterator[Job]:
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except Exception:
            continue

        items = []
        if isinstance(data, dict):
            t = data.get("@type", "")
            if t == "JobPosting":
                items = [data]
            elif t in ("ItemList", "List"):
                items = [e.get("item", e) for e in data.get("itemListElement", [])]
        elif isinstance(data, list):
            items = [d for d in data if isinstance(d, dict) and d.get("@type") == "JobPosting"]

        for item in items:
            job = _ld_to_job(item, is_remote, seen_ids)
            if job:
                posted = item.get("datePosted", "")
                if posted:
                    try:
                        dt = datetime.fromisoformat(posted[:10])
                        if dt < cutoff:
                            continue
                    except Exception:
                        pass
                yield job


def _ld_to_job(item: dict, is_remote: bool, seen_ids: set) -> Job | None:
    title = item.get("title") or item.get("name", "")
    if not title:
        return None

    url = item.get("url") or item.get("sameAs") or ""
    if not url:
        return None

    job_id = f"ce_{hashlib.md5(url.encode()).hexdigest()[:12]}"
    if job_id in seen_ids:
        return None
    seen_ids.add(job_id)

    org = item.get("hiringOrganization") or {}
    company = org.get("name", "N/A") if isinstance(org, dict) else "N/A"

    loc_data = item.get("jobLocation") or {}
    addr = loc_data.get("address", {}) if isinstance(loc_data, dict) else {}
    location = (addr.get("addressLocality") or addr.get("addressRegion")
                or addr.get("addressCountry") or "France")

    salary_info = item.get("baseSalary") or {}
    salary = None
    if isinstance(salary_info, dict):
        val = salary_info.get("value") or {}
        if isinstance(val, dict):
            lo = val.get("minValue")
            hi = val.get("maxValue")
            unit = salary_info.get("unitText", "")
            if lo and hi:
                salary = f"{int(lo):,}–{int(hi):,} €/{unit}"
            elif lo:
                salary = f"From {int(lo):,} €/{unit}"

    posted_str = item.get("datePosted", "")
    try:
        date_posted = date_type.fromisoformat(posted_str[:10]) if posted_str else None
    except Exception:
        date_posted = None

    return Job(
        id=job_id,
        title=title,
        company=company,
        location=location,
        url=url if url.startswith("http") else JOB_BASE + url,
        salary=salary,
        source="Cadremploi",
        remote=is_remote,
        date_posted=date_posted,
    )


def _parse_html(soup, keyword, location, is_remote, cutoff, seen_ids) -> Iterator[Job]:
    # Try multiple card selector strategies — Cadremploi may use different patterns
    cards = (
        soup.select("article.c-card-offer")
        or soup.select("li.c-card-offer")
        or soup.select("[class*='offer-card']")
        or soup.select("[class*='job-card']")
        or soup.select("article[data-offer-id]")
        or soup.select("li[data-offer-id]")
    )

    label = "remote" if is_remote else location
    if not cards:
        # Log page size for debugging
        text_len = len(soup.get_text())
        print(f"[cadremploi] no cards found for '{keyword}' ({label}), "
              f"page text length={text_len}")
        return

    print(f"[cadremploi] {len(cards)} cards for '{keyword}' ({label})")

    for card in cards:
        job = _card_to_job(card, is_remote, seen_ids)
        if not job:
            continue
        if job.date_posted:
            dt = datetime.combine(job.date_posted, datetime.min.time())
            if dt < cutoff:
                continue
        yield job


def _card_to_job(card, is_remote: bool, seen_ids: set) -> Job | None:
    # Title + URL
    link = (card.select_one("h2 a") or card.select_one("h3 a")
            or card.select_one("[class*='title'] a") or card.select_one("a"))
    if not link:
        return None

    title = link.get_text(strip=True)
    url = link.get("href", "")
    if not url:
        return None
    if not url.startswith("http"):
        url = JOB_BASE + url

    job_id = f"ce_{hashlib.md5(url.encode()).hexdigest()[:12]}"
    if job_id in seen_ids:
        return None
    seen_ids.add(job_id)

    # Company
    company_el = (card.select_one("[class*='company']")
                  or card.select_one("[class*='entreprise']")
                  or card.select_one("[class*='employer']"))
    company = company_el.get_text(strip=True) if company_el else "N/A"

    # Location
    loc_el = (card.select_one("[class*='location']")
              or card.select_one("[class*='lieu']")
              or card.select_one("[class*='city']"))
    location = loc_el.get_text(strip=True) if loc_el else "France"

    # Date
    date_el = card.select_one("time") or card.select_one("[class*='date']")
    date_posted = None
    if date_el:
        dt_attr = date_el.get("datetime") or date_el.get_text(strip=True)
        date_posted = _parse_date(dt_attr)

    # Salary
    salary_el = card.select_one("[class*='salary']") or card.select_one("[class*='salaire']")
    salary = salary_el.get_text(strip=True) if salary_el else None

    return Job(
        id=job_id,
        title=title,
        company=company,
        location=location,
        url=url,
        salary=salary if salary else None,
        source="Cadremploi",
        remote=is_remote,
        date_posted=date_posted,
    )


def _parse_date(text: str) -> date_type | None:
    if not text:
        return None
    text = text.strip()

    # ISO format: 2024-05-01
    try:
        return date_type.fromisoformat(text[:10])
    except Exception:
        pass

    # "il y a X jours"
    m = re.search(r"il y a (\d+)\s*jour", text.lower())
    if m:
        return (datetime.utcnow() - timedelta(days=int(m.group(1)))).date()

    # "il y a X heure"
    m = re.search(r"il y a (\d+)\s*heure", text.lower())
    if m:
        return datetime.utcnow().date()

    # "aujourd'hui"
    if "aujourd" in text.lower():
        return datetime.utcnow().date()

    # "hier"
    if "hier" in text.lower():
        return (datetime.utcnow() - timedelta(days=1)).date()

    return None
