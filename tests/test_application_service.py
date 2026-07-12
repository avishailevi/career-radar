import tempfile
import unittest
import json
from pathlib import Path
from unittest.mock import patch

from services import application_service
from services.job_history_service import generate_job_id


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
        latest_relevant_jobs = application_service.get_latest_relevant_jobs(
            self.history_path,
        )
        latest_summary = application_service.get_latest_scan_summary(self.history_path)

        self.assertEqual(latest_jobs[0]["title"], "ASIC Engineer")
        self.assertEqual(latest_relevant_jobs[0]["title"], "ASIC Engineer")
        self.assertEqual(latest_jobs[0]["match_confidence"], "high")
        self.assertEqual(latest_jobs[0]["relevance_score"], 92)
        self.assertEqual(latest_summary["companies_scanned"], 1)

        latest_scan = self.read_history()["latest_scan"]
        self.assertEqual(
            latest_scan["relevant_job_ids"],
            [latest_relevant_jobs[0]["job_id"]],
        )

    def test_run_scan_stores_all_relevant_job_ids(self):
        jobs = [
            self.build_job("Apple", "High Score", "https://apple.test/1"),
            self.build_job("Intel", "Low Score", "https://intel.test/2"),
            self.build_job("NVIDIA", "Medium Score", "https://nvidia.test/3"),
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

        expected_job_ids = [
            generate_job_id(job["company"], job["title"], job["url"])
            for job in jobs
        ]
        latest_scan = self.read_history()["latest_scan"]

        self.assertEqual(result["relevant_jobs_count"], 3)
        self.assertEqual(result["summary"]["relevant_jobs_count"], 3)
        self.assertEqual(latest_scan["relevant_job_ids"], expected_job_ids)

    def test_latest_relevant_jobs_missing_metadata_is_backward_compatible(self):
        self.write_history(
            {
                "jobs": [
                    self.build_history_job(
                        "Apple",
                        "Old Job",
                        "https://apple.test/old",
                    )
                ],
                "latest_scan": {
                    "new_job_ids": [],
                    "summary": application_service.build_scan_summary(1, 1, 0, []),
                },
            }
        )

        self.assertEqual(
            application_service.get_latest_relevant_jobs(self.history_path),
            [],
        )

    def test_latest_relevant_jobs_use_relevance_ordering(self):
        low = self.build_history_job(
            "Apple",
            "Low Job",
            "https://apple.test/low",
            confidence="low",
            score=99,
        )
        high = self.build_history_job(
            "Intel",
            "High Job",
            "https://intel.test/high",
            confidence="high",
            score=50,
        )
        medium = self.build_history_job(
            "NVIDIA",
            "Medium Job",
            "https://nvidia.test/medium",
            confidence="medium",
            score=80,
        )
        self.write_history(
            {
                "jobs": [low, high, medium],
                "latest_scan": {
                    "relevant_job_ids": [
                        low["job_id"],
                        high["job_id"],
                        medium["job_id"],
                    ],
                },
            }
        )

        jobs = application_service.get_latest_relevant_jobs(self.history_path)

        self.assertEqual(
            [job["title"] for job in jobs],
            ["High Job", "Medium Job", "Low Job"],
        )

    def test_latest_relevant_jobs_hide_dismissed_jobs(self):
        visible = self.build_history_job(
            "Apple",
            "Visible Job",
            "https://apple.test/visible",
        )
        dismissed = self.build_history_job(
            "Intel",
            "Dismissed Job",
            "https://intel.test/dismissed",
            triage_state="dismissed",
        )
        self.write_history(
            {
                "jobs": [visible, dismissed],
                "latest_scan": {
                    "relevant_job_ids": [
                        dismissed["job_id"],
                        visible["job_id"],
                    ],
                },
            }
        )

        jobs = application_service.get_latest_relevant_jobs(self.history_path)

        self.assertEqual([job["title"] for job in jobs], ["Visible Job"])

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

    def build_job(self, company, title, url, confidence="high", score=90):
        return {
            "company": company,
            "title": title,
            "url": url,
            "matched_keyword": "ASIC",
            "matched_location": "Israel",
            "match_confidence": confidence,
            "relevance_score": score,
        }

    def build_history_job(
        self,
        company,
        title,
        url,
        confidence="high",
        score=90,
        triage_state="",
    ):
        return {
            "job_id": generate_job_id(company, title, url),
            "company": company,
            "title": title,
            "url": url,
            "matched_keyword": "ASIC",
            "matched_location": "Israel",
            "match_confidence": confidence,
            "relevance_score": score,
            "triage_state": triage_state,
            "first_seen": "2026-07-12T08:00:00+00:00",
            "last_seen": "2026-07-12T08:00:00+00:00",
        }

    def write_history(self, history):
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        with self.history_path.open("w", encoding="utf-8") as history_file:
            json.dump(history, history_file)

    def read_history(self):
        with self.history_path.open("r", encoding="utf-8") as history_file:
            return json.load(history_file)


if __name__ == "__main__":
    unittest.main()
