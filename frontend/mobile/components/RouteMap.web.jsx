import React from "react";
import { MapContainer, TileLayer, Polyline, CircleMarker, useMap } from "react-leaflet";
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

      {routes.map((route, index) => (
        <Polyline
          key={route.id}
          positions={route.coordinates.map((point) => [
            point.latitude,
            point.longitude,
          ])}
          pathOptions={{
            color: routeColors[index],
            weight:
              selectedRoute === route.id ? 8 : 5,
            opacity: 0.95,
          }}
          eventHandlers={{
            click: () => onSelectRoute(route.id),
          }}
        />
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
