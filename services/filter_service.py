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
    for keyword in keywords:
        if keyword_matches(keyword, text):
            return keyword

    return None


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
