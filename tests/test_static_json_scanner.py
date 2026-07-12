import unittest
from unittest.mock import patch

from scanners.static_json_scanner import StaticJsonScanner
from scanners.static_json_scanner import clean_text
from scanners.static_json_scanner import get_location
from scanners.static_json_scanner import get_job_url


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

    def test_get_job_url_uses_full_direct_url_field(self):
        company = {
            "url": "https://careers.example.com/",
            "url_fields": ["applyUrl"],
            "id_field": "jobId",
            "url_template": "https://careers.example.com/jobs/{id}",
        }
        job = {
            "jobId": 17,
            "applyUrl": "https://careers.example.com/direct/17",
        }

        self.assertEqual(
            get_job_url(company, job),
            "https://careers.example.com/direct/17",
        )

    def test_get_job_url_resolves_relative_job_path(self):
        company = {
            "url": "https://careers.example.com/base/",
            "relative_url_fields": ["path"],
            "id_field": "jobId",
        }
        job = {"jobId": 17, "path": "/job/17"}

        self.assertEqual(
            get_job_url(company, job),
            "https://careers.example.com/job/17",
        )

    def test_get_job_url_uses_verified_job_id_template(self):
        company = {
            "url": "https://elbitsystemscareer.com/",
            "id_field": "jobId",
            "url_template": "https://elbitsystemscareer.com/job?jid={id}",
        }
        job = {"jobId": 20199}

        self.assertEqual(
            get_job_url(company, job),
            "https://elbitsystemscareer.com/job?jid=20199",
        )

    def test_get_job_url_falls_back_to_company_url_without_usable_url(self):
        company = {
            "url": "https://careers.example.com/",
            "url_fields": ["url"],
            "id_field": "jobId",
            "url_template": "https://careers.example.com/jobs/{id}",
        }
        job = {"url": "not a url"}

        self.assertEqual(get_job_url(company, job), "https://careers.example.com/")

    def test_two_elbit_jobs_produce_different_direct_urls(self):
        company = {
            "url": "https://elbitsystemscareer.com/",
            "id_field": "jobId",
            "url_template": "https://elbitsystemscareer.com/job?jid={id}",
        }

        self.assertEqual(
            [
                get_job_url(company, {"jobId": 20199}),
                get_job_url(company, {"jobId": 20739}),
            ],
            [
                "https://elbitsystemscareer.com/job?jid=20199",
                "https://elbitsystemscareer.com/job?jid=20739",
            ],
        )

    def test_elbit_direct_url_is_not_general_search_page(self):
        company = {
            "url": "https://elbitsystemscareer.com/",
            "id_field": "jobId",
            "url_template": "https://elbitsystemscareer.com/job?jid={id}",
        }
        url = get_job_url(company, {"jobId": 20199})

        self.assertIn("/job?jid=20199", url)
        self.assertNotIn("page=search", url)

    def test_iai_static_json_url_template_is_unchanged(self):
        company = {
            "url": "https://jobs.iai.co.il/jobs/",
            "id_field": "id",
            "url_template": "https://jobs.iai.co.il/job/{id}",
        }

        self.assertEqual(
            get_job_url(company, {"id": "76043122"}),
            "https://jobs.iai.co.il/job/76043122",
        )


if __name__ == "__main__":
    unittest.main()
