"""Geometry processing in metres, returning geographic GeoJSON for Kepler.gl.

This demo is deliberately capped for the Render free tier. Production-scale jobs
need asynchronous workers, persistent object storage, and tiling.
"""
from __future__ import annotations

from collections import defaultdict
from math import floor
import random

from pyproj import Transformer
from shapely.geometry import Point, box, mapping, shape
from shapely.ops import transform, unary_union

_TO_UTM = Transformer.from_crs("EPSG:4326", "EPSG:32615", always_xy=True)
_TO_GEO = Transformer.from_crs("EPSG:32615", "EPSG:4326", always_xy=True)

MAX_FEATURES = 2500
MAX_VERTICES = 90000


class GeoInputError(ValueError):
    pass


def sample_points(count: int = 850) -> dict:
    """Synthetic, deterministic Houston-area pressure sites; NOT actual utilities."""
    rng = random.Random(712)
    feats = []
    for index in range(count):
        lon = -95.37 + rng.gauss(0, .080)
        lat = 29.76 + rng.gauss(0, .060)
        pressure = round(max(25, min(92, rng.gauss(58, 9))), 1)
        feats.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [round(lon, 6), round(lat, 6)]},
            "properties": {
                "site_id": f"SIM-{index+1:04d}",
                "pressure_psi": pressure,
                "zone": ("North", "Central", "South")[index % 3],
                "status": "Simulated",
            },
        })
    return {
        "type": "FeatureCollection",
        "features": feats,
        "metadata": {"sample": True, "name": "Synthetic Houston sites",
                     "warning": "Demonstration data only. Not City of Houston GIS or measurements."},
    }


def _number_vertices(geometry: dict) -> int:
    def walk(value):
        if not isinstance(value, list):
            return 0
        if value and isinstance(value[0], (int, float)):
            return 1
        return sum(walk(v) for v in value)
    return walk(geometry.get("coordinates", []))


def _parse_collection(collection: dict):
    if not isinstance(collection, dict) or collection.get("type") != "FeatureCollection":
        raise GeoInputError("Supply an EPSG:4326 GeoJSON FeatureCollection.")
    features = collection.get("features")
    if not isinstance(features, list) or not 1 <= len(features) <= MAX_FEATURES:
        raise GeoInputError(f"Input must contain 1–{MAX_FEATURES} GeoJSON features.")
    result = []
    vertex_total = 0
    for idx, item in enumerate(features):
        if not isinstance(item, dict) or item.get("type") != "Feature":
            raise GeoInputError(f"Feature {idx + 1} is invalid.")
        raw = item.get("geometry")
        if not isinstance(raw, dict) or raw.get("type") not in {
            "Point", "MultiPoint", "LineString", "MultiLineString", "Polygon", "MultiPolygon"
        }:
            raise GeoInputError(f"Feature {idx + 1}: unsupported or empty geometry.")
        vertex_total += _number_vertices(raw)
        if vertex_total > MAX_VERTICES:
            raise GeoInputError(f"Exceeded {MAX_VERTICES:,} coordinate vertices.")
        try:
            geom = shape(raw)
        except (ValueError, TypeError, KeyError) as exc:
            raise GeoInputError(f"Feature {idx + 1}: invalid geometry coordinates.") from exc
        if geom.is_empty or not geom.is_valid:
            raise GeoInputError(f"Feature {idx + 1}: empty or invalid geometry.")
        minx, miny, maxx, maxy = geom.bounds
        if not (-180 <= minx <= maxx <= 180 and -90 <= miny <= maxy <= 90):
            raise GeoInputError("Only longitude/latitude GeoJSON (EPSG:4326) is supported.")
        if not (-102 <= minx <= -90 and 24 <= miny <= 37):
            raise GeoInputError("This demo's UTM-15 processing supports the Texas Gulf region only.")
        projected = transform(_TO_UTM.transform, geom)
        result.append((projected, item.get("properties") or {}))
    return result


def _feature(geom, properties):
    return {
        "type": "Feature",
        "geometry": mapping(transform(_TO_GEO.transform, geom)),
        "properties": properties,
    }


def process_features(collection, *, operation, distance_m=400, cell_m=1200, dissolve=True):
    records = _parse_collection(collection)
    input_count = len(records)
    out = []
    if operation == "buffer":
        buffered = [geom.buffer(distance_m, quad_segs=8) for geom, _ in records]
        if dissolve:
            dissolved = unary_union(buffered)
            out.append(_feature(dissolved, {
                "operation": "Dissolved buffer", "distance_m": distance_m,
                "input_count": input_count, "area_sqkm": round(dissolved.area / 1e6, 3),
            }))
        else:
            for i, polygon in enumerate(buffered):
                out.append(_feature(polygon, {"operation": "Buffer", "feature": i + 1,
                                              "distance_m": distance_m}))
    elif operation == "density":
        # Grid aggregation: each input feature contributes by its projected centroid.
        buckets = defaultdict(list)
        for geom, properties in records:
            center = geom.centroid
            key = (floor(center.x / cell_m), floor(center.y / cell_m))
            p = properties.get("pressure_psi")
            pressure = p if type(p) in (float, int) else None
            buckets[key].append(pressure)
        for (x, y), pressures in buckets.items():
            valid = [p for p in pressures if p is not None]
            gridcell = box(x * cell_m, y * cell_m, (x + 1) * cell_m, (y + 1) * cell_m)
            out.append(_feature(gridcell, {
                "operation": "Density grid",
                "site_count": len(pressures),
                "avg_pressure_psi": round(sum(valid) / len(valid), 2) if valid else None,
                "cell_size_m": cell_m,
            }))
    elif operation == "hull":
        hull = unary_union([g for g, _ in records]).convex_hull
        if hull.geom_type not in ("Polygon", "MultiPolygon"):
            # Degenerate point or line data still produce valid GeoJSON.
            hull = hull.buffer(1)
        out.append(_feature(hull, {
            "operation": "Convex hull", "input_count": input_count,
            "area_sqkm": round(hull.area / 1e6, 3),
        }))
    else:
        raise GeoInputError("Supported operations: buffer, density, hull.")
    return {
        "type": "FeatureCollection",
        "features": out,
        "metadata": {
            "operation": operation,
            "input_features": input_count,
            "output_features": len(out),
            "processing_crs": "EPSG:32615", "output_crs": "EPSG:4326",
            "processed_on": "FastAPI backend",
            "simulated_input": bool(collection.get("metadata", {}).get("sample", False)),
        },
    }
