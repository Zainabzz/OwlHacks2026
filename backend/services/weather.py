"""Server-side weather providers. Credentials and raw upstream errors stay here."""
import asyncio
import math
import os
from datetime import datetime, timezone

import httpx

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
OPENWEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"
PROVIDER_TIMEOUT = 8.0


def numeric(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) else None


def scaled(value, factor, offset=0):
    value = numeric(value)
    return round(value * factor + offset, 2) if value is not None else None


def normalize_meteo(data):
    current = data["current"]
    if not isinstance(current, dict) or numeric(current.get("temperature_2m")) is None:
        raise ValueError("Missing weather data")
    return {
        "temperatureC": numeric(current.get("temperature_2m")),
        "feelsLikeC": numeric(current.get("apparent_temperature")),
        "humidityPercent": numeric(current.get("relative_humidity_2m")),
        "precipitationMm": numeric(current.get("precipitation")),
        "rainMm": numeric(current.get("rain")),
        "snowfallCm": numeric(current.get("snowfall")),
        "cloudCoverPercent": numeric(current.get("cloud_cover")),
        "windSpeedKmh": numeric(current.get("wind_speed_10m")),
        "windDirectionDegrees": numeric(current.get("wind_direction_10m")),
        "isDay": bool(current["is_day"]) if current.get("is_day") in (0, 1) else None,
        "weatherTime": current.get("time"),
    }


def normalize_openweather(data):
    current = data["main"]
    if numeric(current.get("temp")) is None:
        raise ValueError("Missing weather data")
    timestamp = numeric(data.get("dt"))
    return {
        "temperatureC": numeric(current.get("temp")),
        "feelsLikeC": numeric(current.get("feels_like")),
        "humidityPercent": numeric(current.get("humidity")),
        "precipitationMm": None,
        "rainMm": numeric((data.get("rain") or {}).get("1h")),
        # OpenWeather snow is mm water equivalent, not cm snowfall depth.
        "snowfallCm": None,
        "snowWaterEquivalentMm": numeric((data.get("snow") or {}).get("1h")),
        "cloudCoverPercent": numeric((data.get("clouds") or {}).get("all")),
        "windSpeedKmh": scaled((data.get("wind") or {}).get("speed"), 3.6),
        "windDirectionDegrees": numeric((data.get("wind") or {}).get("deg")),
        "isDay": None,
        "weatherTime": datetime.fromtimestamp(timestamp, timezone.utc).isoformat() if timestamp is not None else None,
    }


async def fetch_provider(client, name, url, params, normalize):
    try:
        response = await asyncio.wait_for(client.get(url, params=params, timeout=PROVIDER_TIMEOUT), PROVIDER_TIMEOUT)
        response.raise_for_status()
        values = normalize(response.json())
        values.update({
            "temperatureF": scaled(values.get("temperatureC"), 9 / 5, 32),
            "feelsLikeF": scaled(values.get("feelsLikeC"), 9 / 5, 32),
            "windSpeedMph": scaled(values.get("windSpeedKmh"), 1 / 1.609344),
            "precipitationInches": scaled(values.get("precipitationMm"), 1 / 25.4),
            "rainInches": scaled(values.get("rainMm"), 1 / 25.4),
        })
        return {"name": name, "status": "ok", "data": values, "error": None}
    except httpx.HTTPStatusError as exc:
        code = exc.response.status_code
        message = "API key was rejected; check the server key and account access." if code in (401, 403) else (
            "Rate limit reached. Try again later." if code == 429 else f"Provider returned HTTP {code}.")
    except (httpx.TimeoutException, asyncio.TimeoutError):
        message = "Provider timed out. Try again."
    except httpx.HTTPError:
        message = "Cannot connect to the weather provider."
    except (ValueError, KeyError, TypeError, AttributeError, OverflowError, OSError):
        message = "Provider returned invalid weather data."
    return {"name": name, "status": "unavailable", "data": None, "error": message}


async def get_weather(latitude: float, longitude: float, client=None):
    if client is None:
        async with httpx.AsyncClient(timeout=PROVIDER_TIMEOUT) as owned_client:
            return await get_weather(latitude, longitude, owned_client)

    async def openweather():
        # Read at request time, after main.py has loaded backend/.env.
        key = (os.getenv("OPENWEATHER_API") or os.getenv("OPENWEATHER_API_KEY") or "").strip()
        if not key:
            return {"name": "OpenWeather", "status": "not_configured", "data": None,
                    "error": "OPENWEATHER_API is not configured on the server."}
        return await fetch_provider(client, "OpenWeather", OPENWEATHER_URL,
                                    {"lat": latitude, "lon": longitude, "appid": key, "units": "metric"}, normalize_openweather)

    meteo, keyed = await asyncio.gather(
        fetch_provider(client, "Open-Meteo", OPEN_METEO_URL, {
            "latitude": latitude, "longitude": longitude,
            "current": "temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,rain,snowfall,cloud_cover,wind_speed_10m,wind_direction_10m,is_day",
            "temperature_unit": "celsius", "wind_speed_unit": "kmh", "precipitation_unit": "mm", "timezone": "UTC",
        }, normalize_meteo),
        openweather(),
    )
    source = "openMeteo" if meteo["status"] == "ok" else "openWeather" if keyed["status"] == "ok" else None
    chosen = meteo if source == "openMeteo" else keyed
    return {**(chosen["data"] or {}), "source": source, "timezone": "UTC",
            "status": "ok" if source else "unavailable", "providers": {"openMeteo": meteo, "openWeather": keyed}}
