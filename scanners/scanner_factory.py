from scanners.amazon_scanner import AmazonScanner
from scanners.apple_scanner import AppleScanner
from scanners.comeet_scanner import ComeetScanner
from scanners.dejobs_scanner import DejobsScanner
from scanners.eightfold_scanner import EightfoldScanner
from scanners.generic_scanner import GenericScanner
from scanners.getro_scanner import GetroScanner
from scanners.google_scanner import GoogleScanner
from scanners.microsoft_scanner import MicrosoftScanner
from scanners.static_json_scanner import StaticJsonScanner
from scanners.synopsys_scanner import SynopsysScanner
from scanners.workday_scanner import WorkdayScanner


class ScannerFactory:
    SCANNERS = {
        "amazon": AmazonScanner,
        "apple": AppleScanner,
        "comeet": ComeetScanner,
        "custom": GenericScanner,
        "dejobs": DejobsScanner,
        "eightfold": EightfoldScanner,
        "generic": GenericScanner,
        "getro": GetroScanner,
        "google": GoogleScanner,
        "microsoft": MicrosoftScanner,
        "static_json": StaticJsonScanner,
        "synopsys": SynopsysScanner,
        "workday": WorkdayScanner,
    }

    @staticmethod
    def scan(company: dict, debug: bool = False) -> list[dict]:
        platform = company.get("platform", "generic")
        scanner_class = ScannerFactory.SCANNERS.get(platform, GenericScanner)

        return scanner_class().scan(company, debug=debug)
