import requests
from datetime import datetime, timedelta, date
from typing import Iterator
from notifier import Job

TOKEN_URL = "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=%2Fpartenaire"
SEARCH_URL = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"
JOB_URL = "https://candidat.francetravail.fr/offres/recherche/detail/{id}"

MONTPELLIER_CODE = "34172"
LYON_CODE = "69381"
DISTANCE_KM = 30


def _ft_exp_label(libelle: str) -> str | None:
    """Convert France Travail experienceLibelle to a display label."""
    low = libelle.lower()
    if "débutant" in low:
        return "Junior (débutant accepté)"
    # "1 An(s)" → "1 an d'expérience", "3 An(s)" → "3 ans d'expérience"
    import re
    m = re.match(r"(\d+)\s*an", low)
    if m:
        n = int(m.group(1))
        s = "ans" if n > 1 else "an"
        return f"{n} {s} d'expérience"
    return libelle  # fallback: show raw text


def _get_token(client_id: str, client_secret: str) -> str:
    for scope in ("api_offresdemploiv2 o2dsoffre", "api_offresdemploiv2"):
        r = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": scope,
            },
            timeout=10,
        )
        if r.status_code == 200:
            print(f"[france_travail] auth OK with scope: {scope}")
            return r.json()["access_token"]
        print(f"[france_travail] scope '{scope}' failed: {r.status_code}")
    r.raise_for_status()
    return ""


def fetch(
    client_id: str,
    client_secret: str,
    keywords: list[str],
    office_locations: list[str],
    max_age_hours: int,
) -> Iterator[Job]:
    if not client_id or not client_secret:
        return

    try:
        token = _get_token(client_id, client_secret)
    except Exception as e:
        print(f"[france_travail] auth failed: {e}")
        return

    headers = {"Authorization": f"Bearer {token}"}
    now = datetime.utcnow()
    min_date = (now - timedelta(hours=max_age_hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
    max_date = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    commune_codes = []
    if "Montpellier" in office_locations:
        commune_codes.append(MONTPELLIER_CODE)
    if "Lyon" in office_locations:
        commune_codes.append(LYON_CODE)

    seen_ids: set[str] = set()

    for keyword in keywords:
        # remote anywhere in France — modesTravail=3 = télétravail complet
        params_remote = {
            "motsCles": keyword,
            "minCreationDate": min_date,
            "maxCreationDate": max_date,
            "modesTravail": "3",
            "range": "0-49",
        }
        yield from _query(headers, params_remote, seen_ids, remote=False)

        # office near Montpellier / Lyon
        for code in commune_codes:
            params_office = {
                "motsCles": keyword,
                "commune": code,
                "distance": DISTANCE_KM,
                "minCreationDate": min_date,
                "maxCreationDate": max_date,
                "range": "0-49",
            }
            yield from _query(headers, params_office, seen_ids, remote=False)


def _query(
    headers: dict, params: dict, seen_ids: set, remote: bool
) -> Iterator[Job]:
    try:
        r = requests.get(SEARCH_URL, headers=headers, params=params, timeout=15)
        if r.status_code == 204:
            return
        r.raise_for_status()

        results = r.json().get("resultats", [])
        if results:
            print(f"[france_travail] got {len(results)} results for '{params.get('motsCles')}'")

        for item in results:
            job_id = f"ft_{item['id']}"
            if job_id in seen_ids:
                continue
            seen_ids.add(job_id)

            salaire = item.get("salaire", {})
            salary_str = salaire.get("libelle") or None
            lieu = item.get("lieuTravail", {})
            location = lieu.get("libelle", "France")

            # Detect remote strictly from France Travail's own location code.
            # codePostal "00000" = France-wide / full télétravail in FT's system.
            # Any real city code (75xxx, 69xxx, etc.) = office or hybrid → NOT remote.
            # We can't trust description-based detection: FT data quality is poor
            # and "télétravail possible" (hybrid) slips through modesTravail=3 filter.
            loc_code = lieu.get("codePostal", "")
            loc_libelle = (lieu.get("libelle") or "").lower()
            is_remote = (
                loc_code == "00000"
                or "france entière" in loc_libelle
                or "france entiere" in loc_libelle
            )

            # parse date
            date_str = item.get("dateCreation", "")
            try:
                date_posted = date.fromisoformat(date_str[:10]) if date_str else None
            except ValueError:
                date_posted = None

            raw_desc = item.get("description", "")
            description = raw_desc.strip() if raw_desc and raw_desc.strip() else None

            # e.g. "Débutant accepté", "1 An(s)", "3 An(s)"
            exp_libelle = item.get("experienceLibelle", "").strip()
            experience_level = _ft_exp_label(exp_libelle) if exp_libelle else None

            yield Job(
                id=job_id,
                title=item.get("intitule", ""),
                company=item.get("entreprise", {}).get("nom", "N/A"),
                location=location,
                url=JOB_URL.format(id=item["id"]),
                salary=salary_str,
                source="France Travail",
                remote=is_remote,
                date_posted=date_posted,
                description=description,
                experience_level=experience_level,
            )
    except Exception as e:
        print(f"[france_travail] error: {e}")
