from scanner import scan_company


class ScannerFactory:
    @staticmethod
    def scan(company: dict, debug: bool = False) -> list[dict]:
        platform = company.get("platform", "generic")

        if platform in {
            "workday",
            "apple",
            "microsoft",
            "google",
            "amazon",
            "custom",
            "generic",
        }:
            return scan_company(company, debug=debug)

        return scan_company(company, debug=debug)
