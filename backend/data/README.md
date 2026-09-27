# Optional spatial data

The API reads `buildings.geojson` and `tree_canopy.geojson` here and caches them by modification time. Missing, invalid, or out-of-coverage datasets yield null spatial metrics. No data is downloaded during a routing request.

Each file must be a WGS84 GeoJSON FeatureCollection with a top-level `coverageBbox: [west, south, east, north]` identifying the **complete surveyed/extracted area**, not just the bounds of its polygons. Geometries must be valid Polygon or MultiPolygon features. Building properties require a finite positive `height_m`. Preserve source, collection date, and attribution in top-level metadata. An empty dataset must not stand in for unavailable coverage.

Sources checked:

- [Philadelphia Building Footprints](https://opendataphilly.org/datasets/building-footprints/) and [current layer schema](https://services.arcgis.com/fLeGjb7u4uXqeF9q/ArcGIS/rest/services/Building_Footprints/FeatureServer/0). The layer exposes `approx_hgt` and `max_hgt`; measurements are feet. Convert a verified positive height to meters with `height_m = approx_hgt * 0.3048`. Do not use `base_elevation` as building height. Unknown heights stay unknown.
- [PPR Tree Canopy](https://opendataphilly.org/datasets/ppr-tree-canopy/). The 2015 canopy **outlines** describe crown extent and have LiDAR-derived heights. Tree points alone cannot represent canopy area. The 2008–2018 change layer includes lost canopy; it cannot be used unfiltered as current canopy.

Calculations use UTM 18N (meters), restricted to the Philadelphia area. Canopy coverage is the route length intersecting the union of canopy polygons. Building shade uses flat-roof prism shadows and 12 arrival-time samples based on route duration. Local building coverage must include the maximum possible shadow reach. Unknown heights or low sun can make shade unavailable. Canopy is a static overhead-coverage estimate; these estimates omit seasonal foliage, cloud cover, terrain, and facade details. At night direct sun is zero when both layers provide coverage.

Rain shelter and sidewalk-side advice remain unavailable: they need actual overhead shelter and sidewalk geometry. Do not interpret a building shadow as rain protection.
