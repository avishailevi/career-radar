from urllib.parse import urlencode
from urllib.parse import urljoin
from urllib.parse import urlparse
from urllib.request import Request
from urllib.request import urlopen
import json

from services.filter_service import find_matching_keyword
from services.filter_service import find_matching_location
from services.filter_service import get_job_key


PAGE_SIZE = 10
MAX_RESULTS = 100


def get_eightfold_domain(company: dict) -> str:
    configured_domain = company.get("domain")
    if configured_domain:
        return configured_domain

    hostname = urlparse(company["url"]).hostname or ""
    if hostname.startswith("careers."):
        return hostname.removeprefix("careers.")

    return hostname


def get_search_url(company: dict, start: int) -> str:
    query = urlencode(
        {
            "domain": get_eightfold_domain(company),
            "query": company.get("query", ""),
            "location": company.get("search_location", "Israel"),
            "start": start,
        }
    )

    return f"{urljoin(company['url'], '/api/pcsx/search')}?{query}&"


def fetch_json(url: str) -> dict:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0",
        },
    )

    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def get_position_text(position: dict) -> str:
    fields = [
        position.get("name", ""),
        position.get("department", ""),
        " ".join(position.get("locations", [])),
        " ".join(position.get("standardizedLocations", [])),
    ]

    return " ".join(field for field in fields if field)


def get_position_url(company: dict, position: dict) -> str:
    return urljoin(company["url"], position.get("positionUrl", ""))


class EightfoldScanner:
    def scan(self, company: dict, debug: bool = False) -> list[dict]:
        relevant_jobs = []
        seen_jobs = set()
        positions_checked = 0
        location_match_count = 0
        keyword_match_count = 0
        start = 0

        print(f"\nScanning {company['name']}...")
        if debug:
            print(f"  Platform: {company.get('platform')}")
            print(f"  Search location: {company.get('search_location', 'Israel')}")

        while start < MAX_RESULTS:
            data = fetch_json(get_search_url(company, start))
            positions = data.get("data", {}).get("positions", [])

            if not positions:
                break

            for position in positions:
                positions_checked += 1
                text_to_check = get_position_text(position)
                matched_location = find_matching_location(text_to_check)

                if not matched_location:
                    continue

                location_match_count += 1
                matched_keyword = find_matching_keyword(text_to_check)

                if not matched_keyword:
                    continue

                title = position.get("name", "").strip()
                if not title:
                    continue

                job_key = get_job_key(
                    company["name"],
                    title,
                    matched_location,
                )

                if job_key in seen_jobs:
                    continue

                seen_jobs.add(job_key)
                keyword_match_count += 1
                relevant_jobs.append(
                    {
                        "company": company["name"],
                        "title": title,
                        "url": get_position_url(company, position),
                        "matched_keyword": matched_keyword,
                        "matched_location": matched_location,
                    }
                )

            if len(positions) < PAGE_SIZE:
                break

            start += PAGE_SIZE

        if debug:
            print(f"Debug {company['name']}:")
            print(f"  Positions checked: {positions_checked}")
            print(f"  Location matches: {location_match_count}")
            print(f"  Keyword matches: {keyword_match_count}")
            print(f"  Relevant jobs: {len(relevant_jobs)}")

        return relevant_jobs
