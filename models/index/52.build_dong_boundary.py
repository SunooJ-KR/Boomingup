# ============================================================================
# 52.build_dong_boundary.py
# ============================================================================
# Author:      yjkim
# Purpose:     서울 법정동 경계를 웹 지도용 GeoJSON으로 변환하고 지수 동과 대조한다
# Description: GIS Developer(gisdeveloper.co.kr), 원본 도로명주소 DB의 2023-07
#              법정동 SHP를 사용한다. 경계 출처 표기는
#              "행정구역 경계: GIS Developer(gisdeveloper.co.kr), 원본 도로명주소 DB"이다.
# ============================================================================

# ============================================================================
# 0. 환경 설정
# ============================================================================

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import shapefile
from pyproj import Transformer


WORK_DIR = Path(__file__).resolve().parents[2]
OUTPUT_DIR = WORK_DIR / "output"
BOUNDARY_DIR = OUTPUT_DIR / "raw" / "boundary" / "emd_20230729"
SHP_PATH = BOUNDARY_DIR / "emd.shp"
INDEX_PATH = OUTPUT_DIR / "40.1.dong_index.txt"
GEOJSON_PATH = OUTPUT_DIR / "52.1.seoul_bjd_boundary.geojson"
MATCH_PATH = OUTPUT_DIR / "52.2.dong_boundary_match.txt"

EXPECTED_SEOUL_FEATURES = 467
EXPECTED_INDEX_DONGS = 346
EXPECTED_MATCHED_DONGS = 340
EXPECTED_UNMATCHED_DONGS = {
    "11200_신당동",
    "11290_청량리동",
    "11305_도봉동",
    "11410_길동",
    "11590_봉천동",
    "11620_사당동",
}
MISMATCH_NOTE = "원장 구 코드와 동 이름의 소속 구 불일치"


# ============================================================================
# 1. 도형 변환 함수
# ============================================================================

def signed_area(ring: list[list[float]]) -> float:
    """닫힌 링의 부호 있는 면적을 계산한다. 양수는 반시계 방향이다."""
    return sum(
        x1 * y2 - x2 * y1
        for (x1, y1), (x2, y2) in zip(ring, ring[1:])
    ) / 2


def close_ring(ring: list[list[float]]) -> list[list[float]]:
    """SHP 링이 닫혀 있지 않은 경우 마지막에 첫 좌표를 추가한다."""
    if ring[0] != ring[-1]:
        return [*ring, ring[0]]
    return ring


def normalize_ring(ring: list[list[float]], clockwise: bool) -> list[list[float]]:
    """GeoJSON RFC 7946의 요청 방향으로 링을 정규화한다."""
    ring = close_ring(ring)
    is_clockwise = signed_area(ring) < 0
    if is_clockwise != clockwise:
        return list(reversed(ring))
    return ring


def point_in_ring(point: list[float], ring: list[list[float]]) -> bool:
    """ray casting으로 점이 링 내부에 있는지 판정한다."""
    x, y = point
    inside = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
        crosses_y = (y1 > y) != (y2 > y)
        if crosses_y and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def shape_rings(shape: shapefile.Shape, transformer: Transformer) -> list[list[list[float]]]:
    """pyshp parts를 EPSG:4326 좌표의 닫힌 링 목록으로 나눈다."""
    points = shape.points
    starts = [*shape.parts, len(points)]
    rings: list[list[list[float]]] = []
    for start, end in zip(starts, starts[1:]):
        ring = [
            [round(longitude, 6), round(latitude, 6)]
            for longitude, latitude in (transformer.transform(x, y) for x, y in points[start:end])
        ]
        if len(ring) < 3:
            raise ValueError("세 점 미만의 링이 있습니다.")
        rings.append(close_ring(ring))
    return rings


def shape_to_geometry(shape: shapefile.Shape, transformer: Transformer) -> tuple[dict[str, Any], int]:
    """SHP Polygon을 RFC 7946 Polygon 또는 MultiPolygon으로 바꾼다.

    이 원천의 Polygon은 Shapefile 관례대로 시계 방향 링이 외곽, 반시계 방향
    링이 구멍이다. 변환 뒤에는 RFC 7946 right-hand rule에 맞춰 외곽은 반시계,
    구멍은 시계 방향으로 저장한다.
    """
    rings = shape_rings(shape, transformer)
    outer_rings = [ring for ring in rings if signed_area(ring) < 0]
    hole_rings = [ring for ring in rings if signed_area(ring) > 0]
    if not outer_rings:
        raise ValueError("외곽 링이 없는 Polygon입니다.")
    if len(outer_rings) + len(hole_rings) != len(rings):
        raise ValueError("면적이 0인 링이 있습니다.")

    polygons = [[normalize_ring(ring, clockwise=False)] for ring in outer_rings]
    normalized_outers = [polygon[0] for polygon in polygons]
    for hole in hole_rings:
        containing = [
            index for index, outer in enumerate(normalized_outers)
            if point_in_ring(hole[0], outer)
        ]
        if len(containing) != 1:
            raise ValueError("구멍 링에 대응하는 외곽 링을 하나로 결정할 수 없습니다.")
        polygons[containing[0]].append(normalize_ring(hole, clockwise=True))

    if len(polygons) == 1:
        return {"type": "Polygon", "coordinates": polygons[0]}, len(hole_rings)
    return {"type": "MultiPolygon", "coordinates": polygons}, len(hole_rings)


def make_feature(
    shape: shapefile.Shape,
    record: dict[str, str],
    transformer: Transformer,
    index_dongs: set[str],
) -> tuple[dict[str, Any], int]:
    """SHP record 하나에서 GeoJSON Feature와 구멍 수를 만든다."""
    emd_cd = str(record["EMD_CD"]).strip()
    umd_nm = str(record["EMD_KOR_NM"]).strip()
    dong = f"{emd_cd[:5]}_{umd_nm}"
    geometry, hole_count = shape_to_geometry(shape, transformer)
    return {
        "type": "Feature",
        "properties": {
            "dong": dong,
            "sgg_cd": emd_cd[:5],
            "emd_cd": emd_cd,
            "umd_nm": umd_nm,
            "eng_nm": str(record["EMD_ENG_NM"]).strip(),
            "in_index": dong in index_dongs,
        },
        "geometry": geometry,
    }, hole_count


def iter_coordinates(geometry: dict[str, Any]):
    """Polygon과 MultiPolygon의 모든 좌표를 순회한다."""
    polygons = (
        [geometry["coordinates"]]
        if geometry["type"] == "Polygon"
        else geometry["coordinates"]
    )
    for polygon in polygons:
        for ring in polygon:
            yield from ring


# ============================================================================
# 2. 입력 적재와 검증
# ============================================================================

def load_index_dongs(index_path: Path) -> list[str]:
    """지수 원천에서 중복 없는 동 키를 읽는다."""
    index = pd.read_csv(index_path, sep="\t", dtype={"dong": "string"})
    dongs = sorted(index["dong"].dropna().unique().tolist())
    assert len(dongs) == EXPECTED_INDEX_DONGS, f"지수 동 수가 {EXPECTED_INDEX_DONGS}개가 아닙니다: {len(dongs)}"
    return dongs


def build_features(index_dongs: set[str]) -> tuple[list[dict[str, Any]], int, int]:
    """서울 법정동 Feature를 만들고 멀티파트·구멍 동 수를 센다."""
    transformer = Transformer.from_crs("EPSG:5179", "EPSG:4326", always_xy=True)
    reader = shapefile.Reader(str(SHP_PATH), encoding="cp949")
    features: list[dict[str, Any]] = []
    multipart_count = 0
    hole_dong_count = 0
    for shape_record in reader.iterShapeRecords():
        record = shape_record.record.as_dict()
        if not str(record["EMD_CD"]).startswith("11"):
            continue
        feature, hole_count = make_feature(shape_record.shape, record, transformer, index_dongs)
        features.append(feature)
        if len(shape_record.shape.parts) > 1:
            multipart_count += 1
        if hole_count:
            hole_dong_count += 1
    return features, multipart_count, hole_dong_count


def validate_features(features: list[dict[str, Any]], index_dongs: set[str]) -> None:
    """도형 수, 키, 좌표 범위, 지수 매칭 상태를 검증한다."""
    assert len(features) == EXPECTED_SEOUL_FEATURES, (
        f"서울 도형 수가 {EXPECTED_SEOUL_FEATURES}개가 아닙니다: {len(features)}"
    )
    boundary_dongs = {feature["properties"]["dong"] for feature in features}
    assert len(boundary_dongs) == len(features), "dong 키가 중복됩니다."
    for feature in features:
        for longitude, latitude in iter_coordinates(feature["geometry"]):
            assert 126.7 <= longitude <= 127.3, f"서울 경도 범위를 벗어났습니다: {longitude}"
            assert 37.4 <= latitude <= 37.75, f"서울 위도 범위를 벗어났습니다: {latitude}"
    matched_dongs = index_dongs & boundary_dongs
    unmatched_dongs = index_dongs - boundary_dongs
    assert len(matched_dongs) == EXPECTED_MATCHED_DONGS, (
        f"지수 매칭 수가 {EXPECTED_MATCHED_DONGS}개가 아닙니다: {len(matched_dongs)}"
    )
    assert unmatched_dongs == EXPECTED_UNMATCHED_DONGS, (
        f"지수 미매칭 동이 예상과 다릅니다: {sorted(unmatched_dongs)}"
    )


# ============================================================================
# 3. 출력
# ============================================================================

def write_outputs(features: list[dict[str, Any]], index_dongs: list[str]) -> None:
    """GeoJSON과 지수-경계 대조표를 저장한다."""
    collection = {"type": "FeatureCollection", "features": features}
    with GEOJSON_PATH.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(collection, handle, ensure_ascii=False, separators=(",", ":"))
        handle.write("\n")

    boundary_by_dong = {feature["properties"]["dong"]: feature["properties"] for feature in features}
    match = pd.DataFrame({"dong": index_dongs})
    match["has_boundary"] = match["dong"].isin(boundary_by_dong)
    match["emd_cd"] = match["dong"].map(
        lambda dong: boundary_by_dong.get(dong, {}).get("emd_cd", "")
    )
    match["note"] = match["has_boundary"].map(
        lambda has_boundary: "" if has_boundary else MISMATCH_NOTE
    )
    match.to_csv(MATCH_PATH, sep="\t", index=False, lineterminator="\n")


def main() -> None:
    """서울 법정동 경계를 생성하고 결과를 요약한다."""
    index_dongs = load_index_dongs(INDEX_PATH)
    index_dong_set = set(index_dongs)
    features, multipart_count, hole_dong_count = build_features(index_dong_set)
    validate_features(features, index_dong_set)
    write_outputs(features, index_dongs)

    matched_count = sum(feature["properties"]["in_index"] for feature in features)
    size_mib = GEOJSON_PATH.stat().st_size / (1024 * 1024)
    print(f"서울 도형 수: {len(features)}개")
    print(f"지수 동 매칭 수: {matched_count}개 / {len(index_dongs)}개")
    print(f"원천 멀티파트 동 수: {multipart_count}개 / 구멍 포함 동 수: {hole_dong_count}개")
    print(f"GeoJSON 파일 크기: {size_mib:.2f} MiB")
    print(f"GeoJSON: {GEOJSON_PATH}")
    print(f"대조표: {MATCH_PATH}")


if __name__ == "__main__":
    main()
