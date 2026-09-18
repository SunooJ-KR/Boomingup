# ============================================================================
# 53.export_front_boundary.py
# ============================================================================
# Author:      yjkim
# Purpose:     법정동 경계를 프론트 지도에 맞게 줄이고 자치구 외곽선을 만든다
# ============================================================================

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from shapely.geometry import mapping, shape
from shapely.ops import unary_union


WORK_DIR = Path(__file__).resolve().parents[2]
SOURCE_PATH = WORK_DIR / "output" / "52.1.seoul_bjd_boundary.geojson"
FRONT_DATA_DIR = WORK_DIR / "front" / "public" / "data"
DONG_PATH = FRONT_DATA_DIR / "dong-boundary.geojson"
GU_PATH = FRONT_DATA_DIR / "gu-boundary.geojson"

# WGS84 경위도 기준 약 3m. 공유 경계를 함께 단순화해 동 사이 틈이나 겹침을 막는다.
DONG_TOLERANCE = 0.00003
GU_TOLERANCE = 0.00005

GU_NAMES = {
    "11110": "종로구", "11140": "중구", "11170": "용산구", "11200": "성동구",
    "11215": "광진구", "11230": "동대문구", "11260": "중랑구", "11290": "성북구",
    "11305": "강북구", "11320": "도봉구", "11350": "노원구", "11380": "은평구",
    "11410": "서대문구", "11440": "마포구", "11470": "양천구", "11500": "강서구",
    "11530": "구로구", "11545": "금천구", "11560": "영등포구", "11590": "동작구",
    "11620": "관악구", "11650": "서초구", "11680": "강남구", "11710": "송파구",
    "11740": "강동구",
}


def write_geojson(path: Path, features: list[dict[str, Any]]) -> None:
    """프론트가 바로 읽을 수 있는 작은 GeoJSON을 저장한다."""
    collection = {"type": "FeatureCollection", "features": features}
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(collection, handle, ensure_ascii=False, separators=(",", ":"))
        handle.write("\n")


def main() -> None:
    """법정동·자치구 경계 정적 파일을 만들고 필수 조건을 검증한다."""
    source = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    source_features = source["features"]
    source_geometries = [shape(feature["geometry"]) for feature in source_features]
    simplified_geometries = [
        geometry.simplify(DONG_TOLERANCE, preserve_topology=True)
        for geometry in source_geometries
    ]

    dong_features: list[dict[str, Any]] = []
    gu_geometries: dict[str, list[Any]] = defaultdict(list)
    for feature, geometry in zip(source_features, simplified_geometries):
        properties = feature["properties"]
        sgg_cd = properties["sgg_cd"]
        # 자치구 결합은 단순화 전 원본으로 수행해 법정동 사이의 미세한 틈을 만들지 않는다.
        gu_geometries[sgg_cd].append(source_geometries[len(dong_features)])
        dong_features.append({
            "type": "Feature",
            "properties": {
                "dong": properties["dong"],
                "sgg_cd": sgg_cd,
                "emd_cd": properties["emd_cd"],
                "umd_nm": properties["umd_nm"],
                "gu_name": GU_NAMES[sgg_cd],
            },
            "geometry": mapping(geometry),
        })

    gu_features = []
    for sgg_cd, geometries in sorted(gu_geometries.items()):
        geometry = unary_union(geometries).simplify(GU_TOLERANCE, preserve_topology=True)
        gu_features.append({
            "type": "Feature",
            "properties": {"sgg_cd": sgg_cd, "gu_name": GU_NAMES[sgg_cd]},
            "geometry": mapping(geometry),
        })

    assert len(dong_features) == 467, f"법정동 수가 467개가 아닙니다: {len(dong_features)}"
    assert len(gu_features) == 25, f"자치구 수가 25개가 아닙니다: {len(gu_features)}"
    assert all(feature["geometry"]["type"] in {"Polygon", "MultiPolygon"} for feature in dong_features)
    assert all(feature["geometry"]["type"] in {"Polygon", "MultiPolygon"} for feature in gu_features)

    FRONT_DATA_DIR.mkdir(parents=True, exist_ok=True)
    write_geojson(DONG_PATH, dong_features)
    write_geojson(GU_PATH, gu_features)

    print(f"법정동 경계: {len(dong_features)}개 / {DONG_PATH.stat().st_size / 1024:.0f} KiB")
    print(f"자치구 경계: {len(gu_features)}개 / {GU_PATH.stat().st_size / 1024:.0f} KiB")


if __name__ == "__main__":
    main()
