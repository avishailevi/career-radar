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
| Microsoft | Microsoft Israel | Green | Scanner detects jobs; currently no relevant hardware matches. |
| Broadcom | Workday-like | Green | Opens Workday listing and detects jobs; no Israel matches in loaded results. |
| Google | Google Careers | Green | Detects Google job-result links and finds relevant Israel jobs. |
| Amazon | Amazon Jobs | Green | Reads result cards and finds relevant Annapurna Labs hardware jobs in Israel. |
| Qualcomm | Qualcomm Careers | Green | Detects relevant Israel jobs. |
| Marvell | Workday-like | Green | Opens Workday listing and detects jobs; no Israel matches in loaded results. |
| Cadence | Cadence Careers | Red | Possible bot protection / Cloudflare. |
| Synopsys | Synopsys Careers | Green | Uses Israel search results and detects relevant engineering jobs. |
| Mobileye | Mobileye Careers | Green | Detects relevant Israel jobs. |
| Nuvoton | Company site | Green | Detects relevant Herzliya jobs. |
| Tower Semiconductor | Company site | Green | Detects relevant Migdal Haemek engineering jobs. |
| Applied Materials | Applied Materials Jobs | Green | Uses official Israel jobs page and detects relevant Rehovot hardware jobs. |
| KLA | Company site | Red | Error page. |
| Nova | Company site | Red | Needs job parsing. |
| SolarEdge | Comeet | Green | Uses Comeet job board and detects relevant Herzliya hardware and embedded jobs. |
| Rafael | Company site | Red | Did not load links. |
| Israel Aerospace Industries | Company site | Red | Did not load links. |
| Elbit | Company site | Red | Access denied. |

## Priority Order

1. Review remaining yellow statuses.
2. Review red company statuses where access is not blocked by site protections.
3. Handle Israeli defense companies separately if their sites block scraping.
