# ============================================================================
# test_export_front_boundary.py
# ============================================================================
# Author:      yjkim
# Purpose:     프론트용 경계 축약이 모양과 형식을 지키는지 합성 도형으로 점검
# ============================================================================

import importlib.util
from pathlib import Path


def exporter():
    path = Path(__file__).with_name("53.export_front_boundary.py")
    spec = importlib.util.spec_from_file_location("front_boundary_exporter", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def square(step: float = 0.001) -> list[list[float]]:
    """한 변에 점이 여러 개 찍힌 정사각형 링. 모서리 4개만 남아야 한다."""
    steps = [round(i * step, 6) for i in range(11)]
    bottom = [[x, 0.0] for x in steps]
    right = [[0.01, y] for y in steps[1:]]
    top = [[x, 0.01] for x in reversed(steps[:-1])]
    left = [[0.0, y] for y in reversed(steps[:-1])]
    return [*bottom, *right, *top, *left]


def cell(x: float, y: float) -> list[list[float]]:
    """단위 정사각형 링. 반시계 방향으로 닫는다."""
    return [[x, y], [x + 1.0, y], [x + 1.0, y + 1.0], [x, y + 1.0], [x, y]]


def feature(ring: list[list[float]]) -> dict:
    """합치기 입력으로 쓸 최소한의 Feature."""
    return {"geometry": {"type": "Polygon", "coordinates": [ring]}}


def main():
    ex = exporter()

    # 직선 위의 점은 사라지고 모서리는 남는다. 링은 닫힌 채로 끝난다.
    ring = ex.shrink_ring(square())
    assert ring is not None and len(ring) == 5, f"모서리만 남아야 합니다: {len(ring) if ring else 0}"
    assert ring[0] == ring[-1], "링이 닫혀 있지 않습니다"
    assert [0.0, 0.0] in ring and [0.01, 0.01] in ring, "모서리가 빠졌습니다"

    # tolerance보다 큰 튀어나온 점은 남는다.
    bump = [[0.0, 0.0], [0.005, 0.001], [0.01, 0.0], [0.01, 0.01], [0.0, 0.01], [0.0, 0.0]]
    assert [0.005, 0.001] in ex.shrink_ring(bump), "tolerance를 넘는 점이 사라졌습니다"

    # 선분 길이가 0이면 점 사이 거리로 잰다. 닫힌 링의 첫 구간이 이 경우다.
    assert ex.point_segment_distance([3.0, 4.0], [0.0, 0.0], [0.0, 0.0]) == 5.0

    # 화면에 보이지 않을 만큼 작은 구멍은 버리고 바깥 링은 남긴다.
    tiny = [[0.005, 0.005], [0.005001, 0.005], [0.005, 0.005001], [0.005, 0.005]]
    assert ex.shrink_ring(tiny) is None, "면이 되지 못하는 링은 버려야 합니다"
    assert len(ex.shrink_polygon([square(), tiny])) == 1, "구멍만 빠지고 바깥 링은 남아야 합니다"

    # 바깥 링까지 사라질 정도로 작은 도형은 원본을 그대로 쓴다. 빈 도형을 내보내지 않는다.
    assert ex.shrink_polygon([tiny]) == [ex.round_ring(tiny)]

    # MultiPolygon은 형식을 그대로 유지한다.
    multi = ex.shrink_geometry({"type": "MultiPolygon", "coordinates": [[square()], [square()]]})
    assert multi["type"] == "MultiPolygon" and len(multi["coordinates"]) == 2
    assert ex.count_points(multi) == 10

    # 지수 동이 아닌 경계는 내보내지 않고, 속성은 화면이 쓰는 둘만 남는다.
    source = {"features": [
        {"properties": {"dong": "11110_청운동", "umd_nm": "청운동", "in_index": True},
         "geometry": {"type": "Polygon", "coordinates": [square()]}},
        {"properties": {"dong": "11110_효자동", "umd_nm": "효자동", "in_index": False},
         "geometry": {"type": "Polygon", "coordinates": [square()]}},
    ]}
    features, before, after = ex.build_dong_features(source)
    assert len(features) == 1 and features[0]["properties"] == {"dong": "11110_청운동", "umd_nm": "청운동"}
    assert before == 41 and after == 5, f"좌표 수가 맞지 않습니다: {before} → {after}"

    # 자치구 합치기: 맞붙은 두 동 사이의 선은 사라지고 바깥 테두리만 남는다.
    left = cell(0, 0)
    right = cell(1, 0)
    merged = ex.dissolve([feature(left), feature(right)])
    assert merged["type"] == "Polygon", merged["type"]
    ring = merged["coordinates"][0]
    assert ring[0] == ring[-1], "합친 경계가 닫혀 있지 않습니다"
    # 맞닿은 선분 (1,0)-(1,1)이 사라진다. 그 위의 점 자체는 테두리 위에 남는다
    edges = {(tuple(a), tuple(b)) for a, b in zip(ring, ring[1:])}
    assert ((1.0, 0.0), (1.0, 1.0)) not in edges and ((1.0, 1.0), (1.0, 0.0)) not in edges
    assert len(ring) == 7, f"테두리 점이 7개여야 합니다: {len(ring)}"
    # 줄이고 나면 직선 위의 점이 빠져 직사각형 모서리 4개만 남는다
    assert len(ex.shrink_ring([list(point) for point in ring])) == 5
    assert ex.signed_area([(x, y) for x, y in ring]) > 0, "바깥 링은 반시계 방향이어야 합니다"

    # 가운데가 빈 3x3은 바깥 링 하나와 구멍 하나가 된다.
    donut = [feature(cell(x, y)) for x in range(3) for y in range(3) if (x, y) != (1, 1)]
    holed = ex.dissolve(donut)
    assert holed["type"] == "Polygon" and len(holed["coordinates"]) == 2
    outer, hole = holed["coordinates"]
    assert ex.signed_area([(x, y) for x, y in outer]) > 0
    assert ex.signed_area([(x, y) for x, y in hole]) < 0, "구멍은 시계 방향이어야 합니다"
    assert {x for x, _ in hole} == {1.0, 2.0}, "구멍 자리가 가운데 칸이 아닙니다"

    # 떨어진 두 조각은 MultiPolygon이 된다.
    apart = ex.dissolve([feature(cell(0, 0)), feature(cell(5, 5))])
    assert apart["type"] == "MultiPolygon" and len(apart["coordinates"]) == 2

    # 이름 자리는 가장 넓은 조각의 무게중심이다.
    assert ex.label_point(ex.dissolve([feature(cell(0, 0))])) == [0.5, 0.5]
    big = ex.dissolve([feature(cell(0, 0)), feature(cell(10, 0)), feature(cell(11, 0))])
    assert ex.label_point(big) == [11.0, 0.5], "넓은 쪽 조각에 이름을 놓아야 합니다"

    print("합성 도형 점검 통과: 직선 축약, 튀어나온 점 유지, 링 닫힘, 작은 구멍 제거, 속성 축소, 자치구 합치기, 이름 자리")


if __name__ == "__main__": main()
