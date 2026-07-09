import hashlib
import json
from datetime import datetime
from datetime import timezone
from pathlib import Path


DEFAULT_HISTORY_PATH = Path("data") / "job_history.json"


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

    with path.open("r", encoding="utf-8") as history_file:
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
    return {
        "job_id": generate_job_id(job["company"], job["title"], job["url"]),
        "company": job["company"],
        "title": job["title"],
        "url": job["url"],
        "matched_keyword": job.get("matched_keyword", ""),
        "matched_location": job.get("matched_location", ""),
        "first_seen": seen_at,
        "last_seen": seen_at,
    }


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
