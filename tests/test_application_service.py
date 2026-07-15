import tempfile
import threading
import unittest
import json
import io
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from services import application_service
from services.job_history_service import generate_job_id


class ApplicationServiceTest(unittest.TestCase):
    def setUp(self):
        application_service.reset_session_scan_state()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.history_path = Path(self.temp_dir.name) / "data" / "job_history.json"

    def tearDown(self):
        application_service.reset_session_scan_state()
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

    def test_run_scan_relevant_ids_use_identity_url(self):
        job = self.build_job(
            "Elbit",
            "FPGA engineer",
            "https://elbitsystemscareer.com/job?jid=20199",
        )
        job["identity_url"] = "https://elbitsystemscareer.com/?page=search&jobId=20199"

        with patch(
            "services.application_service.get_companies_to_scan",
            return_value=[{"name": "Elbit"}],
        ):
            with patch(
                "services.application_service.scan_companies",
                return_value=(
                    [job],
                    [{"company": "Elbit", "status": "success_with_jobs"}],
                ),
            ):
                with patch("services.application_service.send_email_digest"):
                    application_service.run_scan(
                        history_path=self.history_path,
                    )

        latest_scan = self.read_history()["latest_scan"]

        self.assertEqual(
            latest_scan["relevant_job_ids"],
            [
                generate_job_id(
                    "Elbit",
                    "FPGA engineer",
                    "https://elbitsystemscareer.com/?page=search&jobId=20199",
                )
            ],
        )

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
        self.assert_health(scan_health[0], "Apple", "success_with_jobs", 1)
        self.assert_health(scan_health[1], "BrokenCo", "failed", 0)
        self.assertEqual(scan_health[1]["error"], "scanner failed")

    def test_default_worker_count_is_four(self):
        self.assertEqual(application_service.get_scan_worker_count({}), 4)

    def test_environment_worker_count_overrides_default(self):
        self.assertEqual(
            application_service.get_scan_worker_count(
                {"CAREER_RADAR_SCAN_WORKERS": "2"},
            ),
            2,
        )

    def test_invalid_worker_count_uses_default(self):
        self.assertEqual(
            application_service.get_scan_worker_count(
                {"CAREER_RADAR_SCAN_WORKERS": "many"},
            ),
            4,
        )

    def test_zero_or_negative_worker_count_uses_default(self):
        self.assertEqual(
            application_service.get_scan_worker_count(
                {"CAREER_RADAR_SCAN_WORKERS": "0"},
            ),
            4,
        )
        self.assertEqual(
            application_service.get_scan_worker_count(
                {"CAREER_RADAR_SCAN_WORKERS": "-3"},
            ),
            4,
        )

    def test_worker_count_is_capped(self):
        self.assertEqual(
            application_service.get_scan_worker_count(
                {"CAREER_RADAR_SCAN_WORKERS": "99"},
            ),
            8,
        )

    def test_worker_count_one_preserves_sequential_behavior(self):
        companies = [{"name": "Apple"}, {"name": "Broadcom"}]
        calls = []

        def scan_company(company):
            calls.append(company["name"])
            return [self.build_job(company["name"], "ASIC", f"https://{company['name']}.test")]

        with patch("services.application_service.scan_company", side_effect=scan_company):
            jobs, scan_health = application_service.scan_companies(
                companies,
                worker_count=1,
            )

        self.assertEqual(calls, ["Apple", "Broadcom"])
        self.assertEqual([job["company"] for job in jobs], ["Apple", "Broadcom"])
        self.assertEqual([result["company"] for result in scan_health], ["Apple", "Broadcom"])

    def test_multiple_companies_execute_concurrently(self):
        companies = [{"name": "Apple"}, {"name": "Broadcom"}]
        both_started = threading.Event()
        release = threading.Event()
        active = set()
        active_lock = threading.Lock()

        def scan_company(company):
            with active_lock:
                active.add(company["name"])
                if len(active) == 2:
                    both_started.set()
            self.assertTrue(both_started.wait(timeout=2))
            release.wait(timeout=2)
            return [self.build_job(company["name"], "ASIC", f"https://{company['name']}.test")]

        with patch("services.application_service.scan_company", side_effect=scan_company):
            thread = threading.Thread(
                target=lambda: application_service.scan_companies(
                    companies,
                    worker_count=2,
                )
            )
            thread.start()
            self.assertTrue(both_started.wait(timeout=2))
            release.set()
            thread.join(timeout=2)

        self.assertFalse(thread.is_alive())

    def test_final_jobs_and_health_keep_requested_order_when_workers_finish_out_of_order(self):
        companies = [{"name": "Slow"}, {"name": "Fast"}]
        slow_release = threading.Event()
        fast_done = threading.Event()

        def scan_company(company):
            if company["name"] == "Fast":
                fast_done.set()
                return [self.build_job("Fast", "ASIC", "https://fast.test")]

            self.assertTrue(fast_done.wait(timeout=2))
            slow_release.wait(timeout=2)
            return [self.build_job("Slow", "ASIC", "https://slow.test")]

        with patch("services.application_service.scan_company", side_effect=scan_company):
            thread_result = {}
            thread = threading.Thread(
                target=lambda: thread_result.update(
                    result=application_service.scan_companies(
                        companies,
                        worker_count=2,
                    )
                )
            )
            thread.start()
            self.assertTrue(fast_done.wait(timeout=2))
            slow_release.set()
            thread.join(timeout=2)

        jobs, scan_health = thread_result["result"]
        self.assertEqual([job["company"] for job in jobs], ["Slow", "Fast"])
        self.assertEqual([result["company"] for result in scan_health], ["Slow", "Fast"])

    def test_future_exception_becomes_failed_company_result(self):
        companies = [{"name": "Apple"}, {"name": "Broadcom"}]

        with patch(
            "services.application_service.scan_company_result",
            side_effect=RuntimeError("future exploded"),
        ):
            jobs, scan_health = application_service.scan_companies(
                companies,
                worker_count=2,
            )

        self.assertEqual(jobs, [])
        self.assert_health(scan_health[0], "Apple", "failed", 0)
        self.assertEqual(scan_health[0]["error"], "future exploded")

    def test_duration_and_jobs_found_are_recorded(self):
        companies = [{"name": "Apple"}]
        jobs_for_company = [self.build_job("Apple", "ASIC", "https://apple.test")]

        with patch(
            "services.application_service.scan_company",
            return_value=jobs_for_company,
        ):
            jobs, scan_health = application_service.scan_companies(
                companies,
                worker_count=1,
            )

        self.assertEqual(jobs, jobs_for_company)
        self.assertEqual(scan_health[0]["jobs_found"], 1)
        self.assertIsInstance(scan_health[0]["duration_seconds"], float)
        self.assertGreaterEqual(scan_health[0]["duration_seconds"], 0.0)

    def test_progress_tracks_running_and_completed_companies(self):
        companies = [{"name": "Apple"}, {"name": "Broadcom"}]
        both_started = threading.Event()
        release = threading.Event()
        active = set()
        active_lock = threading.Lock()

        def scan_company(company):
            with active_lock:
                active.add(company["name"])
                if len(active) == 2:
                    both_started.set()
            release.wait(timeout=2)
            return []

        with patch("services.application_service.scan_company", side_effect=scan_company):
            thread = threading.Thread(
                target=lambda: application_service.scan_companies(
                    companies,
                    worker_count=2,
                )
            )
            thread.start()
            self.assertTrue(both_started.wait(timeout=2))
            status = application_service.get_scan_status()
            release.set()
            thread.join(timeout=2)

        self.assertEqual(status["total_companies"], 2)
        self.assertEqual(status["completed_companies"], 0)
        self.assertEqual(status["completed_company_names"], [])
        self.assertEqual(status["running_companies"], ["Apple", "Broadcom"])
        self.assertGreaterEqual(status["elapsed_seconds"], 0.0)
        final_status = application_service.get_scan_status()
        self.assertEqual(final_status["completed_companies"], 2)
        self.assertEqual(
            final_status["completed_company_names"],
            ["Apple", "Broadcom"],
        )
        self.assertEqual(final_status["running_companies"], [])

    def test_completed_company_progress_keeps_requested_order(self):
        companies = [{"name": "Slow"}, {"name": "Fast"}]
        fast_done = threading.Event()
        fast_progress_recorded = threading.Event()
        release_slow = threading.Event()
        mark_completed = application_service._mark_company_completed

        def scan_company(company):
            if company["name"] == "Fast":
                fast_done.set()
                return []

            release_slow.wait(timeout=2)
            return []

        def record_completion(index):
            mark_completed(index)
            if index == 1:
                fast_progress_recorded.set()

        with patch("services.application_service.scan_company", side_effect=scan_company):
            with patch(
                "services.application_service._mark_company_completed",
                side_effect=record_completion,
            ):
                thread = threading.Thread(
                    target=lambda: application_service.scan_companies(
                        companies,
                        worker_count=2,
                    )
                )
                thread.start()
                self.assertTrue(fast_done.wait(timeout=2))
                self.assertTrue(fast_progress_recorded.wait(timeout=2))
                status = application_service.get_scan_status()
                self.assertEqual(status["completed_company_names"], ["Fast"])
                release_slow.set()
                thread.join(timeout=2)

        self.assertFalse(thread.is_alive())
        self.assertEqual(
            application_service.get_scan_status()["completed_company_names"],
            ["Slow", "Fast"],
        )

    def test_repeated_parallel_runs_are_deterministic(self):
        companies = [{"name": "Apple"}, {"name": "Broadcom"}, {"name": "Marvell"}]

        def scan_company(company):
            return [self.build_job(company["name"], "ASIC", f"https://{company['name']}.test")]

        with patch("services.application_service.scan_company", side_effect=scan_company):
            first = application_service.scan_companies(companies, worker_count=3)
        with patch("services.application_service.scan_company", side_effect=scan_company):
            second = application_service.scan_companies(companies, worker_count=3)

        self.assertEqual(
            [job["company"] for job in first[0]],
            [job["company"] for job in second[0]],
        )
        self.assertEqual(
            [result["company"] for result in first[1]],
            [result["company"] for result in second[1]],
        )

    def test_debug_output_is_printed_in_requested_company_order(self):
        companies = [{"name": "Slow"}, {"name": "Fast"}]
        fast_done = threading.Event()
        release_slow = threading.Event()

        def scan_company(company):
            if company["name"] == "Fast":
                print("Fast output")
                fast_done.set()
                return []

            self.assertTrue(fast_done.wait(timeout=2))
            release_slow.wait(timeout=2)
            print("Slow output")
            return []

        output = io.StringIO()
        with patch("services.application_service.DEBUG", True):
            with patch("services.application_service.scan_company", side_effect=scan_company):
                thread = threading.Thread(
                    target=lambda: application_service.scan_companies(
                        companies,
                        worker_count=2,
                    )
                )
                with redirect_stdout(output):
                    thread.start()
                    self.assertTrue(fast_done.wait(timeout=2))
                    release_slow.set()
                    thread.join(timeout=2)

        self.assertLess(
            output.getvalue().index("Slow output"),
            output.getvalue().index("Fast output"),
        )

    def test_existing_scan_health_without_duration_or_jobs_fields_loads(self):
        health = [{"company": "Apple", "status": "success_with_jobs"}]
        self.write_history(
            {
                "jobs": [],
                "latest_scan": {
                    "summary": application_service.build_scan_summary(1, 0, 0, health),
                    "scan_health": health,
                },
            }
        )

        self.assertEqual(application_service.get_latest_scan_health(self.history_path), health)

    def test_history_is_written_once_after_all_scans_complete(self):
        jobs = [self.build_job("Apple", "ASIC", "https://apple.test")]
        scans_done = threading.Event()

        def scan_companies(companies):
            scans_done.set()
            return jobs, [{"company": "Apple", "status": "success_with_jobs"}]

        with patch("services.application_service.get_companies_to_scan", return_value=[{"name": "Apple"}]):
            with patch("services.application_service.scan_companies", side_effect=scan_companies):
                with patch("services.application_service.update_job_history") as update_history:
                    update_history.return_value = {
                        "new_jobs": [],
                        "previously_seen_count": 0,
                        "total_seen_count": 1,
                    }
                    with patch("services.application_service.send_email_digest"):
                        application_service.run_scan(history_path=self.history_path)

        self.assertTrue(scans_done.is_set())
        update_history.assert_called_once_with(jobs, self.history_path)

    def test_email_is_sent_once_after_complete_result_is_assembled(self):
        calls = []

        def scan_companies(companies):
            calls.append("scan")
            return [self.build_job("Apple", "ASIC", "https://apple.test")], [
                {"company": "Apple", "status": "success_with_jobs"}
            ]

        def update_history(jobs, history_path):
            calls.append("history")
            new_jobs = [dict(job, job_id=f"{index}") for index, job in enumerate(jobs)]
            return {
                "new_jobs": new_jobs,
                "previously_seen_count": 0,
                "total_seen_count": len(jobs),
            }

        def send_email(jobs):
            calls.append("email")

        with patch("services.application_service.get_companies_to_scan", return_value=[{"name": "Apple"}]):
            with patch("services.application_service.scan_companies", side_effect=scan_companies):
                with patch("services.application_service.update_job_history", side_effect=update_history):
                    with patch("services.application_service.send_email_digest", side_effect=send_email):
                        application_service.run_scan(history_path=self.history_path)

        self.assertEqual(calls, ["scan", "history", "email"])

    def test_no_email_is_sent_when_scan_fails_before_history_update(self):
        with patch("services.application_service.get_companies_to_scan", return_value=[{"name": "Apple"}]):
            with patch(
                "services.application_service.scan_companies",
                side_effect=RuntimeError("scan orchestration failed"),
            ):
                with patch("services.application_service.send_email_digest") as send_email:
                    with self.assertRaises(RuntimeError):
                        application_service.run_scan(history_path=self.history_path)

        send_email.assert_not_called()

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

    def test_fresh_session_hides_previous_scan_without_deleting_history(self):
        job = self.build_history_job(
            "Apple",
            "Previous Job",
            "https://apple.test/previous",
        )
        history = {
            "jobs": [job],
            "latest_scan": {
                "summary": application_service.build_scan_summary(
                    1,
                    1,
                    1,
                    [{"company": "Apple", "status": "success_with_jobs"}],
                ),
                "scan_health": [
                    {"company": "Apple", "status": "success_with_jobs"},
                ],
                "new_job_ids": [job["job_id"]],
                "relevant_job_ids": [job["job_id"]],
            },
        }
        self.write_history(history)

        self.assertFalse(application_service.session_has_scan())
        self.assertEqual(
            application_service.get_current_session_new_jobs(self.history_path),
            [],
        )
        self.assertEqual(
            application_service.get_current_session_relevant_jobs(self.history_path),
            [],
        )
        self.assertEqual(
            application_service.get_current_session_scan_summary(
                self.history_path,
            )["companies_scanned"],
            0,
        )
        self.assertEqual(
            application_service.get_current_session_scan_health(self.history_path),
            [],
        )
        self.assertEqual(self.read_history(), history)

    def test_current_session_results_are_available_after_successful_scan(self):
        jobs = [self.build_job("Apple", "ASIC Engineer", "https://apple.test/1")]

        with patch(
            "services.application_service.get_companies_to_scan",
            return_value=[{"name": "Apple"}],
        ):
            with patch(
                "services.application_service.scan_companies",
                return_value=(jobs, [{"company": "Apple", "status": "success_with_jobs"}]),
            ):
                with patch("services.application_service.send_email_digest"):
                    application_service.run_scan(history_path=self.history_path)

        self.assertTrue(application_service.session_has_scan())
        self.assertEqual(
            application_service.get_current_session_scan_summary(
                self.history_path,
            )["companies_scanned"],
            1,
        )
        self.assertEqual(
            application_service.get_current_session_new_jobs(
                self.history_path,
            )[0]["title"],
            "ASIC Engineer",
        )
        self.assertEqual(
            application_service.get_current_session_relevant_jobs(
                self.history_path,
            )[0]["title"],
            "ASIC Engineer",
        )

    def test_resetting_session_returns_to_fresh_state(self):
        jobs = [self.build_job("Apple", "ASIC Engineer", "https://apple.test/1")]

        with patch(
            "services.application_service.get_companies_to_scan",
            return_value=[{"name": "Apple"}],
        ):
            with patch(
                "services.application_service.scan_companies",
                return_value=(jobs, [{"company": "Apple", "status": "success_with_jobs"}]),
            ):
                with patch("services.application_service.send_email_digest"):
                    application_service.run_scan(history_path=self.history_path)

        application_service.reset_session_scan_state()

        self.assertFalse(application_service.session_has_scan())
        self.assertEqual(
            application_service.get_current_session_new_jobs(self.history_path),
            [],
        )
        self.assertEqual(
            application_service.get_latest_new_jobs(self.history_path)[0]["title"],
            "ASIC Engineer",
        )

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

    def assert_health(self, health, company, status, jobs_found):
        self.assertEqual(health["company"], company)
        self.assertEqual(health["status"], status)
        self.assertEqual(health["jobs_found"], jobs_found)
        self.assertIsInstance(health["duration_seconds"], float)

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
