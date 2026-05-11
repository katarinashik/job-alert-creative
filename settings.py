SEARCH_KEYWORDS = [
    # VIDEO EDITOR / MONTAGE
    "monteur vidéo",
    "video editor",
    "montage vidéo",
    "chef montage",
    "responsable montage",
    # MOTION DESIGN
    "motion designer",
    "motion design",
    "graphiste motion",
    # HEAD OF VIDEO / PRODUCTION
    "head of video",
    "responsable vidéo",
    "responsable production vidéo",
    "video production manager",
    "video production lead",
    "post-production manager",
    "responsable post-production",
    "post-production supervisor",
    # CREATIVE PROJECT MANAGER (studio / video)
    "chef de projet vidéo",
    "chef de projet video",
    "chef de projet créatif",
    "creative project manager",
    "creative studio manager",
    # SOCIAL MEDIA WITH VIDEO FOCUS
    "social media manager video",
    "social media video",
    "content creator video",
    "créateur de contenu vidéo",
    # PLATFORM-SPECIFIC
    "youtube manager",
    "tiktok manager",
    "short form content",
    "short-form content",
    "responsable contenu vidéo",
    # BROADER (caught by video signal filter)
    "social media manager",
    "community manager",
    "content manager",
]

OFFICE_LOCATIONS = ["Montpellier", "Lyon"]

MAX_JOB_AGE_HOURS = 6

BLOCKED_COMPANIES = [
    "prolific",
    "peaktew",
    "scale ai",
]

BLOCKED_DESCRIPTION_PHRASES = [
    "after 27 applicants",
    "after 27 candidatures",
    "automatically closing after 27",
    "closes after 27",
    "closing after 27",
    "submit your cv for consideration",
]

# Block contract types, intérim, and C-level
BLOCKED_TITLE_WORDS = [
    # Contract types (FR + EN)
    "stage", "stagiaire",
    "alternance", "alternant", "alternante",
    "apprentissage", "apprenti", "apprentie",
    "apprenticeship", "apprentice",
    "internship", "intern",
    "intérim", "interim", "interimaire", "intérimaire",
    # Too junior
    "junior",
    "débutant", "debutant",
    # Too senior
    "director", "directeur", "directrice",
    "vp",
    "c-level",
]

# Group A — role type
GROUP_A_WORDS = [
    " manager ", " responsable ", " chef ", " chargé ", " chargée ",
    " coordinateur ", " coordinatrice ", " coordinator ",
    " producer ", " producteur ", " productrice ",
    " superviseur ", " supervisor ",
    " head ", " project ", " projet ",
    " editor ", " éditeur ", " editeur ", " monteur ", " monteuse ",
    " créateur ", " créatrice ",
    " operations ", " opérations ",
    " production ",
    " designer ",
]

# Group B — domain
GROUP_B_WORDS = [
    " video ", " vidéo ",
    " motion ",
    " content ", " contenu ",
    " digital ", " social ",
    " media ", " médias ", " medias ",
    " community ", " brand ",
    " creative ", " créatif ", " créative ",
    " campaign ", " campagne ",
    "post-production",
    "réseaux sociaux", "reseaux sociaux",
    " youtube ", " tiktok ",
    " montage ", " studio ",
]

# Special PM rule
PM_INDICATORS = ["project manager", "chef de projet"]
PM_DOMAIN_WORDS = [
    " video ", " vidéo ", " motion ", " creative ", " créatif ",
    " content ", " contenu ", " media ", " studio ",
    " social ", " brand ", " digital ",
]

# ── VIDEO SIGNAL FILTER ──────────────────────────────────────────────────────
# At least one of these must appear in title OR description.
# Blocks community managers, content marketers, SEO etc. without video focus.
VIDEO_SIGNAL_TERMS = [
    "montage", "monteur", "monteuse",
    "video editor", "video editing",
    "motion design", "motion designer",
    "after effects", "premiere pro", "davinci", "final cut",
    "post-production", "post production",
    "production vidéo", "video production",
    "short-form", "short form",
    "youtube", "tiktok", "reels",
    "head of video", "responsable vidéo",
    "creative studio",
    "vidéo",
]

# ── EXCLUDED JOB TYPES ───────────────────────────────────────────────────────
# Blocked if these appear in title (pure non-video roles)
BLOCKED_ROLE_KEYWORDS = [
    "seo", "sea", "sem",
    "copywriter", "copywriting",
    "rédacteur", "rédactrice", "rédaction",
    "b2b saas", "field marketing", "marketing enterprise",
    "account manager", "account executive",
    "growth hacker",
]

# ── SCORE BOOST ─────────────────────────────────────────────────────────────
SCORE_BOOST_TERMS = [
    "montage", "monteur", "video editor",
    "motion design", "after effects", "premiere pro", "davinci",
    "post-production", "production vidéo",
    "short-form", "short form", "vertical video",
    "youtube", "tiktok", "reels", "instagram",
    "head of video", "creative studio",
    "vidéo", "workflow", "pipeline",
    "kpi", "analytics", "audience", "reach", "engagement",
    "notion", "asana", "monday", "frame.io", "airtable",
]

# +2 for profile-matched companies
PREFERRED_COMPANIES = [
    "webedia", "dailymotion", "brut", "konbini",
    "humanoid", "reworld media", "reworld",
    "jellysmack", "biomerieux", "bioxmerieux",
    "euronews", "orange",
    "gl events", "seb group",
    "artefact", "capgemini",
    "doctolib", "swile", "partoo",
]

# Blocked domains (title + description)
BLOCKED_DOMAIN_KEYWORDS = [
    "monétique", "monetique",
    " iard ",
    "aéronautique", "aeronautique",
    "t2s ", "target2",
    "juridique", "notariat",
    "immobilier",
    "assurance vie",
    "pharmacie clinique",
    "supply chain industrielle",
    "génie civil", "genie civil",
    " btp ",
]

BLOCKED_LOCATION_KEYWORDS = [
    "luxembourg",
    "niort",
    "bartenheim",
    "chaumont",
    "limoges",
]

# Minimum annual salary (if stated) — 35k for video roles
MIN_SALARY_EUR = 35_000
