#!/usr/bin/env python3
"""DB 연결 없이 정제·원장 적재의 파일 파싱과 변환을 점검합니다."""

from __future__ import annotations

import csv
import decimal
import importlib.util
import math
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]


def load_module(filename: str, name: str):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def line_data_count(path: Path) -> int:
    """제공 원천은 한 레코드가 한 줄인 TSV이므로 빠르게 데이터 행 수를 셉니다."""
    with path.open("rb") as handle:
        return max(0, sum(1 for _ in handle) - 1)


def expect_value_error(callback) -> None:
    try:
        callback()
    except ValueError:
        return
    raise AssertionError("ValueError가 발생해야 합니다.")


def fixture_row(trades, kind: str) -> dict[str, str]:
    row = {column: "" for column in trades.SOURCE_COLUMNS[kind]}
    row.update({
        "aptSeq": "A-1", "aptNm": "단지", "umdNm": "역삼동", "buildYear": "2000",
        "excluUseAr": "84.50", "floor": "12", "dealYear": "2026", "dealMonth": "08",
        "dealDay": "31", "sggCd": "11680", "deal_ym": "202608", "gu": "강남구",
    })
    if kind == "sale":
        row.update({"bonbun": "0000", "bubun": "0001", "roadNmBonbun": "0000", "roadNmBubun": "0002", "is_cancelled": "False", "deal_amount_manwon": "12345.67"})
    else:
        row.update({"roadNmBonbun": "0000", "roadNmBubun": "0002", "is_jeonse": "True", "deposit_manwon": "12345.67", "monthly_rent_manwon": "0"})
    return row


def run_fixture_tests(clean, trades) -> None:
    """DB 없이 변환의 성공값과 필수 실패 경로를 작고 독립적인 fixture로 확인합니다."""
    sale = fixture_row(trades, "sale")
    sale_values = trades.transform_trade_row(sale, "sale", 1)
    sale_columns = trades.TABLE_COLUMNS["sale"]
    assert sale_values[sale_columns.index("bonbun")] == "0000"
    assert sale_values[sale_columns.index("bubun")] == "0001"
    assert sale_values[sale_columns.index("is_cancelled")] is False
    assert sale_values[sale_columns.index("deal_amount_manwon")].as_tuple().exponent == -2
    assert sale_values[sale_columns.index("cdeal_type")] is None

    rent = fixture_row(trades, "rent")
    rent_values = trades.transform_trade_row(rent, "rent", 1)
    rent_columns = trades.TABLE_COLUMNS["rent"]
    assert rent_values[rent_columns.index("road_nm_bonbun")] == "0000"
    assert rent_values[rent_columns.index("is_jeonse")] is True
    assert rent_values[rent_columns.index("monthly_rent_manwon")] == 0

    expect_value_error(lambda: clean.validate_clean_header(["dong", "dong"], clean.CLEAN_SOURCE_HEADERS["index"], Path("fixture")))
    expect_value_error(lambda: trades.validate_trade_header(list(trades.SOURCE_COLUMNS["sale"][:-1]), "sale"))
    expect_value_error(lambda: clean._strict_number(pd.Series(["invalid"]), "number"))
    expect_value_error(lambda: clean._strict_bool(pd.Series(["maybe"]), "boolean"))
    expect_value_error(lambda: clean._date_column(pd.Series(["2026-02-30"]), "date"))
    assert clean._blank_to_none("   ") is None
    expect_value_error(lambda: clean._strict_number(pd.Series(["1.5"]), "integer", integer=True))
    expect_value_error(lambda: clean.validate_prediction_status(pd.Series(["UNKNOWN"])))
    expect_value_error(lambda: clean._require_quarter(pd.DataFrame({"quarter": ["2026Q5"]}), "quarter", "fixture"))

    missing = fixture_row(trades, "sale")
    del missing["aptSeq"]
    expect_value_error(lambda: trades.transform_trade_row(missing, "sale", 1))
    extra = fixture_row(trades, "sale")
    extra[None] = ["too-many-fields"]
    expect_value_error(lambda: trades.transform_trade_row(extra, "sale", 1))


def boundary_feature(geometry: dict, **properties: object) -> dict:
    base = {
        "dong": "11110_테스트동", "sgg_cd": "11110", "emd_cd": "11110101",
        "umd_nm": "테스트동", "eng_nm": "Test-dong", "in_index": False,
    }
    base.update(properties)
    return {"type": "Feature", "properties": base, "geometry": geometry}


def decimal_boundary_centroid(exterior_rings: list[list[list[float]]]) -> tuple[decimal.Decimal, decimal.Decimal]:
    """50자리 Decimal local-coordinate shoelace 기준값을 독립 계산합니다."""
    with decimal.localcontext() as context:
        context.prec = 50
        weighted_lng = decimal.Decimal(0)
        weighted_lat = decimal.Decimal(0)
        total_area = decimal.Decimal(0)
        for raw_ring in exterior_rings:
            ring = [(decimal.Decimal(str(lng)), decimal.Decimal(str(lat))) for lng, lat in raw_ring]
            origin_lng, origin_lat = ring[0]
            twice_area = decimal.Decimal(0)
            centroid_lng_numerator = decimal.Decimal(0)
            centroid_lat_numerator = decimal.Decimal(0)
            for (lng_a, lat_a), (lng_b, lat_b) in zip(ring, ring[1:]):
                lng_a -= origin_lng
                lat_a -= origin_lat
                lng_b -= origin_lng
                lat_b -= origin_lat
                cross = lng_a * lat_b - lng_b * lat_a
                twice_area += cross
                centroid_lng_numerator += (lng_a + lng_b) * cross
                centroid_lat_numerator += (lat_a + lat_b) * cross
            area = abs(twice_area) / 2
            centroid_lng = origin_lng + centroid_lng_numerator / (3 * twice_area)
            centroid_lat = origin_lat + centroid_lat_numerator / (3 * twice_area)
            total_area += area
            weighted_lng += area * centroid_lng
            weighted_lat += area * centroid_lat
        return weighted_lng / total_area, weighted_lat / total_area


def previous_boundary_centroid(exterior_rings: list[list[list[float]]]) -> tuple[float, float]:
    """B01 수정 전 절대 좌표 shoelace 식을 regression 검출용으로 재현합니다."""
    weighted_lng = 0.0
    weighted_lat = 0.0
    total_area = 0.0
    for ring in exterior_rings:
        twice_area = 0.0
        centroid_lng_numerator = 0.0
        centroid_lat_numerator = 0.0
        for (lng_a, lat_a), (lng_b, lat_b) in zip(ring, ring[1:]):
            cross = lng_a * lat_b - lng_b * lat_a
            twice_area += cross
            centroid_lng_numerator += (lng_a + lng_b) * cross
            centroid_lat_numerator += (lat_a + lat_b) * cross
        area = abs(twice_area) / 2.0
        total_area += area
        weighted_lng += area * (centroid_lng_numerator / (3.0 * twice_area))
        weighted_lat += area * (centroid_lat_numerator / (3.0 * twice_area))
    return weighted_lng / total_area, weighted_lat / total_area


def assert_decimal_centroid(row: dict, exterior_rings: list[list[list[float]]]) -> None:
    """loader 결과가 Decimal 기준값에서 1e-9도 이내인지 확인합니다."""
    expected_lng, expected_lat = decimal_boundary_centroid(exterior_rings)
    tolerance = decimal.Decimal("1e-9")
    assert abs(decimal.Decimal(str(row["centroid_lng"])) - expected_lng) <= tolerance
    assert abs(decimal.Decimal(str(row["centroid_lat"])) - expected_lat) <= tolerance
    previous_lng, previous_lat = previous_boundary_centroid(exterior_rings)
    assert max(
        abs(decimal.Decimal(str(previous_lng)) - expected_lng),
        abs(decimal.Decimal(str(previous_lat)) - expected_lat),
    ) > tolerance


def run_boundary_fixture_tests(clean) -> None:
    """Polygon·MultiPolygon 및 구멍이 있는 합성 경계의 공간값을 DB 없이 점검합니다."""
    polygon = boundary_feature({
        "type": "Polygon",
        "coordinates": [
            [[0, 0], [4, 0], [4, 4], [0, 4], [0, 0]],
            [[0.5, 0.5], [1.5, 0.5], [1.5, 1.5], [0.5, 1.5], [0.5, 0.5]],
        ],
    })
    polygon_row = clean.transform_boundary_feature(polygon, 1)
    assert polygon_row["geometry"] == '{"type":"Polygon","coordinates":[[[0,0],[4,0],[4,4],[0,4],[0,0]],[[0.5,0.5],[1.5,0.5],[1.5,1.5],[0.5,1.5],[0.5,0.5]]]}'
    assert (polygon_row["min_lng"], polygon_row["min_lat"], polygon_row["max_lng"], polygon_row["max_lat"]) == (0.0, 0.0, 4.0, 4.0)
    # 구멍은 centroid 면적 가중에서 제외하므로 exterior 정사각형의 중심을 유지합니다.
    assert math.isclose(polygon_row["centroid_lng"], 2.0)
    assert math.isclose(polygon_row["centroid_lat"], 2.0)

    multipolygon = boundary_feature({
        "type": "MultiPolygon",
        "coordinates": [
            [[[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]]],
            [[[10, 0], [14, 0], [14, 4], [10, 4], [10, 0]]],
        ],
    })
    multipolygon_row = clean.transform_boundary_feature(multipolygon, 2)
    assert (multipolygon_row["min_lng"], multipolygon_row["min_lat"], multipolygon_row["max_lng"], multipolygon_row["max_lat"]) == (0.0, 0.0, 14.0, 4.0)
    assert math.isclose(multipolygon_row["centroid_lng"], 9.8)
    assert math.isclose(multipolygon_row["centroid_lat"], 1.8)

    # 서울 EPSG:4326 범위의 작은 도형은 절대 좌표 shoelace 식에서 상쇄가 발생합니다.
    seoul_polygon_ring = [
        [127.00085603724403, 37.563915713366605],
        [127.00106207593059, 37.564438459668125],
        [127.00116400912117, 37.563883205216165],
        [127.00146910057715, 37.56473003545158],
        [127.00116589986766, 37.5649013367235],
        [127.00103563269772, 37.5653838398091],
        [127.0008, 37.5647],
        [127.00085603724403, 37.563915713366605],
    ]
    seoul_polygon = boundary_feature({"type": "Polygon", "coordinates": [seoul_polygon_ring]})
    seoul_polygon_row = clean.transform_boundary_feature(seoul_polygon, 3)
    assert_decimal_centroid(seoul_polygon_row, [seoul_polygon_ring])

    seoul_multipolygon_ring = [
        [127.00385603724403, 37.563915713366605],
        [127.00406207593059, 37.564438459668125],
        [127.00416400912117, 37.563883205216165],
        [127.00446910057715, 37.56473003545158],
        [127.00416589986766, 37.5649013367235],
        [127.00403563269772, 37.5653838398091],
        [127.0038, 37.5647],
        [127.00385603724403, 37.563915713366605],
    ]
    seoul_multipolygon = boundary_feature({
        "type": "MultiPolygon",
        "coordinates": [[seoul_polygon_ring], [seoul_multipolygon_ring]],
    })
    seoul_multipolygon_row = clean.transform_boundary_feature(seoul_multipolygon, 4)
    assert_decimal_centroid(seoul_multipolygon_row, [seoul_polygon_ring, seoul_multipolygon_ring])

    invalid_type = boundary_feature({"type": "LineString", "coordinates": [[0, 0], [1, 1]]})
    expect_value_error(lambda: clean.transform_boundary_feature(invalid_type, 5))
    missing_property = boundary_feature({"type": "Polygon", "coordinates": polygon["geometry"]["coordinates"]})
    del missing_property["properties"]["emd_cd"]
    expect_value_error(lambda: clean.transform_boundary_feature(missing_property, 6))


def run_support_fixture_tests(clean) -> None:
    """판단 보조 산출물의 코드값·flag·peer 검사가 잘못된 값을 막는지 확인합니다."""
    frame = pd.DataFrame({"index_se_band": ["LOW", "MID"]})
    clean._require_enum(frame, "index_se_band", {"LOW", "MID", "HIGH"}, "fixture")
    expect_value_error(lambda: clean._require_enum(
        pd.DataFrame({"delta_state": ["DISTINGUISHABLE", "UNKNOWN"]}),
        "delta_state", {"DISTINGUISHABLE", "INDISTINGUISHABLE"}, "fixture",
    ))
    # 빈 칸은 nullable일 때만 통과한다.
    clean._require_enum(pd.DataFrame({"peak_5y_state": ["AT_PEAK", ""]}), "peak_5y_state",
                        {"AT_PEAK"}, "fixture", nullable=True)
    expect_value_error(lambda: clean._require_enum(
        pd.DataFrame({"peak_5y_state": ["AT_PEAK", ""]}), "peak_5y_state", {"AT_PEAK"}, "fixture",
    ))

    clean.validate_sample_flags(pd.Series(["FEW_SALES;HIGH_INDEX_ERROR", None]))
    expect_value_error(lambda: clean.validate_sample_flags(pd.Series(["FEW_SALES;MOMENTUM"])))

    known = {"11110_교북동", "11140_중림동"}
    clean.validate_peer_dongs(pd.Series(['[{"dong":"11140_중림동","reason":"가까워요"}]', None]), known)
    expect_value_error(lambda: clean.validate_peer_dongs(pd.Series(["[]"]), known))
    expect_value_error(lambda: clean.validate_peer_dongs(pd.Series(['[{"dong":"99999_없는동","reason":"x"}]']), known))
    expect_value_error(lambda: clean.validate_peer_dongs(pd.Series(['[{"dong":"11140_중림동"}]']), known))


def main() -> int:
    clean = load_module("50.load_db.py", "boomingup_clean_loader_test")
    trades = load_module("51.load_trades.py", "boomingup_trade_loader_test")
    run_fixture_tests(clean, trades)
    run_boundary_fixture_tests(clean)
    run_support_fixture_tests(clean)

    frames = clean.load_clean_sources()
    assert len(clean.GU_BY_SGG_CD) == 25
    assert all(frames["dong"]["dong"] == frames["dong"]["sgg_cd"] + "_" + frames["dong"]["umd_nm"])
    assert set(frames["dong_feature"]["dong"]).issubset(set(frames["dong"]["dong"]))
    assert set(frames["event_dong_path"]["dong"]).issubset(set(frames["dong"]["dong"]))
    assert set(frames["event_summary"]["event_id"]).issubset(set(frames["market_event"]["event_id"]))
    assert len(frames["dong_prediction"]) == 0
    assert len(frames["dong_boundary"]) == 467
    assert frames["dong_boundary"]["in_index"].sum() == 340
    assert set(frames["dong_support"]["dong"]).issubset(set(frames["dong"]["dong"]))
    # 기준 분기는 하나이고 μ는 서울 전체 값이라 모든 행에서 같다.
    assert frames["dong_support"]["as_of"].nunique() == 1
    assert frames["dong_support"]["mu_12m"].nunique() == 1
    assert set(frames["dong_boundary"].loc[frames["dong_boundary"]["in_index"], "dong"]).issubset(set(frames["dong"]["dong"]))

    print("정제 원천 점검")
    for table, frame in frames.items():
        print(f"  app.{table}: 원천/적재 예정 {len(frame):,}행")

    print("원장 원천 점검")
    for kind, path in trades.SOURCE_FILES.items():
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            trades.validate_trade_header(reader.fieldnames, kind)
            samples = []
            for row_no, row in enumerate(reader, start=1):
                samples.append(trades.transform_trade_row(row, kind, row_no))
                if row_no == 3:
                    break
        assert len(samples) == 3
        assert all(values[trades.TABLE_COLUMNS[kind].index("deal_ym")] is not None for values in samples)
        source_count = line_data_count(path)
        dry_run_count = min(source_count, 10_000)
        print(f"  {path.name}: 원천 {source_count:,}행, dry-run 적재 예정 {dry_run_count:,}행")

    print("DB 없이 파일 파싱·타입 변환·관계 불변식 점검을 통과했습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
