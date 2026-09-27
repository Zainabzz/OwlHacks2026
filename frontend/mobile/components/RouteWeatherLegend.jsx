import { useState } from "react";
import {
  View,
  Text,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
} from "react-native";

import {
  ROUTE_COLORS,
  DARK_ROUTE_COLORS,
} from "../src/services/routing";

const METRICS = [
  {
    key: "durationMinutes",
    label: "Travel time",
    icon: "◷",
    unit: "min",
  },
  {
    key: "sunExposurePercent",
    label: "Sun exposure",
    icon: "☀",
    unit: "%",
  },
  {
    key: "treeCanopyPercent",
    label: "Tree canopy",
    icon: "♧",
    unit: "%",
  },
  {
    key: "buildingShadePercent",
    label: "Building shade",
    icon: "▥",
    unit: "%",
  },
  {
    key: "rainExposurePercent",
    label: "Rain exposure",
    icon: "☂",
    unit: "%",
  },
  {
    key: "temperatureC",
    label: "Temperature",
    icon: "°",
    unit: "°C",
  },
  {
    key: "windImpact",
    label: "Wind impact",
    icon: "≋",
  },
  {
    key: "airQualityIndex",
    label: "Area AQI (US estimate)",
    icon: "◎",
  },
  {
    key: "snowCondition",
    label: "Modeled snowfall",
    icon: "❄",
  },
];

function formatMetric(metric, value) {
  if (value === null || value === undefined) {
    return "Not available";
  }

  if (typeof value === "number") {
    return `${Math.round(value * 10) / 10}${metric.unit || ""}`;
  }

  return String(value);
}

function MetricCard({ metric, value, theme }) {
  return (
    <View
      style={[
        styles.metricCard,
        { backgroundColor: theme.surfaceSecondary },
      ]}
    >
      <View style={styles.metricHeading}>
        <Text
          style={[
            styles.metricIcon,
            { color: theme.primary },
          ]}
        >
          {metric.icon}
        </Text>

        <Text
          style={[
            styles.metricLabel,
            { color: theme.textSecondary },
          ]}
        >
          {metric.label}
        </Text>
      </View>

      <Text
        style={[
          styles.metricValue,
          { color: theme.text },
        ]}
      >
        {formatMetric(metric, value)}
      </Text>
    </View>
  );
}

export default function RouteWeatherLegend({
  routes = [],
  selectedRoute,
  onSelectRoute,
  isDark,
  theme,
  loading = false,
}) {
  const [expanded, setExpanded] = useState(true);

  const routeColors = isDark
    ? DARK_ROUTE_COLORS
    : ROUTE_COLORS;

  const activeRoute =
    routes.find((route) => route.id === selectedRoute) ||
    routes[0];

  const activeIndex = routes.findIndex(
    (route) => route.id === activeRoute?.id
  );

  const activeColor =
    routeColors[Math.max(0, activeIndex) % routeColors.length];

  const metrics = activeRoute?.metrics || {};

  return (
    <View
      style={[
        styles.container,
        {
          backgroundColor: theme.surface,
          borderColor: theme.border,
        },
      ]}
    >
      {/* EXPAND / COLLAPSE */}

      <TouchableOpacity
        onPress={() => setExpanded(!expanded)}
        style={styles.header}
        accessibilityRole="button"
        accessibilityLabel={
          expanded
            ? "Collapse route comparison"
            : "Expand route comparison"
        }
      >
        <Text
          style={[
            styles.title,
            { color: theme.text },
          ]}
        >
          Compare routes
        </Text>

        <Text
          style={[
            styles.chevron,
            { color: theme.primary },
          ]}
        >
          {expanded ? "⌄" : "⌃"}
        </Text>
      </TouchableOpacity>

      {expanded && (
        <>
          {/* ROUTE LEGEND */}

          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.routeList}
          >
            {routes.map((route, index) => {
              const color =
                routeColors[index % routeColors.length];

              const active = activeRoute?.id === route.id;

              return (
                <TouchableOpacity
                  key={route.id}
                  onPress={() => onSelectRoute(route.id)}
                  style={[
                    styles.routeChip,
                    {
                      backgroundColor:
                        theme.surfaceSecondary,
                      borderColor: active
                        ? color
                        : theme.border,
                      borderWidth: active ? 2 : 1,
                    },
                  ]}
                >
                  <View
                    style={[
                      styles.routeDot,
                      { backgroundColor: color },
                    ]}
                  />

                  <Text
                    style={{
                      color: theme.text,
                      fontWeight: active ? "700" : "500",
                    }}
                  >
                    {route.name}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </ScrollView>

          {loading ? (
            <Text
              style={{
                color: theme.textSecondary,
                paddingVertical: 16,
              }}
            >
              Calculating route conditions...
            </Text>
          ) : activeRoute ? (
            <>
              {/* SELECTED ROUTE */}

              <View style={styles.activeHeading}>
                <View
                  style={[
                    styles.routeDot,
                    {
                      backgroundColor: activeColor,
                      width: 14,
                      height: 14,
                    },
                  ]}
                />

                <Text
                  style={[
                    styles.activeTitle,
                    { color: theme.text },
                  ]}
                >
                  {activeRoute.name}
                </Text>
              </View>

              <View style={styles.metricsGrid}>
                {METRICS.map((metric) => (
                  <View
                    key={metric.key}
                    style={styles.metricColumn}
                  >
                    <MetricCard
                      metric={metric}
                      value={metrics[metric.key]}
                      theme={theme}
                    />
                  </View>
                ))}
              </View>

              <View
                style={[
                  styles.guidanceBox,
                  {
                    backgroundColor:
                      theme.surfaceSecondary,
                  },
                ]}
              >
                <Text
                  style={[
                    styles.guidanceTitle,
                    { color: theme.text },
                  ]}
                >
                  Sidewalk guidance
                </Text>

                <Text
                  style={{
                    color: theme.textSecondary,
                    fontSize: 13,
                    lineHeight: 19,
                  }}
                >
                  {activeRoute.sidewalkGuidance ||
                    "Sidewalk-side exposure data is not available yet."}
                </Text>
              </View>

              {activeRoute.metricContext && (
                <Text style={[styles.notice, { color: theme.textSecondary }]}>
                  Weather: starting-point model · {activeRoute.metricContext.weatherTime || "unavailable"} UTC.
                  {"\n"}Area AQI: {activeRoute.metricContext.airQualityTime || "unavailable"} UTC. Sidewalk ice conditions unavailable.
                  {"\n"}Weather: Open-Meteo. Air quality: CAMS via Open-Meteo.
                </Text>
              )}
              <Text
                style={[
                  styles.notice,
                  { color: theme.textSecondary },
                ]}
              >
                {activeRoute.isDemo
                  ? "Demo route. Weather exposure has not been calculated."
                  : "Exposure estimates depend on available weather and geographic data."}
              </Text>
            </>
          ) : (
            <Text
              style={{
                color: theme.textSecondary,
                paddingVertical: 12,
              }}
            >
              No routes available.
            </Text>
          )}
        </>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    borderRadius: 20,
    borderWidth: 1,
    padding: 16,
  },

  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    minHeight: 30,
  },

  title: {
    fontSize: 18,
    fontWeight: "700",
  },

  chevron: {
    fontSize: 26,
    fontWeight: "600",
  },

  routeList: {
    gap: 10,
    paddingVertical: 16,
  },

  routeChip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    paddingHorizontal: 14,
    paddingVertical: 12,
    borderRadius: 24,
  },

  routeDot: {
    width: 11,
    height: 11,
    borderRadius: 6,
  },

  activeHeading: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    marginBottom: 14,
    marginTop: 4,
  },

  activeTitle: {
    fontSize: 17,
    fontWeight: "700",
  },

  metricsGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 10,
  },

  metricColumn: {
    width: "48%",
    flexGrow: 1,
  },

  metricCard: {
    borderRadius: 12,
    padding: 12,
    minHeight: 83,
    justifyContent: "center",
  },

  metricHeading: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    marginBottom: 8,
  },

  metricIcon: {
    fontSize: 17,
    fontWeight: "600",
  },

  metricLabel: {
    fontSize: 12,
    flexShrink: 1,
  },

  metricValue: {
    fontSize: 17,
    fontWeight: "700",
  },

  guidanceBox: {
    padding: 14,
    borderRadius: 12,
    marginTop: 14,
    gap: 6,
  },

  guidanceTitle: {
    fontSize: 14,
    fontWeight: "700",
  },

  notice: {
    fontSize: 11,
    lineHeight: 16,
    marginTop: 12,
  },
});