import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import local_app
from services import application_service
from services.job_history_service import generate_job_id


class LocalAppTest(unittest.TestCase):
    def setUp(self):
        application_service.reset_session_scan_state()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.history_path = Path(self.temp_dir.name) / "job_history.json"
        self.history_patcher = patch.object(
            local_app,
            "HISTORY_PATH",
            self.history_path,
        )
        self.history_patcher.start()
        local_app.app.config["TESTING"] = True
        self.client = local_app.app.test_client()

    def tearDown(self):
        self.history_patcher.stop()
        application_service.reset_session_scan_state()
        self.temp_dir.cleanup()

    def test_fresh_startup_hides_previous_scan_summary(self):
        self.write_previous_scan_history()

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Ready to scan.", response.data)
        self.assertIn(b"No scan has been run during this session.", response.data)
        self.assertIn(b"<strong>0</strong>", response.data)
        self.assertNotIn(b"<strong>7</strong>", response.data)

    def test_fresh_startup_hides_previous_new_jobs(self):
        self.write_previous_scan_history()

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"No scan has been run during this session.", response.data)
        self.assertNotIn(b"Previous Job", response.data)
        self.assertNotIn(b"No new jobs from the latest scan.", response.data)
        self.assertIn(b'href="/relevant"', response.data)
        self.assertIn(b'href="/"', response.data)
        self.assertEqual(response.data.count(b'class="summary-card summary-link"'), 2)

    def test_fresh_startup_hides_previous_relevant_jobs(self):
        self.write_previous_scan_history()

        response = self.client.get("/relevant")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"No scan has been run during this session.", response.data)
        self.assertNotIn(b"Previous Job", response.data)
        self.assertNotIn(b"No relevant-job list is stored", response.data)

    def test_saved_view_uses_local_history_without_running_scan(self):
        with patch("local_app.get_triage_jobs", return_value=[]) as get_triage_jobs:
            with patch("local_app.run_scan") as run_scan:
                response = self.client.get("/saved")

        self.assertEqual(response.status_code, 200)
        get_triage_jobs.assert_called_once_with("saved", local_app.HISTORY_PATH)
        run_scan.assert_not_called()
        self.assertIn(b"No saved jobs.", response.data)

    def test_applied_view_uses_local_history_without_running_scan(self):
        with patch("local_app.get_triage_jobs", return_value=[]) as get_triage_jobs:
            with patch("local_app.run_scan") as run_scan:
                response = self.client.get("/applied")

        self.assertEqual(response.status_code, 200)
        get_triage_jobs.assert_called_once_with("applied", local_app.HISTORY_PATH)
        run_scan.assert_not_called()
        self.assertIn(b"No applied jobs.", response.data)

    def test_dismissed_view_uses_local_history_without_running_scan(self):
        with patch("local_app.get_triage_jobs", return_value=[]) as get_triage_jobs:
            with patch("local_app.run_scan") as run_scan:
                response = self.client.get("/dismissed")

        self.assertEqual(response.status_code, 200)
        get_triage_jobs.assert_called_once_with("dismissed", local_app.HISTORY_PATH)
        run_scan.assert_not_called()
        self.assertIn(b"No dismissed jobs.", response.data)

    def test_after_scan_now_dashboard_appears_normally(self):
        with patch("local_app.get_scan_status", return_value=self.status("idle")):
            with patch("local_app.threading.Thread", self.ImmediateThread):
                with patch(
                    "services.application_service.get_companies_to_scan",
                    return_value=[{"name": "Apple"}],
                ):
                    with patch(
                        "services.application_service.scan_companies",
                        return_value=(
                            [self.job("Apple", "ASIC Engineer", "https://apple.test/1")],
                            [{"company": "Apple", "status": "success_with_jobs"}],
                        ),
                    ):
                        with patch("services.application_service.send_email_digest"):
                            post_response = self.client.post("/scan")

        self.assertEqual(post_response.status_code, 302)
        self.assertTrue(application_service.session_has_scan())

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"<strong>1</strong>", response.data)
        self.assertIn(b"ASIC Engineer", response.data)
        self.assertNotIn(b"No scan has been run during this session.", response.data)

    def test_scan_health_fresh_state_renders(self):
        self.write_previous_scan_history()

        response = self.client.get("/scan-health")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Run a scan to view health information.", response.data)
        self.assertNotIn(b"success_with_jobs", response.data)

    def test_relevant_view_uses_local_history_without_running_scan(self):
        jobs = [
            {
                "job_id": "1234567890abcdef",
                "company": "Apple",
                "title": "ASIC Engineer",
                "url": "https://apple.test/1",
                "matched_keyword": "ASIC",
                "matched_location": "Israel",
                "match_confidence": "high",
                "relevance_score": 92,
            }
        ]

        with patch(
            "local_app.get_current_session_relevant_jobs",
            return_value=jobs,
        ) as get_jobs:
            with patch("local_app.run_scan") as run_scan:
                response = self.client.get("/relevant")

        self.assertEqual(response.status_code, 200)
        get_jobs.assert_called_once_with(local_app.HISTORY_PATH)
        run_scan.assert_not_called()
        self.assertIn(b"Relevant Jobs", response.data)
        self.assertIn(b"ASIC Engineer", response.data)
        self.assertIn(b"Short ID", response.data)
        self.assertIn(b"12345678", response.data)

    def test_relevant_view_empty_state_when_metadata_is_missing(self):
        with patch("local_app.session_has_scan", return_value=True):
            with patch("local_app.get_current_session_relevant_jobs", return_value=[]):
                response = self.client.get("/relevant")

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            b"No relevant-job list is stored for the latest scan.",
            response.data,
        )
        self.assertIn(b"Run Scan Now to refresh it.", response.data)

    def test_new_jobs_empty_state_after_session_scan(self):
        with patch("local_app.session_has_scan", return_value=True):
            with patch("local_app.get_current_session_new_jobs", return_value=[]):
                response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"No new jobs from the latest scan.", response.data)

    def test_summary_cards_navigation_does_not_scan(self):
        with patch("local_app.run_scan") as run_scan:
            response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.count(b'class="summary-card summary-link"'), 2)
        self.assertIn(b'<span>Companies scanned</span>', response.data)
        self.assertIn(b'href="/"', response.data)
        self.assertIn(b'href="/relevant"', response.data)
        run_scan.assert_not_called()

    def test_mark_job_route_updates_triage_state(self):
        with patch("local_app.mark_job") as mark_job:
            response = self.client.post(
                "/jobs/abc12345/mark",
                data={"state": "saved", "next": "/saved"},
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/saved")
        mark_job.assert_called_once_with(
            "abc12345",
            "saved",
            local_app.HISTORY_PATH,
        )

    def test_mark_job_route_returns_to_relevant_view(self):
        with patch("local_app.mark_job") as mark_job:
            response = self.client.post(
                "/jobs/abc12345/mark",
                data={"state": "dismissed", "next": "/relevant"},
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/relevant")
        mark_job.assert_called_once_with(
            "abc12345",
            "dismissed",
            local_app.HISTORY_PATH,
        )

    def test_scan_now_starts_background_scan_when_idle(self):
        fake_thread = self.FakeThread()

        with patch("local_app.get_scan_status", return_value=self.status("idle")):
            with patch("local_app.threading.Thread", return_value=fake_thread):
                response = self.client.post("/scan")

        self.assertEqual(response.status_code, 302)
        self.assertTrue(fake_thread.started)

    def test_scan_now_does_not_start_duplicate_scan_when_running(self):
        with patch("local_app.get_scan_status", return_value=self.status("running")):
            with patch("local_app.threading.Thread") as thread:
                response = self.client.post("/scan")

        self.assertEqual(response.status_code, 302)
        thread.assert_not_called()

    def test_scan_health_empty_state_after_session_scan(self):
        with patch("local_app.session_has_scan", return_value=True):
            with patch("local_app.get_current_session_scan_health", return_value=[]):
                response = self.client.get("/scan-health")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"No scan has completed yet.", response.data)

    def test_auto_refresh_only_while_scan_is_running(self):
        with patch("local_app.get_scan_status", return_value=self.status("running")):
            running_response = self.client.get("/")

        with patch("local_app.get_scan_status", return_value=self.status("completed")):
            completed_response = self.client.get("/")

        self.assertIn(b'http-equiv="refresh"', running_response.data)
        self.assertIn(b'content="3"', running_response.data)
        self.assertNotIn(b'http-equiv="refresh"', completed_response.data)

    def test_failed_scan_message_renders_without_stack_trace(self):
        status = self.status("failed")
        status["message"] = "Scan failed."
        status["error"] = "Could not complete the scan."

        with patch("local_app.get_scan_status", return_value=status):
            response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Scan failed.", response.data)
        self.assertIn(b"Could not complete the scan.", response.data)
        self.assertNotIn(b"Traceback", response.data)

    def test_running_scan_progress_renders_current_companies(self):
        status = self.status("running")
        status["total_companies"] = 3
        status["completed_companies"] = 1
        status["running_companies"] = ["Apple", "Broadcom"]
        status["elapsed_seconds"] = 2.5

        with patch("local_app.get_scan_status", return_value=status):
            response = self.client.get("/scan-health")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"1/3 completed", response.data)
        self.assertIn(b"Scanning Apple, Broadcom", response.data)

    def job(self, company, title, url):
        return {
            "company": company,
            "title": title,
            "url": url,
            "matched_keyword": "ASIC",
            "matched_location": "Israel",
        }

    def write_previous_scan_history(self):
        job = self.history_job("Apple", "Previous Job", "https://apple.test/old")
        history = {
            "jobs": [job],
            "latest_scan": {
                "summary": {
                    "companies_scanned": 7,
                    "companies_with_relevant_jobs": ["Apple"],
                    "companies_with_zero_relevant_jobs": [],
                    "failed_companies": [],
                    "relevant_jobs_count": 3,
                    "new_jobs_count": 2,
                },
                "scan_health": [
                    {"company": "Apple", "status": "success_with_jobs"},
                ],
                "new_job_ids": [job["job_id"]],
                "relevant_job_ids": [job["job_id"]],
            },
        }
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        with self.history_path.open("w", encoding="utf-8") as history_file:
            json.dump(history, history_file)
        return history

    def history_job(self, company, title, url):
        return {
            "job_id": generate_job_id(company, title, url),
            "company": company,
            "title": title,
            "url": url,
            "matched_keyword": "ASIC",
            "matched_location": "Israel",
            "triage_state": "",
            "first_seen": "2026-07-12T08:00:00+00:00",
            "last_seen": "2026-07-12T08:00:00+00:00",
        }

    def status(self, state="idle"):
        return {
            "state": state,
            "message": "Ready to scan.",
            "started_at": "",
            "completed_at": "",
            "error": "",
            "total_companies": 0,
            "completed_companies": 0,
            "running_companies": [],
            "elapsed_seconds": 0.0,
        }

    class FakeThread:
        def __init__(self):
            self.started = False

        def start(self):
            self.started = True

    class ImmediateThread:
        def __init__(self, target, daemon=False):
            self.target = target
            self.daemon = daemon

        def start(self):
            self.target()


if __name__ == "__main__":
    unittest.main()
