#!/usr/bin/env python3
"""
Automated Port Geocoding Script

This script automatically finds latitude/longitude coordinates for all ports
in your ports.geojson file using the Nominatim geocoding service (OpenStreetMap).

It's FREE, doesn't require an API key, and works pretty well for ports!

Usage:
    python3 auto_geocode_ports.py --dry-run    # Preview what will be found
    python3 auto_geocode_ports.py              # Actually update scraper.py
    python3 auto_geocode_ports.py --merge      # Only geocode missing ports, keep existing
"""

import json
import time
import re
from typing import Dict, Optional, Tuple
from urllib.request import urlopen, Request
from urllib.parse import quote
from datetime import datetime

# Rate limiting - Nominatim requires 1 request per second
DELAY_BETWEEN_REQUESTS = 1.1

# User agent is required by Nominatim
USER_AGENT = "USCG-Port-Status-Monitor/1.0"

# State/territory mapping for better geocoding
STATE_TERRITORY_MAP = {
    'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas',
    'CA': 'California', 'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware',
    'FL': 'Florida', 'GA': 'Georgia', 'HI': 'Hawaii', 'ID': 'Idaho',
    'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa', 'KS': 'Kansas',
    'KY': 'Kentucky', 'LA': 'Louisiana', 'ME': 'Maine', 'MD': 'Maryland',
    'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota', 'MS': 'Mississippi',
    'MO': 'Missouri', 'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada',
    'NH': 'New Hampshire', 'NJ': 'New Jersey', 'NM': 'New Mexico', 'NY': 'New York',
    'NC': 'North Carolina', 'ND': 'North Dakota', 'OH': 'Ohio', 'OK': 'Oklahoma',
    'OR': 'Oregon', 'PA': 'Pennsylvania', 'RI': 'Rhode Island', 'SC': 'South Carolina',
    'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah',
    'VT': 'Vermont', 'VA': 'Virginia', 'WA': 'Washington', 'WV': 'West Virginia',
    'WI': 'Wisconsin', 'WY': 'Wyoming',
    'PR': 'Puerto Rico', 'VI': 'Virgin Islands', 'GU': 'Guam', 'AS': 'American Samoa'
}

# Common nautical abbreviations
NAUTICAL_ABBREVIATIONS = {
    'ICW': 'Intracoastal Waterway',
    'AICW': 'Atlantic Intracoastal Waterway',
    'GICW': 'Gulf Intracoastal Waterway',
    'COTP': 'Captain of the Port',
    'USCG': 'US Coast Guard',
}


def load_ports_from_geojson() -> list:
    """Load all unique sub-ports from the current GeoJSON."""
    print("📖 Loading ports from api/ports.geojson...")
    
    try:
        with open('api/ports.geojson', 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print("❌ Error: api/ports.geojson not found!")
        print("   Make sure you're running this from your project root folder.")
        return []
    
    ports = []
    seen = set()
    
    for feature in data['features']:
        if feature['properties'].get('type') == 'sub_port':
            zone = feature['properties'].get('zone_name', '')
            port = feature['properties']['name']
            
            # Create unique key
            key = (zone, port)
            if key not in seen:
                seen.add(key)
                ports.append({
                    'zone': zone,
                    'name': port,
                    'current_coords': feature['geometry']['coordinates']
                })
    
    print(f"✅ Found {len(ports)} unique ports")
    return ports


def extract_state_from_port_name(port_name: str) -> Tuple[str, Optional[str]]:
    """
    Extract state/territory code from port name.
    Returns (cleaned_name, state_code)
    
    Examples:
        "CHICAGO, IL" -> ("CHICAGO", "IL")
        "PR, SAN JUAN" -> ("SAN JUAN", "PR")
        "MIAMI" -> ("MIAMI", None)
    """
    # Pattern 1: State at end like "CHICAGO, IL"
    match = re.search(r',\s*([A-Z]{2})$', port_name)
    if match:
        state_code = match.group(1)
        if state_code in STATE_TERRITORY_MAP:
            cleaned = port_name[:match.start()].strip()
            return (cleaned, state_code)
    
    # Pattern 2: State at start like "PR, SAN JUAN" or "VI, ST THOMAS"
    match = re.match(r'^([A-Z]{2}),\s*(.+)$', port_name)
    if match:
        state_code = match.group(1)
        if state_code in STATE_TERRITORY_MAP:
            cleaned = match.group(2).strip()
            return (cleaned, state_code)
    
    # Pattern 3: Check zone name for state hints
    # This would need zone_name passed in, handle separately
    
    return (port_name, None)


def clean_port_name(port_name: str, zone_name: str) -> Tuple[str, Optional[str]]:
    """
    Clean up port name and extract state for better geocoding results.
    Returns (cleaned_name, state_code)
    """
    # First extract any state codes
    name, state_code = extract_state_from_port_name(port_name)
    
    # If no state found in port name, try to infer from zone
    if not state_code:
        for code, full_name in STATE_TERRITORY_MAP.items():
            if full_name.upper() in zone_name.upper():
                state_code = code
                break
    
    # Expand abbreviations
    for abbr, expansion in NAUTICAL_ABBREVIATIONS.items():
        # Match whole word only
        name = re.sub(r'\b' + abbr + r'\b', expansion, name)
    
    # Common replacements for better results
    replacements = {
        'ST CROIX': 'Saint Croix',
        'ST THOMAS': 'Saint Thomas',
        'ST JOHN': 'Saint John',
        'ST ': 'Saint ',
        'MT ': 'Mount ',
        'PT ': 'Point ',
        'FT ': 'Fort ',
    }
    
    for old, new in replacements.items():
        if name.startswith(old):
            name = new + name[len(old):]
        else:
            name = name.replace(' ' + old, ' ' + new)
    
    return (name.strip(), state_code)


def build_search_query(port_name: str, zone_name: str) -> list:
    """
    Build multiple search queries to try, in order of specificity.
    This helps us find the port even if the exact name doesn't match.
    """
    clean_name, state_code = clean_port_name(port_name, zone_name)
    
    queries = []
    state_name = STATE_TERRITORY_MAP.get(state_code, '') if state_code else ''
    
    # If we have a state, use it prominently
    if state_name:
        # Try 1: Port name with state
        if not clean_name.lower().startswith('port'):
            queries.append(f"Port of {clean_name}, {state_name}, United States")
        queries.append(f"{clean_name}, {state_name}, United States")
        
        # Try 2: With harbor
        if 'harbor' not in clean_name.lower() and 'harbour' not in clean_name.lower():
            queries.append(f"{clean_name} Harbor, {state_name}, United States")
        
        # Try 3: Just city and state (for ports named after cities)
        if '-' in clean_name:
            main_city = clean_name.split('-')[0].strip()
            queries.append(f"{main_city}, {state_name}, United States")
    else:
        # No state - use generic searches (less accurate)
        # Try 1: Port name with "Port" prefix
        if not clean_name.lower().startswith('port'):
            queries.append(f"Port of {clean_name}, United States")
        
        # Try 2: Exact name
        queries.append(f"{clean_name}, United States")
        
        # Try 3: Just the main city name (for ports like "HOUSTON-GALVESTON")
        if '-' in clean_name:
            main_city = clean_name.split('-')[0].strip()
            queries.append(f"Port of {main_city}, United States")
        
        # Try 4: Add "harbor" or "harbor entrance"
        if 'harbor' not in clean_name.lower():
            queries.append(f"{clean_name} Harbor, United States")
    
    return queries


def geocode_location(search_query: str) -> Optional[Tuple[float, float]]:
    """
    Use Nominatim (OpenStreetMap) to find coordinates for a location.
    Returns (latitude, longitude) or None if not found.
    """
    encoded_query = quote(search_query)
    url = f"https://nominatim.openstreetmap.org/search?q={encoded_query}&format=json&limit=1"
    
    try:
        req = Request(url, headers={'User-Agent': USER_AGENT})
        response = urlopen(req, timeout=10)
        data = json.loads(response.read().decode())
        
        if data and len(data) > 0:
            lat = float(data[0]['lat'])
            lon = float(data[0]['lon'])
            return (lat, lon)
        
        return None
    
    except Exception as e:
        print(f"   ⚠️  Geocoding error: {e}")
        return None


def geocode_port(port: dict) -> Optional[Tuple[float, float]]:
    """
    Try multiple queries to geocode a port.
    Returns (latitude, longitude) or None.
    """
    queries = build_search_query(port['name'], port['zone'])
    
    for i, query in enumerate(queries):
        if i > 0:
            # Only show trying message for fallback attempts
            print(f"   🔄 Trying alternate query: \"{query}\"")
        
        coords = geocode_location(query)
        
        if coords:
            return coords
        
        # Rate limiting
        time.sleep(DELAY_BETWEEN_REQUESTS)
    
    return None


def load_existing_coordinates() -> Dict[str, dict]:
    """
    Load existing PORT_COORDINATES from scraper.py.
    Returns empty dict if not found or file doesn't exist.
    """
    try:
        with open('scraper.py', 'r') as f:
            content = f.read()
        
        # Find PORT_COORDINATES dictionary
        pattern = r'PORT_COORDINATES\s*=\s*\{([^}]+)\}'
        match = re.search(pattern, content, re.DOTALL)
        
        if not match:
            return {}
        
        # Parse the dictionary manually (safer than eval)
        coords_text = match.group(1)
        coordinates = {}
        
        # Match each line like: "PORT NAME": {"lat": 25.7617, "lon": -80.1918}
        line_pattern = r'"([^"]+)":\s*\{\s*"lat":\s*([-\d.]+),\s*"lon":\s*([-\d.]+)'
        
        for match in re.finditer(line_pattern, coords_text):
            port_name = match.group(1)
            lat = float(match.group(2))
            lon = float(match.group(3))
            coordinates[port_name] = {"lat": lat, "lon": lon}
        
        return coordinates
    
    except FileNotFoundError:
        return {}
    except Exception as e:
        print(f"⚠️  Warning: Could not load existing coordinates: {e}")
        return {}


def geocode_all_ports(ports: list, dry_run: bool = False, existing_coords: Dict = None) -> Dict[str, dict]:
    """
    Geocode all ports and return a dictionary ready for PORT_COORDINATES.
    
    Args:
        ports: List of port dictionaries
        dry_run: If True, don't modify files
        existing_coords: Existing coordinates to preserve (for merge mode)
    
    Returns:
        Dict like: {"PORT NAME": {"lat": 25.7617, "lon": -80.1918}}
    """
    print()
    print("=" * 70)
    print("🌍 STARTING AUTOMATED GEOCODING")
    print("=" * 70)
    print()
    
    if dry_run:
        print("🔍 DRY RUN MODE - Will not modify any files")
        print()
    
    if existing_coords:
        print(f"🔄 MERGE MODE - Preserving {len(existing_coords)} existing coordinates")
        print()
    
    coordinates = existing_coords.copy() if existing_coords else {}
    successful = 0
    failed = []
    skipped = 0
    
    # Create log file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"geocoding_log_{timestamp}.txt"
    log_file = open(log_filename, 'w')
    
    log_file.write("=" * 70 + "\n")
    log_file.write("USCG PORT GEOCODING LOG\n")
    log_file.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    log_file.write("=" * 70 + "\n\n")
    
    total = len(ports)
    
    for idx, port in enumerate(ports, 1):
        port_name = port['name']
        zone_name = port['zone']
        
        # Skip if already have coordinates (merge mode)
        if port_name in coordinates:
            if existing_coords and port_name in existing_coords:
                skipped += 1
                continue
        
        print(f"[{idx}/{total}] 🔍 Geocoding: {port_name} ({zone_name})")
        log_file.write(f"[{idx}/{total}] Port: {port_name} (Zone: {zone_name})\n")
        
        coords = geocode_port(port)
        
        if coords:
            lat, lon = coords
            coordinates[port_name] = {"lat": lat, "lon": lon}
            print(f"   ✅ Found: {lat:.4f}, {lon:.4f}")
            log_file.write(f"   ✅ SUCCESS: {lat:.6f}, {lon:.6f}\n")
            successful += 1
        else:
            print(f"   ❌ Could not find coordinates")
            log_file.write(f"   ❌ FAILED: No coordinates found\n")
            failed.append({
                'name': port_name,
                'zone': zone_name
            })
            
            # Add placeholder coordinates in the MIDDLE OF THE OCEAN
            # This makes failed geocodes obvious on the map
            coordinates[port_name] = {
                "lat": 0.0,
                "lon": 0.0,
                "needs_manual_fix": True
            }
        
        log_file.write("\n")
        print()
    
    # Write summary to log
    log_file.write("\n" + "=" * 70 + "\n")
    log_file.write("SUMMARY\n")
    log_file.write("=" * 70 + "\n")
    log_file.write(f"Total ports: {total}\n")
    log_file.write(f"Successful: {successful}\n")
    log_file.write(f"Failed: {len(failed)}\n")
    if existing_coords:
        log_file.write(f"Skipped (already had coords): {skipped}\n")
    log_file.write("\n")
    
    if failed:
        log_file.write("=" * 70 + "\n")
        log_file.write("PORTS NEEDING MANUAL COORDINATES\n")
        log_file.write("=" * 70 + "\n\n")
        log_file.write("Copy these into scraper.py and add real coordinates:\n\n")
        for item in failed:
            log_file.write(f'    "{item["name"]}": {{"lat": 0.0, "lon": 0.0}},  # FIXME: {item["zone"]}\n')
        log_file.write("\n")
        log_file.write("💡 These ports will show at 0°N, 0°E (middle of Atlantic Ocean)\n")
        log_file.write("   Look for dots off the coast of Africa to find them!\n")
    
    log_file.close()
    
    print("=" * 70)
    print("📊 GEOCODING SUMMARY")
    print("=" * 70)
    print(f"✅ Successful: {successful}/{total}")
    print(f"❌ Failed: {len(failed)}/{total}")
    if existing_coords:
        print(f"⏭️  Skipped (already geocoded): {skipped}/{total}")
    print()
    print(f"📄 Full log saved to: {log_filename}")
    
    if failed:
        print()
        print("⚠️  Ports that need manual coordinates (showing first 15):")
        for item in failed[:15]:
            print(f"   - {item['name']} ({item['zone']})")
        if len(failed) > 15:
            print(f"   ... and {len(failed) - 15} more (see {log_filename})")
        print()
        print("🌍 Failed ports will appear at 0°N, 0°E on your map")
        print("   (In the Atlantic Ocean off the coast of Africa)")
        print("   This makes them easy to spot and fix!")
    
    print()
    
    return coordinates


def update_scraper_file(coordinates: Dict[str, dict], dry_run: bool = False):
    """
    Update scraper.py with the new PORT_COORDINATES dictionary.
    """
    if dry_run:
        print("=" * 70)
        print("📝 PREVIEW: Here's what would be added to scraper.py:")
        print("=" * 70)
        print()
        print("PORT_COORDINATES = {")
        for port_name in sorted(list(coordinates.keys())[:10]):  # Show first 10
            coord = coordinates[port_name]
            print(f'    "{port_name}": {{"lat": {coord["lat"]:.4f}, "lon": {coord["lon"]:.4f}}},')
        if len(coordinates) > 10:
            print(f"    # ... and {len(coordinates) - 10} more ports")
        print("}")
        print()
        print("💡 Run without --dry-run to actually update scraper.py")
        return
    
    print("=" * 70)
    print("📝 UPDATING scraper.py")
    print("=" * 70)
    
    try:
        with open('scraper.py', 'r') as f:
            content = f.read()
    except FileNotFoundError:
        print("❌ Error: scraper.py not found!")
        print("   Make sure you're running this from your project root folder.")
        return
    
    # Build the new PORT_COORDINATES dictionary
    coord_lines = ["PORT_COORDINATES = {"]
    for port_name in sorted(coordinates.keys()):
        coord = coordinates[port_name]
        coord_lines.append(f'    "{port_name}": {{"lat": {coord["lat"]:.6f}, "lon": {coord["lon"]:.6f}}},')
    coord_lines.append("}")
    
    new_coords_section = "\n".join(coord_lines)
    
    # Find and replace the PORT_COORDINATES dictionary
    pattern = r'PORT_COORDINATES\s*=\s*\{[^}]*\}'
    
    if re.search(pattern, content):
        # Replace existing
        updated_content = re.sub(pattern, new_coords_section, content, flags=re.DOTALL)
        action = "Updated"
    else:
        # Append to end of file
        updated_content = content + "\n\n# Auto-generated port coordinates\n" + new_coords_section + "\n"
        action = "Added"
    
    # Backup original
    with open('scraper.py.backup', 'w') as f:
        f.write(content)
    print("💾 Created backup: scraper.py.backup")
    
    # Write updated file
    with open('scraper.py', 'w') as f:
        f.write(updated_content)
    
    print(f"✅ {action} PORT_COORDINATES in scraper.py")
    print(f"📊 Added {len(coordinates)} port coordinates")
    print()
    print("🔄 Next steps:")
    print("   1. Review the changes in scraper.py")
    print("   2. Run: python3 update_ports.py")
    print("   3. Check your map to see the updated positions!")
    print()


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Automatically geocode all ports and update scraper.py"
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview results without modifying files'
    )
    parser.add_argument(
        '--merge',
        action='store_true',
        help='Only geocode missing ports, keep existing coordinates'
    )
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("🤖 AUTOMATED PORT GEOCODING")
    print("=" * 70)
    print()
    print("This script will:")
    print("  1. Load all ports from your ports.geojson")
    print("  2. Use OpenStreetMap to find real coordinates")
    print("  3. Update your scraper.py with the results")
    print("  4. Create a detailed log file")
    print()
    
    if args.merge:
        print("🔄 MERGE MODE: Will preserve existing coordinates")
        print()
    
    print("⏱️  This will take a while (1+ second per port for rate limiting)")
    print("☕ Go grab a coffee - this might take 10-15 minutes!")
    print()
    
    if not args.dry_run:
        response = input("Ready to start? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("Cancelled.")
            return
    
    # Load existing coordinates if in merge mode
    existing_coords = None
    if args.merge:
        existing_coords = load_existing_coordinates()
        if existing_coords:
            print(f"✅ Loaded {len(existing_coords)} existing coordinates from scraper.py")
            print()
        else:
            print("⚠️  No existing coordinates found in scraper.py")
            print("   Running in normal mode instead")
            print()
    
    # Load ports
    ports = load_ports_from_geojson()
    if not ports:
        return
    
    # Geocode all ports
    coordinates = geocode_all_ports(ports, dry_run=args.dry_run, existing_coords=existing_coords)
    
    # Update scraper.py
    if coordinates:
        update_scraper_file(coordinates, dry_run=args.dry_run)
    else:
        print("❌ No coordinates found - nothing to update")


if __name__ == "__main__":
    main()