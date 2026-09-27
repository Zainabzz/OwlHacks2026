import { useEffect, useRef } from "react";
import { StyleSheet } from "react-native";
import MapView, { Marker, Polyline } from "react-native-maps";
import { ROUTE_COLORS, DARK_ROUTE_COLORS } from "../src/services/routing";

export default function RouteMap({
  start,
  end,
  routes = [],
  selectedRoute,
  onSelectRoute,
  isDark,
}) {
  const mapRef = useRef(null);

  const routeColors = isDark
    ? DARK_ROUTE_COLORS
    : ROUTE_COLORS;

  useEffect(() => {
    const allCoordinates = [
      start,
      end,
      ...routes.flatMap((route) => route.coordinates),
    ].filter(
      (point) =>
        Number.isFinite(point?.latitude) &&
        Number.isFinite(point?.longitude)
    );

    if (allCoordinates.length < 2) return;

    const timeout = setTimeout(() => {
      mapRef.current?.fitToCoordinates(allCoordinates, {
        edgePadding: {
          top: 80,
          right: 55,
          bottom: 80,
          left: 55,
        },
        animated: true,
      });
    }, 350);

    return () => clearTimeout(timeout);
  }, [start, end, routes]);

  return (
    <MapView
      ref={mapRef}
      style={styles.map}
      initialRegion={{
        latitude: start.latitude,
        longitude: start.longitude,
        latitudeDelta: 0.025,
        longitudeDelta: 0.025,
      }}
      userInterfaceStyle={isDark ? "dark" : "light"}
      showsUserLocation
      showsMyLocationButton
    >
      {routes.map((route, index) => {
        const isSelected = selectedRoute === route.id;

        return (
          <Polyline
            key={route.id}
            coordinates={route.coordinates}
            strokeColor={routeColors[index % routeColors.length]}
            strokeWidth={isSelected ? 8 : 5}
            zIndex={isSelected ? 10 : index + 1}
            tappable
            onPress={() => onSelectRoute(route.id)}
          />
        );
      })}

      <Marker
        coordinate={start}
        title="Starting location"
        pinColor="#277A59"
      />

      <Marker
        coordinate={end}
        title="Destination"
        pinColor="#D65D4A"
      />
    </MapView>
  );
}

const styles = StyleSheet.create({
  map: {
    flex: 1,
    width: "100%",
    height: "100%",
  },
});
