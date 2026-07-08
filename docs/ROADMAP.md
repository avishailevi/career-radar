# Career Radar Roadmap

Career Radar is a Python project for finding relevant hardware and semiconductor jobs from company career sites.

## Current Goal

Build a stable job scanning engine that finds relevant jobs in Israel for hardware, semiconductor, board design, RTL, FPGA, verification, physical design, embedded, and system integration roles.

## v0.1 - Stable Scanner

Status: In progress

Goals:
- Scan relevant companies.
- Find real job links.
- Filter by location.
- Filter by keywords.
- Print relevant results in the console.

Done:
- Git and GitHub setup.
- Initial company list.
- Basic Playwright scanner.
- Working scans for Intel, NVIDIA, Apple, and Microsoft.

Next:
- Stabilize Google.
- Stabilize Workday-based companies.
- Improve company-specific/platform-specific scanners.

## v0.2 - Engine Improvements

Goals:
- Refactor scanners by platform.
- Add better debug output.
- Add cleaner project structure.
- Improve performance with parallel scanning.

## v0.3 - Persistence

Goals:
- Add SQLite storage.
- Track first seen and last seen jobs.
- Show only new jobs.
- Avoid duplicate results.

## v0.4 - User Workflow

Goals:
- Export results to CSV.
- Add better CLI options.
- Add daily scan mode.

## Future

Possible future features:
- Telegram/email notifications.
- Resume/job match scoring.
- Auto-apply assistance.
- Dashboard.
