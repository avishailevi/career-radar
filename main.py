import sys

from services.application_service import get_companies_by_status
from services.application_service import get_companies_to_scan
from services.application_service import get_requested_company_names
from services.application_service import get_visible_new_jobs
from services.application_service import run_scan
from services.application_service import scan_companies
from services.application_service import sort_jobs_by_relevance
from services.job_history_service import get_job_short_id
from services.job_history_service import get_jobs_by_triage_state
from services.job_history_service import set_job_triage_state


def configure_output_encoding() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass


def is_triage_command() -> bool:
    return len(sys.argv) > 1 and sys.argv[1].lower() == "mark"


def is_triage_view_command() -> bool:
    return len(sys.argv) == 2 and sys.argv[1].lower() in {
        "saved",
        "applied",
        "dismissed",
    }


def handle_triage_command() -> None:
    if len(sys.argv) != 4:
        print("Usage: python main.py mark <job_id> <saved|dismissed|applied>")
        return

    result = set_job_triage_state(sys.argv[2], sys.argv[3])
    print(result["message"])


def get_empty_triage_message(state: str) -> str:
    return f"No {state} jobs."


def print_triage_jobs(state: str, jobs: list[dict]) -> None:
    if not jobs:
        print(get_empty_triage_message(state))
        return

    for job in jobs:
        print(f"ID: {get_job_short_id(job)}")
        print(f"Company: {job.get('company', '')}")
        print(f"Title: {job.get('title', '')}")
        print(f"Location: {job.get('matched_location', 'Unknown')}")
        print(f"Matched keyword: {job.get('matched_keyword', 'Unknown')}")
        print(f"URL: {job.get('url', '')}")
        print(f"First seen: {job.get('first_seen', '')}")
        print(f"Last seen: {job.get('last_seen', '')}")
        print()


def handle_triage_view_command() -> None:
    state = sys.argv[1].lower()
    print_triage_jobs(state, get_jobs_by_triage_state(state))


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

    if is_triage_view_command():
        handle_triage_view_command()
        return

    companies_to_scan = get_companies_to_scan(sys.argv[1:])

    if not companies_to_scan:
        print("No matching company found.")
        return

    scan_result = run_scan(sys.argv[1:])

    print_daily_summary(
        companies_scanned=scan_result["companies_scanned"],
        relevant_jobs_count=scan_result["relevant_jobs_count"],
        new_jobs=scan_result["visible_new_jobs"],
        previously_seen_count=scan_result["previously_seen_count"],
        scan_health=scan_result["scan_health"],
    )


if __name__ == "__main__":
    main()
