"""Philadelphia route exposure estimates from arrival-time Open-Meteo forecasts."""
import asyncio
import logging
import math
from bisect import bisect_left
from datetime import timedelta

import httpx
from astral import Observer
from astral.sun import elevation
from shapely.geometry import LineString
from shapely.ops import substring, transform

if __package__ == "backend.services":
    from ..spatial import PROJECT, UNPROJECT
else:
    from spatial import PROJECT, UNPROJECT
from .weather import OPEN_METEO_URL, numeric

FIELDS = "direct_normal_irradiance,rain,showers,wind_speed_10m,wind_direction_10m"
EMPTY = {"sunExposurePercent": None, "rainExposurePercent": None, "windImpact": None}
EXPOSURE_TIMEOUT = 15.0
LOGGER = logging.getLogger(__name__)


def sample_route(coordinates, duration, departure):
    if numeric(duration) is None or duration <= 0 or len(coordinates) < 2 or not all(
        -75.30 <= p["longitude"] <= -74.95 and 39.85 <= p["latitude"] <= 40.15 for p in coordinates
    ):
        return []
    route = transform(PROJECT, LineString([(p["longitude"], p["latitude"]) for p in coordinates]))
    if route.length <= 0:
        return []
    samples = []
    for index in range(12):
        piece = substring(route, route.length * index / 12, route.length * (index + 1) / 12)
        midpoint = piece.interpolate(.5, normalized=True)
        longitude, latitude = UNPROJECT(midpoint.x, midpoint.y)
        # Keep each bend: averaging bearings first would erase opposing headwinds.
        headings = []
        for a, b in zip(piece.coords, list(piece.coords)[1:]):
            dx, dy = b[0] - a[0], b[1] - a[1]
            length = math.hypot(dx, dy)
            if length:
                headings.append((math.degrees(math.atan2(dx, dy)) % 360, length / piece.length))
        samples.append({"latitude": latitude, "longitude": longitude, "headings": headings,
                        "arrival": departure + timedelta(seconds=duration * (index + .5) / 12)})
    return samples


def forecast_values(payload, arrival):
    """Accumulations use the hour ENDING after arrival; wind uses the nearest hour."""
    hourly = payload.get("hourly", {}) if isinstance(payload, dict) else {}
    if not isinstance(hourly, dict):
        return {}
    times = hourly.get("time", [])
    if not isinstance(times, list) or not times or any(numeric(t) is None for t in times):
        return {}
    if any(a >= b for a, b in zip(times, times[1:])):
        return {}
    timestamp = arrival.timestamp()
    end = bisect_left(times, timestamp)
    if end >= len(times) or timestamp < times[0] - 3600:
        return {}
    nearest = end - 1 if end > 0 and timestamp - times[end - 1] < times[end] - timestamp else end
    result = {}
    for field in FIELDS.split(","):
        index = nearest if field.startswith("wind_") else end
        values = hourly.get(field, [])
        result[field] = numeric(values[index]) if isinstance(values, list) and index < len(values) else None
    return result


def summarize(samples, payloads):
    scores = {key: [] for key in EMPTY}
    for sample, payload in zip(samples, payloads):
        values = forecast_values(payload, sample["arrival"])
        night = elevation(Observer(latitude=sample["latitude"], longitude=sample["longitude"]), sample["arrival"]) <= 0
        radiation = values.get("direct_normal_irradiance")
        if night or (radiation is not None and radiation >= 0):
            scores["sunExposurePercent"].append(0 if night else 100 if radiation >= 120 else 0)
        rain, showers = values.get("rain"), values.get("showers")
        if rain is not None and showers is not None and min(rain, showers) >= 0:
            scores["rainExposurePercent"].append(100 if rain + showers >= .1 else 0)
        speed, direction = values.get("wind_speed_10m"), values.get("wind_direction_10m")
        if speed == 0:
            scores["windImpact"].append(0)
        elif speed is not None and speed > 0 and direction is not None and 0 <= direction <= 360:
            headwind = sum(max(0, speed * math.cos(math.radians(direction - bearing))) * weight
                           for bearing, weight in sample["headings"])
            scores["windImpact"].append(headwind)
    metrics = {key: round(sum(values) / len(values), 1) if values else None for key, values in scores.items()}
    coverage = {key: round(len(values) / len(samples) * 100) for key, values in scores.items()}
    return {"metrics": metrics, "coveragePercent": coverage,
            "status": "ok" if all(value == 100 for value in coverage.values()) else "partial" if any(coverage.values()) else "unavailable",
            "source": "Open-Meteo", "sampleCount": len(samples)}


async def get_route_exposure(coordinates, duration, departure, client):
    samples = sample_route(coordinates, duration, departure)
    if not samples:
        return {"metrics": dict(EMPTY), "coveragePercent": {}, "status": "unsupported", "source": None,
                "message": "Exposure estimates require a walking route within the Philadelphia area."}
    params = {
        "latitude": ",".join(str(round(s["latitude"], 5)) for s in samples),
        "longitude": ",".join(str(round(s["longitude"], 5)) for s in samples),
        "hourly": FIELDS, "wind_speed_unit": "mph", "precipitation_unit": "mm",
        "timezone": "UTC", "timeformat": "unixtime",
        "start_hour": departure.replace(minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M"),
        "end_hour": (samples[-1]["arrival"] + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M"),
    }
    try:
        response = await asyncio.wait_for(
            client.get(OPEN_METEO_URL, params=params, timeout=EXPOSURE_TIMEOUT),
            EXPOSURE_TIMEOUT,
        )
        response.raise_for_status()
        payloads = response.json()
        if not isinstance(payloads, list) or len(payloads) != len(samples):
            raise ValueError("Invalid forecast response")
        result = summarize(samples, payloads)
        if result["status"] == "unavailable":
            result["message"] = "Forecast returned no usable hourly data."
        return result
    except httpx.HTTPStatusError as exc:
        LOGGER.warning("Route exposure forecast returned HTTP %s", exc.response.status_code)
        message = f"Forecast provider returned HTTP {exc.response.status_code}."
    except (httpx.TimeoutException, asyncio.TimeoutError):
        LOGGER.warning("Route exposure forecast timed out")
        message = "Forecast provider timed out."
    except httpx.HTTPError as exc:
        LOGGER.warning("Route exposure forecast connection failed (%s)", type(exc).__name__)
        message = "Unable to connect to the forecast provider."
    except (ValueError, TypeError, AttributeError):
        LOGGER.warning("Route exposure forecast response was invalid")
        message = "Forecast provider returned invalid data."
    result = summarize(samples, [{} for _ in samples])
    result["message"] = message
    return result


def apply_shade(exposure, spatial):
    result = {**exposure, "metrics": dict(exposure["metrics"])}
    unshaded = numeric(spatial.get("sunExposurePercent"))
    sun = result["metrics"]["sunExposurePercent"]
    adjusted = unshaded is not None and sun is not None
    if adjusted:
        result["metrics"]["sunExposurePercent"] = round(sun * unshaded / 100, 1)
    result["sunBasis"] = "weather-and-shade" if adjusted else "open-sky"
    return result
