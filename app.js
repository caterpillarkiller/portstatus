// ==========================================================================
// app.js  —  USCG Port Status Map  (two-layer: COTP zones + sub-ports)
// ==========================================================================
// Zoom thresholds
//   <= SUBPORT_ZOOM_THRESHOLD  →  show only COTP zone dots (big)
//   >  SUBPORT_ZOOM_THRESHOLD  →  hide zone dots, show individual sub-port dots
// ==========================================================================

const SUBPORT_ZOOM_THRESHOLD = 7;   // adjust if you want sub-ports to appear earlier/later

// ---------------------------------------------------------------------------
// Colour palette (matches legend)
// ---------------------------------------------------------------------------
const STATUS_COLORS = {
    NORMAL:  '#2ecc71',
    WHISKEY: '#f1c40f',
    'X-RAY': '#f39c12',
    YANKEE:  '#e67e22',
    ZULU:    '#e74c3c',
};
const DEFAULT_COLOR = '#7f8c8d';

// ---------------------------------------------------------------------------
// Map initialisation
// ---------------------------------------------------------------------------
mapboxgl.accessToken = window.MAPBOX_TOKEN || '';

const map = new mapboxgl.Map({
    container: 'map',
    style:     'mapbox://styles/mapbox/nautical-v1',
    center:    [-98, 39],
    zoom:      3
});

map.addControl(new mapboxgl.NavigationControl(), 'top-right');

// ---------------------------------------------------------------------------
// Shared state
// ---------------------------------------------------------------------------
let portData = null;       // raw GeoJSON FeatureCollection
let popupInstance = null;  // single reusable Popup

// ---------------------------------------------------------------------------
// Utility – format a date/time string into local + UTC
// ---------------------------------------------------------------------------
function formatTimePair(isoString) {
    if (!isoString) return { local: 'Unknown', utc: 'Unknown' };
    const d = new Date(isoString);
    if (isNaN(d.getTime())) {
        // Might be just a date like "2025-09-30" — parse as local midnight
        const parts = isoString.split('-');
        if (parts.length === 3) {
            return { local: isoString, utc: isoString + ' (date only)' };
        }
        return { local: isoString, utc: isoString };
    }
    const local = d.toLocaleString('en-US', {
        month: 'short', day: 'numeric', year: 'numeric',
        hour: '2-digit', minute: '2-digit', second: '2-digit'
    });
    const utc = d.toUTCString();
    return { local, utc };
}

// ---------------------------------------------------------------------------
// Utility – badge HTML for a condition
// ---------------------------------------------------------------------------
function conditionBadge(condition) {
    const color = STATUS_COLORS[condition] || DEFAULT_COLOR;
    return `<span style="display:inline-block;padding:2px 8px;border-radius:4px;
            background:${color};color:#fff;font-weight:bold;font-size:13px;
            ${condition === 'WHISKEY' ? 'color:#333' : ''}">${condition}</span>`;
}

// ---------------------------------------------------------------------------
// Utility – next-update helper.
// The scraper runs every hour via GitHub Actions.  If the NAVCEN comments
// contain a phrase like "next update 0600 local" we surface that.
// Otherwise we just say "within 1 hour".
// ---------------------------------------------------------------------------
function extractNextUpdate(comments) {
    if (!comments) return null;
    // Look for patterns like "next update 0600", "next update at 1800 local", "reevaluation at 0800"
    const match = comments.match(/(?:next\s+update|reevaluation|reassessment)\s+(?:at\s+)?(\d{3,4})\s*(local|utc|zulu)?/i);
    if (match) {
        return match[1] + (match[2] ? ' ' + match[2].toUpperCase() : ' local');
    }
    return null;
}

// ---------------------------------------------------------------------------
// Popup builders
// ---------------------------------------------------------------------------
function buildZonePopup(props) {
    const times       = formatTimePair(props.lastUpdated);
    const subPorts    = props.sub_ports || [];
    const nextUpd     = extractNextUpdate(subPorts.map(s => s.comments).join(' '));

    let html = `<div class="popup-content">
        <h3 class="popup-title">${props.name} <span style="font-size:11px;color:#888;">(COTP Zone)</span></h3>
        <div style="margin-bottom:6px;">${conditionBadge(props.condition)}&nbsp;
            <span style="font-size:12px;color:#555;">${props.marsec_level || ''}</span>
        </div>`;

    // Sub-port summary table
    if (subPorts.length > 0) {
        html += `<div style="margin:8px 0 4px;font-size:12px;font-weight:bold;color:#444;">Individual Ports:</div>
                 <table style="width:100%;border-collapse:collapse;font-size:12px;margin-bottom:8px;">`;
        for (const sp of subPorts) {
            const spColor = STATUS_COLORS[sp.condition] || DEFAULT_COLOR;
            const dot     = `<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:${spColor};margin-right:5px;"></span>`;
            html += `<tr style="border-bottom:1px solid #eee;">
                <td style="padding:3px 0;">${dot}${sp.name}</td>
                <td style="padding:3px 0;font-weight:bold;color:${spColor};">${sp.condition}</td>
            </tr>`;
            if (sp.comments) {
                html += `<tr>
                    <td colspan="2" style="padding:1px 0 3px 15px;font-size:11px;color:#666;font-style:italic;">${sp.comments}</td>
                </tr>`;
            }
        }
        html += `</table>`;
    }

    // Timestamps
    html += `<div class="popup-time">
        <span style="font-weight:bold;font-size:12px;">Last Updated:</span><br>
        ${times.local}<br>
        <span style="color:#999;font-size:11px;">UTC: ${times.utc}</span>
    </div>`;

    // Next update
    if (nextUpd) {
        html += `<div class="popup-time" style="margin-top:4px;">
            <span style="font-weight:bold;font-size:12px;">Next Update:</span><br>
            ${nextUpd}
        </div>`;
    } else {
        html += `<div class="popup-time" style="margin-top:4px;">
            <span style="font-weight:bold;font-size:12px;">Next Update:</span><br>
            Within 1 hour (automated)
        </div>`;
    }

    // Link to source
    if (props.source_url) {
        html += `<div style="margin-top:6px;font-size:11px;">
            <a href="${props.source_url}" target="_blank" style="color:#3498db;">View on NAVCEN →</a>
        </div>`;
    }

    html += `</div>`;
    return html;
}

function buildSubPortPopup(props) {
    const times   = formatTimePair(props.lastUpdated);
    const nextUpd = extractNextUpdate(props.comments);

    let html = `<div class="popup-content">
        <h3 class="popup-title">${props.name}</h3>
        <div style="font-size:11px;color:#888;margin-bottom:4px;">Part of <strong>${props.zone_name}</strong> COTP Zone</div>
        <div style="margin-bottom:6px;">${conditionBadge(props.condition)}</div>`;

    // Comments / notes from NAVCEN
    if (props.comments) {
        html += `<div style="margin:6px 0;padding:6px 8px;background:#f7f7f7;border-left:3px solid ${STATUS_COLORS[props.condition] || DEFAULT_COLOR};border-radius:0 4px 4px 0;font-size:12px;color:#444;">
            <strong>Notes:</strong> ${props.comments}
        </div>`;
    }

    // Last changed (from NAVCEN table) vs our scrape time
    if (props.last_changed) {
        html += `<div class="popup-time" style="margin-top:4px;">
            <span style="font-weight:bold;font-size:12px;">Status Since:</span><br>
            ${props.last_changed}
        </div>`;
    }

    html += `<div class="popup-time" style="margin-top:4px;">
        <span style="font-weight:bold;font-size:12px;">Last Scraped:</span><br>
        ${times.local}<br>
        <span style="color:#999;font-size:11px;">UTC: ${times.utc}</span>
    </div>`;

    // Next update
    if (nextUpd) {
        html += `<div class="popup-time" style="margin-top:4px;">
            <span style="font-weight:bold;font-size:12px;">Next Update:</span><br>
            ${nextUpd}
        </div>`;
    } else {
        html += `<div class="popup-time" style="margin-top:4px;">
            <span style="font-weight:bold;font-size:12px;">Next Update:</span><br>
            Within 1 hour (automated)
        </div>`;
    }

    html += `</div>`;
    return html;
}

// ---------------------------------------------------------------------------
// Load data & add map layers
// ---------------------------------------------------------------------------
async function loadPorts() {
    try {
        const res  = await fetch('/api/ports.geojson');
        portData   = await res.json();
    } catch (e) {
        console.error('Failed to fetch port data', e);
        return;
    }

    // Split features into two source datasets
    const zoneFeatures    = portData.features.filter(f => f.properties.type === 'cotp_zone');
    const subPortFeatures = portData.features.filter(f => f.properties.type === 'sub_port');

    // ---- COTP Zone source & layer ----
    map.addSource('cotp-zones', { type: 'geojson', data: { type: 'FeatureCollection', features: zoneFeatures } });

    map.addLayer({
        id:     'cotp-zone-circles',
        type:   'circle',
        source: 'cotp-zones',
        paint: {
            'circle-radius': [
                'interpolate', ['linear'], ['zoom'],
                2, 8,   // zoom 2  →  radius 8
                7, 11,  // zoom 7  →  radius 11
                10, 13
            ],
            'circle-color': [
                'match', ['get', 'condition'],
                'NORMAL',  STATUS_COLORS.NORMAL,
                'WHISKEY', STATUS_COLORS.WHISKEY,
                'X-RAY',   STATUS_COLORS['X-RAY'],
                'YANKEE',  STATUS_COLORS.YANKEE,
                'ZULU',    STATUS_COLORS.ZULU,
                DEFAULT_COLOR
            ],
            'circle-stroke-width': 2,
            'circle-stroke-color': '#ffffff',
            'circle-opacity': 1
        }
    });

    // Label layer for zone names
    map.addLayer({
        id:     'cotp-zone-labels',
        type:   'symbol',
        source: 'cotp-zones',
        layout: {
            'text-field':  ['get', 'name'],
            'text-size':   11,
            'text-offset': [0, 1.8],
            'text-justify': 'center',
            'text-anchor': 'top'
        },
        paint: {
            'text-color': '#333',
            'text-halo-color': '#fff',
            'text-halo-width': 2
        }
    });

    // ---- Sub-port source & layer ----
    map.addSource('sub-ports', { type: 'geojson', data: { type: 'FeatureCollection', features: subPortFeatures } });

    map.addLayer({
        id:     'sub-port-circles',
        type:   'circle',
        source: 'sub-ports',
        paint: {
            'circle-radius': [
                'interpolate', ['linear'], ['zoom'],
                7, 5,
                10, 7,
                14, 9
            ],
            'circle-color': [
                'match', ['get', 'condition'],
                'NORMAL',  STATUS_COLORS.NORMAL,
                'WHISKEY', STATUS_COLORS.WHISKEY,
                'X-RAY',   STATUS_COLORS['X-RAY'],
                'YANKEE',  STATUS_COLORS.YANKEE,
                'ZULU',    STATUS_COLORS.ZULU,
                DEFAULT_COLOR
            ],
            'circle-stroke-width': 1.5,
            'circle-stroke-color': '#ffffff',
            'circle-opacity': 1
        }
    });

    map.addLayer({
        id:     'sub-port-labels',
        type:   'symbol',
        source: 'sub-ports',
        layout: {
            'text-field':  ['get', 'name'],
            'text-size':   10,
            'text-offset': [0, 1.6],
            'text-justify': 'center',
            'text-anchor': 'top'
        },
        paint: {
            'text-color': '#444',
            'text-halo-color': '#fff',
            'text-halo-width': 1.5
        }
    });

    // Apply initial zoom-based visibility
    updateLayerVisibility();

    // Update the info panel
    updateInfoPanel();
}

// ---------------------------------------------------------------------------
// Show / hide layers based on zoom
// ---------------------------------------------------------------------------
function updateLayerVisibility() {
    const z = map.getZoom();
    if (z <= SUBPORT_ZOOM_THRESHOLD) {
        // Zoomed out — show zone dots, hide sub-ports
        map.setLayoutProperty('cotp-zone-circles', 'visibility', 'visible');
        map.setLayoutProperty('cotp-zone-labels',   'visibility', 'visible');
        map.setLayoutProperty('sub-port-circles',   'visibility', 'none');
        map.setLayoutProperty('sub-port-labels',    'visibility', 'none');
    } else {
        // Zoomed in — show sub-ports, hide zone dots
        map.setLayoutProperty('cotp-zone-circles', 'visibility', 'none');
        map.setLayoutProperty('cotp-zone-labels',   'visibility', 'none');
        map.setLayoutProperty('sub-port-circles',   'visibility', 'visible');
        map.setLayoutProperty('sub-port-labels',    'visibility', 'visible');
    }
}

map.on('zoom', updateLayerVisibility);

// ---------------------------------------------------------------------------
// Hover / click popups
// ---------------------------------------------------------------------------
function showPopup(lngLat, html) {
    if (popupInstance) popupInstance.remove();
    popupInstance = new mapboxgl.Popup({ closeButton: true, closeOnClick: false, maxWidth: '320px' })
        .setLngLat(lngLat)
        .setHTML(html)
        .addTo(map);
}

function hidePopup() {
    if (popupInstance) { popupInstance.remove(); popupInstance = null; }
}

// --- COTP zone hover ---
map.on('mouseenter', 'cotp-zone-circles', (e) => {
    map.getCanvas().style.cursor = 'pointer';
    const feat = e.features[0];
    showPopup(feat.geometry.coordinates, buildZonePopup(feat.properties));
});
map.on('mouseleave', 'cotp-zone-circles', () => {
    map.getCanvas().style.cursor = '';
    hidePopup();
});

// --- Sub-port hover ---
map.on('mouseenter', 'sub-port-circles', (e) => {
    map.getCanvas().style.cursor = 'pointer';
    const feat = e.features[0];
    showPopup(feat.geometry.coordinates, buildSubPortPopup(feat.properties));
});
map.on('mouseleave', 'sub-port-circles', () => {
    map.getCanvas().style.cursor = '';
    hidePopup();
});

// --- Click-to-zoom on COTP zone (zooms in to reveal sub-ports) ---
map.on('click', 'cotp-zone-circles', (e) => {
    const feat = e.features[0];
    map.easeTo({
        center: feat.geometry.coordinates,
        zoom:   SUBPORT_ZOOM_THRESHOLD + 2,
        duration: 800
    });
});

// ---------------------------------------------------------------------------
// Info panel (top-left)
// ---------------------------------------------------------------------------
function updateInfoPanel() {
    const panel = document.getElementById('info-panel');
    if (!panel || !portData) return;

    const zones = portData.features.filter(f => f.properties.type === 'cotp_zone');
    const subs  = portData.features.filter(f => f.properties.type === 'sub_port');

    // Latest update time across all features
    let latestTime = null;
    for (const f of portData.features) {
        const t = f.properties.lastUpdated;
        if (t && (!latestTime || t > latestTime)) latestTime = t;
    }
    const times = formatTimePair(latestTime);

    panel.innerHTML = `
        <h2 style="margin:0 0 6px;font-size:16px;">🚢 USCG Port Status</h2>
        <div style="font-size:12px;color:#555;">
            <strong>${zones.length}</strong> COTP Zones &nbsp;|&nbsp; <strong>${subs.length}</strong> Individual Ports<br>
            <span style="font-size:11px;">Last updated: ${times.local}<br>
            <span style="color:#999;">UTC: ${times.utc}</span></span>
        </div>
        <div style="margin-top:8px;font-size:11px;color:#777;">
            Zoom in past level ${SUBPORT_ZOOM_THRESHOLD} to see individual ports.<br>
            Click a zone dot to zoom in automatically.
        </div>`;
}

// ---------------------------------------------------------------------------
// Legend
// ---------------------------------------------------------------------------
function buildLegend() {
    const legend = document.getElementById('legend');
    if (!legend) return;
    legend.innerHTML = '<strong style="font-size:13px;">Port Condition</strong><br><br>';
    const labels = [
        ['NORMAL',  'Open – no restrictions'],
        ['WHISKEY', 'Advisory / minor restrictions'],
        ['X-RAY',   'Moderate restrictions'],
        ['YANKEE',  'Significant restrictions'],
        ['ZULU',    'Port closed'],
    ];
    for (const [code, desc] of labels) {
        legend.innerHTML += `<div style="display:flex;align-items:center;margin-bottom:5px;">
            <span style="display:inline-block;width:16px;height:16px;border-radius:50%;
                  background:${STATUS_COLORS[code]};border:2px solid #fff;
                  box-shadow:0 0 2px rgba(0,0,0,0.3);margin-right:8px;"></span>
            <span style="font-size:12px;"><strong>${code}</strong> – ${desc}</span>
        </div>`;
    }
}

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------
map.on('load', () => {
    loadPorts();
    buildLegend();
});