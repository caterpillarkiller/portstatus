"""
Export port status history to CSV or Excel
"""

import csv
import argparse
from datetime import datetime
from database import PortStatusDB


def export_to_csv(output_file: str, days: int = None):
    """Export complete history to CSV file"""
    
    with PortStatusDB() as db:
        history = db.get_all_history(days=days)
    
    if not history:
        print("❌ No history data found")
        return
    
    # Define CSV columns
    fieldnames = [
        'port_name',
        'zone_name',
        'latitude',
        'longitude',
        'condition',
        'details',
        'marsec_level',
        'restrictions',
        'recorded_at',
        'source_url'
    ]
    
    # Write to CSV
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for record in history:
            writer.writerow({
                'port_name': record.get('port_name', ''),
                'zone_name': record.get('zone_name', ''),
                'latitude': record.get('latitude', ''),
                'longitude': record.get('longitude', ''),
                'condition': record.get('condition', ''),
                'details': record.get('details', ''),
                'marsec_level': record.get('marsec_level', ''),
                'restrictions': record.get('restrictions', ''),
                'recorded_at': record.get('recorded_at', ''),
                'source_url': record.get('source_url', '')
            })
    
    print(f"✅ Exported {len(history)} records to {output_file}")


def export_port_summary(output_file: str):
    """Export current status of all ports"""
    
    with PortStatusDB() as db:
        statuses = db.get_all_latest_statuses()
    
    if not statuses:
        print("❌ No status data found")
        return
    
    fieldnames = [
        'port_name',
        'zone_name',
        'latitude',
        'longitude',
        'current_condition',
        'details',
        'marsec_level',
        'last_updated',
        'source_url'
    ]
    
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for record in statuses:
            writer.writerow({
                'port_name': record.get('port_name', ''),
                'zone_name': record.get('zone_name', ''),
                'latitude': record.get('latitude', ''),
                'longitude': record.get('longitude', ''),
                'current_condition': record.get('condition', 'UNKNOWN'),
                'details': record.get('details', ''),
                'marsec_level': record.get('marsec_level', ''),
                'last_updated': record.get('recorded_at', ''),
                'source_url': record.get('source_url', '')
            })
    
    print(f"✅ Exported current status for {len(statuses)} ports to {output_file}")


def export_status_changes(output_file: str, days: int = 7):
    """Export recent status changes"""
    
    with PortStatusDB() as db:
        changes = db.get_status_changes(days=days)
    
    if not changes:
        print(f"❌ No status changes found in last {days} days")
        return
    
    fieldnames = [
        'port_name',
        'old_condition',
        'new_condition',
        'change_time'
    ]
    
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for record in changes:
            writer.writerow({
                'port_name': record.get('port_name', ''),
                'old_condition': record.get('old_condition', 'NEW'),
                'new_condition': record.get('new_condition', ''),
                'change_time': record.get('change_time', '')
            })
    
    print(f"✅ Exported {len(changes)} status changes to {output_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Export USCG port status history')
    parser.add_argument('--type', 
                       choices=['history', 'summary', 'changes'],
                       default='history',
                       help='Type of export: history (all records), summary (latest status), changes (recent changes)')
    parser.add_argument('--output', 
                       default=None,
                       help='Output CSV filename')
    parser.add_argument('--days',
                       type=int,
                       default=None,
                       help='Number of days of history to export (default: all)')
    
    args = parser.parse_args()
    
    # Generate default filename if not provided
    if not args.output:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        if args.type == 'history':
            args.output = f'port_history_{timestamp}.csv'
        elif args.type == 'summary':
            args.output = f'port_summary_{timestamp}.csv'
        else:
            args.output = f'port_changes_{timestamp}.csv'
    
    # Run the appropriate export
    if args.type == 'history':
        export_to_csv(args.output, days=args.days)
    elif args.type == 'summary':
        export_port_summary(args.output)
    else:
        export_status_changes(args.output, days=args.days or 7)