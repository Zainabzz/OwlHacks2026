import MapView, { Marker } from "react-native-maps";
import { StyleSheet } from "react-native";

export default function NavigationMap({
  location,
  isDark,
}) {
  return (
    <MapView
      style={styles.map}
      initialRegion={{
        latitude: location?.latitude ?? 39.9526,
        longitude: location?.longitude ?? -75.1636,
        latitudeDelta: 0.025,
        longitudeDelta: 0.025,
      }}
      showsUserLocation={true}
      showsMyLocationButton={true}
      userInterfaceStyle={isDark ? "dark" : "light"}
    >
      {location && (
        <Marker
          coordinate={{
            latitude: location.latitude,
            longitude: location.longitude,
          }}
          title="Your location"
        />
      )}
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