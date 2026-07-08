from scanner import scan_company


class AmazonScanner:
    def scan(self, company: dict, debug: bool = False) -> list[dict]:
        return scan_company(company, debug=debug)
