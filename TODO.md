# Career Radar TODO

## Current Priority

- Finish the scanner-factory refactor safely.
- Keep behavior unchanged while moving toward platform-based scanners.

## Next Tasks

- Implement `GenericScanner` as the default scanner wrapper.
- Route non-Workday platforms through `GenericScanner` in `ScannerFactory`.
- Validate syntax and imports after each change.
- Keep `main.py` stable.

## Validation

- Run Python compile checks for all project Python files.
- Run import checks for core modules.
- Use targeted company runs only when the local environment can run Playwright browsers.

## Known Follow-Up Work

- Stabilize Workday-like companies.
- Stabilize Google scanning.
- Review red/yellow company statuses in `docs/COMPANIES.md`.
- Keep documentation aligned with the code after each small refactor.
