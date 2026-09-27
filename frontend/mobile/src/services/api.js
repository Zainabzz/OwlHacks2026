const API_URL = process.env.EXPO_PUBLIC_API_URL;

export async function requestApi(path, options = {}) {
  if (!API_URL?.trim()) {
    throw new Error("EXPO_PUBLIC_API_URL is missing from frontend/mobile/.env");
  }
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 30000);
  try {
    const response = await fetch(`${API_URL.trim().replace(/\/+$/, "")}${path}`, {
      ...options,
      signal: controller.signal,
    });
    let data;
    try {
      data = await response.json();
    } catch {
      throw new Error("The server returned an invalid response. Check the API URL.");
    }
    if (!response.ok) {
      throw new Error(typeof data?.detail === "string" ? data.detail : "Unable to retrieve routes or places. Please try again.");
    }
    return data;
  } catch (error) {
    if (error.name === "AbortError") throw new Error("The server took too long to respond. Please try again.");
    if (error instanceof TypeError) throw new Error("Cannot reach the server. Check your connection and API URL.");
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}
