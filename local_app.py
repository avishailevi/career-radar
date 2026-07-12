import os
import threading
import webbrowser
from pathlib import Path

from flask import Flask
from flask import redirect
from flask import render_template
from flask import request
from flask import url_for

from services.application_service import get_current_session_new_jobs
from services.application_service import get_current_session_relevant_jobs
from services.application_service import get_current_session_scan_health
from services.application_service import get_current_session_scan_summary
from services.application_service import get_scan_status
from services.application_service import get_triage_jobs
from services.application_service import mark_job
from services.application_service import run_scan
from services.application_service import session_has_scan


app = Flask(__name__)
HISTORY_PATH = Path(
    os.environ.get("CAREER_RADAR_HISTORY_PATH", "data/job_history.json")
)


def _run_scan_in_background() -> None:
    try:
        run_scan(history_path=HISTORY_PATH)
    except Exception:
        pass


@app.get("/")
def new_jobs():
    return render_template(
        "jobs.html",
        active_tab="new",
        title="New Jobs",
        empty_message=get_scan_empty_message(),
        jobs=get_current_session_new_jobs(HISTORY_PATH),
        scan_status=get_scan_status(),
        scan_summary=get_current_session_scan_summary(HISTORY_PATH),
        show_actions=True,
    )


@app.get("/relevant")
def relevant_jobs():
    return render_template(
        "jobs.html",
        active_tab="relevant",
        title="Relevant Jobs",
        empty_message=get_relevant_empty_message(),
        jobs=get_current_session_relevant_jobs(HISTORY_PATH),
        scan_status=get_scan_status(),
        scan_summary=get_current_session_scan_summary(HISTORY_PATH),
        show_actions=True,
    )


@app.post("/scan")
def scan_now():
    scan_status = get_scan_status()

    if scan_status["state"] != "running":
        thread = threading.Thread(target=_run_scan_in_background, daemon=True)
        thread.start()

    return redirect(url_for("new_jobs"))


@app.post("/jobs/<job_id>/mark")
def mark_job_route(job_id):
    state = request.form.get("state", "")
    next_path = request.form.get("next", "/")
    mark_job(job_id, state, HISTORY_PATH)
    return redirect(next_path or url_for("new_jobs"))


@app.get("/saved")
def saved_jobs():
    return render_template(
        "jobs.html",
        active_tab="saved",
        title="Saved",
        empty_message="No saved jobs.",
        jobs=get_triage_jobs("saved", HISTORY_PATH),
        scan_status=get_scan_status(),
        scan_summary=get_current_session_scan_summary(HISTORY_PATH),
        show_actions=True,
    )


@app.get("/applied")
def applied_jobs():
    return render_template(
        "jobs.html",
        active_tab="applied",
        title="Applied",
        empty_message="No applied jobs.",
        jobs=get_triage_jobs("applied", HISTORY_PATH),
        scan_status=get_scan_status(),
        scan_summary=get_current_session_scan_summary(HISTORY_PATH),
        show_actions=False,
    )


@app.get("/dismissed")
def dismissed_jobs():
    return render_template(
        "jobs.html",
        active_tab="dismissed",
        title="Dismissed",
        empty_message="No dismissed jobs.",
        jobs=get_triage_jobs("dismissed", HISTORY_PATH),
        scan_status=get_scan_status(),
        scan_summary=get_current_session_scan_summary(HISTORY_PATH),
        show_actions=True,
    )


@app.get("/scan-health")
def scan_health():
    return render_template(
        "scan_health.html",
        active_tab="scan_health",
        scan_status=get_scan_status(),
        scan_summary=get_current_session_scan_summary(HISTORY_PATH),
        scan_health=get_current_session_scan_health(HISTORY_PATH),
        has_session_scan=session_has_scan(),
    )


def get_scan_empty_message() -> str:
    if not session_has_scan():
        return "No scan has been run during this session."

    return "No new jobs from the latest scan."


def get_relevant_empty_message() -> str:
    if not session_has_scan():
        return "No scan has been run during this session."

    return (
        "No relevant-job list is stored for the latest scan. "
        "Run Scan Now to refresh it."
    )


def open_browser(port: int) -> None:
    webbrowser.open(f"http://127.0.0.1:{port}/")


if __name__ == "__main__":
    port = 8765
    if not os.environ.get("CAREER_RADAR_NO_BROWSER"):
        threading.Timer(1.0, open_browser, args=[port]).start()
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)
