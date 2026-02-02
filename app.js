// Your Mapbox access token (loaded from config.js)
mapboxgl.accessToken = CONFIG.mapboxToken;

// Initialize the map
const map = new mapboxgl.Map({
    container: 'map',
    style: 'mapbox://styles/mapbox/light-v11', // Clean, simple style
    center: [-95.7, 37.1], // Center on USA
    zoom: 4
});

// Add navigation controls (zoom buttons)
map.addControl(new mapboxgl.NavigationControl(), 'top-left');

// Load and display ports when map is ready
map.on('load', async () => {
    await loadPorts();
    updateLastUpdateTime();
});

// Function to load port data
async function loadPorts() {
    try {
        const response = await fetch('api/ports.geojson');
        const data = await response.json();

        // Add the port data as a source
        map.addSource('ports', {
            type: 'geojson',
            data: data
        });

        // Add a layer to display the ports as circles
        map.addLayer({
            id: 'ports-layer',
            type: 'circle',
            source: 'ports',
            paint: {
                'circle-radius': 8,
                'circle-color': [
                    'match',
                    ['get', 'condition'],
                    'NORMAL', '#2ecc71',    // green
                    'WHISKEY', '#f1c40f',   // yellow
                    'X-RAY', '#f39c12',     // orange
                    'YANKEE', '#e67e22',    // darker orange
                    'ZULU', '#e74c3c',      // red
                    '#7f8c8d'               // gray (unknown/default)
                ],
                'circle-stroke-width': 2,
                'circle-stroke-color': '#ffffff',
                'circle-opacity': 0.9
            }
        });

        // Add hover effect - change cursor
        map.on('mouseenter', 'ports-layer', () => {
            map.getCanvas().style.cursor = 'pointer';
        });

        map.on('mouseleave', 'ports-layer', () => {
            map.getCanvas().style.cursor = '';
        });

        // Show popup on hover
        map.on('mouseenter', 'ports-layer', (e) => {
            const coordinates = e.features[0].geometry.coordinates.slice();
            const props = e.features[0].properties;

            // Create popup HTML
            const popupHTML = createPopupHTML(props);

            // Create and display popup
            new mapboxgl.Popup({
                closeButton: false,
                closeOnClick: false
            })
                .setLngLat(coordinates)
                .setHTML(popupHTML)
                .addTo(map);
        });

        // Remove popup when mouse leaves
        map.on('mouseleave', 'ports-layer', () => {
            const popups = document.getElementsByClassName('mapboxgl-popup');
            if (popups.length) {
                popups[0].remove();
            }
        });

        // Click to zoom in on port
        map.on('click', 'ports-layer', (e) => {
            map.flyTo({
                center: e.features[0].geometry.coordinates,
                zoom: 10
            });
        });

    } catch (error) {
        console.error('Error loading port data:', error);
        alert('Error loading port data. Make sure you have ports.geojson in the api folder.');
    }
}

// Function to create popup HTML
function createPopupHTML(props) {
    // Format timestamps in both UTC and local time
    const formatTimestamp = (isoString) => {
        if (!isoString) return 'Unknown';
        
        const date = new Date(isoString);
        
        // UTC time
        const utcString = date.toUTCString();
        
        // Local time with timezone
        const localString = date.toLocaleString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            timeZoneName: 'short'
        });
        
        return `${localString}<br><span style="font-size: 0.9em; color: #999;">UTC: ${utcString}</span>`;
    };
    
    const lastUpdated = formatTimestamp(props.lastUpdated);
    const nextUpdate = props.nextUpdate ? formatTimestamp(props.nextUpdate) : 'On next update cycle';
    
    return `
        <div class="popup-title">${props.name || 'Unknown Port'}</div>
        <div class="popup-status ${props.condition || 'UNKNOWN'}">${props.condition || 'UNKNOWN'}</div>
        <div class="popup-details">
            ${props.details || 'No additional details available.'}
        </div>
        <div class="popup-timestamp">
            <strong>Last Updated:</strong><br>${lastUpdated}<br><br>
            <strong>Next Update:</strong><br>${nextUpdate}
        </div>
    `;
}

// Update the last update time display
function updateLastUpdateTime() {
    const now = new Date();
    
    // Local time
    const localTime = now.toLocaleString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        timeZoneName: 'short'
    });
    
    // UTC time
    const utcTime = now.toUTCString();
    
    document.getElementById('last-update').innerHTML = 
        `Last updated: ${localTime}<br><span style="font-size: 0.85em; color: #999;">UTC: ${utcTime}</span>`;
}

// Refresh data every 5 minutes (300000 ms)
setInterval(async () => {
    // Remove existing source and layer
    if (map.getLayer('ports-layer')) {
        map.removeLayer('ports-layer');
    }
    if (map.getSource('ports')) {
        map.removeSource('ports');
    }
    
    // Reload data
    await loadPorts();
    updateLastUpdateTime();
}, 300000);