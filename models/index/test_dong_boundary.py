# ============================================================================
# test_dong_boundary.py
# ============================================================================
# Author:      yjkim
# Purpose:     법정동 경계 변환의 좌표계·링 방향·키·지수 매칭 플래그를 합성 도형으로 점검한다
# ============================================================================

# ============================================================================
# 0. 모듈 적재
# ============================================================================

import importlib.util
from pathlib import Path
from types import SimpleNamespace

from pyproj import Transformer


SCRIPT_PATH = Path(__file__).with_name("52.build_dong_boundary.py")
spec = importlib.util.spec_from_file_location("build_dong_boundary", SCRIPT_PATH)
assert spec is not None and spec.loader is not None
boundary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(boundary)


# ============================================================================
# 1. 합성 도형 생성
# ============================================================================

def project_ring(ring: list[list[float]], transformer: Transformer) -> list[tuple[float, float]]:
    """경위도 링을 원천 EPSG:5186 좌표로 바꾼다."""
    return [transformer.transform(longitude, latitude) for longitude, latitude in ring]


to_5186 = Transformer.from_crs("EPSG:4326", "EPSG:5186", always_xy=True)
to_4326 = Transformer.from_crs("EPSG:5186", "EPSG:4326", always_xy=True)

# 원천 Shapefile 규약: 외곽은 시계 방향, 구멍은 반시계 방향이다.
outer_one_ccw = [
    [126.950000, 37.550000], [126.960000, 37.550000], [126.960000, 37.560000],
    [126.950000, 37.560000], [126.950000, 37.550000],
]
hole_one_ccw = [
    [126.953000, 37.553000], [126.957000, 37.553000], [126.957000, 37.557000],
    [126.953000, 37.557000], [126.953000, 37.553000],
]
outer_two_ccw = [
    [126.970000, 37.550000], [126.980000, 37.550000], [126.980000, 37.560000],
    [126.970000, 37.560000], [126.970000, 37.550000],
]
source_rings = [list(reversed(outer_one_ccw)), hole_one_ccw, list(reversed(outer_two_ccw))]
source_points = [point for ring in source_rings for point in project_ring(ring, to_5186)]
part_starts = []
offset = 0
for ring in source_rings:
    part_starts.append(offset)
    offset += len(ring)
shape = SimpleNamespace(points=source_points, parts=part_starts)
record = {"EMD_CD": "11110101", "COL_ADM_SE": "11110", "EMD_NM": "청운동"}


# ============================================================================
# 2. 변환 결과 검증
# ============================================================================

feature, hole_count = boundary.make_feature(shape, record, to_4326, {"11110_청운동"})
properties = feature["properties"]
geometry = feature["geometry"]

assert properties == {
    "dong": "11110_청운동",
    "sgg_cd": "11110",
    "emd_cd": "11110101",
    "umd_nm": "청운동",
    "eng_nm": "",
    "in_index": True,
}
assert geometry["type"] == "MultiPolygon"
assert len(geometry["coordinates"]) == 2
assert hole_count == 1

# EPSG:5186 → EPSG:4326 결과는 [경도, 위도] 순서이고 소수점 여섯째 자리까지 저장된다.
first_longitude, first_latitude = geometry["coordinates"][0][0][0]
assert (first_longitude, first_latitude) == (126.95, 37.55)

# RFC 7946: 외곽은 반시계(양수), 구멍은 시계(음수)여야 한다.
for polygon in geometry["coordinates"]:
    assert boundary.signed_area(polygon[0]) > 0
assert boundary.signed_area(geometry["coordinates"][0][1]) < 0

_, unmatched_hole_count = boundary.make_feature(shape, record, to_4326, set())
assert unmatched_hole_count == 1
assert boundary.make_feature(shape, record, to_4326, set())[0]["properties"]["in_index"] is False

print("합성 도형 점검 통과: 좌표 변환, 링 방향, dong 키, in_index 플래그")
