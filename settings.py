SEARCH_KEYWORDS = [
    # CONTENT / SOCIAL MEDIA
    "content manager",
    "content strategist",
    "social media manager",
    "social media strategist",
    "community manager",
    "brand content manager",
    "digital content manager",
    "head of content",
    "responsable contenu",
    "chargé de contenu",
    "chargée de contenu",
    "chargé des réseaux sociaux",
    "responsable réseaux sociaux",
    # CHEF DE PROJET / PROJECT MANAGER (domain-qualified only)
    "chef de projet digital",
    "chef de projet contenu",
    "chef de projet marketing",
    "chef de projet médias",
    "chef de projet communication",
    "chef de projet créatif",
    "project manager digital",
    "project manager content",
    "project manager media",
    "project manager marketing",
    "project manager creative",
    "project manager social media",
    # OPERATIONS
    "content operations manager",
    "operations manager digital",
    "responsable opérations digitales",
    "media operations manager",
    "post-production manager",
    "production manager digital",
    "workflow manager",
    "responsable production digitale",
    # VIDEO / POST-PRODUCTION
    "responsable post-production",
    "post-production supervisor",
    "video production manager",
    # MARKETING DIGITAL
    "digital marketing manager",
    "chargé de marketing digital",
    "responsable marketing digital",
    "growth manager",
    "traffic manager",
    "performance marketing manager",
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

# Block contract types and out-of-range seniority levels
BLOCKED_TITLE_WORDS = [
    # Contract types to ignore (French + English)
    "stage", "stagiaire",
    "alternance", "alternant", "alternante",
    "apprentissage", "apprenti", "apprentie",
    "apprenticeship", "apprentice",
    "internship", "intern",
    # Too junior
    "junior",
    "débutant", "debutant",
    # Too senior (C-level / director)
    "director", "directeur", "directrice",
    "vp",
    "c-level",
]

# Group A — role type (title must contain at least one, space-padded for word boundary)
GROUP_A_WORDS = [
    " manager ", " responsable ", " chef ", " chargé ", " chargée ",
    " coordinateur ", " coordinatrice ", " coordinator ",
    " producer ", " producteur ", " productrice ",
    " superviseur ", " supervisor ",
    " head ", " project ", " projet ",
    " editor ", " éditeur ", " editeur ",
    " operations ", " opérations ",
    " production ",
]

# Group B — domain (title must contain at least one, space-padded)
GROUP_B_WORDS = [
    " content ", " contenu ",
    " digital ", " social ",
    " media ", " médias ", " medias ",
    " marketing ", " community ", " brand ",
    " editorial ", " éditorial ",
    " video ", " vidéo ",
    " workflow ", " creative ", " créatif ", " créative ",
    " campaign ", " campagne ",
    "post-production",
    "réseaux sociaux", "reseaux sociaux",
]

# Special rule: if "project manager" or "chef de projet" in title,
# these domain words are required (stricter than GROUP_B)
PM_INDICATORS = ["project manager", "chef de projet"]
PM_DOMAIN_WORDS = [
    " digital ", " content ", " contenu ",
    " media ", " médias ", " medias ",
    " marketing ", " creative ", " créatif ", " créative ",
    " social ", " brand ", " communication ",
]

# Score boost: +1 per matching term in description
SCORE_BOOST_TERMS = [
    "content", "contenu", "social media", "réseaux sociaux",
    "digital", "marketing", "video", "vidéo", "montage",
    "workflow", "operations", "opérations", "kpi",
    "analytics", "performance", "engagement", "reach",
    "community", "brand", "editorial", "éditorial",
    "production", "post-production", "creator", "créateur",
    "notion", "slack", "monday", "asana", "meta", "instagram",
    "youtube", "tiktok", "facebook", "ab test", "a/b test",
    "dashboard", "reporting", "audience", "retention",
    "strategy", "stratégie", "campaign", "campagne",
]

# +2 bonus for profile-matched companies (bypass no filters)
PREFERRED_COMPANIES = [
    "webedia", "dailymotion", "brut", "konbini",
    "humanoid", "reworld media", "reworld",
    "cegid", "agicap",
    "cdiscount", "fnac darty", "fnac",
    "gl events", "seb group", " seb ",
    "euronews",
    "doctolib", "payfit", "swile",
    "partoo", "livestorm",
    "orange",
    "capgemini",
    "jellysmack", "biomerieux", "bioxmerieux",
    "artefact",
]

# Blocked irrelevant domains (checked in title + description)
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

# Rejected cities (even for "remote" — different jurisdiction or too far)
BLOCKED_LOCATION_KEYWORDS = [
    "luxembourg",
    "niort",
    "bartenheim",
    "chaumont",
    "limoges",
]

# Minimum annual salary to show (if salary is specified)
MIN_SALARY_EUR = 39_000
