#!/usr/bin/env python3
"""
Port Coordinate Finder
This tool helps you find and add coordinates for ports in your scraper.py file.

Usage:
    python find_port_coordinates.py --list     # List all ports without coordinates
    python find_port_coordinates.py --search "Port of Miami"  # Find coordinates for a specific port
"""

import json
import argparse

def load_current_geojson():
    """Load the current ports.geojson to see what ports exist."""
    try:
        with open('api/ports.geojson', 'r') as f:
            data = json.load(f)
        return data
    except FileNotFoundError:
        print("Error: api/ports.geojson not found!")
        print("Make sure you're running this from your project root folder.")
        return None

def list_ports_without_coordinates():
    """List all unique sub-ports and check which ones share coordinates (fake offsets)."""
    data = load_current_geojson()
    if not data:
        return
    
    print("=" * 70)
    print("ANALYZING PORTS IN YOUR GEOJSON")
    print("=" * 70)
    print()
    
    # Track coordinates to find duplicates/offsets
    coord_map = {}
    zone_coords = {}
    
    for feature in data['features']:
        props = feature['properties']
        coords = tuple(feature['geometry']['coordinates'])
        
        if props.get('type') == 'cotp_zone':
            zone_name = props['name']
            zone_coords[zone_name] = coords
        elif props.get('type') == 'sub_port':
            zone_name = props.get('zone_name', 'Unknown')
            port_name = props['name']
            
            if coords not in coord_map:
                coord_map[coords] = []
            coord_map[coords].append({
                'zone': zone_name,
                'port': port_name
            })
    
    # Find ports that share coordinates (likely fake offsets)
    print("🔍 PORTS WITH SHARED/OFFSET COORDINATES (Need Real Coords):")
    print("-" * 70)
    
    zones_needing_work = {}
    
    for coords, ports in coord_map.items():
        if len(ports) > 1:
            # Multiple ports at same/similar location - definitely need real coords
            for port_info in ports:
                zone = port_info['zone']
                if zone not in zones_needing_work:
                    zones_needing_work[zone] = []
                zones_needing_work[zone].append(port_info['port'])
    
    # Print by zone
    total_ports = 0
    for zone in sorted(zones_needing_work.keys()):
        print(f"\n📍 {zone}")
        print("   Ports needing real coordinates:")
        for port in sorted(zones_needing_work[zone]):
            print(f"      - {port}")
            total_ports += 1
    
    print()
    print("=" * 70)
    print(f"SUMMARY: {total_ports} ports need real coordinates")
    print("=" * 70)
    print()
    print("💡 NEXT STEPS:")
    print("   1. Pick a zone to work on (start with your most important ports)")
    print("   2. For each port, search Google Maps for coordinates")
    print("   3. Add them to the PORT_COORDINATES dict in scraper.py")
    print()
    print("📋 EXAMPLE:")
    print('   PORT_COORDINATES = {')
    print('       "PORT OF MIAMI": {"lat": 25.7617, "lon": -80.1918},')
    print('       "PORT OF HOUSTON": {"lat": 29.7604, "lon": -95.2631},')
    print('   }')
    print()

def search_port_instructions(port_name):
    """Provide instructions for finding a specific port's coordinates."""
    print("=" * 70)
    print(f"FINDING COORDINATES FOR: {port_name}")
    print("=" * 70)
    print()
    print("📍 HOW TO FIND COORDINATES:")
    print()
    print("1. Go to Google Maps: https://www.google.com/maps")
    print(f"2. Search for: \"{port_name}\"")
    print("3. Right-click on the port location")
    print("4. Click on the coordinates that appear at the top")
    print("5. They'll be copied to your clipboard!")
    print()
    print("🔍 ALTERNATIVE METHODS:")
    print()
    print("   • USCG Homeport: https://homeport.uscg.mil/")
    print("   • MarineTraffic: https://www.marinetraffic.com/")
    print("   • Wikipedia (many ports have infoboxes with coordinates)")
    print()
    print("📝 COORDINATE FORMAT:")
    print()
    print("   Google Maps gives you: 25.7617, -80.1918")
    print("                           ^^^^^^  ^^^^^^^^")
    print("                          latitude longitude")
    print()
    print("   Add to scraper.py as:")
    print(f'   "{port_name.upper()}": {{"lat": 25.7617, "lon": -80.1918}}')
    print()
    print("⚠️  IMPORTANT:")
    print("   - Latitude comes first in Google Maps")
    print("   - In GeoJSON, longitude comes first!")
    print("   - scraper.py will handle the conversion automatically")
    print()

def export_port_list():
    """Export a CSV of all ports for batch geocoding."""
    data = load_current_geojson()
    if not data:
        return
    
    ports = []
    for feature in data['features']:
        if feature['properties'].get('type') == 'sub_port':
            ports.append({
                'zone': feature['properties'].get('zone_name', ''),
                'port': feature['properties']['name']
            })
    
    # Write CSV
    output_file = 'ports_to_geocode.csv'
    with open(output_file, 'w') as f:
        f.write("Zone,Port Name\n")
        for port in sorted(ports, key=lambda x: (x['zone'], x['port'])):
            f.write(f'"{port["zone"]}","{port["port"]}"\n')
    
    print(f"✅ Exported {len(ports)} ports to: {output_file}")
    print()
    print("💡 You can use this CSV to:")
    print("   - Import into Google Sheets")
    print("   - Use a geocoding service (geocode.xyz, locationiq.com)")
    print("   - Share with a team member to help find coordinates")
    print()

def main():
    parser = argparse.ArgumentParser(
        description="Helper tool for finding port coordinates"
    )
    parser.add_argument(
        '--list',
        action='store_true',
        help='List all ports that need real coordinates'
    )
    parser.add_argument(
        '--search',
        type=str,
        help='Get instructions for finding a specific port\'s coordinates'
    )
    parser.add_argument(
        '--export',
        action='store_true',
        help='Export CSV of all ports for batch geocoding'
    )
    
    args = parser.parse_args()
    
    if args.list:
        list_ports_without_coordinates()
    elif args.search:
        search_port_instructions(args.search)
    elif args.export:
        export_port_list()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()