import { requestApi } from "./api.js";
import { isValidPoint } from "./routing.js";

export async function fetchWeather(latitude, longitude) {
  if (!isValidPoint({ latitude, longitude })) throw new Error("Choose a valid location to load weather.");
  const params = new URLSearchParams({ latitude: String(latitude), longitude: String(longitude) });
  const data = await requestApi(`/api/weather?${params}`);
  if (!data?.providers || !["ok", "unavailable"].includes(data.status)) {
    throw new Error("The server returned invalid weather data.");
  }
  return data;
}
