# OwlRoute backend

From the repository root, create the project environment and install dependencies once (Python 3.11 or newer):

```sh
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt
```

Start the backend with the project interpreter:

```sh
sh backend/start.sh --reload
```

The launcher also works from the backend directory as `sh start.sh --reload`. In VS Code select `backend/.venv/bin/python` using **Python: Select Interpreter** if an interpreter was already selected. The workspace default points there. Run `backend/.venv/bin/python -m pip check` to check dependency compatibility.

Start the Expo frontend in another terminal:

```sh
cd frontend/mobile
npm install
npm run web
```

For a phone, use `npm start` after setting the API URL as described below. The backend must remain running while the app is open.

`backend/.env` supplies `MAPBOX_ACCESS_TOKEN`. It is loaded relative to `main.py`, regardless of the working directory. The token must support Mapbox Directions and Search Box. `/health` tests server availability.

Set `EXPO_PUBLIC_API_URL=http://<your-computer-LAN-IP>:8000` in `frontend/mobile/.env` for physical devices. A browser on the same computer can use `http://localhost:8000`. Restart Expo after changing the variable: `cd frontend/mobile && npx expo start --clear`.

Choose a starting location and destination from search results on the homepage or route screen. GPS can fill the start, but location permission is optional when entering a start manually. Both fields also accept latitude, longitude coordinates. Search suggestions and coordinate retrieval are separate backend calls using a shared session token. `/api/routes` accepts `{start: {latitude, longitude}, destination: {latitude, longitude}}` and returns shared route geometry/metrics IDs.

Weather is a distance-weighted current-condition average from five equally spaced samples along each route geometry (endpoints have half weight). Each route includes its own `weather` object, provider averages, sample counts, and coverage percentage. Missing samples are excluded and shown as partial coverage; a complete outage leaves temperatures null. Temperature is displayed in Fahrenheit. US AQI remains a starting-area estimate. These are not measurements on each sidewalk or arrival-time forecasts. Optional upstream failures leave environmental metrics null while returning valid directions. Snowfall includes the model time; ice and sidewalk clearance are unknown. Keys and upstream token-bearing URLs are not returned to the client.

See [spatial data setup](data/README.md) for the Philadelphia building index, the limitations of the supplied tree datasets, and exposure metric assumptions. The launcher builds or refreshes the optional building index before starting. Live GPS progress and ElevenLabs voice are deferred as described in the supplied plan.

Run isolated API/spatial tests (no provider credentials or live API calls required):

```sh
backend/.venv/bin/python -m unittest discover -s backend/tests -v
```

Weather uses two providers in parallel: keyless Open-Meteo and OpenWeather Current Weather (`/data/2.5/weather`). Configure `OPENWEATHER_API` in `backend/.env` (the alias `OPENWEATHER_API_KEY` is also accepted), then restart Uvicorn. No provider key belongs in the frontend environment.

`GET /api/weather?latitude=39.9496&longitude=-75.1719` returns separate `providers.openMeteo` and `providers.openWeather` entries with status, normalized data, and sanitized errors. Open-Meteo is the preferred source; OpenWeather is the fallback. One failed provider does not discard the other. The route API uses the same weather service. The bottom route legend shows the selected route’s average temperature in Fahrenheit, using Open-Meteo with OpenWeather as a fallback. Separate provider temperature displays are omitted.

Both providers are requested in metric units; Fahrenheit/inch/mph fields are converted explicitly. OpenWeather's snow water equivalent remains separate from Open-Meteo's snowfall depth. An authentication failure means the configured key/account access needs attention; raw provider responses and key-bearing URLs are never returned to the browser.


Philadelphia exposure metrics use a separate Open-Meteo hourly forecast request for 12 equally spaced route sections, sampled at estimated arrival times using a steady walking pace. The supported area is longitude -75.30 to -74.95 and latitude 39.85 to 40.15. Forecast requests are batched by route and run alongside temperature requests; outages leave unavailable metrics null while preserving directions. Each route includes `exposure.status`, per-metric `coveragePercent`, and `sunBasis`.

- `sunExposurePercent`: percentage of sampled walking time with forecast direct normal irradiance at least 120 W/m². Nighttime samples are zero. This is an **open-sky sunshine estimate**, not sidewalk shade coverage or UV exposure. Where verified spatial layers supply route shade, it is multiplied by the route's unshaded fraction as an approximate adjustment. The legend identifies which basis is used.
- `rainExposurePercent`: percentage of sampled walking time in forecast hours with rain plus showers at least 0.1 mm. This is neither rain probability nor measured minutes of rain. It does not account for overhead shelter.
- `windImpact`: average positive headwind component in mph, calculated from forecast wind-from direction against each segment's walking bearing. Tailwinds contribute zero; opposing directions are evaluated before averaging. Wind is modeled at 10 m height and excludes street-level shelter or wind tunnels.

Accumulated rainfall and radiation use the forecast hour ending after the arrival time; instantaneous wind uses the nearest hour. Missing data is excluded from each metric independently and the legend labels partial forecast coverage. Temperature continues to show the current route average in Fahrenheit.


The route API returns up to three distinct Mapbox walking routes using a configured pace of 1.30 m/s (Mapbox's default is 1.42 m/s), so durations are more conservative. When Mapbox supplies fewer than three, the backend tries eight nearby waypoint detours in parallel with a three-second timeout per optional request. Duplicate routes and detours exceeding 2.2 times the direct distance are discarded. Fewer than three routes is valid; an unavailable alternative never removes the primary route.

Routes are ranked primarily by travel time, with the supplied modest shade/canopy preference in warm or mild dry weather and sunshine preference in cold dry weather. Forecast rain also disables the dry-weather modifier. Missing spatial data adds no bonus. Each ranked route retains its own Fahrenheit weather average and exposure forecast. `rank` starts at 1 and exactly one returned route has `isPreferred: true`. The maps and legend share this order and route colors; selecting an alternative changes the displayed metrics without changing which route is preferred.
