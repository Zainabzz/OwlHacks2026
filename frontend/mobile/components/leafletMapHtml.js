const LEAFLET_CSS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
const LEAFLET_JS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
const OSM_TILES = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";

function safeJson(value) {
  return JSON.stringify(value).replace(/</g, "\\u003c");
}

export function createLeafletMapHtml({ center, zoom = 14, isDark = false, start, end, routes = [], selectedRoute }) {
  const data = {
    center,
    zoom,
    isDark,
    start,
    end,
    routes: routes.map((route) => ({
      id: route.id,
      name: route.name,
      coordinates: route.coordinates,
    })),
    selectedRoute,
  };

  return `<!doctype html>
<html>
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no" />
  <link rel="stylesheet" href="${LEAFLET_CSS}" />
  <style>
    html, body, #map { width: 100%; height: 100%; margin: 0; padding: 0; overflow: hidden; }
    body { background: ${isDark ? "#101B2D" : "#F5F8F4"}; }
    .leaflet-control-attribution { font-size: 9px !important; }
  </style>
</head>
<body>
  <div id="map" role="application" aria-label="Route map"></div>
  <script src="${LEAFLET_JS}"></script>
  <script>
    (function () {
      const data = ${safeJson(data)};
      const map = L.map('map', { zoomControl: true }).setView(data.center, data.zoom);
      L.tileLayer('${OSM_TILES}', {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>'
      }).addTo(map);

      const colors = data.isDark
        ? ['#7BE0BF', '#45C4E8', '#FFCA75']
        : ['#277A59', '#3288D1', '#D68A19'];
      const layers = new Map();
      const selectedColor = '#45C4E8';

      function setSelectedRoute(id) {
        data.routes.forEach((route, index) => {
          const layer = layers.get(route.id);
          if (!layer) return;
          const selected = route.id === id;
          layer.setStyle({
            color: selected ? (data.isDark ? selectedColor : colors[index % colors.length]) : colors[index % colors.length],
            opacity: selected ? 1 : 0.65,
            weight: selected ? 8 : 5
          });
          if (selected) layer.bringToFront();
        });
      }

      data.routes.forEach((route, index) => {
        const layer = L.polyline(route.coordinates.map(point => [point.latitude, point.longitude]), {
          color: colors[index % colors.length],
          opacity: 0.65,
          weight: 5,
          lineJoin: 'round',
          lineCap: 'round'
        }).addTo(map);
        if (route.name) layer.bindTooltip(route.name);
        layer.on('click', function () {
          setSelectedRoute(route.id);
          window.ReactNativeWebView?.postMessage(JSON.stringify({ type: 'select-route', id: route.id }));
        });
        layers.set(route.id, layer);
      });

      const points = [];
      if (data.start) {
        const point = [data.start.latitude, data.start.longitude];
        points.push(point);
        L.circleMarker(point, { radius: 8, color: '#fff', weight: 3, fillColor: '#277A59', fillOpacity: 1 })
          .addTo(map).bindPopup('Starting location');
      }
      if (data.end) {
        const point = [data.end.latitude, data.end.longitude];
        points.push(point);
        L.circleMarker(point, { radius: 8, color: '#fff', weight: 3, fillColor: '#D65D4A', fillOpacity: 1 })
          .addTo(map).bindPopup('Destination');
      }
      data.routes.forEach(route => route.coordinates.forEach(point => points.push([point.latitude, point.longitude])));
      if (points.length > 1) map.fitBounds(points, { padding: [32, 32], maxZoom: 16 });
      setSelectedRoute(data.selectedRoute);
      window.setSelectedRoute = setSelectedRoute;
      window.ReactNativeWebView?.postMessage(JSON.stringify({ type: 'map-ready' }));
    })();
  </script>
</body>
</html>`;
}

