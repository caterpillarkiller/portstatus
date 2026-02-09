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

# Auto-generated port coordinates
PORT_COORDINATES = {
    "32nd Street": {"lat": 40.772905, "lon": -73.913537},
    "ADAK": {"lat": 51.873613, "lon": -176.639032},
    "AFOGNAK": {"lat": 58.007217, "lon": -152.769410},
    "AICW - BEAUFORT TO CAPE FEAR": {"lat": 34.719033, "lon": -76.693383},
    "AICW - CAPE FEAR TO LITTLE RIVER": {"lat": 34.719033, "lon": -76.693383},
    "AICW - NORFOLK TO BEAUFORT": {"lat": 34.719033, "lon": -76.693383},
    "AKUTAN": {"lat": 54.133449, "lon": -165.776486},
    "ALBEMARLE & CHESAPEAKE CANAL - ICW": {"lat": 36.723684, "lon": -76.167684},
    "ALEXANDRIA": {"lat": 32.340130, "lon": -90.270404},
    "ALEXANDRIA BAY": {"lat": 44.336241, "lon": -75.918063},
    "AMELIA": {"lat": 37.331966, "lon": -78.008448},
    "ANACORTES": {"lat": 48.521724, "lon": -122.611852},
    "ANCHORAGE 9 (SOUTH SFB)": {"lat": 0.000000, "lon": 0.000000},
    "APRA HARBOR": {"lat": 13.422866, "lon": 144.662993},
    "ASHLAND, WI": {"lat": 46.206232, "lon": -90.680259},
    "ASHTABULA": {"lat": 41.898751, "lon": -80.790682},
    "Albany": {"lat": 42.621700, "lon": -73.759016},
    "Atchafalaya River MM 00 to MM 45": {"lat": 0.000000, "lon": 0.000000},
    "BALTIMORE": {"lat": 39.269489, "lon": -76.569448},
    "BANGOR": {"lat": 44.801626, "lon": -68.771329},
    "BAR HARBOR, ME": {"lat": 44.391601, "lon": -68.204483},
    "BARDEN INLET": {"lat": 0.000000, "lon": 0.000000},
    "BAYFIELD, WI": {"lat": 46.780322, "lon": -91.384072},
    "BAYOU BOEUF LOCK": {"lat": 29.682936, "lon": -91.175962},
    "BAYOU CHENE": {"lat": 29.639599, "lon": -91.093991},
    "BAYOU LAFOURCHE": {"lat": 29.651884, "lon": -90.542259},
    "BAYOU SORREL LOCK": {"lat": 30.133122, "lon": -91.322962},
    "BEAUFORT": {"lat": 32.474397, "lon": -80.743158},
    "BEAUMONT (TX)": {"lat": 30.079020, "lon": -94.091830},
    "BELLINGHAM": {"lat": 42.386063, "lon": -71.032501},
    "BERWICK": {"lat": 41.060202, "lon": -76.246126},
    "BETHEL": {"lat": 60.791462, "lon": -161.748675},
    "BIG BEND": {"lat": 39.698218, "lon": -121.460802},
    "BLYTHEVILLE": {"lat": 35.928325, "lon": -89.904561},
    "BOCA GRANDE": {"lat": 26.748959, "lon": -82.262039},
    "BODEGA BAY": {"lat": 33.610120, "lon": -117.848478},
    "BOGUE INLET": {"lat": 34.664980, "lon": -77.034963},
    "BOSTON": {"lat": 42.367663, "lon": -71.053083},
    "BRADENTON": {"lat": 27.498928, "lon": -82.574819},
    "BREMERTON": {"lat": 47.487018, "lon": -122.764063},
    "BRIDGEPORT": {"lat": 41.179269, "lon": -73.188786},
    "BROADWAY": {"lat": 41.904300, "lon": -73.974956},
    "BROOKLYN": {"lat": 40.685873, "lon": -74.007056},
    "BRUNSWICK": {"lat": 36.778900, "lon": -77.867088},
    "BUFFALO": {"lat": 42.849503, "lon": -78.863924},
    "BURNS HARBOR, IN": {"lat": 41.633566, "lon": -87.153889},
    "CABRILLO": {"lat": 32.672226, "lon": -117.240939},
    "CALUMET, IL": {"lat": 41.667447, "lon": -87.592741},
    "CAMDEN": {"lat": 32.782356, "lon": -89.838692},
    "CAMERON": {"lat": 25.964507, "lon": -97.375920},
    "CAPE HINCHINBROOK ENTRANCE": {"lat": 0.000000, "lon": 0.000000},
    "CAPE VINCENT": {"lat": 44.128925, "lon": -76.334294},
    "CAROLINA BEACH INLET": {"lat": 0.000000, "lon": 0.000000},
    "CARQUINEZ STRAIT (& FACILITIES)": {"lat": 0.000000, "lon": 0.000000},
    "CARUTHERSVILLE": {"lat": 35.921172, "lon": -89.908991},
    "CATALINA ISLAND - AVALON HARBOR": {"lat": 0.000000, "lon": 0.000000},
    "CATALINA ISLAND - TWO HARBORS": {"lat": 0.000000, "lon": 0.000000},
    "CATOOSA": {"lat": 0.000000, "lon": 0.000000},
    "CC BUOY LAKE CHARLES P.S.": {"lat": 0.000000, "lon": 0.000000},
    "CEDAR KEY": {"lat": 29.137721, "lon": -83.035964},
    "CHANNEL ISLANDS HARBOR": {"lat": 34.164172, "lon": -119.224275},
    "CHARENTON CANAL": {"lat": 29.912801, "lon": -91.541077},
    "CHARLESTON": {"lat": 32.835766, "lon": -79.882915},
    "CHARLOTTE": {"lat": 27.029636, "lon": -82.197615},
    "CHENEGA BAY": {"lat": 60.065297, "lon": -148.014290},
    "CHERRY POINT": {"lat": 39.258792, "lon": -120.512150},
    "CHESAPEAKE & DELAWARE CANAL (FROM DELAWARE RIVER ENTRANCE TO DELAWARE/MARYLAND STATELINE)": {"lat": 0.000000, "lon": 0.000000},
    "CHESAPEAKE BAY ENTRANCE - PILOT STATION": {"lat": 0.000000, "lon": 0.000000},
    "CHESAPEAKE BAY NORTH CHANNEL TO MD": {"lat": 0.000000, "lon": 0.000000},
    "CHICAGO, IL": {"lat": 41.667447, "lon": -87.592741},
    "CHINCOTEAGUE": {"lat": 37.933180, "lon": -75.378814},
    "CINCINNATI": {"lat": 39.099314, "lon": -84.536271},
    "CITY OF LONG BEACH": {"lat": 40.588551, "lon": -73.658263},
    "CLEVELAND": {"lat": 41.503986, "lon": -81.703746},
    "COLD BAY": {"lat": 55.207163, "lon": -162.714653},
    "CONNEAUT": {"lat": 41.944098, "lon": -80.556101},
    "CONNECTICUT RIVER": {"lat": 41.352742, "lon": -71.972085},
    "COOK INLET": {"lat": 58.941944, "lon": -153.185555},
    "CORDOVA": {"lat": 31.767242, "lon": -106.450977},
    "CORONADO": {"lat": 32.620481, "lon": -117.133254},
    "CORTE MADERA CHANNEL": {"lat": 37.944138, "lon": -122.507149},
    "CRESCENT CITY HARBOR": {"lat": 43.079802, "lon": -89.469041},
    "Calhoun Port Authority": {"lat": 0.000000, "lon": 0.000000},
    "DANA POINT": {"lat": 33.474653, "lon": -117.682910},
    "DE COAST AND DE ICW": {"lat": 0.000000, "lon": 0.000000},
    "DELAWARE BAY (INCLUDING THEIR TRIBUTARIES)": {"lat": 0.000000, "lon": 0.000000},
    "DELAWARE RIVER (INCLUDING THEIR TRIBUTARIES)": {"lat": 0.000000, "lon": 0.000000},
    "DETROIT RIVER": {"lat": 42.000819, "lon": -83.141245},
    "DILLINGHAM": {"lat": 59.038096, "lon": -158.464064},
    "DULUTH, MN": {"lat": 46.782844, "lon": -92.106868},
    "DUNKIRK": {"lat": 42.483224, "lon": -79.334560},
    "EAST BAY": {"lat": 42.143962, "lon": -80.077506},
    "EASTERN LAKE ERIE": {"lat": 0.000000, "lon": 0.000000},
    "EASTPORT": {"lat": 44.905039, "lon": -66.984637},
    "EGMONT KEY": {"lat": 27.589357, "lon": -82.762317},
    "EL SEGUNDO": {"lat": 33.923885, "lon": -118.378659},
    "ELLWOOD": {"lat": 33.304309, "lon": -82.129286},
    "ERIE": {"lat": 42.849503, "lon": -78.863924},
    "ESCANABA, MI": {"lat": 45.745571, "lon": -87.064743},
    "EVANSVILLE": {"lat": 41.155891, "lon": -80.762858},
    "EVERETT": {"lat": 47.980557, "lon": -122.218232},
    "FAIRPORT HARBOR": {"lat": 41.751916, "lon": -81.272346},
    "FALSE PASS": {"lat": 54.855256, "lon": -163.415370},
    "FERNDALE": {"lat": 42.460592, "lon": -83.134648},
    "FORT MYERS BEACH": {"lat": 26.452025, "lon": -81.948145},
    "FORT PIERCE": {"lat": 27.446706, "lon": -80.325606},
    "FORT SMITH": {"lat": 0.000000, "lon": 0.000000},
    "FRANKFORT, MI": {"lat": 44.633622, "lon": -86.234184},
    "FREEPORT": {"lat": 28.942304, "lon": -95.335011},
    "GALVESTON": {"lat": 29.307058, "lon": -94.804201},
    "GARY, IN": {"lat": 41.602096, "lon": -87.337065},
    "GEORGETOWN": {"lat": 30.637015, "lon": -97.677563},
    "GIWW": {"lat": 0.000000, "lon": 0.000000},
    "GIWW MM 44.2 EHL -20 WHL": {"lat": 0.000000, "lon": 0.000000},
    "GLADSTONE, MI": {"lat": 45.845757, "lon": -87.018847},
    "GLOUCESTER HARBOR": {"lat": 42.595929, "lon": -70.668933},
    "GRAND HAVEN, MI": {"lat": 43.063073, "lon": -86.228386},
    "GRAND MARAIS, MN": {"lat": 47.750467, "lon": -90.334675},
    "GREAT SOUTH BAY": {"lat": 40.690377, "lon": -73.101501},
    "GREEN BAY, WI": {"lat": 44.595396, "lon": -88.088210},
    "GREENVILLE": {"lat": 33.411105, "lon": -91.063586},
    "GREENWICH": {"lat": 41.010573, "lon": -73.666531},
    "GROTON/NEW LONDON": {"lat": 41.364311, "lon": -72.089344},
    "GULFPORT": {"lat": 30.361109, "lon": -89.094011},
    "HALF MOON BAY": {"lat": 37.463552, "lon": -122.428586},
    "HAMPTON ROADS AND THIMBLE SHOAL CH": {"lat": 0.000000, "lon": 0.000000},
    "HATTERAS INLET": {"lat": 35.192551, "lon": -75.752561},
    "HELENA": {"lat": 30.484576, "lon": -88.495261},
    "HILLSBOROUGH BAY": {"lat": 27.865839, "lon": -82.450395},
    "HILO HARBOR (Big Island)": {"lat": 0.000000, "lon": 0.000000},
    "HILTON HEAD": {"lat": 32.383630, "lon": -99.748275},
    "HOLLAND, MI": {"lat": 42.787602, "lon": -86.109083},
    "HOMER": {"lat": 59.604799, "lon": -151.423795},
    "HONOLULU HARBOR (Oahu)": {"lat": 0.000000, "lon": 0.000000},
    "HOUGHTON/HANCOCK, MI": {"lat": 47.124976, "lon": -88.574386},
    "HOUMA": {"lat": 29.595407, "lon": -90.723821},
    "HOUMA NAVIGATION CANAL": {"lat": 29.425183, "lon": -90.723290},
    "HOUSTON": {"lat": 29.605072, "lon": -95.177814},
    "HUMBOLDT BAY": {"lat": 40.749848, "lon": -124.209506},
    "HUNTINGTON": {"lat": 41.103110, "lon": -82.220992},
    "HUNTINGTON HARBOR": {"lat": 40.870526, "lon": -73.460288},
    "INDIANA HARBOR, IN": {"lat": 41.633566, "lon": -87.153889},
    "INTERCOASTAL CITY": {"lat": 0.000000, "lon": 0.000000},
    "INTERNATIONAL PORT OF DUTCH HARBOR": {"lat": 0.000000, "lon": 0.000000},
    "Illinois River - Zone 1 (Grafton, MM 0-9.9)": {"lat": 0.000000, "lon": 0.000000},
    "Illinois River - Zone 2 (Hardin, MM 10-49.9)": {"lat": 0.000000, "lon": 0.000000},
    "Illinois River - Zone 3 (Meredosia, MM 50-80.2)": {"lat": 0.000000, "lon": 0.000000},
    "Illinois River - Zone 4 (Beardstown, MM 80.3-101.9)": {"lat": 0.000000, "lon": 0.000000},
    "Illinois River - Zone 5 (Havana, MM 102-128.9)": {"lat": 0.000000, "lon": 0.000000},
    "Illinois River - Zone 6 (Copperas Creek, MM 129-145.5)": {"lat": 0.000000, "lon": 0.000000},
    "Illinois River - Zone 7 (Peoria, MM 145.6-187)": {"lat": 0.000000, "lon": 0.000000},
    "KAHULUI HARBOR (Maui)": {"lat": 20.895791, "lon": -156.471941},
    "KAKTOVIK": {"lat": 70.127450, "lon": -143.612865},
    "KALAELOA BARBERS POINT HARBOR (Oahu)": {"lat": 0.000000, "lon": 0.000000},
    "KAUMALAPAU HARBOR (Lanai)": {"lat": 0.000000, "lon": 0.000000},
    "KAUNAKAKAI HARBOR (Molokai)": {"lat": 0.000000, "lon": 0.000000},
    "KAWAIHAE HARBOR (Big Island)": {"lat": 0.000000, "lon": 0.000000},
    "KENAI": {"lat": 59.604799, "lon": -151.423795},
    "KEY WEST": {"lat": 24.564695, "lon": -81.797630},
    "KING COVE": {"lat": 55.059662, "lon": -162.311411},
    "KING SALMON": {"lat": 58.688434, "lon": -156.661838},
    "KIVALINA": {"lat": 67.727876, "lon": -164.540719},
    "KNOWLES HEAD ANCHORAGE": {"lat": 0.000000, "lon": 0.000000},
    "KODIAK": {"lat": 57.790166, "lon": -152.406707},
    "KOTZEBUE": {"lat": 66.898206, "lon": -162.597762},
    "LA POINTE, MADELINE ISLAND, WI": {"lat": 0.000000, "lon": 0.000000},
    "LACKAWANNA": {"lat": 41.446985, "lon": -75.799485},
    "LAKE CHARLES": {"lat": 30.230510, "lon": -93.216981},
    "LAKE ERIE": {"lat": 42.143225, "lon": -81.239436},
    "LAKE HURON": {"lat": 46.146157, "lon": -84.089812},
    "LAKE ONTARIO": {"lat": 43.363873, "lon": -78.241309},
    "LAKE PROVIDENCE": {"lat": 0.000000, "lon": 0.000000},
    "LAKE ST. CLAIR": {"lat": 42.493484, "lon": -82.739273},
    "LARSEN BAY": {"lat": 57.536558, "lon": -153.981606},
    "LITTLE RIVER": {"lat": 33.696879, "lon": -94.206540},
    "LITTLE ROCK": {"lat": 32.525973, "lon": -89.025334},
    "LOCKWOODS FOLLY INLET": {"lat": 0.000000, "lon": 0.000000},
    "LOOP": {"lat": 48.000715, "lon": -122.217113},
    "LOOP PLATFORM": {"lat": 0.000000, "lon": 0.000000},
    "LORAIN": {"lat": 41.263355, "lon": -82.173475},
    "LOUISVILLE": {"lat": 40.837531, "lon": -81.259573},
    "LUDINGTON, MI": {"lat": 43.952974, "lon": -86.459201},
    "Lake Michigan-Grays Reef Passage": {"lat": 42.537018, "lon": -83.359624},
    "Leland Bowman Locks": {"lat": 0.000000, "lon": 0.000000},
    "Lower Columbia River (Entrance Bar up to Vancouver, WA)": {"lat": 0.000000, "lon": 0.000000},
    "MA - CAPE COD CANAL": {"lat": 41.751505, "lon": -70.584014},
    "MA - PORT OF FALL RIVER/SOMERSET": {"lat": 42.499409, "lon": -90.663975},
    "MA - PORT OF HYANNIS": {"lat": 42.499409, "lon": -90.663975},
    "MA - PORT OF NANTUCKET": {"lat": 42.499409, "lon": -90.663975},
    "MA - PORT OF NEW BEDFORD/FAIRHAVEN": {"lat": 42.499409, "lon": -90.663975},
    "MA - PORT OF OAK BLUFFS/MARTHA'S VINEYARD": {"lat": 42.499409, "lon": -90.663975},
    "MA - PORT OF PROVINCETOWN": {"lat": 42.499409, "lon": -90.663975},
    "MA - PORT OF VINEYARD HAVEN/MARTHA'S VINEYARD": {"lat": 42.499409, "lon": -90.663975},
    "MA - PORT OF WOODS HOLE": {"lat": 42.499409, "lon": -90.663975},
    "MANISTEE, MI": {"lat": 44.330804, "lon": -86.026204},
    "MANITOWOC, WI": {"lat": 44.074064, "lon": -87.696988},
    "MARCH POINT": {"lat": 48.500223, "lon": -122.557785},
    "MARINA DEL REY": {"lat": 33.977685, "lon": -118.448647},
    "MARINETTE, WI": {"lat": 45.383498, "lon": -88.040957},
    "MASONBORO INLET": {"lat": 34.184893, "lon": -77.812205},
    "MASSENA": {"lat": 44.981183, "lon": -74.739531},
    "MEMPHIS": {"lat": 34.982718, "lon": -89.776624},
    "MENOMINEE, MI": {"lat": 45.578574, "lon": -87.562159},
    "MIAMI": {"lat": 25.773514, "lon": -80.169196},
    "MIAMI RIVER": {"lat": 39.724598, "lon": -84.226967},
    "MILWAUKEE, WI": {"lat": 43.012807, "lon": -87.897432},
    "MISSION BAY": {"lat": 26.373286, "lon": -80.207437},
    "MOBILE": {"lat": 33.635161, "lon": -117.937259},
    "MONROE": {"lat": 33.888493, "lon": -88.474701},
    "MONTAGUE STRAIT": {"lat": 0.000000, "lon": 0.000000},
    "MONTAUK": {"lat": 41.044676, "lon": -71.959543},
    "MONTEREY HARBOR": {"lat": 36.606915, "lon": -121.890536},
    "MORGAN CITY": {"lat": 34.619185, "lon": -86.986857},
    "MORRILTON": {"lat": 0.000000, "lon": 0.000000},
    "MORRO BAY": {"lat": 35.365808, "lon": -120.849901},
    "MOSS LANDING": {"lat": 36.803594, "lon": -121.786275},
    "MOTCO": {"lat": 38.036647, "lon": -122.015968},
    "MT. VERNON": {"lat": 40.393396, "lon": -82.485718},
    "MURRELLS INLET": {"lat": 33.547481, "lon": -79.064006},
    "MUSKEGON, MI": {"lat": 43.234181, "lon": -86.248392},
    "MUSKOGEE": {"lat": 0.000000, "lon": 0.000000},
    "MYRTLE BEACH": {"lat": 33.695646, "lon": -78.890041},
    "MYSTIC": {"lat": 41.352742, "lon": -71.972085},
    "McCLELLANVILLE": {"lat": 33.088225, "lon": -79.461174},
    "Mississippi River MM 20 BHP-167.5 AHP": {"lat": 0.000000, "lon": 0.000000},
    "Mississippi River from MM 167.5 to MM 303 AHP": {"lat": 0.000000, "lon": 0.000000},
    "Missouri River - Brunswick Reach (MM 300-200)": {"lat": 0.000000, "lon": 0.000000},
    "Missouri River - Jefferson Reach (MM 200-100)": {"lat": 0.000000, "lon": 0.000000},
    "Missouri River - Kansas City Reach (MM 400-300)": {"lat": 0.000000, "lon": 0.000000},
    "Missouri River - Omaha Reach (MM 630-500)": {"lat": 0.000000, "lon": 0.000000},
    "Missouri River - Sioux City Reach (MM 734.8-630)": {"lat": 0.000000, "lon": 0.000000},
    "Missouri River - St. Joseph Reach (MM 500-400)": {"lat": 0.000000, "lon": 0.000000},
    "Missouri River - Washington Reach (MM 100-0)": {"lat": 0.000000, "lon": 0.000000},
    "NAKNEK": {"lat": 58.726664, "lon": -157.018426},
    "NAPA RIVER (VALLEJO)": {"lat": 0.000000, "lon": 0.000000},
    "NASHVILLE (CMB RIVER, TN RIVER IN EAST TN)": {"lat": 0.000000, "lon": 0.000000},
    "NATCHEZ": {"lat": 31.560408, "lon": -91.403171},
    "NATIONAL CITY": {"lat": 32.678109, "lon": -117.099197},
    "NAWILIWILI HARBOR (Kauai)": {"lat": 21.953037, "lon": -159.355874},
    "NENANA": {"lat": 64.563529, "lon": -149.095978},
    "NEW HAVEN": {"lat": 40.841277, "lon": -73.711705},
    "NEW RIVER INLET": {"lat": 34.527388, "lon": -77.336903},
    "NEW TOPSAIL INLET": {"lat": 34.340538, "lon": -77.664785},
    "NEW YORK": {"lat": 41.375014, "lon": -74.691971},
    "NEWPORT BAY HARBOR": {"lat": 39.857544, "lon": -74.133922},
    "NIKISKI": {"lat": 60.721058, "lon": -151.246208},
    "NJ COAST AND NJ ICW": {"lat": 0.000000, "lon": 0.000000},
    "NOME": {"lat": 64.498992, "lon": -165.398799},
    "NORTH LITTLE ROCK": {"lat": 0.000000, "lon": 0.000000},
    "NORTH TONAWANDA": {"lat": 43.040774, "lon": -78.866053},
    "NORTHEAST MISSISSIPPI (TEN TOM WATERWAY)": {"lat": 0.000000, "lon": 0.000000},
    "NORTHERN ALABAMA (TN RIVER IN ALABAMA)": {"lat": 0.000000, "lon": 0.000000},
    "NORWALK": {"lat": 41.117597, "lon": -73.407897},
    "NOYO RIVER (FORT BRAGG)": {"lat": 39.437784, "lon": -123.657641},
    "Nouthern Coast Ports (Cape Disappointment, OR north to Grays Harbor, WA)": {"lat": 0.000000, "lon": 0.000000},
    "OCEANSIDE": {"lat": 33.190496, "lon": -117.355134},
    "OCRACOKE INLET": {"lat": 35.062928, "lon": -76.027408},
    "OGDENSBURG": {"lat": 44.706107, "lon": -75.482147},
    "OLD RIVER LOCK": {"lat": 31.001053, "lon": -91.670369},
    "OLYMPIA": {"lat": 47.053472, "lon": -122.901936},
    "ONTONAGON, MI": {"lat": 46.647188, "lon": -89.329379},
    "ORANGE": {"lat": 41.375014, "lon": -74.691971},
    "OREGON INLET": {"lat": 35.775560, "lon": -75.532032},
    "ORIENT POINT": {"lat": 41.154653, "lon": -72.246437},
    "OSCEOLA": {"lat": 35.705078, "lon": -89.969532},
    "OSWEGO": {"lat": 43.464745, "lon": -76.510171},
    "OWENSBORO": {"lat": 37.418706, "lon": -86.879165},
    "OYSTER BAY": {"lat": 40.769657, "lon": -73.499861},
    "PADUCAH": {"lat": 39.386190, "lon": -84.530760},
    "PAGO PAGO (American Samoa)": {"lat": -14.276934, "lon": -170.685462},
    "PANAMA CITY": {"lat": 30.180337, "lon": -85.729139},
    "PASCAGOULA": {"lat": 30.364680, "lon": -88.558599},
    "PELEE PASS": {"lat": 0.000000, "lon": 0.000000},
    "PENSACOLA": {"lat": 30.404086, "lon": -87.209140},
    "PETALUMA RIVER": {"lat": 38.200685, "lon": -122.566550},
    "PINE BLUFF": {"lat": 33.348456, "lon": -90.153973},
    "PITTSBURGH": {"lat": 40.368320, "lon": -80.109385},
    "PLYMOUTH": {"lat": 42.096068, "lon": -70.691052},
    "POINT HOPE": {"lat": 68.349305, "lon": -166.739207},
    "POINT LOMA": {"lat": 32.726526, "lon": -117.244454},
    "POINT MUGU": {"lat": 34.085414, "lon": -119.060992},
    "PORT ALLEN (Kauai)": {"lat": 21.901113, "lon": -159.587161},
    "PORT ALLEN LOCK": {"lat": 30.431125, "lon": -91.206704},
    "PORT ANGELES": {"lat": 48.118146, "lon": -123.430741},
    "PORT ARTHUR": {"lat": 29.871658, "lon": -93.933230},
    "PORT CANAVERAL": {"lat": 28.416056, "lon": -80.607827},
    "PORT CHESTER": {"lat": 41.001764, "lon": -73.665683},
    "PORT CLARENCE": {"lat": 65.154227, "lon": -166.933968},
    "PORT EVERGLADES": {"lat": 26.096852, "lon": -80.127261},
    "PORT FOURCHON": {"lat": 29.123236, "lon": -90.189240},
    "PORT GRAHAM": {"lat": 59.339569, "lon": -151.845055},
    "PORT HADLOCK (INDIAN ISLAND)": {"lat": 0.000000, "lon": 0.000000},
    "PORT JEFFERSON": {"lat": 40.946512, "lon": -73.069126},
    "PORT LIONS": {"lat": 57.867556, "lon": -152.883105},
    "PORT MACKENZIE": {"lat": 61.268991, "lon": -149.920295},
    "PORT MANATEE CHANNEL": {"lat": 0.000000, "lon": 0.000000},
    "PORT MOLLER": {"lat": 55.988611, "lon": -160.576944},
    "PORT OF ALASKA (ANCHORAGE)": {"lat": 61.244687, "lon": -149.881695},
    "PORT OF BENICIA": {"lat": 38.056344, "lon": -122.126290},
    "PORT OF BROWNSVILLE": {"lat": 25.964507, "lon": -97.375920},
    "PORT OF FERNANDINA": {"lat": 0.000000, "lon": 0.000000},
    "PORT OF GUSTAVUS/GLACIER BAY": {"lat": 0.000000, "lon": 0.000000},
    "PORT OF HAINES": {"lat": 0.000000, "lon": 0.000000},
    "PORT OF HOONAH/ICY STRAITS": {"lat": 0.000000, "lon": 0.000000},
    "PORT OF HUENEME": {"lat": 34.149172, "lon": -119.208719},
    "PORT OF JACKSONVILLE": {"lat": 30.421084, "lon": -81.571719},
    "PORT OF JUNEAU/AUKE BAY": {"lat": 0.000000, "lon": 0.000000},
    "PORT OF KAKE": {"lat": 0.000000, "lon": 0.000000},
    "PORT OF KETCHIKAN/WARD COVE": {"lat": 0.000000, "lon": 0.000000},
    "PORT OF KLAWOCK (Prince of Wales Island)": {"lat": 0.000000, "lon": 0.000000},
    "PORT OF LONG BEACH": {"lat": 33.753700, "lon": -118.216561},
    "PORT OF LOS ANGELES": {"lat": 33.741951, "lon": -118.261237},
    "PORT OF MOREHEAD CITY": {"lat": 34.719290, "lon": -76.699655},
    "PORT OF NEW IBERIA": {"lat": 0.000000, "lon": 0.000000},
    "PORT OF OAKLAND": {"lat": 37.795759, "lon": -122.278821},
    "PORT OF PALM BEACH": {"lat": 26.767007, "lon": -80.051152},
    "PORT OF PETERSBURG": {"lat": 0.000000, "lon": 0.000000},
    "PORT OF REDWOOD CITY": {"lat": 37.513270, "lon": -122.208577},
    "PORT OF RICHMOND": {"lat": 39.991380, "lon": -75.102416},
    "PORT OF SACRAMENTO": {"lat": 0.000000, "lon": 0.000000},
    "PORT OF SAN FRANCISCO": {"lat": 37.783074, "lon": -122.511316},
    "PORT OF SITKA": {"lat": 57.116106, "lon": -135.394746},
    "PORT OF SKAGWAY": {"lat": 59.527413, "lon": -135.229827},
    "PORT OF STOCKTON": {"lat": 37.951035, "lon": -121.326614},
    "PORT OF VICTORIA": {"lat": -37.846931, "lon": 144.980090},
    "PORT OF WEST ST. MARY": {"lat": 0.000000, "lon": 0.000000},
    "PORT OF WILMINGTON": {"lat": 34.197846, "lon": -77.952593},
    "PORT OF WRANGELL": {"lat": 0.000000, "lon": 0.000000},
    "PORT OF YAKUTAT": {"lat": 0.000000, "lon": 0.000000},
    "PORT ROYAL": {"lat": 32.379084, "lon": -80.692607},
    "PORT SAN LUIS": {"lat": 35.172055, "lon": -120.756086},
    "PORT SUTTON": {"lat": 27.906690, "lon": -82.420649},
    "PORT TOWNSEND": {"lat": 48.117970, "lon": -122.769544},
    "PORT VALDEZ": {"lat": 61.105556, "lon": -146.501944},
    "PORTAGE": {"lat": 61.669634, "lon": -150.087141},
    "PORTLAND HARBOR": {"lat": 43.657582, "lon": -70.240604},
    "PORTSMOUTH, NH": {"lat": 43.075131, "lon": -70.760183},
    "PR, ARECIBO": {"lat": 18.404750, "lon": -66.681035},
    "PR, CEIBA / ROOSEVELT ROADS": {"lat": 0.000000, "lon": 0.000000},
    "PR, CULEBRA": {"lat": 18.313678, "lon": -65.282623},
    "PR, FAJARDO": {"lat": 18.327803, "lon": -65.656183},
    "PR, GUANICA": {"lat": 17.979837, "lon": -66.915646},
    "PR, GUAYAMA / LAS MAREAS": {"lat": 17.958930, "lon": -66.138172},
    "PR, GUAYANILLA": {"lat": 18.044225, "lon": -66.795712},
    "PR, MAYAGUEZ": {"lat": 18.211635, "lon": -67.095357},
    "PR, PONCE": {"lat": 17.968028, "lon": -66.617404},
    "PR, SALINAS/AGUIRRE": {"lat": 17.954869, "lon": -66.222833},
    "PR, SAN JUAN": {"lat": 18.460602, "lon": -66.116259},
    "PR, TALLABOA": {"lat": 18.009971, "lon": -66.739128},
    "PR, VIEQUES": {"lat": 18.152462, "lon": -65.442659},
    "PR, YABUCOA": {"lat": 18.068739, "lon": -65.903608},
    "PRINCE WILLIAM SOUND": {"lat": 60.615000, "lon": -147.168056},
    "Port Allen Route MM 0-64.1": {"lat": 0.000000, "lon": 0.000000},
    "Port Isabel": {"lat": 26.073412, "lon": -97.208584},
    "Port Mansfield": {"lat": 26.554788, "lon": -97.424981},
    "Port Of New Orleans": {"lat": 29.937231, "lon": -90.061446},
    "Port of Greater Baton Rouge": {"lat": 30.438503, "lon": -91.201716},
    "Port of Harlingen": {"lat": 0.000000, "lon": 0.000000},
    "Port of New York and New Jersey": {"lat": 0.000000, "lon": 0.000000},
    "Port of Palacios": {"lat": 0.000000, "lon": 0.000000},
    "Port of Plaquemines": {"lat": 0.000000, "lon": 0.000000},
    "Port of South LA": {"lat": 36.161623, "lon": -115.173461},
    "Port of St. Bernard": {"lat": 0.000000, "lon": 0.000000},
    "RATTLESNAKE": {"lat": 27.889468, "lon": -82.524263},
    "RED DOG MINE": {"lat": 68.070680, "lon": -162.875059},
    "REDONDO BEACH - KING HARBOR": {"lat": 33.846302, "lon": -118.394961},
    "RI - PORT OF GALILEE": {"lat": 41.379819, "lon": -71.508908},
    "RI - PORT OF NEW HARBOR/BLOCK ISLAND": {"lat": 41.379819, "lon": -71.508908},
    "RI - PORT OF NEWPORT/JAMESTOWN": {"lat": 41.379819, "lon": -71.508908},
    "RI - PORT OF PROVIDENCE/EAST PROVIDENCE": {"lat": 0.000000, "lon": 0.000000},
    "RI - PORT OF QUONSET/DAVISVILLE": {"lat": 41.379819, "lon": -71.508908},
    "RICHARDSON BAY": {"lat": 37.879256, "lon": -122.484723},
    "RICHMOND - HOPEWELL": {"lat": 37.292326, "lon": -77.302075},
    "RIVERHEAD": {"lat": 40.916869, "lon": -72.662419},
    "ROCHESTER": {"lat": 43.255075, "lon": -77.608612},
    "ROCKPORT": {"lat": 28.020573, "lon": -97.054434},
    "ROSEDALE": {"lat": 33.855100, "lon": -91.026611},
    "ROTA HARBOR": {"lat": 0.000000, "lon": 0.000000},
    "SABINE": {"lat": 31.332549, "lon": -93.872222},
    "SABINE BAR": {"lat": 47.666453, "lon": -122.383505},
    "SACKETS HARBOR": {"lat": 43.946171, "lon": -76.119093},
    "SACRAMENTO RIVER": {"lat": 39.661909, "lon": -121.997373},
    "SAGINAW": {"lat": 43.420039, "lon": -83.949037},
    "SAIPAN": {"lat": 13.556753, "lon": 144.921153},
    "SALEM": {"lat": 40.821560, "lon": -73.681487},
    "SALISBURY": {"lat": 38.366027, "lon": -75.600996},
    "SALLISAW": {"lat": 0.000000, "lon": 0.000000},
    "SAN DIEGO": {"lat": 32.620481, "lon": -117.133254},
    "SAN FRANCISCO BAY": {"lat": 37.714029, "lon": -122.307794},
    "SAN JOAQUIN RIVER": {"lat": 37.112977, "lon": -120.590078},
    "SAN PABLO BAY": {"lat": 38.047532, "lon": -122.382798},
    "SAN PABLO STRAIT": {"lat": 37.975314, "lon": -122.441146},
    "SAND KEY": {"lat": 24.455536, "lon": -81.877691},
    "SAND POINT": {"lat": 55.340583, "lon": -160.497852},
    "SANTA BARBARA": {"lat": 34.422132, "lon": -119.702667},
    "SANTA CRUZ HARBOR": {"lat": 36.982146, "lon": -121.989995},
    "SANTA CRUZ ISLAND": {"lat": 34.018464, "lon": -119.775101},
    "SANTA ROSA ISLAND": {"lat": 33.965795, "lon": -120.091897},
    "SARASOTA": {"lat": 27.336581, "lon": -82.530855},
    "SAVANNAH": {"lat": 32.079007, "lon": -81.092134},
    "SEAPORT MANATEE": {"lat": 0.000000, "lon": 0.000000},
    "SEARSPORT, ME": {"lat": 44.458671, "lon": -68.925313},
    "SEATTLE": {"lat": 47.657156, "lon": -122.379783},
    "SELDOVIA": {"lat": 59.439206, "lon": -151.713909},
    "SEWARD": {"lat": 60.101395, "lon": -149.440428},
    "SHALLOTTE INLET": {"lat": 33.912678, "lon": -78.379681},
    "SHREVEPORT BOSSIER CITY": {"lat": 0.000000, "lon": 0.000000},
    "SILVER BAY, MN": {"lat": 47.294297, "lon": -91.257371},
    "SMACKOVER": {"lat": 0.000000, "lon": 0.000000},
    "SOUTH PASS LIGHT": {"lat": 29.015270, "lon": -89.166871},
    "ST CROIX, CHRISTIANSTED": {"lat": 17.745594, "lon": -64.697340},
    "ST CROIX, FREDERIKSTED": {"lat": 17.729124, "lon": -64.758916},
    "ST CROIX, KRAUSE LAGOON": {"lat": 0.000000, "lon": 0.000000},
    "ST CROIX, LIMETREE BAY": {"lat": 0.000000, "lon": 0.000000},
    "ST GEORGE": {"lat": 56.602288, "lon": -169.544527},
    "ST JOHN, CRUZ BAY": {"lat": 18.335601, "lon": -64.755041},
    "ST JOHN, ENIGHED POND": {"lat": 0.000000, "lon": 0.000000},
    "ST PAUL": {"lat": 57.122225, "lon": -170.275003},
    "ST PETERSBURG": {"lat": 27.761982, "lon": -82.630828},
    "ST THOMAS, CHARLOTTE AMALIE HARBOR": {"lat": 0.000000, "lon": 0.000000},
    "ST THOMAS, EAST GREGGERIE CHANNEL": {"lat": 0.000000, "lon": 0.000000},
    "ST THOMAS, RED HOOK BAY": {"lat": 0.000000, "lon": 0.000000},
    "ST THOMAS, WEST GREGGERIE CHANNEL": {"lat": 0.000000, "lon": 0.000000},
    "ST. CLAIR RIVER": {"lat": 42.987947, "lon": -82.425341},
    "ST. JOSEPH, MI": {"lat": 41.903196, "lon": -85.535673},
    "STAMFORD": {"lat": 41.053430, "lon": -73.538734},
    "STURGEON BAY, WI": {"lat": 44.834164, "lon": -87.377042},
    "SUISUN BAY (& FACILITIES)": {"lat": 0.000000, "lon": 0.000000},
    "SUPERIOR, WI": {"lat": 46.789548, "lon": -90.854271},
    "SWPASS LIGHTERING AREA": {"lat": 0.000000, "lon": 0.000000},
    "Soo Locks - MacArthur": {"lat": 0.000000, "lon": 0.000000},
    "Soo Locks-Poe": {"lat": 0.000000, "lon": 0.000000},
    "Southern Coast Ports (Tillamook to CA/OR border)": {"lat": 0.000000, "lon": 0.000000},
    "St Marys River- Pipe Island Passage": {"lat": 0.000000, "lon": 0.000000},
    "St Marys River-Little Rapids Cut": {"lat": 0.000000, "lon": 0.000000},
    "St Marys River-Middle Neebish Channel": {"lat": 0.000000, "lon": 0.000000},
    "St Marys River-West Neebish Channel": {"lat": 0.000000, "lon": 0.000000},
    "Straits of Mackinac (Mack Island to St. Ignace)": {"lat": 0.000000, "lon": 0.000000},
    "Straits of Mackinac-South Channel": {"lat": 0.000000, "lon": 0.000000},
    "TACOMA": {"lat": 47.266240, "lon": -122.397272},
    "TACONITE HARBOR, MN": {"lat": 47.521071, "lon": -90.930339},
    "TAMPA": {"lat": 27.928686, "lon": -82.438622},
    "TATITLEK": {"lat": 60.884975, "lon": -146.680949},
    "TENTH AVENUE": {"lat": 32.702525, "lon": -117.156171},
    "TEXAS CITY": {"lat": 26.367241, "lon": -98.801452},
    "TINIAN": {"lat": 13.533741, "lon": 144.879029},
    "TOGIAK": {"lat": 59.061944, "lon": -160.376389},
    "TOMALES BAY": {"lat": 38.169643, "lon": -122.909996},
    "TONAWANDA": {"lat": 43.020679, "lon": -78.878383},
    "TWO HARBORS, MN": {"lat": 47.025714, "lon": -91.673052},
    "Upper Columbia River and Snake River (from Bonneville Navigation Lock to Lewiston, ID)": {"lat": 0.000000, "lon": 0.000000},
    "Upper Mississippi River - Pool 02 Hastings (MM 815.2 - 847.5)": {"lat": 42.498115, "lon": -90.654240},
    "Upper Mississippi River - Pool 03 Red Wing (MM 796.9 - 815.1)": {"lat": 42.498115, "lon": -90.654240},
    "Upper Mississippi River - Pool 04 Alma (MM 752.8 - 769.8)": {"lat": 42.498115, "lon": -90.654240},
    "Upper Mississippi River - Pool 05 Minnesota City (MM 738.1 - 752.7)": {"lat": 42.498115, "lon": -90.654240},
    "Upper Mississippi River - Pool 05a Winona (MM 728.6 - 738)": {"lat": 42.498115, "lon": -90.654240},
    "Upper Mississippi River - Pool 06 Trempeleau (MM 714.3 - 728.5)": {"lat": 42.498115, "lon": -90.654240},
    "Upper Mississippi River - Pool 07 La Crescent (MM 702.5 - 714.2)": {"lat": 42.498115, "lon": -90.654240},
    "Upper Mississippi River - Pool 08 Genoa (MM 679.2 - 702.4)": {"lat": 42.498115, "lon": -90.654240},
    "Upper Mississippi River - Pool 09 Lynxville (MM 647.9 - 679.1)": {"lat": 42.498115, "lon": -90.654240},
    "Upper Mississippi River - Pool 10 Guttenburg (MM 615.1 - 647.8)": {"lat": 42.498115, "lon": -90.654240},
    "Upper Mississippi River - Pool 11 Dubuque (MM 583 - 615)": {"lat": 42.498115, "lon": -90.654240},
    "Upper Mississippi River - Pool 12 Bellevue (MM 556.7 - 582.9)": {"lat": 42.498115, "lon": -90.654240},
    "Upper Mississippi River - Pool 13 Fulton (MM 522.4 - 556.6)": {"lat": 42.498115, "lon": -90.654240},
    "Upper Mississippi River - Pool 14 LeClaire (MM 493.3 - 522.3)": {"lat": 42.498115, "lon": -90.654240},
    "Upper Mississippi River - Pool 15 Rock Island (MM 482.9 - 493.2)": {"lat": 42.498115, "lon": -90.654240},
    "Upper Mississippi River - Pool 16 Muscatine (457.2 - 482.8)": {"lat": 42.498115, "lon": -90.654240},
    "Upper Mississippi River - Pool 17 New Boston (MM 437.1 - 457.1)": {"lat": 42.498115, "lon": -90.654240},
    "Upper Mississippi River - Pool 18 Gladstone (MM 410.5 - 437)": {"lat": 42.498115, "lon": -90.654240},
    "Upper Mississippi River - Pool 19 Keokuk (MM 364.2 - 410.4)": {"lat": 42.498115, "lon": -90.654240},
    "Upper Mississippi River - Pool 20 Canton (MM 343.2 - 364.1)": {"lat": 42.498115, "lon": -90.654240},
    "Upper Mississippi River - Pool 21 Quincy (MM 324.9 - 343.1)": {"lat": 42.498115, "lon": -90.654240},
    "Upper Mississippi River - Pool 22 Saverton (MM 301.2 - 324.8)": {"lat": 42.498115, "lon": -90.654240},
    "Upper Mississippi River - Pool 24 Clarksville (MM 273.4 - 301.1)": {"lat": 42.498115, "lon": -90.654240},
    "Upper Mississippi River - Pool 25 Winfield (MM 241.4 - 273.3)": {"lat": 42.498115, "lon": -90.654240},
    "Upper Mississippi River - Pool 26 Alton (MM 200.5 - 241.3)": {"lat": 42.498115, "lon": -90.654240},
    "Upper Mississippi River - Pool 27 St. Lous (MM 185.5 - 200.4)": {"lat": 42.498115, "lon": -90.654240},
    "Upper Mississippi River - St. Louis Harbor (MM 179 - 184)": {"lat": 42.498115, "lon": -90.654240},
    "Upper Mississippi River - Zone 28 Port of St. Louis (MM 160.1 - 185.4)": {"lat": 42.498115, "lon": -90.654240},
    "Upper Mississippi River - Zone 29 Chester to Meramec River (MM 109.9 - 160.0)": {"lat": 42.498115, "lon": -90.654240},
    "VALDEZ ARM": {"lat": 60.973611, "lon": -146.798611},
    "VALDEZ NARROWS": {"lat": 0.000000, "lon": 0.000000},
    "VAN BUREN": {"lat": 34.191773, "lon": -88.411434},
    "VENTURA": {"lat": 34.169946, "lon": -119.195897},
    "VERMILION": {"lat": 40.174981, "lon": -87.732386},
    "VICKSBURG": {"lat": 32.389377, "lon": -90.886527},
    "VTS GOLDEN GATE MAIN SHIP CHANNEL": {"lat": 0.000000, "lon": 0.000000},
    "VTS MAIN TRAFFIC LANES": {"lat": 0.000000, "lon": 0.000000},
    "VTS NORTH TRAFFIC LANES": {"lat": 0.000000, "lon": 0.000000},
    "VTS PILOT STATION PRECAUTIONARY AREA": {"lat": 0.000000, "lon": 0.000000},
    "VTS SOUTH TRAFFIC LANES": {"lat": 0.000000, "lon": 0.000000},
    "WAINWRIGHT": {"lat": 70.636944, "lon": -160.038333},
    "WASHINGTON": {"lat": 39.589350, "lon": -77.710254},
    "WAUKEGAN, IL": {"lat": 42.360227, "lon": -87.831816},
    "WEBBERS FALLS": {"lat": 0.000000, "lon": 0.000000},
    "WEEDON ISLAND": {"lat": 27.845303, "lon": -82.601487},
    "WEST MEMPHIS": {"lat": 35.142035, "lon": -90.135093},
    "WESTERN LAKE ERIE": {"lat": 42.873401, "lon": -78.875657},
    "WHITTIER": {"lat": 60.782278, "lon": -148.720719},
    "Whitefish Bay": {"lat": 43.127650, "lon": -87.912991},
    "YORKTOWN - CHEATHAM ANNEX - WEST POINT": {"lat": 37.235666, "lon": -76.513649},
}
