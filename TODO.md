# Career Radar TODO

## Current Priority

- Product coverage expansion: the priority companies are now supported through shared platform scanners.
- Current audit target: keep supported-company coverage reliable through platform-level scanners.

## Next Tasks

- Validate syntax and imports after each change.
- Keep `main.py` stable.
- Re-check Microsoft hardware relevance when its live Israel postings change.
- Monitor Intel Workday detail verification; structured Israel listings work, but detail pages may still be generic to the current verifier.
- Tune broad keyword matching to reduce false positives without reducing hardware coverage.
- Continue company expansion using platform-level feeds/APIs before company-specific handling.

## Validation

- Run Python compile checks for all project Python files.
- Run import checks for core modules.
- Use targeted company runs only when the local environment can run Playwright browsers.

## Known Follow-Up Work

- Keep documentation aligned with the code after each small refactor.
- Track remaining yellow companies in `docs/COMPANIES.md` as platform or live-data limitations until shared fixes exist.
- Latest historical audit summary: `reports/company_audit_20260709_122000.md` reported 18 supported companies, with Broadcom/Marvell blocked on Workday location discovery and Microsoft returning no current hardware keyword matches.
