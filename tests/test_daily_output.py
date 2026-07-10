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

    def test_main_sends_email_only_for_visible_new_jobs(self):
        visible_job = self.build_job("Qualcomm", "Best Job", "high", 80)
        dismissed_job = self.build_job("Apple", "Dismissed Job", "high", 90)
        dismissed_job["triage_state"] = "dismissed"

        with patch("main.get_companies_to_scan", return_value=[{"name": "Apple"}]):
            with patch("main.scan_companies", return_value=([], [])):
                with patch(
                    "main.update_job_history",
                    return_value={
                        "new_jobs": [dismissed_job, visible_job],
                        "previously_seen_count": 0,
                    },
                ):
                    with patch("main.print_daily_summary") as print_summary:
                        with patch("main.send_email_digest") as send_email:
                            main.main()

        send_email.assert_called_once_with([visible_job])
        print_summary.assert_called_once()
        self.assertEqual(print_summary.call_args.kwargs["new_jobs"], [visible_job])

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
