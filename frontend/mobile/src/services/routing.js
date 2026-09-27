import { requestApi } from "./api.js";

export const ROUTE_COLORS = ["#277A59", "#3288D1", "#D68A19"];
export const DARK_ROUTE_COLORS = ["#7BE0BF", "#45C4E8", "#FFCA75"];

export function isValidPoint(point) {
  return Number.isFinite(point?.latitude) && Math.abs(point.latitude) <= 90 &&
    Number.isFinite(point?.longitude) && Math.abs(point.longitude) <= 180;
}

export async function getRoutes(start, end) {
  if (!isValidPoint(start) || !isValidPoint(end)) {
    throw new Error("Choose valid starting and destination locations.");
  }
  const data = await requestApi("/api/routes", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      start: { latitude: start.latitude, longitude: start.longitude },
      destination: { latitude: end.latitude, longitude: end.longitude },
    }),
  });
  if (!Array.isArray(data?.routes) || data.routes.some(route =>
    !route || typeof route.id !== "string" || !Array.isArray(route.coordinates) ||
    route.coordinates.length < 2 || !route.coordinates.every(isValidPoint)
  ) || new Set(data.routes.map(route => route.id)).size !== data.routes.length) {
    throw new Error("The server returned invalid route data.");
  }
  if (!data.routes.length) throw new Error("No walking routes found between these locations.");
  return data.routes;
}
