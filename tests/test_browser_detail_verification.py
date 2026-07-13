import unittest

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from audit_companies import classify_result
from scanner import DETAIL_FAILED
from scanner import DETAIL_VERIFIED
from scanner import LISTING_FALLBACK
from scanner import DetailReadResult
from scanner import get_job_detail_result
from scanner import get_job_verification_state


class FakeBodyLocator:
    def __init__(self, text: str, error: Exception | None = None):
        self.text = text
        self.error = error

    def inner_text(self, timeout: int) -> str:
        if self.error:
            raise self.error

        return self.text


class FakePage:
    def __init__(
        self,
        *,
        body_text: str = "",
        page_title: str = "",
        final_url: str = "https://careers.example.com/job/example",
        goto_error: Exception | None = None,
        body_error: Exception | None = None,
    ):
        self.body_text = body_text
        self.page_title = page_title
        self.url = final_url
        self.goto_error = goto_error
        self.body_error = body_error
        self.closed = False

    def goto(self, url: str, wait_until: str, timeout: int) -> None:
        if self.goto_error:
            raise self.goto_error

    def wait_for_load_state(self, state: str, timeout: int) -> None:
        return None

    def wait_for_timeout(self, timeout: int) -> None:
        return None

    def wait_for_selector(self, selector: str, timeout: int) -> None:
        return None

    def wait_for_function(self, expression: str, arg: list, timeout: int) -> None:
        return None

    def locator(self, selector: str) -> FakeBodyLocator:
        return FakeBodyLocator(self.body_text, self.body_error)

    def evaluate(self, script: str) -> str:
        return self.body_text

    def title(self) -> str:
        return self.page_title

    def close(self) -> None:
        self.closed = True


class FakeContext:
    def __init__(self, page: FakePage):
        self.page = page

    def new_page(self) -> FakePage:
        return self.page


def meaningful_body(title: str) -> str:
    return (
        f"{title}\n"
        "locations\nIsrael\n"
        "job description\n"
        "We are looking for an engineer to own design verification, "
        "requirements, architecture reviews, implementation planning, "
        "debug, and collaboration with hardware teams. "
        * 8
    )


def counters(**overrides):
    values = {
        "job_like_urls": 0,
        "location_matches": 0,
        "keyword_matches": 0,
        "relevant_jobs": 0,
        "detail_pages_checked": 0,
        "detail_pages_attempted": 0,
        "detail_pages_verified": 0,
        "detail_pages_failed": 0,
        "empty_detail_pages": 0,
        "page_text_fallbacks": 0,
        "listing_fallbacks_used": 0,
        "detail_keyword_matches": 0,
    }
    values.update(overrides)
    return values


class BrowserDetailVerificationTest(unittest.TestCase):
    def test_successful_verified_detail_page_extraction(self):
        title = "Formal Verification Engineer"
        page = FakePage(body_text=meaningful_body(title), page_title=title)

        result = get_job_detail_result(FakeContext(page), page.url, title)

        self.assertEqual(result.status, "verified")
        self.assertIn(title, result.text)
        self.assertTrue(page.closed)

    def test_navigation_failure_is_reported(self):
        page = FakePage(goto_error=PlaywrightError("navigation failed"))

        result = get_job_detail_result(FakeContext(page), page.url, "ASIC Engineer")

        self.assertEqual(result.status, "navigation_error")

    def test_timeout_is_reported(self):
        page = FakePage(goto_error=PlaywrightTimeoutError("timed out"))

        result = get_job_detail_result(FakeContext(page), page.url, "ASIC Engineer")

        self.assertEqual(result.status, "timeout")

    def test_empty_body_is_reported(self):
        page = FakePage(body_text="", page_title="ASIC Engineer")

        result = get_job_detail_result(FakeContext(page), page.url, "ASIC Engineer")

        self.assertEqual(result.status, "empty_body")

    def test_redirect_to_generic_listing_page_is_not_verified(self):
        title = "ASIC Engineer"
        page = FakePage(
            body_text=meaningful_body(title),
            page_title="Careers",
            final_url="https://careers.example.com/",
        )

        result = get_job_detail_result(FakeContext(page), page.url, title)

        self.assertEqual(result.status, "redirected_away_from_job_detail")

    def test_generic_navigation_shell_is_not_verified(self):
        body = (
            "Careers Home Search Jobs Sign In Privacy Contact "
            "Teams Locations Benefits "
            * 30
        )
        page = FakePage(body_text=body, page_title="Careers")

        result = get_job_detail_result(FakeContext(page), page.url, "ASIC Engineer")

        self.assertEqual(result.status, "invalid_or_generic_page")

    def test_valid_job_page_requires_title_and_description_signal(self):
        title = "Board Design Engineer"
        page = FakePage(
            body_text=meaningful_body(title),
            page_title=f"{title} - Careers",
        )

        result = get_job_detail_result(FakeContext(page), page.url, title)

        self.assertEqual(result.status, "verified")

    def test_listing_card_fallback_is_classified_separately(self):
        result = DetailReadResult(
            text="",
            requested_url="https://careers.example.com/job/1",
            final_url="https://careers.example.com/job/1",
            status="empty_body",
        )

        self.assertEqual(
            get_job_verification_state(True, result, True),
            LISTING_FALLBACK,
        )
        self.assertEqual(
            get_job_verification_state(True, result, False),
            DETAIL_FAILED,
        )
        self.assertEqual(
            get_job_verification_state(
                True,
                DetailReadResult(
                    text=meaningful_body("ASIC Engineer"),
                    requested_url="https://careers.example.com/job/1",
                    final_url="https://careers.example.com/job/1",
                    status="verified",
                ),
                False,
            ),
            DETAIL_VERIFIED,
        )

    def test_audit_does_not_mark_fallback_only_browser_scan_supported(self):
        status = classify_result(
            jobs=[{"title": "ASIC Engineer"}],
            counters=counters(
                detail_pages_attempted=2,
                detail_pages_failed=2,
                listing_fallbacks_used=2,
                detail_keyword_matches=0,
            ),
            error=None,
        )

        self.assertEqual(status, "FALLBACK_ONLY")

    def test_audit_supports_browser_scan_with_detail_verified_match(self):
        status = classify_result(
            jobs=[{"title": "ASIC Engineer"}],
            counters=counters(
                detail_pages_attempted=2,
                detail_pages_verified=1,
                detail_keyword_matches=1,
            ),
            error=None,
        )

        self.assertEqual(status, "SUPPORTED")

    def test_static_json_and_api_backed_classification_remains_supported(self):
        for platform in ["static_json", "eightfold", "comeet", "getro"]:
            with self.subTest(platform=platform):
                status = classify_result(
                    jobs=[{"title": "ASIC Engineer"}],
                    counters=counters(),
                    error=None,
                    platform=platform,
                )

                self.assertEqual(status, "SUPPORTED")

    def test_browser_listing_without_detail_evidence_is_fallback_only(self):
        status = classify_result(
            jobs=[{"title": "ASIC Engineer"}],
            counters=counters(),
            error=None,
            platform="custom",
        )

        self.assertEqual(status, "FALLBACK_ONLY")


if __name__ == "__main__":
    unittest.main()
