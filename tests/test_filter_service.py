import unittest

from services.filter_service import get_title_from_url
from services.filter_service import is_bad_url
from services.filter_service import is_job_url


class FilterServiceTest(unittest.TestCase):
    def test_google_job_result_url_is_job_url(self):
        url = (
            "https://www.google.com/about/careers/applications/"
            "jobs/results/92143107436356294-soc-dft-engineer-google-cloud"
        )

        self.assertTrue(is_job_url(url))

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

    def test_title_from_google_job_url_removes_numeric_id(self):
        url = (
            "https://www.google.com/about/careers/applications/"
            "jobs/results/92143107436356294-soc-dft-engineer-google-cloud"
        )

        title = get_title_from_url(url)

        self.assertEqual(title, "Soc Dft Engineer Google Cloud")

    def test_title_from_empty_url_path_is_empty(self):
        title = get_title_from_url("https://www.google.com/")

        self.assertEqual(title, "")


if __name__ == "__main__":
    unittest.main()
