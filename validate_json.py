#!/usr/bin/env python3
"""
JSON Validator for ports.geojson
This script will check if your ports.geojson file is valid JSON
and tell you exactly where the problem is if it's not.
"""

import json
import sys

def validate_geojson(filepath):
    """Validate a GeoJSON file and provide helpful error messages."""
    print(f"🔍 Checking: {filepath}")
    print("-" * 50)
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Check if file is empty
        if not content.strip():
            print("❌ ERROR: File is empty!")
            return False
            
        # Try to parse JSON
        data = json.loads(content)
        
        # Check if it's valid GeoJSON structure
        if not isinstance(data, dict):
            print("❌ ERROR: Root element should be an object ({})")
            return False
            
        if 'type' not in data:
            print("⚠️  WARNING: Missing 'type' field (should be 'FeatureCollection')")
            
        if data.get('type') != 'FeatureCollection':
            print(f"⚠️  WARNING: Type is '{data.get('type')}' but should be 'FeatureCollection'")
            
        if 'features' not in data:
            print("❌ ERROR: Missing 'features' array")
            return False
            
        if not isinstance(data['features'], list):
            print("❌ ERROR: 'features' should be an array")
            return False
            
        # Validate features
        feature_count = len(data['features'])
        print(f"✅ Valid JSON!")
        print(f"✅ Valid GeoJSON structure!")
        print(f"📊 Found {feature_count} features")
        
        # Check for common issues
        for i, feature in enumerate(data['features']):
            if 'geometry' not in feature:
                print(f"⚠️  WARNING: Feature {i} missing 'geometry'")
            if 'properties' not in feature:
                print(f"⚠️  WARNING: Feature {i} missing 'properties'")
                
        print("-" * 50)
        print("✅ File is valid and ready to use!")
        return True
        
    except json.JSONDecodeError as e:
        print(f"❌ JSON PARSE ERROR:")
        print(f"   Line {e.lineno}, Column {e.colno}")
        print(f"   {e.msg}")
        print()
        print("💡 Common fixes:")
        print("   - Check for missing commas between items")
        print("   - Check for missing closing brackets ] or }")
        print("   - Check for trailing commas before ] or }")
        print("   - Make sure the file isn't cut off at the end")
        return False
        
    except FileNotFoundError:
        print(f"❌ ERROR: File not found: {filepath}")
        print()
        print("💡 Make sure:")
        print("   - You're running this from your project root folder")
        print("   - The 'api' folder exists")
        print("   - The file 'ports.geojson' is inside the 'api' folder")
        return False
        
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {e}")
        return False

if __name__ == "__main__":
    # Default file path
    filepath = "api/ports.geojson"
    
    # Allow custom path from command line
    if len(sys.argv) > 1:
        filepath = sys.argv[1]
    
    print("=" * 50)
    print("🔧 PORTS.GEOJSON VALIDATOR")
    print("=" * 50)
    print()
    
    is_valid = validate_geojson(filepath)
    
    print()
    if is_valid:
        print("🎉 Your file is ready to use!")
        sys.exit(0)
    else:
        print("❌ Please fix the errors above and try again")
        sys.exit(1)