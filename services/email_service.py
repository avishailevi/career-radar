import os
import smtplib
from collections import defaultdict
from email.message import EmailMessage


ENABLED_VALUES = {"1", "true", "yes", "on"}


def is_email_enabled(env: dict | None = None) -> bool:
    source = env if env is not None else os.environ
    return source.get("CAREER_RADAR_EMAIL_ENABLED", "").strip().lower() in ENABLED_VALUES


def get_email_config(env: dict | None = None) -> dict:
    source = env if env is not None else os.environ
    return {
        "enabled": is_email_enabled(source),
        "smtp_host": source.get("CAREER_RADAR_SMTP_HOST", ""),
        "smtp_port": get_smtp_port(source),
        "smtp_user": source.get("CAREER_RADAR_SMTP_USER", ""),
        "smtp_password": source.get("CAREER_RADAR_SMTP_PASSWORD", ""),
        "email_from": source.get("CAREER_RADAR_EMAIL_FROM", ""),
        "email_to": source.get("CAREER_RADAR_EMAIL_TO", ""),
    }


def get_smtp_port(env: dict) -> int:
    try:
        return int(env.get("CAREER_RADAR_SMTP_PORT", "587") or 587)
    except ValueError:
        return 587


def group_jobs_by_company(jobs: list[dict]) -> dict:
    grouped_jobs = defaultdict(list)

    for job in jobs:
        grouped_jobs[job["company"]].append(job)

    return dict(sorted(grouped_jobs.items()))


def format_email_body(jobs: list[dict]) -> str:
    lines = ["Career Radar found new hardware jobs today.", ""]

    for company, company_jobs in group_jobs_by_company(jobs).items():
        lines.append(company)
        lines.append("-" * len(company))

        for job in company_jobs:
            lines.append(f"Title: {job['title']}")
            lines.append(f"Location: {job.get('matched_location', 'Unknown')}")
            lines.append(f"Matched keyword: {job.get('matched_keyword', 'Unknown')}")
            lines.append(f"URL: {job['url']}")
            lines.append("")

    return "\n".join(lines).strip() + "\n"


def format_email_subject(jobs: list[dict]) -> str:
    return f"Career Radar — {len(jobs)} new jobs"


def has_required_config(config: dict) -> bool:
    required_fields = [
        "smtp_host",
        "smtp_user",
        "smtp_password",
        "email_from",
        "email_to",
    ]
    return all(config.get(field) for field in required_fields)


def send_email_digest(jobs: list[dict], env: dict | None = None) -> bool:
    config = get_email_config(env)

    if not config["enabled"] or not jobs:
        return False

    if not has_required_config(config):
        return False

    message = EmailMessage()
    message["Subject"] = format_email_subject(jobs)
    message["From"] = config["email_from"]
    message["To"] = config["email_to"]
    message.set_content(format_email_body(jobs))

    try:
        with smtplib.SMTP(config["smtp_host"], config["smtp_port"]) as smtp:
            smtp.starttls()
            smtp.login(config["smtp_user"], config["smtp_password"])
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException):
        return False

    return True
