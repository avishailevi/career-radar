from urllib.parse import urljoin

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from services.filter_service import POSSIBLE_JOB_TEXT_HINTS
from services.filter_service import find_matching_keyword
from services.filter_service import find_matching_location
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


def get_job_detail_text(context, url: str) -> str:
    detail_page = None

    try:
        detail_page = context.new_page()
        detail_page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=45000,
        )

        try:
            detail_page.wait_for_load_state("networkidle", timeout=15000)
        except PlaywrightError:
            pass

        detail_page.wait_for_timeout(2000)
        return detail_page.locator("body").inner_text(timeout=10000).strip()

    except PlaywrightError:
        return ""

    finally:
        if detail_page:
            try:
                detail_page.close()
            except PlaywrightError:
                pass


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
    page_text_fallback_count = 0
    detail_keyword_match_count = 0
    page_url = ""
    page_title = ""
    page_text = ""
    link_base_url = ""
    followed_link_text = None
    read_detail_pages = should_read_detail_pages(company)

    usable_link_samples = []
    possible_job_link_samples = []
    job_url_samples = []
    location_match_samples = []
    keyword_match_samples = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

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
                title = link.inner_text().strip()
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
                text_to_check = title
                matched_from_detail = False

                add_debug_sample(
                    job_url_samples,
                    {
                        "title": title,
                        "url": full_url,
                    },
                )

                if read_detail_pages:
                    detail_page_count += 1
                    detail_text = get_job_detail_text(page.context, full_url)

                    if detail_text:
                        matched_from_detail = True
                        text_to_check = f"{text_to_check} {detail_text}"
                    else:
                        empty_detail_page_count += 1
                        card_text = get_job_card_text(page_text, title)

                        if card_text:
                            page_text_fallback_count += 1
                            text_to_check = f"{text_to_check} {card_text}"

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

                matched_keyword = find_matching_keyword(text_to_check)

                if not matched_keyword:
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

                add_debug_sample(
                    keyword_match_samples,
                    {
                        "title": title,
                        "url": full_url,
                        "matched_location": matched_location,
                        "matched_keyword": matched_keyword,
                    },
                )

                relevant_jobs.append(
                    {
                        "company": company["name"],
                        "title": title,
                        "url": full_url,
                        "matched_keyword": matched_keyword,
                    }
                )

            except Exception:
                continue

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
            print(f"  Empty detail pages: {empty_detail_page_count}")
            print(f"  Page text fallbacks: {page_text_fallback_count}")
            print(f"  Detail keyword matches: {detail_keyword_match_count}")

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
                print(f"      {sample['url']}")

    return relevant_jobs
