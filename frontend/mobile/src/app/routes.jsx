import React, { useEffect, useMemo, useState} from "react";
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  Keyboard,
  ScrollView,
} from "react-native";
import { fetchWeather } from "../services/weather";
import RouteWeatherLegend from "../../components/RouteWeatherLegend";
import { useLocalSearchParams, router } from "expo-router";
import * as Location from "expo-location";

import DestinationSearch from "../../components/DestinationSearch";
import RouteMap from "../../components/RouteMap";
import { colors } from "../../constants/colors";

import {
  getRoutes,
  isValidPoint,
} from "../services/routing";

function parseLocation(value, fallback = null) {
  if (!value || typeof value !== "string") {
    return fallback;
  }

  try {
    const parsed = JSON.parse(value);

    if (
      isValidPoint(parsed)
    ) {
      return parsed;
    }
  } catch {
    // Use the fallback when route parameters are invalid.
  }

  return fallback;
}

export default function RoutesScreen() {
  const params = useLocalSearchParams();

  const initialStart = useMemo(
    () => parseLocation(params.start),
    [params.start]
  );

  const initialEnd = useMemo(
    () => parseLocation(params.end),
    [params.end]
  );

  const [start, setStart] = useState(initialStart);
  const [end, setEnd] = useState(initialEnd);

  const [isDark, setIsDark] = useState(
    params.theme === "dark"
  );

  const [routes, setRoutes] = useState([]);
  const [selectedRoute, setSelectedRoute] = useState(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [isDemo, setIsDemo] = useState(false);

  const [weatherState, setWeatherState] = useState(null);
  const weatherKey = isValidPoint(start) ? `${start.latitude},${start.longitude}` : null;
  const weather = weatherState?.key === weatherKey ? weatherState.data : null;
  const weatherError = weatherState?.key === weatherKey ? weatherState.error : "";

  useEffect(() => {
    if (!weatherKey) return;
    let cancelled = false;
    const [latitude, longitude] = weatherKey.split(",").map(Number);
    fetchWeather(latitude, longitude).then(data => {
      if (!cancelled) setWeatherState({ key: weatherKey, data, error: "" });
    }).catch(err => {
      if (!cancelled) setWeatherState({ key: weatherKey, data: null, error: err.message });
    });
    return () => { cancelled = true; };
  }, [weatherKey]);

  const theme = isDark ? colors.dark : colors.light;

  useEffect(() => {
    let cancelled = false;

    async function loadRoutes() {
      setLoading(true);
      setError("");
      setSelectedRoute(null);
      setRoutes([]);

      if (!isValidPoint(start) || !isValidPoint(end)) {
        setLoading(false);
        return;
      }

      try {
        const result = await getRoutes(start, end);

        if (!cancelled) {
          setRoutes(result);
          setSelectedRoute(result[0]?.id ?? null);
          setIsDemo(false);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message || "Unable to load routes.");
          setIsDemo(false);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadRoutes();

    return () => {
      cancelled = true;
    };
  }, [start, end]);

  const swapLocations = () => {
    Keyboard.dismiss();

    setStart(end);
    setEnd(start);


    setSelectedRoute(null);
  };

  const useCurrentLocation = async () => {
    try {
      const { status } =
        await Location.requestForegroundPermissionsAsync();

      if (status !== "granted") {
        setError("Location permission is required.");
        return;
      }

      const result = await Location.getCurrentPositionAsync({
        accuracy: Location.Accuracy.Balanced,
      });

      const current = {
        name: "Current location",
        latitude: result.coords.latitude,
        longitude: result.coords.longitude,
      };

      setStart(current);
      setError("");
    } catch {
      setError("Unable to retrieve your current location.");
    }
  };

  return (
    <View
      style={[
        styles.container,
        { backgroundColor: theme.background },
      ]}
    >
      {/* HEADER */}

      <View style={styles.header}>
        <TouchableOpacity
          onPress={() => router.back()}
          style={styles.backButton}
        >
          <Text
            style={[
              styles.backText,
              { color: theme.text },
            ]}
          >
            ←
          </Text>
        </TouchableOpacity>

        <Text
          style={[
            styles.headerTitle,
            { color: theme.text },
          ]}
        >
          Your routes
        </Text>

        <TouchableOpacity
          onPress={() => setIsDark(!isDark)}
          style={[
            styles.themeButton,
            { backgroundColor: theme.surface },
          ]}
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

      {/* START AND DESTINATION */}

      <View
        style={[
          styles.locationCard,
          {
            backgroundColor: theme.surface,
            borderColor: theme.border,
          },
        ]}
      >
        <View style={styles.locationRow}>
          <View
            style={[
              styles.startDot,
              { backgroundColor: theme.primary },
            ]}
          />

          <View style={styles.locationFields}>
            <DestinationSearch value={start} location={end} theme={theme}
              label="Starting location" placeholder="Address or place"
              onSelect={setStart} />
          </View>

          <TouchableOpacity
            onPress={useCurrentLocation}
            accessibilityLabel="Use current location"
            style={styles.currentLocationButton}
          >
            <Text
              style={{
                color: theme.primary,
                fontSize: 20,
              }}
            >
              ◎
            </Text>
          </TouchableOpacity>
        </View>

        <View style={styles.secondRow}>
          <View style={styles.locationFields}>
            <View
              style={[
                styles.separator,
                { backgroundColor: theme.border },
              ]}
            />

            <View style={styles.locationRow}>
              <View style={styles.endDot} />

              <View style={styles.locationFields}>
                <DestinationSearch value={end} location={start} theme={theme}
                  label="Destination" placeholder="Address or place"
                  onSelect={setEnd} />
              </View>
            </View>
          </View>

          <TouchableOpacity
            onPress={swapLocations}
            disabled={!start || !end}
            style={[
              styles.swapButton,
              {
                backgroundColor: theme.surfaceSecondary,
              },
            ]}
            accessibilityLabel="Swap start and destination"
          >
            <Text
              style={[
                styles.swapIcon,
                { color: theme.primary },
              ]}
            >
              ⇅
            </Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* MAP AND WEATHER LEGEND */}

      <View style={styles.routeContent}>
        <View style={styles.mapContainer}>
          {start && end && <RouteMap
            start={start}
            end={end}
            routes={routes}
            selectedRoute={selectedRoute}
            onSelectRoute={setSelectedRoute}
            isDark={isDark}
          />}

          {loading && (
            <View
              style={[
                styles.loadingOverlay,
                { backgroundColor: theme.surface },
              ]}
            >
              <ActivityIndicator
                size="large"
                color={theme.primary}
              />

              <Text
                style={{
                  color: theme.text,
                  marginTop: 12,
                }}
              >
                Finding routes...
              </Text>
            </View>
          )}

          {isDemo && !loading && (
            <View
              style={[
                styles.demoBadge,
                { backgroundColor: theme.surface },
              ]}
            >
              <Text
                style={{
                  color: theme.text,
                  fontSize: 12,
                }}
              >
                Demo paths · Not for navigation
              </Text>
            </View>
          )}
        </View>

        <View
          style={[
            styles.legendContainer,
            { backgroundColor: theme.background },
          ]}
        >
          <ScrollView
            showsVerticalScrollIndicator={false}
            nestedScrollEnabled
            contentContainerStyle={styles.legendScroll}
          >
            <View style={{ padding: 16, marginBottom: 12, borderRadius: 16, backgroundColor: theme.surface }}>
              <Text style={{ color: theme.text, fontWeight: "700", marginBottom: 8 }}>Weather at your starting point</Text>
              {!!weatherError && <Text accessibilityRole="alert" style={{ color: theme.text }}>{weatherError}</Text>}
              {!weatherKey && <Text style={{ color: theme.textSecondary }}>Choose a starting location.</Text>}
              {weatherKey && !weather && !weatherError && <ActivityIndicator color={theme.primary} />}
              {weather && Object.entries(weather.providers).map(([id, provider]) => (
                <View key={id} style={{ marginVertical: 6 }}>
                  <Text style={{ color: theme.text }}>
                    {provider.name}: {provider.status === "ok" ? `${provider.data.temperatureF}°F (${provider.data.temperatureC}°C)` : provider.error}
                  </Text>
                  {provider.status === "ok" && <Text style={{ color: theme.textSecondary, fontSize: 12 }}>{provider.data.weatherTime || "Time unavailable"} · UTC</Text>}
                </View>
              ))}
            </View>
            <RouteWeatherLegend
              routes={routes}
              selectedRoute={selectedRoute}
              onSelectRoute={setSelectedRoute}
              isDark={isDark}
              theme={theme}
              loading={loading}
            />
          </ScrollView>
        </View>
      </View>

      {!!error && (
        <View
          style={[
            styles.errorBox,
            { backgroundColor: theme.surface },
          ]}
        >
          <Text
            style={{
              color: theme.text,
              textAlign: "center",
            }}
          >
            {error}
          </Text>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    paddingTop: 50,
  },

  header: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 20,
    marginBottom: 20,
  },

  backButton: {
    width: 42,
  },

  backText: {
    fontSize: 30,
  },

  headerTitle: {
    flex: 1,
    fontSize: 22,
    fontWeight: "700",
  },

  themeButton: {
    width: 44,
    height: 44,
    borderRadius: 22,
    alignItems: "center",
    justifyContent: "center",
  },

  themeIcon: {
    fontSize: 26,
  },

  locationCard: {
    marginHorizontal: 16,
    padding: 16,
    borderRadius: 20,
    borderWidth: 1,
  },

  locationRow: {
    flexDirection: "row",
    alignItems: "center",
    minHeight: 50,
  },

  locationFields: {
    flex: 1,
  },

  locationInput: {
    flex: 1,
    fontSize: 16,
    paddingHorizontal: 12,
    paddingVertical: 10,
  },

  startDot: {
    width: 12,
    height: 12,
    borderRadius: 6,
    marginLeft: 5,
  },

  endDot: {
    width: 12,
    height: 12,
    borderRadius: 3,
    backgroundColor: "#D65D4A",
    marginLeft: 5,
  },

  currentLocationButton: {
    padding: 8,
  },

  secondRow: {
    flexDirection: "row",
    alignItems: "center",
  },

  separator: {
    height: 1,
    marginLeft: 30,
    marginVertical: 4,
  },

  swapButton: {
    width: 44,
    height: 44,
    borderRadius: 22,
    justifyContent: "center",
    alignItems: "center",
    marginLeft: 10,
  },

  swapIcon: {
    fontSize: 26,
    fontWeight: "600",
  },

  routeContent: {
    flex: 1,
    minHeight: 0,
  },

  legendContainer: {
    flex: 1,
    minHeight: 150,
    marginHorizontal: 16,
    marginBottom: 16,
  },

  legendScroll: {
    paddingBottom: 20,
  },

  mapContainer: {
    flex: 1.2,
    minHeight: 180,
    marginHorizontal: 16,
    marginBottom: 12,
    borderRadius: 20,
    overflow: "hidden",
  },

  loadingOverlay: {
    position: "absolute",
    top: 20,
    alignSelf: "center",
    padding: 20,
    borderRadius: 16,
    alignItems: "center",
  },

  demoBadge: {
    position: "absolute",
    bottom: 20,
    alignSelf: "center",
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 12,
  },

  errorBox: {
    marginHorizontal: 16,
    marginBottom: 12,
    padding: 12,
    borderRadius: 12,
  },
});
