# USCG Port Status Monitor

A simple, interactive map displaying real-time status information for United States Coast Guard monitored ports.

## Project Overview

This web application visualizes port conditions using color-coded markers:
- 🟢 **NORMAL** - Open without restrictions
- 🟡 **WHISKEY** - Advisory conditions
- 🟠 **X-RAY** - Moderate restrictions  
- 🟠 **YANKEE** - Significant restrictions
- 🔴 **ZULU** - Port closed
- ⚪ **UNKNOWN** - No data available

## Features

- Interactive map powered by Mapbox
- Hover tooltips showing detailed port information
- Click to zoom into any port
- Color-coded status indicators
- Auto-refresh every 5 minutes
- Last update timestamp display
- Responsive legend

## Setup Instructions

### 1. Get a Mapbox Access Token

1. Go to [mapbox.com](https://www.mapbox.com/)
2. Create a free account
3. Navigate to your [Account page](https://account.mapbox.com/)
4. Copy your "Default public token" (starts with `pk.`)

### 2. Configure Your Token (IMPORTANT!)

1. In your project folder, find `config.template.js`
2. **Make a copy** and rename it to `config.js`
3. Open `config.js` in VS Code
4. Replace `YOUR_MAPBOX_TOKEN_HERE` with your actual token
5. Save the file

**🔒 Security Note:** The `config.js` file is in `.gitignore` so your token won't be pushed to GitHub!

### 3. Run Locally

You need a local web server to run this project (you can't just open index.html in a browser).

**Option A: Using Python (recommended)**
1. Open Terminal (press `Cmd + Space`, type "Terminal")
2. Navigate to your project folder:
   ```bash
   cd path/to/your/repo
   ```
3. Run this command:
   ```bash
   python3 -m http.server 8000
   ```
4. Open your browser and go to: `http://localhost:8000`
5. To stop the server, press `Ctrl + C` in Terminal

**Option B: Using VS Code Live Server Extension**
1. In VS Code, go to Extensions (sidebar icon that looks like blocks)
2. Search for "Live Server" by Ritwick Dey
3. Install it
4. Right-click on `index.html` and select "Open with Live Server"

## Project Structure

```
├── index.html              # Main HTML page
├── style.css               # Styling
├── app.js                  # Map logic and interactivity
├── config.template.js      # Template for API keys (COMMIT THIS)
├── config.js               # Your actual API keys (DO NOT COMMIT)
├── .gitignore              # Keeps config.js private
├── api/
│   └── ports.geojson       # Port data (GeoJSON format)
├── README.md               # This file
└── LICENSE                 # MIT License
```

## Updating Port Data

The file `api/ports.geojson` contains your port data. Currently it has sample data for 9 major US ports including Charleston, SC.

### To add or update ports:

1. Open `api/ports.geojson` in VS Code
2. Follow the GeoJSON format structure
3. Each port needs:
   - **coordinates**: `[longitude, latitude]` ⚠️ Note: longitude comes first!
   - **name**: Port name
   - **condition**: One of `NORMAL`, `WHISKEY`, `X-RAY`, `YANKEE`, `ZULU`
   - **details**: Description of current status
   - **lastUpdated**: ISO timestamp (e.g., `2026-02-01T10:00:00Z`)
   - **nextUpdate**: ISO timestamp

### Example port entry:

```json
{
  "type": "Feature",
  "geometry": {
    "type": "Point",
    "coordinates": [-122.4194, 37.7749]
  },
  "properties": {
    "name": "Port of San Francisco",
    "condition": "NORMAL",
    "details": "All operations normal.",
    "lastUpdated": "2026-02-01T10:00:00Z",
    "nextUpdate": "2026-02-01T16:00:00Z"
  }
}
```

## Getting Real USCG Data

The USCG publishes port status information at:
- **Homeport**: https://homeport.uscg.mil/

Currently, you'll need to manually update the GeoJSON file by checking port statuses. In the future, you could build a backend service to automatically fetch this data.

## Publishing Your Map Online

### Using GitHub Pages (Free!)

1. Make sure `config.template.js` is committed (not `config.js`!)
2. Go to your repo on GitHub.com
3. Click **Settings** → **Pages** (left sidebar)
4. Under "Source", select **main** branch
5. Click **Save**
6. **Important:** After deployment, create `config.js` directly on GitHub:
   - Click "Add file" → "Create new file"
   - Name it `config.js`
   - Paste your token configuration
   - Commit directly to main branch

Your site will be live at: `https://yourusername.github.io/your-repo-name/`

### Alternative: Netlify

1. Go to [netlify.com](https://www.netlify.com/)
2. Sign up with GitHub
3. Click "Add new site" → "Import an existing project"
4. Select your repository
5. Add environment variable for `MAPBOX_TOKEN`
6. Click Deploy

## Committing to GitHub

When using GitHub Desktop:

1. You'll see your files listed
2. **Make sure `config.js` is NOT in the list** (it should be grayed out or not visible)
3. You SHOULD see:
   - ✅ `config.template.js` (this is safe to commit)
   - ✅ `.gitignore` (keeps config.js private)
   - ✅ All other files
4. Write your commit message
5. Click "Commit to main"
6. Click "Push origin"

## Future Enhancements

- [ ] Automatic data refresh from USCG sources
- [ ] Filter ports by condition
- [ ] Search for specific ports
- [ ] Mobile-responsive improvements
- [ ] Historical data trackinga
- [ ] Notification system for condition changes
- [ ] Add more ports beyond the initial 9

## Technologies Used

- **Mapbox GL JS** - Interactive mapping
- **HTML/CSS/JavaScript** - Core web technologies
- **GeoJSON** - Geospatial data format

## Contributing

Feel free to submit issues or pull requests to improve this project!

## License

MIT License - See LICENSE file for details

## Questions?

Open an issue on GitHub or reach out for help!