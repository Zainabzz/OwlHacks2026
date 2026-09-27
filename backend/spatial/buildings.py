"""Streaming SQLite/RTree index for Philadelphia building footprints."""
import json
import math
import os
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

from pyproj import Transformer
from shapely.geometry import box, shape
from shapely.ops import transform

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
SOURCE = DATA_DIR / "raw" / "buildings" / "LI_BUILDING_FOOTPRINTS.geojson"
INDEX = DATA_DIR / "processed" / "buildings.sqlite3"
PROJECT = Transformer.from_crs("EPSG:4326", "EPSG:32618", always_xy=True).transform
_BUILD_LOCK = threading.Lock()


@contextmanager
def _connection(path):
    connection = sqlite3.connect(path)
    try:
        yield connection
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()


def iter_features(path, chunk_size=1024 * 1024):
    """Yield GeoJSON features without loading the 474 MB source into memory."""
    decoder = json.JSONDecoder()
    with Path(path).open("r", encoding="utf-8") as source:
        buffer = ""
        while '"features"' not in buffer:
            chunk = source.read(chunk_size)
            if not chunk:
                raise ValueError("GeoJSON has no features array")
            buffer += chunk
        cursor = buffer.index('"features"') + len('"features"')
        while cursor < len(buffer) and buffer[cursor].isspace():
            cursor += 1
        if cursor == len(buffer):
            raise ValueError("Invalid GeoJSON features array")
        if buffer[cursor] != ":":
            raise ValueError("Invalid GeoJSON features property")
        cursor += 1
        while True:
            while cursor < len(buffer) and (buffer[cursor].isspace() or buffer[cursor] == ":"):
                cursor += 1
            if cursor == len(buffer):
                chunk = source.read(chunk_size)
                if not chunk:
                    raise ValueError("Unexpected end of GeoJSON")
                buffer, cursor = chunk, 0
                continue
            if buffer[cursor] == "[":
                cursor += 1
                break
            raise ValueError("Invalid GeoJSON features array")

        while True:
            while cursor < len(buffer) and (buffer[cursor].isspace() or buffer[cursor] == ","):
                cursor += 1
            if cursor == len(buffer):
                chunk = source.read(chunk_size)
                if not chunk:
                    raise ValueError("Unexpected end of GeoJSON feature array")
                buffer, cursor = chunk, 0
                continue
            if buffer[cursor] == "]":
                return
            try:
                feature, end = decoder.raw_decode(buffer, cursor)
            except json.JSONDecodeError:
                chunk = source.read(chunk_size)
                if not chunk:
                    raise
                buffer = buffer[cursor:] + chunk
                cursor = 0
                continue
            cursor = end
            yield feature
            if cursor > chunk_size:
                buffer, cursor = buffer[cursor:], 0


def _source_stamp(path):
    stat = path.stat()
    return stat.st_mtime_ns, stat.st_size


def _height_m(properties):
    feet = properties.get("approx_hgt")
    if isinstance(feet, bool) or not isinstance(feet, (int, float)) or not math.isfinite(feet) or feet <= 0:
        return None
    return feet * 0.3048


def build_index(source=SOURCE, index=INDEX):
    source, index = Path(source), Path(index)
    index.parent.mkdir(parents=True, exist_ok=True)
    stamp, size = _source_stamp(source)
    temporary = index.with_suffix(index.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    west = south = math.inf
    east = north = -math.inf
    count = skipped = 0
    max_height = 0.0
    try:
        with _connection(temporary) as connection:
            connection.execute("PRAGMA journal_mode=OFF")
            connection.execute("PRAGMA synchronous=OFF")
            connection.execute("CREATE TABLE buildings (id INTEGER PRIMARY KEY, geometry BLOB NOT NULL, height_m REAL)")
            connection.execute("CREATE VIRTUAL TABLE bounds USING rtree(id, min_x, max_x, min_y, max_y)")
            connection.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            rows = []
            for feature in iter_features(source):
                try:
                    geometry = shape(feature["geometry"])
                    if geometry.geom_type not in {"Polygon", "MultiPolygon"} or geometry.is_empty or not geometry.is_valid:
                        skipped += 1
                        continue
                    projected = transform(PROJECT, geometry)
                    if projected.is_empty or not all(math.isfinite(value) for value in projected.bounds):
                        skipped += 1
                        continue
                    min_x, min_y, max_x, max_y = projected.bounds
                    properties = feature.get("properties") or {}
                    height = _height_m(properties)
                    if height is not None:
                        max_height = max(max_height, height)
                    rows.append((sqlite3.Binary(projected.wkb), height, min_x, max_x, min_y, max_y))
                    w, s, e, n = geometry.bounds
                    west, south, east, north = min(west, w), min(south, s), max(east, e), max(north, n)
                    if len(rows) >= 1000:
                        _insert_rows(connection, rows, count)
                        count += len(rows)
                        rows.clear()
                except (KeyError, TypeError, ValueError, OverflowError):
                    skipped += 1
            if rows:
                _insert_rows(connection, rows, count)
                count += len(rows)
            coverage = transform(PROJECT, box(west, south, east, north)).bounds if count else ()
            metadata = {
                "source": str(source.resolve()), "source_mtime_ns": str(stamp),
                "source_size": str(size), "feature_count": str(count),
                "skipped_count": str(skipped), "crs": "EPSG:32618",
                "max_height_m": str(max_height),
                "coverage": json.dumps(coverage),
            }
            connection.executemany("INSERT INTO metadata(key, value) VALUES (?, ?)", metadata.items())
        os.replace(temporary, index)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _insert_rows(connection, rows, offset):
    connection.executemany(
        "INSERT INTO buildings(id, geometry, height_m) VALUES (?, ?, ?)",
        ((offset + i + 1, row[0], row[1]) for i, row in enumerate(rows)),
    )
    connection.executemany(
        "INSERT INTO bounds(id, min_x, max_x, min_y, max_y) VALUES (?, ?, ?, ?, ?)",
        ((offset + i + 1, *row[2:]) for i, row in enumerate(rows)),
    )


def _metadata(connection):
    return dict(connection.execute("SELECT key, value FROM metadata"))


def read_metadata(index):
    with _connection(index) as connection:
        return _metadata(connection)


def ensure_index(source=SOURCE, index=INDEX):
    source, index = Path(source), Path(index)
    if not source.is_file():
        return None
    stamp, size = _source_stamp(source)
    with _BUILD_LOCK:
        fresh = False
        try:
            with _connection(index) as connection:
                metadata = _metadata(connection)
            fresh = metadata.get("source_mtime_ns") == str(stamp) and metadata.get("source_size") == str(size)
        except (OSError, sqlite3.Error):
            pass
        if not fresh:
            build_index(source, index)
    return index


def index_is_current(source, index):
    source, index = Path(source), Path(index)
    if not source.is_file() or not index.is_file():
        return False
    stamp, size = _source_stamp(source)
    try:
        with _connection(index) as connection:
            metadata = _metadata(connection)
        return metadata.get("source_mtime_ns") == str(stamp) and metadata.get("source_size") == str(size)
    except sqlite3.Error:
        return False


def query(index, bounds):
    """Return projected geometries/heights intersecting (minx,miny,maxx,maxy)."""
    import shapely

    min_x, min_y, max_x, max_y = bounds
    with _connection(index) as connection:
        metadata = _metadata(connection)
        rows = connection.execute(
            "SELECT b.geometry, b.height_m FROM bounds r JOIN buildings b USING(id) "
            "WHERE r.max_x >= ? AND r.min_x <= ? AND r.max_y >= ? AND r.min_y <= ?",
            (min_x, max_x, min_y, max_y),
        ).fetchall()
    return metadata, [(shapely.from_wkb(blob), height) for blob, height in rows]


if __name__ == "__main__":
    import time
    started = time.monotonic()
    existed = index_is_current(SOURCE, INDEX)
    ensure_index()
    action = "Using cached" if existed else "Built"
    print(f"{action} {INDEX} in {time.monotonic() - started:.1f}s")
