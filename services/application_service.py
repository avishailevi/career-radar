import io
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import as_completed
from contextlib import redirect_stdout
from dataclasses import dataclass
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
SCAN_WORKERS_ENV = "CAREER_RADAR_SCAN_WORKERS"
DEFAULT_SCAN_WORKERS = 4
MAX_SCAN_WORKERS = 8

_scan_lock = threading.Lock()
_scan_status_lock = threading.Lock()
_scan_started_monotonic = 0.0
_scan_status = {
    "state": "idle",
    "message": "Ready to scan.",
    "started_at": "",
    "completed_at": "",
    "error": "",
    "total_companies": 0,
    "completed_companies": 0,
    "running_companies": [],
    "elapsed_seconds": 0.0,
}
_session_has_scan = False


@dataclass
class CompanyScanResult:
    index: int
    company_name: str
    jobs: list[dict]
    health: dict
    output: str = ""


class ThreadLocalStdout:
    def __init__(self, fallback):
        self.fallback = fallback
        self.local = threading.local()

    def set_buffer(self, buffer) -> None:
        self.local.buffer = buffer

    def clear_buffer(self) -> None:
        if hasattr(self.local, "buffer"):
            del self.local.buffer

    def write(self, text: str) -> int:
        buffer = getattr(self.local, "buffer", None)
        if buffer is not None:
            return buffer.write(text)

        return self.fallback.write(text)

    def flush(self) -> None:
        buffer = getattr(self.local, "buffer", None)
        if buffer is not None:
            return None

        return self.fallback.flush()

    def __getattr__(self, name):
        return getattr(self.fallback, name)


def get_scan_worker_count(environ: dict | None = None) -> int:
    value = (environ or os.environ).get(SCAN_WORKERS_ENV, "")

    try:
        worker_count = int(str(value).strip())
    except ValueError:
        return DEFAULT_SCAN_WORKERS

    if worker_count <= 0:
        return DEFAULT_SCAN_WORKERS

    return min(worker_count, MAX_SCAN_WORKERS)


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
    if isinstance(sys.stdout, ThreadLocalStdout):
        return ScannerFactory.scan(company, debug=DEBUG)

    if DEBUG:
        return ScannerFactory.scan(company, debug=True)

    with redirect_stdout(io.StringIO()):
        return ScannerFactory.scan(company, debug=False)


def build_scan_health(
    company_name: str,
    jobs: list[dict],
    duration_seconds: float,
    error: str = "",
) -> dict:
    status = "failed"

    if not error:
        status = "success_with_jobs" if jobs else "success_zero_jobs"

    health = {
        "company": company_name,
        "status": status,
        "duration_seconds": duration_seconds,
        "jobs_found": len(jobs),
    }
    if error:
        health["error"] = error

    return health


def get_error_message(error: Exception) -> str:
    for line in str(error).splitlines():
        clean_line = line.strip()
        if clean_line:
            return clean_line

    return error.__class__.__name__


def scan_company_result(
    index: int,
    company: dict,
    stdout_proxy: ThreadLocalStdout | None = None,
) -> CompanyScanResult:
    company_name = company["name"]
    output = io.StringIO()
    start = time.monotonic()
    _mark_company_started(index)

    if stdout_proxy:
        stdout_proxy.set_buffer(output)

    try:
        if stdout_proxy:
            jobs = scan_company(company)
        else:
            with redirect_stdout(output):
                jobs = scan_company(company)
        return CompanyScanResult(
            index=index,
            company_name=company_name,
            jobs=jobs,
            health=build_scan_health(
                company_name,
                jobs,
                time.monotonic() - start,
            ),
            output=output.getvalue(),
        )
    except Exception as error:
        return CompanyScanResult(
            index=index,
            company_name=company_name,
            jobs=[],
            health=build_scan_health(
                company_name,
                [],
                time.monotonic() - start,
                get_error_message(error),
            ),
            output=output.getvalue(),
        )
    finally:
        if stdout_proxy:
            stdout_proxy.clear_buffer()
        _mark_company_completed(index)


def build_failed_company_result(
    index: int,
    company: dict,
    error: Exception,
) -> CompanyScanResult:
    company_name = company["name"]
    return CompanyScanResult(
        index=index,
        company_name=company_name,
        jobs=[],
        health=build_scan_health(company_name, [], 0.0, get_error_message(error)),
    )


def scan_companies(
    companies_to_scan: list[dict],
    worker_count: int | None = None,
) -> tuple[list[dict], list[dict]]:
    worker_count = worker_count or get_scan_worker_count()
    worker_count = max(1, min(worker_count, len(companies_to_scan) or 1))
    results_by_index = {}

    if not companies_to_scan:
        return [], []

    _initialize_scan_progress(companies_to_scan)

    if worker_count == 1:
        for index, company in enumerate(companies_to_scan):
            result = scan_company_result(index, company)
            results_by_index[index] = result
    else:
        original_stdout = sys.stdout
        stdout_proxy = ThreadLocalStdout(original_stdout)
        sys.stdout = stdout_proxy
        try:
            with ThreadPoolExecutor(max_workers=worker_count) as executor:
                futures_by_index = {}
                for index, company in enumerate(companies_to_scan):
                    future = executor.submit(
                        scan_company_result,
                        index,
                        company,
                        stdout_proxy,
                    )
                    futures_by_index[future] = index

                for future in as_completed(futures_by_index):
                    index = futures_by_index[future]
                    company = companies_to_scan[index]
                    try:
                        result = future.result()
                    except Exception as error:
                        result = build_failed_company_result(index, company, error)
                        _mark_company_completed(index)

                    results_by_index[index] = result
        finally:
            sys.stdout = original_stdout

    ordered_results = [
        results_by_index[index]
        for index in range(len(companies_to_scan))
    ]

    if DEBUG:
        for result in ordered_results:
            if result.output:
                print(result.output, end="")

    all_jobs = [
        job
        for result in ordered_results
        for job in result.jobs
    ]
    scan_health = [result.health for result in ordered_results]
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
    global _scan_started_monotonic

    with _scan_status_lock:
        _scan_status["state"] = state
        _scan_status["message"] = message
        _scan_status["error"] = error

        if state == "running":
            _scan_started_monotonic = time.monotonic()
            _scan_status["started_at"] = _utc_now()
            _scan_status["completed_at"] = ""
            _scan_status["completed_companies"] = 0
            _scan_status["running_companies"] = []
            _scan_status["elapsed_seconds"] = 0.0

        if state in {"completed", "failed"}:
            _scan_status["completed_at"] = _utc_now()
            _scan_status["running_companies"] = []
            _scan_status["elapsed_seconds"] = get_elapsed_scan_seconds()


def get_elapsed_scan_seconds() -> float:
    if not _scan_started_monotonic:
        return 0.0

    return time.monotonic() - _scan_started_monotonic


def _initialize_scan_progress(companies_to_scan: list[dict]) -> None:
    with _scan_status_lock:
        _scan_status["total_companies"] = len(companies_to_scan)
        _scan_status["completed_companies"] = 0
        _scan_status["running_companies"] = []
        _scan_status["elapsed_seconds"] = get_elapsed_scan_seconds()
        _scan_status["_company_order"] = {
            index: company["name"]
            for index, company in enumerate(companies_to_scan)
        }
        _scan_status["_running_indices"] = set()


def _update_running_companies_locked() -> None:
    company_order = _scan_status.get("_company_order", {})
    running_indices = sorted(_scan_status.get("_running_indices", set()))
    _scan_status["running_companies"] = [
        company_order[index]
        for index in running_indices
        if index in company_order
    ]
    _scan_status["elapsed_seconds"] = get_elapsed_scan_seconds()


def _mark_company_started(index: int) -> None:
    with _scan_status_lock:
        _scan_status.setdefault("_running_indices", set()).add(index)
        _update_running_companies_locked()


def _mark_company_completed(index: int) -> None:
    with _scan_status_lock:
        _scan_status.setdefault("_running_indices", set()).discard(index)
        _scan_status["completed_companies"] = _scan_status.get(
            "completed_companies",
            0,
        ) + 1
        _update_running_companies_locked()


def get_scan_status() -> dict:
    with _scan_status_lock:
        status = {
            key: value
            for key, value in _scan_status.items()
            if not key.startswith("_")
        }
        status["running_companies"] = list(status.get("running_companies", []))
        if status.get("state") == "running":
            status["elapsed_seconds"] = get_elapsed_scan_seconds()
        return status


def session_has_scan() -> bool:
    return _session_has_scan


def reset_session_scan_state() -> None:
    global _scan_started_monotonic
    global _session_has_scan
    _session_has_scan = False
    _scan_started_monotonic = 0.0
    with _scan_status_lock:
        _scan_status.clear()
        _scan_status.update(
            {
                "state": "idle",
                "message": "Ready to scan.",
                "started_at": "",
                "completed_at": "",
                "error": "",
                "total_companies": 0,
                "completed_companies": 0,
                "running_companies": [],
                "elapsed_seconds": 0.0,
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
