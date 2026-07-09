from html import unescape
import json
import re
from urllib.parse import urljoin
from urllib.request import Request
from urllib.request import urlopen

from services.filter_service import evaluate_job_relevance
from services.filter_service import get_job_key


TAG_LOCATION_PATTERN = re.compile(r"#([A-Za-z][A-Za-z -]+)")
HTML_TAG_PATTERN = re.compile(r"<[^>]+>")


def fetch_json(url: str) -> list[dict]:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0",
        },
    )

    with urlopen(request, timeout=30) as response:
        data = json.loads(response.read().decode("utf-8"))

    if isinstance(data, list):
        return data

    return []


def clean_text(value) -> str:
    if value is None:
        return ""

    text = unescape(str(value))
    text = HTML_TAG_PATTERN.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def get_field_text(job: dict, field: str) -> str:
    return clean_text(job.get(field, ""))


def get_text_to_check(company: dict, job: dict) -> str:
    fields = company.get("text_fields", [])
    return " ".join(
        get_field_text(job, field)
        for field in fields
        if get_field_text(job, field)
    )


def get_location(company: dict, job: dict) -> str | None:
    for field in company.get("location_fields", []):
        location = get_field_text(job, field)
        if location:
            return location

    for field in company.get("text_fields", []):
        match = TAG_LOCATION_PATTERN.search(get_field_text(job, field))
        if match:
            return match.group(1).strip()

    return company.get("default_location")


def get_job_url(company: dict, job: dict) -> str:
    id_field = company.get("id_field", "id")
    job_id = job.get(id_field, "")
    template = company.get("url_template")

    if template:
        return template.format(id=job_id)

    return urljoin(company["url"], str(job_id))


def is_allowed_job(company: dict, job: dict) -> bool:
    allowed_field_values = company.get("allowed_field_values", {})

    for field, allowed_values in allowed_field_values.items():
        if job.get(field) not in allowed_values:
            return False

    return True


class StaticJsonScanner:
    def scan(self, company: dict, debug: bool = False) -> list[dict]:
        relevant_jobs = []
        seen_jobs = set()
        jobs = fetch_json(company["feed_url"])
        location_match_count = 0
        keyword_match_count = 0

        print(f"\nScanning {company['name']}...")
        if debug:
            print(f"  Platform: {company.get('platform')}")
            print(f"  Feed URL: {company.get('feed_url')}")

        for job in jobs:
            if not is_allowed_job(company, job):
                continue

            title = get_field_text(job, company.get("title_field", "title"))
            if not title:
                continue

            matched_location = get_location(company, job)
            if not matched_location:
                continue

            location_match_count += 1
            text_to_check = f"{title} {matched_location} {get_text_to_check(company, job)}"
            relevance = evaluate_job_relevance(
                title,
                text_to_check,
                matched_location,
            )

            if not relevance:
                continue

            job_key = get_job_key(company["name"], title, matched_location)
            if job_key in seen_jobs:
                continue

            seen_jobs.add(job_key)
            keyword_match_count += 1
            relevant_jobs.append(
                {
                    "company": company["name"],
                    "title": title,
                    "url": get_job_url(company, job),
                    "matched_location": matched_location,
                    "matched_keyword": relevance["matched_keyword"],
                    "relevance_score": relevance["relevance_score"],
                    "match_confidence": relevance["match_confidence"],
                }
            )

        if debug:
            print(f"Debug {company['name']}:")
            print(f"  Jobs checked: {len(jobs)}")
            print(f"  Location matches: {location_match_count}")
            print(f"  Keyword matches: {keyword_match_count}")
            print(f"  Relevant jobs: {len(relevant_jobs)}")

        return relevant_jobs
