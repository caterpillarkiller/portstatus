"""
Main update script — orchestrates:
    1. Scrape NAVCEN (zones + sub-ports)
    2. Store everything in SQLite
    3. Generate the two-layer GeoJSON that the map reads
"""

import json, sys
from datetime import datetime, timezone
from database import PortStatusDB
from scraper import NAVCENScraper, COTP_COORDINATES, worst_status


# ---------------------------------------------------------------------------
# GeoJSON generator
# ---------------------------------------------------------------------------
def generate_geojson():
    """
    Reads the database and writes api/ports.geojson with TWO layers of features:

      • One feature per COTP zone   (properties.type == "cotp_zone")
            – condition = worst status among its sub-ports
            – sub_ports array embedded so the popup can list them

      • One feature per sub-port    (properties.type == "sub_port")
            – condition = that sub-port's own status
            – comments, last_changed, parent zone name
    """
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    with PortStatusDB() as db:
        zones     = db.get_all_zones()
        all_subs  = db.get_all_subports()

    # ----- group sub-ports by zone_id for quick lookup -----
    subs_by_zone: dict = {}
    for sp in all_subs:
        subs_by_zone.setdefault(sp["zone_id"], []).append(sp)

    features = []

    # ----- COTP zone features -----
    for z in zones:
        zone_id   = z["zone_id"]
        sub_list  = subs_by_zone.get(zone_id, [])

        # Derive zone condition = worst of all sub-ports (fall back to recorded zone_condition)
        sub_statuses = [sp["condition"] for sp in sub_list if sp.get("condition")]
        if sub_statuses:
            zone_condition = worst_status(sub_statuses)
        else:
            zone_condition = z.get("zone_condition") or "NORMAL"

        # Find the most recent sub-port update time for "last updated"
        sub_timestamps = [sp["recorded_at"] for sp in sub_list if sp.get("recorded_at")]
        last_updated = max(sub_timestamps) if sub_timestamps else (z.get("recorded_at") or now_utc)

        # Embed a summary of sub-ports so the popup can show them without a second fetch
        sub_summary = []
        for sp in sub_list:
            sub_summary.append({
                "name":         sp["port_name"],
                "condition":    sp.get("condition") or "NORMAL",
                "comments":     sp.get("comments") or "",
                "last_changed": sp.get("last_changed") or "",
            })

        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [z["longitude"], z["latitude"]]
            },
            "properties": {
                "type":          "cotp_zone",
                "name":          z["zone_name"],
                "condition":     zone_condition,
                "marsec_level":  z.get("marsec_level") or "MARSEC 1",
                "sector_info":   z.get("sector_info") or "",
                "source_url":    z.get("source_url") or "",
                "lastUpdated":   last_updated,
                "nextUpdate":    "",          # filled by frontend based on scrape schedule
                "sub_ports":     sub_summary
            }
        })

    # ----- Sub-port features -----
    for sp in all_subs:
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [sp["longitude"], sp["latitude"]]
            },
            "properties": {
                "type":          "sub_port",
                "name":          sp["port_name"],
                "zone_name":     sp["zone_name"],
                "condition":     sp.get("condition") or "NORMAL",
                "comments":      sp.get("comments") or "",
                "last_changed":  sp.get("last_changed") or "",
                "lastUpdated":   sp.get("recorded_at") or now_utc,
                "nextUpdate":    ""
            }
        })

    geojson = {"type": "FeatureCollection", "features": features}

    import os
    os.makedirs("api", exist_ok=True)
    with open("api/ports.geojson", "w", encoding="utf-8") as f:
        json.dump(geojson, f, indent=2, ensure_ascii=False)

    zone_count = len([f for f in features if f["properties"]["type"] == "cotp_zone"])
    sub_count  = len([f for f in features if f["properties"]["type"] == "sub_port"])
    print(f"✅ Generated api/ports.geojson — {zone_count} zones, {sub_count} sub-ports")


# ---------------------------------------------------------------------------
# main update flow
# ---------------------------------------------------------------------------
def update_ports():
    print("=" * 60)
    print("USCG Port Status Update  (hierarchical)")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60 + "\n")

    # 1 — scrape
    print("📡 Step 1: Scraping NAVCEN …")
    scraper = NAVCENScraper()
    zones_data = scraper.scrape_all_zones()

    if not zones_data:
        print("❌ No data scraped.  Attempting GeoJSON from existing DB …")
        generate_geojson()
        return

    print(f"✅ Scraped {len(zones_data)} zones\n")

    # 2 — store
    print("💾 Step 2: Updating database …")
    with PortStatusDB() as db:
        for zd in zones_data:
            zone_name = zd["zone_name"]
            parent_coords = COTP_COORDINATES.get(zone_name, {"lat": 39.8283, "lon": -98.5795})

            zone_id = db.upsert_zone(
                zone_name    = zone_name,
                lat          = parent_coords["lat"],
                lon          = parent_coords["lon"],
                marsec_level = zd.get("marsec_level", ""),
                sector_info  = zd.get("sector_info", ""),
                source_url   = zd.get("source_url", ""),
            )

            # Compute zone-level condition (worst sub-port) and record it
            sub_statuses = [sp["status"] for sp in zd["sub_ports"]]
            zone_cond    = worst_status(sub_statuses) if sub_statuses else "NORMAL"
            db.record_zone_status(zone_id, zone_cond, zd.get("marsec_level", ""))

            # Record each sub-port
            for sp in zd["sub_ports"]:
                subport_id = db.upsert_subport(
                    zone_id   = zone_id,
                    port_name = sp["name"],
                    lat       = sp["latitude"],
                    lon       = sp["longitude"],
                )
                db.record_subport_status(
                    zone_id      = zone_id,
                    subport_id   = subport_id,
                    condition    = sp["status"],
                    comments     = sp.get("comments", ""),
                    last_changed = sp.get("last_changed", ""),
                )

    print("✅ Database updated\n")

    # 3 — GeoJSON
    print("🗺️  Step 3: Generating GeoJSON …")
    generate_geojson()

    print("\n" + "=" * 60)
    print(f"✅ Update complete: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)


# ---------------------------------------------------------------------------
# quick smoke-test mode
# ---------------------------------------------------------------------------
def test_update():
    """Populate DB with fake data so you can test the map without network."""
    print("🧪 Running test update …\n")

    fake_zones = [
        {
            "zone_name": "CHARLESTON",
            "marsec_level": "MARSEC 1",
            "sector_info": "SECTOR CHARLESTON (07-37090)",
            "source_url": "https://www.navcen.uscg.gov/port-status?zone=CHARLESTON",
            "sub_ports": [
                {"name": "CHARLESTON",     "status": "NORMAL",  "comments": "",                           "last_changed": "2026-02-02", "latitude": 32.7765, "longitude": -79.9253},
                {"name": "GEORGETOWN",     "status": "WHISKEY", "comments": "Fog advisory in effect",    "last_changed": "2026-02-02", "latitude": 33.3766, "longitude": -79.2945},
                {"name": "BEAUFORT",       "status": "NORMAL",  "comments": "",                           "last_changed": "2026-02-02", "latitude": 32.3539, "longitude": -80.6703},
                {"name": "HILTON HEAD",    "status": "NORMAL",  "comments": "",                           "last_changed": "2026-02-02", "latitude": 32.1440, "longitude": -80.8431},
                {"name": "MYRTLE BEACH",   "status": "NORMAL",  "comments": "",                           "last_changed": "2026-02-02", "latitude": 33.6946, "longitude": -78.8910},
            ]
        },
        {
            "zone_name": "MIAMI",
            "marsec_level": "MARSEC 1",
            "sector_info": "SECTOR MIAMI",
            "source_url": "https://www.navcen.uscg.gov/port-status?zone=MIAMI",
            "sub_ports": [
                {"name": "MIAMI",              "status": "NORMAL",  "comments": "PORTCON V",                                          "last_changed": "2026-02-01", "latitude": 25.7617, "longitude": -80.1918},
                {"name": "PORT EVERGLADES",    "status": "NORMAL",  "comments": "PORTCON V",                                          "last_changed": "2026-02-01", "latitude": 26.0874, "longitude": -80.1100},
                {"name": "FORT PIERCE",        "status": "X-RAY",   "comments": "WITH RESTRICTIONS - Port Condition IV MSIB22-029",  "last_changed": "2026-02-01", "latitude": 27.1002, "longitude": -80.1293},
                {"name": "PORT OF PALM BEACH", "status": "NORMAL",  "comments": "PORTCON V",                                          "last_changed": "2026-02-01", "latitude": 26.7315, "longitude": -80.0364},
            ]
        },
        {
            "zone_name": "HOUSTON-GALVESTON",
            "marsec_level": "MARSEC 1",
            "sector_info": "SECTOR HOUSTON-GALVESTON (08-37170)",
            "source_url": "https://www.navcen.uscg.gov/port-status?zone=HOUSTON-GALVESTON",
            "sub_ports": [
                {"name": "HOUSTON",     "status": "NORMAL",  "comments": "SEE MSIB 31-24",                          "last_changed": "2025-09-11", "latitude": 29.7604, "longitude": -95.3698},
                {"name": "GALVESTON",   "status": "WHISKEY", "comments": "WITH RESTRICTIONS - SEE MSIB 34-24",      "last_changed": "2024-12-15", "latitude": 29.3013, "longitude": -94.8177},
                {"name": "TEXAS CITY",  "status": "NORMAL",  "comments": "SEE MSIB 31-24",                          "last_changed": "2025-09-11", "latitude": 29.4170, "longitude": -94.9030},
                {"name": "FREEPORT",    "status": "ZULU",    "comments": "CLOSED - storm damage — next update 0600 local 2026-02-03", "last_changed": "2026-02-02", "latitude": 28.5420, "longitude": -95.1170},
            ]
        },
        {
            "zone_name": "NEW YORK",
            "marsec_level": "MARSEC 1",
            "sector_info": "SECTOR NEW YORK",
            "source_url": "https://www.navcen.uscg.gov/port-status?zone=NEW YORK",
            "sub_ports": [
                {"name": "NEW YORK",     "status": "NORMAL", "comments": "", "last_changed": "2026-02-01", "latitude": 40.6892, "longitude": -74.0445},
                {"name": "BROOKLYN",     "status": "NORMAL", "comments": "", "last_changed": "2026-02-01", "latitude": 40.6782, "longitude": -73.9442},
            ]
        },
    ]

    with PortStatusDB() as db:
        for zd in fake_zones:
            zone_name = zd["zone_name"]
            parent_coords = COTP_COORDINATES.get(zone_name, {"lat": 39.8283, "lon": -98.5795})
            zone_id = db.upsert_zone(zone_name, parent_coords["lat"], parent_coords["lon"],
                                     zd["marsec_level"], zd["sector_info"], zd["source_url"])

            sub_statuses = [sp["status"] for sp in zd["sub_ports"]]
            db.record_zone_status(zone_id, worst_status(sub_statuses), zd["marsec_level"])

            for sp in zd["sub_ports"]:
                subport_id = db.upsert_subport(zone_id, sp["name"], sp["latitude"], sp["longitude"])
                db.record_subport_status(zone_id, subport_id, sp["status"], sp["comments"], sp["last_changed"])

    generate_geojson()
    print("\n✅ Test update complete — open the map to verify!")


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if "--test" in sys.argv:
        test_update()
    else:
        update_ports()