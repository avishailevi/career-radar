import json
from urllib.request import Request
from urllib.request import urlopen

from services.filter_service import evaluate_job_relevance
from services.filter_service import get_job_key


GETRO_API_URL = "https://api.getro.com/api/v2/collections/{network_id}/search/jobs"


def fetch_jobs_page(network_id: str, query: dict) -> dict:
    request = Request(
        GETRO_API_URL.format(network_id=network_id),
        data=json.dumps(query).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0",
        },
        method="POST",
    )

    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def get_location(job: dict) -> str:
    locations = job.get("locations") or []
    if not locations:
        return ""

    return ", ".join(location for location in locations if location)


def get_text_to_check(job: dict) -> str:
    fields = [
        job.get("title", ""),
        get_location(job),
        " ".join(job.get("job_functions") or []),
        " ".join(job.get("jobFunctions") or []),
    ]

    organization = job.get("organization") or {}
    fields.extend(organization.get("industry_tags") or [])

    return " ".join(field for field in fields if field)


def get_jobs_from_response(response: dict) -> tuple[list[dict], int]:
    results = response.get("results") or {}
    jobs = results.get("jobs") or []
    total = results.get("count") or len(jobs)

    if not isinstance(jobs, list):
        return [], 0

    return jobs, total


def build_query(company: dict, page: int) -> dict:
    filters = dict(company.get("filters", {}))
    filters["organization.id"] = [company["organization_id"]]

    return {
        "hitsPerPage": company.get("hits_per_page", 50),
        "page": page,
        "query": company.get("query", ""),
        "filters": filters,
    }


class GetroScanner:
    def scan(self, company: dict, debug: bool = False) -> list[dict]:
        relevant_jobs = []
        seen_jobs = set()
        total = None
        page = 0
        jobs_checked = 0
        location_match_count = 0
        keyword_match_count = 0

        print(f"\nScanning {company['name']}...")
        if debug:
            print(f"  Platform: {company.get('platform')}")
            print(f"  Network ID: {company.get('network_id')}")
            print(f"  Organization ID: {company.get('organization_id')}")

        while total is None or jobs_checked < total:
            jobs, total = get_jobs_from_response(
                fetch_jobs_page(company["network_id"], build_query(company, page))
            )
            if not jobs:
                break

            jobs_checked += len(jobs)
            page += 1

            for job in jobs:
                title = (job.get("title") or "").strip()
                matched_location = get_location(job)
                if not title or not matched_location:
                    continue

                location_match_count += 1
                relevance = evaluate_job_relevance(
                    title,
                    get_text_to_check(job),
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
                        "url": job.get("url") or company["url"],
                        "matched_location": matched_location,
                        "matched_keyword": relevance["matched_keyword"],
                        "relevance_score": relevance["relevance_score"],
                        "match_confidence": relevance["match_confidence"],
                    }
                )

        if debug:
            print(f"Debug {company['name']}:")
            print(f"  Jobs checked: {jobs_checked}")
            print(f"  Location matches: {location_match_count}")
            print(f"  Keyword matches: {keyword_match_count}")
            print(f"  Relevant jobs: {len(relevant_jobs)}")

        return relevant_jobs
