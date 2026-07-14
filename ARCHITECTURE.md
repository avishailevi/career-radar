# Career Radar Architecture

## Purpose

Career Radar scans company career pages and returns only jobs that match target hardware and semiconductor roles in Israel.

## Current Runtime Flow

```text
main.py
  -> companies.py
  -> scanners/scanner_factory.py
      -> scanners/workday_scanner.py
          -> scanner.py
      -> scanners/generic_scanner.py
          -> scanner.py
  -> services/filter_service.py
  -> services/platform_service.py
  -> keywords.py
```

## Main Modules

### `main.py`

Command-line entry point.

Responsibilities:
- Select all companies or one requested company.
- Call `ScannerFactory.scan`.
- Print matching jobs.

### `companies.py`

Contains company names, platform metadata, and career URLs.

### `scanner.py`

Current shared scanning implementation.

Responsibilities:
- Open career pages with Playwright.
- Follow job-list links when needed.
- Collect links.
- Read detail pages for selected platforms.
- Build debug output.
- Return relevant job dictionaries.

### `services/filter_service.py`

Shared filtering and matching logic.

Responsibilities:
- Filter bad titles.
- Filter bad URLs.
- Detect job-like URLs.
- Detect job-list URLs that should be followed from career landing pages.
- Match target locations.
- Match target keywords.
- Build duplicate-detection keys.

### `services/platform_service.py`

Shared platform behavior rules.

Responsibilities:
- Decide which platforms should read job detail pages.
- Decide which platforms should follow a job-list link from a career landing page.

### `scanners/scanner_factory.py`

Routes companies by platform.

Current behavior:
- `workday` companies use `WorkdayScanner`.
- Other companies use `GenericScanner`.
- Workday listing URLs can be followed without being treated as job detail URLs.

### `scanners/workday_scanner.py`

Workday platform scanner.

Current behavior:
- Uses Workday CXS search JSON for candidate discovery.
- Applies Israel location facets when Workday exposes them.
- Builds canonical Workday detail URLs with the board/site segment.
- Reuses the shared browser detail verifier from `scanner.py`, capped to a small Workday sample by default.
- Uses `identity_url` with `workday://<tenant>/<requisition>` when CXS exposes a valid requisition ID.
- Preserves existing job output fields and verification states.

### `scanners/generic_scanner.py`

Default scanner wrapper.

Current behavior:
- Delegates to `scanner.scan_company`.

## Development Direction

Move gradually from one shared scanner toward platform-based scanners, without breaking the stable v0.1 command-line scanner.

Next architecture step:
- Keep extracting platform-specific behavior only when a company/platform needs it.
