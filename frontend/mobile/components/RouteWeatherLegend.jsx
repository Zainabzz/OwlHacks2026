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
import { formatDuration } from "../src/services/formatting";

const METRICS = [
  {
    key: "durationMinutes",
    label: "Travel time",
    icon: "◷",
  },
  {
    key: "distanceMiles",
    label: "Distance",
    icon: "↔",
    unit: " mi",
  },
  {
    key: "sunExposurePercent",
    label: "Sun exposure",
    icon: "☀",
    unit: "%",
  },
  {
    key: "treeCanopyPercent",
    label: "Tree canopy coverage",
    icon: "♧",
    unit: "%",
  },
  {
    key: "buildingShadePercent",
    label: "Estimated building shade",
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
    key: "temperatureF",
    label: "Average temperature",
    icon: "°",
    unit: "°F",
  },
  {
    key: "windImpact",
    label: "Wind impact",
    icon: "≋",
    unit: " mph",
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
    if (metric.key === "durationMinutes") return formatDuration(value);
    if (metric.key === "distanceMiles") return `${value.toFixed(2)} mi`;
    return `${Math.round(value * 10) / 10}${metric.unit || ""}`;
  }

  return String(value);
}

function MetricCard({ metric, value, theme, detail }) {
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
      {!!detail && <Text style={{ color: theme.textSecondary, fontSize: 11, marginTop: 6 }}>{detail}</Text>}
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
  const exposure = activeRoute?.exposure;
  const exposureDetails = {
    sunExposurePercent: exposure?.sunBasis === "weather-and-shade" ? "Sunshine estimate with route shade" : "Sunshine estimate · open sky",
    rainExposurePercent: "Walk in forecast rain · no shelter adjustment",
    windImpact: "Average headwind · regional estimate",
  };
  const metricDetail = key => {
    if (key === "treeCanopyPercent") return "Unavailable: tree locations do not include canopy outlines.";
    if (key === "buildingShadePercent") {
      if (exposure?.spatialStatus === "nighttime") return "No direct sun at estimated arrival time; building shade is not applicable.";
      return "Estimated from Philadelphia footprints and approximate heights using a flat-roof shadow model.";
    }
    if (!exposureDetails[key]) return null;
    if (exposure?.status === "unsupported") return "Philadelphia routes only";
    const coverage = exposure?.coveragePercent?.[key];
    if (coverage === 0) return "Forecast unavailable";
    return exposureDetails[key] + (coverage > 0 && coverage < 100 ? ` · ${coverage}% forecast coverage` : "");
  };

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
              const isPreferred = route.isPreferred ?? (index === 0);

              return (
                <TouchableOpacity
                  key={route.id}
                  onPress={() => onSelectRoute(route.id)}
                  accessibilityRole="button"
                  accessibilityLabel={`${route.name}${isPreferred ? ", preferred route" : ""}${route.metrics?.durationMinutes != null ? `, ${formatDuration(route.metrics.durationMinutes)}` : ""}${Number.isFinite(route.metrics?.distanceMiles) ? `, ${route.metrics.distanceMiles.toFixed(2)} miles` : ""}`}
                  style={[
                    styles.routeChip,
                    {
                      backgroundColor: active
                        ? (isDark ? "#1E2D25" : "#E8F5E9")
                        : theme.surfaceSecondary,
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

                  <View style={styles.chipTextContainer}>
                    <View style={styles.chipHeaderRow}>
                      <Text
                        style={{
                          color: theme.text,
                          fontWeight: active ? "700" : "600",
                          fontSize: 14,
                        }}
                      >
                        {route.name}
                      </Text>
                      {isPreferred && (
                        <View
                          style={[
                            styles.chipBadge,
                            {
                              backgroundColor: isDark
                                ? "#143D27"
                                : "#C8E6C9",
                            },
                          ]}
                        >
                          <Text
                            style={[
                              styles.chipBadgeText,
                              {
                                color: isDark
                                  ? "#7BE0BF"
                                  : "#1B5E20",
                              },
                            ]}
                          >
                            Preferred
                          </Text>
                        </View>
                      )}
                    </View>
                    {route.metrics?.durationMinutes !== null && route.metrics?.durationMinutes !== undefined && (
                      <Text
                        style={{
                          color: theme.textSecondary,
                          fontSize: 12,
                          marginTop: 2,
                        }}
                      >
                        {formatDuration(route.metrics.durationMinutes)}
                      </Text>
                    )}
                  </View>
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

                {(activeRoute.isPreferred ?? (activeIndex === 0)) ? (
                  <View
                    style={[
                      styles.preferredBadge,
                      {
                        backgroundColor: isDark
                          ? "#143D27"
                          : "#C8E6C9",
                      },
                    ]}
                  >
                    <Text
                      style={[
                        styles.preferredBadgeText,
                        {
                          color: isDark
                            ? "#7BE0BF"
                            : "#1B5E20",
                        },
                      ]}
                    >
                      ★ Preferred Route
                    </Text>
                  </View>
                ) : (
                  <View
                    style={[
                      styles.altBadge,
                      {
                        backgroundColor: theme.surfaceSecondary,
                        borderColor: theme.border,
                        borderWidth: 1,
                      },
                    ]}
                  >
                    <Text
                      style={[
                        styles.altBadgeText,
                        { color: theme.textSecondary },
                      ]}
                    >
                      Alternative {activeIndex}
                    </Text>
                  </View>
                )}
              </View>

              <View style={styles.metricsGrid}>
                {METRICS.map((metric) => (
                  <View
                    key={metric.key}
                    style={styles.metricColumn}
                  >
                    <MetricCard
                      metric={metric}
                      value={metric.key === "buildingShadePercent" && exposure?.spatialStatus === "nighttime"
                        ? "Nighttime"
                        : metrics[metric.key]}
                      detail={metricDetail(metric.key)}
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

              {exposure && (
                <Text style={[styles.notice, { color: theme.textSecondary }]}>
                Exposure: Open-Meteo forecast at estimated arrival times, assuming a steady walking pace.
                {exposure.sunBasis === "open-sky" ? " Sun estimate excludes building and tree shade." : " Sun estimate combines forecast sunshine with modeled building shade; tree canopy data is unavailable."}
                {" "}Rain shows the share of the walk in hours with at least 0.1 mm of rain; it is not rain probability. Wind excludes street-level shelter.
                </Text>
              )}
              {activeRoute.metricContext && (
                <Text style={[styles.notice, { color: theme.textSecondary }]}>
                  Weather: route average{activeRoute.weather?.coveragePercent < 100 ? " (partial coverage)" : ""} · {activeRoute.metricContext.weatherTime || "unavailable"} UTC.
                  {"\n"}Area AQI: {activeRoute.metricContext.airQualityTime || "unavailable"} UTC. Sidewalk ice conditions unavailable.
                  {"\n"}Weather: {activeRoute.metricContext.weatherSource === "openWeather" ? "OpenWeather" : activeRoute.metricContext.weatherSource === "openMeteo" ? "Open-Meteo" : activeRoute.metricContext.weatherSource === "mixed" ? "Open-Meteo / OpenWeather" : "unavailable"}. Air quality: CAMS via Open-Meteo.
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

  chipTextContainer: {
    flexDirection: "column",
  },

  chipHeaderRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },

  chipBadge: {
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 6,
  },

  chipBadgeText: {
    fontSize: 10,
    fontWeight: "700",
  },

  routeDot: {
    width: 11,
    height: 11,
    borderRadius: 6,
  },

  activeHeading: {
    flexDirection: "row",
    flexWrap: "wrap",
    alignItems: "center",
    gap: 10,
    marginBottom: 14,
    marginTop: 4,
  },

  activeTitle: {
    fontSize: 17,
    fontWeight: "700",
  },

  preferredBadge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 8,
  },

  preferredBadgeText: {
    fontSize: 12,
    fontWeight: "700",
  },

  altBadge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 8,
  },

  altBadgeText: {
    fontSize: 12,
    fontWeight: "600",
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
