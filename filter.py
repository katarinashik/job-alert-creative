import re
import hashlib
import settings
import storage
from notifier import Job

MIN_DESCRIPTION_LENGTH = 200


def is_relevant(title: str, company: str) -> bool:
    t = title.lower()
    c = company.lower()
    padded = f" {t} "

    for blocked in settings.BLOCKED_COMPANIES:
        if blocked in c:
            return False

    for word in settings.BLOCKED_TITLE_WORDS:
        if re.search(rf"\b{re.escape(word.strip())}\b", t):
            return False

    has_role = any(w in padded for w in settings.GROUP_A_WORDS)
    has_domain = any(w in padded for w in settings.GROUP_B_WORDS)

    if not (has_role and has_domain):
        return False

    # Special rule: project manager / chef de projet requires a specific domain qualifier
    if any(pm in padded for pm in settings.PM_INDICATORS):
        if not any(d in padded for d in settings.PM_DOMAIN_WORDS):
            return False

    return True


def is_valid_location(job: Job) -> bool:
    loc = (job.location or "").lower()

    for blocked in settings.BLOCKED_LOCATION_KEYWORDS:
        if blocked in loc:
            return False

    if job.remote:
        return True
    if any(city.lower() in loc for city in settings.OFFICE_LOCATIONS):
        return True
    if loc in ("france", ""):
        title = (job.title or "").lower()
        return any(city.lower() in title for city in settings.OFFICE_LOCATIONS)
    return False


def _extract_max_salary(salary_str: str) -> int | None:
    """Return max annual salary in EUR, or None if unparseable."""
    if not salary_str:
        return None
    s = salary_str.lower().replace(" ", " ")

    is_monthly = bool(re.search(r"mensuel|monthly|par mois|/month\b|/mois\b", s))
    is_hourly = bool(re.search(r"horaire|hourly|/hour\b|/hr\b", s))

    # "sur 13 mois" — France Travail sometimes pays 13th month
    months = 12
    m = re.search(r"sur\s+(\d+)\s*mois", s)
    if m:
        months = int(m.group(1))

    values: list[int] = []

    # k-suffix: "38k", "42.5k"
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*k\b", s):
        values.append(int(float(m.group(1)) * 1000))

    if not values:
        # Remove decimal thousand-separators: "38.000" or "38,000" → "38000"
        s_clean = re.sub(r"(\d)[.,](\d{3})(?!\d)", r"\1\2", s)
        for m in re.finditer(r"\b(\d{4,6})\b", s_clean):
            v = int(m.group(1))
            if 1_000 <= v <= 500_000:
                values.append(v)

    if not values:
        return None

    max_v = max(values)

    if is_hourly:
        max_v = max_v * 35 * 52  # ~35h × 52 weeks
    elif is_monthly:
        max_v = max_v * months

    return max_v


def is_valid_salary(job: Job) -> bool:
    """Show if: no salary stated OR max annual salary >= MIN_SALARY_EUR."""
    if not job.salary:
        return True
    max_salary = _extract_max_salary(job.salary)
    if max_salary is None:
        return True  # can't parse → show rather than wrongly block
    return max_salary >= settings.MIN_SALARY_EUR


def is_valid_domain(job: Job) -> bool:
    combined = f"{job.title} {job.description or ''}".lower()
    for kw in settings.BLOCKED_DOMAIN_KEYWORDS:
        if kw in combined:
            return False
    return True


def is_valid_description(job: Job, seen_hashes: set) -> bool:
    desc = job.description
    if desc is None:
        return True
    desc_clean = desc.strip()
    if not desc_clean:
        return True
    if len(desc_clean) < MIN_DESCRIPTION_LENGTH:
        return False

    desc_lower = desc_clean.lower()
    for phrase in settings.BLOCKED_DESCRIPTION_PHRASES:
        if phrase in desc_lower:
            return False

    snippet = " ".join(desc_clean[:500].lower().split())
    h = hashlib.md5(snippet.encode()).hexdigest()

    if h in seen_hashes:
        return False
    seen_hashes.add(h)

    if storage.is_desc_hash_seen(h):
        return False
    storage.add_desc_hash(h)

    return True


def score(title: str, company: str = "") -> int:
    t = title.lower()
    c = company.lower()
    s = sum(1 for term in settings.SCORE_BOOST_TERMS if term in t)
    if any(pref in c for pref in settings.PREFERRED_COMPANIES):
        s += 2
    return s
