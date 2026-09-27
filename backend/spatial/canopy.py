from shapely.ops import unary_union


def covered_percent(route, polygons):
    """Length coverage in a shared meter-based CRS; overlaps count only once."""
    if route.length <= 0:
        return None
    min_x, min_y, max_x, max_y = route.bounds
    overlaps = []
    for polygon in polygons:
        left, bottom, right, top = polygon.bounds
        if right < min_x or left > max_x or top < min_y or bottom > max_y:
            continue
        clipped = route.intersection(polygon)
        if not clipped.is_empty:
            overlaps.append(clipped)
    if not overlaps:
        return 0.0
    # Union the small route-clipped line fragments, not thousands of full footprint
    # polygons and long shadows. Overlapping shadows still count only once.
    covered_length = unary_union(overlaps).length
    return round(min(100, max(0, covered_length / route.length * 100)), 1)
