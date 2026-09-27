# Philadelphia spatial data

The repository contains these source files under `backend/data/raw/buildings/`:

- `LI_BUILDING_FOOTPRINTS.geojson` is a 474 MB GeoJSON FeatureCollection in OGC:CRS84 (longitude/latitude). It contains Polygon building footprints and `approx_hgt` and `max_hgt` values in feet. The backend uses only positive finite `approx_hgt` values, converted to meters; it never treats `base_elevation` as height.
- `trees/ppr_tree_inventory_2025.geojson` is a GeoJSON point inventory in OGC:CRS84. It includes species, trunk diameter (`tree_dbh`), and year, but no crown outlines or tree heights.
- `trees/TreeCanopyChange_2008_2018.csv` has class, area, and length fields but no geometry. Its gain/loss categories do not describe current canopy.

**Tree canopy percentage is therefore unavailable.** Tree points and a geometry-free gain/loss table cannot support route canopy coverage or tree shade. The API returns null for canopy coverage and explains why. Add a current canopy polygon dataset with known coverage before reporting that metric; do not infer crown extents from trunk points.

## Building index

The backend streams the large building source into a local SQLite RTree index in `backend/data/processed/buildings.sqlite3`, reprojecting features to EPSG:32618 (UTM 18N) and converting `approx_hgt` from feet to meters. The processed directory is generated, ignored by Git, and never sent to the mobile client. The index is reused until the source file changes. Invalid source records are skipped during indexing; the supplied file currently has one skipped record, so routes near an omitted feature may have additional uncertainty.

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

Building shade uses 12 arrival-time samples along the route and flat-roof prism shadows from mapped footprint geometry and approximate building heights. The resulting building shade is an estimate, not a sidewalk-level measurement; it omits facade shape, terrain, street furniture, and height error. Unknown nearby heights, low sun, or a shadow corridor beyond the downloaded footprint extent make the estimate unavailable. Invalid source records are skipped and may cause added uncertainty if near a route.

Sun exposure combines the arrival-time Open-Meteo open-sky sunshine estimate with the modeled building shade when building analysis is available. The tree inventory is not used to claim canopy or shade. Total route shade remains unavailable until current canopy polygons are supplied. Cloud cover remains a weather metric; clouds do not alter geometric building shade. Rain exposure does not account for overhead shelter. The Philadelphia operating area is limited to longitude -75.30 to -74.95 and latitude 39.85 to 40.15.

Sources: [Philadelphia Building Footprints](https://opendataphilly.org/datasets/building-footprints/), [PPR Tree Inventory](https://opendataphilly.org/datasets/ppr-tree-inventory/), [PPR Tree Canopy](https://opendataphilly.org/datasets/ppr-tree-canopy/).
