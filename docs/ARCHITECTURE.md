# Career Radar Architecture

## Purpose

Career Radar scans company career pages and returns only jobs that are relevant for Avishai's target roles.

## Current Architecture

```text
main.py
  -> companies.py
  -> scanner.py
  -> keywords.py
```

### main.py

Entry point.

Responsibilities:
- Parse optional company argument.
- Select companies to scan.
- Call the scanner.
- Print relevant jobs.

### companies.py

Contains the company list and career URLs.

### scanner.py

Current general-purpose scanner.

Responsibilities:
- Open career pages with Playwright.
- Collect links.
- Filter bad links and bad titles.
- Detect job-like URLs.
- Match location.
- Match keywords.
- Return relevant jobs.

### keywords.py

Contains target keywords and target locations.

### models/

Early structure for data models.

### scanners/

Early structure for future scanner implementations.

### services/

Early structure for filtering and business logic.

## Target Architecture

The project should gradually move from one generic scanner to platform-based scanners.

```text
main.py
companies.py
keywords.py

models/
  job.py

services/
  filter_service.py

scanners/
  base_scanner.py
  generic_scanner.py
  workday_scanner.py
  apple_scanner.py
  microsoft_scanner.py
  google_scanner.py
```

## Platform-Based Scanner Direction

Many companies use the same job platforms. We should reuse scanner logic by platform rather than by company.

Examples:
- Intel, NVIDIA, Broadcom, Marvell, KLA: Workday structured discovery plus shared detail verification.
- Apple: Apple careers.
- Microsoft: Microsoft Israel careers.
- Google: Google Careers.
- Other sites: Generic scanner.

## Development Rule

`main` should remain stable.
Large changes should be developed in feature branches and merged only after local testing.
