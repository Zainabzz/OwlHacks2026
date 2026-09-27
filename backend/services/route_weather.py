"""Distance-weighted current weather estimates along walking-route geometry."""
import asyncio
import math

from .weather import get_weather, numeric, scaled

FIELDS = (
    "temperatureC", "feelsLikeC", "humidityPercent", "precipitationMm", "rainMm",
    "snowfallCm", "snowWaterEquivalentMm", "cloudCoverPercent", "windSpeedKmh",
)


def route_samples(coordinates):
    segments = []
    total = 0
    for a, b in zip(coordinates, coordinates[1:]):
        lat1, lat2 = map(math.radians, (a["latitude"], b["latitude"]))
        delta = (b["longitude"] - a["longitude"] + 180) % 360 - 180
        hav = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(math.radians(delta) / 2) ** 2
        length = 2 * 6371000 * math.asin(math.sqrt(min(1, hav)))
        if length > 0:
            segments.append((total, length, a, b, delta))
            total += length
    if not segments:
        return [(coordinates[0], 1)]
    samples = []
    for index in range(5):
        distance = total * index / 4
        offset, length, a, b, delta = next((s for s in segments if s[0] + s[1] >= distance), segments[-1])
        fraction = min(1, max(0, (distance - offset) / length))
        point = {"latitude": a["latitude"] + fraction * (b["latitude"] - a["latitude"]),
                 "longitude": (a["longitude"] + fraction * delta + 180) % 360 - 180}
        # Trapezoidal integration: endpoints represent half an interval.
        samples.append((point, 0.125 if index in (0, 4) else 0.25))
    return samples


def average_weather(values, weights):
    result = {}
    for field in FIELDS:
        valid = [(value[field], weight) for value, weight in zip(values, weights) if numeric(value.get(field)) is not None]
        result[field] = round(sum(value * weight for value, weight in valid) / sum(weight for _, weight in valid), 2) if valid else None
    result["temperatureF"] = scaled(result["temperatureC"], 9 / 5, 32)
    result["feelsLikeF"] = scaled(result["feelsLikeC"], 9 / 5, 32)
    result["windSpeedMph"] = scaled(result["windSpeedKmh"], 1 / 1.609344)
    for field in ("rain", "precipitation"):
        result[field + "Inches"] = scaled(result[field + "Mm"], 1 / 25.4)
    times = sorted({value["weatherTime"] for value in values if value.get("weatherTime")})
    result["weatherTime"] = times[0] if times else None
    result["weatherTimeEnd"] = times[-1] if times else None
    valid_weights = [weight for value, weight in zip(values, weights) if numeric(value.get("temperatureC")) is not None]
    result["sampleCount"] = len(values)
    result["availableSamples"] = len(valid_weights)
    result["coveragePercent"] = round(sum(valid_weights) * 100)
    return result


async def get_route_weather(coordinates, client):
    samples = route_samples(coordinates)
    results = await asyncio.gather(*(get_weather(point["latitude"], point["longitude"], client) for point, _ in samples))
    weights = [weight for _, weight in samples]
    average = average_weather(results, weights)
    sources = {result["source"] for result in results if result.get("source")}
    providers = {}
    for key, name in (("openMeteo", "Open-Meteo"), ("openWeather", "OpenWeather")):
        entries = [result["providers"][key] for result in results]
        data = average_weather([entry.get("data") or {} for entry in entries], weights)
        available = data["availableSamples"] > 0
        providers[key] = {"name": name, "status": "ok" if available else "unavailable",
                          "data": data if available else None,
                          "error": None if available else entries[0]["error"]}
    return {**average, "providers": providers, "source": next(iter(sources)) if len(sources) == 1 else "mixed" if sources else None,
            "status": "ok" if average["availableSamples"] else "unavailable", "timezone": "UTC",
            "scope": "Distance-weighted route average", "method": "Five equally spaced samples along the route, weighted by distance; current conditions, not an arrival forecast."}
