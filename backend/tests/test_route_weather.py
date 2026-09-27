import unittest
from unittest.mock import AsyncMock, patch

from backend.services.route_weather import average_weather, get_route_weather, route_samples


class SamplingTests(unittest.TestCase):
    def test_samples_follow_bends_and_not_vertex_density(self):
        # Unevenly spaced vertices: halfway is at the bend, not at vertex index 2.
        points = [{"latitude": lat, "longitude": lon} for lat, lon in [(0, 0), (0, .01), (0, .02), (0, 1), (1, 1)]]
        samples = route_samples(points)
        self.assertEqual(len(samples), 5)
        self.assertAlmostEqual(samples[1][0]["longitude"], .5)
        self.assertAlmostEqual(samples[2][0]["longitude"], 1)
        self.assertAlmostEqual(samples[2][0]["latitude"], 0)
        self.assertAlmostEqual(samples[3][0]["latitude"], .5)
        self.assertEqual(samples[-1][0], points[-1])
        self.assertEqual(sum(weight for _, weight in samples), 1)

    def test_duplicate_points_and_zero_length(self):
        point = {"latitude": 40, "longitude": -75}
        self.assertEqual(route_samples([point, point]), [(point, 1)])

    def test_weighted_fahrenheit_and_missing_values(self):
        weights = [.125, .25, .25, .25, .125]
        result = average_weather([{"temperatureC": t} for t in [0, 10, 20, 30, 80]], weights)
        self.assertEqual(result["temperatureC"], 25)
        self.assertEqual(result["temperatureF"], 77)
        self.assertEqual(result["coveragePercent"], 100)
        partial = average_weather([{}, {"temperatureC": 0}], [.5, .5])
        self.assertEqual(partial["temperatureF"], 32)
        self.assertEqual(partial["availableSamples"], 1)
        self.assertEqual(partial["coveragePercent"], 50)
        self.assertIsNone(partial["snowfallCm"])
        self.assertIsNone(average_weather([{}], [1])["temperatureF"])


class RouteWeatherTests(unittest.IsolatedAsyncioTestCase):
    async def test_route_specific_samples_and_provider_averages(self):
        async def fake_weather(latitude, longitude, client):
            data = {"temperatureC": longitude * 10, "weatherTime": "2026-09-27T12:00"}
            return {**data, "source": "openMeteo", "providers": {
                "openMeteo": {"status": "ok", "data": data, "error": None},
                "openWeather": {"status": "unavailable", "data": None, "error": "Unavailable"},
            }}
        with patch('backend.services.route_weather.get_weather', new=AsyncMock(side_effect=fake_weather)) as fetch:
            result = await get_route_weather([{"latitude": 0, "longitude": 0}, {"latitude": 0, "longitude": 2}], object())
        self.assertEqual(fetch.await_count, 5)
        self.assertEqual(result["temperatureF"], 50)
        self.assertEqual(result["providers"]["openMeteo"]["data"]["temperatureF"], 50)
        self.assertEqual(result["providers"]["openWeather"]["status"], "unavailable")
        self.assertEqual(result["availableSamples"], 5)
