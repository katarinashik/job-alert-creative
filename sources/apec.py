"""
APEC scraper — placeholder (not yet implemented).

APEC is highly relevant for this profile: it targets "cadres" (managers, 3+ years),
which matches content manager / chef de projet / responsable digital roles exactly.

To implement: APEC's search page is a JS SPA — requires Playwright/Selenium or
reverse-engineering their internal GraphQL API. Candidates would come from:
  https://www.apec.fr/candidat/recherche-emploi.html/emploi

Until implemented, coverage comes from France Travail, LinkedIn/Indeed, and WTTJ.
"""
from typing import Iterator
from notifier import Job


def fetch(keywords, office_locations, max_age_hours) -> Iterator[Job]:
    return
    yield
