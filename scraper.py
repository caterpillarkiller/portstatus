"""
Scraper for USCG NAVCEN Port Status data
Fetches current port conditions from https://www.navcen.uscg.gov/port-status
"""

import requests
from bs4 import BeautifulSoup
from typing import Dict, List
import re


# Port coordinates mapping (from your existing data + additions)
PORT_COORDINATES = {
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
}


class NAVCENScraper:
    """Scraper for USCG NAVCEN port status"""
    
    BASE_URL = "https://www.navcen.uscg.gov/port-status"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
    
    def get_port_zones(self) -> List[str]:
        """Get list of all port zones from main page"""
        try:
            response = self.session.get(self.BASE_URL, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find all port zone links
            zones = []
            for link in soup.find_all('a', href=re.compile(r'port-status\?zone=')):
                zone_name = link.text.strip()
                if zone_name and zone_name not in zones:
                    zones.append(zone_name)
            
            print(f"✅ Found {len(zones)} port zones")
            return zones
            
        except Exception as e:
            print(f"❌ Error fetching port zones: {e}")
            return []
    
    def scrape_port_status(self, zone: str) -> Dict:
        """Scrape status for a specific port zone"""
        try:
            url = f"{self.BASE_URL}?zone={zone}"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract port information
            port_data = {
                "zone_name": zone,
                "condition": "NORMAL",  # Default
                "details": "",
                "marsec_level": "MARSEC-1",  # Default
                "restrictions": "",
                "sector_info": "",
                "source_url": url
            }
            
            # Look for sector information
            page_text = soup.get_text()
            
            # Extract SECTOR info
            sector_match = re.search(r'SECTOR\s+[\w\s-]+\s*\(\d{2}-\d{5}\)', page_text)
            if sector_match:
                port_data["sector_info"] = sector_match.group(0).strip()
            
            # Look for MARSEC level
            marsec_match = re.search(r'MARSEC[- ]?(LEVEL[- ]?)?\d', page_text, re.IGNORECASE)
            if marsec_match:
                port_data["marsec_level"] = marsec_match.group(0).upper()
            
            # Look for condition keywords
            text_lower = page_text.lower()
            if 'closed' in text_lower or 'zulu' in text_lower:
                port_data["condition"] = "ZULU"
                port_data["details"] = "Port closed or severe restrictions"
            elif 'yankee' in text_lower or 'significant restriction' in text_lower:
                port_data["condition"] = "YANKEE"
                port_data["details"] = "Significant restrictions in place"
            elif 'x-ray' in text_lower or 'moderate restriction' in text_lower:
                port_data["condition"] = "X-RAY"
                port_data["details"] = "Moderate restrictions in place"
            elif 'whiskey' in text_lower or 'advisory' in text_lower or 'caution' in text_lower:
                port_data["condition"] = "WHISKEY"
                port_data["details"] = "Advisory conditions in effect"
            else:
                port_data["details"] = "All operations normal. No restrictions in effect."
            
            # Try to extract more detailed information
            # Look for any restriction text
            for p in soup.find_all('p'):
                text = p.get_text().strip()
                if text and len(text) > 20:  # Get substantial paragraphs
                    if any(word in text.lower() for word in ['restriction', 'caution', 'advisory', 'closed', 'notice']):
                        port_data["restrictions"] = text[:500]  # Limit length
                        break
            
            return port_data
            
        except Exception as e:
            print(f"❌ Error scraping {zone}: {e}")
            return None
    
    def scrape_all_ports(self) -> List[Dict]:
        """Scrape status for all ports"""
        zones = self.get_port_zones()
        
        if not zones:
            print("❌ No port zones found")
            return []
        
        all_data = []
        
        for i, zone in enumerate(zones, 1):
            print(f"[{i}/{len(zones)}] Scraping {zone}...")
            
            data = self.scrape_port_status(zone)
            
            if data:
                # Add coordinates if we have them
                coords = PORT_COORDINATES.get(zone)
                if coords:
                    data["latitude"] = coords["lat"]
                    data["longitude"] = coords["lon"]
                else:
                    # Use default coordinates (center of US)
                    data["latitude"] = 39.8283
                    data["longitude"] = -98.5795
                    print(f"⚠️  No coordinates for {zone}, using default")
                
                all_data.append(data)
        
        print(f"\n✅ Successfully scraped {len(all_data)} ports")
        return all_data


if __name__ == "__main__":
    # Test the scraper
    print("Testing NAVCEN scraper...\n")
    
    scraper = NAVCENScraper()
    
    # Test with Charleston
    print("Testing single port (Charleston)...")
    charleston_data = scraper.scrape_port_status("CHARLESTON")
    
    if charleston_data:
        print(f"\n✅ Charleston Status:")
        print(f"   Condition: {charleston_data['condition']}")
        print(f"   Details: {charleston_data['details']}")
        print(f"   MARSEC: {charleston_data['marsec_level']}")
        print(f"   Sector: {charleston_data['sector_info']}")
    
    print("\n" + "="*60)
    print("Ready to scrape all ports!")
    print("="*60)