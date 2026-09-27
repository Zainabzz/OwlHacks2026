import unittest
from unittest.mock import patch
from datetime import datetime, timezone
import tempfile
import json
from pathlib import Path

import httpx
from fastapi.testclient import TestClient
from shapely.geometry import LineString, box

from backend import main
from backend.spatial import route_metrics
from backend.spatial.canopy import covered_percent
from backend.spatial.shade import building_shadow

PAYLOAD = {"start": {"latitude": 39.9496, "longitude": -75.1719},
           "destination": {"latitude": 39.9524, "longitude": -75.1636}}


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)
        self.requests = []
        self.weather_down = False
        self.mapbox_down = False
        self.no_routes = False
        self.invalid_geometry = False
        self.snowfall = 0
        self.async_client = httpx.AsyncClient
        self.token_patch = patch.object(main, "MAPBOX_TOKEN", "test-secret")
        self.token_patch.start()
        self.http_patch = patch.object(main.httpx, "AsyncClient", side_effect=lambda **kwargs:
            self.async_client(transport=httpx.MockTransport(self.upstream), **kwargs))
        self.http_patch.start()

    def tearDown(self):
        self.http_patch.stop()
        self.token_patch.stop()

    def upstream(self, request):
        self.requests.append(request)
        if "api.mapbox.com" == request.url.host:
            if self.mapbox_down:
                return httpx.Response(401, json={"message": "test-secret"})
            if request.url.path.endswith("/suggest"):
                return httpx.Response(200, json={"suggestions": [{"mapbox_id": "place:123", "name": "Market"}]})
            if "/retrieve/" in request.url.path:
                return httpx.Response(200, json={"features": [{"geometry": {"coordinates": [-75.159, 39.953]}, "properties": {"name": "Market"}}]})
            if self.no_routes:
                return httpx.Response(200, json={"code": "NoRoute"})
            return httpx.Response(200, json={"code": "Ok", "routes": [{"duration": 600,
                "geometry": {"coordinates": [] if self.invalid_geometry else [[-75.1719, 39.9496], [-75.1636, 39.9524]]}}]})
        if self.weather_down:
            return httpx.Response(503)
        if request.url.host == "air-quality-api.open-meteo.com":
            return httpx.Response(200, json={"current": {"us_aqi": 42, "time": "2026-09-26T12:00"}})
        return httpx.Response(200, json={"current": {"temperature_2m": 18, "snowfall": self.snowfall, "time": "2026-09-26T12:00"}})

    def test_routes_and_metrics_share_identity(self):
        response = self.client.post("/api/routes", json=PAYLOAD)
        self.assertEqual(response.status_code, 200)
        route = response.json()["routes"][0]
        self.assertEqual(route["id"], "route-1")
        self.assertEqual(route["coordinates"][0], PAYLOAD["start"])
        self.assertEqual(route["metrics"]["durationMinutes"], 10)
        self.assertEqual(route["metrics"]["airQualityIndex"], 42)
        self.assertIn("2026-09-26T12:00", route["metrics"]["snowCondition"])
        self.assertIsNone(route["metrics"]["rainExposurePercent"])
        self.assertFalse(route["isDemo"])

    def test_environmental_outage_keeps_routes(self):
        self.weather_down = True
        response = self.client.post("/api/routes", json=PAYLOAD)
        self.assertEqual(response.status_code, 200)
        metrics = response.json()["routes"][0]["metrics"]
        for key in ["temperatureC", "snowCondition", "airQualityIndex"]:
            self.assertIsNone(metrics[key])

    def test_missing_snow_is_unknown(self):
        self.snowfall = None
        self.assertIsNone(self.client.post("/api/routes", json=PAYLOAD).json()["routes"][0]["metrics"]["snowCondition"])

    def test_upstream_error_hides_key(self):
        self.mapbox_down = True
        response = self.client.post("/api/routes", json=PAYLOAD)
        self.assertEqual(response.status_code, 502)
        self.assertNotIn("test-secret", response.text)
        self.assertNotIn("access_token", response.text)

    def test_no_route(self):
        self.no_routes = True
        self.assertEqual(self.client.post("/api/routes", json=PAYLOAD).json()["routes"], [])
        self.assertEqual(len(self.requests), 1)

    def test_invalid_geometry(self):
        self.invalid_geometry = True
        self.assertEqual(self.client.post("/api/routes", json=PAYLOAD).status_code, 502)

    def test_invalid_input(self):
        response = self.client.post("/api/routes", json={**PAYLOAD, "start": {"latitude": 91, "longitude": 0}})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.requests, [])

    def test_suggest_then_retrieve_same_session(self):
        token = "12345678-1234-4234-8234-123456789abc"
        suggestions = self.client.get("/api/search/suggest", params={"q": "market", "session_token": token}).json()
        response = self.client.get("/api/search/retrieve", params={"id": suggestions["suggestions"][0]["id"], "session_token": token})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["location"]["latitude"], 39.953)
        self.assertTrue(all(r.url.params["session_token"] == token for r in self.requests))


class SpatialTests(unittest.TestCase):
    def test_canopy_overlap_counted_once(self):
        route = LineString([(0, 0), (100, 0)])
        self.assertEqual(covered_percent(route, [box(0, -1, 30, 1), box(20, -1, 50, 1)]), 50)
        self.assertEqual(covered_percent(route, []), 0)

    def test_shadow_points_away_from_sun(self):
        shadow = building_shadow(box(0, 0, 10, 10), 10, 180, 45)
        self.assertAlmostEqual(shadow.bounds[3], 20)
        self.assertTrue(building_shadow(box(0, 0, 10, 10), 10, 180, -1).is_empty)

    def test_missing_or_outside_coverage_is_unknown(self):
        with tempfile.TemporaryDirectory() as directory, patch("backend.spatial.DATA_DIR", Path(directory)):
            route = [PAYLOAD["start"], PAYLOAD["destination"]]
            self.assertTrue(all(v is None for v in route_metrics(route, 600, datetime.now(timezone.utc)).values()))
            Path(directory, "tree_canopy.geojson").write_text(json.dumps({"coverageBbox": [0, 0, 1, 1], "features": []}))
            self.assertIsNone(route_metrics(route, 600, datetime.now(timezone.utc))["treeCanopyPercent"])

    def test_known_coverage_and_nighttime_sun(self):
        from shapely.geometry import mapping
        with tempfile.TemporaryDirectory() as directory, patch("backend.spatial.DATA_DIR", Path(directory)):
            coverage = [-75.25, 39.90, -75.05, 40.02]
            canopy = {"coverageBbox": coverage, "features": [{"geometry": mapping(box(*coverage)), "properties": {}}]}
            buildings = {"coverageBbox": coverage, "features": []}
            Path(directory, "tree_canopy.geojson").write_text(json.dumps(canopy))
            Path(directory, "buildings.geojson").write_text(json.dumps(buildings))
            # 04:00 UTC is midnight in Philadelphia in June.
            values = route_metrics([PAYLOAD["start"], PAYLOAD["destination"]], 600, datetime(2026, 6, 1, 4, tzinfo=timezone.utc))
            self.assertEqual(values["treeCanopyPercent"], 100)
            self.assertEqual(values["sunExposurePercent"], 0)
            self.assertEqual(values["buildingShadePercent"], 0)

    def test_unknown_building_heights_do_not_claim_shade(self):
        from shapely.geometry import mapping
        with tempfile.TemporaryDirectory() as directory, patch("backend.spatial.DATA_DIR", Path(directory)):
            data = {"coverageBbox": [-75.25, 39.90, -75.05, 40.02], "features": [{
                "geometry": mapping(box(-75.172, 39.948, -75.17, 39.95)), "properties": {}}]}
            Path(directory, "buildings.geojson").write_text(json.dumps(data))
            values = route_metrics([PAYLOAD["start"], PAYLOAD["destination"]], 600, datetime(2026, 6, 1, 16, tzinfo=timezone.utc))
            self.assertIsNone(values["buildingShadePercent"])


if __name__ == "__main__":
    unittest.main()
