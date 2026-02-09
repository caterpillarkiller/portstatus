#!/usr/bin/env python3
"""
Import Port Coordinates from KML

This tool reads a KML file (edited in Google Earth) and updates your
scraper.py with the corrected coordinates.

WORKFLOW:
1. Run: python3 export_to_kml.py           # Export current ports
2. Open ports.kml in Google Earth
3. Drag ports to correct locations
4. Save the edited KML (File → Save Place As...)
5. Run: python3 import_from_kml.py corrected_ports.kml

Usage:
    python3 import_from_kml.py ports.kml
    python3 import_from_kml.py corrected_ports.kml --dry-run
"""

import argparse
import re
from xml.etree import ElementTree as ET


def parse_kml_file(kml_file):
    """
    Parse a KML file and extract port coordinates.
    
    Returns:
        Dict like: {"PORT NAME": {"lat": 25.7617, "lon": -80.1918}}
    """
    print(f"📖 Reading KML file: {kml_file}")
    
    try:
        tree = ET.parse(kml_file)
        root = tree.getroot()
    except Exception as e:
        print(f"❌ Error reading KML file: {e}")
        return None
    
    # Handle KML namespace
    namespace = {'kml': 'http://www.opengis.net/kml/2.2'}
    
    # Try with namespace
    placemarks = root.findall('.//kml:Placemark', namespace)
    
    # If no results, try without namespace (some KML files don't use it)
    if not placemarks:
        # Remove namespace from tag names
        for elem in root.iter():
            if '}' in elem.tag:
                elem.tag = elem.tag.split('}')[1]
        placemarks = root.findall('.//Placemark')
    
    if not placemarks:
        print("❌ No placemarks found in KML file!")
        return None
    
    coordinates = {}
    skipped = []
    
    for placemark in placemarks:
        # Get name
        name_elem = placemark.find('.//{http://www.opengis.net/kml/2.2}name')
        if name_elem is None:
            name_elem = placemark.find('.//name')
        
        if name_elem is None or not name_elem.text:
            continue
        
        name = name_elem.text.strip()
        
        # Remove any warning markers we added
        name = re.sub(r'\s*⚠️.*$', '', name)
        name = name.strip()
        
        # Get coordinates
        coord_elem = placemark.find('.//{http://www.opengis.net/kml/2.2}coordinates')
        if coord_elem is None:
            coord_elem = placemark.find('.//coordinates')
        
        if coord_elem is None or not coord_elem.text:
            skipped.append(name)
            continue
        
        # Parse coordinates (KML format is: lon,lat,altitude)
        coord_text = coord_elem.text.strip()
        parts = coord_text.split(',')
        
        if len(parts) < 2:
            skipped.append(name)
            continue
        
        try:
            lon = float(parts[0])
            lat = float(parts[1])
            
            # Store coordinates
            coordinates[name] = {
                "lat": lat,
                "lon": lon
            }
        except ValueError:
            skipped.append(name)
            continue
    
    print(f"✅ Found {len(coordinates)} ports with coordinates")
    
    if skipped:
        print(f"⚠️  Skipped {len(skipped)} placemarks (no valid coordinates)")
    
    return coordinates


def update_scraper_with_coordinates(coordinates, dry_run=False):
    """
    Update scraper.py PORT_COORDINATES with the new coordinates.
    """
    if dry_run:
        print()
        print("=" * 70)
        print("🔍 DRY RUN - Preview of changes:")
        print("=" * 70)
        print()
        print("First 10 ports that would be updated:")
        for i, (name, coords) in enumerate(list(coordinates.items())[:10]):
            print(f'  "{name}": {{"lat": {coords["lat"]:.6f}, "lon": {coords["lon"]:.6f}}}')
        if len(coordinates) > 10:
            print(f"  ... and {len(coordinates) - 10} more")
        print()
        print("💡 Run without --dry-run to actually update scraper.py")
        return
    
    print()
    print("=" * 70)
    print("📝 UPDATING scraper.py")
    print("=" * 70)
    
    # Read current scraper.py
    try:
        with open('scraper.py', 'r') as f:
            content = f.read()
    except FileNotFoundError:
        print("❌ Error: scraper.py not found!")
        print("   Make sure you're running this from your project root folder.")
        return False
    
    # Build the new PORT_COORDINATES dictionary
    coord_lines = ["PORT_COORDINATES = {"]
    for port_name in sorted(coordinates.keys()):
        coord = coordinates[port_name]
        coord_lines.append(f'    "{port_name}": {{"lat": {coord["lat"]:.6f}, "lon": {coord["lon"]:.6f}}},')
    coord_lines.append("}")
    
    new_coords_section = "\n".join(coord_lines)
    
    # Find and replace the PORT_COORDINATES dictionary
    pattern = r'PORT_COORDINATES\s*=\s*\{[^}]*\}'
    
    if re.search(pattern, content, re.DOTALL):
        # Replace existing
        updated_content = re.sub(pattern, new_coords_section, content, flags=re.DOTALL)
        action = "Updated"
    else:
        # Append to end of file
        updated_content = content + "\n\n# Imported port coordinates from KML\n" + new_coords_section + "\n"
        action = "Added"
    
    # Backup original
    backup_file = 'scraper.py.backup'
    with open(backup_file, 'w') as f:
        f.write(content)
    print(f"💾 Created backup: {backup_file}")
    
    # Write updated file
    with open('scraper.py', 'w') as f:
        f.write(updated_content)
    
    print(f"✅ {action} PORT_COORDINATES in scraper.py")
    print(f"📊 Updated {len(coordinates)} port coordinates")
    print()
    
    return True


def compare_with_existing(kml_coordinates):
    """
    Compare KML coordinates with existing scraper.py coordinates.
    Shows what changed.
    """
    print()
    print("=" * 70)
    print("🔍 COMPARING WITH EXISTING COORDINATES")
    print("=" * 70)
    
    # Try to load existing coordinates
    try:
        with open('scraper.py', 'r') as f:
            content = f.read()
        
        pattern = r'PORT_COORDINATES\s*=\s*\{([^}]+)\}'
        match = re.search(pattern, content, re.DOTALL)
        
        if not match:
            print("ℹ️  No existing PORT_COORDINATES found in scraper.py")
            print("   All coordinates will be new")
            return
        
        coords_text = match.group(1)
        existing = {}
        
        line_pattern = r'"([^"]+)":\s*\{\s*"lat":\s*([-\d.]+),\s*"lon":\s*([-\d.]+)'
        for m in re.finditer(line_pattern, coords_text):
            port_name = m.group(1)
            lat = float(m.group(2))
            lon = float(m.group(3))
            existing[port_name] = {"lat": lat, "lon": lon}
        
        # Compare
        new_ports = []
        updated_ports = []
        unchanged_ports = []
        
        for name, new_coords in kml_coordinates.items():
            if name not in existing:
                new_ports.append(name)
            else:
                old_coords = existing[name]
                # Check if coordinates changed significantly (more than 0.0001 degrees)
                lat_diff = abs(new_coords['lat'] - old_coords['lat'])
                lon_diff = abs(new_coords['lon'] - old_coords['lon'])
                
                if lat_diff > 0.0001 or lon_diff > 0.0001:
                    updated_ports.append({
                        'name': name,
                        'old': old_coords,
                        'new': new_coords,
                        'distance_km': calculate_distance(old_coords, new_coords)
                    })
                else:
                    unchanged_ports.append(name)
        
        print()
        print(f"📊 SUMMARY:")
        print(f"   🆕 New ports: {len(new_ports)}")
        print(f"   ✏️  Updated ports: {len(updated_ports)}")
        print(f"   ✅ Unchanged ports: {len(unchanged_ports)}")
        
        if new_ports:
            print()
            print(f"🆕 NEW PORTS (first 10):")
            for name in new_ports[:10]:
                coords = kml_coordinates[name]
                print(f"   - {name}: {coords['lat']:.4f}, {coords['lon']:.4f}")
            if len(new_ports) > 10:
                print(f"   ... and {len(new_ports) - 10} more")
        
        if updated_ports:
            print()
            print(f"✏️  UPDATED PORTS (showing significant moves):")
            # Sort by distance moved
            updated_ports.sort(key=lambda x: x['distance_km'], reverse=True)
            for item in updated_ports[:15]:
                name = item['name']
                old = item['old']
                new = item['new']
                dist = item['distance_km']
                print(f"   - {name}")
                print(f"     Old: {old['lat']:.4f}, {old['lon']:.4f}")
                print(f"     New: {new['lat']:.4f}, {new['lon']:.4f}")
                print(f"     Moved: {dist:.1f} km")
            if len(updated_ports) > 15:
                print(f"   ... and {len(updated_ports) - 15} more")
        
        print()
    
    except Exception as e:
        print(f"⚠️  Could not compare: {e}")


def calculate_distance(coord1, coord2):
    """
    Calculate approximate distance between two coordinates in kilometers.
    Uses simple Euclidean approximation (good enough for our purposes).
    """
    lat_diff = coord2['lat'] - coord1['lat']
    lon_diff = coord2['lon'] - coord1['lon']
    
    # Rough conversion: 1 degree ≈ 111 km
    # Adjust longitude by latitude
    import math
    avg_lat = (coord1['lat'] + coord2['lat']) / 2
    lon_km = lon_diff * 111 * math.cos(math.radians(avg_lat))
    lat_km = lat_diff * 111
    
    distance = math.sqrt(lon_km**2 + lat_km**2)
    return distance


def main():
    parser = argparse.ArgumentParser(
        description="Import corrected port coordinates from KML file"
    )
    parser.add_argument(
        'kml_file',
        help='Path to KML file with corrected coordinates'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without modifying scraper.py'
    )
    parser.add_argument(
        '--compare',
        action='store_true',
        help='Show comparison with existing coordinates'
    )
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("📥 IMPORT COORDINATES FROM KML")
    print("=" * 70)
    print()
    
    # Parse KML
    coordinates = parse_kml_file(args.kml_file)
    
    if not coordinates:
        print("❌ No coordinates found in KML file")
        return
    
    # Compare with existing if requested
    if args.compare or not args.dry_run:
        compare_with_existing(coordinates)
    
    # Update scraper.py
    if args.dry_run:
        update_scraper_with_coordinates(coordinates, dry_run=True)
    else:
        print()
        response = input("Update scraper.py with these coordinates? (yes/no): ")
        if response.lower() in ['yes', 'y']:
            success = update_scraper_with_coordinates(coordinates, dry_run=False)
            
            if success:
                print()
                print("🎉 SUCCESS!")
                print()
                print("📋 NEXT STEPS:")
                print("   1. Review the changes in scraper.py")
                print("   2. Run: python3 update_ports.py")
                print("   3. Run: python3 export_to_kml.py")
                print("   4. Verify in Google Earth that ports are correct")
                print("   5. Check your web map: http://localhost:8000")
                print()
        else:
            print("Cancelled.")


if __name__ == "__main__":
    main()