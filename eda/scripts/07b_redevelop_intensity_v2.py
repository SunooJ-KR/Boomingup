"""7번 축 보강: 정비사업 강도 지표를 '전체 세대수' 기준으로 재계산.

기존 07_cross_axis.py의 redevelop_intensity = rz_active_households / stock_hh는
분자(rz_active_households, 정비구역 계획상 전체 세대수 - 아파트+빌라 등 포함)와
분모(stock_hh, 건축물대장 기준 "아파트만"의 준공 누적 세대수)의 대상 범위가 달라서
19개 동에서 비율이 100%를 넘는 구조적 문제가 있었다(2026-09-16 확인, 보광동 예:
rz=5222, stock_hh=552=아파트만).

이 스크립트는 분모를 10번 축에서 이미 받아온 행정안전부 주민등록 세대수(hh_cnt,
아파트+빌라+단독주택 등 전체 주택유형 포함)로 바꿔서, 분자·분모의 대상 범위를 맞춘
재계산 버전(intensity_v2)을 만들고 변동성과의 상관을 다시 확인한다.

한계: hh_cnt는 2025Q2·2026Q2 두 시점 스냅샷뿐이라(행안부 API가 2022-10 이전은
집계 자체가 없음) 2011~2026년 전체 기간에 동일한 최근 세대수를 고정값으로
적용한다 - 세대수가 그동안 바뀌었을 수 있다는 시점 불일치는 남는다. 다만 이건
"범위가 다른 두 숫자를 나눈" 구조적 오류보다는 훨씬 가벼운 한계다.
"""
import numpy as np
import pandas as pd
from scipy import stats

pd.set_option("display.width", 140)

feat = pd.read_csv("../output/07_redevelop_intensity_vs_volatility.csv")
# feat에는 기존 intensity(아파트 기준), volatility만 있고 rz_active_households 자체는
# 없으므로 원본 dong_feature에서 다시 받아온다.
import sys
sys.path.insert(0, ".")
from _db import query_df

rz = query_df("""
    select f.dong, max(f.rz_active_households) as rz_active_households
    from app.dong_feature f
    join app.dataset_snapshot ds on ds.snapshot_id = f.snapshot_id
    where ds.is_active
    group by f.dong;
""")

pop = pd.read_csv("../output/11_population_dong_monthly.csv")
hh = pop[pop["stats_ym"] == 202606].groupby("dong")["hh_cnt"].sum().rename("hh_cnt_total")

df = feat.merge(rz, on="dong", how="left").merge(hh, on="dong", how="left")
print(f"전체 동: {len(df)}, 세대수 데이터 있는 동: {df['hh_cnt_total'].notna().sum()}")

df["intensity_v2"] = df["rz_active_households"] / df["hh_cnt_total"]
df["intensity_v2_over_1"] = df["intensity_v2"] > 1

print(f"\n기존(아파트 기준) 강도>1: {df['intensity_over_1'].sum()}개")
print(f"신규(전체 세대수 기준) 강도>1: {df['intensity_v2_over_1'].sum()}개")
print(f"\n신규 기준으로도 여전히 1을 넘는 동(상위 10개):")
print(df.sort_values("intensity_v2", ascending=False)[["dong", "rz_active_households", "hh_cnt_total", "intensity_v2"]].head(10).to_string(index=False))

corr_v2_all = df["intensity_v2"].corr(df["volatility"])
_, p_v2_all = stats.pearsonr(df["intensity_v2"].dropna(), df.dropna(subset=["intensity_v2"])["volatility"])

normal_v2 = df[~df["intensity_v2_over_1"]].dropna(subset=["intensity_v2"])
corr_v2_normal = normal_v2["intensity_v2"].corr(normal_v2["volatility"])
_, p_v2_normal = stats.pearsonr(normal_v2["intensity_v2"], normal_v2["volatility"])

print(f"\n=== 재계산(intensity_v2) 상관계수 ===")
print(f"전체(n={df['intensity_v2'].notna().sum()}): r={corr_v2_all:.4f}, p={p_v2_all:.4f}")
print(f"정상범위만(n={len(normal_v2)}): r={corr_v2_normal:.4f}, p={p_v2_normal:.4f}")

print(f"\n=== 참고: 기존(v1, 아파트 기준) 상관계수 ===")
corr_v1_normal = df.loc[~df["intensity_over_1"], "redevelop_intensity"].corr(df.loc[~df["intensity_over_1"], "volatility"])
print(f"정상범위만(v1): r={corr_v1_normal:.4f}")

df.to_csv("../output/07b_redevelop_intensity_v2.csv", index=False)
print("\nCSV 저장 완료: eda/output/07b_redevelop_intensity_v2.csv")
