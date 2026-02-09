#!/usr/bin/env python3
"""
Generate Manual Fix Checklist

Creates a text file listing all ports that need manual coordinates,
with helpful search hints for finding them.

Usage:
    python3 generate_fix_checklist.py
"""

import json
import re


def extract_state_from_zone(zone_name):
    """Try to extract state from zone name."""
    states = {
        'CHARLESTON': 'South Carolina',
        'MIAMI': 'Florida',
        'BOSTON': 'Massachusetts',
        'NEW YORK': 'New York',
        'HOUSTON': 'Texas',
        'LOS ANGELES': 'California',
        'SEATTLE': 'Washington',
        'ALASKA': 'Alaska',
        'HAWAII': 'Hawaii',
        'PUERTO RICO': 'Puerto Rico',
        'SAN JUAN': 'Puerto Rico',
        'GUAM': 'Guam',
        'VIRGINIA': 'Virginia',
        'MARYLAND': 'Maryland',
        'DELAWARE': 'Delaware',
        'PENNSYLVANIA': 'Pennsylvania',
        'GREAT LAKES': 'Michigan/Illinois',
        'LAKE MICHIGAN': 'Michigan',
        'DETROIT': 'Michigan',
        'DULUTH': 'Minnesota',
        'MOBILE': 'Alabama',
        'NEW ORLEANS': 'Louisiana',
        'GALVESTON': 'Texas',
        'PORTLAND': 'Oregon',
        'SAN FRANCISCO': 'California',
        'SAN DIEGO': 'California',
    }
    
    for key, state in states.items():
        if key in zone_name.upper():
            return state
    
    return None


def generate_search_hints(port_name, zone_name):
    """Generate helpful search queries for finding a port."""
    state = extract_state_from_zone(zone_name)
    
    hints = []
    
    # Clean up the name
    clean_name = port_name.strip()
    
    # Remove state codes if present
    clean_name = re.sub(r',\s*[A-Z]{2}$', '', clean_name)
    clean_name = re.sub(r'^[A-Z]{2},\s*', '', clean_name)
    
    # Basic searches
    if state:
        hints.append(f'"{clean_name}, {state}"')
        hints.append(f'"Port {clean_name} {state}"')
        hints.append(f'"{clean_name} harbor {state}"')
    else:
        hints.append(f'"{clean_name} United States"')
        hints.append(f'"Port {clean_name}"')
    
    # Add NOAA chart search
    hints.append(f'"NOAA chart {clean_name}"')
    
    return hints


def main():
    print("=" * 70)
    print("📋 GENERATING MANUAL FIX CHECKLIST")
    print("=" * 70)
    print()
    
    # Load ports.geojson
    try:
        with open('api/ports.geojson', 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print("❌ Error: api/ports.geojson not found!")
        print("   Run: python3 update_ports.py")
        return
    
    # Find ports at 0,0
    needs_fixing = []
    
    for feature in data['features']:
        if feature['properties'].get('type') != 'sub_port':
            continue
        
        coords = feature['geometry']['coordinates']
        
        if coords[0] == 0.0 and coords[1] == 0.0:
            needs_fixing.append({
                'name': feature['properties']['name'],
                'zone': feature['properties'].get('zone_name', 'Unknown'),
            })
    
    if not needs_fixing:
        print("🎉 No ports need fixing! All have coordinates.")
        return
    
    print(f"Found {len(needs_fixing)} ports needing coordinates")
    print()
    
    # Generate checklist file
    output_file = 'manual_fix_checklist.txt'
    
    with open(output_file, 'w') as f:
        f.write("=" * 70 + "\n")
        f.write("MANUAL COORDINATE FIX CHECKLIST\n")
        f.write(f"Total ports to fix: {len(needs_fixing)}\n")
        f.write("=" * 70 + "\n\n")
        
        f.write("HOW TO USE THIS LIST:\n")
        f.write("1. Open ports.kml in Google Earth\n")
        f.write("2. Find the port in the 'ERRORS' folder (bright magenta at 0°N, 0°E)\n")
        f.write("3. Use the search hints below to find the correct location\n")
        f.write("4. Drag the pin to the correct spot in Google Earth\n")
        f.write("5. Check off the port below\n")
        f.write("6. When done, save the KML and run: python3 import_from_kml.py\n")
        f.write("\n")
        f.write("=" * 70 + "\n\n")
        
        # Group by zone
        by_zone = {}
        for port in needs_fixing:
            zone = port['zone']
            if zone not in by_zone:
                by_zone[zone] = []
            by_zone[zone].append(port)
        
        # Write checklist
        for zone in sorted(by_zone.keys()):
            f.write(f"\n{'=' * 70}\n")
            f.write(f"ZONE: {zone} ({len(by_zone[zone])} ports)\n")
            f.write(f"{'=' * 70}\n\n")
            
            for port in sorted(by_zone[zone], key=lambda x: x['name']):
                f.write(f"[ ] {port['name']}\n")
                f.write(f"    Zone: {zone}\n")
                
                # Add search hints
                hints = generate_search_hints(port['name'], zone)
                f.write(f"    Google Search:\n")
                for hint in hints[:3]:
                    f.write(f"      • {hint}\n")
                
                f.write("\n")
        
        # Summary at end
        f.write("\n" + "=" * 70 + "\n")
        f.write("SUMMARY BY ZONE\n")
        f.write("=" * 70 + "\n\n")
        
        for zone in sorted(by_zone.keys()):
            f.write(f"  {zone}: {len(by_zone[zone])} ports\n")
    
    print(f"✅ Created: {output_file}")
    print()
    print("📋 This file contains:")
    print(f"   • All {len(needs_fixing)} ports needing coordinates")
    print("   • Organized by COTP zone")
    print("   • Search hints for each port")
    print("   • Checkboxes to track progress")
    print()
    print("💡 Open this file in a text editor and use it as you fix ports in Google Earth!")
    print()


if __name__ == "__main__":
    main()