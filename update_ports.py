"""
Main update script for USCG Port Status Monitor
Scrapes NAVCEN → Updates Database → Generates GeoJSON
"""

import json
from datetime import datetime
from database import PortStatusDB
from scraper import NAVCENScraper


def update_ports():
    """Main function to update port statuses"""
    
    print("="*60)
    print("USCG Port Status Update")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60 + "\n")
    
    # Step 1: Scrape NAVCEN
    print("📡 Step 1: Scraping NAVCEN for port statuses...")
    scraper = NAVCENScraper()
    port_data = scraper.scrape_all_ports()
    
    if not port_data:
        print("❌ No data scraped. Exiting.")
        return
    
    print(f"✅ Scraped {len(port_data)} ports\n")
    
    # Step 2: Update Database
    print("💾 Step 2: Updating database...")
    
    with PortStatusDB() as db:
        for port in port_data:
            # Add/update port
            port_id = db.add_or_update_port(
                port_name=port['zone_name'],
                zone_name=port['zone_name'],
                latitude=port['latitude'],
                longitude=port['longitude'],
                sector_info=port.get('sector_info')
            )
            
            # Add status record
            db.add_status_record(
                port_id=port_id,
                condition=port['condition'],
                details=port['details'],
                marsec_level=port.get('marsec_level'),
                restrictions=port.get('restrictions'),
                source_url=port['source_url']
            )
    
    print("✅ Database updated\n")
    
    # Step 3: Generate GeoJSON
    print("🗺️  Step 3: Generating GeoJSON for map...")
    generate_geojson()
    
    print("\n" + "="*60)
    print(f"✅ Update complete: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)


def generate_geojson():
    """Generate GeoJSON file from latest database statuses"""
    
    with PortStatusDB() as db:
        statuses = db.get_all_latest_statuses()
    
    # Build GeoJSON structure
    features = []
    
    for port in statuses:
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [port['longitude'], port['latitude']]
            },
            "properties": {
                "name": f"Port of {port['port_name']}",
                "condition": port.get('condition', 'UNKNOWN'),
                "details": port.get('details', 'No information available'),
                "marsec_level": port.get('marsec_level', 'Unknown'),
                "lastUpdated": port.get('recorded_at', ''),
                "nextUpdate": ""  # Could calculate based on update frequency
            }
        }
        features.append(feature)
    
    geojson = {
        "type": "FeatureCollection",
        "features": features
    }
    
    # Write to file
    output_path = 'api/ports.geojson'
    
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(geojson, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Generated {output_path} with {len(features)} ports")
        
    except Exception as e:
        print(f"❌ Error writing GeoJSON: {e}")


def test_update():
    """Test update with just a few ports"""
    print("🧪 Running test update (limited ports)...\n")
    
    # Create test data
    test_ports = [
        {
            'zone_name': 'CHARLESTON',
            'latitude': 32.7765,
            'longitude': -79.9253,
            'condition': 'NORMAL',
            'details': 'Test data - All operations normal',
            'marsec_level': 'MARSEC-1',
            'restrictions': '',
            'sector_info': 'SECTOR CHARLESTON (07-37090)',
            'source_url': 'https://www.navcen.uscg.gov/port-status?zone=CHARLESTON'
        },
        {
            'zone_name': 'MIAMI',
            'latitude': 25.7617,
            'longitude': -80.1918,
            'condition': 'WHISKEY',
            'details': 'Test data - Weather advisory in effect',
            'marsec_level': 'MARSEC-1',
            'restrictions': '',
            'sector_info': 'SECTOR MIAMI',
            'source_url': 'https://www.navcen.uscg.gov/port-status?zone=MIAMI'
        }
    ]
    
    with PortStatusDB() as db:
        for port in test_ports:
            port_id = db.add_or_update_port(
                port_name=port['zone_name'],
                zone_name=port['zone_name'],
                latitude=port['latitude'],
                longitude=port['longitude'],
                sector_info=port['sector_info']
            )
            
            db.add_status_record(
                port_id=port_id,
                condition=port['condition'],
                details=port['details'],
                marsec_level=port['marsec_level'],
                restrictions=port['restrictions'],
                source_url=port['source_url']
            )
    
    generate_geojson()
    print("\n✅ Test update complete")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--test':
        # Run test with sample data
        test_update()
    else:
        # Run full update
        update_ports()