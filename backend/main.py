import asyncio
import math
import os
import logging
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from uuid import UUID
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

load_dotenv(Path(__file__).with_name(".env"))
app = FastAPI(title="OwlRoute API")
# Development only. Restrict origins before deployment.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
MAPBOX_TOKEN = os.getenv("MAPBOX_ACCESS_TOKEN")


class Point(BaseModel):
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)


class RouteRequest(BaseModel):
    start: Point
    destination: Point


def spatial_metrics(coordinates, duration, departure):
    # Optional spatial packages/data must not prevent basic routing from starting.
    if __package__:
        from .spatial import route_metrics
    else:
        from spatial import route_metrics
    return route_metrics(coordinates, duration, departure)


def number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) else None


async def mapbox_get(client, path, params):
    if not MAPBOX_TOKEN:
        raise HTTPException(503, "MAPBOX_ACCESS_TOKEN is not configured on the server")
    try:
        response = await client.get(f"https://api.mapbox.com/{path}", params={**params, "access_token": MAPBOX_TOKEN})
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError("Invalid response")
        return data
    except (httpx.HTTPError, ValueError) as exc:
        # Never return upstream request URLs: they contain the access token.
        raise HTTPException(502, "Mapbox is unavailable or rejected the request. Please try again.") from exc


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/search/suggest")
async def suggest_places(
    session_token: UUID,
    q: str = Query(min_length=2, max_length=256),
    latitude: float | None = Query(default=None, ge=-90, le=90),
    longitude: float | None = Query(default=None, ge=-180, le=180),
):
    params = {"q": q, "session_token": str(session_token), "limit": 5, "language": "en"}
    if latitude is not None and longitude is not None:
        params["proximity"] = f"{longitude},{latitude}"
    async with httpx.AsyncClient(timeout=15) as client:
        data = await mapbox_get(client, "search/searchbox/v1/suggest", params)
    return {"suggestions": [
        {"id": item["mapbox_id"], "name": item.get("name", "Destination"),
         "description": item.get("full_address") or item.get("place_formatted", "")}
        for item in data.get("suggestions", [])
        if isinstance(item, dict) and item.get("mapbox_id")
    ]}


@app.get("/api/search/retrieve")
async def retrieve_place(session_token: UUID, id: str = Query(min_length=1, max_length=512)):
    async with httpx.AsyncClient(timeout=15) as client:
        data = await mapbox_get(client, f"search/searchbox/v1/retrieve/{quote(id, safe='')}",
                                {"session_token": str(session_token)})
    try:
        feature = data["features"][0]
        longitude, latitude = feature["geometry"]["coordinates"][:2]
        point = Point(latitude=latitude, longitude=longitude)
        properties = feature.get("properties", {})
        return {"location": {**point.model_dump(), "name": properties.get("name") or properties.get("full_address") or "Destination"}}
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise HTTPException(502, "The selected place has no usable coordinates") from exc


async def fetch_conditions(client, point, air_quality=False):
    url = "https://air-quality-api.open-meteo.com/v1/air-quality" if air_quality else "https://api.open-meteo.com/v1/forecast"
    variables = "us_aqi" if air_quality else "temperature_2m,precipitation,rain,snowfall,wind_speed_10m,wind_direction_10m"
    try:
        response = await client.get(url, params={
            "latitude": point.latitude, "longitude": point.longitude,
            "current": variables, "timezone": "UTC",
        })
        response.raise_for_status()
        current = response.json().get("current", {})
        return current if isinstance(current, dict) else {}
    except (httpx.HTTPError, ValueError, AttributeError):
        # Optional environmental services must not prevent route selection.
        return {}


async def fetch_mapbox_routes(client, start, destination):
    coordinates = f"{start.longitude},{start.latitude};{destination.longitude},{destination.latitude}"
    result = await mapbox_get(client, f"directions/v5/mapbox/walking/{coordinates}", {
        "alternatives": "true", "geometries": "geojson", "overview": "full", "steps": "false",
    })
    if result.get("code") == "NoRoute":
        return []
    if result.get("code") != "Ok" or not isinstance(result.get("routes"), list):
        raise HTTPException(502, "Unable to calculate walking routes")
    return result["routes"]


@app.post("/api/routes")
async def calculate_routes(request: RouteRequest):
    async with httpx.AsyncClient(timeout=20) as client:
        mapbox_routes = await fetch_mapbox_routes(client, request.start, request.destination)
        weather, air = await asyncio.gather(
            fetch_conditions(client, request.start),
            fetch_conditions(client, request.start, air_quality=True),
        ) if mapbox_routes else ({}, {})

    snowfall = number(weather.get("snowfall"))
    observed_at = weather.get("time")
    snow = None if snowfall is None else f"{snowfall:g} cm snowfall · {observed_at or 'time unavailable'} UTC. Sidewalk ice/clearance unknown."
    routes = []
    generated_at = datetime.now(timezone.utc)
    for index, route in enumerate(mapbox_routes[:3]):
        try:
            coordinates = [Point(latitude=coord[1], longitude=coord[0]).model_dump()
                           for coord in route["geometry"]["coordinates"]]
            if len(coordinates) < 2:
                raise ValueError("Empty route")
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise HTTPException(502, "Mapbox returned invalid route geometry") from exc
        duration = number(route.get("duration"))
        try:
            spatial = await asyncio.to_thread(spatial_metrics, coordinates, duration, generated_at)
        except Exception:
            logging.getLogger(__name__).warning("Spatial estimates unavailable; check local datasets")
            spatial = {}
        routes.append({
            "id": f"route-{index + 1}", "name": f"Route {index + 1}", "coordinates": coordinates,
            "metrics": {
                "durationMinutes": round(duration / 60, 1) if duration is not None and duration >= 0 else None,
                "temperatureC": number(weather.get("temperature_2m")),
                "windImpact": None, "airQualityIndex": number(air.get("us_aqi")), "snowCondition": snow,
                "sunExposurePercent": None, "treeCanopyPercent": None,
                "buildingShadePercent": None, "rainExposurePercent": None,
                **spatial,
            },
            "metricContext": {
                "weatherScope": "Starting-point modeled conditions",
                "weatherTime": observed_at, "airQualityScope": "Estimated US AQI for the starting-point area",
                "airQualityTime": air.get("time"), "timezone": "UTC",
                "spatialQuality": "Estimated from local polygon coverage and flat-roof shadows; unavailable outside verified coverage",
                "spatialTime": generated_at.isoformat(),
            },
            "sidewalkGuidance": None, "isDemo": False,
        })
    return {
        "routes": routes,
        "weather": {
            "temperatureC": number(weather.get("temperature_2m")),
            "precipitationMm": number(weather.get("precipitation")),
            "rainMm": number(weather.get("rain")), "snowfallCm": snowfall,
            "windSpeedKmh": number(weather.get("wind_speed_10m")),
            "windDirectionDegrees": number(weather.get("wind_direction_10m")), "observedAt": observed_at,
        },
        "airQuality": {"usAqi": number(air.get("us_aqi")), "observedAt": air.get("time")},
        "generatedAt": generated_at.isoformat(),
        "weatherScope": "Starting-point modeled conditions",
    }