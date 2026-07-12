import hashlib
import json
from datetime import datetime
from datetime import timezone
from pathlib import Path


DEFAULT_HISTORY_PATH = Path("data") / "job_history.json"
VALID_TRIAGE_STATES = {"saved", "dismissed", "applied"}


def normalize_identifier_part(value) -> str:
    return " ".join(str(value or "").strip().lower().split())


def generate_job_id(company: str, title: str, url: str) -> str:
    raw_id = "|".join(
        [
            normalize_identifier_part(company),
            normalize_identifier_part(title),
            normalize_identifier_part(url),
        ]
    )
    return hashlib.sha256(raw_id.encode("utf-8")).hexdigest()


def get_seen_at() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_history(history_path: str | Path = DEFAULT_HISTORY_PATH) -> dict:
    path = Path(history_path)

    if not path.exists():
        return {"jobs": []}

    with path.open("r", encoding="utf-8-sig") as history_file:
        data = json.load(history_file)

    if isinstance(data, dict) and isinstance(data.get("jobs"), list):
        return data

    return {"jobs": []}


def save_history(history: dict, history_path: str | Path = DEFAULT_HISTORY_PATH) -> None:
    path = Path(history_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as history_file:
        json.dump(history, history_file, indent=2, ensure_ascii=False)
        history_file.write("\n")


def build_history_record(job: dict, seen_at: str) -> dict:
    record = {
        "job_id": generate_job_id(job["company"], job["title"], job["url"]),
        "company": job["company"],
        "title": job["title"],
        "url": job["url"],
        "matched_keyword": job.get("matched_keyword", ""),
        "matched_location": job.get("matched_location", ""),
        "triage_state": job.get("triage_state", ""),
        "first_seen": seen_at,
        "last_seen": seen_at,
    }
    if "match_confidence" in job:
        record["match_confidence"] = job.get("match_confidence")
    if "relevance_score" in job:
        record["relevance_score"] = job.get("relevance_score")

    return record


def update_job_history(
    jobs: list[dict],
    history_path: str | Path = DEFAULT_HISTORY_PATH,
) -> dict:
    history = load_history(history_path)
    records_by_id = {
        record["job_id"]: record
        for record in history["jobs"]
        if record.get("job_id")
    }
    previously_seen_count = 0
    new_jobs = []
    processed_job_ids = set()
    seen_at = get_seen_at()

    for job in jobs:
        record = build_history_record(job, seen_at)
        job_id = record["job_id"]

        if job_id in processed_job_ids:
            continue

        processed_job_ids.add(job_id)

        if job_id in records_by_id:
            existing_record = records_by_id[job_id]
            existing_record["last_seen"] = seen_at
            existing_record["matched_keyword"] = record["matched_keyword"]
            existing_record["matched_location"] = record["matched_location"]
            if "match_confidence" in record:
                existing_record["match_confidence"] = record["match_confidence"]
            if "relevance_score" in record:
                existing_record["relevance_score"] = record["relevance_score"]
            previously_seen_count += 1
            continue

        records_by_id[job_id] = record
        new_jobs.append(record)

    history["jobs"] = sorted(
        records_by_id.values(),
        key=lambda record: (
            normalize_identifier_part(record.get("company")),
            normalize_identifier_part(record.get("title")),
            normalize_identifier_part(record.get("url")),
        ),
    )
    save_history(history, history_path)

    return {
        "new_jobs": new_jobs,
        "previously_seen_count": previously_seen_count,
        "total_seen_count": len(history["jobs"]),
    }


def get_job_short_id(job: dict) -> str:
    return job.get("job_id", "")[:8]


def is_dismissed_job(job: dict) -> bool:
    return job.get("triage_state") == "dismissed"


def sort_triage_jobs(jobs: list[dict]) -> list[dict]:
    jobs_by_name = sorted(
        jobs,
        key=lambda job: (
            normalize_identifier_part(job.get("company")),
            normalize_identifier_part(job.get("title")),
        ),
    )
    return sorted(
        jobs_by_name,
        key=lambda job: str(job.get("last_seen", "")),
        reverse=True,
    )


def get_jobs_by_triage_state(
    state: str,
    history_path: str | Path = DEFAULT_HISTORY_PATH,
) -> list[dict]:
    triage_state = normalize_triage_state(state)

    if triage_state not in VALID_TRIAGE_STATES:
        return []

    history = load_history(history_path)
    return sort_triage_jobs(
        [
            job
            for job in history.get("jobs", [])
            if normalize_triage_state(job.get("triage_state")) == triage_state
        ]
    )


def get_jobs_by_ids(
    job_ids: list[str],
    history_path: str | Path = DEFAULT_HISTORY_PATH,
) -> list[dict]:
    history = load_history(history_path)
    records_by_id = {
        job.get("job_id"): job
        for job in history.get("jobs", [])
        if job.get("job_id")
    }
    return [
        records_by_id[job_id]
        for job_id in job_ids
        if job_id in records_by_id
    ]


def save_latest_scan(
    latest_scan: dict,
    history_path: str | Path = DEFAULT_HISTORY_PATH,
) -> None:
    history = load_history(history_path)
    history["latest_scan"] = latest_scan
    save_history(history, history_path)


def get_latest_scan(
    history_path: str | Path = DEFAULT_HISTORY_PATH,
) -> dict:
    history = load_history(history_path)
    latest_scan = history.get("latest_scan")

    if isinstance(latest_scan, dict):
        return latest_scan

    return {}


def normalize_triage_state(state: str) -> str:
    return str(state or "").strip().lower()


def find_job_by_identifier(history: dict, job_identifier: str) -> tuple[dict | None, str]:
    clean_identifier = str(job_identifier or "").strip().lower()

    if not clean_identifier:
        return None, "not_found"

    matches = [
        job
        for job in history.get("jobs", [])
        if job.get("job_id", "").lower().startswith(clean_identifier)
    ]

    if not matches:
        return None, "not_found"

    if len(matches) > 1:
        return None, "ambiguous"

    return matches[0], "found"


def set_job_triage_state(
    job_identifier: str,
    state: str,
    history_path: str | Path = DEFAULT_HISTORY_PATH,
) -> dict:
    triage_state = normalize_triage_state(state)

    if triage_state not in VALID_TRIAGE_STATES:
        return {
            "updated": False,
            "error": "invalid_state",
            "message": (
                "Invalid state. Use one of: "
                + ", ".join(sorted(VALID_TRIAGE_STATES))
            ),
        }

    history = load_history(history_path)
    job, status = find_job_by_identifier(history, job_identifier)

    if status == "not_found":
        return {
            "updated": False,
            "error": "not_found",
            "message": f"No job found for ID '{job_identifier}'.",
        }

    if status == "ambiguous":
        return {
            "updated": False,
            "error": "ambiguous",
            "message": f"Job ID '{job_identifier}' matches more than one job.",
        }

    job["triage_state"] = triage_state
    save_history(history, history_path)

    return {
        "updated": True,
        "job": job,
        "message": (
            f"Marked {get_job_short_id(job)} as {triage_state}: "
            f"{job.get('title', '')}"
        ),
    }
