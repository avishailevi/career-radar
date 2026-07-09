from scanners.amazon_scanner import AmazonScanner
from scanners.apple_scanner import AppleScanner
from scanners.dejobs_scanner import DejobsScanner
from scanners.generic_scanner import GenericScanner
from scanners.google_scanner import GoogleScanner
from scanners.microsoft_scanner import MicrosoftScanner
from scanners.synopsys_scanner import SynopsysScanner
from scanners.workday_scanner import WorkdayScanner


class ScannerFactory:
    SCANNERS = {
        "amazon": AmazonScanner,
        "apple": AppleScanner,
        "custom": GenericScanner,
        "dejobs": DejobsScanner,
        "generic": GenericScanner,
        "google": GoogleScanner,
        "microsoft": MicrosoftScanner,
        "synopsys": SynopsysScanner,
        "workday": WorkdayScanner,
    }

    @staticmethod
    def scan(company: dict, debug: bool = False) -> list[dict]:
        platform = company.get("platform", "generic")
        scanner_class = ScannerFactory.SCANNERS.get(platform, GenericScanner)

        return scanner_class().scan(company, debug=debug)
