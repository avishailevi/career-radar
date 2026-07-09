import unittest
from unittest.mock import Mock
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

        workday_scanner_class = Mock()
        workday_scanner = workday_scanner_class.return_value
        workday_scanner.scan.return_value = expected_jobs

        with patch.dict(ScannerFactory.SCANNERS, {"workday": workday_scanner_class}):
            jobs = ScannerFactory.scan(company, debug=True)

        self.assertEqual(jobs, expected_jobs)
        workday_scanner.scan.assert_called_once_with(company, debug=True)

    def test_apple_platform_uses_apple_scanner(self):
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

        apple_scanner_class = Mock()
        apple_scanner = apple_scanner_class.return_value
        apple_scanner.scan.return_value = expected_jobs

        with patch.dict(ScannerFactory.SCANNERS, {"apple": apple_scanner_class}):
            jobs = ScannerFactory.scan(company, debug=False)

        self.assertEqual(jobs, expected_jobs)
        apple_scanner.scan.assert_called_once_with(company, debug=False)

    def test_custom_platform_uses_generic_scanner(self):
        company = {
            "name": "KLA",
            "platform": "custom",
            "url": "https://example.com",
        }

        generic_scanner_class = Mock()
        generic_scanner = generic_scanner_class.return_value
        generic_scanner.scan.return_value = []

        with patch.dict(ScannerFactory.SCANNERS, {"custom": generic_scanner_class}):
            jobs = ScannerFactory.scan(company)

        self.assertEqual(jobs, [])
        generic_scanner.scan.assert_called_once_with(company, debug=False)

    def test_dejobs_platform_uses_dejobs_scanner(self):
        company = {
            "name": "Cadence",
            "platform": "dejobs",
            "url": "https://example.com",
        }

        dejobs_scanner_class = Mock()
        dejobs_scanner = dejobs_scanner_class.return_value
        dejobs_scanner.scan.return_value = []

        with patch.dict(ScannerFactory.SCANNERS, {"dejobs": dejobs_scanner_class}):
            jobs = ScannerFactory.scan(company)

        self.assertEqual(jobs, [])
        dejobs_scanner.scan.assert_called_once_with(company, debug=False)

    def test_eightfold_platform_uses_eightfold_scanner(self):
        company = {
            "name": "Qualcomm",
            "platform": "eightfold",
            "url": "https://example.com",
        }

        eightfold_scanner_class = Mock()
        eightfold_scanner = eightfold_scanner_class.return_value
        eightfold_scanner.scan.return_value = []

        with patch.dict(ScannerFactory.SCANNERS, {"eightfold": eightfold_scanner_class}):
            jobs = ScannerFactory.scan(company)

        self.assertEqual(jobs, [])
        eightfold_scanner.scan.assert_called_once_with(company, debug=False)

    def test_synopsys_platform_uses_synopsys_scanner(self):
        company = {
            "name": "Synopsys",
            "platform": "synopsys",
            "url": "https://example.com",
        }

        synopsys_scanner_class = Mock()
        synopsys_scanner = synopsys_scanner_class.return_value
        synopsys_scanner.scan.return_value = []

        with patch.dict(ScannerFactory.SCANNERS, {"synopsys": synopsys_scanner_class}):
            jobs = ScannerFactory.scan(company)

        self.assertEqual(jobs, [])
        synopsys_scanner.scan.assert_called_once_with(company, debug=False)

    def test_static_json_platform_uses_static_json_scanner(self):
        company = {
            "name": "Elbit",
            "platform": "static_json",
            "url": "https://example.com",
        }

        static_json_scanner_class = Mock()
        static_json_scanner = static_json_scanner_class.return_value
        static_json_scanner.scan.return_value = []

        with patch.dict(
            ScannerFactory.SCANNERS,
            {"static_json": static_json_scanner_class},
        ):
            jobs = ScannerFactory.scan(company)

        self.assertEqual(jobs, [])
        static_json_scanner.scan.assert_called_once_with(company, debug=False)

    def test_missing_platform_uses_generic_scanner(self):
        company = {
            "name": "Unknown",
            "url": "https://example.com",
        }

        generic_scanner_class = Mock()
        generic_scanner = generic_scanner_class.return_value
        generic_scanner.scan.return_value = []

        with patch.dict(ScannerFactory.SCANNERS, {"generic": generic_scanner_class}):
            jobs = ScannerFactory.scan(company)

        self.assertEqual(jobs, [])
        generic_scanner.scan.assert_called_once_with(company, debug=False)


if __name__ == "__main__":
    unittest.main()
