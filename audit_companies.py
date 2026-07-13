import contextlib
import io
import re
import sys
from datetime import datetime
from pathlib import Path

from companies import companies
from scanners.scanner_factory import ScannerFactory


REPORTS_DIR = Path("reports")
STRUCTURED_PLATFORMS = {
    "comeet",
    "eightfold",
    "getro",
    "static_json",
}

COUNTER_PATTERNS = {
    "job_like_urls": r"Job-like URLs:\s*(\d+)",
    "location_matches": r"Location matches:\s*(\d+)",
    "keyword_matches": r"Keyword matches:\s*(\d+)",
    "relevant_jobs": r"Relevant jobs:\s*(\d+)",
    "detail_pages_checked": r"Detail pages checked:\s*(\d+)",
    "detail_pages_attempted": r"Detail pages attempted:\s*(\d+)",
    "detail_pages_verified": r"Detail pages verified:\s*(\d+)",
    "detail_pages_failed": r"Detail pages failed:\s*(\d+)",
    "detail_pages_skipped": r"Detail pages skipped:\s*(\d+)",
    "empty_detail_pages": r"Empty detail pages:\s*(\d+)",
    "page_text_fallbacks": r"Page text fallbacks:\s*(\d+)",
    "listing_fallbacks_used": r"Listing fallbacks used:\s*(\d+)",
    "detail_keyword_matches": r"Detail keyword matches:\s*(\d+)",
}


def get_requested_company_names() -> list[str]:
    requested_names = []

    for arg in sys.argv[1:]:
        for name in arg.split(","):
            clean_name = name.strip().lower()
            if clean_name:
                requested_names.append(clean_name)

    return requested_names


def get_companies_to_audit() -> list[dict]:
    requested_names = get_requested_company_names()

    if not requested_names:
        return companies

    return [
        company
        for company in companies
        if any(
            requested_name in company["name"].lower()
            for requested_name in requested_names
        )
    ]


def parse_counter(output: str, pattern: str) -> int:
    match = re.search(pattern, output)

    if not match:
        return 0

    return int(match.group(1))


def parse_debug_counters(output: str) -> dict[str, int]:
    return {
        name: parse_counter(output, pattern)
        for name, pattern in COUNTER_PATTERNS.items()
    }


def classify_result(
    jobs: list[dict],
    counters: dict[str, int],
    error: str | None,
    platform: str = "generic",
) -> str:
    if error:
        return "ERROR"

    if jobs:
        if platform in STRUCTURED_PLATFORMS:
            return "SUPPORTED"

        if counters["detail_keyword_matches"] > 0:
            return "SUPPORTED"

        return "FALLBACK_ONLY"

    if counters["job_like_urls"] == 0:
        return "NO_JOB_LINKS"

    if counters["location_matches"] == 0:
        return "NO_LOCATION_MATCHES"

    if counters["keyword_matches"] == 0:
        return "NO_KEYWORD_MATCHES"

    return "NO_RELEVANT_JOBS"


def suggest_next_action(status: str, platform: str) -> str:
    if status == "SUPPORTED":
        return "Mark as Supported after reviewing returned jobs."

    if status == "FALLBACK_ONLY":
        return "Returned jobs only from listing/card text; verify real job-detail page extraction."

    if status == "ERROR":
        return "Fix scanner crash or page loading error."

    if status == "NO_JOB_LINKS":
        return f"Improve {platform} job link discovery or add platform-specific scanner."

    if status == "NO_LOCATION_MATCHES":
        return "Check whether location appears only on detail pages or needs location keywords update."

    if status == "NO_KEYWORD_MATCHES":
        return "Check whether jobs are truly irrelevant or keywords need platform/company-specific improvement."

    return "Inspect debug output and decide whether this is expected or needs scanner improvement."


def audit_company(company: dict) -> dict:
    output_buffer = io.StringIO()
    jobs = []
    error = None

    try:
        with contextlib.redirect_stdout(output_buffer):
            jobs = ScannerFactory.scan(company, debug=True)
    except Exception as exc:
        error = repr(exc)

    output = output_buffer.getvalue()
    counters = parse_debug_counters(output)
    platform = company.get("platform", "generic")
    status = classify_result(jobs, counters, error, platform)

    return {
        "company": company["name"],
        "platform": platform,
        "status": status,
        "jobs": jobs,
        "error": error,
        "debug_output": output,
        "counters": counters,
        "next_action": suggest_next_action(
            status,
            platform,
        ),
    }


def build_report(results: list[dict]) -> str:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    supported_count = sum(1 for result in results if result["status"] == "SUPPORTED")

    lines = [
        "# Career Radar Company Audit",
        "",
        f"Generated: {timestamp}",
        f"Companies audited: {len(results)}",
        f"Supported with relevant jobs: {supported_count}",
        "",
        "## Summary",
        "",
        "| Company | Platform | Status | Jobs | Detail verified | Fallbacks | Detail skipped | Job-like URLs | Location matches | Keyword matches | Next action |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]

    for result in results:
        counters = result["counters"]
        lines.append(
            "| "
            f"{result['company']} | "
            f"{result['platform']} | "
            f"{result['status']} | "
            f"{len(result['jobs'])} | "
            f"{counters['detail_keyword_matches']} | "
            f"{counters['listing_fallbacks_used']} | "
            f"{counters['detail_pages_skipped']} | "
            f"{counters['job_like_urls']} | "
            f"{counters['location_matches']} | "
            f"{counters['keyword_matches']} | "
            f"{result['next_action']} |"
        )

    lines.extend(["", "## Relevant jobs", ""])

    for result in results:
        if not result["jobs"]:
            continue

        lines.append(f"### {result['company']}")
        lines.append("")

        for job in result["jobs"]:
            lines.append(f"- {job['title']}")
            lines.append(f"  - Matched: {job['matched_keyword']}")
            lines.append(f"  - Location: {job.get('matched_location', 'Unknown')}")
            if "verification_state" in job:
                lines.append(f"  - Verification: {job['verification_state']}")
            lines.append(f"  - URL: {job['url']}")

        lines.append("")

    lines.extend(["", "## Full debug output", ""])

    for result in results:
        lines.append(f"### {result['company']}")
        lines.append("")

        if result["error"]:
            lines.append(f"ERROR: {result['error']}")
            lines.append("")

        lines.append("```text")
        lines.append(result["debug_output"].strip())
        lines.append("```")
        lines.append("")

    return "\n".join(lines)


def save_report(report: str) -> Path:
    REPORTS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = REPORTS_DIR / f"company_audit_{timestamp}.md"
    report_path.write_text(report, encoding="utf-8")
    return report_path


def main() -> None:
    companies_to_audit = get_companies_to_audit()

    if not companies_to_audit:
        print("No matching companies found.")
        return

    print(f"Auditing {len(companies_to_audit)} companies...")

    results = []

    for company in companies_to_audit:
        print(f"- {company['name']}")
        results.append(audit_company(company))

    report = build_report(results)
    report_path = save_report(report)

    print("\nAudit complete.")
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()
