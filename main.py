import sys
import io
import os
from collections import defaultdict
from contextlib import redirect_stdout

from companies import companies
from scanners.scanner_factory import ScannerFactory
from services.email_service import send_email_digest
from services.job_history_service import get_job_short_id
from services.job_history_service import is_dismissed_job
from services.job_history_service import set_job_triage_state
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


def is_triage_command() -> bool:
    return len(sys.argv) > 1 and sys.argv[1].lower() == "mark"


def handle_triage_command() -> None:
    if len(sys.argv) != 4:
        print("Usage: python main.py mark <job_id> <saved|dismissed|applied>")
        return

    result = set_job_triage_state(sys.argv[2], sys.argv[3])
    print(result["message"])


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


def get_confidence_rank(job: dict) -> int:
    confidence_order = {
        "high": 3,
        "medium": 2,
        "low": 1,
    }
    return confidence_order.get(job.get("match_confidence"), 0)


def sort_jobs_by_relevance(jobs: list[dict]) -> list[dict]:
    return sorted(
        jobs,
        key=lambda job: (
            -get_confidence_rank(job),
            -job.get("relevance_score", 0),
            job.get("company", ""),
            job.get("title", ""),
        ),
    )


def get_visible_new_jobs(new_jobs: list[dict]) -> list[dict]:
    return [
        job
        for job in new_jobs
        if not is_dismissed_job(job)
    ]


def scan_companies(companies_to_scan: list[dict]) -> tuple[list[dict], list[dict]]:
    all_jobs = []
    scan_health = []

    for company in companies_to_scan:
        company_name = company["name"]

        try:
            jobs = scan_company(company)
        except Exception:
            scan_health.append(
                {
                    "company": company_name,
                    "status": "failed",
                }
            )
            continue

        all_jobs.extend(jobs)
        status = "success_with_jobs" if jobs else "success_zero_jobs"
        scan_health.append(
            {
                "company": company_name,
                "status": status,
            }
        )

    return all_jobs, scan_health


def get_companies_by_status(scan_health: list[dict], status: str) -> list[str]:
    return [
        result["company"]
        for result in scan_health
        if result["status"] == status
    ]


def format_company_count(label: str, companies: list[str]) -> str:
    if not companies:
        return f"{label}: 0"

    return f"{label}: {len(companies)} ({', '.join(companies)})"


def print_daily_summary(
    companies_scanned: int,
    relevant_jobs_count: int,
    new_jobs: list[dict],
    previously_seen_count: int,
    scan_health: list[dict],
) -> None:
    new_job_companies = sorted({job["company"] for job in new_jobs})
    companies_with_jobs = get_companies_by_status(scan_health, "success_with_jobs")
    companies_with_zero_jobs = get_companies_by_status(scan_health, "success_zero_jobs")
    failed_companies = get_companies_by_status(scan_health, "failed")

    print("=" * 40)
    print("Career Radar")
    print("=" * 40)
    print()
    print(f"Companies scanned: {companies_scanned}")
    print(format_company_count("Companies with relevant jobs", companies_with_jobs))
    print(format_company_count("Companies with zero relevant jobs", companies_with_zero_jobs))
    print(format_company_count("Failed companies", failed_companies))
    print(f"Relevant jobs: {relevant_jobs_count}")
    print(f"NEW jobs: {len(new_jobs)}")

    if new_job_companies:
        print(f"Companies containing NEW jobs: {', '.join(new_job_companies)}")

    print()
    print("-" * 40)
    print()

    if new_jobs:
        for job in sort_jobs_by_relevance(new_jobs):
            print(f"{job['company']}")
            print(f"* {job['title']}")
            print(f"  ID: {get_job_short_id(job)}")
            print(f"  Location: {job.get('matched_location', 'Unknown')}")
            print(f"  Matched: {job.get('matched_keyword', 'Unknown')}")
            print(f"  URL: {job['url']}")
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

    if is_triage_command():
        handle_triage_command()
        return

    companies_to_scan = get_companies_to_scan()

    if not companies_to_scan:
        print("No matching company found.")
        return

    all_jobs, scan_health = scan_companies(companies_to_scan)

    history_result = update_job_history(all_jobs)
    new_jobs = history_result["new_jobs"]
    visible_new_jobs = get_visible_new_jobs(new_jobs)
    send_email_digest(visible_new_jobs)

    print_daily_summary(
        companies_scanned=len(companies_to_scan),
        relevant_jobs_count=len(all_jobs),
        new_jobs=visible_new_jobs,
        previously_seen_count=history_result["previously_seen_count"],
        scan_health=scan_health,
    )


if __name__ == "__main__":
    main()
