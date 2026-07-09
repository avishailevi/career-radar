# Career Radar Companies

This file tracks company scan status.

## Status Legend

- Green: working and returning expected results.
- Yellow: partially working or needs validation.
- Red: not working yet / blocked / wrong URL.

## Companies

| Company | Platform / Site Type | Status | Notes |
|---|---|---:|---|
| NVIDIA | Workday | Green | Finds Israel jobs. |
| Apple | Apple Careers | Green | Finds Israel jobs. |
| Intel | Workday | Green | Israel location URL works. |
| Microsoft | Microsoft Israel | Green | Scanner detects Israel jobs; current live results have no relevant hardware matches. |
| Broadcom | Workday-like | Yellow | Opens global Workday listing and detects jobs; no Israel matches in loaded results. |
| Google | Google Careers | Green | Detects Google job-result links and finds relevant Israel jobs. |
| Amazon | Amazon Jobs | Green | Reads result cards and finds relevant Annapurna Labs hardware jobs in Israel. |
| Qualcomm | Eightfold | Yellow | Official board exposes job links but not location metadata to the generic scanner; needs Eightfold platform support or a stable API. |
| Marvell | Workday-like | Yellow | Opens global Workday listing and detects jobs; no Israel matches in loaded results. |
| Cadence | Dejobs | Green | Uses Dejobs Israel listing and detects relevant physical design / verification jobs. |
| Synopsys | Synopsys Careers | Green | Uses Israel search results and detects relevant engineering jobs. |
| Mobileye | Mobileye Careers | Green | Detects relevant Israel jobs. |
| Nuvoton | Company site | Green | Detects relevant Herzliya jobs. |
| Tower Semiconductor | Company site | Green | Detects relevant Migdal Haemek engineering jobs. |
| Applied Materials | Applied Materials Jobs | Green | Uses official Israel jobs page and detects relevant Rehovot hardware jobs. |
| KLA | Workday | Green | Uses direct KLA Israel Workday board and detects relevant board design jobs. |
| Nova | Company site | Red | Official Israel pages appear blocked or dynamically rendered; job rows are not exposed to Playwright. |
| SolarEdge | Comeet | Green | Uses Comeet job board and detects relevant Herzliya hardware and embedded jobs. |
| Rafael | Company site / LHH | Red | Official page exposes no job links; LHH board triggers a download flow and needs special handling. |
| Israel Aerospace Industries | Hebrew company site | Red | Official Hebrew jobs board loads, but matching needs Hebrew location parsing. |
| Elbit | Hebrew company site | Red | Interactive Hebrew search page does not expose job links to the generic scanner. |

## Priority Order

1. Add platform support for Eightfold boards, starting with Qualcomm location metadata.
2. Add platform support for Hebrew/interactive boards where links are not exposed to the generic scanner.
3. Add Hebrew location parsing before re-enabling IAI matching.
4. Revisit blocked/dynamic boards such as Nova and Rafael when a stable source or API is identified.
