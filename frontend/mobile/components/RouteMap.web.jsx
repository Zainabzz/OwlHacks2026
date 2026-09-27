import React from "react";
import { MapContainer, TileLayer, Polyline, CircleMarker, Tooltip, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { ROUTE_COLORS, DARK_ROUTE_COLORS} from "../src/services/routing";

function FitRoutes({ start, end, routes }) {
  const map = useMap();

  React.useEffect(() => {
    const points = [
      start,
      end,
      ...routes.flatMap((route) => route.coordinates),
    ].filter(Boolean);

    if (points.length < 2) return;

    const bounds = points.map((point) => [
      point.latitude,
      point.longitude,
    ]);

    map.fitBounds(bounds, {
      padding: [35, 35],
    });
  }, [map, start, end, routes]);

  return null;
}

function RouteLine({ route, color, isSelected, isPreferred, onSelectRoute }) {
  const ref = React.useRef(null);
  React.useEffect(() => {
    if (isSelected) ref.current?.bringToFront();
  }, [isSelected]);
  return (
    <Polyline ref={ref} positions={route.coordinates.map(point => [point.latitude, point.longitude])}
      pathOptions={{ color, weight: isSelected ? 8 : 5, opacity: isSelected ? 1 : .65, lineJoin: "round", lineCap: "round" }}
      eventHandlers={{ click: () => onSelectRoute(route.id) }}>
      <Tooltip sticky>
        {route.name}{isPreferred ? " (Preferred)" : ""}{Number.isFinite(route.metrics?.durationMinutes) ? ` · ${route.metrics.durationMinutes} min` : ""}
      </Tooltip>
    </Polyline>
  );
}

export default function RouteMap({
  start,
  end,
  routes = [],
  selectedRoute,
  onSelectRoute,
  isDark,
}) {
  const routeColors = isDark
    ? DARK_ROUTE_COLORS
    : ROUTE_COLORS;

  return (
    <MapContainer
      center={[start.latitude, start.longitude]}
      zoom={14}
      style={{
        width: "100%",
        height: "100%",
      }}
    >
      <TileLayer
        attribution="&copy; OpenStreetMap contributors"
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />

      <FitRoutes
        start={start}
        end={end}
        routes={routes}
      />

      {routes.map((route, index) => ({ route, index }))
        .sort((a, b) => Number(a.route.id === selectedRoute) - Number(b.route.id === selectedRoute))
        .map(({ route, index }) => (
          <RouteLine key={route.id} route={route}
            color={routeColors[index % routeColors.length]}
            isSelected={selectedRoute === route.id}
            isPreferred={route.isPreferred ?? (index === 0)}
            onSelectRoute={onSelectRoute} />
        ))}

      <CircleMarker
        center={[start.latitude, start.longitude]}
        radius={8}
        pathOptions={{
          color: "#FFFFFF",
          fillColor: "#277A59",
          fillOpacity: 1,
          weight: 3,
        }}
      />

      <CircleMarker
        center={[end.latitude, end.longitude]}
        radius={8}
        pathOptions={{
          color: "#FFFFFF",
          fillColor: "#D65D4A",
          fillOpacity: 1,
          weight: 3,
        }}
      />
    </MapContainer>
  );
}
