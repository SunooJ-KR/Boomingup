#!/usr/bin/env python3
"""정제 산출물을 새 dataset snapshot으로 적재합니다.

기본값은 dry-run이며, --commit을 명시했을 때만 snapshot을 활성화합니다.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import psycopg
from psycopg import sql


ROOT = Path(__file__).resolve().parents[2]
EXISTING_TABLES = (
    "complex",
    "complex_metrics",
    "horizon_profile",
    "price_cell",
    "price_series",
    "estimate",
    "comparable",
    "regulation_summary",
    "share",
)
# share는 사용자 지시에 따라 snapshot 복사 대상에서 제외합니다.
SNAPSHOT_COPY_TABLES = tuple(table for table in EXISTING_TABLES if table != "share")
NEW_SNAPSHOT_TABLES = (
    "dong",
    "dong_index",
    "dong_feature",
    "market_event",
    "event_summary",
    "event_dong_path",
    "dong_prediction",
    "dong_boundary",
    "dong_support",
)

BOUNDARY_SOURCE = "GIS Developer 행정구역(읍면동) 2023-07, 원본 도로명주소 DB"
BOUNDARY_PROPERTIES = {"dong", "sgg_cd", "emd_cd", "umd_nm", "eng_nm", "in_index"}
BOUNDARY_PATH = ROOT / "output/52.1.seoul_bjd_boundary.geojson"

GU_BY_SGG_CD = {
    "11110": "종로구", "11140": "중구", "11170": "용산구", "11200": "성동구",
    "11215": "광진구", "11230": "동대문구", "11260": "중랑구", "11290": "성북구",
    "11305": "강북구", "11320": "도봉구", "11350": "노원구", "11380": "은평구",
    "11410": "서대문구", "11440": "마포구", "11470": "양천구", "11500": "강서구",
    "11530": "구로구", "11545": "금천구", "11560": "영등포구", "11590": "동작구",
    "11620": "관악구", "11650": "서초구", "11680": "강남구", "11710": "송파구",
    "11740": "강동구",
}

FEATURE_COLUMNS = (
    "sale_n_all_4q", "cancel_share_4q", "median_age_4q", "old30_share_4q",
    "sale_ppm2_med_4q", "rent_n_4q", "jeonse_share_4q", "jeonse_ppm2_med_4q",
    "rz_designated_n", "rz_committee_n", "rz_association_n", "rz_implementation_n",
    "rz_management_n", "rz_construction_n", "rz_active_households", "rz_events_4q",
    "completed_hh_4q", "completed_hh_8q", "stock_hh", "jeonse_ratio_4q",
    "completed_share_8q", "sale_n_log_change_4q", "rent_n_log_change_4q",
)
FEATURE_INTS = {
    "sale_n_all_4q", "rent_n_4q", "rz_designated_n", "rz_committee_n",
    "rz_association_n", "rz_implementation_n", "rz_management_n", "rz_construction_n",
    "rz_active_households", "rz_events_4q", "completed_hh_4q", "completed_hh_8q", "stock_hh",
}

SUPPORT_COLUMNS = (
    "sale_n_all_4q", "n_complexes_4q", "dominant_complex_share_4q", "index_se",
    "index_se_band", "sample_flags", "change_12m", "mu_12m", "delta_12m", "delta_se",
    "delta_state", "peak_5y_gap", "peak_5y_gap_se", "peak_5y_state",
    "structure_type", "structure_desc", "peer_dongs",
)
SUPPORT_INTS = {"sale_n_all_4q", "n_complexes_4q", "structure_type"}
SUPPORT_FLOATS = {
    "dominant_complex_share_4q", "index_se", "change_12m", "mu_12m",
    "delta_12m", "delta_se", "peak_5y_gap", "peak_5y_gap_se",
}
SUPPORT_FLAGS = {"FEW_SALES", "ONE_COMPLEX_DOMINATES", "HIGH_INDEX_ERROR"}
SUPPORT_ENUMS = {
    "index_se_band": ({"LOW", "MID", "HIGH"}, False),
    "delta_state": ({"DISTINGUISHABLE", "INDISTINGUISHABLE"}, False),
    "peak_5y_state": ({"AT_PEAK", "DISTINGUISHABLE", "INDISTINGUISHABLE"}, True),
}

TABLE_COLUMNS = {
    "dong": ("dong", "sgg_cd", "umd_nm", "gu_name"),
    "dong_index": ("dong", "quarter", "log_index", "log_index_se", "n_sales", "n_sales_4q", "eligible"),
    "dong_feature": ("dong", "as_of_quarter", *FEATURE_COLUMNS),
    "market_event": ("event_id", "effective_date", "category", "direction", "label", "verified", "source"),
    "event_summary": (
        "event_id", "effective_date", "category", "label", "event_quarter", "base_quarter",
        "n_dongs", "n_dongs_post", "pre_change_4q", "post_change_4q", "post_median",
        "post_p10", "post_p90", "share_same_direction", "share_up", "pre_observable",
        "post_observable", "overlapping_events", "note",
    ),
    "event_dong_path": ("event_id", "dong", "k", "quarter", "rel_log_change"),
    "dong_prediction": (
        "dong", "horizon_q", "origin", "status", "n_sales_4q", "market_hat",
        "relative_hat", "gamma", "y_hat", "change_pct_est", "lower_pct", "upper_pct",
        "model_version",
    ),
    "dong_boundary": (
        "dong", "emd_cd", "sgg_cd", "umd_nm", "eng_nm", "in_index", "geometry",
        "min_lng", "min_lat", "max_lng", "max_lat", "centroid_lng", "centroid_lat", "source",
    ),
    "dong_support": ("dong", "as_of", *SUPPORT_COLUMNS),
}

CLEAN_SOURCE_HEADERS = {
    "index": ("dong", "sggCd", "umdNm", "quarter", "dq_effect", "log_index",
              "n_sales", "n_sales_4q", "eligible", "log_index_se"),
    "feature": ("dong", "sggCd", "umdNm", "as_of_quarter", *FEATURE_COLUMNS),
    "events": ("event_id", "effective_date", "category", "label", "direction", "verified", "source"),
    "summary": TABLE_COLUMNS["event_summary"],
    "paths": ("event_id", "dong", "sggCd", "umdNm", "k", "quarter", "rel_log_change"),
    "prediction": TABLE_COLUMNS["dong_prediction"],
    "support": TABLE_COLUMNS["dong_support"],
}
QUARTER_PATTERN = re.compile(r"^[0-9]{4}Q[1-4]$")


def masked(text: str) -> str:
    """예외 문자열에 PostgreSQL URL이 섞여도 출력하지 않습니다."""
    return re.sub(r"(?:postgres(?:ql)?://)[^\s'\"]+", "postgresql://***", text, flags=re.I)


def read_dotenv_value(name: str, dotenv_path: Path = ROOT / ".env") -> str | None:
    """새 의존성 없이 단순 KEY=VALUE .env 항목만 읽습니다."""
    if not dotenv_path.is_file():
        return None
    for raw in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, separator, value = line.partition("=")
        if separator and key.strip() == name:
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
                value = value[1:-1]
            return value
    return None


def database_url(env_name: str) -> str:
    value = os.environ.get(env_name) or read_dotenv_value(env_name)
    if not value:
        raise RuntimeError(f"{env_name} 값을 환경변수 또는 .env에서 찾지 못했습니다.")
    return value


def validate_clean_header(fieldnames: list[str] | None, expected: Iterable[str], source: Path) -> None:
    """원천별 header가 순서·중복·누락 없이 정확히 일치하는지 확인합니다."""
    actual = tuple(fieldnames or ())
    required = tuple(expected)
    if actual != required or len(actual) != len(set(actual)):
        raise ValueError(f"{source}: 원천 헤더가 예상과 정확히 일치하지 않습니다.")


def _read_tsv(path: Path, expected_header: Iterable[str]) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(f"원천 파일이 없습니다: {path}")
    with path.open("r", encoding="utf-8", newline="") as handle:
        validate_clean_header(next(csv.reader(handle, delimiter="\t"), None), expected_header, path)
    return pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False, na_filter=False)


def _blank_to_none(value: Any) -> Any:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


def _require_text(frame: pd.DataFrame, columns: Iterable[str], source: str) -> None:
    """PostgreSQL NOT NULL만으로 막히지 않는 공백 text를 사전에 거부합니다."""
    for column in columns:
        frame[column] = frame[column].map(_blank_to_none)
        if frame[column].isna().any():
            raise ValueError(f"{source}: {column}은(는) 공백일 수 없습니다.")


def _require_quarter(frame: pd.DataFrame, column: str, source: str) -> None:
    _require_text(frame, (column,), source)
    if not frame[column].map(lambda value: bool(QUARTER_PATTERN.fullmatch(value))).all():
        raise ValueError(f"{source}: {column}은(는) YYYYQ1~YYYYQ4 형식이어야 합니다.")


def _require_enum(frame: pd.DataFrame, column: str, allowed: set[str], source: str, nullable: bool = False) -> None:
    """CHECK 제약에 걸리기 전에 허용 밖의 코드값을 원천 단계에서 거부합니다."""
    frame[column] = frame[column].map(_blank_to_none)
    values = set(frame[column].dropna())
    if not values.issubset(allowed):
        raise ValueError(f"{source}: {column}에 허용되지 않은 값이 있습니다: {', '.join(sorted(values - allowed))}")
    if not nullable and frame[column].isna().any():
        raise ValueError(f"{source}: {column}은(는) 비어 있을 수 없습니다.")


def validate_sample_flags(series: pd.Series) -> None:
    """';'로 이은 주의 flag가 모두 아는 코드값인지 확인합니다."""
    for value in series.dropna():
        unknown = set(value.split(";")) - SUPPORT_FLAGS
        if unknown:
            raise ValueError(f"69.1: 모르는 sample_flags가 있습니다: {', '.join(sorted(unknown))}")


def validate_peer_dongs(series: pd.Series, known_dongs: set[str]) -> None:
    """jsonb로 들어갈 문자열이 [{"dong": …, "reason": …}] 형태인지 확인합니다."""
    for value in series.dropna():
        try:
            peers = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError("69.1: peer_dongs를 JSON으로 읽을 수 없습니다.") from exc
        if not isinstance(peers, list) or not peers:
            raise ValueError("69.1: peer_dongs는 비어 있지 않은 배열이어야 합니다. 없으면 빈 칸으로 둡니다.")
        for peer in peers:
            if not isinstance(peer, dict) or set(peer) != {"dong", "reason"}:
                raise ValueError("69.1: peer_dongs 원소는 dong과 reason만 가져야 합니다.")
            if peer["dong"] not in known_dongs:
                raise ValueError(f"69.1: 60.1에 없는 peer dong이 있습니다: {peer['dong']}")


def validate_prediction_status(series: pd.Series) -> None:
    allowed_status = {"PREDICTED", "INSUFFICIENT_SALES"}
    if not set(series).issubset(allowed_status):
        raise ValueError("predictions: 허용되지 않은 status가 있습니다.")


def _strict_number(series: pd.Series, column: str, integer: bool = False) -> pd.Series:
    cleaned = series.map(_blank_to_none)
    try:
        numeric = pd.to_numeric(cleaned, errors="raise")
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{column}: 숫자로 변환할 수 없는 값이 있습니다.") from exc
    if integer:
        non_integer = numeric.dropna().map(lambda value: float(value).is_integer())
        if not non_integer.all():
            raise ValueError(f"{column}: 정수여야 하는 값에 소수점이 있습니다.")
        return numeric.astype("Int64")
    return numeric.astype(float)


def _strict_bool(series: pd.Series, column: str, nullable: bool = False) -> pd.Series:
    values = {"true": True, "false": False, "1": True, "0": False}
    result: list[bool | None] = []
    for value in series.map(_blank_to_none):
        if value is None and nullable:
            result.append(None)
        elif isinstance(value, bool):
            result.append(value)
        elif isinstance(value, str) and value.lower() in values:
            result.append(values[value.lower()])
        else:
            raise ValueError(f"{column}: boolean으로 변환할 수 없는 값이 있습니다.")
    return pd.Series(result, index=series.index, dtype="boolean")


def _date_column(series: pd.Series, column: str) -> pd.Series:
    try:
        parsed = pd.to_datetime(series.map(_blank_to_none), format="%Y-%m-%d", errors="raise")
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{column}: YYYY-MM-DD 날짜가 아닙니다.") from exc
    return parsed.dt.date


def _boundary_number(value: Any, label: str) -> float:
    """GeoJSON 위치의 유한한 경도·위도 값을 float으로 변환합니다."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"52.1: {label} 좌표가 유한한 숫자가 아닙니다.")
    return float(value)


def _ring_area_centroid(ring: list[tuple[float, float]]) -> tuple[float, float, float]:
    """닫힌 exterior ring의 평면 shoelace 면적과 중심을 계산합니다."""
    origin_lng, origin_lat = ring[0]
    twice_area = 0.0
    centroid_lng_numerator = 0.0
    centroid_lat_numerator = 0.0
    # 절대 경위도(약 127, 37)에서 cross product를 빼면 작은 면적에서
    # 부동소수 상쇄가 커지므로, ring 첫 좌표를 local 원점으로 옮겨 계산합니다.
    for (absolute_lng_a, absolute_lat_a), (absolute_lng_b, absolute_lat_b) in zip(ring, ring[1:]):
        lng_a, lat_a = absolute_lng_a - origin_lng, absolute_lat_a - origin_lat
        lng_b, lat_b = absolute_lng_b - origin_lng, absolute_lat_b - origin_lat
        cross = lng_a * lat_b - lng_b * lat_a
        twice_area += cross
        centroid_lng_numerator += (lng_a + lng_b) * cross
        centroid_lat_numerator += (lat_a + lat_b) * cross
    if math.isclose(twice_area, 0.0, abs_tol=1e-15):
        raise ValueError("52.1: 면적이 0인 exterior ring이 있습니다.")
    return (
        abs(twice_area) / 2.0,
        origin_lng + centroid_lng_numerator / (3.0 * twice_area),
        origin_lat + centroid_lat_numerator / (3.0 * twice_area),
    )


def _parse_boundary_ring(ring: Any, label: str) -> list[tuple[float, float]]:
    if not isinstance(ring, list) or len(ring) < 4:
        raise ValueError(f"52.1: {label} ring은 닫힌 좌표 4개 이상이어야 합니다.")
    parsed: list[tuple[float, float]] = []
    for position_no, position in enumerate(ring, start=1):
        if not isinstance(position, list) or len(position) < 2:
            raise ValueError(f"52.1: {label}의 {position_no}번째 좌표가 [경도, 위도]가 아닙니다.")
        parsed.append((_boundary_number(position[0], "경도"), _boundary_number(position[1], "위도")))
    if parsed[0] != parsed[-1]:
        raise ValueError(f"52.1: {label} ring이 닫혀 있지 않습니다.")
    return parsed


def transform_boundary_feature(feature: Any, feature_no: int) -> dict[str, Any]:
    """GeoJSON Feature 하나를 app.dong_boundary 적재 행으로 엄격하게 변환합니다."""
    source_label = f"52.1: {feature_no}번째 Feature"
    if not isinstance(feature, dict) or set(feature) != {"type", "properties", "geometry"}:
        raise ValueError(f"{source_label}의 키 집합이 정확하지 않습니다.")
    if feature["type"] != "Feature":
        raise ValueError(f"{source_label}의 type은 Feature여야 합니다.")
    properties = feature["properties"]
    if not isinstance(properties, dict) or set(properties) != BOUNDARY_PROPERTIES:
        raise ValueError(f"{source_label}의 properties 키 집합이 정확하지 않습니다.")
    required = ("dong", "sgg_cd", "emd_cd", "umd_nm")
    values: dict[str, str] = {}
    for name in required:
        value = _blank_to_none(properties[name])
        if not isinstance(value, str):
            raise ValueError(f"{source_label}: {name}은(는) 공백이 아닌 text여야 합니다.")
        values[name] = value
    eng_nm = _blank_to_none(properties["eng_nm"])
    if eng_nm is not None and not isinstance(eng_nm, str):
        raise ValueError(f"{source_label}: eng_nm은 text 또는 null이어야 합니다.")
    if not isinstance(properties["in_index"], bool):
        raise ValueError(f"{source_label}: in_index는 boolean이어야 합니다.")
    if values["dong"] != values["sgg_cd"] + "_" + values["umd_nm"]:
        raise ValueError(f"{source_label}: dong 불변식 위반입니다.")

    geometry = feature["geometry"]
    if not isinstance(geometry, dict) or set(geometry) != {"type", "coordinates"}:
        raise ValueError(f"{source_label}: geometry 키 집합이 정확하지 않습니다.")
    geometry_type = geometry["type"]
    if geometry_type not in {"Polygon", "MultiPolygon"}:
        raise ValueError(f"{source_label}: geometry type은 Polygon 또는 MultiPolygon이어야 합니다.")
    polygons = geometry["coordinates"] if geometry_type == "MultiPolygon" else [geometry["coordinates"]]
    if not isinstance(polygons, list) or not polygons:
        raise ValueError(f"{source_label}: polygon 좌표가 없습니다.")

    all_positions: list[tuple[float, float]] = []
    exterior_rings: list[list[tuple[float, float]]] = []
    for polygon_no, polygon in enumerate(polygons, start=1):
        if not isinstance(polygon, list) or not polygon:
            raise ValueError(f"{source_label}: {polygon_no}번째 polygon에 ring이 없습니다.")
        for ring_no, raw_ring in enumerate(polygon, start=1):
            ring = _parse_boundary_ring(raw_ring, f"{source_label} {polygon_no}-{ring_no}")
            all_positions.extend(ring)
            if ring_no == 1:
                exterior_rings.append(ring)

    # EPSG:4326 경위도를 평면으로 근사하고 exterior ring만 면적 가중합니다.
    # 따라서 interior ring(구멍)은 centroid 계산에서 제외합니다.
    areas_and_centroids = [_ring_area_centroid(ring) for ring in exterior_rings]
    total_area = sum(area for area, _, _ in areas_and_centroids)
    centroid_lng = sum(area * lng for area, lng, _ in areas_and_centroids) / total_area
    centroid_lat = sum(area * lat for area, _, lat in areas_and_centroids) / total_area
    longitudes, latitudes = zip(*all_positions, strict=True)
    return {
        "dong": values["dong"],
        "emd_cd": values["emd_cd"],
        "sgg_cd": values["sgg_cd"],
        "umd_nm": values["umd_nm"],
        "eng_nm": eng_nm,
        "in_index": properties["in_index"],
        "geometry": json.dumps(geometry, ensure_ascii=False, separators=(",", ":")),
        "min_lng": min(longitudes),
        "min_lat": min(latitudes),
        "max_lng": max(longitudes),
        "max_lat": max(latitudes),
        "centroid_lng": centroid_lng,
        "centroid_lat": centroid_lat,
        "source": BOUNDARY_SOURCE,
    }


def load_dong_boundaries(index_dongs: Iterable[str], path: Path = BOUNDARY_PATH) -> pd.DataFrame:
    """법정동 경계를 읽고 지수 포함 관계와 340개 포함 동 수를 점검합니다."""
    if not path.is_file():
        raise FileNotFoundError(f"경계 원천 파일이 없습니다: {path}")
    try:
        collection = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"52.1: GeoJSON을 해석할 수 없습니다: {path}") from exc
    if not isinstance(collection, dict) or set(collection) != {"type", "features"}:
        raise ValueError("52.1: FeatureCollection 키 집합이 정확하지 않습니다.")
    if collection["type"] != "FeatureCollection" or not isinstance(collection["features"], list):
        raise ValueError("52.1: FeatureCollection 형식이 아닙니다.")
    records = [transform_boundary_feature(feature, no) for no, feature in enumerate(collection["features"], start=1)]
    frame = pd.DataFrame(records, columns=TABLE_COLUMNS["dong_boundary"])
    if frame["dong"].duplicated().any():
        raise ValueError("52.1: 중복 dong 경계가 있습니다.")
    in_index_dongs = set(frame.loc[frame["in_index"], "dong"])
    unknown_dongs = sorted(in_index_dongs - set(index_dongs))
    if unknown_dongs:
        raise ValueError("52.1: 60.1에 없는 in_index dong이 있습니다: " + ", ".join(unknown_dongs))
    if len(in_index_dongs) != 340:
        raise ValueError(f"52.1: in_index dong은 340개여야 합니다 (현재 {len(in_index_dongs)}개).")
    return frame


def load_clean_sources(predictions: Path | None = None) -> dict[str, pd.DataFrame]:
    """원천 TSV를 읽어 DB 컬럼명·타입으로 변환하고 관계 불변식을 점검합니다."""
    index = _read_tsv(ROOT / "output/60.1.dong_index_se.txt", CLEAN_SOURCE_HEADERS["index"])
    index["sgg_cd"] = index["sggCd"].map(_blank_to_none)
    index["umd_nm"] = index["umdNm"].map(_blank_to_none)
    index["dong"] = index["dong"].map(_blank_to_none)
    _require_text(index, ("dong", "sgg_cd", "umd_nm"), "60.1")
    _require_quarter(index, "quarter", "60.1")
    expected_dong = index["sgg_cd"] + "_" + index["umd_nm"]
    if not (index["dong"] == expected_dong).all():
        raise ValueError("60.1: dong = sggCd || '_' || umdNm 불변식 위반입니다.")
    unknown_codes = sorted(set(index["sgg_cd"]) - set(GU_BY_SGG_CD))
    if unknown_codes:
        raise ValueError(f"60.1: 구 이름 매핑이 없는 sggCd가 있습니다: {', '.join(unknown_codes)}")
    index["log_index"] = _strict_number(index["log_index"], "log_index")
    index["n_sales"] = _strict_number(index["n_sales"], "n_sales", integer=True)
    index["n_sales_4q"] = _strict_number(index["n_sales_4q"], "n_sales_4q", integer=True)
    index["eligible"] = _strict_bool(index["eligible"], "eligible")
    dongs = index[["dong", "sgg_cd", "umd_nm"]].drop_duplicates().copy()
    dongs["gu_name"] = dongs["sgg_cd"].map(GU_BY_SGG_CD)
    boundaries = load_dong_boundaries(dongs["dong"])

    feature = _read_tsv(ROOT / "output/42.1.dong_features.txt", CLEAN_SOURCE_HEADERS["feature"])
    feature["dong"] = feature["dong"].map(_blank_to_none)
    feature["sgg_cd"] = feature["sggCd"].map(_blank_to_none)
    feature["umd_nm"] = feature["umdNm"].map(_blank_to_none)
    _require_text(feature, ("dong", "sgg_cd", "umd_nm"), "42.1")
    _require_quarter(feature, "as_of_quarter", "42.1")
    if not (feature["dong"] == feature["sgg_cd"] + "_" + feature["umd_nm"]).all():
        raise ValueError("42.1: dong 불변식 위반입니다.")
    if not set(feature["dong"]).issubset(set(dongs["dong"])):
        raise ValueError("42.1: 60.1에 없는 dong이 있습니다.")
    for column in FEATURE_COLUMNS:
        feature[column] = _strict_number(feature[column], column, integer=column in FEATURE_INTS)

    events = _read_tsv(ROOT / "models/index/event_dates.tsv", CLEAN_SOURCE_HEADERS["events"])
    _require_text(events, ("event_id", "category", "direction", "label"), "event_dates")
    events["effective_date"] = _date_column(events["effective_date"], "effective_date")
    events["verified"] = _strict_bool(events["verified"], "verified")

    summary = _read_tsv(ROOT / "output/46.2.event_summary.txt", CLEAN_SOURCE_HEADERS["summary"])
    _require_text(summary, ("event_id", "category", "label"), "46.2")
    _require_quarter(summary, "event_quarter", "46.2")
    _require_quarter(summary, "base_quarter", "46.2")
    summary["effective_date"] = _date_column(summary["effective_date"], "effective_date")
    for column in ("n_dongs", "n_dongs_post"):
        summary[column] = _strict_number(summary[column], column, integer=True)
    for column in ("pre_change_4q", "post_change_4q", "post_median", "post_p10", "post_p90", "share_same_direction", "share_up"):
        summary[column] = _strict_number(summary[column], column)
    for column in ("pre_observable", "post_observable"):
        summary[column] = _strict_bool(summary[column], column, nullable=True)
    if not set(summary["event_id"]).issubset(set(events["event_id"])):
        raise ValueError("46.2: event_dates.tsv에 없는 event_id가 있습니다.")

    paths = _read_tsv(ROOT / "output/46.1.event_dong_paths.txt", CLEAN_SOURCE_HEADERS["paths"])
    paths["sgg_cd"] = paths["sggCd"].map(_blank_to_none)
    paths["umd_nm"] = paths["umdNm"].map(_blank_to_none)
    _require_text(paths, ("event_id", "dong", "sgg_cd", "umd_nm"), "46.1")
    _require_quarter(paths, "quarter", "46.1")
    if not (paths["dong"] == paths["sgg_cd"] + "_" + paths["umd_nm"]).all():
        raise ValueError("46.1: dong 불변식 위반입니다.")
    if not set(paths["dong"]).issubset(set(dongs["dong"])):
        raise ValueError("46.1: 60.1에 없는 dong이 있습니다.")
    if not set(paths["event_id"]).issubset(set(events["event_id"])):
        raise ValueError("46.1: event_dates.tsv에 없는 event_id가 있습니다.")
    paths["k"] = _strict_number(paths["k"], "k", integer=True)
    paths["rel_log_change"] = _strict_number(paths["rel_log_change"], "rel_log_change")

    support = _read_tsv(ROOT / "output/69.1.dong_support.txt", CLEAN_SOURCE_HEADERS["support"])
    _require_text(support, ("dong", "structure_desc"), "69.1")
    _require_quarter(support, "as_of", "69.1")
    if support["as_of"].nunique() != 1:
        raise ValueError("69.1: 네 산출물이 같은 기준 분기 하나를 써야 합니다.")
    if not set(support["dong"]).issubset(set(dongs["dong"])):
        raise ValueError("69.1: 60.1에 없는 dong이 있습니다.")
    if support["dong"].duplicated().any():
        raise ValueError("69.1: dong이 중복됩니다. 기준 분기 하나에 동 하나여야 합니다.")
    for column in SUPPORT_INTS:
        support[column] = _strict_number(support[column], column, integer=True)
    for column in SUPPORT_FLOATS:
        support[column] = _strict_number(support[column], column)
    for column, (allowed, nullable) in SUPPORT_ENUMS.items():
        _require_enum(support, column, allowed, "69.1", nullable=nullable)
    for column in ("sample_flags", "peer_dongs"):
        support[column] = support[column].map(_blank_to_none)
    validate_sample_flags(support["sample_flags"])
    validate_peer_dongs(support["peer_dongs"], set(dongs["dong"]))
    # 매매 0건이면 비중을 낼 수 없어 결측이다. 0으로 채우면 쏠림이 없는 동과 구분되지 않는다.
    if support.loc[support["sale_n_all_4q"] == 0, "dominant_complex_share_4q"].notna().any():
        raise ValueError("69.1: 매매 0건인 동에 dominant_complex_share_4q가 있습니다.")

    prediction = pd.DataFrame(columns=TABLE_COLUMNS["dong_prediction"])
    if predictions is not None:
        prediction = _read_tsv(predictions, CLEAN_SOURCE_HEADERS["prediction"])
        _require_text(prediction, ("dong", "origin", "status", "model_version"), "predictions")
        for column in ("horizon_q", "n_sales_4q"):
            prediction[column] = _strict_number(prediction[column], column, integer=True)
        for column in ("market_hat", "relative_hat", "gamma", "y_hat", "change_pct_est", "lower_pct", "upper_pct"):
            prediction[column] = _strict_number(prediction[column], column)
        validate_prediction_status(prediction["status"])
        if not set(prediction["dong"].map(_blank_to_none)).issubset(set(dongs["dong"])):
            raise ValueError("predictions: 60.1에 없는 dong이 있습니다.")

    return {
        "dong": dongs.loc[:, TABLE_COLUMNS["dong"]],
        "dong_index": index.rename(columns={"sggCd": "sgg_cd", "umdNm": "umd_nm"}).loc[:, TABLE_COLUMNS["dong_index"]],
        "dong_feature": feature.loc[:, TABLE_COLUMNS["dong_feature"]],
        "market_event": events.loc[:, TABLE_COLUMNS["market_event"]],
        "event_summary": summary.loc[:, TABLE_COLUMNS["event_summary"]],
        "event_dong_path": paths.loc[:, TABLE_COLUMNS["event_dong_path"]],
        "dong_prediction": prediction.loc[:, TABLE_COLUMNS["dong_prediction"]],
        "dong_boundary": boundaries,
        "dong_support": support.loc[:, TABLE_COLUMNS["dong_support"]],
    }


def _copy_frame(cursor: psycopg.Cursor[Any], table: str, snapshot_id: int, frame: pd.DataFrame) -> None:
    columns = ("snapshot_id", *TABLE_COLUMNS[table])
    # write_row()은 psycopg의 text COPY 변환을 사용합니다. PostgreSQL 기본 text COPY는
    # 탭 구분이며 None을 NULL(\\N)로 전송합니다.
    statement = sql.SQL("COPY {} ({}) FROM STDIN").format(
        sql.Identifier("app", table), sql.SQL(", ").join(map(sql.Identifier, columns))
    )
    with cursor.copy(statement) as copy:
        for row in frame.loc[:, TABLE_COLUMNS[table]].itertuples(index=False, name=None):
            copy.write_row((snapshot_id, *(_blank_to_none(value) for value in row)))


def _table_exists(cursor: psycopg.Cursor[Any], table: str) -> bool:
    cursor.execute("select to_regclass(%s)", (f"app.{table}",))
    return cursor.fetchone()[0] is not None


def _copy_existing_table(cursor: psycopg.Cursor[Any], table: str, old_id: int, new_id: int) -> None:
    cursor.execute(
        """select column_name from information_schema.columns
           where table_schema = 'app' and table_name = %s order by ordinal_position""",
        (table,),
    )
    columns = [row[0] for row in cursor.fetchall()]
    if "snapshot_id" not in columns:
        raise RuntimeError(f"app.{table}에 snapshot_id 컬럼이 없습니다.")
    non_snapshot = [column for column in columns if column != "snapshot_id"]
    statement = sql.SQL("insert into {} ({}) select %s, {} from {} where snapshot_id = %s").format(
        sql.Identifier("app", table),
        sql.SQL(", ").join([sql.Identifier("snapshot_id"), *map(sql.Identifier, non_snapshot)]),
        sql.SQL(", ").join(map(sql.Identifier, non_snapshot)),
        sql.Identifier("app", table),
    )
    cursor.execute(statement, (new_id, old_id))


def _count(cursor: psycopg.Cursor[Any], table: str, snapshot_id: int) -> int:
    cursor.execute(sql.SQL("select count(*) from {} where snapshot_id = %s").format(sql.Identifier("app", table)), (snapshot_id,))
    return int(cursor.fetchone()[0])


def verify_snapshot(cursor: psycopg.Cursor[Any], old_id: int, new_id: int, frames: dict[str, pd.DataFrame]) -> dict[str, tuple[int, int]]:
    counts: dict[str, tuple[int, int]] = {}
    for table in SNAPSHOT_COPY_TABLES:
        before, after = _count(cursor, table, old_id), _count(cursor, table, new_id)
        counts[table] = (before, after)
        if before != after:
            raise RuntimeError(f"app.{table}: 기존 snapshot 복사 행 수가 다릅니다 ({before} != {after}).")
    for table, frame in frames.items():
        before, after = _count(cursor, table, old_id), _count(cursor, table, new_id)
        counts[table] = (before, after)
        if after != len(frame):
            raise RuntimeError(f"app.{table}: 적재 행 수가 원천과 다릅니다 ({after} != {len(frame)}).")
    cursor.execute("select count(*) from app.dong where snapshot_id = %s and dong <> sgg_cd || '_' || umd_nm", (new_id,))
    if cursor.fetchone()[0]:
        raise RuntimeError("app.dong 불변식 위반입니다.")
    cursor.execute(
        """select
             (select count(*) from app.dong_index x left join app.dong d using (snapshot_id, dong)
              where x.snapshot_id = %s and d.dong is null) +
             (select count(*) from app.dong_feature x left join app.dong d using (snapshot_id, dong)
              where x.snapshot_id = %s and d.dong is null) +
             (select count(*) from app.event_summary x left join app.market_event e using (snapshot_id, event_id)
              where x.snapshot_id = %s and e.event_id is null) +
             (select count(*) from app.event_dong_path x
                left join app.dong d using (snapshot_id, dong)
                left join app.market_event e using (snapshot_id, event_id)
              where x.snapshot_id = %s and (d.dong is null or e.event_id is null)) +
             (select count(*) from app.dong_prediction x left join app.dong d using (snapshot_id, dong)
              where x.snapshot_id = %s and d.dong is null) +
             (select count(*) from app.dong_support x left join app.dong d using (snapshot_id, dong)
              where x.snapshot_id = %s and d.dong is null)""",
        (new_id, new_id, new_id, new_id, new_id, new_id),
    )
    if cursor.fetchone()[0]:
        raise RuntimeError("신규 테이블 FK 위반이 있습니다.")
    return counts


def print_counts(counts: dict[str, tuple[int, int]], old_id: int, new_id: int) -> None:
    print(f"{'테이블':<24} {'기존 snapshot ' + str(old_id):>18} {'새 snapshot ' + str(new_id):>18}")
    for table, (before, after) in counts.items():
        print(f"app.{table:<20} {before:>18,} {after:>18,}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url-env", default="DATABASE_LOADER_URL")
    parser.add_argument("--as-of", default="2026-08-31")
    parser.add_argument("--note")
    parser.add_argument("--commit", action="store_true", help="검증 후 새 snapshot을 활성화하고 commit합니다.")
    parser.add_argument("--predictions", type=Path, help="dong_prediction TSV 경로입니다.")
    parser.add_argument("--validate-only", action="store_true", help="DB에 접속하지 않고 원천 파일만 검증합니다.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        pd.to_datetime(args.as_of, format="%Y-%m-%d", errors="raise")
        frames = load_clean_sources(args.predictions)
        if args.validate_only:
            if args.commit:
                raise ValueError("--validate-only와 --commit은 함께 사용할 수 없습니다.")
            print("validate-only 완료: DB에 접속하지 않고 원천 파일을 검증했습니다.")
            for table, frame in frames.items():
                print(f"app.{table}: 원천/적재 예정 {len(frame):,}행")
            return 0
        with psycopg.connect(database_url(args.database_url_env)) as connection:
            with connection.cursor() as cursor:
                missing = [table for table in NEW_SNAPSHOT_TABLES if not _table_exists(cursor, table)]
                if missing:
                    sql_by_table = {"dong_boundary": "002_dong_boundary.sql", "dong_support": "004_dong_support.sql"}
                    files = sorted({sql_by_table.get(table, "001_boomingup_tables.sql") for table in missing})
                    raise RuntimeError(
                        "신규 테이블이 없습니다. "
                        + ", ".join(f"data/db/{name}" for name in files)
                        + "을(를) 먼저 적용하세요: "
                        + ", ".join(missing)
                    )
                cursor.execute("select snapshot_id from app.dataset_snapshot where is_active order by snapshot_id")
                active = cursor.fetchall()
                if len(active) != 1:
                    raise RuntimeError(f"active snapshot은 정확히 1개여야 합니다 (현재 {len(active)}개).")
                old_id = int(active[0][0])
                cursor.execute(
                    """insert into app.dataset_snapshot (as_of, source, note, is_active)
                       values (%s, 'boomingup', %s, false) returning snapshot_id""",
                    (args.as_of, args.note or "정제 데이터 snapshot 적재"),
                )
                new_id = int(cursor.fetchone()[0])
                for table in SNAPSHOT_COPY_TABLES:
                    _copy_existing_table(cursor, table, old_id, new_id)
                for table, frame in frames.items():
                    _copy_frame(cursor, table, new_id, frame)
                counts = verify_snapshot(cursor, old_id, new_id, frames)
                if args.commit:
                    cursor.execute("update app.dataset_snapshot set is_active = false where snapshot_id = %s", (old_id,))
                    cursor.execute("update app.dataset_snapshot set is_active = true where snapshot_id = %s", (new_id,))
                    connection.commit()
                    print(f"commit 완료: active snapshot을 {old_id}에서 {new_id}로 전환했습니다.")
                else:
                    connection.rollback()
                    print("dry-run 완료: 모든 INSERT와 새 snapshot을 rollback했습니다.")
                print_counts(counts, old_id, new_id)
    except Exception as exc:
        print(f"오류: {masked(str(exc))}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
