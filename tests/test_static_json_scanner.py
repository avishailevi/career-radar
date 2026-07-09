import unittest
from unittest.mock import patch

from scanners.static_json_scanner import StaticJsonScanner
from scanners.static_json_scanner import clean_text
from scanners.static_json_scanner import get_location


class StaticJsonScannerTest(unittest.TestCase):
    def test_clean_text_removes_html(self):
        text = clean_text("Hardware&lt;div&gt;#Haifa&lt;/div&gt;")

        self.assertEqual(text, "Hardware #Haifa")

    def test_get_location_uses_configured_location_field(self):
        company = {"location_fields": ["city"], "text_fields": ["description"]}
        job = {"city": "יהוד", "description": "FPGA"}

        self.assertEqual(get_location(company, job), "יהוד")

    def test_get_location_extracts_english_hashtag_from_text(self):
        company = {"location_fields": [], "text_fields": ["description"]}
        job = {"description": "דרוש.ה Hardware Engineer #Rehovot"}

        self.assertEqual(get_location(company, job), "Rehovot")

    def test_scan_returns_relevant_json_feed_jobs(self):
        company = {
            "name": "Elbit",
            "platform": "static_json",
            "url": "https://elbitsystemscareer.com/",
            "feed_url": "https://example.com/jobs.json",
            "id_field": "jobId",
            "title_field": "jobTitle",
            "location_fields": ["locationAddress"],
            "text_fields": ["jobTitle", "description"],
            "url_template": "https://example.com/jobs/{id}",
            "default_location": "Israel",
            "allowed_field_values": {"categoryId": [1]},
        }
        feed = [
            {
                "jobId": 1,
                "jobTitle": "Hardware Engineer",
                "locationAddress": "",
                "description": "Board Design #Haifa",
                "categoryId": 1,
            },
            {
                "jobId": 2,
                "jobTitle": "Accountant",
                "locationAddress": "Haifa",
                "description": "Finance",
                "categoryId": 1,
            },
            {
                "jobId": 3,
                "jobTitle": "Hardware Marketing Manager",
                "locationAddress": "Haifa",
                "description": "Hardware",
                "categoryId": 8,
            },
        ]

        with patch("scanners.static_json_scanner.fetch_json", return_value=feed):
            jobs = StaticJsonScanner().scan(company)

        self.assertEqual(
            jobs,
            [
                {
                    "company": "Elbit",
                    "title": "Hardware Engineer",
                    "url": "https://example.com/jobs/1",
                    "matched_keyword": "Board Design",
                    "matched_location": "Haifa",
                    "relevance_score": 85,
                    "match_confidence": "high",
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
