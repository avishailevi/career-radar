import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.job_history_service import generate_job_id
from services.job_history_service import update_job_history


class JobHistoryServiceTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.history_path = Path(self.temp_dir.name) / "data" / "job_history.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_stable_job_id_generation(self):
        first_id = generate_job_id(
            "Apple",
            "Physical Design Engineer",
            "https://example.com/jobs/1",
        )
        second_id = generate_job_id(
            " apple ",
            "Physical   Design Engineer",
            " HTTPS://EXAMPLE.COM/JOBS/1 ",
        )

        self.assertEqual(first_id, second_id)

    def test_first_run_marks_all_jobs_new_and_persists_history(self):
        jobs = [
            self.build_job("Apple", "Physical Design Engineer", "https://apple.test/1"),
            self.build_job("Qualcomm", "ASIC Design Engineer", "https://qcom.test/2"),
        ]

        with patch(
            "services.job_history_service.get_seen_at",
            return_value="2026-07-09T06:00:00+00:00",
        ):
            result = update_job_history(jobs, self.history_path)

        self.assertEqual(len(result["new_jobs"]), 2)
        self.assertEqual(result["previously_seen_count"], 0)
        self.assertTrue(self.history_path.exists())

        with self.history_path.open("r", encoding="utf-8") as history_file:
            history = json.load(history_file)

        self.assertEqual(len(history["jobs"]), 2)
        self.assertEqual(history["jobs"][0]["first_seen"], "2026-07-09T06:00:00+00:00")
        self.assertEqual(history["jobs"][0]["last_seen"], "2026-07-09T06:00:00+00:00")

    def test_second_run_marks_existing_jobs_not_new(self):
        jobs = [
            self.build_job("Apple", "Physical Design Engineer", "https://apple.test/1"),
        ]

        with patch(
            "services.job_history_service.get_seen_at",
            return_value="2026-07-09T06:00:00+00:00",
        ):
            update_job_history(jobs, self.history_path)

        with patch(
            "services.job_history_service.get_seen_at",
            return_value="2026-07-10T06:00:00+00:00",
        ):
            result = update_job_history(jobs, self.history_path)

        self.assertEqual(result["new_jobs"], [])
        self.assertEqual(result["previously_seen_count"], 1)

    def test_duplicate_prevention(self):
        jobs = [
            self.build_job("Apple", "Physical Design Engineer", "https://apple.test/1"),
            self.build_job("Apple", "Physical Design Engineer", "https://apple.test/1"),
        ]

        result = update_job_history(jobs, self.history_path)

        self.assertEqual(len(result["new_jobs"]), 1)

        with self.history_path.open("r", encoding="utf-8") as history_file:
            history = json.load(history_file)

        self.assertEqual(len(history["jobs"]), 1)

    def test_last_seen_updates_when_existing_job_appears_again(self):
        jobs = [
            self.build_job("Apple", "Physical Design Engineer", "https://apple.test/1"),
        ]

        with patch(
            "services.job_history_service.get_seen_at",
            return_value="2026-07-09T06:00:00+00:00",
        ):
            update_job_history(jobs, self.history_path)

        with patch(
            "services.job_history_service.get_seen_at",
            return_value="2026-07-10T06:00:00+00:00",
        ):
            update_job_history(jobs, self.history_path)

        with self.history_path.open("r", encoding="utf-8") as history_file:
            history = json.load(history_file)

        record = history["jobs"][0]
        self.assertEqual(record["first_seen"], "2026-07-09T06:00:00+00:00")
        self.assertEqual(record["last_seen"], "2026-07-10T06:00:00+00:00")

    def test_previously_seen_count_only_counts_jobs_seen_this_run(self):
        first_run_jobs = [
            self.build_job("Apple", "Physical Design Engineer", "https://apple.test/1"),
            self.build_job("Qualcomm", "ASIC Design Engineer", "https://qcom.test/2"),
        ]
        second_run_jobs = [
            self.build_job("Apple", "Physical Design Engineer", "https://apple.test/1"),
        ]

        update_job_history(first_run_jobs, self.history_path)

        result = update_job_history(second_run_jobs, self.history_path)

        self.assertEqual(result["previously_seen_count"], 1)
        self.assertEqual(result["total_seen_count"], 2)

    def build_job(self, company, title, url):
        return {
            "company": company,
            "title": title,
            "url": url,
            "matched_keyword": "ASIC",
            "matched_location": "Israel",
        }


if __name__ == "__main__":
    unittest.main()
