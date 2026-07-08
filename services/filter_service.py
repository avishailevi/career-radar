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
    "workdayjobs.com",
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

    if "/about/careers/applications/jobs/results/" in parsed_url.path:
        return not parsed_url.path.rstrip("/").endswith("/jobs/results")

    return any(hint in url_lower for hint in JOB_URL_HINTS)


def is_possible_job_link(title: str, url: str) -> bool:
    text = f"{title} {url}".lower()
    return any(hint in text for hint in POSSIBLE_JOB_TEXT_HINTS)


def get_title_from_url(url: str) -> str:
    path = urlparse(url).path.rstrip("/")
    slug = unquote(path.rsplit("/", 1)[-1])

    if not slug:
        return ""

    parts = slug.split("-", 1)
    if parts[0].isdigit() and len(parts) > 1:
        slug = parts[1]

    return slug.replace("-", " ").strip().title()


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
