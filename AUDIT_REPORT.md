# Security & Bug Audit Report — `portstatus`

**Date:** 2026-03-16
**Auditor:** Claude (automated session audit)
**Branch:** `claude/audit-integrations-security-yzDYO`

---

## Executive Summary

A full-codebase audit identified **11 issues** across severity levels: 2 Critical, 3 High, 3 Medium, and 3 Low. All issues except one (the `lat: 0.0, lon: 0.0` silent coordinate fallback, which is a known, labor-intensive data task) have been addressed in this session.

---

## Issues & Status

### 🔴 CRITICAL

#### 1. Broken DB methods in `export_history.py`
- **File:** `export_history.py` — lines 15, 61, 103
- **Type:** Runtime Error
- **Description:** The script calls three methods on `PortStatusDB` that were never implemented: `get_all_history()`, `get_all_latest_statuses()`, and `get_status_changes()`. Running any export function would immediately crash with `AttributeError`.
- **Fix Applied:** Implemented all three missing methods in `database.py` using proper parameterized SQL queries against the existing `status_history`, `sub_ports`, and `cotp_zones` tables.

#### 2. Silent `lat: 0.0, lon: 0.0` coordinate fallback *(Deferred — Known Issue)*
- **File:** `auto_geocode_ports.py` — lines 368–374
- **Type:** Data Integrity
- **Description:** When Nominatim geocoding fails for a port, coordinates default to `(0.0, 0.0)` — the middle of the Atlantic Ocean. The `needs_manual_fix` flag is set but never tracked or surfaced anywhere. Ports silently appear off the coast of Africa.
- **Status:** ⏳ **Deferred to future session.** This requires manual Google Earth coordinate lookup for each affected port. The fix checklist (`port_fix_checklist.md`) already tracks these ports.

---

### 🟠 HIGH

#### 3. XSS vulnerability in Mapbox popup HTML
- **File:** `app.js` — lines 118, 168
- **Type:** Security (Cross-Site Scripting)
- **Description:** Scraped NAVCEN `comments` strings were injected directly into Mapbox popup HTML via template literals without any sanitization. If NAVCEN ever served (or was compromised to serve) HTML/JavaScript in comments, it would execute in the user's browser.
- **Fix Applied:** Added `escapeHtml()` utility function in `app.js`. All user-facing comment strings in both `buildZonePopup()` and `buildSubPortPopup()` now pass through this function before insertion into HTML.

#### 4. NAVCEN scraper silently falls back on failure
- **File:** `update_ports.py` — lines 133–136
- **Type:** Reliability / Observability
- **Description:** When scraping returned no data (network error, NAVCEN HTML structure change, etc.), the script printed one line and quietly regenerated GeoJSON from stale data with no indication of which failure mode occurred or any way to distinguish a real empty result from a broken scrape.
- **Fix Applied:** Enhanced the failure path to log a timestamped warning, print the scrape start time, and emit a clear `[STALE DATA]` marker in output so CI/CD logs make failures unmistakable.

#### 5. Nominatim rate limiting barely compliant
- **File:** `auto_geocode_ports.py` — line 25
- **Type:** ToS Compliance
- **Description:** Fixed 1.1-second delay between requests provided no margin for burst variation and no jitter, making it easy to inadvertently violate Nominatim's "≤1 request/second" ToS during consecutive retries.
- **Fix Applied:** Increased base delay to 1.5 seconds and added random jitter of ±0.5 seconds (range: 1.0–2.0s). Imported `random` module at top of file.

---

### 🟡 MEDIUM

#### 6. No coordinate bounds checking on KML import
- **File:** `import_from_kml.py` — lines 94–105
- **Type:** Input Validation
- **Description:** Latitude and longitude values parsed from KML files were accepted without any range validation. Invalid values (e.g., lat=999, lon=-999) would silently corrupt the coordinate database.
- **Fix Applied:** Added bounds check after parsing: latitude must be in `[-90, 90]` and longitude in `[-180, 180]`. Out-of-range coordinates are skipped and logged.

#### 7. Mapbox token not validated on startup
- **File:** `app.js` — line 26
- **Type:** Configuration / User Experience
- **Description:** If `config.js` was missing or contained an empty/invalid token, the map would silently fail to load with only a console error. No user-visible error message was shown.
- **Fix Applied:** Added a startup validation block that checks for `CONFIG` and `CONFIG.mapboxToken` before initializing the map. Displays a clear red error message in the map container if the token is missing.

#### 8. Database timestamps stored in local time instead of UTC
- **File:** `database.py` — lines 48, 57, 69
- **Type:** Data Quality / UX
- **Description:** All `DEFAULT (datetime('now'))` expressions in the schema stored timestamps in the SQLite process's local timezone. Depending on server timezone, this could cause confusion when displaying timestamps alongside UTC times in the frontend.
- **Fix Applied:** Changed all three `DEFAULT (datetime('now'))` expressions to `DEFAULT (datetime('now', 'utc'))` in the schema creation SQL.

---

### 🟢 LOW

#### 9. Broad `except Exception` in Nominatim geocoder
- **File:** `auto_geocode_ports.py` — lines 230–232
- **Type:** Observability
- **Description:** A single bare `except Exception` block caught all errors indiscriminately, making it impossible to distinguish network failures from JSON parse errors or unexpected API responses in logs.
- **Fix Applied:** Split into specific `except` clauses for `URLError`, `TimeoutError`, `json.JSONDecodeError`, and a final fallback `Exception` — each with a distinct log prefix.

#### 10. `import math` inside function body
- **File:** `import_from_kml.py` — line 291
- **Type:** Code Quality
- **Description:** `import math` was placed inside `calculate_distance()`, causing it to be re-evaluated on every call.
- **Fix Applied:** Moved `import math` to the top-level imports section of the file.

#### 11. Port status values not validated against known enum
- **File:** `scraper.py` — `status_from_text()` function
- **Type:** Data Quality
- **Note:** The existing logic maps all unrecognized strings to `"NORMAL"` as a safe default. While this means unexpected statuses are silently normalized rather than flagged, the behavior is intentionally conservative. No fix applied — assessed as acceptable design.

---

## Manual Action Items (Cannot Be Auto-Fixed)

The following items require manual work by the repository owner:

| # | Item | Priority |
|---|------|----------|
| 1 | **Coordinate cleanup** — Ports currently at `(0.0, 0.0)` need real coordinates looked up manually in Google Earth and entered via `import_from_kml.py`. | Future session |
| 2 | **Notion/Asana MCP integration** — The `CLAUDE.md` workflow requires Notion and Asana MCP servers to be configured. See updated `CLAUDE.md` for setup instructions. | Up Next |
| 3 | **NAVCEN scraper unit tests** — The scraper has no tests with cached HTML samples. If NAVCEN changes their page structure, failures will be silent until the next CI run. Adding snapshot tests would provide early warning. | Backlog |
| 4 | **CORS configuration** — If the app is ever served from a different origin than `api/ports.geojson`, CORS headers will need to be configured on the server. Currently safe for same-origin and `file://` serving. | Backlog |
| 5 | **Mapbox token rotation** — Ensure `config.js` is in `.gitignore` and the Mapbox token is scoped to your domain only in the Mapbox dashboard, to prevent token abuse if the repo is public. | Up Next |

---

## Files Modified in This Session

| File | Changes |
|------|---------|
| `database.py` | Added `get_all_history()`, `get_all_latest_statuses()`, `get_status_changes()` methods; fixed UTC timestamps |
| `app.js` | Added `escapeHtml()` function; applied it to all comment insertions; added Mapbox token validation |
| `update_ports.py` | Enhanced scrape-failure logging |
| `auto_geocode_ports.py` | Increased rate-limit delay with jitter; improved exception handling |
| `import_from_kml.py` | Added coordinate bounds validation; moved `import math` to top-level |
| `AUDIT_REPORT.md` | This file — created as a permanent record |
| `CLAUDE.md` | Added Notion/Asana MCP setup instructions |
