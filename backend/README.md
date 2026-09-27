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
