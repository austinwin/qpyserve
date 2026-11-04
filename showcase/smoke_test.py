"""Run as a Docker build-time sanity check for actual geometry calculations."""
from geoengine import GeoInputError, process_features, sample_points

source = sample_points(120)
assert len(source["features"]) == 120
assert source["metadata"]["sample"] is True

for operation in ("buffer", "density", "hull"):
    result = process_features(source, operation=operation, distance_m=350, cell_m=1200)
    assert result["type"] == "FeatureCollection"
    assert result["metadata"]["input_features"] == 120
    assert result["metadata"]["output_features"] == len(result["features"])
    assert len(result["features"]) > 0
    assert result["metadata"]["output_crs"] == "EPSG:4326"
    for feature in result["features"]:
        assert feature["geometry"]["type"] in ("Polygon", "MultiPolygon")
    print(f"PASS {operation}: {len(result['features'])} geometry feature(s)")

grid = process_features(source, operation="density", cell_m=1200)
assert sum(f["properties"]["site_count"] for f in grid["features"]) == 120

try:
    process_features({"type": "FeatureCollection", "features": []}, operation="buffer")
    raise AssertionError("Empty collections must be rejected")
except GeoInputError:
    print("PASS invalid collection rejected")

print("All spatial smoke tests passed")
