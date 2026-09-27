"""Spatial index for Philadelphia's 2025 mapped street-tree inventory."""
import math
import os
import sqlite3
import threading
from pathlib import Path

from shapely.geometry import Point

from .buildings import PROJECT, _source_stamp, iter_features

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
SOURCE = DATA_DIR / "raw" / "trees" / "ppr_tree_inventory_2025.geojson"
INDEX = DATA_DIR / "processed" / "trees.sqlite3"
TREE_RADIUS_METERS = 10
TREE_INDEX_VERSION = "2025-inventory-v1"
_BUILD_LOCK = threading.Lock()


def _metadata(connection):
    return dict(connection.execute("SELECT key, value FROM metadata"))


def _stamp_matches(metadata, source):
    stamp, size = _source_stamp(source)
    return (metadata.get("source_mtime_ns") == str(stamp)
            and metadata.get("source_size") == str(size)
            and metadata.get("index_version") == TREE_INDEX_VERSION)


def _valid_point(feature):
    geometry = feature.get("geometry") or {}
    coordinates = geometry.get("coordinates")
    if geometry.get("type") != "Point" or not isinstance(coordinates, list) or len(coordinates) < 2:
        return None
    longitude, latitude = coordinates[:2]
    if (isinstance(longitude, bool) or isinstance(latitude, bool)
            or not isinstance(longitude, (int, float)) or not isinstance(latitude, (int, float))
            or not math.isfinite(longitude) or not math.isfinite(latitude)
            or not (-75.30 <= longitude <= -74.95 and 39.85 <= latitude <= 40.15)):
        return None
    return PROJECT(longitude, latitude)


def build_index(source=SOURCE, index=INDEX):
    source, index = Path(source), Path(index)
    index.parent.mkdir(parents=True, exist_ok=True)
    stamp, size = _source_stamp(source)
    temporary = index.with_suffix(index.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    count = skipped = 0
    try:
        with sqlite3.connect(temporary) as connection:
            connection.execute("PRAGMA journal_mode=OFF")
            connection.execute("PRAGMA synchronous=OFF")
            connection.execute("CREATE TABLE trees (id INTEGER PRIMARY KEY, x REAL NOT NULL, y REAL NOT NULL)")
            connection.execute("CREATE VIRTUAL TABLE bounds USING rtree(id, min_x, max_x, min_y, max_y)")
            connection.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            rows = []
            for feature in iter_features(source):
                point = _valid_point(feature)
                if point is None:
                    skipped += 1
                    continue
                x, y = point
                rows.append((x, y))
                if len(rows) >= 5000:
                    _insert_rows(connection, rows, count)
                    count += len(rows)
                    rows.clear()
            if rows:
                _insert_rows(connection, rows, count)
                count += len(rows)
            metadata = {
                "source": str(source.resolve()),
                "source_mtime_ns": str(stamp),
                "source_size": str(size),
                "feature_count": str(count),
                "skipped_count": str(skipped),
                "crs": "EPSG:32618",
                "index_version": TREE_INDEX_VERSION,
            }
            connection.executemany("INSERT INTO metadata(key, value) VALUES (?, ?)", metadata.items())
        os.replace(temporary, index)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _insert_rows(connection, rows, offset):
    connection.executemany(
        "INSERT INTO trees(id, x, y) VALUES (?, ?, ?)",
        ((offset + i + 1, x, y) for i, (x, y) in enumerate(rows)),
    )
    connection.executemany(
        "INSERT INTO bounds(id, min_x, max_x, min_y, max_y) VALUES (?, ?, ?, ? ,?)",
        ((offset + i + 1, x, x, y, y) for i, (x, y) in enumerate(rows)),
    )


def ensure_index(source=SOURCE, index=INDEX):
    source, index = Path(source), Path(index)
    if not source.is_file():
        return None
    with _BUILD_LOCK:
        fresh = False
        try:
            with sqlite3.connect(index) as connection:
                fresh = _stamp_matches(_metadata(connection), source)
        except (OSError, sqlite3.Error):
            pass
        if not fresh:
            build_index(source, index)
    return index


def count_near_route(route, radius_meters=TREE_RADIUS_METERS):
    """Count mapped inventory points within a fixed-width route corridor."""
    index = ensure_index()
    if index is None or route.is_empty or route.length <= 0:
        return None
    min_x, min_y, max_x, max_y = route.buffer(radius_meters).bounds
    try:
        with sqlite3.connect(index) as connection:
            candidates = connection.execute(
                "SELECT t.x, t.y FROM bounds r JOIN trees t USING(id) "
                "WHERE r.max_x >= ? AND r.min_x <= ? AND r.max_y >= ? AND r.min_y <= ?",
                (min_x, max_x, min_y, max_y),
            ).fetchall()
        return sum(route.distance(Point(x, y)) <= radius_meters for x, y in candidates)
    except sqlite3.Error:
        return None
