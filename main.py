import sys

from companies import companies
from scanners.scanner_factory import ScannerFactory


DEBUG = True


def configure_output_encoding() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass


def get_companies_to_scan():
    if len(sys.argv) == 1:
        return companies

    requested_company = " ".join(sys.argv[1:]).lower()

    matching_companies = [
        company
        for company in companies
        if requested_company in company["name"].lower()
    ]

    return matching_companies


def main():
    configure_output_encoding()

    print("=" * 50)
    print("Career Radar")
    print("=" * 50)

    companies_to_scan = get_companies_to_scan()

    if not companies_to_scan:
        print("No matching company found.")
        return

    all_jobs = []

    for company in companies_to_scan:
        jobs = ScannerFactory.scan(company, debug=DEBUG)
        all_jobs.extend(jobs)

    print("\nRelevant jobs found:")
    print("=" * 50)

    if not all_jobs:
        print("No relevant jobs found.")
        return

    for job in all_jobs:
        print(f"\nCompany: {job['company']}")
        print(f"Title: {job['title']}")
        print(f"Matched: {job['matched_keyword']}")
        print(f"URL: {job['url']}")


if __name__ == "__main__":
    main()
