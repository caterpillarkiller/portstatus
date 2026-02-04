#!/usr/bin/env python3
"""
Export Ports to KML for Google Earth

This tool exports your ports to a KML file that you can open in Google Earth
to visually verify coordinates and spot errors.

Features:
- Color-coded placemarks by port condition
- Separate folders for each COTP zone
- Shows ports that failed geocoding (at 0,0) in bright red
- Includes port status and comments in descriptions

Usage:
    python3 export_to_kml.py                    # Creates ports.kml
    python3 export_to_kml.py --output myports.kml
"""

import json
import argparse
from datetime import datetime
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom


def prettify_xml(elem):
    """Return a pretty-printed XML string for the Element."""
    rough_string = tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")


def get_color_by_condition(condition):
    """
    Return KML color code based on port condition.
    KML uses AABBGGRR format (Alpha, Blue, Green, Red)
    """
    colors = {
        'NORMAL': 'ff00ff00',    # Green
        'WHISKEY': 'ff00ffff',   # Yellow
        'X-RAY': 'ff0099ff',     # Orange
        'YANKEE': 'ff0066ff',    # Dark Orange
        'ZULU': 'ff0000ff',      # Red
        'UNKNOWN': 'ff808080',   # Gray
    }
    return colors.get(condition, 'ff808080')


def get_icon_by_condition(condition):
    """Return appropriate icon for condition."""
    icons = {
        'NORMAL': 'http://maps.google.com/mapfiles/kml/paddle/grn-circle.png',
        'WHISKEY': 'http://maps.google.com/mapfiles/kml/paddle/ylw-circle.png',
        'X-RAY': 'http://maps.google.com/mapfiles/kml/paddle/orange-circle.png',
        'YANKEE': 'http://maps.google.com/mapfiles/kml/paddle/orange-circle.png',
        'ZULU': 'http://maps.google.com/mapfiles/kml/paddle/red-circle.png',
        'UNKNOWN': 'http://maps.google.com/mapfiles/kml/paddle/wht-circle.png',
    }
    return icons.get(condition, 'http://maps.google.com/mapfiles/kml/paddle/wht-circle.png')


def load_ports_from_geojson():
    """Load ports from the GeoJSON file."""
    try:
        with open('api/ports.geojson', 'r') as f:
            data = json.load(f)
        return data
    except FileNotFoundError:
        print("❌ Error: api/ports.geojson not found!")
        print("   Make sure you're running this from your project root folder.")
        return None


def create_kml_styles(kml):
    """Create KML styles for different port conditions."""
    styles = {
        'NORMAL': ('normalStyle', 'ff00ff00'),
        'WHISKEY': ('whiskeyStyle', 'ff00ffff'),
        'X-RAY': ('xrayStyle', 'ff0099ff'),
        'YANKEE': ('yankeeStyle', 'ff0066ff'),
        'ZULU': ('zuluStyle', 'ff0000ff'),
        'UNKNOWN': ('unknownStyle', 'ff808080'),
        'ERROR': ('errorStyle', 'ffff00ff'),  # Bright magenta for errors
    }
    
    document = kml.find('Document')
    
    for condition, (style_id, color) in styles.items():
        style = SubElement(document, 'Style', id=style_id)
        icon_style = SubElement(style, 'IconStyle')
        SubElement(icon_style, 'color').text = color
        SubElement(icon_style, 'scale').text = '1.2'
        icon = SubElement(icon_style, 'Icon')
        SubElement(icon, 'href').text = get_icon_by_condition(condition)
        
        label_style = SubElement(style, 'LabelStyle')
        SubElement(label_style, 'scale').text = '0.9'


def create_placemark(folder, port_data):
    """Create a KML placemark for a port."""
    placemark = SubElement(folder, 'Placemark')
    
    port_name = port_data['name']
    condition = port_data.get('condition', 'UNKNOWN')
    comments = port_data.get('comments', '')
    last_changed = port_data.get('last_changed', 'Unknown')
    zone_name = port_data.get('zone_name', '')
    coords = port_data['coordinates']
    
    # Check if this is a failed geocode (at 0,0)
    is_error = (coords[0] == 0.0 and coords[1] == 0.0)
    
    # Name
    name_text = f"{port_name}"
    if is_error:
        name_text += " ⚠️ NEEDS COORDINATES"
    SubElement(placemark, 'name').text = name_text
    
    # Description with HTML formatting
    description_html = f"""
    <![CDATA[
    <h3>{port_name}</h3>
    <table border="1" cellpadding="5" style="border-collapse: collapse;">
        <tr><td><b>Zone:</b></td><td>{zone_name}</td></tr>
        <tr><td><b>Condition:</b></td><td style="color: {'green' if condition == 'NORMAL' else 'red'};">{condition}</td></tr>
        <tr><td><b>Last Changed:</b></td><td>{last_changed}</td></tr>
        <tr><td><b>Coordinates:</b></td><td>{coords[1]:.6f}, {coords[0]:.6f}</td></tr>
    """
    
    if comments:
        description_html += f"<tr><td><b>Comments:</b></td><td>{comments}</td></tr>"
    
    if is_error:
        description_html += """
        <tr><td colspan="2" style="background-color: #ffcccc;">
            <b>⚠️ WARNING: This port is at 0°N, 0°E (geocoding failed)</b><br/>
            Please find the correct coordinates and update scraper.py
        </td></tr>
        """
    
    description_html += "</table>]]>"
    
    SubElement(placemark, 'description').text = description_html
    
    # Style
    style_url = '#errorStyle' if is_error else f'#{condition.lower()}Style'
    if condition in ['NORMAL', 'WHISKEY', 'X-RAY', 'YANKEE', 'ZULU']:
        style_url = f'#{condition.lower()}Style'
    else:
        style_url = '#unknownStyle'
    
    if is_error:
        style_url = '#errorStyle'
    
    SubElement(placemark, 'styleUrl').text = style_url
    
    # Coordinates (KML uses lon,lat,altitude)
    point = SubElement(placemark, 'Point')
    SubElement(point, 'coordinates').text = f"{coords[0]},{coords[1]},0"
    
    return placemark


def export_to_kml(output_file='ports.kml'):
    """Export ports to KML file."""
    print("=" * 70)
    print("🌍 EXPORTING PORTS TO KML FOR GOOGLE EARTH")
    print("=" * 70)
    print()
    
    # Load GeoJSON data
    geojson_data = load_ports_from_geojson()
    if not geojson_data:
        return False
    
    # Create KML root
    kml = Element('kml', xmlns='http://www.opengis.net/kml/2.2')
    document = SubElement(kml, 'Document')
    SubElement(document, 'name').text = 'USCG Port Status Monitor'
    SubElement(document, 'description').text = f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
    
    # Create styles
    create_kml_styles(kml)
    
    # Group ports by zone
    zones = {}
    error_ports = []
    
    for feature in geojson_data['features']:
        props = feature['properties']
        coords = feature['geometry']['coordinates']
        
        # Only process sub-ports (individual ports, not zones)
        if props.get('type') != 'sub_port':
            continue
        
        zone_name = props.get('zone_name', 'Unknown Zone')
        
        port_data = {
            'name': props['name'],
            'zone_name': zone_name,
            'condition': props.get('condition', 'UNKNOWN'),
            'comments': props.get('comments', ''),
            'last_changed': props.get('last_changed', 'Unknown'),
            'coordinates': coords
        }
        
        # Track error ports separately
        if coords[0] == 0.0 and coords[1] == 0.0:
            error_ports.append(port_data)
        
        # Add to zone
        if zone_name not in zones:
            zones[zone_name] = []
        zones[zone_name].append(port_data)
    
    # Create "ERRORS - NEEDS COORDINATES" folder first (most important)
    if error_ports:
        error_folder = SubElement(document, 'Folder')
        SubElement(error_folder, 'name').text = f'⚠️ ERRORS - NEEDS COORDINATES ({len(error_ports)} ports)'
        SubElement(error_folder, 'description').text = 'These ports failed geocoding and are at 0°N, 0°E'
        SubElement(error_folder, 'open').text = '1'  # Open by default
        
        for port_data in sorted(error_ports, key=lambda x: x['name']):
            create_placemark(error_folder, port_data)
    
    # Create folders for each zone
    for zone_name in sorted(zones.keys()):
        zone_ports = zones[zone_name]
        
        # Count ports by condition
        condition_counts = {}
        for port in zone_ports:
            condition = port['condition']
            condition_counts[condition] = condition_counts.get(condition, 0) + 1
        
        folder = SubElement(document, 'Folder')
        
        # Folder name with counts
        folder_name = f"{zone_name} ({len(zone_ports)} ports)"
        if len(condition_counts) > 1 or 'NORMAL' not in condition_counts:
            # Show condition breakdown if not all normal
            status_summary = ', '.join([f"{count} {cond}" for cond, count in sorted(condition_counts.items())])
            folder_name += f" - {status_summary}"
        
        SubElement(folder, 'name').text = folder_name
        
        # Add placemarks for each port in this zone
        for port_data in sorted(zone_ports, key=lambda x: x['name']):
            create_placemark(folder, port_data)
    
    # Write KML file
    kml_string = prettify_xml(kml)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(kml_string)
    
    print(f"✅ Exported {len([f for f in geojson_data['features'] if f['properties'].get('type') == 'sub_port'])} ports to: {output_file}")
    print()
    
    if error_ports:
        print(f"⚠️  WARNING: {len(error_ports)} ports need coordinates!")
        print("   These are shown in bright magenta at 0°N, 0°E")
        print()
    
    print("📍 NEXT STEPS:")
    print("   1. Open the KML file in Google Earth")
    print("   2. Look for ports in the wrong locations")
    print("   3. Look for magenta pins at 0°N, 0°E (failed geocodes)")
    print("   4. Right-click any port → 'Add Placemark' to mark corrections")
    print("   5. Update coordinates in scraper.py")
    print("   6. Re-run: python3 update_ports.py")
    print()
    print("💡 TIP: In Google Earth, you can:")
    print("   - Use the ruler tool to measure distances")
    print("   - Save your own correction placemarks")
    print("   - Export a new KML with your corrections")
    print()
    
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Export ports to KML for Google Earth visualization"
    )
    parser.add_argument(
        '--output',
        type=str,
        default='ports.kml',
        help='Output KML filename (default: ports.kml)'
    )
    
    args = parser.parse_args()
    
    success = export_to_kml(args.output)
    
    if success:
        print(f"🌍 Open {args.output} in Google Earth to verify your ports!")
    else:
        print("❌ Export failed")


if __name__ == "__main__":
    main()