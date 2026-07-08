import unittest
from unittest.mock import patch

from scanners.scanner_factory import ScannerFactory


class ScannerFactoryTest(unittest.TestCase):
    def test_workday_platform_uses_workday_scanner(self):
        company = {
            "name": "NVIDIA",
            "platform": "workday",
            "url": "https://example.com",
        }
        expected_jobs = [
            {
                "company": "NVIDIA",
                "title": "ASIC Engineer",
                "url": "https://example.com/job/1",
                "matched_keyword": "ASIC",
            }
        ]

        with patch(
            "scanners.scanner_factory.WorkdayScanner"
        ) as workday_scanner_class:
            workday_scanner = workday_scanner_class.return_value
            workday_scanner.scan.return_value = expected_jobs

            jobs = ScannerFactory.scan(company, debug=True)

        self.assertEqual(jobs, expected_jobs)
        workday_scanner.scan.assert_called_once_with(company, debug=True)

    def test_other_platform_uses_generic_scanner(self):
        company = {
            "name": "Apple",
            "platform": "apple",
            "url": "https://example.com",
        }
        expected_jobs = [
            {
                "company": "Apple",
                "title": "Hardware Engineer",
                "url": "https://example.com/job/2",
                "matched_keyword": "Hardware",
            }
        ]

        with patch(
            "scanners.scanner_factory.GenericScanner"
        ) as generic_scanner_class:
            generic_scanner = generic_scanner_class.return_value
            generic_scanner.scan.return_value = expected_jobs

            jobs = ScannerFactory.scan(company, debug=False)

        self.assertEqual(jobs, expected_jobs)
        generic_scanner.scan.assert_called_once_with(company, debug=False)

    def test_missing_platform_uses_generic_scanner(self):
        company = {
            "name": "Unknown",
            "url": "https://example.com",
        }

        with patch(
            "scanners.scanner_factory.GenericScanner"
        ) as generic_scanner_class:
            generic_scanner = generic_scanner_class.return_value
            generic_scanner.scan.return_value = []

            jobs = ScannerFactory.scan(company)

        self.assertEqual(jobs, [])
        generic_scanner.scan.assert_called_once_with(company, debug=False)


if __name__ == "__main__":
    unittest.main()
