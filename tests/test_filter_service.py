import unittest

from services.filter_service import clean_link_title
from services.filter_service import evaluate_job_relevance
from services.filter_service import find_matching_keyword
from services.filter_service import find_matching_location
from services.filter_service import get_title_from_url
from services.filter_service import is_bad_url
from services.filter_service import is_identifier_title
from services.filter_service import is_job_list_url
from services.filter_service import is_job_url


class FilterServiceTest(unittest.TestCase):
    def test_clean_link_title_uses_first_non_empty_line(self):
        title = clean_link_title(
            "\nApplications Engineer\nRaanana, Israel\nCategory: Engineering"
        )

        self.assertEqual(title, "Applications Engineer")

    def test_google_job_result_url_is_job_url(self):
        url = (
            "https://www.google.com/about/careers/applications/"
            "jobs/results/92143107436356294-soc-dft-engineer-google-cloud"
        )

        self.assertTrue(is_job_url(url))

    def test_hw_keyword_matches_hardware_abbreviation(self):
        matched_keyword = find_matching_keyword("Computing HW Engineer")

        self.assertEqual(matched_keyword, "HW")

    def test_rehovot_location_matches(self):
        matched_location = find_matching_location("Computing HW Engineer in Rehovot")

        self.assertEqual(matched_location, "Rehovot")

    def test_hyphenated_petah_tikva_location_matches(self):
        matched_location = find_matching_location(
            "https://cadence.dejobs.org/petah-tikva-isr/job/"
        )

        self.assertEqual(matched_location, "Petah-Tikva")

    def test_co_il_domain_does_not_match_location(self):
        matched_location = find_matching_location("https://jobs.iai.co.il/job/76043122")

        self.assertIsNone(matched_location)

    def test_google_job_result_url_is_not_bad_url(self):
        url = (
            "https://www.google.com/about/careers/applications/"
            "jobs/results/92143107436356294-soc-dft-engineer-google-cloud"
        )

        self.assertFalse(is_bad_url(url))

    def test_google_results_listing_url_is_not_job_url(self):
        url = (
            "https://www.google.com/about/careers/applications/"
            "jobs/results/?location=Israel&page=2"
        )

        self.assertFalse(is_job_url(url))

    def test_pdf_url_is_bad_url(self):
        url = "https://careers.google.com/jobs/dist/legal/EEOC.pdf"

        self.assertTrue(is_bad_url(url))

    def test_nuvoton_job_url_is_job_url(self):
        url = (
            "https://nuvoton.co.il/careers/co/chip-design/60.D63/"
            "chip-design-engineer/all"
        )

        self.assertTrue(is_job_url(url))

    def test_nuvoton_category_url_is_not_job_url(self):
        url = "https://nuvoton.co.il/careers/co/architecture/all"

        self.assertFalse(is_job_url(url))

    def test_dejobs_job_detail_url_is_job_url(self):
        url = (
            "https://cadence.dejobs.org/petah-tikva-isr/"
            "functional-verification-engineer/26E331/job/"
        )

        self.assertTrue(is_job_url(url))

    def test_dejobs_listing_url_is_not_job_url(self):
        url = "https://cadence.dejobs.org/locations/isr/jobs/"

        self.assertFalse(is_job_url(url))

    def test_workday_job_detail_url_is_job_url(self):
        url = (
            "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite/"
            "job/Israel-Tel-Aviv/Senior-Physical-Design-Engineer_JR1999999"
        )

        self.assertTrue(is_job_url(url))

    def test_workday_listing_url_is_not_job_url(self):
        url = "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite"

        self.assertFalse(is_job_url(url))

    def test_workday_listing_url_is_job_list_url(self):
        url = "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite"

        self.assertTrue(is_job_list_url(url))

    def test_company_home_page_is_not_job_list_url(self):
        url = "https://www.marvell.com/company/careers.html"

        self.assertFalse(is_job_list_url(url))

    def test_title_from_google_job_url_removes_numeric_id(self):
        url = (
            "https://www.google.com/about/careers/applications/"
            "jobs/results/92143107436356294-soc-dft-engineer-google-cloud"
        )

        title = get_title_from_url(url)

        self.assertEqual(title, "Soc Dft Engineer Google Cloud")

    def test_title_from_mobileye_job_url_uses_title_slug_before_identifier(self):
        url = (
            "https://careers.mobileye.com/jobs/3d-algorithm-developer/"
            "bb661a53-79b8-459d-a8df-5dd419d62596"
        )

        title = get_title_from_url(url)

        self.assertEqual(title, "3D Algorithm Developer")

    def test_title_from_empty_url_path_is_empty(self):
        title = get_title_from_url("https://www.google.com/")

        self.assertEqual(title, "")

    def test_uuid_like_title_is_identifier_title(self):
        title = "Bb661A53 79B8 459D A8Df 5Dd419D62596"

        self.assertTrue(is_identifier_title(title))

    def test_normal_job_title_is_not_identifier_title(self):
        title = "Senior Silicon Physical Design Engineer"

        self.assertFalse(is_identifier_title(title))

    def test_strong_hardware_title_has_high_confidence(self):
        relevance = evaluate_job_relevance(
            "Senior RTL Design Engineer",
            "Hardware Engineering role in Haifa",
            "Haifa",
        )

        self.assertEqual(relevance["matched_keyword"], "RTL")
        self.assertGreaterEqual(relevance["relevance_score"], 75)
        self.assertEqual(relevance["match_confidence"], "high")

    def test_weak_body_keyword_without_strong_context_is_filtered(self):
        relevance = evaluate_job_relevance(
            "Program Manager",
            "Work with hardware teams on delivery planning",
            "Haifa",
        )

        self.assertIsNone(relevance)

    def test_sparse_hardware_engineer_title_still_passes(self):
        relevance = evaluate_job_relevance(
            "Hardware Engineer",
            "",
            "Haifa",
        )

        self.assertEqual(relevance["matched_keyword"], "Hardware")
        self.assertEqual(relevance["relevance_score"], 50)
        self.assertEqual(relevance["match_confidence"], "medium")

    def test_negative_title_suppresses_weak_positive_match(self):
        relevance = evaluate_job_relevance(
            "Product Marketing Manager",
            "Hardware product launch role in Israel",
            "Israel",
        )

        self.assertIsNone(relevance)

    def test_system_engineer_requires_hardware_context(self):
        weak_relevance = evaluate_job_relevance(
            "System Engineer",
            "Cross-functional delivery role",
            "Haifa",
        )
        strong_relevance = evaluate_job_relevance(
            "System Engineer",
            "RF and FPGA system design role",
            "Haifa",
        )

        self.assertIsNone(weak_relevance)
        self.assertIsNotNone(strong_relevance)
        self.assertEqual(strong_relevance["matched_keyword"], "FPGA")

    def test_city_location_scores_higher_than_broad_israel_location(self):
        broad_relevance = evaluate_job_relevance(
            "Firmware Engineer",
            "Embedded firmware role",
            "Israel",
        )
        city_relevance = evaluate_job_relevance(
            "Firmware Engineer",
            "Embedded firmware role",
            "Haifa",
        )

        self.assertLess(
            broad_relevance["relevance_score"],
            city_relevance["relevance_score"],
        )


if __name__ == "__main__":
    unittest.main()
