import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from shapely.geometry import box, mapping

from backend.spatial.buildings import build_index, index_is_current, iter_features, query
from backend.spatial import route_is_nighttime, route_metrics


class BuildingIndexTests(unittest.TestCase):
    def fixture(self, path):
        features = [
            {"type": "Feature", "properties": {"approx_hgt": 32}, "geometry": mapping(box(-75.17, 39.95, -75.169, 39.951))},
            {"type": "Feature", "properties": {"approx_hgt": None}, "geometry": mapping(box(-75.18, 39.94, -75.179, 39.941))},
        ]
        path.write_text(json.dumps({"type": "FeatureCollection", "name": "fixture", "features": features}))

    def test_streaming_reader_handles_small_chunks(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "features.geojson"
            self.fixture(path)
            self.assertEqual(len(list(iter_features(path, chunk_size=19))), 2)

    def test_index_projects_geometry_and_converts_height_feet_to_meters(self):
        with tempfile.TemporaryDirectory() as directory:
            source, index = Path(directory) / "source.geojson", Path(directory) / "index.sqlite3"
            self.fixture(source)
            build_index(source, index)
            self.assertTrue(index_is_current(source, index))
            metadata, found = query(index, (-9_000_000, -9_000_000, 9_000_000, 9_000_000))
            self.assertEqual(metadata["crs"], "EPSG:32618")
            self.assertEqual(int(metadata["feature_count"]), 2)
            self.assertEqual(len(found), 2)
            self.assertAlmostEqual(found[0][1], 9.7536)
            self.assertIsNone(found[1][1])
            self.assertGreater(found[0][0].bounds[0], 0)

    def test_route_metrics_use_actual_source_schema_and_keep_tree_coverage_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "raw" / "buildings" / "LI_BUILDING_FOOTPRINTS.geojson"
            source.parent.mkdir(parents=True)
            # Outer footprints establish the documented complete local extract bounds.
            features = [
                {"type": "Feature", "properties": {"approx_hgt": 32}, "geometry": mapping(box(-75.25, 39.90, -75.249, 39.901))},
                {"type": "Feature", "properties": {"approx_hgt": 32}, "geometry": mapping(box(-75.05, 39.90, -75.049, 39.901))},
                {"type": "Feature", "properties": {"approx_hgt": 32}, "geometry": mapping(box(-75.25, 40.02, -75.249, 40.021))},
                {"type": "Feature", "properties": {"approx_hgt": 32}, "geometry": mapping(box(-75.05, 40.02, -75.049, 40.021))},
            ]
            source.write_text(json.dumps({"type": "FeatureCollection", "features": features}))
            processed = root / "processed"
            build_index(source, processed / "buildings.sqlite3")
            with patch("backend.spatial.DATA_DIR", root):
                values = route_metrics(
                    [{"latitude": 39.9496, "longitude": -75.1719}, {"latitude": 39.9524, "longitude": -75.1636}],
                    600, datetime(2026, 6, 1, 16, tzinfo=timezone.utc),
                )
            self.assertIsNone(values["treeCanopyPercent"])
            self.assertIsNotNone(values["buildingShadePercent"])
            self.assertIsNotNone(values["sunExposurePercent"])

    def test_nighttime_is_not_reported_as_zero_building_shade(self):
        route = [{"latitude": 39.9496, "longitude": -75.1719}, {"latitude": 39.9524, "longitude": -75.1636}]
        self.assertTrue(route_is_nighttime(route, 600, datetime(2026, 6, 1, 4, tzinfo=timezone.utc)))


if __name__ == "__main__":
    unittest.main()
