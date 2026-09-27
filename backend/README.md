# OwlRoute backend

From the repository root, install `backend/requirements.txt` into your Python virtual environment, then run:

```sh
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

`backend/.env` supplies `MAPBOX_ACCESS_TOKEN`. It is loaded relative to `main.py`, regardless of the working directory. The token must support Mapbox Directions and Search Box. `/health` tests server availability.

Set `EXPO_PUBLIC_API_URL=http://<your-computer-LAN-IP>:8000` in `frontend/mobile/.env` for physical devices. A browser on the same computer can use `http://localhost:8000`. Restart Expo after changing the variable: `cd frontend/mobile && npx expo start --clear`.

The homepage requires location permission and a selected search result. Search suggestions and coordinate retrieval are separate backend calls using a shared session token. `/api/routes` accepts `{start: {latitude, longitude}, destination: {latitude, longitude}}` and returns shared route geometry/metrics IDs.

Weather and US AQI are starting-area modeled conditions, not measurements on each sidewalk. Optional upstream failures leave environmental metrics null while returning valid directions. Snowfall includes the model time; ice and sidewalk clearance are unknown. Keys and upstream token-bearing URLs are not returned to the client.

See [spatial data setup](data/README.md) for optional canopy and building layers. Live GPS progress and ElevenLabs voice are deferred as described in the supplied plan.

Run isolated API/spatial tests (no provider credentials or live API calls required):

```sh
python -m unittest discover -s backend/tests -v
```

Weather uses two providers in parallel: keyless Open-Meteo and OpenWeather Current Weather (`/data/2.5/weather`). Configure `OPENWEATHER_API` in `backend/.env` (the alias `OPENWEATHER_API_KEY` is also accepted), then restart Uvicorn. No provider key belongs in the frontend environment.

`GET /api/weather?latitude=39.9496&longitude=-75.1719` returns separate `providers.openMeteo` and `providers.openWeather` entries with status, normalized data, and sanitized errors. Open-Meteo is the preferred source; OpenWeather is the fallback. One failed provider does not discard the other. The route API uses the same weather service. The route screen shows both providers and their timestamps.

Both providers are requested in metric units; Fahrenheit/inch/mph fields are converted explicitly. OpenWeather's snow water equivalent remains separate from Open-Meteo's snowfall depth. An authentication failure means the configured key/account access needs attention; raw provider responses and key-bearing URLs are never returned to the browser.
