from dataclasses import dataclass
from urllib.parse import urljoin

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from services.filter_service import POSSIBLE_JOB_TEXT_HINTS
from services.filter_service import clean_link_title
from services.filter_service import find_matching_location
from services.filter_service import evaluate_job_relevance
from services.filter_service import get_job_key
from services.filter_service import get_title_from_url
from services.filter_service import is_identifier_title
from services.filter_service import is_bad_title
from services.filter_service import is_bad_url
from services.filter_service import is_job_list_url
from services.filter_service import is_job_url
from services.filter_service import is_possible_job_link
from services.platform_service import should_follow_job_list_link
from services.platform_service import should_read_detail_pages

DEBUG_SAMPLE_LIMIT = 5
JOB_CARD_CONTEXT_LINES = 6
MIN_DETAIL_TEXT_LENGTH = 300
MAX_DETAIL_PAGES_PER_COMPANY = 10

DETAIL_VERIFIED = "detail_verified"
LISTING_FALLBACK = "listing_fallback"
DETAIL_FAILED = "detail_failed"

DETAIL_DESCRIPTION_HINTS = [
    "about the job",
    "basic qualifications",
    "description",
    "job description",
    "job requisition",
    "locations",
    "minimum qualifications",
    "qualifications",
    "requirements",
    "responsibilities",
    "what you'll be doing",
    "we are looking",
]


@dataclass
class DetailReadResult:
    text: str
    requested_url: str
    final_url: str
    status: str
    page_title: str = ""
    error: str = ""


def add_debug_sample(samples: list[dict], sample: dict) -> None:
    if len(samples) < DEBUG_SAMPLE_LIMIT:
        samples.append(sample)


def get_matching_text_lines(page_text: str) -> list[str]:
    matching_lines = []

    for line in page_text.splitlines():
        clean_line = line.strip()
        if not clean_line:
            continue

        if any(hint in clean_line.lower() for hint in POSSIBLE_JOB_TEXT_HINTS):
            matching_lines.append(clean_line)

        if len(matching_lines) >= DEBUG_SAMPLE_LIMIT:
            break

    return matching_lines


def get_job_card_text(page_text: str, title: str) -> str:
    clean_lines = [
        line.strip()
        for line in page_text.splitlines()
        if line.strip()
    ]

    title_lower = title.lower()

    for index, line in enumerate(clean_lines):
        if title_lower in line.lower():
            if "\t" in line:
                return line

            end_index = index + JOB_CARD_CONTEXT_LINES
            return " ".join(clean_lines[index:end_index])

    return ""


def get_link_base_url(page) -> str:
    try:
        base = page.locator("base").first
        if base.count() > 0:
            base_href = base.get_attribute("href")
            if base_href:
                return base_href
    except PlaywrightError:
        pass

    return page.url


def get_job_list_link(page, link_texts: list[str]):
    links = page.locator("a").all()

    for link in links:
        try:
            title = link.inner_text().strip()
            href = link.get_attribute("href")

            if not title or not href:
                continue

            if title not in link_texts:
                continue

            full_url = urljoin(get_link_base_url(page), href)
            if is_job_url(full_url) or is_job_list_url(full_url):
                return link, href, title

        except PlaywrightError:
            continue

    return None, None, None


def normalize_for_match(text: str) -> str:
    return " ".join(text.lower().replace("-", " ").replace("–", " ").split())


def title_matches_detail(expected_title: str, page_title: str, body_text: str) -> bool:
    expected = normalize_for_match(expected_title)
    title = normalize_for_match(page_title)
    body = normalize_for_match(body_text)

    if not expected:
        return False

    if expected in title or expected in body:
        return True

    significant_words = [
        word
        for word in expected.split()
        if len(word) > 2
    ]

    if len(significant_words) < 2:
        return False

    matched_words = sum(
        1
        for word in significant_words
        if word in title or word in body
    )

    return matched_words >= max(2, len(significant_words) - 1)


def has_detail_description_signal(body_text: str) -> bool:
    text = body_text.lower()
    return any(hint in text for hint in DETAIL_DESCRIPTION_HINTS)


def validate_detail_read_result(
    result: DetailReadResult,
    expected_title: str,
) -> DetailReadResult:
    text = result.text.strip()

    if not text:
        return DetailReadResult(
            text="",
            requested_url=result.requested_url,
            final_url=result.final_url,
            status="empty_body",
            page_title=result.page_title,
            error=result.error,
        )

    if result.final_url and not is_job_url(result.final_url):
        return DetailReadResult(
            text=text,
            requested_url=result.requested_url,
            final_url=result.final_url,
            status="redirected_away_from_job_detail",
            page_title=result.page_title,
            error=result.error,
        )

    if len(text) < MIN_DETAIL_TEXT_LENGTH:
        return DetailReadResult(
            text=text,
            requested_url=result.requested_url,
            final_url=result.final_url,
            status="invalid_or_generic_page",
            page_title=result.page_title,
            error=result.error,
        )

    if not title_matches_detail(expected_title, result.page_title, text):
        return DetailReadResult(
            text=text,
            requested_url=result.requested_url,
            final_url=result.final_url,
            status="invalid_or_generic_page",
            page_title=result.page_title,
            error=result.error,
        )

    if not has_detail_description_signal(text):
        return DetailReadResult(
            text=text,
            requested_url=result.requested_url,
            final_url=result.final_url,
            status="invalid_or_generic_page",
            page_title=result.page_title,
            error=result.error,
        )

    return DetailReadResult(
        text=text,
        requested_url=result.requested_url,
        final_url=result.final_url,
        status="verified",
        page_title=result.page_title,
        error=result.error,
    )


def get_page_body_text(page) -> str:
    try:
        page.wait_for_selector("body", timeout=10000)
    except PlaywrightError:
        return ""

    try:
        return page.locator("body").inner_text(timeout=10000).strip()
    except PlaywrightError:
        pass

    try:
        body_text = page.evaluate("() => document.body ? document.body.innerText : ''")
        return body_text.strip()
    except PlaywrightError:
        return ""


def wait_for_meaningful_detail_text(page, expected_title: str) -> None:
    expected = normalize_for_match(expected_title)

    try:
        page.wait_for_selector("body", timeout=10000)
    except PlaywrightError:
        return

    try:
        page.wait_for_function(
            r"""([expectedTitle, minLength]) => {
                const body = document.body ? document.body.innerText : '';
                const title = document.title || '';
                const text = `${title} ${body}`
                    .toLowerCase()
                    .replace(/[-–]/g, ' ')
                    .replace(/\s+/g, ' ')
                    .trim();
                return body.trim().length >= minLength
                    || (expectedTitle && text.includes(expectedTitle));
            }""",
            arg=[expected, MIN_DETAIL_TEXT_LENGTH],
            timeout=8000,
        )
    except PlaywrightError:
        pass


def get_page_title(page) -> str:
    try:
        return page.title()
    except PlaywrightError:
        return ""


def get_error_summary(error: Exception) -> str:
    for line in str(error).splitlines():
        clean_line = line.strip()
        if clean_line:
            return clean_line

    return error.__class__.__name__


def get_job_detail_result(
    context,
    url: str,
    expected_title: str,
) -> DetailReadResult:
    detail_page = None

    try:
        detail_page = context.new_page()
        detail_page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=45000,
        )
        wait_for_meaningful_detail_text(detail_page, expected_title)
        result = DetailReadResult(
            text=get_page_body_text(detail_page),
            requested_url=url,
            final_url=detail_page.url,
            status="loaded",
            page_title=get_page_title(detail_page),
        )
        return validate_detail_read_result(result, expected_title)

    except PlaywrightTimeoutError as error:
        return DetailReadResult(
            text="",
            requested_url=url,
            final_url=detail_page.url if detail_page else "",
            status="timeout",
            page_title=get_page_title(detail_page) if detail_page else "",
            error=get_error_summary(error),
        )

    except PlaywrightError as error:
        return DetailReadResult(
            text="",
            requested_url=url,
            final_url=detail_page.url if detail_page else "",
            status="navigation_error",
            page_title=get_page_title(detail_page) if detail_page else "",
            error=get_error_summary(error),
        )

    finally:
        if detail_page:
            try:
                detail_page.close()
            except PlaywrightError:
                pass


def get_job_verification_state(
    read_detail_pages: bool,
    detail_result: DetailReadResult | None,
    used_listing_fallback: bool,
) -> str:
    if detail_result and detail_result.status == "verified":
        return DETAIL_VERIFIED

    if read_detail_pages and used_listing_fallback:
        return LISTING_FALLBACK

    if read_detail_pages:
        return DETAIL_FAILED

    return LISTING_FALLBACK


def try_follow_job_list_link(page) -> str | None:
    link_texts = [
        "See all jobs",
        "Search Jobs",
        "SEARCH JOBS",
        "Open Positions",
        "Jobs",
    ]

    job_link, job_href, job_title = get_job_list_link(page, link_texts)
    if job_link and job_href and job_title:
        try:
            page.goto(
                urljoin(get_link_base_url(page), job_href),
                wait_until="domcontentloaded",
                timeout=30000,
            )

            try:
                page.wait_for_load_state("networkidle", timeout=30000)
            except PlaywrightError:
                pass

            page.wait_for_timeout(3000)
            return job_title

        except PlaywrightError:
            pass

    for link_text in link_texts:
        try:
            link = page.get_by_role("link", name=link_text).first
            if link.count() == 0:
                continue

            href = link.get_attribute("href")
            if href:
                page.goto(
                    urljoin(page.url, href),
                    wait_until="domcontentloaded",
                    timeout=30000,
                )
            else:
                link.click()

            page.wait_for_load_state("domcontentloaded", timeout=30000)

            try:
                page.wait_for_load_state("networkidle", timeout=30000)
            except PlaywrightError:
                pass

            page.wait_for_timeout(3000)
            return link_text

        except PlaywrightError:
            continue

    return None


def scan_company(company: dict, debug: bool = False) -> list[dict]:
    relevant_jobs = []
    seen_urls = set()
    seen_jobs = set()

    total_links = 0
    usable_links = 0
    bad_title_count = 0
    bad_url_count = 0
    job_url_count = 0
    location_match_count = 0
    keyword_match_count = 0
    duplicate_job_count = 0
    detail_page_count = 0
    empty_detail_page_count = 0
    detail_verified_count = 0
    detail_failed_count = 0
    detail_skipped_count = 0
    page_text_fallback_count = 0
    detail_keyword_match_count = 0
    detail_failure_reasons = {}
    page_url = ""
    page_title = ""
    page_text = ""
    link_base_url = ""
    followed_link_text = None
    read_detail_pages = should_read_detail_pages(company)
    max_detail_pages = company.get(
        "max_detail_pages",
        MAX_DETAIL_PAGES_PER_COMPANY,
    )

    usable_link_samples = []
    possible_job_link_samples = []
    job_url_samples = []
    location_match_samples = []
    keyword_match_samples = []
    detail_verified_samples = []
    detail_failure_samples = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        print(f"\nScanning {company['name']}...")
        if debug:
            print(f"  Platform: {company.get('platform')}")
            print(f"  Read detail pages: {read_detail_pages}")

        try:
            page.goto(
                company["url"],
                wait_until="domcontentloaded",
                timeout=60000,
            )
        except PlaywrightError as error:
            print(f"Failed to load {company['name']}: {error}")
            context.close()
            browser.close()
            return []

        try:
            page.wait_for_load_state("networkidle", timeout=30000)
        except PlaywrightError:
            pass

        page.wait_for_timeout(5000)

        if should_follow_job_list_link(company):
            followed_link_text = try_follow_job_list_link(page)

        page_url = page.url

        try:
            page_title = page.title()
        except PlaywrightError:
            page_title = ""

        try:
            page_text = page.locator("body").inner_text(timeout=10000)
        except PlaywrightError:
            page_text = ""

        link_base_url = get_link_base_url(page)
        links = page.locator("a").all()
        total_links = len(links)

        for link in links:
            try:
                link_text = link.inner_text().strip()
                title = clean_link_title(link_text)
                href = link.get_attribute("href")

                if not href:
                    continue

                usable_links += 1
                full_url = urljoin(link_base_url, href)
                if not title or is_identifier_title(title):
                    title_from_url = get_title_from_url(full_url)
                    if title_from_url:
                        title = title_from_url

                if not title:
                    continue

                add_debug_sample(
                    usable_link_samples,
                    {
                        "title": title,
                        "url": full_url,
                    },
                )

                if is_possible_job_link(title, full_url):
                    add_debug_sample(
                        possible_job_link_samples,
                        {
                            "title": title,
                            "url": full_url,
                        },
                    )

                if full_url in seen_urls:
                    continue

                seen_urls.add(full_url)

                if is_bad_title(title):
                    bad_title_count += 1
                    continue

                if is_bad_url(full_url):
                    bad_url_count += 1
                    continue

                if not is_job_url(full_url):
                    continue

                job_url_count += 1
                text_to_check = f"{title} {full_url} {link_text}"
                matched_from_detail = False
                detail_result = None
                used_listing_fallback = False

                add_debug_sample(
                    job_url_samples,
                    {
                        "title": title,
                        "url": full_url,
                    },
                )

                card_text = get_job_card_text(page_text, title)
                if card_text:
                    text_to_check = f"{text_to_check} {card_text}"

                listing_location = find_matching_location(text_to_check)
                should_verify_detail = (
                    read_detail_pages
                    and detail_page_count < max_detail_pages
                    and listing_location is not None
                )

                if should_verify_detail:
                    detail_page_count += 1
                    detail_result = get_job_detail_result(
                        page.context,
                        full_url,
                        title,
                    )

                    if detail_result.status == "verified":
                        detail_verified_count += 1
                        matched_from_detail = True
                        text_to_check = f"{text_to_check} {detail_result.text}"

                        add_debug_sample(
                            detail_verified_samples,
                            {
                                "title": title,
                                "requested_url": detail_result.requested_url,
                                "final_url": detail_result.final_url,
                                "page_title": detail_result.page_title,
                                "body_length": len(detail_result.text),
                                "error": detail_result.error,
                            },
                        )
                    else:
                        detail_failed_count += 1
                        detail_failure_reasons[detail_result.status] = (
                            detail_failure_reasons.get(detail_result.status, 0)
                            + 1
                        )

                        if detail_result.status == "empty_body":
                            empty_detail_page_count += 1

                        add_debug_sample(
                            detail_failure_samples,
                            {
                                "title": title,
                                "reason": detail_result.status,
                                "requested_url": detail_result.requested_url,
                                "final_url": detail_result.final_url,
                                "page_title": detail_result.page_title,
                                "body_length": len(detail_result.text),
                            },
                        )

                        if card_text:
                            used_listing_fallback = True
                            page_text_fallback_count += 1

                elif read_detail_pages:
                    detail_skipped_count += 1
                    if card_text:
                        used_listing_fallback = True
                        page_text_fallback_count += 1

                matched_location = find_matching_location(text_to_check)

                if not matched_location:
                    continue

                location_match_count += 1

                add_debug_sample(
                    location_match_samples,
                    {
                        "title": title,
                        "url": full_url,
                        "matched_location": matched_location,
                    },
                )

                relevance = evaluate_job_relevance(
                    title,
                    text_to_check,
                    matched_location,
                )

                if not relevance:
                    continue

                job_key = get_job_key(
                    company["name"],
                    title,
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

                add_debug_sample(
                    keyword_match_samples,
                    {
                        "title": title,
                        "url": full_url,
                        "matched_location": matched_location,
                        "matched_keyword": relevance["matched_keyword"],
                        "relevance_score": relevance["relevance_score"],
                        "match_confidence": relevance["match_confidence"],
                        "verification_state": verification_state,
                    },
                )

                relevant_jobs.append(
                    {
                        "company": company["name"],
                        "title": title,
                        "url": full_url,
                        "matched_location": matched_location,
                        "matched_keyword": relevance["matched_keyword"],
                        "relevance_score": relevance["relevance_score"],
                        "match_confidence": relevance["match_confidence"],
                        "verification_state": verification_state,
                    }
                )

            except Exception:
                continue

        context.close()
        browser.close()

    if debug:
        print(f"Debug {company['name']}:")
        print(f"  Page URL: {page_url}")
        print(f"  Page title: {page_title}")

        if followed_link_text:
            print(f"  Followed job list link: {followed_link_text}")

        print(f"  Total links: {total_links}")
        print(f"  Usable links: {usable_links}")
        print(f"  Bad titles filtered: {bad_title_count}")
        print(f"  Bad URLs filtered: {bad_url_count}")
        print(f"  Job-like URLs: {job_url_count}")
        print(f"  Location matches: {location_match_count}")
        print(f"  Duplicate jobs filtered: {duplicate_job_count}")

        if read_detail_pages:
            print(f"  Detail pages checked: {detail_page_count}")
            print(f"  Detail pages attempted: {detail_page_count}")
            print(f"  Detail pages verified: {detail_verified_count}")
            print(f"  Detail pages failed: {detail_failed_count}")
            print(f"  Detail pages skipped: {detail_skipped_count}")
            print(f"  Empty detail pages: {empty_detail_page_count}")
            print(f"  Page text fallbacks: {page_text_fallback_count}")
            print(f"  Listing fallbacks used: {page_text_fallback_count}")
            print(f"  Detail keyword matches: {detail_keyword_match_count}")

            if detail_failure_reasons:
                failure_summary = "; ".join(
                    f"{reason}={count}"
                    for reason, count in sorted(detail_failure_reasons.items())
                )
                print(f"  Detail failure reasons: {failure_summary}")

        print(f"  Keyword matches: {keyword_match_count}")
        print(f"  Relevant jobs: {len(relevant_jobs)}")

        matching_text_lines = get_matching_text_lines(page_text)
        if matching_text_lines:
            print("  Page text job-like samples:")
            for line in matching_text_lines:
                print(f"    - {line}")

        if job_url_count == 0 and usable_link_samples:
            print("  Usable link samples:")
            for sample in usable_link_samples:
                print(f"    - {sample['title']}")
                print(f"      {sample['url']}")

        if possible_job_link_samples:
            print("  Possible job link samples:")
            for sample in possible_job_link_samples:
                print(f"    - {sample['title']}")
                print(f"      {sample['url']}")

        if job_url_samples:
            print("  Job-like URL samples:")
            for sample in job_url_samples:
                print(f"    - {sample['title']}")
                print(f"      {sample['url']}")

        if location_match_samples:
            print("  Location match samples:")
            for sample in location_match_samples:
                print(f"    - {sample['title']}")
                print(f"      Matched location: {sample['matched_location']}")
                print(f"      {sample['url']}")

        if keyword_match_samples:
            print("  Keyword match samples:")
            for sample in keyword_match_samples:
                print(f"    - {sample['title']}")
                print(f"      Matched location: {sample['matched_location']}")
                print(f"      Matched keyword: {sample['matched_keyword']}")
                print(f"      Verification: {sample['verification_state']}")
                print(f"      {sample['url']}")

        if detail_verified_samples:
            print("  Detail verified samples:")
            for sample in detail_verified_samples:
                print(f"    - {sample['title']}")
                print(f"      Final URL: {sample['final_url']}")
                print(f"      Page title: {sample['page_title']}")
                print(f"      Body length: {sample['body_length']}")
                if sample["error"]:
                    print(f"      Error: {sample['error']}")

        if detail_failure_samples:
            print("  Detail failure samples:")
            for sample in detail_failure_samples:
                print(f"    - {sample['title']}")
                print(f"      Reason: {sample['reason']}")
                print(f"      Requested URL: {sample['requested_url']}")
                print(f"      Final URL: {sample['final_url']}")
                print(f"      Page title: {sample['page_title']}")
                print(f"      Body length: {sample['body_length']}")

    return relevant_jobs
