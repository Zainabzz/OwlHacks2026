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
        self.multi_routes = False
        self.waypoint_routes = False
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
            if self.multi_routes:
                return httpx.Response(200, json={"code": "Ok", "routes": [
                    {"duration": 600, "distance": 1000, "geometry": {"coordinates": [[-75.1719, 39.9496], [-75.1670, 39.9510], [-75.1636, 39.9524]]}},
                    {"duration": 720, "distance": 1150, "geometry": {"coordinates": [[-75.1719, 39.9496], [-75.1690, 39.9540], [-75.1636, 39.9524]]}},
                    {"duration": 840, "distance": 1300, "geometry": {"coordinates": [[-75.1719, 39.9496], [-75.1650, 39.9480], [-75.1636, 39.9524]]}},
                ]})
            if self.waypoint_routes:
                coords = request.url.path.split("/")[-1].split(";")
                if len(coords) == 3:
                    wp = coords[1]
                    return httpx.Response(200, json={"code": "Ok", "routes": [
                        {"duration": 700 + round(abs(float(wp.split(",")[1]) - 39.951) * 10000), "distance": 1100, "geometry": {"coordinates": [[-75.1719, 39.9496], [float(c) for c in wp.split(",")], [-75.1636, 39.9524]]}}
                    ]})
                return httpx.Response(200, json={"code": "Ok", "routes": [
                    {"duration": 600, "distance": 1000, "geometry": {"coordinates": [[-75.1719, 39.9496], [-75.1680, 39.9510], [-75.1636, 39.9524]]}}
                ]})
            return httpx.Response(200, json={"code": "Ok", "routes": [{"duration": 600,
                "geometry": {"coordinates": [] if self.invalid_geometry else [[-75.1719, 39.9496], [-75.1636, 39.9524]]}}]})
        if self.weather_down:
            return httpx.Response(503)
        if request.url.host == "air-quality-api.open-meteo.com":
            return httpx.Response(200, json={"current": {"us_aqi": 42, "time": "2026-09-26T12:00"}})
        if "hourly" in request.url.params:
            now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0).timestamp()
            hourly = {"time": [now, now + 3600], "direct_normal_irradiance": [500, 500],
                      "rain": [0.2, 0.2], "showers": [0, 0], "wind_speed_10m": [10, 10], "wind_direction_10m": [45, 45]}
            return httpx.Response(200, json=[{"hourly": hourly}] * 12)
        return httpx.Response(200, json={"current": {"temperature_2m": 18, "snowfall": self.snowfall, "time": "2026-09-26T12:00"}})

    def test_routes_and_metrics_share_identity(self):
        response = self.client.post("/api/routes", json=PAYLOAD)
        self.assertEqual(response.status_code, 200)
        route = response.json()["routes"][0]
        self.assertEqual(route["id"], "route-1")
        self.assertEqual(route["coordinates"][0], PAYLOAD["start"])
        self.assertEqual(route["metrics"]["durationMinutes"], 10)
        self.assertIsNone(route["metrics"]["distanceMiles"])
        self.assertEqual(route["metrics"]["airQualityIndex"], 42)
        self.assertIn("2026-09-26T12:00", route["metrics"]["snowCondition"])
        self.assertIsNone(route["metrics"]["treeCanopyCoveragePercent"])
        self.assertIsNone(route["metrics"]["estimatedShadePercent"])
        self.assertTrue(any("tree inventory contains trunk points" in item for item in route["exposure"]["limitations"]))
        self.assertEqual(route["metrics"]["rainExposurePercent"], 100)
        self.assertIsNotNone(route["metrics"]["sunExposurePercent"])
        self.assertGreater(route["metrics"]["windImpact"], 0)
        self.assertIn(route["exposure"]["sunBasis"], ["weather-and-shade", "open-sky"])
        if route["exposure"]["spatialStatus"] == "nighttime":
            self.assertIsNone(route["metrics"]["buildingShadePercent"])
        self.assertFalse(route["isDemo"])

    def test_route_weather_samples_geometry_and_exposes_fahrenheit(self):
        response = self.client.post("/api/routes", json=PAYLOAD)
        route = response.json()["routes"][0]
        self.assertEqual(route["metrics"]["temperatureF"], 64.4)
        self.assertEqual(route["weather"]["sampleCount"], 5)
        self.assertEqual(route["weather"]["availableSamples"], 5)
        self.assertEqual(route["metricContext"]["weatherScope"], "Distance-weighted route average")
        samples = [r for r in self.requests if r.url.host == "api.open-meteo.com" and "current" in r.url.params]
        self.assertEqual(len(samples), 5)
        self.assertAlmostEqual(float(samples[0].url.params["latitude"]), PAYLOAD["start"]["latitude"])
        self.assertAlmostEqual(float(samples[-1].url.params["latitude"]), PAYLOAD["destination"]["latitude"])

    def test_environmental_outage_keeps_routes(self):
        self.weather_down = True
        response = self.client.post("/api/routes", json=PAYLOAD)
        self.assertEqual(response.status_code, 200)
        metrics = response.json()["routes"][0]["metrics"]
        for key in ["temperatureC", "snowCondition", "airQualityIndex", "rainExposurePercent", "windImpact"]:
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

    def test_long_opaque_mapbox_id_is_retrievable(self):
        token = "12345678-1234-4234-8234-123456789abc"
        identifier = "dXJuOm1ieHBvaTo" + "a" * 4400
        response = self.client.get("/api/search/retrieve", params={"id": identifier, "session_token": token})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.requests[-1].url.path.endswith(identifier))

    def test_malformed_search_responses_are_gateway_errors(self):
        token = "12345678-1234-4234-8234-123456789abc"
        for payload in [{"suggestions": None}, {"suggestions": {}}]:
            with patch.object(main, "mapbox_get", return_value=payload):
                response = self.client.get("/api/search/suggest", params={"q": "market", "session_token": token})
            self.assertEqual(response.status_code, 502)
        with patch.object(main, "mapbox_get", return_value={"features": [{"geometry": {"coordinates": [-75, 40]}, "properties": None}]}):
            response = self.client.get("/api/search/retrieve", params={"id": "place", "session_token": token})
        self.assertEqual(response.status_code, 502)

    def test_suggest_then_retrieve_same_session(self):
        token = "12345678-1234-4234-8234-123456789abc"
        suggestions = self.client.get("/api/search/suggest", params={"q": "market", "session_token": token}).json()
        response = self.client.get("/api/search/retrieve", params={"id": suggestions["suggestions"][0]["id"], "session_token": token})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["location"]["latitude"], 39.953)
        self.assertTrue(all(r.url.params["session_token"] == token for r in self.requests))


    def test_multiple_routes_ranked_and_preferred(self):
        self.multi_routes = True
        response = self.client.post("/api/routes", json=PAYLOAD)
        self.assertEqual(response.status_code, 200)
        routes = response.json()["routes"]
        self.assertEqual(len(routes), 3)

        # Route 1 is preferred
        self.assertEqual(routes[0]["id"], "route-1")
        self.assertEqual(routes[0]["name"], "Route 1")
        self.assertTrue(routes[0]["isPreferred"])
        self.assertEqual(routes[0]["rank"], 1)
        self.assertEqual(routes[0]["metrics"]["durationMinutes"], 10.0)
        self.assertEqual(routes[0]["metrics"]["distanceMiles"], 0.62)

        # Route 2 is alternative
        self.assertEqual(routes[1]["id"], "route-2")
        self.assertEqual(routes[1]["name"], "Route 2")
        self.assertFalse(routes[1]["isPreferred"])
        self.assertEqual(routes[1]["rank"], 2)
        self.assertEqual(routes[1]["metrics"]["durationMinutes"], 12.0)
        self.assertEqual(routes[1]["metrics"]["distanceMiles"], 0.71)

        # Route 3 is alternative
        self.assertEqual(routes[2]["id"], "route-3")
        self.assertEqual(routes[2]["name"], "Route 3")
        self.assertFalse(routes[2]["isPreferred"])
        self.assertEqual(routes[2]["rank"], 3)
        self.assertEqual(routes[2]["metrics"]["durationMinutes"], 14.0)
        self.assertEqual(routes[2]["metrics"]["distanceMiles"], 0.81)

    def test_ranking_preserves_each_routes_weather_and_exposure(self):
        self.multi_routes = True
        def index_for(coords):
            return {39.9510: 0, 39.9540: 1, 39.9480: 2}[coords[1]["latitude"]]
        async def weather_for(coords, client):
            index = index_for(coords)
            return {"temperatureC": 25 + index, "temperatureF": 77 + index * 1.8,
                    "rainMm": 0, "source": "openMeteo", "marker": index}
        async def exposure_for(coords, duration, departure, client):
            index = index_for(coords)
            return {"metrics": {"sunExposurePercent": 50 + index, "rainExposurePercent": 0, "windImpact": index + 1},
                    "marker": index, "status": "ok"}
        def spatial_for(coords, duration, departure):
            return {"treeCanopyPercent": 100 if index_for(coords) == 1 else 0,
                    "buildingShadePercent": 100 if index_for(coords) == 1 else 0}
        with patch.object(main, "get_route_weather", side_effect=weather_for), \
             patch.object(main, "get_route_exposure", side_effect=exposure_for), \
             patch.object(main, "spatial_metrics", side_effect=spatial_for):
            response = self.client.post("/api/routes", json=PAYLOAD)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["routes"][0]["metrics"]["durationMinutes"], 12)
        self.assertEqual(data["weather"]["marker"], 1)
        for rank, route in enumerate(data["routes"], 1):
            index = index_for(route["coordinates"])
            self.assertEqual(route["rank"], rank)
            self.assertEqual(route["isPreferred"], rank == 1)
            self.assertEqual(route["weather"]["marker"], index)
            self.assertEqual(route["exposure"]["marker"], index)
            self.assertEqual(route["metrics"]["temperatureF"], 77 + index * 1.8)
            self.assertEqual(route["metrics"]["windImpact"], index + 1)
            self.assertEqual(route["metrics"]["sunExposurePercent"], 50 + index)

    def test_failed_or_invalid_alternatives_preserve_primary_route(self):
        original = main.mapbox_get
        for failure in [main.HTTPException(502, "Provider unavailable"), {"code": "Ok", "routes": [{"geometry": None}]}]:
            async def optional_failure(client, path, params):
                if path.count(";") == 2:
                    if isinstance(failure, Exception):
                        raise failure
                    return failure
                return await original(client, path, params)
            with patch.object(main, "mapbox_get", side_effect=optional_failure):
                response = self.client.post("/api/routes", json=PAYLOAD)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.json()["routes"]), 1)
            self.assertTrue(response.json()["routes"][0]["isPreferred"])

    def test_waypoint_routes_found_and_ranked(self):
        self.waypoint_routes = True
        response = self.client.post("/api/routes", json=PAYLOAD)
        self.assertEqual(response.status_code, 200)
        routes = response.json()["routes"]
        self.assertGreaterEqual(len(routes), 2)
        self.assertTrue(routes[0]["isPreferred"])
        self.assertEqual(routes[0]["rank"], 1)
        for r in routes[1:]:
            self.assertFalse(r["isPreferred"])


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
            self.assertIsNone(values["buildingShadePercent"])

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
