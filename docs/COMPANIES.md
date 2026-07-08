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
| Broadcom | Workday-like | Yellow | Finds jobs, but not Israel yet. |
| Google | Google Careers | Yellow | Page loads, job links are not detected reliably yet. |
| Amazon | Amazon Jobs | Red | Needs dedicated handling. |
| Qualcomm | Qualcomm Careers | Red | Needs Israel filtering. |
| Marvell | Workday-like | Red | Needs Israel filtering. |
| Cadence | Cadence Careers | Red | Possible bot protection / Cloudflare. |
| Synopsys | Synopsys Careers | Red | Current URL returned 404. |
| Mobileye | Mobileye Careers | Red | Current URL returned 404. |
| Nuvoton | Company site | Red | Needs dedicated parsing. |
| Tower Semiconductor | Company site | Red | Needs career page handling. |
| Applied Materials | Company site | Red | Access denied. |
| KLA | Company site | Red | Error page. |
| Nova | Company site | Red | Needs job parsing. |
| SolarEdge | Company site | Red | Needs job parsing. |
| Rafael | Company site | Red | Did not load links. |
| Israel Aerospace Industries | Company site | Red | Did not load links. |
| Elbit | Company site | Red | Access denied. |

## Priority Order

1. Stabilize Workday-like companies.
2. Stabilize Google.
3. Stabilize Qualcomm and Marvell.
4. Handle Israeli defense companies separately if their sites block scraping.
