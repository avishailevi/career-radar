import unittest
from unittest.mock import patch

from scanners.eightfold_scanner import EightfoldScanner
from scanners.eightfold_scanner import get_eightfold_domain
from scanners.eightfold_scanner import get_search_url


class EightfoldScannerTest(unittest.TestCase):
    def test_get_eightfold_domain_uses_configured_domain(self):
        company = {
            "url": "https://careers.qualcomm.com/",
            "domain": "qualcomm.com",
        }

        self.assertEqual(get_eightfold_domain(company), "qualcomm.com")

    def test_get_eightfold_domain_derives_from_careers_host(self):
        company = {"url": "https://careers.example.com/"}

        self.assertEqual(get_eightfold_domain(company), "example.com")

    def test_get_search_url_uses_israel_location(self):
        company = {
            "url": "https://careers.qualcomm.com/",
            "domain": "qualcomm.com",
            "search_location": "Israel",
        }

        url = get_search_url(company, 10)

        self.assertEqual(
            url,
            "https://careers.qualcomm.com/api/pcsx/search?"
            "domain=qualcomm.com&query=&location=Israel&start=10&",
        )

    def test_scan_returns_relevant_israel_jobs(self):
        company = {
            "name": "Qualcomm",
            "platform": "eightfold",
            "url": "https://careers.qualcomm.com/",
            "domain": "qualcomm.com",
            "search_location": "Israel",
        }
        response = {
            "data": {
                "positions": [
                    {
                        "id": 1,
                        "name": "Senior RTL Design Engineer",
                        "department": "Hardware Engineering",
                        "locations": ["Haifa, Haifa District, Israel"],
                        "standardizedLocations": ["Haifa, Haifa District, IL"],
                        "positionUrl": "/careers/job/1",
                    },
                    {
                        "id": 2,
                        "name": "Sales Manager",
                        "department": "Sales",
                        "locations": ["Haifa, Haifa District, Israel"],
                        "standardizedLocations": ["Haifa, Haifa District, IL"],
                        "positionUrl": "/careers/job/2",
                    },
                    {
                        "id": 3,
                        "name": "ASIC Engineer",
                        "department": "Hardware Engineering",
                        "locations": ["Chennai, Tamil Nadu, India"],
                        "standardizedLocations": ["Chennai, TN, IN"],
                        "positionUrl": "/careers/job/3",
                    },
                ]
            }
        }

        with patch("scanners.eightfold_scanner.fetch_json", return_value=response):
            jobs = EightfoldScanner().scan(company)

        self.assertEqual(
            jobs,
            [
                {
                    "company": "Qualcomm",
                    "title": "Senior RTL Design Engineer",
                    "url": "https://careers.qualcomm.com/careers/job/1",
                    "matched_keyword": "RTL",
                    "matched_location": "Israel",
                    "relevance_score": 75,
                    "match_confidence": "high",
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
