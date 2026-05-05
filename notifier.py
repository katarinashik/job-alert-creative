import requests
from dataclasses import dataclass
from typing import Optional
from datetime import date

MONTHS_FR = ["jan.", "fév.", "mar.", "avr.", "mai", "juin",
             "juil.", "août", "sep.", "oct.", "nov.", "déc."]


@dataclass
class Job:
    id: str
    title: str
    company: str
    location: str
    url: str
    salary: Optional[str] = None
    source: str = ""
    remote: bool = False
    date_posted: Optional[date] = None
    experience_level: Optional[str] = None
    description: Optional[str] = None
    company_size: Optional[str] = None


# Creative / digital tool patterns — longer/more specific patterns first
SKILL_PATTERNS = [
    ("meta business suite",  "Meta Business"),
    ("adobe premiere",       "Premiere Pro"),
    ("premiere pro",         "Premiere Pro"),
    ("after effects",        "After Effects"),
    ("final cut",            "Final Cut"),
    ("davinci resolve",      "DaVinci"),
    ("google analytics",     "Google Analytics"),
    ("google ads",           "Google Ads"),
    ("adobe photoshop",      "Photoshop"),
    ("adobe illustrator",    "Illustrator"),
    ("adobe indesign",       "InDesign"),
    ("adobe creative",       "Adobe CC"),
    (" semrush ",            "SEMrush"),
    (" ahrefs ",             "Ahrefs"),
    (" hubspot ",            "HubSpot"),
    (" hootsuite ",          "Hootsuite"),
    (" buffer ",             "Buffer"),
    (" sprout ",             "Sprout"),
    (" notion ",             "Notion"),
    (" asana ",              "Asana"),
    (" monday ",             "Monday"),
    (" clickup ",            "ClickUp"),
    (" trello ",             "Trello"),
    (" jira ",               "Jira"),
    (" slack ",              "Slack"),
    (" tiktok ",             "TikTok"),
    (" instagram ",          "Instagram"),
    (" youtube ",            "YouTube"),
    (" canva ",              "Canva"),
    (" figma ",              "Figma"),
    (" wordpress ",          "WordPress"),
    (" salesforce ",         "Salesforce"),
    (" excel ",              "Excel"),
    (" powerpoint ",         "PowerPoint"),
]


def extract_skills(description: str) -> list[str]:
    if not description:
        return []
    import re
    clean = re.sub(r"[^\w\s]", " ", description.lower())
    padded = f" {clean} "
    seen: set[str] = set()
    found: list[str] = []
    for pattern, display in SKILL_PATTERNS:
        if display in seen:
            continue
        if pattern in padded:
            seen.add(display)
            found.append(display)
        if len(found) >= 7:
            break
    return [s for s in found if not any(s != o and s in o for o in found)]


def _stars(job_score: int) -> str:
    if job_score <= 0:
        return ""
    if job_score == 1:
        return "⭐ "
    if job_score == 2:
        return "⭐⭐ "
    return "⭐⭐⭐ "


def send(token: str, chat_id: str, job: Job, job_score: int = 0) -> None:
    stars = _stars(job_score)
    company_line = f"🏢 {_esc(job.company)}"
    if job.company_size:
        company_line += f"  👥 {_esc(job.company_size)}"
    lines = [f"{stars}*{_esc(job.title)}*", company_line]

    if job.location:
        lines.append(f"📍 {_esc(job.location)}")
    if job.remote:
        lines.append("🌍 Remote / Télétravail")

    if job.experience_level:
        lines.append(f"👤 {_esc(job.experience_level)}")

    if job.salary:
        lines.append(f"💰 {_esc(job.salary)}")

    skills = extract_skills(job.description or "")
    if skills:
        lines.append(f"🛠 {' · '.join(skills)}")

    if job.date_posted:
        d = job.date_posted
        lines.append(f"📅 {d.day} {MONTHS_FR[d.month - 1]} {d.year}")

    if job.source:
        lines.append(f"📌 {job.source}")

    lines.append(f"🔗 [Voir l'offre]({job.url})")

    text = "\n".join(lines)

    keyboard = {
        "inline_keyboard": [[
            {"text": "✅ Postulée",     "callback_data": f"applied|{job.id}"},
            {"text": "💾 Sauvegarder", "callback_data": f"save|{job.id}"},
            {"text": "❌ Ignorer",      "callback_data": f"ignore|{job.id}"},
        ]]
    }

    requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
            "reply_markup": keyboard,
        },
        timeout=10,
    ).raise_for_status()


def _esc(text: str) -> str:
    for ch in r"_*[]()~`>#+-=|{}.!":
        text = text.replace(ch, f"\\{ch}")
    return text
