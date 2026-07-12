import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import main


class DailyOutputTest(unittest.TestCase):
    def test_sort_jobs_by_relevance_uses_confidence_then_score(self):
        jobs = [
            self.build_job("Apple", "Medium High Score", "medium", 95),
            self.build_job("Qualcomm", "High Lower Score", "high", 70),
            self.build_job("Intel", "Medium Lower Score", "medium", 60),
            self.build_job("NVIDIA", "High Higher Score", "high", 90),
        ]

        sorted_titles = [
            job["title"]
            for job in main.sort_jobs_by_relevance(jobs)
        ]

        self.assertEqual(
            sorted_titles,
            [
                "High Higher Score",
                "High Lower Score",
                "Medium High Score",
                "Medium Lower Score",
            ],
        )

    def test_daily_summary_prints_new_jobs_in_relevance_order(self):
        new_jobs = [
            self.build_job("Apple", "Medium Job", "medium", 90),
            self.build_job("Qualcomm", "Best Job", "high", 80),
        ]
        scan_health = [
            {"company": "Apple", "status": "success_with_jobs"},
            {"company": "Qualcomm", "status": "success_with_jobs"},
        ]
        output = io.StringIO()

        with redirect_stdout(output):
            main.print_daily_summary(
                companies_scanned=2,
                relevant_jobs_count=2,
                new_jobs=new_jobs,
                previously_seen_count=0,
                scan_health=scan_health,
            )

        text = output.getvalue()

        self.assertLess(text.index("Best Job"), text.index("Medium Job"))
        self.assertIn("Location: Israel", text)
        self.assertIn("Matched: ASIC", text)
        self.assertIn("URL: https://example.com/best-job", text)
        self.assertIn("ID: ", text)
        self.assertNotIn("Confidence:", text)
        self.assertNotIn("Score:", text)

    def test_dismissed_jobs_are_excluded_from_visible_new_jobs(self):
        visible_job = self.build_job("Qualcomm", "Best Job", "high", 80)
        dismissed_job = self.build_job("Apple", "Dismissed Job", "high", 90)
        dismissed_job["triage_state"] = "dismissed"

        visible_jobs = main.get_visible_new_jobs([dismissed_job, visible_job])

        self.assertEqual(visible_jobs, [visible_job])

    def test_main_formats_structured_scan_result(self):
        visible_job = self.build_job("Qualcomm", "Best Job", "high", 80)

        with patch("main.sys.argv", ["main.py"]):
            with patch("main.get_companies_to_scan", return_value=[{"name": "Apple"}]):
                with patch(
                    "main.run_scan",
                    return_value={
                        "companies_scanned": 1,
                        "relevant_jobs_count": 1,
                        "visible_new_jobs": [visible_job],
                        "previously_seen_count": 0,
                        "scan_health": [
                            {"company": "Apple", "status": "success_with_jobs"},
                        ],
                    },
                ) as run_scan:
                    with patch("main.print_daily_summary") as print_summary:
                        main.main()

        run_scan.assert_called_once_with([])
        print_summary.assert_called_once()
        self.assertEqual(print_summary.call_args.kwargs["new_jobs"], [visible_job])

    def test_cli_company_filter_passes_args_to_scan_service(self):
        visible_job = self.build_job("Apple", "Best Job", "high", 80)

        with patch("main.sys.argv", ["main.py", "Apple"]):
            with patch("main.get_companies_to_scan", return_value=[{"name": "Apple"}]):
                with patch(
                    "main.run_scan",
                    return_value={
                        "companies_scanned": 1,
                        "relevant_jobs_count": 1,
                        "visible_new_jobs": [visible_job],
                        "previously_seen_count": 0,
                        "scan_health": [
                            {"company": "Apple", "status": "success_with_jobs"},
                        ],
                    },
                ) as run_scan:
                    with patch("main.print_daily_summary") as print_summary:
                        main.main()

        run_scan.assert_called_once_with(["Apple"])
        print_summary.assert_called_once()

    def test_mark_command_does_not_scan(self):
        output = io.StringIO()

        with patch("main.sys.argv", ["main.py", "mark", "abc12345", "saved"]):
            with patch(
                "main.set_job_triage_state",
                return_value={"message": "Marked abc12345 as saved: ASIC Engineer"},
            ) as set_state:
                with patch("main.scan_companies") as scan_companies:
                    with redirect_stdout(output):
                        main.main()

        set_state.assert_called_once_with("abc12345", "saved")
        scan_companies.assert_not_called()
        self.assertIn("Marked abc12345 as saved", output.getvalue())

    def test_saved_command_prints_saved_jobs_without_scanning(self):
        output = io.StringIO()
        jobs = [
            {
                "job_id": "1234567890abcdef",
                "company": "Apple",
                "title": "Physical Design Engineer",
                "url": "https://apple.test/1",
                "matched_keyword": "ASIC",
                "matched_location": "Israel",
                "first_seen": "2026-07-10T06:00:00+00:00",
                "last_seen": "2026-07-12T06:00:00+00:00",
            }
        ]

        with patch("main.sys.argv", ["main.py", "saved"]):
            with patch("main.get_jobs_by_triage_state", return_value=jobs) as get_jobs:
                with patch("main.scan_companies") as scan_companies:
                    with redirect_stdout(output):
                        main.main()

        get_jobs.assert_called_once_with("saved")
        scan_companies.assert_not_called()
        text = output.getvalue()
        self.assertIn("ID: 12345678", text)
        self.assertIn("Company: Apple", text)
        self.assertIn("Title: Physical Design Engineer", text)
        self.assertIn("Location: Israel", text)
        self.assertIn("Matched keyword: ASIC", text)
        self.assertIn("URL: https://apple.test/1", text)
        self.assertIn("First seen: 2026-07-10T06:00:00+00:00", text)
        self.assertIn("Last seen: 2026-07-12T06:00:00+00:00", text)

    def test_applied_command_empty_state_without_scanning(self):
        output = io.StringIO()

        with patch("main.sys.argv", ["main.py", "applied"]):
            with patch("main.get_jobs_by_triage_state", return_value=[]):
                with patch("main.scan_companies") as scan_companies:
                    with redirect_stdout(output):
                        main.main()

        scan_companies.assert_not_called()
        self.assertEqual(output.getvalue().strip(), "No applied jobs.")

    def test_dismissed_command_empty_state_without_scanning(self):
        output = io.StringIO()

        with patch("main.sys.argv", ["main.py", "dismissed"]):
            with patch("main.get_jobs_by_triage_state", return_value=[]):
                with patch("main.scan_companies") as scan_companies:
                    with redirect_stdout(output):
                        main.main()

        scan_companies.assert_not_called()
        self.assertEqual(output.getvalue().strip(), "No dismissed jobs.")

    def test_saved_command_empty_state_without_scanning(self):
        output = io.StringIO()

        with patch("main.sys.argv", ["main.py", "saved"]):
            with patch("main.get_jobs_by_triage_state", return_value=[]):
                with patch("main.scan_companies") as scan_companies:
                    with redirect_stdout(output):
                        main.main()

        scan_companies.assert_not_called()
        self.assertEqual(output.getvalue().strip(), "No saved jobs.")

    def build_job(self, company, title, confidence, score):
        slug = title.lower().replace(" ", "-")
        return {
            "company": company,
            "title": title,
            "job_id": f"{slug}-job-id",
            "url": f"https://example.com/{slug}",
            "matched_keyword": "ASIC",
            "matched_location": "Israel",
            "match_confidence": confidence,
            "relevance_score": score,
        }


if __name__ == "__main__":
    unittest.main()
