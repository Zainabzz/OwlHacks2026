# Building footprint source

Place the Philadelphia `LI_BUILDING_FOOTPRINTS.geojson` dataset in this folder. The file is about 474 MB and is excluded from Git; the backend needs it locally to build `backend/data/processed/buildings.sqlite3` and calculate building shade.

The expected path is:

```text
backend/data/raw/buildings/LI_BUILDING_FOOTPRINTS.geojson
```

See [the data guide](../../README.md) for source details and processing notes.
