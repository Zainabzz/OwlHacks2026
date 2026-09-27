from shapely.ops import unary_union


def covered_percent(route, polygons):
    """Length coverage in a shared meter-based CRS; overlaps count only once."""
    if route.length <= 0:
        return None
    coverage = unary_union(polygons)
    return round(min(100, max(0, route.intersection(coverage).length / route.length * 100)), 1)
