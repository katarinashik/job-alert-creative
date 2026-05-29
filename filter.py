import re
import hashlib
import settings
import storage
from notifier import Job

MIN_DESCRIPTION_LENGTH = 200

# Signals that a job is actually located in Paris/IDF (not truly remote)
_PARIS_SIGNALS = [
    " paris ", "paris,", "paris\n", "(paris)", "paris 1", "paris 2",
    "paris 3", "paris 4", "paris 5", "paris 6", "paris 7", "paris 8",
    "paris 9", "paris 10", "paris 11", "paris 12", "paris 13",
    "paris 14", "paris 15", "paris 16", "paris 17", "paris 18",
    "paris 19", "paris 20",
    "75001", "75002", "75003", "75004", "75005", "75006", "75007",
    "75008", "75009", "75010", "75011", "75012", "75013", "75014",
    "75015", "75016", "75017", "75018", "75019", "75020",
    "île-de-france", "ile-de-france", "idf",
    "levallois", "boulogne-billancourt", "neuilly-sur-seine",
    "la défense", "la defense",
]

# Signals that override: job is genuinely fully remote
_FULL_REMOTE_SIGNALS = [
    "100% remote", "100% télétravail", "full remote", "fully remote",
    "télétravail complet", "full télétravail", "remote first",
    "remote-first", "remote only", "entièrement en télétravail",
    "100 % télétravail", "poste 100%",
]


def _is_paris_only(job: Job) -> bool:
    """
    True when a job claims remote but description/location strongly indicate
    it's actually a Paris-area office role (LinkedIn often mislabels these).
    """
    loc = (job.location or "").lower()

    # Location field itself says Paris and NOT our target cities
    if "paris" in loc and not any(c.lower() in loc for c in settings.OFFICE_LOCATIONS):
        return True

    desc = (job.description or "").lower()
    if not desc:
        return False

    # Explicit full-remote language overrides any Paris mention
    if any(sig in desc for sig in _FULL_REMOTE_SIGNALS):
        return False

    # Check the first 400 chars (job header) where location is usually listed
    header = desc[:400]
    return any(sig in header for sig in _PARIS_SIGNALS)


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

    # Block pure non-video roles (SEO, copywriting, B2B SaaS, etc.)
    for kw in settings.BLOCKED_ROLE_KEYWORDS:
        if kw in t:
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


def has_video_signal(job: Job) -> bool:
    """
    Returns True if:
    - Title contains 'content' / 'contenu' (all content roles pass without video requirement)
    - OR title/description contains at least one video-specific term
    """
    title = job.title.lower()
    # All "content X" roles pass regardless of video signal
    if "content" in title or "contenu" in title:
        return True
    combined = f"{title} {(job.description or '').lower()}"
    return any(term in combined for term in settings.VIDEO_SIGNAL_TERMS)


def is_valid_location(job: Job) -> bool:
    loc = (job.location or "").lower()

    for blocked in settings.BLOCKED_LOCATION_KEYWORDS:
        if blocked in loc:
            return False

    if job.remote:
        # LinkedIn/jobspy is_remote flag is unreliable — cross-check description
        if _is_paris_only(job):
            return False
        return True
    if any(city.lower() in loc for city in settings.OFFICE_LOCATIONS):
        return True
    if loc in ("france", ""):
        text = f"{job.title or ''} {job.description or ''}".lower()
        return any(city.lower() in text for city in settings.OFFICE_LOCATIONS)
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
