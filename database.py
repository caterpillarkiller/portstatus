"""
SQLite database for USCG Port Status Monitor.

Schema (v2 — hierarchical):
  cotp_zones      – one row per Captain-of-the-Port zone
  sub_ports       – one row per individual port inside a zone
  status_history  – every status snapshot, for both zones AND sub-ports
"""

import sqlite3
from datetime import datetime
from typing import Optional, List, Dict


class PortStatusDB:
    """Database context-manager.  Usage:  with PortStatusDB() as db: ..."""

    DB_PATH = "port_status.db"

    def __init__(self, db_path: str = None):
        self.db_path = db_path or self.DB_PATH
        self.conn: Optional[sqlite3.Connection] = None

    def __enter__(self):
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON;")
        self._create_tables()
        return self

    def __exit__(self, *args):
        if self.conn:
            self.conn.close()

    # ------------------------------------------------------------------
    # schema
    # ------------------------------------------------------------------
    def _create_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS cotp_zones (
                zone_id      INTEGER PRIMARY KEY AUTOINCREMENT,
                zone_name    TEXT UNIQUE NOT NULL,
                latitude     REAL NOT NULL,
                longitude    REAL NOT NULL,
                marsec_level TEXT,
                sector_info  TEXT,
                source_url   TEXT,
                created_at   TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS sub_ports (
                subport_id   INTEGER PRIMARY KEY AUTOINCREMENT,
                zone_id      INTEGER NOT NULL REFERENCES cotp_zones(zone_id),
                port_name    TEXT NOT NULL,
                latitude     REAL NOT NULL,
                longitude    REAL NOT NULL,
                created_at   TEXT DEFAULT (datetime('now')),
                UNIQUE(zone_id, port_name)
            );

            CREATE TABLE IF NOT EXISTS status_history (
                history_id   INTEGER PRIMARY KEY AUTOINCREMENT,
                zone_id      INTEGER REFERENCES cotp_zones(zone_id),
                subport_id   INTEGER REFERENCES sub_ports(subport_id),
                condition    TEXT NOT NULL,
                comments     TEXT,
                last_changed TEXT,
                marsec_level TEXT,
                recorded_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_status_zone
                ON status_history(zone_id, recorded_at DESC);
            CREATE INDEX IF NOT EXISTS idx_status_subport
                ON status_history(subport_id, recorded_at DESC);
        """)
        self.conn.commit()

    # ------------------------------------------------------------------
    # upsert helpers
    # ------------------------------------------------------------------
    def upsert_zone(self, zone_name: str, lat: float, lon: float,
                    marsec_level: str = "", sector_info: str = "",
                    source_url: str = "") -> int:
        """Insert or update a COTP zone. Returns zone_id."""
        self.conn.execute("""
            INSERT INTO cotp_zones (zone_name, latitude, longitude, marsec_level, sector_info, source_url)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(zone_name) DO UPDATE SET
                latitude     = excluded.latitude,
                longitude    = excluded.longitude,
                marsec_level = excluded.marsec_level,
                sector_info  = excluded.sector_info,
                source_url   = excluded.source_url
        """, (zone_name, lat, lon, marsec_level, sector_info, source_url))
        self.conn.commit()
        row = self.conn.execute("SELECT zone_id FROM cotp_zones WHERE zone_name=?", (zone_name,)).fetchone()
        return row["zone_id"]

    def upsert_subport(self, zone_id: int, port_name: str, lat: float, lon: float) -> int:
        """Insert or update a sub-port. Returns subport_id."""
        self.conn.execute("""
            INSERT INTO sub_ports (zone_id, port_name, latitude, longitude)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(zone_id, port_name) DO UPDATE SET
                latitude  = excluded.latitude,
                longitude = excluded.longitude
        """, (zone_id, port_name, lat, lon))
        self.conn.commit()
        row = self.conn.execute(
            "SELECT subport_id FROM sub_ports WHERE zone_id=? AND port_name=?",
            (zone_id, port_name)
        ).fetchone()
        return row["subport_id"]

    # ------------------------------------------------------------------
    # record a status snapshot
    # ------------------------------------------------------------------
    def record_zone_status(self, zone_id: int, condition: str,
                           marsec_level: str = ""):
        self.conn.execute("""
            INSERT INTO status_history (zone_id, subport_id, condition, comments, last_changed, marsec_level)
            VALUES (?, NULL, ?, NULL, NULL, ?)
        """, (zone_id, condition, marsec_level))
        self.conn.commit()

    def record_subport_status(self, zone_id: int, subport_id: int,
                              condition: str, comments: str = "",
                              last_changed: str = ""):
        self.conn.execute("""
            INSERT INTO status_history (zone_id, subport_id, condition, comments, last_changed, marsec_level)
            VALUES (?, ?, ?, ?, ?, NULL)
        """, (zone_id, subport_id, condition, comments, last_changed))
        self.conn.commit()

    # ------------------------------------------------------------------
    # read helpers used by generate_geojson
    # ------------------------------------------------------------------
    def get_all_zones(self) -> List[Dict]:
        """All COTP zones with their latest recorded condition."""
        rows = self.conn.execute("""
            SELECT z.zone_id, z.zone_name, z.latitude, z.longitude,
                   z.marsec_level, z.sector_info, z.source_url,
                   h.condition AS zone_condition,
                   h.recorded_at AS recorded_at
            FROM cotp_zones z
            LEFT JOIN (
                SELECT zone_id, condition, recorded_at
                FROM status_history
                WHERE subport_id IS NULL
                GROUP BY zone_id
                HAVING recorded_at = MAX(recorded_at)
            ) h ON z.zone_id = h.zone_id
        """).fetchall()
        return [dict(r) for r in rows]

    def get_subports_for_zone(self, zone_id: int) -> List[Dict]:
        """All sub-ports in a zone with their latest status."""
        rows = self.conn.execute("""
            SELECT sp.subport_id, sp.port_name, sp.latitude, sp.longitude,
                   h.condition, h.comments, h.last_changed, h.recorded_at
            FROM sub_ports sp
            LEFT JOIN (
                SELECT subport_id, condition, comments, last_changed, recorded_at
                FROM status_history
                WHERE subport_id IS NOT NULL
                GROUP BY subport_id
                HAVING recorded_at = MAX(recorded_at)
            ) h ON sp.subport_id = h.subport_id
            WHERE sp.zone_id = ?
            ORDER BY sp.port_name
        """, (zone_id,)).fetchall()
        return [dict(r) for r in rows]

    def get_all_subports(self) -> List[Dict]:
        """All sub-ports across all zones with latest status (for GeoJSON)."""
        rows = self.conn.execute("""
            SELECT sp.subport_id, sp.zone_id, sp.port_name,
                   sp.latitude, sp.longitude,
                   z.zone_name,
                   h.condition, h.comments, h.last_changed, h.recorded_at
            FROM sub_ports sp
            JOIN cotp_zones z ON sp.zone_id = z.zone_id
            LEFT JOIN (
                SELECT subport_id, condition, comments, last_changed, recorded_at
                FROM status_history
                WHERE subport_id IS NOT NULL
                GROUP BY subport_id
                HAVING recorded_at = MAX(recorded_at)
            ) h ON sp.subport_id = h.subport_id
            ORDER BY z.zone_name, sp.port_name
        """).fetchall()
        return [dict(r) for r in rows]