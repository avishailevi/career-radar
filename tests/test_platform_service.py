import unittest

from services.platform_service import should_follow_job_list_link
from services.platform_service import should_read_detail_pages


class PlatformServiceTest(unittest.TestCase):
    def test_workday_reads_detail_pages_and_follows_job_list_link(self):
        company = {"platform": "workday"}

        self.assertTrue(should_read_detail_pages(company))
        self.assertTrue(should_follow_job_list_link(company))

    def test_apple_reads_detail_pages_without_following_job_list_link(self):
        company = {"platform": "apple"}

        self.assertTrue(should_read_detail_pages(company))
        self.assertFalse(should_follow_job_list_link(company))

    def test_amazon_does_not_read_detail_pages_or_follow_job_list_link(self):
        company = {"platform": "amazon"}

        self.assertFalse(should_read_detail_pages(company))
        self.assertFalse(should_follow_job_list_link(company))

    def test_microsoft_reads_detail_pages_and_follows_job_list_link(self):
        company = {"platform": "microsoft"}

        self.assertTrue(should_read_detail_pages(company))
        self.assertTrue(should_follow_job_list_link(company))

    def test_mobileye_reads_detail_pages_and_follows_job_list_link(self):
        company = {"platform": "mobileye"}

        self.assertTrue(should_read_detail_pages(company))
        self.assertTrue(should_follow_job_list_link(company))

    def test_tower_reads_detail_pages_without_following_job_list_link(self):
        company = {"platform": "tower"}

        self.assertTrue(should_read_detail_pages(company))
        self.assertFalse(should_follow_job_list_link(company))

    def test_google_reads_detail_pages_and_follows_job_list_link(self):
        company = {"platform": "google"}

        self.assertTrue(should_read_detail_pages(company))
        self.assertTrue(should_follow_job_list_link(company))

    def test_other_platform_does_not_read_detail_pages(self):
        company = {"platform": "custom"}

        self.assertFalse(should_read_detail_pages(company))
        self.assertTrue(should_follow_job_list_link(company))

    def test_missing_platform_does_not_read_detail_pages(self):
        company = {}

        self.assertFalse(should_read_detail_pages(company))
        self.assertTrue(should_follow_job_list_link(company))


if __name__ == "__main__":
    unittest.main()
