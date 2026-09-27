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
if __package__:
    from .services.weather import get_weather
    from .services.route_weather import get_route_weather
    from .services.exposure import get_route_exposure, apply_shade
else:
    from services.weather import get_weather
    from services.route_weather import get_route_weather
    from services.exposure import get_route_exposure, apply_shade

load_dotenv(Path(__file__).with_name(".env"))
app = FastAPI(title="OwlRoute API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
MAPBOX_TOKEN = os.getenv("MAPBOX_ACCESS_TOKEN")

class Point(BaseModel):
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)

class RouteRequest(BaseModel):
    start: Point
    destination: Point

def spatial_metrics(coordinates, duration, departure):
    if __package__:
        from .spatial import route_metrics
    else:
        from spatial import route_metrics
    return route_metrics(coordinates, duration, departure)

def route_spatial_status(coordinates, duration, departure):
    if __package__:
        from .spatial import route_is_nighttime
    else:
        from spatial import route_is_nighttime
    nighttime = route_is_nighttime(coordinates, duration, departure)
    return "nighttime" if nighttime is True else "daytime" if nighttime is False else "unavailable"

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
    suggestions = data.get("suggestions")
    if not isinstance(suggestions, list):
        raise HTTPException(502, "Mapbox returned invalid search suggestions. Please try again.")
    return {"suggestions": [
        {"id": item["mapbox_id"], "name": item.get("name", "Destination"),
         "description": item.get("full_address") or item.get("place_formatted", "")}
        for item in suggestions
        if isinstance(item, dict) and item.get("mapbox_id")
    ]}

@app.get("/api/search/retrieve")
async def retrieve_place(session_token: UUID, id: str = Query(min_length=1, max_length=16384)):
    async with httpx.AsyncClient(timeout=15) as client:
        data = await mapbox_get(client, f"search/searchbox/v1/retrieve/{quote(id, safe='')}",
                                {"session_token": str(session_token)})
    try:
        feature = data["features"][0]
        longitude, latitude = feature["geometry"]["coordinates"][:2]
        point = Point(latitude=latitude, longitude=longitude)
        properties = feature.get("properties", {})
        return {"location": {**point.model_dump(), "name": properties.get("name") or properties.get("full_address") or "Destination"}}
    except (KeyError, IndexError, TypeError, ValueError, AttributeError) as exc:
        raise HTTPException(502, "The selected place has no usable coordinates") from exc

async def fetch_air_quality(client, point):
    url = "https://air-quality-api.open-meteo.com/v1/air-quality"
    variables = "us_aqi"
    try:
        response = await client.get(url, params={
            "latitude": point.latitude, "longitude": point.longitude,
            "current": variables, "timezone": "UTC",
        })
        response.raise_for_status()
        current = response.json().get("current", {})
        return current if isinstance(current, dict) else {}
    except (httpx.HTTPError, ValueError, AttributeError):
        return {}

def validate_route_geometry(route):
    try:
        coordinates = [Point(latitude=coord[1], longitude=coord[0]).model_dump()
                       for coord in route["geometry"]["coordinates"]]
        if len(coordinates) < 2:
            raise ValueError("Empty route")
        return coordinates
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise HTTPException(502, "Mapbox returned invalid route geometry") from exc


def route_similarity(coords_a, coords_b):
    if not coords_a or not coords_b:
        return 0.0
    set_a = {(round(c[0] * 5000), round(c[1] * 5000)) for c in coords_a}
    set_b = {(round(c[0] * 5000), round(c[1] * 5000)) for c in coords_b}
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 1.0


async def fetch_mapbox_routes(client, start, destination):
    coordinates = f"{start.longitude},{start.latitude};{destination.longitude},{destination.latitude}"
    result = await mapbox_get(client, f"directions/v5/mapbox/walking/{coordinates}", {
        "alternatives": "true", "geometries": "geojson", "overview": "full", "steps": "false",
    })
    if result.get("code") == "NoRoute":
        return []
    if result.get("code") != "Ok" or not isinstance(result.get("routes"), list):
        raise HTTPException(502, "Unable to calculate walking routes")

    primary_routes = result["routes"]
    for route in primary_routes:
        validate_route_geometry(route)
    if not primary_routes:
        return []


    all_routes = list(primary_routes)
    direct_route = primary_routes[0]
    direct_dist = number(direct_route.get("distance")) or 0

    s_lat, s_lng = start.latitude, start.longitude
    d_lat, d_lng = destination.latitude, destination.longitude
    mid_lat = (s_lat + d_lat) / 2
    mid_lng = (s_lng + d_lng) / 2
    dy = (d_lat - s_lat) * 111000
    dx = (d_lng - s_lng) * 111000 * math.cos(math.radians(mid_lat))
    dist = math.hypot(dx, dy)

    if len(primary_routes) < 3 and dist >= 30 and abs(math.cos(math.radians(mid_lat))) > 1e-6:
        perp_x = -dy / dist
        perp_y = dx / dist
        base_offset = max(60.0, min(dist * 0.25, 350.0))

        candidates_params = [
            (0.5, 1.0),
            (0.5, -1.0),
            (0.35, 1.2),
            (0.65, -1.2),
            (0.35, -1.2),
            (0.65, 1.2),
            (0.5, 1.8),
            (0.5, -1.8),
        ]

        async def fetch_waypoint_route(frac, factor):
            f_lat = s_lat + frac * (d_lat - s_lat)
            f_lng = s_lng + frac * (d_lng - s_lng)
            off = base_offset * factor
            wp_lat = f_lat + (perp_y * off) / 111000
            wp_lng = f_lng + (perp_x * off) / (111000 * math.cos(math.radians(mid_lat)))
            if not (-90 <= wp_lat <= 90 and -180 <= wp_lng <= 180):
                return None
            try:
                res = await asyncio.wait_for(mapbox_get(
                    client,
                    f"directions/v5/mapbox/walking/{s_lng},{s_lat};{wp_lng:.6f},{wp_lat:.6f};{d_lng},{d_lat}",
                    {"geometries": "geojson", "overview": "full", "steps": "false"}
                ), timeout=3)
                if res.get("code") == "Ok" and isinstance(res.get("routes"), list) and res["routes"]:
                    candidate = res["routes"][0]
                    validate_route_geometry(candidate)
                    return candidate
            except (HTTPException, asyncio.TimeoutError):
                pass
            return None

        waypoint_results = await asyncio.gather(*[fetch_waypoint_route(frac, factor) for frac, factor in candidates_params])
        for r in waypoint_results:
            if r and isinstance(r, dict) and "geometry" in r and "coordinates" in r["geometry"]:
                all_routes.append(r)

    unique = [direct_route]
    remaining = [r for r in all_routes[1:] if (number(r.get("distance")) or 0) <= (direct_dist * 2.2 if direct_dist > 0 else 999999)]
    remaining.sort(key=lambda r: number(r.get("duration")) if number(r.get("duration")) is not None else math.inf)

    for cand in remaining:
        cand_coords = cand.get("geometry", {}).get("coordinates", [])
        is_dup = False
        for u in unique:
            u_coords = u.get("geometry", {}).get("coordinates", [])
            if route_similarity(cand_coords, u_coords) > 0.75:
                is_dup = True
                break
        if not is_dup:
            unique.append(cand)
            if len(unique) >= 3:
                break

    return unique

@app.post("/api/routes")
async def calculate_routes(request: RouteRequest):
    generated_at = datetime.now(timezone.utc)
    async with httpx.AsyncClient(timeout=20) as client:
        mapbox_routes = await fetch_mapbox_routes(client, request.start, request.destination)
        geometries = [validate_route_geometry(route) for route in mapbox_routes[:3]]
        route_weather, air, exposures = await asyncio.gather(
            asyncio.gather(*(get_route_weather(coordinates, client) for coordinates in geometries)),
            fetch_air_quality(client, request.start),
            asyncio.gather(*(get_route_exposure(coordinates, number(route.get("duration")), generated_at, client)
                             for route, coordinates in zip(mapbox_routes[:3], geometries))),
        ) if geometries else ([], {}, [])

    routes = []
    for index, (route, coordinates, weather) in enumerate(zip(mapbox_routes[:3], geometries, route_weather)):
        snowfall = number(weather.get("snowfallCm"))
        observed_at = weather.get("weatherTime")
        snow = None if snowfall is None else f"{snowfall:g} cm average snowfall · {observed_at or 'time unavailable'} UTC. Sidewalk ice/clearance unknown."
        duration = number(route.get("duration"))
        try:
            spatial = await asyncio.to_thread(spatial_metrics, coordinates, duration, generated_at)
        except Exception:
            logging.getLogger(__name__).warning("Spatial estimates unavailable; check local datasets")
            spatial = {}
        exposure = apply_shade(exposures[index], spatial)
        exposure["spatialStatus"] = route_spatial_status(coordinates, duration, generated_at)
        exposure["limitations"] = [
            "The downloaded 2025 tree inventory contains trunk points, not crown outlines; tree canopy coverage is unavailable.",
            "Building shade uses approximate footprint heights and a flat-roof shadow model; it is an estimate, not a sidewalk-level measurement.",
            "Total shade is unavailable because current tree canopy polygons were not supplied.",
        ]
        if exposure["spatialStatus"] == "nighttime":
            exposure["limitations"].append("Estimated arrival samples are after sunset; building shade is not applicable.")
        routes.append({
            "id": f"route-{index + 1}", "name": f"Route {index + 1}", "coordinates": coordinates,
            "metrics": {
                "durationMinutes": round(duration / 60, 1) if duration is not None and duration >= 0 else None,
                "temperatureC": number(weather.get("temperatureC")),
                "temperatureF": number(weather.get("temperatureF")),
                "windImpact": None, "airQualityIndex": number(air.get("us_aqi")), "snowCondition": snow,
                "sunExposurePercent": None, "treeCanopyPercent": None,
                "treeCanopyCoveragePercent": None,
                "buildingShadePercent": None, "rainExposurePercent": None,
                "estimatedShadePercent": None,
                **spatial,
                **exposure["metrics"],
                "treeCanopyCoveragePercent": number(spatial.get("treeCanopyPercent")),
                "estimatedShadePercent": None,
            },
            "metricContext": {
                "weatherScope": "Distance-weighted route average",
                "weatherTime": observed_at, "weatherSource": weather.get("source"), "airQualityScope": "Estimated US AQI for the starting-point area",
                "airQualityTime": air.get("time"), "timezone": "UTC",
                "spatialQuality": "Philadelphia building footprints indexed in UTM 18N; approximate-height flat-roof shadow model. Tree canopy unavailable because supplied tree files contain points and geometry-free change summaries, not canopy polygons.",
                "spatialTime": generated_at.isoformat(),
            },
            "exposure": exposure,
            "weather": weather,
            "sidewalkGuidance": None, "isDemo": False,
        })
    def compute_score(route):
        duration = route["metrics"]["durationMinutes"]
        if duration is None or duration <= 0:
            return -math.inf
        metrics = route["metrics"]
        weather = route["weather"]
        canopy = number(metrics.get("treeCanopyPercent")) or 0
        shade = number(metrics.get("buildingShadePercent")) or 0
        sun = number(metrics.get("sunExposurePercent")) or 0
        temp = number(weather.get("temperatureC"))
        wet = any((number(weather.get(key)) or 0) > 0 for key in ("rainMm", "precipitationMm", "snowfallCm"))
        wet = wet or (number(metrics.get("rainExposurePercent")) or 0) > 0
        if wet:
            modifier = 0
        elif temp is not None and temp >= 20:
            modifier = (canopy * .20 + shade * .15) / 100
        elif temp is not None and temp < 10:
            modifier = sun * .10 / 100
        else:
            modifier = (canopy * .15 + shade * .05) / 100
        return 1000 / duration * (1 + modifier)

    routes.sort(key=compute_score, reverse=True)
    for index, route in enumerate(routes):
        route.update(id=f"route-{index + 1}", name=f"Route {index + 1}", rank=index + 1, isPreferred=index == 0)
    return {
        "routes": routes,
        "weather": routes[0]["weather"] if routes else {},
        "airQuality": {"usAqi": number(air.get("us_aqi")), "observedAt": air.get("time")},
        "generatedAt": generated_at.isoformat(),
        "weatherScope": "Distance-weighted route average",
    }

@app.get("/api/weather")
async def weather(
    latitude: float = Query(ge=-90, le=90, allow_inf_nan=False),
    longitude: float = Query(ge=-180, le=180, allow_inf_nan=False),
):
    return await get_weather(latitude, longitude)
