# Career Radar TODO

## Current Priority

- Company status cleanup: remaining unresolved items are platform-level blockers, not one-off company URL fixes.

## Next Tasks

- Validate syntax and imports after each change.
- Keep `main.py` stable.
- Add Eightfold platform support for location metadata, starting with Qualcomm.
- Add Hebrew/interactive board support for Israeli defense company sites.
- Revisit blocked or dynamically rendered boards only when a stable source/API is identified.

## Validation

- Run Python compile checks for all project Python files.
- Run import checks for core modules.
- Use targeted company runs only when the local environment can run Playwright browsers.

## Known Follow-Up Work

- Keep documentation aligned with the code after each small refactor.
- Track remaining red/yellow companies in `docs/COMPANIES.md` as platform blockers until their shared platform support exists.
