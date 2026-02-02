# USCG Port Status Backend

Automated system for scraping USCG NAVCEN port status data, storing historical records, and generating map data.

## 🏗️ Architecture

```
Backend/
├── database.py          # SQLite database operations
├── scraper.py           # NAVCEN web scraper
├── update_ports.py      # Main update orchestrator
├── export_history.py    # CSV/Excel export tool
├── requirements.txt     # Python dependencies
├── port_status.db       # SQLite database (auto-created)
└── .github/workflows/
    └── update-ports.yml # Automated updates (hourly)
```

## 📊 Database Schema

### Ports Table
- `port_id` - Unique identifier
- `port_name` - Port name
- `zone_name` - USCG zone name
- `latitude` / `longitude` - Coordinates
- `sector_info` - USCG sector details
- `created_at` - When port was added

### Status History Table
- `history_id` - Unique identifier
- `port_id` - Foreign key to ports
- `condition` - Port condition (NORMAL, WHISKEY, X-RAY, YANKEE, ZULU)
- `details` - Status description
- `marsec_level` - Maritime Security level
- `restrictions` - Any restrictions in place
- `source_url` - NAVCEN source URL
- `recorded_at` - Timestamp of this status

## 🚀 Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Test the System

Run a test update with sample data:

```bash
python update_ports.py --test
```

This will:
- Create the database
- Add 2 test ports
- Generate test GeoJSON

### 3. Run Full Update

Scrape all ports from NAVCEN:

```bash
python update_ports.py
```

This will:
- Scrape all ports from NAVCEN
- Update the database
- Generate `api/ports.geojson`

### 4. Enable Automated Updates

The GitHub Action in `.github/workflows/update-ports.yml` will:
- Run every hour automatically
- Scrape latest NAVCEN data
- Commit updates to your repo
- Deploy automatically via GitHub Pages

**No additional setup needed!** Just push the files to GitHub.

## 📈 Exporting Historical Data

### Export Complete History

```bash
python export_history.py --type history
```

Generates: `port_history_YYYYMMDD_HHMMSS.csv`

### Export Last 30 Days

```bash
python export_history.py --type history --days 30
```

### Export Current Status Summary

```bash
python export_history.py --type summary
```

Generates: `port_summary_YYYYMMDD_HHMMSS.csv`

### Export Recent Status Changes

```bash
python export_history.py --type changes --days 7
```

Generates: `port_changes_YYYYMMDD_HHMMSS.csv`

### Custom Filename

```bash
python export_history.py --type history --output my_export.csv
```

## 🔍 Querying the Database

### Python API

```python
from database import PortStatusDB

# Get latest status for all ports
with PortStatusDB() as db:
    statuses = db.get_all_latest_statuses()
    for port in statuses:
        print(f"{port['port_name']}: {port['condition']}")

# Get history for specific port
with PortStatusDB() as db:
    history = db.get_port_history("CHARLESTON", days=7)
    print(f"Charleston had {len(history)} status records in last 7 days")

# Get recent status changes
with PortStatusDB() as db:
    changes = db.get_status_changes(days=7)
    for change in changes:
        print(f"{change['port_name']}: {change['old_condition']} → {change['new_condition']}")
```

## 🛠️ Port Coordinates

Coordinates are defined in `scraper.py`:

```python
PORT_COORDINATES = {
    "CHARLESTON": {"lat": 32.7765, "lon": -79.9253},
    "MIAMI": {"lat": 25.7617, "lon": -80.1918},
    # ... add more ports here
}
```

To add a new port:
1. Find coordinates on Google Maps
2. Add to `PORT_COORDINATES` dictionary
3. Remember: GeoJSON uses `[longitude, latitude]` order!

## 📅 Update Frequency

- **Automatic**: Every hour via GitHub Actions
- **Manual**: Run `python update_ports.py` anytime
- **On code changes**: Automatically runs when scraper/database code is updated

## 🔒 Data Retention

The database stores **ALL** historical records. To manage size:

```python
# Delete old records (example - not included by default)
from database import PortStatusDB
import sqlite3

conn = sqlite3.connect('port_status.db')
conn.execute("DELETE FROM status_history WHERE recorded_at < datetime('now', '-90 days')")
conn.commit()
conn.close()
```

## 📊 Excel Export (Future Enhancement)

To add Excel export, install:

```bash
pip install openpyxl
```

Then modify `export_history.py` to write `.xlsx` files instead of `.csv`.

## 🐛 Troubleshooting

### Database locked error
The database is probably being accessed by multiple processes. Wait a moment and try again.

### Scraping errors
NAVCEN website structure may have changed. Check `scraper.py` and update selectors.

### No coordinates for port
Add the port to `PORT_COORDINATES` dictionary in `scraper.py`.

## 📝 Future Enhancements

- [ ] Email notifications on status changes
- [ ] Historical trend charts
- [ ] Excel export with formatting
- [ ] Admin web interface
- [ ] API endpoint for real-time queries
- [ ] Telegram/SMS alerts

## 🎓 Understanding Port Conditions

- **NORMAL** (🟢) - Open without restrictions
- **WHISKEY** (🟡) - Advisory conditions
- **X-RAY** (🟠) - Moderate restrictions
- **YANKEE** (🟠) - Significant restrictions
- **ZULU** (🔴) - Port closed