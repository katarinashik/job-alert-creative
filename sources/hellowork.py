"""
HelloWork scraper — HTML + JSON-LD based.
hellowork.com is a large French job board with strong creative/marketing listings.
Uses SSR (Next.js), so job data is available in the HTML response.
"""
import re
import json
import hashlib
import requests
from datetime import datetime, timedelta, date as date_type
from typing import Iterator
from notifier import Job

BASE_URL = "https://www.hellowork.com/fr-fr/emploi/recherche.html"
JOB_BASE = "https://www.hellowork.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.hellowork.com/",
}


def fetch(
    keywords: list[str],
    office_locations: list[str],
    max_age_hours: int,
) -> Iterator[Job]:
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        print("[hellowork] beautifulsoup4 not installed, skipping")
        return

    seen_ids: set[str] = set()
    cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)

    for keyword in keywords:
        # Remote jobs
        yield from _search(keyword, "France", is_remote=True,
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
        "k": keyword,
        "l": location,
        "ray": "30",
        "c": "CDI,CDD",
    }
    if is_remote:
        params["teletravail"] = "true"
        params.pop("ray", None)

    try:
        r = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            print(f"[hellowork] HTTP {r.status_code} for '{keyword}' @ {location}")
            return
        soup = BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        print(f"[hellowork] request failed for '{keyword}': {e}")
        return

    # Try JSON-LD first
    jobs_from_ld = list(_parse_jsonld(soup, is_remote, seen_ids, cutoff))
    if jobs_from_ld:
        label = "remote" if is_remote else location
        print(f"[hellowork] {len(jobs_from_ld)} jobs (JSON-LD) for '{keyword}' ({label})")
        yield from jobs_from_ld
        return

    # Try __NEXT_DATA__ (Next.js hydration)
    jobs_from_next = list(_parse_next_data(soup, is_remote, seen_ids, cutoff))
    if jobs_from_next:
        label = "remote" if is_remote else location
        print(f"[hellowork] {len(jobs_from_next)} jobs (NEXT_DATA) for '{keyword}' ({label})")
        yield from jobs_from_next
        return

    # Fallback: HTML cards
    yield from _parse_html(soup, keyword, location, is_remote, cutoff, seen_ids)


def _parse_jsonld(soup, is_remote, seen_ids, cutoff) -> Iterator[Job]:
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
            posted = item.get("datePosted", "")
            if posted:
                try:
                    dt = datetime.fromisoformat(posted[:10])
                    if dt < cutoff:
                        continue
                except Exception:
                    pass

            job = _ld_to_job(item, is_remote, seen_ids)
            if job:
                yield job


def _parse_next_data(soup, is_remote, seen_ids, cutoff) -> Iterator[Job]:
    tag = soup.find("script", id="__NEXT_DATA__")
    if not tag:
        return
    try:
        data = json.loads(tag.string or "")
    except Exception:
        return

    # Drill into props.pageProps for job list
    page_props = (data.get("props", {}).get("pageProps", {})
                  or data.get("props", {}).get("initialState", {}))

    jobs_raw = (page_props.get("jobs") or page_props.get("offers")
                or page_props.get("results") or [])

    if not jobs_raw and isinstance(page_props, dict):
        # Try to find any list of dicts with "title" key
        for v in page_props.values():
            if isinstance(v, list) and v and isinstance(v[0], dict) and "title" in v[0]:
                jobs_raw = v
                break

    for item in jobs_raw:
        if not isinstance(item, dict):
            continue

        posted = item.get("datePosted") or item.get("publishedAt") or item.get("date") or ""
        if posted:
            try:
                dt = datetime.fromisoformat(str(posted)[:10])
                if dt < cutoff:
                    continue
            except Exception:
                pass

        job = _next_item_to_job(item, is_remote, seen_ids)
        if job:
            yield job


def _next_item_to_job(item: dict, is_remote: bool, seen_ids: set) -> Job | None:
    title = item.get("title") or item.get("name") or ""
    if not title:
        return None

    url = item.get("url") or item.get("link") or item.get("applyUrl") or ""
    if not url:
        return None
    if not url.startswith("http"):
        url = JOB_BASE + url

    job_id = f"hw_{hashlib.md5(url.encode()).hexdigest()[:12]}"
    if job_id in seen_ids:
        return None
    seen_ids.add(job_id)

    company = (item.get("company") or item.get("companyName")
               or item.get("employer") or "N/A")
    if isinstance(company, dict):
        company = company.get("name", "N/A")

    location = (item.get("location") or item.get("city")
                or item.get("place") or "France")
    if isinstance(location, dict):
        location = location.get("name") or location.get("city") or "France"

    salary = item.get("salary") or item.get("salaire") or None
    if isinstance(salary, dict):
        lo = salary.get("min") or salary.get("minimum")
        hi = salary.get("max") or salary.get("maximum")
        salary = f"{lo}–{hi} €" if lo and hi else str(salary) if salary else None

    posted_str = item.get("datePosted") or item.get("publishedAt") or ""
    try:
        date_posted = date_type.fromisoformat(str(posted_str)[:10]) if posted_str else None
    except Exception:
        date_posted = None

    return Job(
        id=job_id,
        title=str(title),
        company=str(company),
        location=str(location),
        url=url,
        salary=str(salary) if salary else None,
        source="HelloWork",
        remote=is_remote,
        date_posted=date_posted,
    )


def _ld_to_job(item: dict, is_remote: bool, seen_ids: set) -> Job | None:
    title = item.get("title") or item.get("name", "")
    if not title:
        return None

    url = item.get("url") or item.get("sameAs") or ""
    if not url:
        return None
    if not url.startswith("http"):
        url = JOB_BASE + url

    job_id = f"hw_{hashlib.md5(url.encode()).hexdigest()[:12]}"
    if job_id in seen_ids:
        return None
    seen_ids.add(job_id)

    org = item.get("hiringOrganization") or {}
    company = org.get("name", "N/A") if isinstance(org, dict) else "N/A"

    loc_data = item.get("jobLocation") or {}
    addr = loc_data.get("address", {}) if isinstance(loc_data, dict) else {}
    location = (addr.get("addressLocality") or addr.get("addressRegion") or "France")

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

    posted_str = item.get("datePosted", "")
    try:
        date_posted = date_type.fromisoformat(posted_str[:10]) if posted_str else None
    except Exception:
        date_posted = None

    return Job(
        id=job_id,
        title=str(title),
        company=str(company),
        location=str(location),
        url=url,
        salary=salary,
        source="HelloWork",
        remote=is_remote,
        date_posted=date_posted,
    )


def _parse_html(soup, keyword, location, is_remote, cutoff, seen_ids) -> Iterator[Job]:
    cards = (
        soup.select("li[data-id]")
        or soup.select("article[data-id]")
        or soup.select("[class*='JobCard']")
        or soup.select("[class*='job-card']")
        or soup.select("[class*='offer-item']")
        or soup.select("li[class*='tw-']")  # Tailwind-based cards
    )

    label = "remote" if is_remote else location
    if not cards:
        text_len = len(soup.get_text())
        print(f"[hellowork] no cards found for '{keyword}' ({label}), "
              f"page text length={text_len}")
        return

    print(f"[hellowork] {len(cards)} cards (HTML) for '{keyword}' ({label})")

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

    job_id = f"hw_{hashlib.md5(url.encode()).hexdigest()[:12]}"
    if job_id in seen_ids:
        return None
    seen_ids.add(job_id)

    company_el = (card.select_one("[class*='company']")
                  or card.select_one("[class*='employer']")
                  or card.select_one("[class*='entreprise']"))
    company = company_el.get_text(strip=True) if company_el else "N/A"

    loc_el = (card.select_one("[class*='location']")
              or card.select_one("[class*='city']")
              or card.select_one("[class*='lieu']"))
    location = loc_el.get_text(strip=True) if loc_el else "France"

    date_el = card.select_one("time") or card.select_one("[class*='date']")
    date_posted = None
    if date_el:
        dt_attr = date_el.get("datetime") or date_el.get_text(strip=True)
        date_posted = _parse_date(dt_attr)

    salary_el = (card.select_one("[class*='salary']")
                 or card.select_one("[class*='salaire']"))
    salary = salary_el.get_text(strip=True) if salary_el else None

    return Job(
        id=job_id,
        title=title,
        company=company,
        location=location,
        url=url,
        salary=salary if salary else None,
        source="HelloWork",
        remote=is_remote,
        date_posted=date_posted,
    )


def _parse_date(text: str) -> date_type | None:
    if not text:
        return None
    text = text.strip()
    try:
        return date_type.fromisoformat(text[:10])
    except Exception:
        pass
    m = re.search(r"il y a (\d+)\s*jour", text.lower())
    if m:
        return (datetime.utcnow() - timedelta(days=int(m.group(1)))).date()
    m = re.search(r"il y a (\d+)\s*heure", text.lower())
    if m:
        return datetime.utcnow().date()
    if "aujourd" in text.lower():
        return datetime.utcnow().date()
    if "hier" in text.lower():
        return (datetime.utcnow() - timedelta(days=1)).date()
    return None
