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
    features, before, after = ex.build_features(source)
    assert len(features) == 1 and features[0]["properties"] == {"dong": "11110_청운동", "umd_nm": "청운동"}
    assert before == 41 and after == 5, f"좌표 수가 맞지 않습니다: {before} → {after}"

    print("합성 도형 점검 통과: 직선 축약, 튀어나온 점 유지, 링 닫힘, 작은 구멍 제거, 속성 축소")


if __name__ == "__main__": main()
