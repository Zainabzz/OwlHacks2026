import { useEffect, useMemo, useRef, useState } from "react";
import { StyleSheet } from "react-native";
import { WebView } from "react-native-webview";
import { createLeafletMapHtml } from "./leafletMapHtml";

export default function RouteMap({
  start,
  end,
  routes = [],
  selectedRoute,
  onSelectRoute,
  isDark,
}) {
  const mapRef = useRef(null);
  const [mapReady, setMapReady] = useState(false);
  const html = useMemo(() => createLeafletMapHtml({
    center: [start.latitude, start.longitude],
    start,
    end,
    routes,
    isDark,
  }), [start, end, routes, isDark]);

  useEffect(() => {
    if (!mapReady) return;
    const selected = JSON.stringify(selectedRoute);
    mapRef.current?.injectJavaScript(`window.setSelectedRoute(${selected}); true;`);
  }, [mapReady, selectedRoute]);

  return (
    <WebView
      ref={mapRef}
      source={{ html, baseUrl: "https://localhost" }}
      originWhitelist={["*"]}
      javaScriptEnabled
      domStorageEnabled
      bounces={false}
      style={styles.map}
      onLoadStart={() => setMapReady(false)}
      onMessage={(event) => {
        try {
          const message = JSON.parse(event.nativeEvent.data);
          if (message.type === "map-ready") setMapReady(true);
          if (message.type === "select-route") onSelectRoute(message.id);
        } catch {
          // Ignore messages that are not part of the map bridge.
        }
      }}
    />
  );
}

const styles = StyleSheet.create({
  map: {
    flex: 1,
    width: "100%",
    height: "100%",
  },
});
