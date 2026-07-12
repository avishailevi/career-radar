import unittest
from unittest.mock import patch

import local_app


class LocalAppTest(unittest.TestCase):
    def setUp(self):
        local_app.app.config["TESTING"] = True
        self.client = local_app.app.test_client()

    def test_new_jobs_empty_state_renders_without_scan(self):
        with patch("local_app.get_latest_new_jobs", return_value=[]):
            with patch("local_app.get_latest_scan_summary", return_value=self.summary()):
                with patch("local_app.get_scan_status", return_value=self.status()):
                    response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"No new jobs from the latest scan.", response.data)
        self.assertIn(b'href="/relevant"', response.data)
        self.assertIn(b'href="/"', response.data)
        self.assertIn(b"Relevant jobs", response.data)
        self.assertIn(b"New jobs", response.data)
        self.assertNotIn(b'<a class="summary-card summary-link" href="">', response.data)

    def test_summary_cards_navigation_does_not_scan(self):
        with patch("local_app.run_scan") as run_scan:
            with patch("local_app.get_latest_new_jobs", return_value=[]):
                with patch("local_app.get_latest_scan_summary", return_value=self.summary()):
                    with patch("local_app.get_scan_status", return_value=self.status()):
                        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.count(b'class="summary-card summary-link"'), 2)
        self.assertIn(b'<span>Companies scanned</span>', response.data)
        self.assertIn(b'href="/"', response.data)
        self.assertIn(b'href="/relevant"', response.data)
        run_scan.assert_not_called()

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

        with patch("local_app.get_latest_relevant_jobs", return_value=jobs) as get_jobs:
            with patch("local_app.run_scan") as run_scan:
                with patch("local_app.get_latest_scan_summary", return_value=self.summary()):
                    with patch("local_app.get_scan_status", return_value=self.status()):
                        response = self.client.get("/relevant")

        self.assertEqual(response.status_code, 200)
        get_jobs.assert_called_once_with(local_app.HISTORY_PATH)
        run_scan.assert_not_called()
        self.assertIn(b"Relevant Jobs", response.data)
        self.assertIn(b"ASIC Engineer", response.data)
        self.assertIn(b"Short ID", response.data)
        self.assertIn(b"12345678", response.data)

    def test_relevant_view_empty_state_when_metadata_is_missing(self):
        with patch("local_app.get_latest_relevant_jobs", return_value=[]):
            with patch("local_app.get_latest_scan_summary", return_value=self.summary()):
                with patch("local_app.get_scan_status", return_value=self.status()):
                    response = self.client.get("/relevant")

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            b"No relevant-job list is stored for the latest scan.",
            response.data,
        )
        self.assertIn(b"Run Scan Now to refresh it.", response.data)

    def test_saved_view_uses_local_history_without_running_scan(self):
        with patch("local_app.get_triage_jobs", return_value=[]) as get_triage_jobs:
            with patch("local_app.run_scan") as run_scan:
                with patch("local_app.get_latest_scan_summary", return_value=self.summary()):
                    with patch("local_app.get_scan_status", return_value=self.status()):
                        response = self.client.get("/saved")

        self.assertEqual(response.status_code, 200)
        get_triage_jobs.assert_called_once_with("saved", local_app.HISTORY_PATH)
        run_scan.assert_not_called()
        self.assertIn(b"No saved jobs.", response.data)

    def test_applied_view_uses_local_history_without_running_scan(self):
        with patch("local_app.get_triage_jobs", return_value=[]) as get_triage_jobs:
            with patch("local_app.run_scan") as run_scan:
                with patch("local_app.get_latest_scan_summary", return_value=self.summary()):
                    with patch("local_app.get_scan_status", return_value=self.status()):
                        response = self.client.get("/applied")

        self.assertEqual(response.status_code, 200)
        get_triage_jobs.assert_called_once_with("applied", local_app.HISTORY_PATH)
        run_scan.assert_not_called()
        self.assertIn(b"No applied jobs.", response.data)

    def test_dismissed_view_uses_local_history_without_running_scan(self):
        with patch("local_app.get_triage_jobs", return_value=[]) as get_triage_jobs:
            with patch("local_app.run_scan") as run_scan:
                with patch("local_app.get_latest_scan_summary", return_value=self.summary()):
                    with patch("local_app.get_scan_status", return_value=self.status()):
                        response = self.client.get("/dismissed")

        self.assertEqual(response.status_code, 200)
        get_triage_jobs.assert_called_once_with("dismissed", local_app.HISTORY_PATH)
        run_scan.assert_not_called()
        self.assertIn(b"No dismissed jobs.", response.data)

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

    def test_scan_health_empty_state_renders(self):
        with patch("local_app.get_latest_scan_health", return_value=[]):
            with patch("local_app.get_latest_scan_summary", return_value=self.summary()):
                with patch("local_app.get_scan_status", return_value=self.status()):
                    response = self.client.get("/scan-health")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"No scan has completed yet.", response.data)

    def test_auto_refresh_only_while_scan_is_running(self):
        with patch("local_app.get_latest_new_jobs", return_value=[]):
            with patch("local_app.get_latest_scan_summary", return_value=self.summary()):
                with patch("local_app.get_scan_status", return_value=self.status("running")):
                    running_response = self.client.get("/")

        with patch("local_app.get_latest_new_jobs", return_value=[]):
            with patch("local_app.get_latest_scan_summary", return_value=self.summary()):
                with patch("local_app.get_scan_status", return_value=self.status("completed")):
                    completed_response = self.client.get("/")

        self.assertIn(b'http-equiv="refresh"', running_response.data)
        self.assertIn(b'content="3"', running_response.data)
        self.assertNotIn(b'http-equiv="refresh"', completed_response.data)

    def test_failed_scan_message_renders_without_stack_trace(self):
        status = self.status("failed")
        status["message"] = "Scan failed."
        status["error"] = "Could not complete the scan."

        with patch("local_app.get_latest_new_jobs", return_value=[]):
            with patch("local_app.get_latest_scan_summary", return_value=self.summary()):
                with patch("local_app.get_scan_status", return_value=status):
                    response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Scan failed.", response.data)
        self.assertIn(b"Could not complete the scan.", response.data)
        self.assertNotIn(b"Traceback", response.data)

    def summary(self):
        return {
            "companies_scanned": 0,
            "companies_with_relevant_jobs": [],
            "companies_with_zero_relevant_jobs": [],
            "failed_companies": [],
            "relevant_jobs_count": 0,
            "new_jobs_count": 0,
        }

    def status(self, state="idle"):
        return {
            "state": state,
            "message": "Ready to scan.",
            "started_at": "",
            "completed_at": "",
            "error": "",
        }

    class FakeThread:
        def __init__(self):
            self.started = False

        def start(self):
            self.started = True


if __name__ == "__main__":
    unittest.main()
