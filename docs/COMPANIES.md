# Career Radar Companies

This file tracks company scan status.

## Status Legend

- Green: working and returning expected results.
- Yellow: partially working or needs validation.
- Red: not working yet / blocked / wrong URL.

## Companies

| Company | Platform / Site Type | Status | Notes |
|---|---|---:|---|
| NVIDIA | Workday | Yellow | Structured Israel discovery works; audit returns mixed detail verification because detail reads are sampled. |
| Apple | Apple Careers | Green | Finds Israel jobs. |
| Intel | Workday | Yellow | Structured Israel discovery works; live detail verification may fall back to listing data. |
| Microsoft | Microsoft Israel | Yellow | Scanner detects Israel jobs; current live results have no relevant hardware keyword matches. |
| Broadcom | Workday | Green | Uses Workday Israel location facets and verifies direct detail pages. |
| Google | Google Careers | Green | Detects Google job-result links and finds relevant Israel jobs. |
| Amazon | Amazon Jobs | Green | Reads result cards and finds relevant Annapurna Labs hardware jobs in Israel. |
| Qualcomm | Eightfold | Green | Uses Eightfold search API and detects relevant Israel hardware / firmware / DSP jobs. |
| Marvell | Workday | Yellow | Uses Workday country facets and finds Israel hardware roles; audit returns mixed detail verification. |
| Cadence | Dejobs | Green | Uses Dejobs Israel listing and detects relevant physical design / verification jobs. |
| Synopsys | Synopsys Careers | Green | Uses Israel search results and detects relevant engineering jobs. |
| Mobileye | Mobileye Careers | Green | Detects relevant Israel jobs. |
| Nuvoton | Company site | Green | Detects relevant Herzliya jobs. |
| Tower Semiconductor | Company site | Green | Detects relevant Migdal Haemek engineering jobs. |
| Applied Materials | Applied Materials Jobs | Green | Uses official Israel jobs page and detects relevant Rehovot hardware jobs. |
| KLA | Workday | Yellow | Uses Workday structured Israel discovery; audit returns mixed detail verification because detail reads are sampled. |
| Nova | Comeet | Green | Uses Comeet embedded position data and detects relevant Rehovot hardware / system jobs. |
| SolarEdge | Comeet | Green | Uses Comeet job board and detects relevant Herzliya hardware and embedded jobs. |
| Rafael | Getro / LHH | Green | Uses Getro API behind LHH board and detects relevant RF, embedded, system, optical, and verification jobs. |
| Israel Aerospace Industries | Static Hebrew JSON | Green | Uses official Hebrew jobs JSON feed and detects relevant hardware / engineering jobs. |
| Elbit | Static Hebrew JSON | Green | Uses public Hebrew jobs JSON feed and detects relevant hardware / engineering jobs. |

## Priority Order

1. Monitor Intel Workday detail verification and improve only if fallback quality becomes a product issue.
2. Validate Microsoft periodically; current scan works but live results have no relevant hardware keyword matches.
3. Reduce false positives in broad platform scanners while preserving hardware coverage.
4. Keep expanding Israeli hardware company coverage from platform-level feeds/APIs first.
