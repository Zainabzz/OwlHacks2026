import { useEffect, useRef, useState } from "react";
import { View, Text, TouchableOpacity, StyleSheet, StatusBar, SafeAreaView, Platform, Keyboard } from "react-native";
import * as Location from "expo-location";
import { router } from "expo-router";
import DestinationSearch from "./components/DestinationSearch";
import Logo from "./components/Logo";
import NavigationMap from "./components/MapView";
import { colors } from "./constants/colors";

export default function App() {
  const [isDark, setIsDark] = useState(false);
  const [selectedDestination, setSelectedDestination] = useState(null);
  const [navigationError, setNavigationError] = useState("");
  const [location, setLocation] = useState(null);
  const startEdited = useRef(false);
  const [deviceLocation, setDeviceLocation] = useState(null);
  const [locationError, setLocationError] = useState("");

  const theme = isDark ? colors.dark : colors.light;

  useEffect(() => {
    let cancelled = false;
    async function getLocation() {
      try {
        const { status } =
          await Location.requestForegroundPermissionsAsync();

        if (cancelled) return;
        if (status !== "granted") {
          setLocationError(
            "Location permission denied. Search for a starting location instead."
          );
          return;
        }

        const current =
          await Location.getCurrentPositionAsync({
            accuracy: Location.Accuracy.Balanced,
          });

        if (cancelled) return;
        const point = {
          name: "Current location",
          latitude: current.coords.latitude,
          longitude: current.coords.longitude,
        };
        setDeviceLocation(point);
        if (!startEdited.current) setLocation(point);
      } catch {
        if (cancelled) return;
        setLocationError(
          "Unable to get your location. Search for a starting location instead."
        );
      }
    }

    getLocation();
    return () => { cancelled = true; };
  }, []);

  const handleNavigation = () => {
    Keyboard.dismiss();

    if (!selectedDestination) {
      setNavigationError("Select a destination from the search results first.");
      return;
    }
    if (!location) {
      setNavigationError("Select a starting location from the search results first.");
      return;
    }
    setNavigationError("");

    router.push({
      pathname: "/routes",
      params: {
        start: JSON.stringify(location),
        end: JSON.stringify(selectedDestination),
        theme: isDark ? "dark" : "light",
      },
    });
  };

  return (
    <SafeAreaView
      style={[
        styles.container,
        { backgroundColor: theme.background },
      ]}
    >
      <StatusBar
        barStyle={isDark ? "light-content" : "dark-content"}
        backgroundColor={theme.background}
      />

      <View style={styles.header}>
        <Logo color={theme.primary} size={46} />

        <TouchableOpacity
          onPress={() => setIsDark(!isDark)}
          style={[
            styles.themeButton,
            { backgroundColor: theme.surface },
          ]}
          accessibilityRole="button"
          accessibilityLabel={
            isDark ? "Switch to light mode" : "Switch to dark mode"
          }
        >
          <Text
            style={[
              styles.themeIcon,
              { color: theme.primary },
            ]}
          >
            {isDark ? "☀" : "☾"}
          </Text>
        </TouchableOpacity>
      </View>

      <View
        style={[
          styles.searchCard,
          {
            backgroundColor: theme.surface,
            borderColor: theme.border,
          },
        ]}
      >
        <DestinationSearch
          value={location}
          location={deviceLocation || selectedDestination}
          label="Starting location"
          placeholder="Search starting address or place"
          theme={theme}
          onSelect={place => {
            startEdited.current = true;
            setLocation(place);
            setNavigationError("");
          }}
        />
        {deviceLocation && <TouchableOpacity
          onPress={() => { startEdited.current = true; setLocation({ ...deviceLocation }); setNavigationError(""); }}
          accessibilityRole="button" style={{ paddingVertical: 8, marginBottom: 8 }}>
          <Text style={{ color: theme.primary }}>Use current location</Text>
        </TouchableOpacity>}
        <DestinationSearch
          value={selectedDestination}
          location={location || deviceLocation}
          theme={theme}
          onSelect={place => { setSelectedDestination(place); setNavigationError(""); }}
          onSubmit={handleNavigation}
        />
        {!!navigationError && (
          <Text accessibilityRole="alert" style={{ color: theme.textSecondary, marginBottom: 12 }}>{navigationError}</Text>
        )}

        <TouchableOpacity
          onPress={handleNavigation}
          activeOpacity={0.8}
          style={[
            styles.navigationButton,
            { backgroundColor: theme.primary },
          ]}
        >
          <Text
            style={[
              styles.navigationText,
              { color: theme.buttonText },
            ]}
          >
            Find routes
          </Text>
        </TouchableOpacity>
      </View>

      {locationError ? (
        <Text
          style={[
            styles.locationStatus,
            { color: theme.textSecondary },
          ]}
        >
          {locationError}
        </Text>
      ) : null}

      <View
        style={[
          styles.mapContainer,
          { borderColor: theme.border },
        ]}
      >
        <NavigationMap
          location={location}
          isDark={isDark}
        />
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    paddingTop:
      Platform.OS === "android"
        ? StatusBar.currentHeight
        : 0,
  },

  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: 20,
    paddingVertical: 12,
  },

  themeButton: {
    width: 44,
    height: 44,
    borderRadius: 22,
    justifyContent: "center",
    alignItems: "center",
  },

  themeIcon: {
    fontSize: 28,
    fontWeight: "600",
  },

  searchCard: {
    marginHorizontal: 16,
    marginBottom: 14,
    padding: 18,
    borderRadius: 22,
    borderWidth: 1,

    ...Platform.select({
      web: {
        boxShadow: "0 4px 18px rgba(0,0,0,0.06)",
      },
      default: {
        elevation: 3,
      },
    }),
  },

  inputRow: {
    flexDirection: "row",
    alignItems: "center",
    minHeight: 55,
    marginBottom: 16,
  },

  locationIcon: {
    fontSize: 32,
    marginRight: 12,
  },

  input: {
    flex: 1,
    fontSize: 19,
    fontWeight: "500",
    paddingVertical: 10,
    outlineStyle: "none",
  },

  navigationButton: {
    height: 56,
    borderRadius: 14,
    justifyContent: "center",
    alignItems: "center",
  },

  navigationText: {
    fontSize: 17,
    fontWeight: "700",
  },

  locationStatus: {
    fontSize: 12,
    marginHorizontal: 20,
    marginBottom: 8,
  },

  mapContainer: {
    flex: 1,
    marginHorizontal: 16,
    marginBottom: 16,
    borderRadius: 22,
    borderWidth: 1,
    overflow: "hidden",
    minHeight: 250,
  },
}); 
