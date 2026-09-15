# ============================================================================
# 42.build_dong_features.py
# ============================================================================
# Author:      yjkim
# Purpose:     보유 데이터로 법정동×기점(as_of_quarter) feature 테이블을 만든다
# Description: 사전 등록 결정 13. 모든 값은 기점 t 분기 말까지의 정보로만 계산한다.
#              - 거래: 직전 4분기(t 포함) 매매 건수·취소 비율·연식, 전세가율·전세 비중
#              - 정비사업: 서울시 추진현황 구역을 지번의 법정동으로 집계한 단계별 누적 구역 수
#                ※ 2026-06 기준 파일 하나라 목록에서 빠진(해제·완료) 구역은 없다 → 생존 편향 한계
#              - 입주: 건축물대장 사용승인일 기준 직전 4·8분기 준공 세대수와 누적 재고 대비 비율
#              - 입지·용적률 feature는 결정 14 선별에서 제외돼 만들지 않는다
#              기점 목록은 41.1.vintage_momentum.txt의 (dong, as_of_quarter)를 그대로 쓴다.
# ============================================================================

# ============================================================================
# 0. 환경 설정
# ============================================================================

import re
from pathlib import Path

import numpy as np
import pandas as pd

from _dong_index import load_sales

work_dir = Path(__file__).resolve().parents[2]   # 저장소 루트
output_dir = work_dir / "output"
REDEVELOP_PATH = output_dir / "raw" / "redevelop" / "redevelop_2606.xlsx"

GU_CODE = {
    "종로구": "11110", "중구": "11140", "용산구": "11170", "성동구": "11200",
    "광진구": "11215", "동대문구": "11230", "중랑구": "11260", "성북구": "11290",
    "강북구": "11305", "도봉구": "11320", "노원구": "11350", "은평구": "11380",
    "서대문구": "11410", "마포구": "11440", "양천구": "11470", "강서구": "11500",
    "구로구": "11530", "금천구": "11545", "영등포구": "11560", "동작구": "11590",
    "관악구": "11620", "서초구": "11650", "강남구": "11680", "송파구": "11710",
    "강동구": "11740",
}
# 정비사업 원본 열 위치 (병합 헤더 네 행 아래, 2026-09-15 헤더 확인)
ZONE_STAGE_COLUMNS = {
    "designated": 11, "committee": 13, "association": 14,
    "implementation": 16, "management": 18, "construction": 22,
}
ZONE_HOUSEHOLD_COLUMN = 10


def to_quarter(values, fmt):
    return pd.to_datetime(values, format=fmt, errors="coerce").dt.to_period("Q")


def trailing_windows(frame, width):
    """각 행을 자신이 포함되는 기점 t = quarter .. quarter+width-1 로 복제한다."""
    parts = []
    for shift in range(width):
        part = frame.copy()
        part["as_of_quarter"] = part["quarter"] + shift
        parts.append(part)
    return pd.concat(parts, ignore_index=True)


def parse_zone_umd(value, gu):
    """정비사업 대표 지번에서 법정동명만 꺼낸다.

    '번지·일대·일원' 범위 표기는 떼고, 동명 안의 숫자(신문로1가)는 동명으로 남긴다.
    쉼표 등으로 지번을 여러 개 적은 값은 None이다.
    """
    if pd.isna(value):
        return None
    address = re.sub(r"\s+", "", str(value).strip())
    gu = re.sub(r"\s+", "", str(gu).strip())
    if address.startswith(gu):
        address = address[len(gu):]
    address = re.sub(r"(?:번지)?(?:일대|일원)?$", "", address)
    matched = re.fullmatch(r"(?P<umd>.*[가-힣])(?P<bon>\d+)(?:-(?P<bub>\d+))?", address)
    return matched.group("umd") if matched else None


keys = pd.read_csv(output_dir / "41.1.vintage_momentum.txt", sep="\t", dtype=str,
                   usecols=["dong", "sggCd", "umdNm", "as_of_quarter"])
keys["as_of_quarter"] = pd.PeriodIndex(keys["as_of_quarter"], freq="Q")
print(f"===== 0. 기점 키 {len(keys):,}행 (동 {keys['dong'].nunique()}개) =====")


# ============================================================================
# 1. 매매 feature
# ============================================================================

raw_sale = pd.read_csv(output_dir / "11.1.trades_sale.txt", sep="\t", dtype=str,
                       usecols=["sggCd", "umdNm", "buildYear", "deal_ym", "is_cancelled"])
raw_sale = raw_sale.dropna(subset=["sggCd", "umdNm", "deal_ym"]).copy()
raw_sale["dong"] = raw_sale["sggCd"] + "_" + raw_sale["umdNm"]
raw_sale["quarter"] = to_quarter(raw_sale["deal_ym"], "%Y%m")
raw_sale["cancelled"] = raw_sale["is_cancelled"].eq("True")
age = raw_sale["quarter"].dt.year - pd.to_numeric(raw_sale["buildYear"], errors="coerce")
raw_sale["age"] = age
raw_sale["old30"] = age.ge(30).where(age.notna())

sale_window = trailing_windows(raw_sale[["dong", "quarter", "cancelled", "age", "old30"]], width=4)
sale_features = (sale_window
    .groupby(["dong", "as_of_quarter"])
    .agg(sale_n_all_4q=("cancelled", "size"), cancel_share_4q=("cancelled", "mean"),
         median_age_4q=("age", "median"), old30_share_4q=("old30", "mean"))
    .reset_index())

valid_sale = load_sales(output_dir / "11.1.trades_sale.txt")
valid_sale["ppm2"] = np.exp(valid_sale["log_ppm2"])
sale_price = (trailing_windows(valid_sale[["dong", "quarter", "ppm2"]], width=4)
    .groupby(["dong", "as_of_quarter"])["ppm2"].median()
    .rename("sale_ppm2_med_4q").reset_index())
print("===== 1. 매매 feature 완료 =====")


# ============================================================================
# 2. 전월세 feature
# ============================================================================

rent = pd.read_csv(output_dir / "11.2.trades_rent.txt", sep="\t", dtype=str,
                   usecols=["sggCd", "umdNm", "deal_ym", "excluUseAr", "deposit_manwon", "is_jeonse"])
rent = rent.dropna(subset=["sggCd", "umdNm", "deal_ym"]).copy()
rent["dong"] = (rent["sggCd"] + "_" + rent["umdNm"]).astype("category")
rent["quarter"] = to_quarter(rent["deal_ym"], "%Y%m")
rent["jeonse"] = rent["is_jeonse"].eq("True")
rent_area = pd.to_numeric(rent["excluUseAr"], errors="coerce")
rent["deposit_ppm2"] = pd.to_numeric(rent["deposit_manwon"], errors="coerce") / rent_area.where(rent_area.gt(0))

rent_window = trailing_windows(rent[["dong", "quarter", "jeonse", "deposit_ppm2"]], width=4)
rent_features = (rent_window
    .groupby(["dong", "as_of_quarter"], observed=True)
    .agg(rent_n_4q=("jeonse", "size"), jeonse_share_4q=("jeonse", "mean"))
    .reset_index())
jeonse_price = (rent_window[rent_window["jeonse"] & rent_window["deposit_ppm2"].gt(0)]
    .groupby(["dong", "as_of_quarter"], observed=True)["deposit_ppm2"].median()
    .rename("jeonse_ppm2_med_4q").reset_index())
for frame in (rent_features, jeonse_price):
    frame["dong"] = frame["dong"].astype(str)
del rent_window
print("===== 2. 전월세 feature 완료 =====")


# ============================================================================
# 3. 정비사업 구역 feature
# ============================================================================

zone_raw = pd.read_excel(REDEVELOP_PATH, header=None, skiprows=4)
populated = zone_raw[[0, 1, 2, 3]].notna().all(axis=1)
zones = zone_raw[populated & zone_raw[2].astype(str).str.strip().isin(GU_CODE)].copy()
zones["gu"] = zones[2].astype(str).str.strip()
zones["umd"] = [parse_zone_umd(value, gu) for value, gu in zip(zones[4], zones["gu"])]
parse_failed = int(zones["umd"].isna().sum())
zones = zones[zones["umd"].notna()].copy()
zones["dong"] = zones["gu"].map(GU_CODE) + "_" + zones["umd"]
zones["households"] = pd.to_numeric(zones[ZONE_HOUSEHOLD_COLUMN], errors="coerce").fillna(0)
for stage, column in ZONE_STAGE_COLUMNS.items():
    zones[stage] = pd.to_datetime(zones[column], errors="coerce").dt.to_period("Q")

zone_panel = keys[["dong", "as_of_quarter"]].merge(
    zones[["dong", "households", *ZONE_STAGE_COLUMNS]], on="dong", how="inner")
t = zone_panel["as_of_quarter"]
zone_panel["events_4q"] = 0
for stage in ZONE_STAGE_COLUMNS:
    reached = zone_panel[stage].notna() & (zone_panel[stage] <= t)
    zone_panel[f"rz_{stage}_n"] = reached
    zone_panel["events_4q"] += (reached & (zone_panel[stage] > t - 4)).astype(int)
active = zone_panel["rz_designated_n"] & ~zone_panel["rz_construction_n"]
zone_panel["rz_active_households"] = zone_panel["households"].where(active, 0)
zone_features = (zone_panel
    .groupby(["dong", "as_of_quarter"])
    [[f"rz_{stage}_n" for stage in ZONE_STAGE_COLUMNS] + ["rz_active_households", "events_4q"]]
    .sum()
    .rename(columns={"events_4q": "rz_events_4q"})
    .reset_index())
print(f"===== 3. 정비사업 feature 완료: 구역 {len(zones)}개 (지번 파싱 실패 {parse_failed}개 제외) =====")


# ============================================================================
# 4. 입주(준공) feature
# ============================================================================

ledger = pd.read_csv(output_dir / "19.1.building_ledger.txt", sep="\t", dtype=str,
                     usecols=["join_key", "hhld_cnt", "use_apr_day"])
key_parts = ledger["join_key"].str.split(" ", n=2, expand=True)
ledger["dong"] = key_parts[0].map(GU_CODE) + "_" + key_parts[1]
ledger["quarter"] = to_quarter(ledger["use_apr_day"], "%Y%m%d")
ledger["households"] = pd.to_numeric(ledger["hhld_cnt"], errors="coerce")
ledger = ledger.dropna(subset=["dong", "quarter", "households"])
completed = ledger.groupby(["dong", "quarter"])["households"].sum().reset_index()

supply_features = keys[["dong", "as_of_quarter"]].copy()
for width in (4, 8):
    window = (trailing_windows(completed, width)
        .groupby(["dong", "as_of_quarter"])["households"].sum()
        .rename(f"completed_hh_{width}q").reset_index())
    supply_features = supply_features.merge(window, on=["dong", "as_of_quarter"], how="left")

stock = completed.sort_values(["dong", "quarter"]).copy()
stock["stock_hh"] = stock.groupby("dong")["households"].cumsum()
stock["quarter_ord"] = stock["quarter"].apply(lambda period: period.ordinal)
supply_features["quarter_ord"] = supply_features["as_of_quarter"].apply(lambda period: period.ordinal)
supply_features = pd.merge_asof(
    supply_features.sort_values("quarter_ord"), stock[["dong", "quarter_ord", "stock_hh"]].sort_values("quarter_ord"),
    on="quarter_ord", by="dong", direction="backward").drop(columns="quarter_ord")
print("===== 4. 입주 feature 완료 =====")


# ============================================================================
# 5. 병합 및 저장
# ============================================================================

features = keys.copy()
for frame in (sale_features, sale_price, rent_features, jeonse_price, zone_features, supply_features):
    features = features.merge(frame, on=["dong", "as_of_quarter"], how="left")

count_columns = ["sale_n_all_4q", "rent_n_4q", "completed_hh_4q", "completed_hh_8q", "rz_active_households",
                 "rz_events_4q", *[f"rz_{stage}_n" for stage in ZONE_STAGE_COLUMNS]]
features[count_columns] = features[count_columns].fillna(0)
features["jeonse_ratio_4q"] = features["jeonse_ppm2_med_4q"] / features["sale_ppm2_med_4q"]
features["completed_share_8q"] = features["completed_hh_8q"] / features["stock_hh"]

previous = features[["dong", "as_of_quarter", "sale_n_all_4q", "rent_n_4q"]].copy()
previous["as_of_quarter"] = previous["as_of_quarter"] + 4
features = features.merge(previous, on=["dong", "as_of_quarter"], how="left", suffixes=("", "_prev4q"))
features["sale_n_log_change_4q"] = np.log1p(features["sale_n_all_4q"]) - np.log1p(features["sale_n_all_4q_prev4q"])
features["rent_n_log_change_4q"] = np.log1p(features["rent_n_4q"]) - np.log1p(features["rent_n_4q_prev4q"])
features = features.drop(columns=["sale_n_all_4q_prev4q", "rent_n_4q_prev4q"])

features_path = output_dir / "42.1.dong_features.txt"
features.to_csv(features_path, sep="\t", index=False, lineterminator="\n")

print("\n===== 5. 컬럼별 채움률 =====")
fill = features.drop(columns=["dong", "sggCd", "umdNm", "as_of_quarter"]).notna().mean().round(3)
print(fill.to_string())
print(f"\nfeature: {features_path} ({len(features):,}행, {features.shape[1]}열)")
