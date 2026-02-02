"""
Database operations for USCG Port Status tracking
Stores historical port status data in SQLite
"""

import sqlite3
from datetime import datetime
from typing import List, Dict, Optional
import json


class PortStatusDB:
    def __init__(self, db_path: str = 'port_status.db'):
        """Initialize database connection"""
        self.db_path = db_path
        self.conn = None
        self.create_tables()
    
    def connect(self):
        """Create database connection"""
        if not self.conn:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
        return self.conn
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def create_tables(self):
        """Create database tables if they don't exist"""
        conn = self.connect()
        cursor = conn.cursor()
        
        # Ports table - stores basic port information
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ports (
                port_id INTEGER PRIMARY KEY AUTOINCREMENT,
                port_name TEXT UNIQUE NOT NULL,
                zone_name TEXT NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                sector_info TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Status history table - stores every status change
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS status_history (
                history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                port_id INTEGER NOT NULL,
                condition TEXT NOT NULL,
                details TEXT,
                marsec_level TEXT,
                restrictions TEXT,
                source_url TEXT,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (port_id) REFERENCES ports(port_id)
            )
        """)
        
        # Create indexes for faster queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_status_port_date 
            ON status_history(port_id, recorded_at DESC)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_status_date 
            ON status_history(recorded_at DESC)
        """)
        
        conn.commit()
        print("✅ Database tables created/verified")
    
    def add_or_update_port(self, port_name: str, zone_name: str, 
                           latitude: float, longitude: float, 
                           sector_info: str = None) -> int:
        """Add a new port or update existing port info"""
        conn = self.connect()
        cursor = conn.cursor()
        
        # Try to insert, if exists update
        cursor.execute("""
            INSERT INTO ports (port_name, zone_name, latitude, longitude, sector_info)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(port_name) 
            DO UPDATE SET 
                zone_name = excluded.zone_name,
                latitude = excluded.latitude,
                longitude = excluded.longitude,
                sector_info = excluded.sector_info
        """, (port_name, zone_name, latitude, longitude, sector_info))
        
        conn.commit()
        
        # Get the port_id
        cursor.execute("SELECT port_id FROM ports WHERE port_name = ?", (port_name,))
        port_id = cursor.fetchone()[0]
        
        return port_id
    
    def add_status_record(self, port_id: int, condition: str, 
                         details: str = None, marsec_level: str = None,
                         restrictions: str = None, source_url: str = None):
        """Add a new status record for a port"""
        conn = self.connect()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO status_history 
            (port_id, condition, details, marsec_level, restrictions, source_url)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (port_id, condition, details, marsec_level, restrictions, source_url))
        
        conn.commit()
        print(f"✅ Recorded status for port_id {port_id}: {condition}")
    
    def get_latest_status(self, port_id: int) -> Optional[Dict]:
        """Get the most recent status for a port"""
        conn = self.connect()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM status_history 
            WHERE port_id = ? 
            ORDER BY recorded_at DESC 
            LIMIT 1
        """, (port_id,))
        
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    
    def get_all_latest_statuses(self) -> List[Dict]:
        """Get the most recent status for all ports"""
        conn = self.connect()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                p.port_id,
                p.port_name,
                p.zone_name,
                p.latitude,
                p.longitude,
                p.sector_info,
                s.condition,
                s.details,
                s.marsec_level,
                s.restrictions,
                s.recorded_at,
                s.source_url
            FROM ports p
            LEFT JOIN (
                SELECT port_id, condition, details, marsec_level, 
                       restrictions, recorded_at, source_url,
                       ROW_NUMBER() OVER (PARTITION BY port_id ORDER BY recorded_at DESC) as rn
                FROM status_history
            ) s ON p.port_id = s.port_id AND s.rn = 1
            ORDER BY p.port_name
        """)
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_port_history(self, port_name: str, days: int = 30) -> List[Dict]:
        """Get status history for a specific port"""
        conn = self.connect()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                p.port_name,
                p.zone_name,
                s.condition,
                s.details,
                s.marsec_level,
                s.restrictions,
                s.recorded_at
            FROM status_history s
            JOIN ports p ON s.port_id = p.port_id
            WHERE p.port_name = ?
            AND s.recorded_at >= datetime('now', ? || ' days')
            ORDER BY s.recorded_at DESC
        """, (port_name, -days))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_all_history(self, days: int = None) -> List[Dict]:
        """Get complete status history for all ports"""
        conn = self.connect()
        cursor = conn.cursor()
        
        if days:
            cursor.execute("""
                SELECT 
                    p.port_name,
                    p.zone_name,
                    p.latitude,
                    p.longitude,
                    s.condition,
                    s.details,
                    s.marsec_level,
                    s.restrictions,
                    s.recorded_at,
                    s.source_url
                FROM status_history s
                JOIN ports p ON s.port_id = p.port_id
                WHERE s.recorded_at >= datetime('now', ? || ' days')
                ORDER BY s.recorded_at DESC, p.port_name
            """, (-days,))
        else:
            cursor.execute("""
                SELECT 
                    p.port_name,
                    p.zone_name,
                    p.latitude,
                    p.longitude,
                    s.condition,
                    s.details,
                    s.marsec_level,
                    s.restrictions,
                    s.recorded_at,
                    s.source_url
                FROM status_history s
                JOIN ports p ON s.port_id = p.port_id
                ORDER BY s.recorded_at DESC, p.port_name
            """)
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_status_changes(self, days: int = 7) -> List[Dict]:
        """Get all status changes in the last N days"""
        conn = self.connect()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                p.port_name,
                s1.condition as new_condition,
                s2.condition as old_condition,
                s1.recorded_at as change_time
            FROM status_history s1
            JOIN ports p ON s1.port_id = p.port_id
            LEFT JOIN status_history s2 ON s2.port_id = s1.port_id 
                AND s2.history_id = (
                    SELECT MAX(history_id) 
                    FROM status_history 
                    WHERE port_id = s1.port_id 
                    AND history_id < s1.history_id
                )
            WHERE s1.recorded_at >= datetime('now', ? || ' days')
            AND (s2.condition IS NULL OR s1.condition != s2.condition)
            ORDER BY s1.recorded_at DESC
        """, (-days,))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()


if __name__ == "__main__":
    # Test the database
    print("Testing database setup...")
    
    with PortStatusDB() as db:
        # Add a test port
        port_id = db.add_or_update_port(
            "Port of Charleston",
            "CHARLESTON",
            32.7765,
            -79.9253,
            "SECTOR CHARLESTON (07-37090)"
        )
        
        # Add a test status
        db.add_status_record(
            port_id,
            "NORMAL",
            "All operations normal. Test entry.",
            "MARSEC-1",
            "No restrictions"
        )
        
        # Query it back
        latest = db.get_latest_status(port_id)
        print(f"\nLatest status: {latest}")
        
        print("\n✅ Database test complete!")