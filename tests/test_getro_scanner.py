import unittest
from unittest.mock import patch

from scanners.getro_scanner import GetroScanner
from scanners.getro_scanner import get_jobs_from_response


class GetroScannerTest(unittest.TestCase):
    def test_get_jobs_from_response_reads_results(self):
        response = {
            "results": {
                "count": 1,
                "jobs": [{"title": "Hardware System Engineer"}],
            }
        }

        jobs, total = get_jobs_from_response(response)

        self.assertEqual(jobs, [{"title": "Hardware System Engineer"}])
        self.assertEqual(total, 1)

    def test_scan_filters_by_keyword_and_location(self):
        company = {
            "name": "Rafael",
            "platform": "getro",
            "url": "https://jobs.lhh.co.il/companies/rafael-advanced-defense-systems",
            "network_id": "1200",
            "organization_id": 23055,
        }
        response = {
            "results": {
                "count": 2,
                "jobs": [
                    {
                        "title": "Hardware System Engineer",
                        "url": "https://example.com/job/1",
                        "locations": ["North District, Israel"],
                        "organization": {
                            "industry_tags": ["Manufacturing"],
                        },
                    },
                    {
                        "title": "Marketing Manager",
                        "url": "https://example.com/job/2",
                        "locations": ["Haifa, Israel"],
                        "organization": {
                            "industry_tags": ["Marketing"],
                        },
                    },
                ],
            }
        }

        with patch("scanners.getro_scanner.fetch_jobs_page", return_value=response):
            jobs = GetroScanner().scan(company)

        self.assertEqual(
            jobs,
            [
                {
                    "company": "Rafael",
                    "title": "Hardware System Engineer",
                    "url": "https://example.com/job/1",
                    "matched_keyword": "Hardware",
                    "matched_location": "North District, Israel",
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
