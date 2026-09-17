# ============================================================================
# 62.build_dong_features.py
# ============================================================================
# Author:      yjkim
# Purpose:     기점 분기별 동 feature를 만든다. 첫 판은 거래 단지 수와 집중도다
# Description: 계획 docs/model-develope-plan.md §3-③, 진행 docs/model-build-process.md P0-5.
#              동의 지수를 믿을 수 있는지는 거래 "건수"만으로 판단할 수 없다.
#              20건이 한 단지에서만 나왔다면 그 동의 지수는 단지 하나의 지수다.
#              그래서 gate와 화면 신뢰도 블록이 쓸 두 값을 만든다.
#                - n_complexes_4q            직전 4분기에 거래가 있던 단지 수
#                - dominant_complex_share_4q 그중 가장 많이 거래된 단지의 몫
#
#              기점 분기 말까지 공개된 정보로만 만든다(as-of 원칙). 창은 기점 분기를
#              포함한 직전 4분기다.
# ============================================================================

# ============================================================================
# 0. 환경 설정
# ============================================================================

from pathlib import Path

import numpy as np
import pandas as pd

from _dong_index import load_sales_any

work_dir = Path(__file__).resolve().parents[2]
output_dir = work_dir / "output"

LAST_COMPLETE_QUARTER = pd.Period("2026Q2", freq="Q")
WINDOW_Q = 4


# ============================================================================
# 1. 매매 적재
# ============================================================================

sales, source = load_sales_any(work_dir)
sales = sales[sales["quarter"] <= LAST_COMPLETE_QUARTER].reset_index(drop=True)
print("===== 1. 매매 적재 완료 =====")
print(f"  원천: {source}")
print(f"  {len(sales):,}건 / 동 {sales['dong'].nunique()}개 / {sales['quarter'].min()} ~ {sales['quarter'].max()}")


# ============================================================================
# 2. 기점별 거래 단지 수와 집중도
# ============================================================================

# (동, 단지, 분기) 건수로 한 번 줄여 두면 기점마다 원장 전체를 다시 훑지 않는다
by_complex = (sales.groupby(["dong", "aptSeq", "quarter"], observed=True)
              .size().rename("n").reset_index())

dongs = sales[["dong", "sggCd", "umdNm"]].drop_duplicates("dong")
quarters = pd.period_range(sales["quarter"].min(), LAST_COMPLETE_QUARTER, freq="Q")

rows = []
for as_of in quarters:
    window = by_complex[(by_complex["quarter"] > as_of - WINDOW_Q) & (by_complex["quarter"] <= as_of)]
    if window.empty:
        continue
    per_complex = window.groupby(["dong", "aptSeq"], observed=True)["n"].sum()
    per_dong = per_complex.groupby("dong")
    frame = pd.DataFrame({
        "n_complexes_4q": per_dong.size(),
        "dominant_n": per_dong.max(),
        "sale_n_all_4q": per_dong.sum(),
    }).reset_index()
    frame["as_of_quarter"] = as_of
    rows.append(frame)

counted = pd.concat(rows, ignore_index=True)

# 거래가 없던 동×기점도 행을 남긴다. 화면과 gate가 "거래 0건"을 값으로 읽어야 한다
grid = dongs.merge(pd.DataFrame({"as_of_quarter": quarters}), how="cross")
features = grid.merge(counted, on=["dong", "as_of_quarter"], how="left")
features["n_complexes_4q"] = features["n_complexes_4q"].fillna(0).astype(int)
features["sale_n_all_4q"] = features["sale_n_all_4q"].fillna(0).astype(int)
features["dominant_complex_share_4q"] = np.where(
    features["sale_n_all_4q"] > 0,
    features["dominant_n"] / features["sale_n_all_4q"],
    np.nan,      # 거래가 없으면 집중도는 0이 아니라 "없음"이다
)
features = features.drop(columns="dominant_n").sort_values(["dong", "as_of_quarter"]).reset_index(drop=True)

print("\n===== 2. feature 생성 완료 =====")
print(f"  {len(features):,}행 = 동 {features['dong'].nunique()}개 × 기점 {features['as_of_quarter'].nunique()}개")
print(f"  거래 0건 기점 {int((features['sale_n_all_4q'] == 0).sum()):,}행 (집중도 결측)")


# ============================================================================
# 3. 완료 조건 점검 — 원장에서 직접 센 값과 맞는가
# ============================================================================

sample = features[features["sale_n_all_4q"] > 0].sample(3, random_state=20260917)
print("\n===== 3. 원장 직접 집계와 대조 =====")
for _, row in sample.iterrows():
    as_of = row["as_of_quarter"]
    raw = sales[(sales["dong"] == row["dong"])
                & (sales["quarter"] > as_of - WINDOW_Q) & (sales["quarter"] <= as_of)]
    expected_n = raw["aptSeq"].nunique()
    expected_share = raw["aptSeq"].value_counts().iloc[0] / len(raw)
    assert expected_n == row["n_complexes_4q"], f"{row['dong']} {as_of}: 단지 수 불일치"
    assert abs(expected_share - row["dominant_complex_share_4q"]) < 1e-12, f"{row['dong']} {as_of}: 집중도 불일치"
    print(f"  {row['dong']} {as_of}: 단지 {expected_n}개, 최대 단지 몫 {expected_share:.3f} — 일치")


# ============================================================================
# 4. 저장과 요약
# ============================================================================

feature_path = output_dir / "62.1.dong_complex_concentration.txt"
features.to_csv(feature_path, sep="\t", index=False, lineterminator="\n")

served = features[features["sale_n_all_4q"] >= 20]     # 현행 gate 기준(결정 7)
print("\n===== 4. 현행 gate(4분기 20건) 통과 동의 집중도 =====")
print(f"  통과 {len(served):,}행 중 한 단지가 절반 넘게 차지한 경우 "
      f"{int((served['dominant_complex_share_4q'] > 0.5).sum()):,}행 "
      f"({(served['dominant_complex_share_4q'] > 0.5).mean():.1%})")
print(f"  거래 단지 수 중앙값 {served['n_complexes_4q'].median():.0f}개, "
      f"하위 10% {served['n_complexes_4q'].quantile(0.1):.0f}개")
print(f"\nfeature: {feature_path}")
