"""Optional Philadelphia coverage calculations from cached, normalized GeoJSON."""
import json
import math
from datetime import timedelta
from functools import lru_cache
from pathlib import Path

from astral import Observer
from astral.sun import azimuth, elevation
from pyproj import Transformer
from shapely.geometry import LineString, box, shape
from shapely.ops import transform, substring

from .canopy import covered_percent
from .shade import building_shadow

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
PROJECT = Transformer.from_crs("EPSG:4326", "EPSG:32618", always_xy=True).transform
UNPROJECT = Transformer.from_crs("EPSG:32618", "EPSG:4326", always_xy=True).transform


@lru_cache(maxsize=8)
def load_layer(path, modified):
    del modified  # Cache invalidates when the local file changes.
    data = json.loads(Path(path).read_text())
    # Explicit coverage bounds avoid treating regions outside an extract as 0%.
    coverage = transform(PROJECT, box(*data["coverageBbox"]))
    features = []
    for feature in data["features"]:
        geometry = shape(feature["geometry"])
        if geometry.geom_type not in {"Polygon", "MultiPolygon"} or not geometry.is_valid:
            raise ValueError("Expected valid polygon coverage")
        features.append((transform(PROJECT, geometry), feature.get("properties", {})))
    return coverage, features


def layer(name):
    path = DATA_DIR / name
    try:
        return load_layer(str(path), path.stat().st_mtime_ns)
    except (OSError, ValueError, KeyError, TypeError):
        return None


def route_metrics(coordinates, duration_seconds, departure):
    result = {"treeCanopyPercent": None, "buildingShadePercent": None, "sunExposurePercent": None}
    # UTM 18N is appropriate for this Philadelphia implementation, not worldwide routes.
    if not all(-75.30 <= p["longitude"] <= -74.95 and 39.85 <= p["latitude"] <= 40.15 for p in coordinates):
        return result
    route = transform(PROJECT, LineString([(p["longitude"], p["latitude"]) for p in coordinates]))
    if route.length <= 0:
        return result
    canopy_data = layer("tree_canopy.geojson")
    canopy = None
    if canopy_data and canopy_data[0].covers(route):
        canopy = [geometry for geometry, _ in canopy_data[1] if geometry.intersects(route)]
        result["treeCanopyPercent"] = covered_percent(route, canopy)

    building_data = layer("buildings.geojson")
    if not building_data or duration_seconds is None or duration_seconds < 0:
        return result
    coverage, features = building_data
    if not coverage.covers(route):
        return result
    heights = [properties.get("height_m") for _, properties in features]
    if any(not isinstance(h, (int, float)) or not math.isfinite(h) or h <= 0 for h in heights):
        return result  # Unknown heights must not silently imply no shade.
    max_height = max(heights, default=0)
    shade_length = sun_length = 0.0
    # Sample arrival time at the midpoint of each of 12 equal-length route pieces.
    for index in range(12):
        fraction = (index + 0.5) / 12
        piece = substring(route, route.length * index / 12, route.length * (index + 1) / 12)
        midpoint = route.interpolate(fraction, normalized=True)
        longitude, latitude = UNPROJECT(midpoint.x, midpoint.y)
        observer = Observer(latitude=latitude, longitude=longitude)
        arrival = departure + timedelta(seconds=duration_seconds * fraction)
        altitude = elevation(observer, arrival)
        if altitude <= 0:
            continue  # No direct sunlight at night; no building shadow is claimed.
        # Very low sun produces unbounded shadows beyond a local extract.
        if altitude < 3:
            return result
        reach = max_height / math.tan(math.radians(altitude))
        if not coverage.covers(piece.buffer(reach + 1)):
            return result
        candidates = [(geometry, h) for (geometry, _), h in zip(features, heights)
                      if geometry.distance(piece) <= reach]
        shadows = [building_shadow(g, h, azimuth(observer, arrival), altitude) for g, h in candidates]
        shade_length += piece.length * covered_percent(piece, shadows) / 100
        if canopy is not None:
            sun_length += piece.length * (1 - covered_percent(piece, shadows + canopy) / 100)
    result["buildingShadePercent"] = round(shade_length / route.length * 100, 1)
    if canopy is not None:
        result["sunExposurePercent"] = round(sun_length / route.length * 100, 1)
    return result
