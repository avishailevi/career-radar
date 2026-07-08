from scanners.generic_scanner import GenericScanner
from scanners.workday_scanner import WorkdayScanner


class ScannerFactory:
    @staticmethod
    def scan(company: dict, debug: bool = False) -> list[dict]:
        platform = company.get("platform", "generic")

        if platform == "workday":
            return WorkdayScanner().scan(company, debug=debug)

        return GenericScanner().scan(company, debug=debug)
