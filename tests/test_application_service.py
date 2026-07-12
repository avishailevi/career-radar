import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services import application_service


class ApplicationServiceTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.history_path = Path(self.temp_dir.name) / "data" / "job_history.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_run_scan_returns_structured_result_and_persists_latest_scan(self):
        jobs = [
            {
                "company": "Apple",
                "title": "ASIC Engineer",
                "url": "https://apple.test/1",
                "matched_keyword": "ASIC",
                "matched_location": "Israel",
                "match_confidence": "high",
                "relevance_score": 92,
            }
        ]
        scan_health = [{"company": "Apple", "status": "success_with_jobs"}]

        with patch(
            "services.application_service.get_companies_to_scan",
            return_value=[{"name": "Apple"}],
        ):
            with patch(
                "services.application_service.scan_companies",
                return_value=(jobs, scan_health),
            ):
                with patch("services.application_service.send_email_digest") as send_email:
                    result = application_service.run_scan(
                        history_path=self.history_path,
                    )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["companies_scanned"], 1)
        self.assertEqual(result["relevant_jobs_count"], 1)
        self.assertEqual(result["summary"]["new_jobs_count"], 1)
        self.assertEqual(result["visible_new_jobs"][0]["company"], "Apple")
        send_email.assert_called_once_with(result["visible_new_jobs"])

        latest_jobs = application_service.get_latest_new_jobs(self.history_path)
        latest_summary = application_service.get_latest_scan_summary(self.history_path)

        self.assertEqual(latest_jobs[0]["title"], "ASIC Engineer")
        self.assertEqual(latest_jobs[0]["match_confidence"], "high")
        self.assertEqual(latest_jobs[0]["relevance_score"], 92)
        self.assertEqual(latest_summary["companies_scanned"], 1)

    def test_scan_companies_isolates_company_failures(self):
        companies = [{"name": "Apple"}, {"name": "BrokenCo"}]

        with patch(
            "services.application_service.scan_company",
            side_effect=[
                [
                    {
                        "company": "Apple",
                        "title": "ASIC Engineer",
                        "url": "https://apple.test/1",
                    }
                ],
                RuntimeError("scanner failed"),
            ],
        ):
            jobs, scan_health = application_service.scan_companies(companies)

        self.assertEqual(len(jobs), 1)
        self.assertEqual(
            scan_health,
            [
                {"company": "Apple", "status": "success_with_jobs"},
                {"company": "BrokenCo", "status": "failed"},
            ],
        )

    def test_concurrent_scan_is_prevented(self):
        application_service._scan_lock.acquire()
        try:
            result = application_service.run_scan(history_path=self.history_path)
        finally:
            application_service._scan_lock.release()

        self.assertEqual(result["status"], "already_running")
        self.assertIn("already in progress", result["message"])

    def test_latest_new_jobs_hide_dismissed_jobs(self):
        jobs = [
            {
                "company": "Apple",
                "title": "ASIC Engineer",
                "url": "https://apple.test/1",
                "matched_keyword": "ASIC",
                "matched_location": "Israel",
            }
        ]

        with patch(
            "services.application_service.get_companies_to_scan",
            return_value=[{"name": "Apple"}],
        ):
            with patch(
                "services.application_service.scan_companies",
                return_value=(jobs, [{"company": "Apple", "status": "success_with_jobs"}]),
            ):
                with patch("services.application_service.send_email_digest"):
                    result = application_service.run_scan(
                        history_path=self.history_path,
                    )

        job_id = result["new_jobs"][0]["job_id"][:8]
        application_service.mark_job(job_id, "dismissed", self.history_path)

        self.assertEqual(application_service.get_latest_new_jobs(self.history_path), [])


if __name__ == "__main__":
    unittest.main()
