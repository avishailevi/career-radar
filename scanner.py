import re
from urllib.parse import urljoin

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

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
]


JOB_URL_HINTS = [
    "/job/",
    "/jobs/",
    "/careers/job",
    "jobid",
    "job_id",
    "job-",
    "jobdetails?jobseqno",
    "jobs.apple.com",
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
    "/products/",
    "/support/",
    "/training/",
    "/solutions/",
    "/applications/",
    "/sustainability",
    "/environmental-social",
    "/corporate-responsibility",
]


DETAIL_TEXT_PLATFORMS = {
    "microsoft",
}

DEBUG_SAMPLE_LIMIT = 5


def is_bad_title(title: str) -> bool:
    title_lower = title.lower()
    return any(bad in title_lower for bad in BAD_TITLES)


def is_bad_url(url: str) -> bool:
    url_lower = url.lower()
    return any(bad in url_lower for bad in BAD_URL_PARTS)


def is_job_url(url: str) -> bool:
    url_lower = url.lower()
    return any(hint in url_lower for hint in JOB_URL_HINTS)


def is_possible_job_link(title: str, url: str) -> bool:
    text = f"{title} {url}".lower()
    return any(hint in text for hint in POSSIBLE_JOB_TEXT_HINTS)


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


def should_read_detail_pages(company: dict) -> bool:
    return company.get("platform") in DETAIL_TEXT_PLATFORMS


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
        return detail_page.locator("body").inner_text(timeout=10000)

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

    for link_text in link_texts:
        try:
            link = page.get_by_role("link", name=link_text).first
            if link.count() == 0:
                continue

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

    total_links = 0
    usable_links = 0
    bad_title_count = 0
    bad_url_count = 0
    job_url_count = 0
    location_match_count = 0
    keyword_match_count = 0
    detail_page_count = 0
    detail_keyword_match_count = 0
    page_url = ""
    page_title = ""
    page_text = ""
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

        links = page.locator("a").all()
        total_links = len(links)

        for link in links:
            try:
                title = link.inner_text().strip()
                href = link.get_attribute("href")

                if not title or not href:
                    continue

                usable_links += 1
                full_url = urljoin(company["url"], href)

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
                text_to_check = f"{title} {full_url}"

                add_debug_sample(
                    job_url_samples,
                    {
                        "title": title,
                        "url": full_url,
                    },
                )

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

                if not matched_keyword and read_detail_pages:
                    detail_text = get_job_detail_text(page.context, full_url)

                    if detail_text:
                        detail_page_count += 1
                        text_to_check = f"{text_to_check} {detail_text}"
                        matched_keyword = find_matching_keyword(text_to_check)

                        if matched_keyword:
                            detail_keyword_match_count += 1

                if not matched_keyword:
                    continue

                keyword_match_count += 1

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

        if read_detail_pages:
            print(f"  Detail pages checked: {detail_page_count}")
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
