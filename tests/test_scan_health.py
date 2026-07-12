import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import main
from services import application_service


class ScanHealthTest(unittest.TestCase):
    def test_scan_companies_tracks_success_zero_and_failed_statuses(self):
        companies = [
            {"name": "Apple"},
            {"name": "Broadcom"},
            {"name": "Marvell"},
        ]
        apple_jobs = [
            {
                "company": "Apple",
                "title": "Physical Design Engineer",
                "url": "https://apple.test/job/1",
                "matched_keyword": "Physical Design",
                "matched_location": "Israel",
            }
        ]

        def scan_company(company):
            if company["name"] == "Apple":
                return apple_jobs
            if company["name"] == "Broadcom":
                return []
            raise RuntimeError("scan failed")

        with patch("services.application_service.scan_company", side_effect=scan_company):
            jobs, scan_health = application_service.scan_companies(companies)

        self.assertEqual(jobs, apple_jobs)
        self.assertEqual(
            scan_health,
            [
                {"company": "Apple", "status": "success_with_jobs"},
                {"company": "Broadcom", "status": "success_zero_jobs"},
                {"company": "Marvell", "status": "failed"},
            ],
        )

    def test_daily_summary_prints_scan_health(self):
        scan_health = [
            {"company": "Apple", "status": "success_with_jobs"},
            {"company": "Broadcom", "status": "success_zero_jobs"},
            {"company": "Marvell", "status": "failed"},
        ]
        output = io.StringIO()

        with redirect_stdout(output):
            main.print_daily_summary(
                companies_scanned=3,
                relevant_jobs_count=1,
                new_jobs=[],
                previously_seen_count=1,
                scan_health=scan_health,
            )

        text = output.getvalue()

        self.assertIn("Companies scanned: 3", text)
        self.assertIn("Companies with relevant jobs: 1 (Apple)", text)
        self.assertIn("Companies with zero relevant jobs: 1 (Broadcom)", text)
        self.assertIn("Failed companies: 1 (Marvell)", text)
        self.assertIn("Relevant jobs: 1", text)
        self.assertIn("NEW jobs: 0", text)
        self.assertIn("Previously seen jobs: 1", text)


if __name__ == "__main__":
    unittest.main()
