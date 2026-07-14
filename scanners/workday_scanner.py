import re
from dataclasses import dataclass
from urllib.parse import urljoin
from urllib.parse import urlparse

import requests
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from scanner import MAX_DETAIL_PAGES_PER_COMPANY
from scanner import get_job_detail_result
from scanner import get_job_verification_state
from services.filter_service import evaluate_job_relevance
from services.filter_service import find_matching_location
from services.filter_service import get_job_key


PAGE_LIMIT = 20
MAX_PAGES = 5
MAX_WORKDAY_DETAIL_PAGES_PER_COMPANY = 2
REQUEST_TIMEOUT_SECONDS = 30
WORKDAY_LOCALE_PATTERN = re.compile(r"^[a-z]{2}-[A-Z]{2}$")
ISRAEL_DESCRIPTOR_HINTS = [
    "israel",
    "isr-",
    "tel aviv",
    "haifa",
    "jerusalem",
    "yokneam",
    "raanana",
    "ra'anana",
    "petah",
    "kiryat",
    "yavne",
    "migdal",
]


@dataclass
class WorkdaySite:
    base_url: str
    tenant: str
    site: str


@dataclass
class WorkdayCandidate:
    title: str
    url: str
    identity_url: str
    locations_text: str
    job_id: str
    posted_on: str
    source_text: str
    order: int


def clean_text(value) -> str:
    return " ".join(str(value or "").split())


def get_workday_board_url(company: dict) -> str:
    return company.get("workday_url") or company["url"]


def get_workday_site(company: dict) -> WorkdaySite:
    board_url = get_workday_board_url(company)
    parsed_url = urlparse(board_url)
    hostname = parsed_url.hostname or ""
    host_parts = hostname.split(".")

    if len(host_parts) < 3 or "workdayjobs" not in hostname:
        raise ValueError(f"Not a Workday jobs URL: {board_url}")

    path_parts = [
        part
        for part in parsed_url.path.split("/")
        if part and not WORKDAY_LOCALE_PATTERN.match(part)
    ]

    if not path_parts:
        raise ValueError(f"Could not determine Workday site from URL: {board_url}")

    return WorkdaySite(
        base_url=f"{parsed_url.scheme}://{parsed_url.netloc}",
        tenant=host_parts[0],
        site=path_parts[0],
    )


def get_workday_search_url(site: WorkdaySite) -> str:
    return f"{site.base_url}/wday/cxs/{site.tenant}/{site.site}/jobs"


def fetch_workday_page(
    site: WorkdaySite,
    offset: int,
    limit: int = PAGE_LIMIT,
    applied_facets: dict | None = None,
) -> dict:
    response = requests.post(
        get_workday_search_url(site),
        json={
            "appliedFacets": applied_facets or {},
            "limit": limit,
            "offset": offset,
            "searchText": "",
        },
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0",
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    data = response.json()

    if not isinstance(data, dict):
        return {}

    return data


def is_israel_descriptor(descriptor: str) -> bool:
    text = clean_text(descriptor).lower()

    if not text:
        return False

    return any(hint in text for hint in ISRAEL_DESCRIPTOR_HINTS)


def iter_facet_groups(facets: list) -> list[dict]:
    groups = []

    for facet in facets:
        if not isinstance(facet, dict):
            continue

        values = facet.get("values", [])
        if not isinstance(values, list):
            continue

        if facet.get("facetParameter"):
            groups.append(facet)

        groups.extend(iter_facet_groups(values))

    return groups


def get_israel_applied_facets(data: dict) -> dict:
    facet_groups = iter_facet_groups(data.get("facets", []))
    exact_country_match = None
    best_match = None

    for group in facet_groups:
        facet_parameter = group.get("facetParameter")
        values = group.get("values", [])

        if not facet_parameter or not isinstance(values, list):
            continue

        matching_ids = [
            value.get("id")
            for value in values
            if isinstance(value, dict)
            and value.get("id")
            and is_israel_descriptor(value.get("descriptor", ""))
        ]

        if not matching_ids:
            continue

        exact_ids = [
            value.get("id")
            for value in values
            if isinstance(value, dict)
            and value.get("id")
            and clean_text(value.get("descriptor")).lower() == "israel"
        ]

        if exact_ids:
            exact_country_match = {facet_parameter: exact_ids}
            break

        if (
            best_match is None
            or len(matching_ids) > len(next(iter(best_match.values())))
        ):
            best_match = {facet_parameter: matching_ids}

    return exact_country_match or best_match or {}


def get_positive_total(value) -> int | None:
    try:
        total = int(value)
    except (TypeError, ValueError):
        return None

    if total > 0:
        return total

    return None


def get_first_bullet_field(posting: dict) -> str:
    bullet_fields = posting.get("bulletFields", [])

    if not isinstance(bullet_fields, list):
        return ""

    for field in bullet_fields:
        value = clean_text(field)
        if value:
            return value

    return ""


def build_workday_job_url(site: WorkdaySite, external_path: str) -> str:
    return urljoin(f"{site.base_url}/{site.site}/", external_path.lstrip("/"))


def get_candidate_from_posting(
    site: WorkdaySite,
    posting: dict,
    order: int,
) -> WorkdayCandidate | None:
    title = clean_text(posting.get("title"))
    external_path = clean_text(posting.get("externalPath"))

    if not title or not external_path:
        return None

    locations_text = clean_text(posting.get("locationsText"))
    job_id = get_first_bullet_field(posting)
    posted_on = clean_text(posting.get("postedOn"))
    url = build_workday_job_url(site, external_path)
    source_text = " ".join(
        part
        for part in [title, locations_text, job_id, posted_on, external_path]
        if part
    )

    return WorkdayCandidate(
        title=title,
        url=url,
        identity_url=url,
        locations_text=locations_text,
        job_id=job_id,
        posted_on=posted_on,
        source_text=source_text,
        order=order,
    )


def discover_workday_candidates(
    company: dict,
    max_pages: int | None = None,
    page_limit: int = PAGE_LIMIT,
) -> tuple[list[WorkdayCandidate], dict]:
    site = get_workday_site(company)
    page_cap = max_pages or company.get("workday_max_pages", MAX_PAGES)
    candidates = []
    seen_urls = set()
    malformed_count = 0
    requests_made = 0
    pagination_cap_reached = False
    total_available = None

    initial_data = fetch_workday_page(site, 0, page_limit)
    requests_made += 1
    applied_facets = get_israel_applied_facets(initial_data)
    first_page_data = None

    if applied_facets:
        first_page_data = fetch_workday_page(site, 0, page_limit, applied_facets)
        requests_made += 1
    else:
        first_page_data = initial_data

    for page_index in range(page_cap):
        offset = page_index * page_limit
        if page_index == 0:
            data = first_page_data
        else:
            data = fetch_workday_page(site, offset, page_limit, applied_facets)
            requests_made += 1
        postings = data.get("jobPostings", [])
        total_available = data.get("total", total_available)
        positive_total = get_positive_total(total_available)

        if not isinstance(postings, list) or not postings:
            break

        for posting in postings:
            if not isinstance(posting, dict):
                malformed_count += 1
                continue

            candidate = get_candidate_from_posting(
                site,
                posting,
                len(candidates),
            )
            if not candidate:
                malformed_count += 1
                continue

            if candidate.url in seen_urls:
                continue

            seen_urls.add(candidate.url)
            candidates.append(candidate)

        if len(postings) < page_limit:
            break

        if positive_total is not None and len(candidates) >= positive_total:
            break
    else:
        positive_total = get_positive_total(total_available)
        if positive_total is None or len(candidates) < positive_total:
            pagination_cap_reached = True

    diagnostics = {
        "site": site,
        "search_url": get_workday_search_url(site),
        "requests_made": requests_made,
        "malformed_count": malformed_count,
        "pagination_cap_reached": pagination_cap_reached,
        "total_available": total_available,
        "applied_facets": applied_facets,
    }
    return candidates, diagnostics


def sort_workday_candidates(candidates: list[WorkdayCandidate]) -> list[WorkdayCandidate]:
    def sort_key(candidate: WorkdayCandidate):
        matched_location = find_matching_location(candidate.source_text)
        relevance = evaluate_job_relevance(
            candidate.title,
            candidate.source_text,
            matched_location,
        )
        relevance_score = relevance["relevance_score"] if relevance else 0

        return (
            matched_location is None,
            -relevance_score,
            candidate.order,
        )

    return sorted(candidates, key=sort_key)


def get_workday_job_text(
    candidate: WorkdayCandidate,
    detail_text: str,
) -> str:
    return " ".join(
        part
        for part in [candidate.source_text, detail_text]
        if part
    )


def add_identity_url(job_data: dict, identity_url: str) -> dict:
    if identity_url != job_data["url"]:
        job_data["identity_url"] = identity_url

    return job_data


def build_workday_jobs(
    company: dict,
    candidates: list[WorkdayCandidate],
    read_detail_result,
    read_detail_pages: bool = True,
    max_detail_pages: int = MAX_DETAIL_PAGES_PER_COMPANY,
) -> tuple[list[dict], dict]:
    relevant_jobs = []
    seen_jobs = set()

    location_match_count = 0
    keyword_match_count = 0
    duplicate_job_count = 0
    detail_page_count = 0
    detail_verified_count = 0
    detail_failed_count = 0
    detail_skipped_count = 0
    listing_fallback_count = 0
    detail_keyword_match_count = 0
    detail_failure_reasons = {}

    for candidate in sort_workday_candidates(candidates):
        detail_result = None
        used_listing_fallback = False
        matched_from_detail = False
        text_to_check = candidate.source_text
        should_verify_detail = (
            read_detail_pages
            and detail_page_count < max_detail_pages
        )

        if should_verify_detail:
            detail_page_count += 1
            detail_result = read_detail_result(candidate.url, candidate.title)

            if detail_result.status == "verified":
                detail_verified_count += 1
                matched_from_detail = True
                text_to_check = get_workday_job_text(
                    candidate,
                    detail_result.text,
                )
            else:
                detail_failed_count += 1
                detail_failure_reasons[detail_result.status] = (
                    detail_failure_reasons.get(detail_result.status, 0) + 1
                )
                used_listing_fallback = True
                listing_fallback_count += 1
        elif read_detail_pages:
            detail_skipped_count += 1
            used_listing_fallback = True

        matched_location = find_matching_location(text_to_check)
        if not matched_location:
            continue

        location_match_count += 1
        relevance = evaluate_job_relevance(
            candidate.title,
            text_to_check,
            matched_location,
        )
        if not relevance:
            continue

        job_key = get_job_key(
            company["name"],
            candidate.title,
            matched_location,
        )
        if job_key in seen_jobs:
            duplicate_job_count += 1
            continue

        seen_jobs.add(job_key)
        keyword_match_count += 1

        if matched_from_detail:
            detail_keyword_match_count += 1

        verification_state = get_job_verification_state(
            read_detail_pages,
            detail_result,
            used_listing_fallback,
        )
        job_data = {
            "company": company["name"],
            "title": candidate.title,
            "url": candidate.url,
            "matched_location": matched_location,
            "matched_keyword": relevance["matched_keyword"],
            "relevance_score": relevance["relevance_score"],
            "match_confidence": relevance["match_confidence"],
            "verification_state": verification_state,
        }
        relevant_jobs.append(add_identity_url(job_data, candidate.identity_url))

    diagnostics = {
        "location_match_count": location_match_count,
        "keyword_match_count": keyword_match_count,
        "duplicate_job_count": duplicate_job_count,
        "detail_page_count": detail_page_count,
        "detail_verified_count": detail_verified_count,
        "detail_failed_count": detail_failed_count,
        "detail_skipped_count": detail_skipped_count,
        "listing_fallback_count": listing_fallback_count,
        "detail_keyword_match_count": detail_keyword_match_count,
        "detail_failure_reasons": detail_failure_reasons,
    }
    return relevant_jobs, diagnostics


class WorkdayScanner:
    def scan(self, company: dict, debug: bool = False) -> list[dict]:
        print(f"\nScanning {company['name']}...")
        if debug:
            print(f"  Platform: {company.get('platform')}")
            print(f"  Board URL: {get_workday_board_url(company)}")

        try:
            candidates, discovery = discover_workday_candidates(company)
        except Exception as error:
            print(f"Failed to load {company['name']}: {error}")
            return []

        read_detail_pages = True
        max_detail_pages = company.get(
            "max_detail_pages",
            MAX_WORKDAY_DETAIL_PAGES_PER_COMPANY,
        )

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context()

            try:
                jobs, scan_diagnostics = build_workday_jobs(
                    company,
                    candidates,
                    lambda url, title: get_job_detail_result(context, url, title),
                    read_detail_pages=read_detail_pages,
                    max_detail_pages=max_detail_pages,
                )
            finally:
                try:
                    context.close()
                    browser.close()
                except PlaywrightError:
                    pass

        if debug:
            israel_candidates = sum(
                1
                for candidate in candidates
                if find_matching_location(candidate.source_text)
            )
            print(f"Debug {company['name']}:")
            print(f"  Workday search URL: {discovery['search_url']}")
            print(f"  Workday applied facets: {discovery['applied_facets']}")
            print(f"  Workday search requests: {discovery['requests_made']}")
            print(f"  Workday total available: {discovery['total_available']}")
            print(f"  Workday candidates discovered: {len(candidates)}")
            print(f"  Workday Israel candidates: {israel_candidates}")
            print(
                "  Workday pagination cap reached: "
                f"{discovery['pagination_cap_reached']}"
            )
            print(
                "  Workday malformed results skipped: "
                f"{discovery['malformed_count']}"
            )
            print(f"  Job-like URLs: {len(candidates)}")
            print(f"  Location matches: {scan_diagnostics['location_match_count']}")
            print(
                "  Duplicate jobs filtered: "
                f"{scan_diagnostics['duplicate_job_count']}"
            )
            print(
                "  Detail pages attempted: "
                f"{scan_diagnostics['detail_page_count']}"
            )
            print(
                "  Detail pages verified: "
                f"{scan_diagnostics['detail_verified_count']}"
            )
            print(
                "  Detail pages failed: "
                f"{scan_diagnostics['detail_failed_count']}"
            )
            print(
                "  Detail pages skipped: "
                f"{scan_diagnostics['detail_skipped_count']}"
            )
            print(
                "  Listing fallbacks used: "
                f"{scan_diagnostics['listing_fallback_count']}"
            )
            print(
                "  Detail keyword matches: "
                f"{scan_diagnostics['detail_keyword_match_count']}"
            )
            if scan_diagnostics["detail_failure_reasons"]:
                failure_summary = "; ".join(
                    f"{reason}={count}"
                    for reason, count in sorted(
                        scan_diagnostics["detail_failure_reasons"].items()
                    )
                )
                print(f"  Detail failure reasons: {failure_summary}")
            print(f"  Keyword matches: {scan_diagnostics['keyword_match_count']}")
            print(f"  Relevant jobs: {len(jobs)}")

            for job in jobs[:5]:
                print(f"  Relevant job: {job['title']}")
                print(f"      URL: {job['url']}")
                print(f"      Location: {job['matched_location']}")
                print(f"      Keyword: {job['matched_keyword']}")
                print(f"      Verification: {job['verification_state']}")

        return jobs
