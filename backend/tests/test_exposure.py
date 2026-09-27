import unittest
from datetime import datetime, timezone

import httpx

from backend.services.exposure import sample_route, forecast_values, summarize, get_route_exposure, apply_shade

NOON = datetime(2026, 6, 1, 16, 30, tzinfo=timezone.utc)
ROUTE = [{"latitude": 39.95, "longitude": -75.17}, {"latitude": 39.96, "longitude": -75.17}]


def forecast(radiation=500, rain=0, showers=0, speed=10, direction=0):
    return {"hourly": {"time": [NOON.timestamp() - 1800, NOON.timestamp() + 1800],
        "direct_normal_irradiance": [radiation, radiation], "rain": [rain, rain], "showers": [showers, showers],
        "wind_speed_10m": [speed, speed], "wind_direction_10m": [direction, direction]}}


def sample(bearing=0, arrival=NOON):
    return {"latitude": 39.95, "longitude": -75.17, "arrival": arrival, "headings": [(bearing, 1)]}


class ExposureTests(unittest.TestCase):
    def test_rain_sun_and_directional_headwind(self):
        result = summarize([sample(), sample(180)], [forecast(rain=.1), forecast(radiation=0)])
        self.assertEqual(result["metrics"], {"sunExposurePercent": 50, "rainExposurePercent": 50, "windImpact": 5})
        self.assertEqual(result["status"], "ok")
        self.assertEqual(summarize([sample(90)], [forecast()])["metrics"]["windImpact"], 0)

    def test_night_and_calm_are_zero_not_missing(self):
        night = NOON.replace(hour=4)
        result = summarize([sample(arrival=night)], [{}])
        self.assertEqual(result["metrics"]["sunExposurePercent"], 0)
        self.assertIsNone(result["metrics"]["rainExposurePercent"])
        self.assertEqual(summarize([sample()], [forecast(speed=0, direction=None)])["metrics"]["windImpact"], 0)

    def test_missing_forecasts_do_not_become_dry_or_calm(self):
        result = summarize([sample(), sample()], [forecast(), {}])
        self.assertEqual(result["coveragePercent"]["rainExposurePercent"], 50)
        self.assertEqual(result["status"], "partial")
        result = summarize([sample()], [{}])
        self.assertTrue(all(v is None for v in result["metrics"].values()))

    def test_accumulations_use_upcoming_interval_and_wind_nearest(self):
        data = forecast()
        data["hourly"]["rain"] = [5, 0]
        data["hourly"]["wind_speed_10m"] = [5, 15]
        result = forecast_values(data, NOON.replace(minute=10))
        self.assertEqual(result["rain"], 0)
        self.assertEqual(result["wind_speed_10m"], 5)
        self.assertEqual(forecast_values(data, NOON.replace(hour=20)), {})

    def test_malformed_hourly_payload_does_not_fail_route(self):
        for hourly in [None, [], "invalid"]:
            self.assertEqual(forecast_values({"hourly": hourly}, NOON), {})
        self.assertEqual(sample_route(ROUTE[:1], 60, NOON), [])

    def test_samples_arrive_in_order_and_respect_philly_bounds(self):
        samples = sample_route(ROUTE, 1200, NOON)
        self.assertEqual(len(samples), 12)
        self.assertEqual((samples[0]["arrival"] - NOON).total_seconds(), 50)
        self.assertEqual((samples[-1]["arrival"] - NOON).total_seconds(), 1150)
        self.assertEqual(sample_route(ROUTE, None, NOON), [])
        self.assertEqual(sample_route([ROUTE[0], ROUTE[0]], 60, NOON), [])
        self.assertEqual(sample_route([{"latitude": 34, "longitude": -118}, ROUTE[0]], 60, NOON), [])

    def test_shade_is_optional_and_does_not_change_rain(self):
        result = summarize([sample()], [forecast(rain=2)])
        adjusted = apply_shade(result, {"sunExposurePercent": 25})
        self.assertEqual(adjusted["metrics"]["sunExposurePercent"], 25)
        self.assertEqual(adjusted["metrics"]["rainExposurePercent"], 100)
        self.assertEqual(result["metrics"]["sunExposurePercent"], 100)
        self.assertEqual(apply_shade(result, {})["sunBasis"], "open-sky")


class ExposureApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_batch_request_and_units(self):
        def upstream(request):
            self.assertEqual(request.url.params["wind_speed_unit"], "mph")
            self.assertEqual(request.url.params["timeformat"], "unixtime")
            self.assertEqual(len(request.url.params["latitude"].split(',')), 12)
            return httpx.Response(200, json=[forecast()] * 12)
        async with httpx.AsyncClient(transport=httpx.MockTransport(upstream)) as client:
            result = await get_route_exposure(ROUTE, 600, NOON, client)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["metrics"]["sunExposurePercent"], 100)

    async def test_outage_and_malformed_batch_are_safe(self):
        for response in [httpx.Response(503), httpx.Response(200, json={}), httpx.Response(200, json=[{}])]:
            async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: response)) as client:
                result = await get_route_exposure(ROUTE, 600, NOON, client)
            self.assertEqual(result["status"], "unavailable")
            self.assertTrue(all(value is None for value in result["metrics"].values()))
