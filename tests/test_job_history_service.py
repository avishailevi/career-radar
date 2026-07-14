import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.job_history_service import generate_job_id
from services.job_history_service import generate_job_id_for_job
from services.job_history_service import get_jobs_by_triage_state
from services.job_history_service import set_job_triage_state
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

    def test_marking_job_saved_dismissed_and_applied(self):
        jobs = [
            self.build_job("Apple", "Physical Design Engineer", "https://apple.test/1"),
            self.build_job("Qualcomm", "ASIC Design Engineer", "https://qcom.test/2"),
            self.build_job("NVIDIA", "RTL Engineer", "https://nvidia.test/3"),
        ]
        update_job_history(jobs, self.history_path)

        history = self.read_history()
        apple_id = self.find_job_id(history, "Apple")
        qcom_id = self.find_job_id(history, "Qualcomm")
        nvidia_id = self.find_job_id(history, "NVIDIA")

        saved = set_job_triage_state(apple_id[:8], "saved", self.history_path)
        dismissed = set_job_triage_state(qcom_id[:8], "dismissed", self.history_path)
        applied = set_job_triage_state(nvidia_id[:8], "applied", self.history_path)

        self.assertTrue(saved["updated"])
        self.assertTrue(dismissed["updated"])
        self.assertTrue(applied["updated"])

        history = self.read_history()
        self.assertEqual(self.find_job(history, "Apple")["triage_state"], "saved")
        self.assertEqual(self.find_job(history, "Qualcomm")["triage_state"], "dismissed")
        self.assertEqual(self.find_job(history, "NVIDIA")["triage_state"], "applied")

    def test_changing_existing_state(self):
        jobs = [
            self.build_job("Apple", "Physical Design Engineer", "https://apple.test/1"),
        ]
        update_job_history(jobs, self.history_path)
        apple_id = self.find_job_id(self.read_history(), "Apple")

        set_job_triage_state(apple_id[:8], "saved", self.history_path)
        result = set_job_triage_state(apple_id[:8], "applied", self.history_path)

        self.assertTrue(result["updated"])
        self.assertEqual(self.find_job(self.read_history(), "Apple")["triage_state"], "applied")

    def test_triage_state_is_preserved_across_history_updates(self):
        jobs = [
            self.build_job("Apple", "Physical Design Engineer", "https://apple.test/1"),
        ]
        update_job_history(jobs, self.history_path)
        apple_id = self.find_job_id(self.read_history(), "Apple")
        set_job_triage_state(apple_id[:8], "dismissed", self.history_path)

        update_job_history(jobs, self.history_path)

        self.assertEqual(self.find_job(self.read_history(), "Apple")["triage_state"], "dismissed")

    def test_old_history_records_without_state_still_work(self):
        job_id = generate_job_id(
            "Apple",
            "Physical Design Engineer",
            "https://apple.test/1",
        )
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        with self.history_path.open("w", encoding="utf-8") as history_file:
            json.dump(
                {
                    "jobs": [
                        {
                            "job_id": job_id,
                            "company": "Apple",
                            "title": "Physical Design Engineer",
                            "url": "https://apple.test/1",
                            "matched_keyword": "ASIC",
                            "matched_location": "Israel",
                            "first_seen": "2026-07-09T06:00:00+00:00",
                            "last_seen": "2026-07-09T06:00:00+00:00",
                        }
                    ]
                },
                history_file,
            )

        result = set_job_triage_state(job_id[:8], "saved", self.history_path)

        self.assertTrue(result["updated"])
        self.assertEqual(self.find_job(self.read_history(), "Apple")["triage_state"], "saved")

    def test_identity_url_keeps_job_id_stable_when_display_url_changes(self):
        old_url = "https://elbitsystemscareer.com/?page=search&jobId=20199"
        new_url = "https://elbitsystemscareer.com/job?jid=20199"
        old_job_id = generate_job_id("Elbit", "FPGA engineer", old_url)
        jobs = [
            {
                "company": "Elbit",
                "title": "FPGA engineer",
                "url": new_url,
                "identity_url": old_url,
                "matched_keyword": "FPGA",
                "matched_location": "Holon",
            }
        ]

        with patch(
            "services.job_history_service.get_seen_at",
            return_value="2026-07-12T06:00:00+00:00",
        ):
            result = update_job_history(jobs, self.history_path)

        history = self.read_history()

        self.assertEqual(result["new_jobs"][0]["job_id"], old_job_id)
        self.assertEqual(history["jobs"][0]["job_id"], old_job_id)
        self.assertEqual(history["jobs"][0]["url"], new_url)
        self.assertNotIn("identity_url", history["jobs"][0])

    def test_existing_history_loads_when_job_uses_identity_url(self):
        old_url = "https://elbitsystemscareer.com/?page=search&jobId=20199"
        new_url = "https://elbitsystemscareer.com/job?jid=20199"
        old_job_id = generate_job_id("Elbit", "FPGA engineer", old_url)
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        with self.history_path.open("w", encoding="utf-8") as history_file:
            json.dump(
                {
                    "jobs": [
                        {
                            "job_id": old_job_id,
                            "company": "Elbit",
                            "title": "FPGA engineer",
                            "url": old_url,
                            "matched_keyword": "FPGA",
                            "matched_location": "Holon",
                            "first_seen": "2026-07-11T06:00:00+00:00",
                            "last_seen": "2026-07-11T06:00:00+00:00",
                        }
                    ]
                },
                history_file,
            )

        with patch(
            "services.job_history_service.get_seen_at",
            return_value="2026-07-12T06:00:00+00:00",
        ):
            result = update_job_history(
                [
                    {
                        "company": "Elbit",
                        "title": "FPGA engineer",
                        "url": new_url,
                        "identity_url": old_url,
                        "matched_keyword": "FPGA",
                        "matched_location": "Holon",
                    }
                ],
                self.history_path,
            )

        history = self.read_history()

        self.assertEqual(result["new_jobs"], [])
        self.assertEqual(result["previously_seen_count"], 1)
        self.assertEqual(history["jobs"][0]["job_id"], old_job_id)
        self.assertEqual(history["jobs"][0]["url"], new_url)

    def test_workday_requisition_prevents_false_new_job_when_url_changes(self):
        legacy_url = (
            "https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/"
            "job/Israel-Tel-Aviv/ASIC-Engineer_JR2020995?source=legacy"
        )
        new_url = (
            "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite/"
            "job/Israel-Tel-Aviv/ASIC-Engineer_JR2020995"
        )
        legacy_job_id = generate_job_id("NVIDIA", "ASIC Engineer", legacy_url)
        self.write_history(
            [
                {
                    "job_id": legacy_job_id,
                    "company": "NVIDIA",
                    "title": "ASIC Engineer",
                    "url": legacy_url,
                    "matched_keyword": "ASIC",
                    "matched_location": "Israel",
                    "triage_state": "",
                    "first_seen": "2026-07-10T06:00:00+00:00",
                    "last_seen": "2026-07-10T06:00:00+00:00",
                }
            ]
        )
        job = {
            "company": "NVIDIA",
            "title": "ASIC Engineer",
            "url": new_url,
            "identity_url": "workday://nvidia/jr2020995",
            "matched_keyword": "ASIC",
            "matched_location": "Israel",
        }
        expected_job_id = generate_job_id_for_job(job)

        with patch(
            "services.job_history_service.get_seen_at",
            return_value="2026-07-11T06:00:00+00:00",
        ):
            result = update_job_history([job], self.history_path)

        history = self.read_history()

        self.assertEqual(result["new_jobs"], [])
        self.assertEqual(result["previously_seen_count"], 1)
        self.assertEqual(len(history["jobs"]), 1)
        self.assertEqual(history["jobs"][0]["job_id"], expected_job_id)
        self.assertEqual(history["jobs"][0]["url"], new_url)
        self.assertEqual(history["jobs"][0]["first_seen"], "2026-07-10T06:00:00+00:00")

    def test_workday_requisition_refresh_preserves_triage_state(self):
        legacy_url = (
            "https://marvell.wd1.myworkdayjobs.com/en-US/MarvellCareers/"
            "job/Petah-Tikva/Design-Verification_2600069"
        )
        new_url = (
            "https://marvell.wd1.myworkdayjobs.com/MarvellCareers/"
            "job/Petah-Tikva/Design-Verification_2600069"
        )
        old_job_id = generate_job_id(
            "Marvell",
            "Design Verification Engineer",
            legacy_url,
        )
        self.write_history(
            [
                {
                    "job_id": old_job_id,
                    "company": "Marvell",
                    "title": "Design Verification Engineer",
                    "url": legacy_url,
                    "matched_keyword": "Design Verification",
                    "matched_location": "Petah-Tikva",
                    "triage_state": "saved",
                    "first_seen": "2026-07-10T06:00:00+00:00",
                    "last_seen": "2026-07-10T06:00:00+00:00",
                }
            ]
        )

        result = update_job_history(
            [
                {
                    "company": "Marvell",
                    "title": "Design Verification Engineer",
                    "url": new_url,
                    "identity_url": "workday://marvell/2600069",
                    "matched_keyword": "Design Verification",
                    "matched_location": "Petah-Tikva",
                }
            ],
            self.history_path,
        )

        history = self.read_history()

        self.assertEqual(result["new_jobs"], [])
        self.assertEqual(history["jobs"][0]["triage_state"], "saved")
        self.assertEqual(history["jobs"][0]["url"], new_url)

    def test_workday_same_title_location_different_requisitions_are_distinct(self):
        jobs = [
            {
                "company": "Intel",
                "title": "RF Hardware Design Engineer",
                "url": "https://intel.wd1.myworkdayjobs.com/External/job/A_JR1111",
                "identity_url": "workday://intel/jr1111",
                "matched_keyword": "RF",
                "matched_location": "Israel",
            },
            {
                "company": "Intel",
                "title": "RF Hardware Design Engineer",
                "url": "https://intel.wd1.myworkdayjobs.com/External/job/B_JR2222",
                "identity_url": "workday://intel/jr2222",
                "matched_keyword": "RF",
                "matched_location": "Israel",
            },
        ]

        result = update_job_history(jobs, self.history_path)
        history = self.read_history()

        self.assertEqual(len(result["new_jobs"]), 2)
        self.assertEqual(len(history["jobs"]), 2)
        self.assertNotEqual(history["jobs"][0]["job_id"], history["jobs"][1]["job_id"])

    def test_workday_same_requisition_on_two_companies_is_distinct(self):
        nvidia = {
            "company": "NVIDIA",
            "title": "ASIC Engineer",
            "url": "https://nvidia.wd5.myworkdayjobs.com/Site/job/A_JR1111",
            "identity_url": "workday://nvidia/jr1111",
            "matched_keyword": "ASIC",
            "matched_location": "Israel",
        }
        intel = {
            "company": "Intel",
            "title": "ASIC Engineer",
            "url": "https://intel.wd1.myworkdayjobs.com/Site/job/A_JR1111",
            "identity_url": "workday://intel/jr1111",
            "matched_keyword": "ASIC",
            "matched_location": "Israel",
        }

        self.assertNotEqual(
            generate_job_id_for_job(nvidia),
            generate_job_id_for_job(intel),
        )

    def test_existing_workday_history_without_identity_url_loads_unchanged(self):
        job_id = generate_job_id(
            "NVIDIA",
            "ASIC Engineer",
            "https://nvidia.wd5.myworkdayjobs.com/Site/job/A_JR1111",
        )
        self.write_history(
            [
                {
                    "job_id": job_id,
                    "company": "NVIDIA",
                    "title": "ASIC Engineer",
                    "url": "https://nvidia.wd5.myworkdayjobs.com/Site/job/A_JR1111",
                    "matched_keyword": "ASIC",
                    "matched_location": "Israel",
                    "triage_state": "applied",
                    "first_seen": "2026-07-10T06:00:00+00:00",
                    "last_seen": "2026-07-10T06:00:00+00:00",
                }
            ]
        )

        self.assertEqual(self.read_history()["jobs"][0]["job_id"], job_id)
        self.assertEqual(
            get_jobs_by_triage_state("applied", self.history_path)[0]["company"],
            "NVIDIA",
        )

    def test_elbit_identity_url_behavior_remains_unchanged(self):
        old_url = "https://elbitsystemscareer.com/?page=search&jobId=20199"
        new_url = "https://elbitsystemscareer.com/job?jid=20199"
        old_job_id = generate_job_id("Elbit", "FPGA engineer", old_url)
        self.write_history(
            [
                {
                    "job_id": old_job_id,
                    "company": "Elbit",
                    "title": "FPGA engineer",
                    "url": old_url,
                    "matched_keyword": "FPGA",
                    "matched_location": "Holon",
                    "triage_state": "dismissed",
                    "first_seen": "2026-07-11T06:00:00+00:00",
                    "last_seen": "2026-07-11T06:00:00+00:00",
                }
            ]
        )

        result = update_job_history(
            [
                {
                    "company": "Elbit",
                    "title": "FPGA engineer",
                    "url": new_url,
                    "identity_url": old_url,
                    "matched_keyword": "FPGA",
                    "matched_location": "Holon",
                }
            ],
            self.history_path,
        )

        history = self.read_history()

        self.assertEqual(result["new_jobs"], [])
        self.assertEqual(history["jobs"][0]["job_id"], old_job_id)
        self.assertEqual(history["jobs"][0]["triage_state"], "dismissed")
        self.assertEqual(history["jobs"][0]["url"], new_url)

    def test_get_jobs_by_triage_state_filters_saved_applied_and_dismissed(self):
        self.write_history(
            [
                self.build_history_job("Apple", "Saved Job", "saved"),
                self.build_history_job("NVIDIA", "Applied Job", "applied"),
                self.build_history_job("Qualcomm", "Dismissed Job", "dismissed"),
                self.build_history_job("Intel", "Unmarked Job", ""),
            ]
        )

        self.assertEqual(
            [job["company"] for job in get_jobs_by_triage_state("saved", self.history_path)],
            ["Apple"],
        )
        self.assertEqual(
            [job["company"] for job in get_jobs_by_triage_state("applied", self.history_path)],
            ["NVIDIA"],
        )
        self.assertEqual(
            [job["company"] for job in get_jobs_by_triage_state("dismissed", self.history_path)],
            ["Qualcomm"],
        )

    def test_get_jobs_by_triage_state_orders_by_newest_last_seen_then_company_title(self):
        self.write_history(
            [
                self.build_history_job(
                    "NVIDIA",
                    "Z Job",
                    "saved",
                    last_seen="2026-07-10T06:00:00+00:00",
                ),
                self.build_history_job(
                    "Apple",
                    "B Job",
                    "saved",
                    last_seen="2026-07-11T06:00:00+00:00",
                ),
                self.build_history_job(
                    "Apple",
                    "A Job",
                    "saved",
                    last_seen="2026-07-11T06:00:00+00:00",
                ),
                self.build_history_job(
                    "Qualcomm",
                    "Newest Job",
                    "saved",
                    last_seen="2026-07-12T06:00:00+00:00",
                ),
            ]
        )

        jobs = get_jobs_by_triage_state("saved", self.history_path)

        self.assertEqual(
            [(job["company"], job["title"]) for job in jobs],
            [
                ("Qualcomm", "Newest Job"),
                ("Apple", "A Job"),
                ("Apple", "B Job"),
                ("NVIDIA", "Z Job"),
            ],
        )

    def test_get_jobs_by_triage_state_ignores_old_unmarked_records(self):
        job = self.build_history_job("Apple", "Old Job", "")
        del job["triage_state"]
        self.write_history([job])

        self.assertEqual(get_jobs_by_triage_state("saved", self.history_path), [])

    def test_invalid_job_id_and_state_do_not_corrupt_history(self):
        jobs = [
            self.build_job("Apple", "Physical Design Engineer", "https://apple.test/1"),
        ]
        update_job_history(jobs, self.history_path)
        before = self.read_history()
        apple_id = self.find_job_id(before, "Apple")

        invalid_state = set_job_triage_state(apple_id[:8], "maybe", self.history_path)
        invalid_id = set_job_triage_state("missing", "saved", self.history_path)
        after = self.read_history()

        self.assertFalse(invalid_state["updated"])
        self.assertEqual(invalid_state["error"], "invalid_state")
        self.assertFalse(invalid_id["updated"])
        self.assertEqual(invalid_id["error"], "not_found")
        self.assertEqual(before, after)

    def build_job(self, company, title, url):
        return {
            "company": company,
            "title": title,
            "url": url,
            "matched_keyword": "ASIC",
            "matched_location": "Israel",
        }

    def build_history_job(
        self,
        company,
        title,
        triage_state,
        last_seen="2026-07-09T06:00:00+00:00",
    ):
        url = f"https://{company.lower()}.test/{title.lower().replace(' ', '-')}"
        return {
            "job_id": generate_job_id(company, title, url),
            "company": company,
            "title": title,
            "url": url,
            "matched_keyword": "ASIC",
            "matched_location": "Israel",
            "triage_state": triage_state,
            "first_seen": "2026-07-08T06:00:00+00:00",
            "last_seen": last_seen,
        }

    def write_history(self, jobs):
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        with self.history_path.open("w", encoding="utf-8") as history_file:
            json.dump({"jobs": jobs}, history_file)

    def read_history(self):
        with self.history_path.open("r", encoding="utf-8") as history_file:
            return json.load(history_file)

    def find_job(self, history, company):
        for job in history["jobs"]:
            if job["company"] == company:
                return job

        return None

    def find_job_id(self, history, company):
        return self.find_job(history, company)["job_id"]


if __name__ == "__main__":
    unittest.main()
