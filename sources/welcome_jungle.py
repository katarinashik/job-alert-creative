"""
Welcome to the Jungle scraper via Algolia internal API.
App ID and search-only key are embedded in window.env on the public site — no auth required.
The key is fetched fresh on every run so it never expires.
"""
import re
import json
import requests
from datetime import datetime, timedelta, date as date_type
from typing import Iterator
from notifier import Job

ALGOLIA_APP = "CSEKHVMS53"
INDEX = "wttj_jobs_production_fr"
ALGOLIA_URL = f"https://{ALGOLIA_APP}-dsn.algolia.net/1/indexes/{INDEX}/query"
JOB_URL = "https://www.welcometothejungle.com/fr/companies/{org_slug}/jobs/{slug}"

# Fallback key — updated manually if auto-fetch fails
_FALLBACK_KEY = "4bd8f6215d0cc52b26430765769e65a0"


def _fetch_algolia_key() -> str:
    """Fetch the current Algolia search key from the WTTJ homepage."""
    try:
        r = requests.get(
            "https://www.welcometothejungle.com/fr",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            timeout=15,
        )
        r.raise_for_status()
        html = r.text

        # Try window.env = {...}
        m = re.search(r'window\.env\s*=\s*(\{[^<]{20,3000}\})', html)
        if m:
            try:
                env = json.loads(m.group(1))
                for k in ("ALGOLIA_API_KEY", "ALGOLIA_SEARCH_KEY", "algoliaApiKey",
                          "algoliaSearchKey", "ALGOLIA_KEY"):
                    if k in env:
                        print(f"[wttj] fetched fresh Algolia key via window.env.{k}")
                        return env[k]
            except json.JSONDecodeError:
                pass

        # Try bare key pattern (32 hex chars) next to "algolia" context
        patterns = [
            r'"X-Algolia-API-Key"\s*:\s*"([a-f0-9]{32})"',
            r'algoliaApiKey["\s:]+([a-f0-9]{32})',
            r'algolia[^"]{0,40}"([a-f0-9]{32})"',
            r'searchKey["\s:]+([a-f0-9]{32})',
        ]
        for pat in patterns:
            m = re.search(pat, html, re.IGNORECASE)
            if m:
                print(f"[wttj] fetched fresh Algolia key via pattern")
                return m.group(1)

    except Exception as e:
        print(f"[wttj] could not fetch fresh key: {e}")

    print("[wttj] using fallback Algolia key")
    return _FALLBACK_KEY


def fetch(
    keywords: list[str],
    office_locations: list[str],
    max_age_hours: int,
) -> Iterator[Job]:
    algolia_key = _fetch_algolia_key()

    # Validate key works before running all keywords
    try:
        test = requests.post(
            ALGOLIA_URL,
            json={"query": "analyst", "hitsPerPage": 1},
            headers={
                "X-Algolia-Application-Id": ALGOLIA_APP,
                "X-Algolia-API-Key": algolia_key,
                "Referer": "https://www.welcometothejungle.com/",
                "Origin": "https://www.welcometothejungle.com",
            },
            timeout=10,
        )
        if test.status_code == 403:
            print("[wttj] key invalid (403) — skipping WTTJ this run")
            return
    except Exception:
        pass

    cutoff = int((datetime.utcnow() - timedelta(hours=max_age_hours)).timestamp())
    seen_ids: set[str] = set()
    headers = {
        "X-Algolia-Application-Id": ALGOLIA_APP,
        "X-Algolia-API-Key": algolia_key,
        "Referer": "https://www.welcometothejungle.com/",
        "Origin": "https://www.welcometothejungle.com",
    }

    for keyword in keywords:
        # Remote jobs anywhere (fulltime or hybrid)
        yield from _query(
            keyword, cutoff, seen_ids, headers,
            extra_filters="(remote:fulltime OR remote:hybrid)",
            is_remote=True,
        )

        # Office jobs in target cities
        for loc in office_locations:
            yield from _query(
                keyword, cutoff, seen_ids, headers,
                facet_filters=[f"offices.city:{loc}"],
                is_remote=False,
            )


def _query(
    keyword: str,
    cutoff: int,
    seen_ids: set,
    headers: dict,
    extra_filters: str = "",
    facet_filters: list = None,
    is_remote: bool = False,
) -> Iterator[Job]:
    base_filter = f"published_at_timestamp > {cutoff}"
    filters = f"{base_filter} AND {extra_filters}" if extra_filters else base_filter

    params = {
        "query": keyword,
        "hitsPerPage": 50,
        "filters": filters,
    }
    if facet_filters:
        params["facetFilters"] = [facet_filters]

    try:
        r = requests.post(ALGOLIA_URL, json=params, headers=headers, timeout=15)
        r.raise_for_status()
        hits = r.json().get("hits", [])

        label = "remote" if is_remote else (facet_filters[0].split(":")[1] if facet_filters else "")
        if hits:
            print(f"[wttj] {len(hits)} results for '{keyword}' ({label})")

        for hit in hits:
            job_id = f"wttj_{hit.get('objectID', '')}"
            if job_id in seen_ids:
                continue
            seen_ids.add(job_id)

            org = hit.get("organization", {})
            org_slug = org.get("slug", "")
            slug = hit.get("slug", "")
            url = JOB_URL.format(org_slug=org_slug, slug=slug)

            offices = hit.get("offices", [])
            if offices:
                o = offices[0]
                parts = [o.get("city"), o.get("state"), o.get("country")]
                location = ", ".join(p for p in parts if p)
            else:
                location = "France"

            date_str = hit.get("published_at", "")
            try:
                date_posted = date_type.fromisoformat(date_str[:10]) if date_str else None
            except ValueError:
                date_posted = None

            sal_min = hit.get("salary_minimum")
            sal_max = hit.get("salary_maximum")
            sal_currency = hit.get("salary_currency", "EUR")
            sal_period = hit.get("salary_period", "")
            salary = None
            if sal_min and sal_max and sal_min != sal_max:
                salary = f"{int(sal_min):,}–{int(sal_max):,} {sal_currency}/{sal_period}"
            elif sal_min:
                salary = f"From {int(sal_min):,} {sal_currency}/{sal_period}"

            exp = hit.get("experience_level_minimum")
            exp_label = None
            if exp is not None:
                if exp == 0:
                    exp_label = "Junior (0-2 ans)"
                elif exp == 1:
                    exp_label = "1-3 ans d'expérience"
                elif exp == 2:
                    exp_label = "2-4 ans d'expérience"
                elif exp == 3:
                    exp_label = "3-5 ans d'expérience"
                elif exp >= 5:
                    exp_label = f"{exp}+ ans d'expérience"

            # Company size — WTTJ returns several possible field names
            size_raw = (org.get("nb_employees_range") or org.get("size") or
                        org.get("nb_employees") or "")
            company_size = str(size_raw).strip() if size_raw else None
            if company_size and not any(c.isdigit() for c in company_size):
                company_size = None  # drop non-informative labels

            yield Job(
                id=job_id,
                title=hit.get("name", ""),
                company=org.get("name", "N/A"),
                location=location,
                url=url,
                salary=salary,
                source="Welcome to the Jungle",
                remote=is_remote or hit.get("has_remote", False),
                date_posted=date_posted,
                experience_level=exp_label,
                company_size=company_size,
            )
    except Exception as e:
        print(f"[wttj] error for '{keyword}': {e}")
