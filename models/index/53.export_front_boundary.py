# ============================================================================
# 53.export_front_boundary.py
# ============================================================================
# Author:      yjkim
# Purpose:     프론트 지도용 동·자치구 경계 파일을 만든다
# Description: 동 경계는 52.1(법정동)에서 지수 동만 남긴다. 자치구 경계는 행정동
#              경계에서 자치구 안쪽 선을 지워 만든다. 자치구 테두리는 법정동으로
#              나누든 행정동으로 나누든 같아서 어느 쪽을 써도 된다(결정 45).
#              둘 다 Douglas-Peucker로 점을 줄이고 좌표를 소수 5자리로 반올림한다.
#              입력이 없는 쪽은 건너뛰므로 한쪽만 있어도 돌아간다.
#              실행: python models/index/53.export_front_boundary.py
# ============================================================================

# ============================================================================
# 0. 환경 설정
# ============================================================================

from __future__ import annotations

import json
from math import atan2, pi
from pathlib import Path
from typing import Any


WORK_DIR = Path(__file__).resolve().parents[2]
DONG_SOURCE_PATH = WORK_DIR / "output" / "52.1.seoul_bjd_boundary.geojson"
GU_SOURCE_PATH = WORK_DIR / "output" / "raw" / "boundary" / "hangjeongdong_서울특별시.geojson"
DONG_TARGET_PATH = WORK_DIR / "front" / "public" / "data" / "dong-boundary.geojson"
GU_TARGET_PATH = WORK_DIR / "front" / "public" / "data" / "gu-boundary.geojson"

DONG_SOURCE_LABEL = "행정구역 경계: GIS Developer(gisdeveloper.co.kr), 원본 도로명주소 DB"
# TODO: 행정동 파일의 정확한 출처와 기준일을 확인해 문구를 확정한다(결정 45).
GU_SOURCE_LABEL = "행정구역 경계: 행정동 경계 GeoJSON (출처 확인 중)"

# 경계를 얼마나 거칠게 줄일지 정하는 값이다. 위도 1도가 약 111km이므로
# 0.00005도는 약 5.5m이고, 서울 전체가 보이는 확대 수준에서는 화면 1픽셀보다 작다.
# ponytail: 조절값이다. 확대했을 때 경계가 각져 보이면 줄이고, 파일이 무거우면 키운다.
TOLERANCE_DEG = 0.00005
# 좌표를 적는 자릿수. 소수 5자리는 약 1.1m다.
COORD_DIGITS = 5
# 링은 닫혀 있어야 하므로 좌표가 4개는 있어야 면이 된다.
MIN_RING_POINTS = 4
# 자치구 안쪽 선을 지우려면 맞닿은 두 동의 좌표가 정확히 같아야 한다. 원천마다 자릿수가
# 달라서 합치기 전에 이 자릿수로 맞춘다. 소수 6자리는 약 0.11m다.
MERGE_DIGITS = 6

EXPECTED_DONGS = 340
EXPECTED_GUS = 25

# 자치구 이름. data/db/50.load_db.py의 GU_BY_SGG_CD와 같은 표다.
GU_BY_SGG_CD = {
    "11110": "종로구", "11140": "중구", "11170": "용산구", "11200": "성동구",
    "11215": "광진구", "11230": "동대문구", "11260": "중랑구", "11290": "성북구",
    "11305": "강북구", "11320": "도봉구", "11350": "노원구", "11380": "은평구",
    "11410": "서대문구", "11440": "마포구", "11470": "양천구", "11500": "강서구",
    "11530": "구로구", "11545": "금천구", "11560": "영등포구", "11590": "동작구",
    "11620": "관악구", "11650": "서초구", "11680": "강남구", "11710": "송파구",
    "11740": "강동구",
}


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
# 2. 자치구 경계 만들기
# ============================================================================

def ring_edges(ring: list[list[float]]) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """링을 방향이 있는 선분 목록으로 바꾼다."""
    points = [(x, y) for x, y in ring]
    return list(zip(points, points[1:]))


def signed_area(ring: list[tuple[float, float]]) -> float:
    """부호 있는 면적. 양수는 반시계 방향이고 GeoJSON에서 바깥 링을 뜻한다."""
    return sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(ring, ring[1:])) / 2


def point_in_ring(point: tuple[float, float], ring: list[tuple[float, float]]) -> bool:
    """ray casting으로 점이 링 안에 있는지 본다. 구멍을 바깥 링에 붙일 때 쓴다."""
    x, y = point
    inside = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
        crosses_y = (y1 > y) != (y2 > y)
        if crosses_y and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def outer_edges(
    edges: list[tuple[tuple[float, float], tuple[float, float]]],
) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """자치구 안쪽 선을 지운다.

    붙어 있는 두 동은 같은 선분을 방향만 반대로 하나씩 갖는다. 그래서 양쪽 끝점이
    같은 선분이 두 번 이상 나오면 자치구 안쪽 선이고, 한 번만 나오면 바깥 경계다.
    이 판정은 좌표가 정확히 같아야 성립하므로, 점을 줄이기 전에 먼저 해야 한다.
    """
    seen: dict[tuple[tuple[float, float], tuple[float, float]], int] = {}
    for start, end in edges:
        seen[(start, end) if start <= end else (end, start)] = seen.get(
            (start, end) if start <= end else (end, start), 0
        ) + 1
    return [
        (start, end)
        for start, end in edges
        if seen[(start, end) if start <= end else (end, start)] == 1
    ]


def turn_angle(
    incoming: tuple[float, float], outgoing: tuple[float, float]
) -> float:
    """들어온 방향에서 나가는 방향까지 반시계로 돈 각도. 0~2π로 맞춘다."""
    angle = atan2(outgoing[1], outgoing[0]) - atan2(-incoming[1], -incoming[0])
    return angle % (2 * pi)


def stitch_rings(
    edges: list[tuple[tuple[float, float], tuple[float, float]]],
) -> list[list[tuple[float, float]]]:
    """남은 선분을 이어서 닫힌 링으로 만든다.

    한 점에서 갈 수 있는 선분이 여럿이면(자치구가 한 점에서만 닿는 자리) 가장
    시계 방향으로 꺾이는 선분을 고른다. 그래야 면을 왼쪽에 둔 채로 돌게 된다.
    """
    remaining: dict[tuple[float, float], list[tuple[float, float]]] = {}
    for start, end in edges:
        remaining.setdefault(start, []).append(end)

    rings: list[list[tuple[float, float]]] = []
    for first in list(remaining):
        while remaining.get(first):
            ring = [first]
            current = first
            previous = None
            while True:
                candidates = remaining.get(current)
                if not candidates:
                    raise ValueError("이어지지 않는 경계 선분이 있습니다.")
                if previous is None or len(candidates) == 1:
                    nxt = candidates[0]
                else:
                    incoming = (current[0] - previous[0], current[1] - previous[1])
                    nxt = min(
                        candidates,
                        key=lambda end: turn_angle(
                            incoming, (end[0] - current[0], end[1] - current[1])
                        ),
                    )
                candidates.remove(nxt)
                if not candidates:
                    del remaining[current]
                ring.append(nxt)
                previous, current = current, nxt
                if current == first:
                    break
            if len(ring) >= MIN_RING_POINTS:
                rings.append(ring)
    return rings


def rings_to_polygons(
    rings: list[list[tuple[float, float]]],
) -> list[list[list[list[float]]]]:
    """링을 바깥과 구멍으로 나누고, 구멍을 담고 있는 바깥 링에 붙인다."""
    outers = [ring for ring in rings if signed_area(ring) > 0]
    holes = [ring for ring in rings if signed_area(ring) < 0]
    if not outers:
        raise ValueError("바깥 링이 없는 자치구가 있습니다.")

    polygons: list[list[list[tuple[float, float]]]] = [[outer] for outer in outers]
    for hole in holes:
        containing = [index for index, outer in enumerate(outers) if point_in_ring(hole[0], outer)]
        if len(containing) != 1:
            raise ValueError("구멍을 담고 있는 바깥 링을 하나로 정할 수 없습니다.")
        polygons[containing[0]].append(hole)

    return [[[list(point) for point in ring] for ring in polygon] for polygon in polygons]


def dissolve(rings: list[list[list[float]]]) -> dict[str, Any]:
    """동 경계 여러 개를 자치구 경계 하나로 합친다."""
    edges: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for ring in rings:
        edges.extend(ring_edges(ring))

    polygons = rings_to_polygons(stitch_rings(outer_edges(edges)))
    if len(polygons) == 1:
        return {"type": "Polygon", "coordinates": polygons[0]}
    return {"type": "MultiPolygon", "coordinates": polygons}


def label_point(geometry: dict[str, Any]) -> list[float]:
    """이름을 적을 자리. 가장 넓은 조각의 무게중심을 쓴다.

    ponytail: 심하게 굽은 모양이면 무게중심이 면 밖으로 나갈 수 있다. 서울 자치구는
    대체로 둥글어 그런 경우가 없었다. 어긋나는 자치구가 생기면 그때 자리를 따로 적는다.
    """
    polygons = (
        [geometry["coordinates"]]
        if geometry["type"] == "Polygon"
        else geometry["coordinates"]
    )
    outers = [[(x, y) for x, y in polygon[0]] for polygon in polygons]
    ring = max(outers, key=lambda outer: abs(signed_area(outer)))
    area = signed_area(ring)
    x = sum((x1 + x2) * (x1 * y2 - x2 * y1) for (x1, y1), (x2, y2) in zip(ring, ring[1:]))
    y = sum((y1 + y2) * (x1 * y2 - x2 * y1) for (x1, y1), (x2, y2) in zip(ring, ring[1:]))
    return [round(x / (6 * area), COORD_DIGITS), round(y / (6 * area), COORD_DIGITS)]


# ============================================================================
# 3. 변환과 저장
# ============================================================================

def build_dong_features(source: dict[str, Any]) -> tuple[list[dict[str, Any]], int, int]:
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


def normalized_rings(feature: dict[str, Any]) -> list[list[list[float]]]:
    """Feature의 링을 합치기 좋은 모양으로 맞춘다.

    좌표를 같은 자릿수로 반올림하고, 반올림 때문에 겹친 이웃 점을 합친다. 또 GeoJSON
    관례대로 첫 링을 바깥(반시계), 나머지를 구멍(시계)으로 돌려 방향을 통일한다.
    방향이 섞여 있으면 남은 선분을 이어 붙일 때 면의 안팎이 뒤집힌다.
    """
    geometry = feature["geometry"]
    polygons = (
        [geometry["coordinates"]]
        if geometry["type"] == "Polygon"
        else geometry["coordinates"]
    )

    rings: list[list[list[float]]] = []
    for polygon in polygons:
        for position, ring in enumerate(polygon):
            snapped = [[round(x, MERGE_DIGITS), round(y, MERGE_DIGITS)] for x, y in ring]
            unique = [snapped[0]]
            for point in snapped[1:]:
                if point != unique[-1]:
                    unique.append(point)
            if unique[0] != unique[-1]:
                unique.append(unique[0])
            if len(unique) < MIN_RING_POINTS:
                continue
            counterclockwise = signed_area([(x, y) for x, y in unique]) > 0
            if counterclockwise != (position == 0):
                unique.reverse()
            rings.append(unique)
    return rings


def build_gu_features(source: dict[str, Any]) -> list[dict[str, Any]]:
    """자치구마다 동 경계를 합쳐 하나의 도형으로 만든다.

    자치구 안의 동을 하나도 빠뜨리지 않아야 자치구 안에 구멍이 생기지 않는다.
    """
    by_sgg_cd: dict[str, list[list[list[float]]]] = {}
    for feature in source["features"]:
        properties = feature["properties"]
        # 법정동 원천(52.1)은 sgg_cd, 행정동 원천은 sgg로 자치구를 적는다
        sgg_cd = properties.get("sgg_cd") or properties["sgg"]
        by_sgg_cd.setdefault(sgg_cd, []).extend(normalized_rings(feature))

    features = []
    for sgg_cd, rings in sorted(by_sgg_cd.items()):
        gu_name = GU_BY_SGG_CD.get(sgg_cd)
        if gu_name is None:
            raise ValueError(f"이름을 모르는 자치구 코드입니다: {sgg_cd}")
        merged = dissolve(rings)
        # 이름 자리는 줄이기 전 도형에서 잡는다. 점을 줄이다 생긴 어긋남이 자리에 섞이지 않는다
        features.append({
            "type": "Feature",
            "properties": {"sgg_cd": sgg_cd, "gu_name": gu_name, "label": label_point(merged)},
            "geometry": shrink_geometry(merged),
        })
    return features


def write_collection(path: Path, features: list[dict[str, Any]], source_label: str) -> float:
    """FeatureCollection을 저장하고 파일 크기(MiB)를 돌려준다."""
    collection = {"type": "FeatureCollection", "source": source_label, "features": features}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(collection, handle, ensure_ascii=False, separators=(",", ":"))
        handle.write("\n")
    return path.stat().st_size / (1024 * 1024)


def export_dong() -> None:
    """법정동 경계에서 지수 동만 남겨 내보낸다."""
    if not DONG_SOURCE_PATH.exists():
        print(f"건너뜀: {DONG_SOURCE_PATH}가 없습니다. 52를 먼저 실행하면 동 경계도 만든다.")
        return

    source = json.loads(DONG_SOURCE_PATH.read_text(encoding="utf-8"))
    features, before, after = build_dong_features(source)
    if len(features) != EXPECTED_DONGS:
        raise ValueError(f"지수 동 경계는 {EXPECTED_DONGS}개여야 합니다 (현재 {len(features)}개).")

    size = write_collection(DONG_TARGET_PATH, features, DONG_SOURCE_LABEL)
    print(f"동 {len(features)}개, 좌표 {before:,}개 → {after:,}개 ({after / before:.1%}), {size:.2f} MiB")
    print(f"저장: {DONG_TARGET_PATH}")


def export_gu() -> None:
    """행정동 경계를 자치구 단위로 합쳐 내보낸다."""
    if not GU_SOURCE_PATH.exists():
        print(f"건너뜀: {GU_SOURCE_PATH}가 없습니다.")
        return

    source = json.loads(GU_SOURCE_PATH.read_text(encoding="utf-8"))
    features = build_gu_features(source)
    if len(features) != EXPECTED_GUS:
        raise ValueError(f"자치구 경계는 {EXPECTED_GUS}개여야 합니다 (현재 {len(features)}개).")

    size = write_collection(GU_TARGET_PATH, features, GU_SOURCE_LABEL)
    points = sum(count_points(feature["geometry"]) for feature in features)
    print(f"자치구 {len(features)}개, 좌표 {points:,}개, {size:.2f} MiB")
    print(f"저장: {GU_TARGET_PATH}")


def main() -> None:
    """프론트용 동·자치구 경계 파일을 만든다. 입력이 없는 쪽은 건너뛴다."""
    export_dong()
    export_gu()


if __name__ == "__main__":
    main()
