import { MapContainer, TileLayer, Marker } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

const markerIcon = new L.Icon({
  iconUrl:
    "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  iconRetinaUrl:
    "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  shadowUrl:
    "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
  iconSize: [25, 41],
  iconAnchor: [12, 41],
});

export default function NavigationMap({
  location,
  isDark,
}) {
  const center = location
    ? [location.latitude, location.longitude]
    : [39.9526, -75.1636];

  return (
    <MapContainer
      key={`${center[0]}-${center[1]}`}
      center={center}
      zoom={14}
      style={{
        height: "100%",
        width: "100%",
        background: isDark ? "#101B2D" : "#F5F8F4",
      }}
    >
      <TileLayer
        attribution='&copy; OpenStreetMap contributors'
        url={
          "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        }
      />

      {location && (
        <Marker position={center} icon={markerIcon} />
      )}
    </MapContainer>
  );
}