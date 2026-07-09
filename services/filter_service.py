import re
from urllib.parse import unquote
from urllib.parse import urlparse

from keywords import keywords, locations


BAD_TITLES = [
    "see full role description",
    "products",
    "accessibility",
    "privacy",
    "contact us",
    "instagram",
    "application status",
    "sustainability",
    "united states",
    "standards of business conduct",
    "israel",
]


JOB_URL_HINTS = [
    "/job/",
    "/jobs/",
    "/careers/job",
    "/details/",
    "jobid",
    "job_id",
    "job-",
    "jobdetails?jobseqno",
    "jobs/results/",
]


POSSIBLE_JOB_TEXT_HINTS = [
    "engineer",
    "developer",
    "architect",
    "manager",
    "lead",
    "specialist",
    "intern",
    "student",
    "researcher",
    "software",
    "hardware",
    "silicon",
    "verification",
    "validation",
    "embedded",
    "fpga",
    "asic",
    "rtl",
    "physical design",
    "board",
]


BAD_URL_PARTS = [
    "instagram.com",
    "facebook.com",
    "linkedin.com",
    "youtube.com",
    "mailto:",
    "/profile/",
    "/login",
    "choose-country-region",
    "/products/",
    "/support/",
    "/training/",
    "/solutions/",
    "/applications/",
    "/sustainability",
    "/environmental-social",
    "/corporate-responsibility",
    "privacy-job-candidates",
]


STRONG_KEYWORDS = {
    "asic",
    "vlsi",
    "rtl",
    "fpga",
    "uvm",
    "systemverilog",
    "verilog",
    "physical design",
    "design verification",
    "board design",
    "pcb",
    "rf",
    "radio frequency",
    "signal integrity",
    "power integrity",
    "sta",
    "timing",
    "place and route",
    "floorplanning",
}


MEDIUM_KEYWORDS = {
    "firmware",
    "embedded",
    "dsp",
    "electrical engineer",
    "electronic",
    "verification",
    "×—×•×ž×¨×”",
    "×§×•×©×—×”",
    "××œ×§×˜×¨×•× ×™×§×”",
    "×”× ×“×¡×ª ×—×©×ž×œ",
    "×•×¨×™×¤×™×§×¦×™×”",
    "××™×ž×•×ª",
}


WEAK_KEYWORDS = {
    "hardware",
    "hw",
    "system integration",
    "integration engineer",
    "system engineer",
    "optical",
    "physicist",
}


TITLE_KEYWORD_SCORES = {
    "strong": 50,
    "medium": 35,
    "weak": 20,
}


TITLE_KEYWORD_OVERRIDES = {
    "hardware": 25,
    "hw": 25,
}


BODY_KEYWORD_SCORES = {
    "strong": 35,
    "medium": 20,
    "weak": 10,
}


NEGATIVE_TITLE_TERMS = {
    "accountant",
    "business development",
    "buyer",
    "customer success",
    "finance",
    "frontend",
    "hr",
    "human resources",
    "legal",
    "marketing",
    "operator",
    "planner",
    "procurement",
    "product manager",
    "program manager",
    "project manager",
    "recruiter",
    "sales",
    "supplier quality",
    "warehouse",
}


NEGATIVE_BODY_TERMS = {
    "business development",
    "customer success",
    "finance",
    "frontend",
    "human resources",
    "legal",
    "marketing",
    "procurement",
    "sales",
}


LOW_CONFIDENCE_THRESHOLD = 50
HIGH_CONFIDENCE_THRESHOLD = 75


def is_bad_title(title: str) -> bool:
    title_lower = title.lower()
    return any(bad == title_lower for bad in BAD_TITLES)


def is_bad_url(url: str) -> bool:
    url_lower = url.lower()
    if url_lower.endswith(".pdf"):
        return True

    if "/about/careers/applications/jobs/results/" in url_lower:
        return False

    return any(bad in url_lower for bad in BAD_URL_PARTS)


def is_job_url(url: str) -> bool:
    url_lower = url.lower()
    parsed_url = urlparse(url_lower)

    if parsed_url.netloc.endswith("dejobs.org"):
        return parsed_url.path.endswith("/job/")

    if parsed_url.netloc.endswith("workdayjobs.com"):
        return "/job/" in parsed_url.path

    if "/about/careers/applications/jobs/results/" in parsed_url.path:
        return not parsed_url.path.rstrip("/").endswith("/jobs/results")

    if "/careers/co/" in parsed_url.path:
        path_parts = [
            part
            for part in parsed_url.path.split("/")
            if part
        ]
        return len(path_parts) >= 6

    return any(hint in url_lower for hint in JOB_URL_HINTS)


def is_job_list_url(url: str) -> bool:
    parsed_url = urlparse(url.lower())

    return parsed_url.netloc.endswith("workdayjobs.com")


def is_possible_job_link(title: str, url: str) -> bool:
    text = f"{title} {url}".lower()
    return any(hint in text for hint in POSSIBLE_JOB_TEXT_HINTS)


def is_identifier_title(title: str) -> bool:
    compact_title = title.replace("-", "").replace(" ", "")

    if len(compact_title) < 16:
        return False

    return all(character in "0123456789abcdefABCDEF" for character in compact_title)


def get_title_from_url(url: str) -> str:
    path = urlparse(url).path.rstrip("/")
    path_parts = path.split("/")
    slug = unquote(path_parts[-1])

    if not slug:
        return ""

    if is_identifier_title(slug) and len(path_parts) > 1:
        slug = unquote(path_parts[-2])

    parts = slug.split("-", 1)
    if parts[0].isdigit() and len(parts) > 1:
        slug = parts[1]

    return slug.replace("-", " ").strip().title()


def clean_link_title(title: str) -> str:
    lines = [
        line.strip()
        for line in title.splitlines()
        if line.strip()
    ]

    if not lines:
        return ""

    return lines[0]


def keyword_matches(keyword: str, text: str) -> bool:
    pattern = r"\b" + re.escape(keyword.lower()) + r"\b"
    return re.search(pattern, text.lower()) is not None


def location_matches(location: str, text: str) -> bool:
    pattern = r"\b" + re.escape(location.lower()) + r"\b"
    return re.search(pattern, text.lower()) is not None


def find_matching_keyword(text: str) -> str | None:
    matches = get_keyword_matches(text)
    if matches:
        return matches[0]["keyword"]

    return None


def get_keyword_strength(keyword: str) -> str:
    keyword_lower = keyword.lower()

    if keyword_lower in STRONG_KEYWORDS:
        return "strong"

    if keyword_lower in MEDIUM_KEYWORDS:
        return "medium"

    return "weak"


def get_keyword_matches(text: str) -> list[dict]:
    matches = []

    for index, keyword in enumerate(keywords):
        if keyword_matches(keyword, text):
            strength = get_keyword_strength(keyword)
            score = TITLE_KEYWORD_OVERRIDES.get(
                keyword.lower(),
                TITLE_KEYWORD_SCORES[strength],
            )
            matches.append(
                {
                    "keyword": keyword,
                    "strength": strength,
                    "score": score,
                    "index": index,
                }
            )

    return sorted(
        matches,
        key=lambda match: (
            match["score"],
            len(match["keyword"]) if match["strength"] != "weak" else -match["index"],
        ),
        reverse=True,
    )


def has_term_match(term: str, text: str) -> bool:
    pattern = r"\b" + re.escape(term.lower()) + r"\b"
    return re.search(pattern, text.lower()) is not None


def get_negative_score(title: str, body: str) -> int:
    score = 0

    if any(has_term_match(term, title) for term in NEGATIVE_TITLE_TERMS):
        score -= 60

    if any(has_term_match(term, body) for term in NEGATIVE_BODY_TERMS):
        score -= 20

    return score


def get_location_score(matched_location: str | None) -> int:
    if not matched_location:
        return 0

    if matched_location.strip().lower() == "israel":
        return 15

    return 25


def get_match_confidence(score: int) -> str:
    if score >= HIGH_CONFIDENCE_THRESHOLD:
        return "high"

    if score >= LOW_CONFIDENCE_THRESHOLD:
        return "medium"

    return "low"


def evaluate_job_relevance(
    title: str,
    body: str,
    matched_location: str | None,
) -> dict | None:
    title_matches = get_keyword_matches(title)
    body_matches = get_keyword_matches(body)
    title_keywords = {match["keyword"] for match in title_matches}

    title_score = min(
        sum(match["score"] for match in title_matches),
        70,
    )
    body_score = min(
        sum(
            BODY_KEYWORD_SCORES[match["strength"]]
            for match in body_matches
            if match["keyword"] not in title_keywords
        ),
        35,
    )
    score = (
        title_score
        + body_score
        + get_location_score(matched_location)
        + get_negative_score(title, body)
    )
    confidence = get_match_confidence(score)
    matches = sorted(
        title_matches + body_matches,
        key=lambda match: (
            match["score"],
            match["keyword"] in title_keywords,
            len(match["keyword"]) if match["strength"] != "weak" else -match["index"],
        ),
        reverse=True,
    )

    if not matches or not matched_location or score < LOW_CONFIDENCE_THRESHOLD:
        return None

    return {
        "matched_keyword": matches[0]["keyword"],
        "relevance_score": score,
        "match_confidence": confidence,
    }


def find_matching_location(text: str) -> str | None:
    for location in locations:
        if location_matches(location, text):
            return location

    return None


def get_job_key(
    company_name: str,
    title: str,
    matched_location: str,
) -> tuple[str, str, str]:
    return (
        company_name.lower(),
        title.strip().lower(),
        matched_location.strip().lower(),
    )
