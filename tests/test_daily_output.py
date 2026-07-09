import io
import unittest
from contextlib import redirect_stdout

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
        self.assertNotIn("Confidence:", text)
        self.assertNotIn("Score:", text)

    def build_job(self, company, title, confidence, score):
        slug = title.lower().replace(" ", "-")
        return {
            "company": company,
            "title": title,
            "url": f"https://example.com/{slug}",
            "matched_keyword": "ASIC",
            "matched_location": "Israel",
            "match_confidence": confidence,
            "relevance_score": score,
        }


if __name__ == "__main__":
    unittest.main()
