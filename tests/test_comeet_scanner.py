import json
import unittest
from unittest.mock import patch

from scanners.comeet_scanner import ComeetScanner
from scanners.comeet_scanner import parse_positions


class ComeetScannerTest(unittest.TestCase):
    def test_parse_positions_reads_embedded_company_positions(self):
        positions = [{"name": "Hardware Engineer"}]
        html = (
            "<script>COMPANY_POSITIONS_DATA = "
            f"{json.dumps(positions)}; POSITION_DATA = null;</script>"
        )

        self.assertEqual(parse_positions(html), positions)

    def test_scan_filters_by_country_department_and_keyword(self):
        company = {
            "name": "Nova",
            "platform": "comeet",
            "url": "https://www.comeet.com/jobs/nova/A5.007",
            "country": "IL",
            "allowed_departments": ["Engineering"],
        }
        positions = [
            {
                "name": "NPI Electronic Engineer",
                "department": "Engineering",
                "location": {
                    "country": "IL",
                    "city": "Rehovot",
                    "name": "Rehovot, IL",
                },
                "url_comeet_hosted_page": "https://example.com/job/1",
            },
            {
                "name": "Product Marketing Manager",
                "department": "Marketing",
                "location": {
                    "country": "IL",
                    "city": "Rehovot",
                    "name": "Rehovot, IL",
                },
                "url_comeet_hosted_page": "https://example.com/job/2",
            },
            {
                "name": "Hardware Engineer",
                "department": "Engineering",
                "location": {
                    "country": "JP",
                    "city": "Chitose",
                    "name": "Chitose, JP",
                },
                "url_comeet_hosted_page": "https://example.com/job/3",
            },
        ]
        html = (
            "<script>COMPANY_POSITIONS_DATA = "
            f"{json.dumps(positions)}; POSITION_DATA = null;</script>"
        )

        with patch("scanners.comeet_scanner.fetch_html", return_value=html):
            jobs = ComeetScanner().scan(company)

        self.assertEqual(
            jobs,
            [
                {
                    "company": "Nova",
                    "title": "NPI Electronic Engineer",
                    "url": "https://example.com/job/1",
                    "matched_keyword": "Electronic",
                    "matched_location": "Rehovot",
                    "relevance_score": 60,
                    "match_confidence": "medium",
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
