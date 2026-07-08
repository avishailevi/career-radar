from scanner import scan_company
from scanners.workday_scanner import WorkdayScanner


class ScannerFactory:
    @staticmethod
    def scan(company: dict, debug: bool = False) -> list[dict]:
        platform = company.get("platform", "generic")

        if platform == "workday":
            return WorkdayScanner().scan(company, debug=debug)

        return scan_company(company, debug=debug)
