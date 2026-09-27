import { useMemo } from "react";
import { StyleSheet } from "react-native";
import { WebView } from "react-native-webview";
import { createLeafletMapHtml } from "./leafletMapHtml";

export default function NavigationMap({ location, isDark }) {
  const latitude = location?.latitude ?? 39.9526;
  const longitude = location?.longitude ?? -75.1636;
  const html = useMemo(() => createLeafletMapHtml({
    center: [latitude, longitude],
    zoom: 14,
    isDark,
    start: location,
  }), [latitude, longitude, isDark, location]);

  return (
    <WebView
      source={{ html, baseUrl: "https://localhost" }}
      originWhitelist={["*"]}
      javaScriptEnabled
      domStorageEnabled
      bounces={false}
      style={styles.map}
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
