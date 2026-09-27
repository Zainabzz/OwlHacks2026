# Philadelphia spatial data

The source datasets are kept in separate folders under `backend/data/raw/`:

- `buildings/LI_BUILDING_FOOTPRINTS.geojson` is a 474 MB GeoJSON FeatureCollection in OGC:CRS84 (longitude/latitude). It contains Polygon building footprints and `approx_hgt` and `max_hgt` values in feet. The backend prefers positive finite `approx_hgt`, falls back to positive finite `max_hgt`, and converts heights to meters. It never treats `base_elevation` as height.
- `trees/ppr_tree_inventory_2025.geojson` is the single tree dataset used by the app: a GeoJSON point inventory in OGC:CRS84 with species, trunk diameter (`tree_dbh`), and year. It has no crown outlines or tree heights.

The app reports the number of mapped 2025 inventory points within 10 meters of each route. **Tree canopy percentage and tree shade remain unavailable** because point locations do not describe canopy outlines. Do not infer canopy coverage from trunk points.

## Building index

The backend streams the large building source into a local SQLite RTree index in `backend/data/processed/buildings.sqlite3`, reprojecting features to EPSG:32618 (UTM 18N) and converting heights from feet to meters. It builds a separate RTree index for tree points in `backend/data/processed/trees.sqlite3`. The processed directory is generated, ignored by Git, and never sent to the mobile client. Both indexes are refreshed when their source or index format changes. Invalid building records are skipped during indexing; the supplied file currently has one skipped record, so routes near an omitted feature may have additional uncertainty.

The project launcher builds or refreshes the index before starting the API:

```sh
sh backend/start.sh --reload
```

You may also prepare it separately:

```sh
backend/.venv/bin/python -m backend.spatial.buildings
```

This one-time pass reads the full source file. Each route analysis then queries only nearby building footprints using the spatial index. If the source file or index is missing, stale, or unreadable, routes still return and spatial metrics remain unavailable.

## Metric meaning and limits

Building shade uses 12 arrival-time samples along the route and flat-roof prism shadows from mapped footprint geometry and approximate heights. When `approx_hgt` is missing, `max_hgt` is used; footprints with neither height are omitted and may cause the estimate to understate shade. The result is an estimate, not a sidewalk-level measurement; it omits facade shape, terrain, street furniture, and height error. Low sun or a shadow corridor beyond the downloaded footprint extent makes the estimate unavailable. Invalid source records are skipped and may cause added uncertainty if near a route.

Sun exposure combines the arrival-time Open-Meteo open-sky sunshine estimate with modeled building shade when both are available. If the hourly forecast is unavailable, sun exposure falls back to solar position and modeled building shade without cloud conditions. The tree inventory is not used to claim canopy or shade. Total route shade remains unavailable until canopy outlines are supplied. Cloud cover remains a weather metric; clouds do not alter geometric building shade. Rain exposure does not account for overhead shelter. The Philadelphia operating area is limited to longitude -75.30 to -74.95 and latitude 39.85 to 40.15.

Sources: [Philadelphia Building Footprints](https://opendataphilly.org/datasets/building-footprints/), [PPR Tree Inventory](https://opendataphilly.org/datasets/ppr-tree-inventory/), [PPR Tree Canopy](https://opendataphilly.org/datasets/ppr-tree-canopy/).
