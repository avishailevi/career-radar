import sys
import io
import os
from collections import defaultdict
from contextlib import redirect_stdout

from companies import companies
from scanners.scanner_factory import ScannerFactory
from services.email_service import send_email_digest
from services.job_history_service import update_job_history


DEBUG = os.environ.get("CAREER_RADAR_DEBUG", "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


def configure_output_encoding() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass


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


def scan_company(company: dict) -> list[dict]:
    if DEBUG:
        return ScannerFactory.scan(company, debug=True)

    with redirect_stdout(io.StringIO()):
        return ScannerFactory.scan(company, debug=False)


def group_jobs_by_company(jobs: list[dict]) -> dict:
    grouped_jobs = defaultdict(list)

    for job in jobs:
        grouped_jobs[job["company"]].append(job)

    return dict(sorted(grouped_jobs.items()))


def print_daily_summary(
    companies_scanned: int,
    relevant_jobs_count: int,
    new_jobs: list[dict],
    previously_seen_count: int,
) -> None:
    new_job_companies = sorted({job["company"] for job in new_jobs})

    print("=" * 40)
    print("Career Radar")
    print("=" * 40)
    print()
    print(f"Companies scanned: {companies_scanned}")
    print(f"Relevant jobs: {relevant_jobs_count}")
    print(f"NEW jobs: {len(new_jobs)}")

    if new_job_companies:
        print(f"Companies containing NEW jobs: {', '.join(new_job_companies)}")

    print()
    print("-" * 40)
    print()

    if new_jobs:
        for company, company_jobs in group_jobs_by_company(new_jobs).items():
            print(company)
            print()

            for job in company_jobs:
                print(f"* {job['title']}")

            print()
    else:
        print("No new jobs today.")
        print()

    print("-" * 40)
    print()
    print(f"Previously seen jobs: {previously_seen_count}")
    print()
    print("=" * 40)


def main():
    configure_output_encoding()

    companies_to_scan = get_companies_to_scan()

    if not companies_to_scan:
        print("No matching company found.")
        return

    all_jobs = []

    for company in companies_to_scan:
        jobs = scan_company(company)
        all_jobs.extend(jobs)

    history_result = update_job_history(all_jobs)
    new_jobs = history_result["new_jobs"]
    send_email_digest(new_jobs)

    print_daily_summary(
        companies_scanned=len(companies_to_scan),
        relevant_jobs_count=len(all_jobs),
        new_jobs=new_jobs,
        previously_seen_count=history_result["previously_seen_count"],
    )


if __name__ == "__main__":
    main()
