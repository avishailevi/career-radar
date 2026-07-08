import sys

from companies import companies
from scanners.scanner_factory import ScannerFactory


DEBUG = True


def get_requested_company_names() -> list[str]:
    requested_names = []

    for arg in sys.argv[1:]:
        for name in arg.split(","):
            clean_name = name.strip().lower()
            if clean_name:
                requested_names.append(clean_name)

    return requested_names


def get_companies_to_scan():
    if len(sys.argv) == 1:
        return companies

    requested_company_names = get_requested_company_names()

    matching_companies = [
        company
        for company in companies
        if any(
            requested_name in company["name"].lower()
            for requested_name in requested_company_names
        )
    ]

    return matching_companies


def main():
    print("=" * 50)
    print("🤖 Career Hunter AI")
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
        print(f"Location: {job.get('matched_location', 'Unknown')}")
        print(f"URL: {job['url']}")


if __name__ == "__main__":
    main()
