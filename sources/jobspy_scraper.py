import pandas as pd
from typing import Iterator
from datetime import date
from notifier import Job

OFFICE_SEARCH_LOCATIONS = {
    "Montpellier": "Montpellier, France",
    "Lyon": "Lyon, France",
}
REMOTE_LOCATION = "France"


def fetch(
    keywords: list[str],
    office_locations: list[str],
    max_age_hours: int,
) -> Iterator[Job]:
    try:
        from jobspy import scrape_jobs
    except ImportError:
        print("[jobspy] not installed, skipping")
        return

    seen_ids: set[str] = set()

    for keyword in keywords:
        # Remote search: pass is_remote=True so LinkedIn filters for remote jobs only
        yield from _scrape(
            scrape_jobs, keyword, REMOTE_LOCATION, max_age_hours,
            seen_ids, is_remote_search=True,
        )
        # Office searches in target cities (no remote filter)
        for loc in office_locations:
            if loc in OFFICE_SEARCH_LOCATIONS:
                yield from _scrape(
                    scrape_jobs, keyword, OFFICE_SEARCH_LOCATIONS[loc], max_age_hours,
                    seen_ids, is_remote_search=False,
                )


def _scrape(
    scrape_jobs,
    keyword: str,
    location: str,
    max_age_hours: int,
    seen_ids: set,
    is_remote_search: bool,
) -> Iterator[Job]:
    try:
        kwargs = dict(
            site_name=["linkedin", "indeed"],
            search_term=keyword,
            location=location,
            results_wanted=50,
            hours_old=max_age_hours,
            country_indeed="France",
            linkedin_fetch_description=True,
            verbose=0,
        )
        if is_remote_search:
            kwargs["is_remote"] = True   # LinkedIn/Glassdoor remote-only filter

        df = scrape_jobs(**kwargs)
        if df is None or df.empty:
            return

        # Log per-site counts so we can see which sources return results
        if not df.empty:
            by_site = df.groupby("site").size().to_dict()
            label = "remote" if is_remote_search else location
            print(f"[jobspy] '{keyword}' ({label}): " +
                  ", ".join(f"{s}={n}" for s, n in sorted(by_site.items())))

        for _, row in df.iterrows():
            job_id = f"spy_{row.get('id', '')}_{row.get('site', '')}"
            if not row.get("id") or job_id in seen_ids:
                continue
            seen_ids.add(job_id)

            job_type = str(row.get("job_type", "")).lower()
            job_level = str(row.get("job_level") or "")

            # Detect remote from the actual job data — NOT from which search we ran.
            # "hybrid" is not remote: user only wants fully remote or office in target cities.
            raw_remote = row.get("is_remote")
            is_remote = (
                (raw_remote is True or str(raw_remote).lower() == "true")
                or "remote" in job_type
                or "télétravail" in job_type
            )

            location_str = _location_str(row)

            dp = row.get("date_posted")
            date_posted = None
            try:
                if dp is not None and not pd.isna(dp):
                    date_posted = dp.date() if hasattr(dp, "date") else (
                        dp if isinstance(dp, date) else None
                    )
            except Exception:
                pass

            raw_desc = row.get("description")
            description = str(raw_desc).strip() if raw_desc and str(raw_desc) not in ("nan", "None", "") else None

            yield Job(
                id=job_id,
                title=str(row.get("title", "")),
                company=str(row.get("company", "N/A")),
                location=location_str,
                url=str(row.get("job_url", "")),
                salary=_salary_str(row),
                source=str(row.get("site", "")).capitalize(),
                remote=is_remote,
                date_posted=date_posted,
                experience_level=job_level if job_level and job_level != "nan" else None,
                description=description,
            )
    except Exception as e:
        print(f"[jobspy] {keyword} @ {location}: {e}")


def _location_str(row) -> str:
    parts = [row.get("city"), row.get("state"), row.get("country")]
    result = ", ".join(str(p) for p in parts if p and str(p) not in ("nan", "None"))
    return result or "France"


def _salary_str(row) -> str | None:
    lo = row.get("min_amount")
    hi = row.get("max_amount")
    currency = row.get("currency", "€")
    interval = row.get("interval", "")
    if lo and hi:
        return f"{int(lo):,}–{int(hi):,} {currency}/{interval}"
    if lo:
        return f"From {int(lo):,} {currency}/{interval}"
    return None
