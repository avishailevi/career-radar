from scanner import scan_company


class GenericScanner:
    def scan(self, company: dict, debug: bool = False) -> list[dict]:
        return scan_company(company, debug=debug)
