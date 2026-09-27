import math
from shapely.affinity import translate
from shapely.geometry import Polygon
from shapely.ops import unary_union


def building_shadow(footprint, height_m, azimuth, elevation):
    """Flat-roof prism estimate. All lengths are meters; azimuth is clockwise from north."""
    if elevation <= 0 or height_m <= 0:
        return Polygon()
    distance = height_m / math.tan(math.radians(elevation))
    dx = -math.sin(math.radians(azimuth)) * distance
    dy = -math.cos(math.radians(azimuth)) * distance
    polygons = list(footprint.geoms) if footprint.geom_type == "MultiPolygon" else [footprint]
    pieces = [footprint, translate(footprint, xoff=dx, yoff=dy)]
    for polygon in polygons:
        for ring in [polygon.exterior, *polygon.interiors]:
            vertices = list(ring.coords)
            for a, b in zip(vertices, vertices[1:]):
                pieces.append(Polygon([a, b, (b[0] + dx, b[1] + dy), (a[0] + dx, a[1] + dy)]))
    return unary_union(pieces)
