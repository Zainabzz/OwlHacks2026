import { requestApi } from "./api.js";
import { isValidPoint } from "./routing.js";

// A non-secret identifier groups suggestions and retrieval into one search session.
export function createSearchSession() {
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, char => {
    const value = Math.floor(Math.random() * 16);
    return (char === "x" ? value : (value & 3) | 8).toString(16);
  });
}

export function parseCoordinateLocation(query) {
  const parts = query.trim().split(",");
  if (parts.length !== 2 || parts.some(part => !/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$/.test(part.trim()))) return null;
  const [latitude, longitude] = parts.map(Number);
  const point = { latitude, longitude, name: `${latitude}, ${longitude}` };
  return isValidPoint(point) ? point : null;
}

export async function suggestPlaces(query, sessionToken, location) {
  const coordinates = parseCoordinateLocation(query);
  if (coordinates) return [{ id: "coordinates", name: coordinates.name, description: "Use these coordinates", location: coordinates }];
  const params = new URLSearchParams({ q: query, session_token: sessionToken });
  if (isValidPoint(location)) {
    params.set("latitude", String(location.latitude));
    params.set("longitude", String(location.longitude));
  }
  const data = await requestApi(`/api/search/suggest?${params}`);
  if (!Array.isArray(data?.suggestions)) throw new Error("Invalid destination search response.");
  return data.suggestions;
}

export async function retrievePlace(id, sessionToken) {
  const params = new URLSearchParams({ id, session_token: sessionToken });
  const data = await requestApi(`/api/search/retrieve?${params}`);
  if (!isValidPoint(data?.location)) throw new Error("This destination has no valid coordinates.");
  return data.location;
}
