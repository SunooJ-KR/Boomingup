# ============================================================================
# 53.export_front_boundary.py
# ============================================================================
# Author:      yjkim
# Purpose:     52.1 경계 GeoJSON을 프론트 지도용으로 줄여서 front/public/data에 둔다
# Description: 지수 동(in_index)만 남기고 Douglas-Peucker로 점을 줄인 뒤 좌표를
#              소수 5자리로 반올림한다. 결정 40의 출처 표기 문구를 파일 안에 함께
#              넣어 화면이 출처를 따로 들고 있지 않아도 되게 한다.
#              실행: python models/index/53.export_front_boundary.py
# ============================================================================

# ============================================================================
# 0. 환경 설정
# ============================================================================

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


WORK_DIR = Path(__file__).resolve().parents[2]
SOURCE_PATH = WORK_DIR / "output" / "52.1.seoul_bjd_boundary.geojson"
TARGET_PATH = WORK_DIR / "front" / "public" / "data" / "dong-boundary.geojson"

SOURCE_LABEL = "행정구역 경계: GIS Developer(gisdeveloper.co.kr), 원본 도로명주소 DB"

# 경계를 얼마나 거칠게 줄일지 정하는 값이다. 위도 1도가 약 111km이므로
# 0.00005도는 약 5.5m이고, 서울 전체가 보이는 확대 수준에서는 화면 1픽셀보다 작다.
# ponytail: 조절값이다. 확대했을 때 경계가 각져 보이면 줄이고, 파일이 무거우면 키운다.
TOLERANCE_DEG = 0.00005
# 좌표를 적는 자릿수. 소수 5자리는 약 1.1m다.
COORD_DIGITS = 5
# 링은 닫혀 있어야 하므로 좌표가 4개는 있어야 면이 된다.
MIN_RING_POINTS = 4

EXPECTED_DONGS = 340


# ============================================================================
# 1. 좌표 줄이기
# ============================================================================

def point_segment_distance(
    point: list[float], start: list[float], end: list[float]
) -> float:
    """점과 선분 사이 거리. 선분 길이가 0이면 두 점 사이 거리로 본다."""
    px, py = point
    x1, y1 = start
    x2, y2 = end
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        return ((px - x1) ** 2 + (py - y1) ** 2) ** 0.5
    t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    return ((px - (x1 + t * dx)) ** 2 + (py - (y1 + t * dy)) ** 2) ** 0.5


def simplify(points: list[list[float]], tolerance: float) -> list[list[float]]:
    """Douglas-Peucker로 모양을 유지하면서 점을 줄인다. 양 끝점은 항상 남는다.

    닫힌 링은 첫 점과 끝 점이 같아 기준 선분의 길이가 0이 되는데,
    이때는 점 사이 거리를 쓰므로 가장 먼 점이 먼저 남고 그다음부터 나뉜다.
    구간을 재귀 대신 stack으로 들고 있어서, 점이 아주 많은 링에서도
    재귀 깊이 제한에 걸리지 않는다.
    """
    if len(points) <= 2:
        return points

    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        start, end = stack.pop()
        if end - start < 2:
            continue
        farthest = start
        max_distance = 0.0
        for index in range(start + 1, end):
            distance = point_segment_distance(points[index], points[start], points[end])
            if distance > max_distance:
                farthest = index
                max_distance = distance
        if max_distance <= tolerance:
            continue
        keep[farthest] = True
        stack.append((start, farthest))
        stack.append((farthest, end))

    return [point for point, kept in zip(points, keep) if kept]


def round_ring(ring: list[list[float]]) -> list[list[float]]:
    """좌표를 반올림하고, 반올림 때문에 겹친 이웃 점을 하나로 합친다."""
    rounded = [[round(x, COORD_DIGITS), round(y, COORD_DIGITS)] for x, y in ring]
    unique = [rounded[0]]
    for point in rounded[1:]:
        if point != unique[-1]:
            unique.append(point)
    return unique


def shrink_ring(ring: list[list[float]]) -> list[list[float]] | None:
    """링 하나를 줄인다. 줄인 결과가 면이 되지 못하면 None을 돌려준다.

    면이 안 될 만큼 작은 링은 화면에서도 보이지 않으므로 그냥 버린다.
    바깥 링이 이렇게 사라지면 호출한 쪽에서 원본 링을 그대로 쓴다.
    """
    shrunk = round_ring(simplify(ring, TOLERANCE_DEG))
    if shrunk[0] != shrunk[-1]:
        shrunk.append(shrunk[0])
    if len(shrunk) < MIN_RING_POINTS:
        return None
    return shrunk


def shrink_polygon(polygon: list[list[list[float]]]) -> list[list[list[float]]]:
    """바깥 링과 구멍 링을 줄인다. 바깥 링이 사라지면 원본을 그대로 쓴다."""
    outer = shrink_ring(polygon[0])
    if outer is None:
        return [round_ring(ring) for ring in polygon]
    holes = [shrunk for ring in polygon[1:] if (shrunk := shrink_ring(ring)) is not None]
    return [outer, *holes]


def shrink_geometry(geometry: dict[str, Any]) -> dict[str, Any]:
    """Polygon과 MultiPolygon을 같은 형식 그대로 줄인다."""
    if geometry["type"] == "Polygon":
        return {"type": "Polygon", "coordinates": shrink_polygon(geometry["coordinates"])}
    polygons = [shrink_polygon(polygon) for polygon in geometry["coordinates"]]
    return {"type": "MultiPolygon", "coordinates": polygons}


def count_points(geometry: dict[str, Any]) -> int:
    """도형이 가진 좌표 수를 센다. 얼마나 줄었는지 보고할 때 쓴다."""
    polygons = (
        [geometry["coordinates"]]
        if geometry["type"] == "Polygon"
        else geometry["coordinates"]
    )
    return sum(len(ring) for polygon in polygons for ring in polygon)


# ============================================================================
# 2. 변환과 저장
# ============================================================================

def build_features(source: dict[str, Any]) -> tuple[list[dict[str, Any]], int, int]:
    """지수 동만 남기고 도형을 줄인다. 줄이기 전후 좌표 수도 함께 돌려준다."""
    features: list[dict[str, Any]] = []
    before = 0
    after = 0
    for feature in source["features"]:
        properties = feature["properties"]
        if not properties["in_index"]:
            continue
        geometry = shrink_geometry(feature["geometry"])
        before += count_points(feature["geometry"])
        after += count_points(geometry)
        features.append({
            "type": "Feature",
            # 화면은 동 키로 목록과 맞추고 이름만 보여 주므로 나머지 속성은 뺀다
            "properties": {"dong": properties["dong"], "umd_nm": properties["umd_nm"]},
            "geometry": geometry,
        })
    return features, before, after


def main() -> None:
    """52.1을 읽어 프론트용 경계 파일을 만들고 결과를 요약한다."""
    if not SOURCE_PATH.exists():
        raise SystemExit(
            f"{SOURCE_PATH}가 없습니다. models/index/52.build_dong_boundary.py를 먼저 실행하세요."
        )

    source = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    features, before, after = build_features(source)
    if len(features) != EXPECTED_DONGS:
        raise ValueError(f"지수 동 경계는 {EXPECTED_DONGS}개여야 합니다 (현재 {len(features)}개).")

    collection = {"type": "FeatureCollection", "source": SOURCE_LABEL, "features": features}
    TARGET_PATH.parent.mkdir(parents=True, exist_ok=True)
    with TARGET_PATH.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(collection, handle, ensure_ascii=False, separators=(",", ":"))
        handle.write("\n")

    size_mib = TARGET_PATH.stat().st_size / (1024 * 1024)
    source_mib = SOURCE_PATH.stat().st_size / (1024 * 1024)
    print(f"동 수: {len(features)}개")
    print(f"좌표 수: {before:,}개 → {after:,}개 ({after / before:.1%})")
    print(f"파일 크기: {source_mib:.2f} MiB → {size_mib:.2f} MiB")
    print(f"저장: {TARGET_PATH}")


if __name__ == "__main__":
    main()
