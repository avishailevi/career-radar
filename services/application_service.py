import io
import os
import threading
from contextlib import redirect_stdout
from datetime import datetime
from datetime import timezone
from pathlib import Path

from companies import companies
from scanners.scanner_factory import ScannerFactory
from services.email_service import send_email_digest
from services.job_history_service import DEFAULT_HISTORY_PATH
from services.job_history_service import generate_job_id_for_job
from services.job_history_service import get_jobs_by_ids
from services.job_history_service import get_jobs_by_triage_state
from services.job_history_service import get_latest_scan
from services.job_history_service import is_dismissed_job
from services.job_history_service import save_latest_scan
from services.job_history_service import set_job_triage_state
from services.job_history_service import update_job_history


DEBUG = os.environ.get("CAREER_RADAR_DEBUG", "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

_scan_lock = threading.Lock()
_scan_status = {
    "state": "idle",
    "message": "Ready to scan.",
    "started_at": "",
    "completed_at": "",
    "error": "",
}
_session_has_scan = False


def get_requested_company_names(args: list[str] | None = None) -> list[str]:
    requested_names = []

    for arg in args or []:
        for name in arg.split(","):
            clean_name = name.strip().lower()
            if clean_name:
                requested_names.append(clean_name)

    return requested_names


def get_companies_to_scan(args: list[str] | None = None) -> list[dict]:
    requested_args = args or []

    if not requested_args:
        return companies

    requested_company_names = get_requested_company_names(requested_args)

    return [
        company
        for company in companies
        if any(
            requested_name in company["name"].lower()
            for requested_name in requested_company_names
        )
    ]


def scan_company(company: dict) -> list[dict]:
    if DEBUG:
        return ScannerFactory.scan(company, debug=True)

    with redirect_stdout(io.StringIO()):
        return ScannerFactory.scan(company, debug=False)


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


def get_stable_job_ids(jobs: list[dict]) -> list[str]:
    job_ids = []
    seen_job_ids = set()

    for job in jobs:
        job_id = generate_job_id_for_job(job)

        if job_id in seen_job_ids:
            continue

        seen_job_ids.add(job_id)
        job_ids.append(job_id)

    return job_ids


def get_companies_by_status(scan_health: list[dict], status: str) -> list[str]:
    return [
        result["company"]
        for result in scan_health
        if result["status"] == status
    ]


def build_scan_summary(
    companies_scanned: int,
    relevant_jobs_count: int,
    new_jobs_count: int,
    scan_health: list[dict],
) -> dict:
    return {
        "companies_scanned": companies_scanned,
        "companies_with_relevant_jobs": get_companies_by_status(
            scan_health,
            "success_with_jobs",
        ),
        "companies_with_zero_relevant_jobs": get_companies_by_status(
            scan_health,
            "success_zero_jobs",
        ),
        "failed_companies": get_companies_by_status(scan_health, "failed"),
        "relevant_jobs_count": relevant_jobs_count,
        "new_jobs_count": new_jobs_count,
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _set_scan_status(state: str, message: str, error: str = "") -> None:
    _scan_status["state"] = state
    _scan_status["message"] = message
    _scan_status["error"] = error

    if state == "running":
        _scan_status["started_at"] = _utc_now()
        _scan_status["completed_at"] = ""

    if state in {"completed", "failed"}:
        _scan_status["completed_at"] = _utc_now()


def get_scan_status() -> dict:
    return dict(_scan_status)


def session_has_scan() -> bool:
    return _session_has_scan


def reset_session_scan_state() -> None:
    global _session_has_scan
    _session_has_scan = False
    _scan_status.update(
        {
            "state": "idle",
            "message": "Ready to scan.",
            "started_at": "",
            "completed_at": "",
            "error": "",
        }
    )


def run_scan(
    company_args: list[str] | None = None,
    history_path: str | Path = DEFAULT_HISTORY_PATH,
) -> dict:
    global _session_has_scan

    if not _scan_lock.acquire(blocking=False):
        return {
            "status": "already_running",
            "message": "A scan is already in progress.",
            "scan_status": get_scan_status(),
        }

    _set_scan_status("running", "Scan in progress.")

    try:
        companies_to_scan = get_companies_to_scan(company_args)

        if not companies_to_scan:
            result = {
                "status": "no_matching_company",
                "message": "No matching company found.",
                "companies_scanned": 0,
                "relevant_jobs_count": 0,
                "new_jobs": [],
                "visible_new_jobs": [],
                "previously_seen_count": 0,
                "scan_health": [],
                "summary": build_scan_summary(0, 0, 0, []),
            }
            _set_scan_status("completed", result["message"])
            _session_has_scan = True
            return result

        all_jobs, scan_health = scan_companies(companies_to_scan)
        history_result = update_job_history(all_jobs, history_path)
        new_jobs = history_result["new_jobs"]
        visible_new_jobs = get_visible_new_jobs(new_jobs)
        send_email_digest(visible_new_jobs)

        relevant_job_ids = get_stable_job_ids(all_jobs)

        summary = build_scan_summary(
            companies_scanned=len(companies_to_scan),
            relevant_jobs_count=len(relevant_job_ids),
            new_jobs_count=len(visible_new_jobs),
            scan_health=scan_health,
        )
        result = {
            "status": "completed",
            "message": "Scan completed.",
            "companies_scanned": len(companies_to_scan),
            "relevant_jobs_count": len(relevant_job_ids),
            "new_jobs": new_jobs,
            "visible_new_jobs": sort_jobs_by_relevance(visible_new_jobs),
            "previously_seen_count": history_result["previously_seen_count"],
            "total_seen_count": history_result["total_seen_count"],
            "scan_health": scan_health,
            "summary": summary,
        }
        save_latest_scan(
            {
                "completed_at": _utc_now(),
                "summary": summary,
                "scan_health": scan_health,
                "new_job_ids": [job["job_id"] for job in new_jobs],
                "relevant_job_ids": relevant_job_ids,
            },
            history_path,
        )
        _set_scan_status("completed", "Scan completed.")
        _session_has_scan = True
        return result
    except Exception as exc:
        _set_scan_status("failed", "Scan failed.", str(exc))
        raise
    finally:
        _scan_lock.release()


def get_latest_new_jobs(
    history_path: str | Path = DEFAULT_HISTORY_PATH,
) -> list[dict]:
    latest_scan = get_latest_scan(history_path)
    new_job_ids = latest_scan.get("new_job_ids", [])

    if not isinstance(new_job_ids, list):
        return []

    return sort_jobs_by_relevance(
        get_visible_new_jobs(get_jobs_by_ids(new_job_ids, history_path))
    )


def get_current_session_new_jobs(
    history_path: str | Path = DEFAULT_HISTORY_PATH,
) -> list[dict]:
    if not session_has_scan():
        return []

    return get_latest_new_jobs(history_path)


def get_latest_relevant_jobs(
    history_path: str | Path = DEFAULT_HISTORY_PATH,
) -> list[dict]:
    latest_scan = get_latest_scan(history_path)
    relevant_job_ids = latest_scan.get("relevant_job_ids", [])

    if not isinstance(relevant_job_ids, list):
        return []

    return sort_jobs_by_relevance(
        get_visible_new_jobs(get_jobs_by_ids(relevant_job_ids, history_path))
    )


def get_current_session_relevant_jobs(
    history_path: str | Path = DEFAULT_HISTORY_PATH,
) -> list[dict]:
    if not session_has_scan():
        return []

    return get_latest_relevant_jobs(history_path)


def get_latest_scan_summary(
    history_path: str | Path = DEFAULT_HISTORY_PATH,
) -> dict:
    latest_scan = get_latest_scan(history_path)
    summary = latest_scan.get("summary")

    if isinstance(summary, dict):
        return summary

    return build_scan_summary(0, 0, 0, [])


def get_current_session_scan_summary(
    history_path: str | Path = DEFAULT_HISTORY_PATH,
) -> dict:
    if not session_has_scan():
        return build_scan_summary(0, 0, 0, [])

    return get_latest_scan_summary(history_path)


def get_latest_scan_health(
    history_path: str | Path = DEFAULT_HISTORY_PATH,
) -> list[dict]:
    latest_scan = get_latest_scan(history_path)
    scan_health = latest_scan.get("scan_health")

    if isinstance(scan_health, list):
        return scan_health

    return []


def get_current_session_scan_health(
    history_path: str | Path = DEFAULT_HISTORY_PATH,
) -> list[dict]:
    if not session_has_scan():
        return []

    return get_latest_scan_health(history_path)


def get_triage_jobs(
    state: str,
    history_path: str | Path = DEFAULT_HISTORY_PATH,
) -> list[dict]:
    return get_jobs_by_triage_state(state, history_path)


def mark_job(
    job_identifier: str,
    state: str,
    history_path: str | Path = DEFAULT_HISTORY_PATH,
) -> dict:
    return set_job_triage_state(job_identifier, state, history_path)
