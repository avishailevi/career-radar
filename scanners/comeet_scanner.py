import json
import re
from urllib.request import Request
from urllib.request import urlopen

from services.filter_service import evaluate_job_relevance
from services.filter_service import get_job_key


POSITIONS_PATTERN = re.compile(
    r"COMPANY_POSITIONS_DATA\s*=\s*(.*?);\s*POSITION_DATA",
    re.DOTALL,
)


def fetch_html(url: str) -> str:
    request = Request(
        url,
        headers={
            "Accept": "text/html",
            "User-Agent": "Mozilla/5.0",
        },
    )

    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def parse_positions(html: str) -> list[dict]:
    match = POSITIONS_PATTERN.search(html)
    if not match:
        return []

    positions = json.loads(match.group(1))
    if isinstance(positions, list):
        return positions

    return []


def is_location_allowed(position: dict, country: str) -> bool:
    location = position.get("location") or {}
    return location.get("country") == country


def is_department_allowed(company: dict, position: dict) -> bool:
    allowed_departments = company.get("allowed_departments")
    if not allowed_departments:
        return True

    return position.get("department") in allowed_departments


def get_location_name(position: dict) -> str:
    location = position.get("location") or {}
    return location.get("city") or location.get("name") or location.get("country") or ""


def get_text_to_check(position: dict) -> str:
    location = position.get("location") or {}
    fields = [
        position.get("name", ""),
        position.get("department", ""),
        location.get("name", ""),
        location.get("city", ""),
        location.get("country", ""),
    ]

    return " ".join(field for field in fields if field)


class ComeetScanner:
    def scan(self, company: dict, debug: bool = False) -> list[dict]:
        relevant_jobs = []
        seen_jobs = set()
        positions = parse_positions(fetch_html(company["url"]))
        country = company.get("country", "IL")
        location_match_count = 0
        department_match_count = 0
        keyword_match_count = 0

        print(f"\nScanning {company['name']}...")
        if debug:
            print(f"  Platform: {company.get('platform')}")
            print(f"  Country: {country}")

        for position in positions:
            if not is_location_allowed(position, country):
                continue

            location_match_count += 1

            if not is_department_allowed(company, position):
                continue

            department_match_count += 1
            title = position.get("name", "").strip()
            matched_location = get_location_name(position)
            text_to_check = get_text_to_check(position)
            relevance = evaluate_job_relevance(
                title,
                text_to_check,
                matched_location,
            )

            if not title or not matched_location or not relevance:
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
                    "url": position.get("url_comeet_hosted_page") or company["url"],
                    "matched_location": matched_location,
                    "matched_keyword": relevance["matched_keyword"],
                    "relevance_score": relevance["relevance_score"],
                    "match_confidence": relevance["match_confidence"],
                }
            )

        if debug:
            print(f"Debug {company['name']}:")
            print(f"  Positions checked: {len(positions)}")
            print(f"  Location matches: {location_match_count}")
            print(f"  Department matches: {department_match_count}")
            print(f"  Keyword matches: {keyword_match_count}")
            print(f"  Relevant jobs: {len(relevant_jobs)}")

        return relevant_jobs
