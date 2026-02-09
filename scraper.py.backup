"""
Scraper for USCG NAVCEN Port Status data
Fetches COTP zones AND their sub-port details from https://www.navcen.uscg.gov/port-status

Hierarchy:
  COTP Zone (e.g. "CHARLESTON") -> contains sub-ports (e.g. "Beaufort", "Georgetown", etc.)
  The zone's displayed color = the worst status among all its sub-ports.
"""

import requests
from bs4 import BeautifulSoup
from typing import Dict, List, Optional
import re
import time


# ---------------------------------------------------------------------------
# COTP Zone coordinates (where the big dot sits on the map at low zoom)
# ---------------------------------------------------------------------------
COTP_COORDINATES = {
    "CHARLESTON": {"lat": 32.7765, "lon": -79.9253},
    "MIAMI": {"lat": 25.7617, "lon": -80.1918},
    "HOUSTON-GALVESTON": {"lat": 29.7604, "lon": -95.2631},
    "LOS ANGELES-LONG BEACH": {"lat": 33.7405, "lon": -118.2437},
    "SEATTLE (PUGET SOUND)": {"lat": 47.6062, "lon": -122.3321},
    "NEW YORK": {"lat": 40.6892, "lon": -74.0445},
    "NEW ORLEANS": {"lat": 29.9511, "lon": -90.0715},
    "BOSTON": {"lat": 42.3601, "lon": -71.0589},
    "SAVANNAH": {"lat": 32.1368, "lon": -81.0901},
    "SAN FRANCISCO": {"lat": 37.7749, "lon": -122.4194},
    "SAN DIEGO": {"lat": 32.7157, "lon": -117.1611},
    "CORPUS CHRISTI": {"lat": 27.8006, "lon": -97.3964},
    "PORT ARTHUR AND LAKE CHARLES": {"lat": 29.9544, "lon": -93.9300},
    "MOBILE": {"lat": 30.6954, "lon": -88.0399},
    "JACKSONVILLE": {"lat": 30.3322, "lon": -81.6557},
    "HONOLULU": {"lat": 21.3099, "lon": -157.8581},
    "DELAWARE BAY": {"lat": 39.4593, "lon": -75.4145},
    "VIRGINIA": {"lat": 36.8468, "lon": -76.2951},
    "COLUMBIA RIVER": {"lat": 46.2084, "lon": -123.8312},
    "DETROIT": {"lat": 42.3314, "lon": -83.0458},
    "DULUTH": {"lat": 46.7867, "lon": -92.1005},
    "EASTERN GREAT LAKES": {"lat": 42.8864, "lon": -78.8784},
    "GUAM": {"lat": 13.4443, "lon": 144.7937},
    "HOUMA": {"lat": 29.5958, "lon": -90.7195},
    "KEY WEST": {"lat": 24.5551, "lon": -81.7800},
    "LAKE MICHIGAN": {"lat": 43.0389, "lon": -87.9065},
    "LONG ISLAND SOUND": {"lat": 41.0534, "lon": -73.5387},
    "LOWER MISSISSIPPI RIVER (MEMPHIS)": {"lat": 35.1495, "lon": -90.0490},
    "MARYLAND-NCR": {"lat": 38.9072, "lon": -77.0369},
    "NORTH CAROLINA": {"lat": 34.7293, "lon": -76.7266},
    "NORTHERN GREAT LAKES": {"lat": 46.4977, "lon": -84.3476},
    "NORTHERN NEW ENGLAND (PORTLAND, MAINE)": {"lat": 43.6591, "lon": -70.2568},
    "OHIO VALLEY": {"lat": 38.2527, "lon": -85.7585},
    "PITTSBURGH": {"lat": 40.4406, "lon": -79.9959},
    "PRINCE WILLIAM SOUND (VALDEZ)": {"lat": 61.1308, "lon": -146.3486},
    "SAN JUAN": {"lat": 18.4655, "lon": -66.1057},
    "SEAK - SOUTHEAST ALASKA (JUNEAU)": {"lat": 58.3019, "lon": -134.4197},
    "SOUTHEASTERN NEW ENGLAND (PROVIDENCE)": {"lat": 41.8240, "lon": -71.4128},
    "ST. PETERSBURG": {"lat": 27.7676, "lon": -82.6403},
    "UPPER MISSISSIPPI RIVER (ST. LOUIS)": {"lat": 38.6270, "lon": -90.1994},
    "WESTERN ALASKA (ANCHORAGE)": {"lat": 61.2181, "lon": -149.9003},
}

# ---------------------------------------------------------------------------
# Sub-port coordinates.  Key = "ZONENAME|SUBPORTNAME" (both upper-cased).
# These are populated automatically the FIRST time a sub-port is seen;
# if we don't have coords yet, we nudge slightly off the parent zone center
# so dots don't stack.  You can manually add precise coords here any time.
# ---------------------------------------------------------------------------
SUBPORT_COORDINATES: Dict[str, Dict[str, float]] = {
    # --- Charleston zone ---
    "CHARLESTON|BEAUFORT":        {"lat": 32.3539, "lon": -80.6703},
    "CHARLESTON|CHARLESTON":     {"lat": 32.7765, "lon": -79.9253},
    "CHARLESTON|GEORGETOWN":     {"lat": 33.3766, "lon": -79.2945},
    "CHARLESTON|HILTON HEAD":    {"lat": 32.1440, "lon": -80.8431},
    "CHARLESTON|LITTLE RIVER":   {"lat": 33.5826, "lon": -78.9291},
    "CHARLESTON|MCCLELLANVILLE": {"lat": 33.0296, "lon": -79.4606},
    "CHARLESTON|MURRELLS INLET": {"lat": 33.5460, "lon": -78.9950},
    "CHARLESTON|MYRTLE BEACH":   {"lat": 33.6946, "lon": -78.8910},
    "CHARLESTON|PORT ROYAL":     {"lat": 32.3780, "lon": -80.6850},

    # --- Houston-Galveston zone ---
    "HOUSTON-GALVESTON|FREEPORT":    {"lat": 28.5420, "lon": -95.1170},
    "HOUSTON-GALVESTON|GALVESTON":   {"lat": 29.3013, "lon": -94.8177},
    "HOUSTON-GALVESTON|HOUSTON":     {"lat": 29.7604, "lon": -95.3698},
    "HOUSTON-GALVESTON|TEXAS CITY":  {"lat": 29.4170, "lon": -94.9030},

    # --- Miami zone ---
    "MIAMI|FORT PIERCE":          {"lat": 27.1002, "lon": -80.1293},
    "MIAMI|MIAMI":                {"lat": 25.7617, "lon": -80.1918},
    "MIAMI|MIAMI RIVER":          {"lat": 25.7700, "lon": -80.2100},
    "MIAMI|PORT EVERGLADES":      {"lat": 26.0874, "lon": -80.1100},
    "MIAMI|PORT OF PALM BEACH":   {"lat": 26.7315, "lon": -80.0364},

    # --- New York zone ---
    "NEW YORK|NEW YORK":          {"lat": 40.6892, "lon": -74.0445},
    "NEW YORK|BROOKLYN":          {"lat": 40.6782, "lon": -73.9442},
    "NEW YORK|STATEN ISLAND":     {"lat": 40.5795, "lon": -74.1502},

    # --- Los Angeles-Long Beach zone ---
    "LOS ANGELES-LONG BEACH|LOS ANGELES":  {"lat": 33.7405, "lon": -118.2437},
    "LOS ANGELES-LONG BEACH|LONG BEACH":   {"lat": 33.7700, "lon": -118.1933},

    # --- New Orleans zone ---
    "NEW ORLEANS|NEW ORLEANS":    {"lat": 29.9511, "lon": -90.0715},
    "NEW ORLEANS|BATON ROUGE":    {"lat": 30.4515, "lon": -91.1871},

    # --- Boston zone ---
    "BOSTON|BOSTON":               {"lat": 42.3601, "lon": -71.0589},

    # --- Savannah zone ---
    "SAVANNAH|SAVANNAH":          {"lat": 32.1368, "lon": -81.0901},

    # --- San Francisco zone ---
    "SAN FRANCISCO|SAN FRANCISCO": {"lat": 37.7749, "lon": -122.4194},
    "SAN FRANCISCO|OAKLAND":      {"lat": 37.8044, "lon": -122.2711},
    "SAN FRANCISCO|STOCKTON":     {"lat": 37.9577, "lon": -121.2908},

    # --- Seattle zone ---
    "SEATTLE (PUGET SOUND)|SEATTLE":  {"lat": 47.6062, "lon": -122.3321},
    "SEATTLE (PUGET SOUND)|TACOMA":   {"lat": 47.2529, "lon": -122.4443},

    # --- San Diego zone ---
    "SAN DIEGO|SAN DIEGO":        {"lat": 32.7157, "lon": -117.1611},

    # --- Corpus Christi zone ---
    "CORPUS CHRISTI|CORPUS CHRISTI": {"lat": 27.8006, "lon": -97.3964},

    # --- Savannah zone ---
    "SAVANNAH|BRUNSWICK":         {"lat": 31.1467, "lon": -81.5158},

    # --- Jacksonville zone ---
    "JACKSONVILLE|JACKSONVILLE":  {"lat": 30.3322, "lon": -81.6557},
    "JACKSONVILLE|BRUNSWICK":     {"lat": 31.1467, "lon": -81.5158},

    # --- Mobile zone ---
    "MOBILE|MOBILE":              {"lat": 30.6954, "lon": -88.0399},

    # --- Key West zone ---
    "KEY WEST|KEY WEST":          {"lat": 24.5551, "lon": -81.7800},

    # --- Virginia zone ---
    "VIRGINIA|NORFOLK":           {"lat": 36.8508, "lon": -76.0121},
    "VIRGINIA|HAMPTON ROADS":     {"lat": 36.8300, "lon": -76.1000},

    # --- Delaware Bay zone ---
    "DELAWARE BAY|WILMINGTON":    {"lat": 39.7392, "lon": -75.5244},
    "DELAWARE BAY|PHILADELPHIA":  {"lat": 39.9526, "lon": -75.1652},

    # --- North Carolina zone ---
    "NORTH CAROLINA|MOREHEAD CITY": {"lat": 34.7226, "lon": -76.7249},
    "NORTH CAROLINA|WILMINGTON":    {"lat": 34.2258, "lon": -77.9461},

    # --- Honolulu zone ---
    "HONOLULU|HONOLULU":          {"lat": 21.3069, "lon": -157.8583},

    # --- Port Arthur / Lake Charles ---
    "PORT ARTHUR AND LAKE CHARLES|PORT ARTHUR":    {"lat": 29.8946, "lon": -94.0153},
    "PORT ARTHUR AND LAKE CHARLES|LAKE CHARLES":   {"lat": 30.1852, "lon": -93.2688},

    # --- Houma zone ---
    "HOUMA|HOUMA":                {"lat": 29.5958, "lon": -90.7195},
    "HOUMA|MORGAN CITY":          {"lat": 29.6944, "lon": -91.2083},

    # --- St. Petersburg zone ---
    "ST. PETERSBURG|ST. PETERSBURG": {"lat": 27.7676, "lon": -82.6403},
    "ST. PETERSBURG|TAMPA":        {"lat": 27.9506, "lon": -82.4572},

    # --- San Juan zone ---
    "SAN JUAN|SAN JUAN":          {"lat": 18.4655, "lon": -66.1057},

    # --- Guam zone ---
    "GUAM|GUAM":                  {"lat": 13.4443, "lon": 144.7937},
}


# ---------------------------------------------------------------------------
# Status severity ranking — higher number = worse condition
# ---------------------------------------------------------------------------
STATUS_SEVERITY = {
    "NORMAL": 0,
    "WHISKEY": 1,
    "X-RAY": 2,
    "YANKEE": 3,
    "ZULU": 4,
}


def status_from_text(raw_status: str) -> str:
    """
    Convert the raw status text from NAVCEN into our condition code.

    NAVCEN uses words like "Open", "Closed", "Open with Restrictions", etc.
    We map those to NORMAL / WHISKEY / X-RAY / YANKEE / ZULU.
    """
    t = raw_status.strip().upper()

    if not t or t == "OPEN":
        return "NORMAL"
    if t == "CLOSED":
        return "ZULU"
    if "RESTRICTION" in t:
        # "OPEN WITH RESTRICTIONS" -> at least WHISKEY; if comments hint at severity we upgrade later
        return "WHISKEY"
    # Catch explicit condition words anywhere in the text
    if "ZULU" in t:
        return "ZULU"
    if "YANKEE" in t:
        return "YANKEE"
    if "X-RAY" in t or "XRAY" in t:
        return "X-RAY"
    if "WHISKEY" in t:
        return "WHISKEY"

    return "NORMAL"


def upgrade_status_from_comments(base_status: str, comments: str) -> str:
    """
    If the Comments column mentions a specific condition or keywords that
    indicate a worse status than the Status column alone, upgrade accordingly.
    e.g.  Status=Open  Comments="WITH RESTRICTIONS - see MSIB..."  -> WHISKEY
          Status=Open  Comments="Port Condition IV"                 -> X-RAY
    """
    c = comments.strip().upper()
    if not c:
        return base_status

    # Explicit condition words in comments override base
    for keyword, code in [("ZULU", "ZULU"), ("YANKEE", "YANKEE"),
                          ("X-RAY", "X-RAY"), ("XRAY", "X-RAY"),
                          ("WHISKEY", "WHISKEY")]:
        if keyword in c:
            # Only upgrade, never downgrade
            if STATUS_SEVERITY.get(code, 0) > STATUS_SEVERITY.get(base_status, 0):
                return code

    # "WITH RESTRICTIONS" bumps to at least WHISKEY
    if "RESTRICTION" in c:
        if STATUS_SEVERITY.get("WHISKEY", 1) > STATUS_SEVERITY.get(base_status, 0):
            return "WHISKEY"

    # "Port Condition IV" or similar moderate-restriction language -> X-RAY
    if "CONDITION IV" in c or "CONDITION 4" in c:
        if STATUS_SEVERITY.get("X-RAY", 2) > STATUS_SEVERITY.get(base_status, 0):
            return "X-RAY"

    return base_status


def worst_status(statuses: List[str]) -> str:
    """Return the worst (highest severity) status from a list."""
    worst = "NORMAL"
    for s in statuses:
        if STATUS_SEVERITY.get(s, 0) > STATUS_SEVERITY.get(worst, 0):
            worst = s
    return worst


class NAVCENScraper:
    """Scraper for USCG NAVCEN port status — zones AND sub-ports."""

    BASE_URL = "https://www.navcen.uscg.gov/port-status"
    RATE_LIMIT_SECS = 1.0      # seconds between HTTP requests
    TIMEOUT_SECS = 20          # per-request timeout
    MAX_RETRIES = 3            # retry attempts on transient errors

    RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _get(self, url: str) -> Optional[requests.Response]:
        """GET with retry + back-off."""
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                resp = self.session.get(url, timeout=self.TIMEOUT_SECS)
                if resp.status_code in self.RETRYABLE_STATUS_CODES:
                    wait = 2 ** attempt
                    print(f"    ⚠️  HTTP {resp.status_code} — retry {attempt}/{self.MAX_RETRIES} in {wait}s")
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                return resp
            except requests.exceptions.Timeout:
                print(f"    ⚠️  Timeout — retry {attempt}/{self.MAX_RETRIES}")
                time.sleep(2 ** attempt)
            except requests.exceptions.RequestException as e:
                print(f"    ⚠️  {e} — retry {attempt}/{self.MAX_RETRIES}")
                time.sleep(2 ** attempt)
        return None                          # all retries exhausted

    # ------------------------------------------------------------------
    # zone list
    # ------------------------------------------------------------------
    def get_port_zones(self) -> List[str]:
        """Scrape the main port-status page for the list of all zone names."""
        resp = self._get(self.BASE_URL)
        if not resp:
            print("❌ Could not fetch main port-status page")
            return []

        soup = BeautifulSoup(resp.content, 'html.parser')
        zones = []
        for link in soup.find_all('a', href=re.compile(r'port-status\?zone=')):
            name = link.text.strip()
            if name and name not in zones:
                zones.append(name)
        print(f"✅ Found {len(zones)} COTP zones")
        return zones

    # ------------------------------------------------------------------
    # scrape one zone (COTP) and its sub-port table
    # ------------------------------------------------------------------
    def scrape_zone(self, zone: str) -> Optional[Dict]:
        """
        Scrape a single COTP zone page.  Returns a dict:
        {
            "zone_name": str,
            "marsec_level": str,
            "sector_info": str,
            "source_url": str,
            "sub_ports": [
                {
                    "name": str,            # as listed in NAVCEN table
                    "status": str,          # NORMAL | WHISKEY | X-RAY | YANKEE | ZULU
                    "comments": str,        # raw comment text from NAVCEN
                    "last_changed": str,    # date string e.g. "2025-09-30"
                    "latitude": float,
                    "longitude": float
                },
                ...
            ]
        }
        """
        url = f"{self.BASE_URL}?zone={zone}"
        resp = self._get(url)
        if not resp:
            print(f"  ❌ Failed to fetch {zone}")
            return None

        soup = BeautifulSoup(resp.content, 'html.parser')
        page_text = soup.get_text()

        # --- MARSEC level ---
        marsec_level = "MARSEC 1"
        marsec_match = re.search(r'MARSEC[- ]?(LEVEL[- ]?)?\d', page_text, re.IGNORECASE)
        if marsec_match:
            marsec_level = marsec_match.group(0).upper()

        # --- Sector info ---
        sector_info = ""
        sector_match = re.search(r'SECTOR\s+[\w\s-]+\s*\(\d{2}-\d{5}\)', page_text)
        if sector_match:
            sector_info = sector_match.group(0).strip()

        # --- Sub-port table ---
        # NAVCEN renders: <table> with <tr> rows.
        # Header row: Port | Status | Comments | Last Changed
        # Data rows:  name | open/closed | comment text | date
        sub_ports = []
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            if len(rows) < 2:
                continue
            # Check if header row contains expected columns
            header_text = rows[0].get_text().upper()
            if 'PORT' not in header_text or 'STATUS' not in header_text:
                continue                     # not our table

            for row in rows[1:]:             # skip header
                cols = row.find_all(['td', 'th'])
                if len(cols) < 3:
                    continue
                raw_name     = cols[0].get_text().strip()
                raw_status   = cols[1].get_text().strip()
                raw_comments = cols[2].get_text().strip() if len(cols) > 2 else ""
                raw_date     = cols[3].get_text().strip() if len(cols) > 3 else ""

                if not raw_name:
                    continue

                # Derive condition code
                base_cond = status_from_text(raw_status)
                final_cond = upgrade_status_from_comments(base_cond, raw_comments)

                # Coordinates — look up known, else nudge off parent
                key = f"{zone}|{raw_name}".upper()
                if key in SUBPORT_COORDINATES:
                    lat = SUBPORT_COORDINATES[key]["lat"]
                    lon = SUBPORT_COORDINATES[key]["lon"]
                else:
                    # Nudge: small random-ish offset so dots don't overlap
                    parent = COTP_COORDINATES.get(zone, {"lat": 39.8283, "lon": -98.5795})
                    idx = len(sub_ports)                # simple sequential offset
                    lat = parent["lat"] + (0.05 * ((idx % 5) - 2))
                    lon = parent["lon"] + (0.05 * ((idx // 5) - 1))
                    print(f"    ℹ️  No coords for sub-port '{raw_name}' in {zone} — using nudged position")

                sub_ports.append({
                    "name": raw_name,
                    "status": final_cond,
                    "comments": raw_comments,
                    "last_changed": raw_date,
                    "latitude": lat,
                    "longitude": lon,
                })

            break                            # we found and parsed the table, stop

        # If the table was empty or missing, treat the whole zone as one "port"
        if not sub_ports:
            parent = COTP_COORDINATES.get(zone, {"lat": 39.8283, "lon": -98.5795})
            sub_ports.append({
                "name": zone.title(),
                "status": "NORMAL",
                "comments": "",
                "last_changed": "",
                "latitude": parent["lat"],
                "longitude": parent["lon"],
            })
            print(f"    ⚠️  No sub-port table found for {zone} — treating as single port")

        return {
            "zone_name": zone,
            "marsec_level": marsec_level,
            "sector_info": sector_info,
            "source_url": url,
            "sub_ports": sub_ports,
        }

    # ------------------------------------------------------------------
    # scrape everything
    # ------------------------------------------------------------------
    def scrape_all_zones(self) -> List[Dict]:
        """Scrape every COTP zone and its sub-ports."""
        zones = self.get_port_zones()
        if not zones:
            print("❌ No zones found — aborting")
            return []

        all_zones = []
        for i, zone in enumerate(zones, 1):
            print(f"[{i}/{len(zones)}] Scraping {zone}...")
            data = self.scrape_zone(zone)
            if data:
                all_zones.append(data)
                n = len(data["sub_ports"])
                print(f"         ✅ {n} sub-port(s)")
            time.sleep(self.RATE_LIMIT_SECS)

        print(f"\n✅ Scraped {len(all_zones)} zones")
        return all_zones


# ---------------------------------------------------------------------------
# Quick stand-alone test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    scraper = NAVCENScraper()

    print("=== Testing single zone: CHARLESTON ===\n")
    charleston = scraper.scrape_zone("CHARLESTON")
    if charleston:
        print(f"\nZone: {charleston['zone_name']}")
        print(f"MARSEC: {charleston['marsec_level']}")
        print(f"Sub-ports ({len(charleston['sub_ports'])}):")
        for sp in charleston["sub_ports"]:
            print(f"  {sp['name']:25s} | {sp['status']:8s} | {sp['comments']}")