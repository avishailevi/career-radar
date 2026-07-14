import unittest
from unittest.mock import patch

from scanner import DETAIL_VERIFIED
from scanner import LISTING_FALLBACK
from scanner import DetailReadResult
from scanners.workday_scanner import WorkdayCandidate
from scanners.workday_scanner import WorkdayScanner
from scanners.workday_scanner import WorkdaySite
from scanners.workday_scanner import build_workday_job_url
from scanners.workday_scanner import build_workday_jobs
from scanners.workday_scanner import discover_workday_candidates
from scanners.workday_scanner import get_candidate_from_posting
from scanners.workday_scanner import get_israel_applied_facets
from scanners.workday_scanner import get_workday_requisition_id
from scanners.workday_scanner import get_workday_search_url
from scanners.workday_scanner import get_workday_site
from scanners.workday_scanner import sort_workday_candidates


def company(**overrides):
    data = {
        "name": "Example",
        "platform": "workday",
        "url": "https://example.wd1.myworkdayjobs.com/en-US/External",
    }
    data.update(overrides)
    return data


def posting(title, external_path, location="Israel", job_id="JR1"):
    return {
        "title": title,
        "externalPath": external_path,
        "locationsText": location,
        "bulletFields": [job_id],
        "postedOn": "Posted Today",
    }


def detail_result(title, body_location="Israel", status="verified"):
    return DetailReadResult(
        text=(
            f"{title}\nJob Description\nResponsibilities\nRequirements\n"
            f"ASIC verification and hardware design role in {body_location}."
        ),
        requested_url="https://example.com/job",
        final_url="https://example.com/job",
        status=status,
        page_title=title,
    )


class WorkdayScannerTests(unittest.TestCase):
    def test_get_workday_site_ignores_locale_path(self):
        site = get_workday_site(company())

        self.assertEqual(site.base_url, "https://example.wd1.myworkdayjobs.com")
        self.assertEqual(site.tenant, "example")
        self.assertEqual(site.site, "External")
        self.assertEqual(
            get_workday_search_url(site),
            "https://example.wd1.myworkdayjobs.com/wday/cxs/example/External/jobs",
        )

    def test_configured_workday_url_supports_corporate_landing_page(self):
        site = get_workday_site(
            company(
                url="https://www.example.com/careers",
                workday_url="https://example.wd1.myworkdayjobs.com/External",
            )
        )

        self.assertEqual(site.site, "External")

    def test_build_workday_job_url_uses_canonical_external_path(self):
        site = WorkdaySite(
            base_url="https://example.wd1.myworkdayjobs.com",
            tenant="example",
            site="External",
        )

        self.assertEqual(
            build_workday_job_url(site, "/job/Israel/ASIC-Engineer_JR1"),
            (
                "https://example.wd1.myworkdayjobs.com/External/job/Israel/"
                "ASIC-Engineer_JR1"
            ),
        )

    def test_candidate_uses_direct_url_for_display_and_requisition_for_identity(self):
        site = WorkdaySite(
            base_url="https://example.wd1.myworkdayjobs.com",
            tenant="example",
            site="External",
        )
        candidate = get_candidate_from_posting(
            site,
            posting(
                "ASIC Engineer",
                "/job/Israel/ASIC-Engineer_JR1234",
                job_id="JR1234",
            ),
            0,
        )

        self.assertEqual(
            candidate.url,
            (
                "https://example.wd1.myworkdayjobs.com/External/job/Israel/"
                "ASIC-Engineer_JR1234"
            ),
        )
        self.assertEqual(candidate.identity_url, "workday://example/jr1234")
        self.assertIn("JR1234", candidate.source_text)

    def test_candidate_without_usable_requisition_falls_back_to_display_url(self):
        site = WorkdaySite(
            base_url="https://example.wd1.myworkdayjobs.com",
            tenant="example",
            site="External",
        )
        candidate = get_candidate_from_posting(
            site,
            posting(
                "ASIC Engineer",
                "/job/Israel/ASIC-Engineer",
                job_id="Spotlight Job",
            ),
            0,
        )

        self.assertEqual(candidate.identity_url, candidate.url)
        self.assertEqual(candidate.job_id, "")

    def test_requisition_id_ignores_non_id_bullet_fields(self):
        self.assertEqual(
            get_workday_requisition_id(
                {
                    "bulletFields": ["Spotlight Job", "JR0283670"],
                    "externalPath": "/job/Israel/ASIC-Engineer_JR9999999",
                }
            ),
            "JR0283670",
        )

    def test_requisition_id_falls_back_to_external_path(self):
        self.assertEqual(
            get_workday_requisition_id(
                {
                    "bulletFields": ["Spotlight Job"],
                    "externalPath": "/job/Israel/ASIC-Engineer_R026223-4",
                }
            ),
            "R026223-4",
        )

    def test_discovery_reads_pages_until_empty_page(self):
        pages = {
            0: {
                "total": 2,
                "jobPostings": [
                    posting("ASIC Engineer", "/job/Israel/ASIC-Engineer_JR1"),
                ],
            },
            1: {
                "total": 2,
                "jobPostings": [
                    posting("FPGA Engineer", "/job/Israel/FPGA-Engineer_JR2"),
                ],
            },
        }

        with patch(
            "scanners.workday_scanner.fetch_workday_page",
            side_effect=lambda site, offset, limit, facets=None: pages[offset],
        ):
            candidates, diagnostics = discover_workday_candidates(
                company(),
                max_pages=5,
                page_limit=1,
            )

        self.assertEqual([candidate.title for candidate in candidates], [
            "ASIC Engineer",
            "FPGA Engineer",
        ])
        self.assertEqual(diagnostics["requests_made"], 2)
        self.assertFalse(diagnostics["pagination_cap_reached"])

    def test_discovery_reports_pagination_cap(self):
        with patch(
            "scanners.workday_scanner.fetch_workday_page",
            return_value={
                "total": 100,
                "jobPostings": [
                    posting("ASIC Engineer", "/job/Israel/ASIC-Engineer_JR1"),
                ],
            },
        ):
            candidates, diagnostics = discover_workday_candidates(
                company(),
                max_pages=1,
                page_limit=1,
            )

        self.assertEqual(len(candidates), 1)
        self.assertTrue(diagnostics["pagination_cap_reached"])

    def test_discovery_deduplicates_urls_and_skips_malformed_postings(self):
        with patch(
            "scanners.workday_scanner.fetch_workday_page",
            return_value={
                "total": 3,
                "jobPostings": [
                    posting("ASIC Engineer", "/job/Israel/ASIC-Engineer_JR1"),
                    posting("ASIC Engineer", "/job/Israel/ASIC-Engineer_JR1"),
                    {"title": "Broken"},
                ],
            },
        ):
            candidates, diagnostics = discover_workday_candidates(
                company(),
                max_pages=1,
            )

        self.assertEqual(len(candidates), 1)
        self.assertEqual(diagnostics["malformed_count"], 1)

    def test_discovery_uses_israel_location_facets_when_available(self):
        calls = []

        def fake_fetch(site, offset, limit, facets=None):
            calls.append(facets)
            if facets:
                return {
                    "total": 1,
                    "jobPostings": [
                        posting("ASIC Engineer", "/job/Israel/ASIC-Engineer_JR1"),
                    ],
                }

            return {
                "total": 100,
                "facets": [
                    {
                        "facetParameter": "locations",
                        "values": [
                            {"descriptor": "United States", "id": "us"},
                            {"descriptor": "Israel", "id": "il"},
                        ],
                    }
                ],
                "jobPostings": [
                    posting("Global Engineer", "/job/US/Global-Engineer_JR9", "US"),
                ],
            }

        with patch(
            "scanners.workday_scanner.fetch_workday_page",
            side_effect=fake_fetch,
        ):
            candidates, diagnostics = discover_workday_candidates(company())

        self.assertEqual([candidate.title for candidate in candidates], [
            "ASIC Engineer",
        ])
        self.assertEqual(diagnostics["applied_facets"], {"locations": ["il"]})
        self.assertEqual(calls[1], {"locations": ["il"]})

    def test_nested_facet_groups_find_country_level_israel(self):
        applied_facets = get_israel_applied_facets(
            {
                "facets": [
                    {
                        "values": [
                            {
                                "facetParameter": "locationHierarchy1",
                                "descriptor": "Locations",
                                "values": [
                                    {"descriptor": "Israel", "id": "country-il"},
                                ],
                            },
                            {
                                "facetParameter": "locations",
                                "descriptor": "Sites",
                                "values": [
                                    {"descriptor": "Israel, Tel Aviv", "id": "site-il"},
                                ],
                            },
                        ]
                    }
                ]
            }
        )

        self.assertEqual(applied_facets, {"locationHierarchy1": ["country-il"]})

    def test_israel_candidates_are_ordered_before_global_candidates(self):
        candidates = [
            WorkdayCandidate(
                title="ASIC Engineer",
                url="https://example.com/global",
                identity_url="https://example.com/global",
                locations_text="United States",
                job_id="JR1",
                posted_on="",
                source_text="ASIC Engineer United States",
                order=0,
            ),
            WorkdayCandidate(
                title="Signal Integrity Engineer",
                url="https://example.com/israel",
                identity_url="https://example.com/israel",
                locations_text="Tel Aviv",
                job_id="JR2",
                posted_on="",
                source_text="Signal Integrity Engineer Tel Aviv",
                order=1,
            ),
        ]

        ordered = sort_workday_candidates(candidates)

        self.assertEqual(ordered[0].url, "https://example.com/israel")

    def test_ordering_is_deterministic_for_equal_candidates(self):
        candidates = [
            WorkdayCandidate(
                title="ASIC Engineer",
                url=f"https://example.com/{index}",
                identity_url=f"https://example.com/{index}",
                locations_text="Israel",
                job_id=f"JR{index}",
                posted_on="",
                source_text="ASIC Engineer Israel",
                order=index,
            )
            for index in [2, 0, 1]
        ]

        ordered_once = [candidate.url for candidate in sort_workday_candidates(candidates)]
        ordered_twice = [candidate.url for candidate in sort_workday_candidates(candidates)]

        self.assertEqual(ordered_once, ordered_twice)
        self.assertEqual(ordered_once, [
            "https://example.com/0",
            "https://example.com/1",
            "https://example.com/2",
        ])

    def test_build_jobs_reuses_detail_verified_state(self):
        candidate = WorkdayCandidate(
            title="ASIC Engineer",
            url="https://example.com/job",
            identity_url="https://example.com/job",
            locations_text="Israel",
            job_id="JR1",
            posted_on="",
            source_text="ASIC Engineer Israel",
            order=0,
        )

        jobs, diagnostics = build_workday_jobs(
            company(),
            [candidate],
            lambda url, title: detail_result(title),
        )

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["verification_state"], DETAIL_VERIFIED)
        self.assertEqual(diagnostics["detail_verified_count"], 1)

    def test_build_jobs_falls_back_to_structured_listing_on_detail_failure(self):
        candidate = WorkdayCandidate(
            title="ASIC Engineer",
            url="https://example.com/job",
            identity_url="https://example.com/job",
            locations_text="Israel",
            job_id="JR1",
            posted_on="",
            source_text="ASIC Engineer Israel",
            order=0,
        )

        jobs, diagnostics = build_workday_jobs(
            company(),
            [candidate],
            lambda url, title: detail_result(title, status="timeout"),
        )

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["verification_state"], LISTING_FALLBACK)
        self.assertEqual(diagnostics["listing_fallback_count"], 1)

    def test_failed_company_scan_returns_empty_list(self):
        with patch(
            "scanners.workday_scanner.discover_workday_candidates",
            side_effect=RuntimeError("network failed"),
        ):
            jobs = WorkdayScanner().scan(company())

        self.assertEqual(jobs, [])


if __name__ == "__main__":
    unittest.main()
