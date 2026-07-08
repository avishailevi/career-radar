# Career Radar Roadmap

Career Radar is a Python project for scanning company career pages and printing jobs that match hardware and semiconductor roles in Israel.

## Current Goal

Build a stable v0.1 scanner that finds relevant jobs only.

Current scope:
- Python command-line output.
- Playwright-based career page scanning.
- Company list in `companies.py`.
- Keyword and location matching in `keywords.py`.
- Shared filtering logic in `services/filter_service.py`.
- Early scanner routing through `scanners/scanner_factory.py`.

Out of scope for v0.1:
- AI.
- Dashboard.
- Telegram or email notifications.
- Automatic applications.

## v0.1 - Stable Scanner

Status: In progress.

Already present:
- Company list with platform metadata.
- Generic scanner logic in `scanner.py`.
- Scanner factory entry point.
- Workday wrapper that currently delegates to the shared scanner implementation.
- Generic scanner wrapper that delegates to the shared scanner implementation.
- Filtering service extracted from `scanner.py`.
- Platform behavior rules extracted from `scanner.py`.
- Documentation under `docs/`.

Known working companies from `docs/COMPANIES.md`:
- NVIDIA.
- Apple.
- Intel.
- Microsoft.

Highest-priority next work:
- Keep Workday behavior stable while preparing for platform-specific scanner logic.
- Stabilize Workday-like companies.
- Then stabilize Google.

## Later

After v0.1 is stable:
- SQLite persistence.
- Tracking first seen and last seen jobs.
- Showing only new jobs.
- CSV export.
- Better CLI options.
