import asyncio
import os
import unittest
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient
from backend import main
from backend.services import weather


class WeatherTests(unittest.IsolatedAsyncioTestCase):
    async def weather_result(self, fail=None, configured=True):
        self.requests = []
        def upstream(request):
            self.requests.append(request)
            meteo = request.url.host == "api.open-meteo.com"
            if fail == "both" or fail == ("meteo" if meteo else "openweather"):
                return httpx.Response(401, json={"message": "do not echo secret-key"})
            if meteo:
                self.assertEqual(request.url.params["precipitation_unit"], "mm")
                return httpx.Response(200, json={"current": {"temperature_2m": 20, "snowfall": 2,
                    "rain": 25.4, "wind_speed_10m": 36, "time": "2026-09-26T12:00", "is_day": 0}})
            self.assertEqual(request.url.params["appid"], "secret-key")
            self.assertEqual(request.url.params["units"], "metric")
            return httpx.Response(200, json={"main": {"temp": 10}, "wind": {"speed": 10},
                "snow": {"1h": 3}, "dt": 1790424000})
        with patch.dict(os.environ, {"OPENWEATHER_API": "secret-key" if configured else "", "OPENWEATHER_API_KEY": ""}):
            async with httpx.AsyncClient(transport=httpx.MockTransport(upstream)) as client:
                return await weather.get_weather(39.95, -75.16, client)

    async def test_both_providers_and_units(self):
        result = await self.weather_result()
        self.assertEqual(len(self.requests), 2)
        self.assertEqual(result["temperatureF"], 68)
        self.assertEqual(result["rainInches"], 1)
        self.assertEqual(result["snowfallCm"], 2)
        self.assertFalse(result["isDay"])
        keyed = result["providers"]["openWeather"]["data"]
        self.assertEqual(keyed["windSpeedKmh"], 36)
        self.assertEqual(keyed["temperatureF"], 50)
        self.assertIsNone(keyed["snowfallCm"])
        self.assertEqual(keyed["snowWaterEquivalentMm"], 3)

    async def test_fallback_and_secret_redaction(self):
        result = await self.weather_result(fail="meteo")
        self.assertEqual(result["source"], "openWeather")
        self.assertEqual(result["temperatureC"], 10)
        result = await self.weather_result(fail="openweather")
        self.assertEqual(result["source"], "openMeteo")
        self.assertIn("key was rejected", result["providers"]["openWeather"]["error"])
        self.assertNotIn("secret-key", str(result))

    async def test_missing_key_and_both_down(self):
        result = await self.weather_result(configured=False)
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(result["providers"]["openWeather"]["status"], "not_configured")
        result = await self.weather_result(fail="both")
        self.assertEqual(result["status"], "unavailable")
        self.assertIsNone(result["source"])

    async def test_timeout_and_bad_json(self):
        async def upstream(request):
            if request.url.host == "api.open-meteo.com":
                await asyncio.sleep(0.05)
            return httpx.Response(200, text="not json")
        with patch.object(weather, "PROVIDER_TIMEOUT", 0.01), patch.dict(os.environ, {"OPENWEATHER_API": "secret-key"}):
            async with httpx.AsyncClient(transport=httpx.MockTransport(upstream)) as client:
                result = await weather.get_weather(39.95, -75.16, client)
        self.assertEqual(result["status"], "unavailable")
        self.assertIn("timed out", result["providers"]["openMeteo"]["error"])
        self.assertIn("invalid", result["providers"]["openWeather"]["error"])


class WeatherEndpointTests(unittest.TestCase):
    def test_coordinates_validated(self):
        client = TestClient(main.app)
        for latitude in [91, "nan", "inf"]:
            self.assertEqual(client.get("/api/weather", params={"latitude": latitude, "longitude": 0}).status_code, 422)
