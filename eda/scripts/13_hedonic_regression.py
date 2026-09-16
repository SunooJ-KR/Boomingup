"""11번 축(추가): 여러 요인을 동시에 통제하는 다변량 회귀(hedonic 회귀).

1~5번 축은 변수 하나씩만 보는 단순 비교였다(예: "층수만" 봤을 때 가격과의 관계).
이 축은 준공연차·층·면적·역거리·한강조망·학군거리·정비사업단계·구·분기를 **한 회귀식에
동시에 넣어서**, 서로 얽힌 변수들을 통제한 뒤 각 요인의 "순수한" 연관성이 얼마나 남는지 본다.

설계:
  log(㎡당 단가) ~ age + age^2 + floor + log(면적) + station_dist_m + river_view_ratio
                   + elem/mid/high_school_m + C(정비사업단계) + C(자치구) + C(분기)
  - far(용적률)·parking_per_hh(세대당 주차)는 거래 기준 결측이 70%가 넘어 제외했다
    (표본이 18만 건 -> 3만 건으로 줄어들어서).
  - 표준오차는 단지(apt_seq) 단위로 군집화한다(같은 단지의 여러 거래는 독립이 아니므로).
  - 다중공선성은 VIF로 확인한다.
"""
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from statsmodels.stats.outliers_influence import variance_inflation_factor

from _db import query_df

pd.set_option("display.width", 140)

sale = query_df("""
    select apt_seq, deal_year, deal_month, exclu_use_ar, floor, deal_amount_manwon, gu
    from app.trade_sale
    where is_cancelled = false
      and deal_amount_manwon > 0
      and exclu_use_ar > 0
      and deal_year >= 2024
      and apt_seq is not null
      and floor > 0 and floor < 70;
""")

complex_df = query_df("""
    select c.apt_seq, c.built_year, c.far, c.bcr, c.parking_per_hh, c.redevelop_stage,
           cm.station_dist_m, cm.river_view_ratio, cm.elem_school_m, cm.mid_school_m, cm.high_school_m
    from app.complex c
    join app.complex_metrics cm on cm.apt_seq = c.apt_seq and cm.snapshot_id = c.snapshot_id
    join app.dataset_snapshot ds on ds.snapshot_id = c.snapshot_id
    where ds.is_active;
""")
# far(용적률)·parking_per_hh(세대당 주차)는 거래 기준으로 각각 77%·72%가 결측이다(2026-09-16
# 확인 — 단지 수 기준으로는 36%만 결측인데, 거래가 많은 대단지 쪽에 결측이 쏠려있어 거래
# 기준 결측률이 훨씬 높다). 회귀에 넣으면 표본이 18만 건에서 3만 건으로 줄어들어 제외한다.

df = sale.merge(complex_df, on="apt_seq", how="inner")
print(f"매칭된 거래 {len(df)}건 / 전체 실거래 {len(sale)}건 (매칭률 {len(df) / len(sale) * 100:.1f}%)")

df["price_per_m2"] = df["deal_amount_manwon"].astype(float) / df["exclu_use_ar"].astype(float)
df["log_price"] = np.log(df["price_per_m2"])
df["age"] = df["deal_year"] - df["built_year"].astype(float)
df = df[(df["age"] >= 0) & (df["age"] <= 60)]
df["age2"] = df["age"] ** 2
df["log_area"] = np.log(df["exclu_use_ar"].astype(float))
df["floor"] = df["floor"].astype(float)
df["quarter"] = df["deal_year"].astype(str) + "Q" + (((df["deal_month"] - 1) // 3) + 1).astype(str)
df["redevelop_stage"] = df["redevelop_stage"].fillna("해당없음")

num_cols = ["station_dist_m", "river_view_ratio", "elem_school_m", "mid_school_m", "high_school_m"]
for c in num_cols:
    df[c] = df[c].astype(float)
df = df.dropna(subset=["log_price", "age", "floor", "log_area", "gu", "quarter", *num_cols])
print(f"회귀 대상(결측 제거 후): {len(df)}건, 단지 {df['apt_seq'].nunique()}개")

formula = (
    "log_price ~ age + age2 + floor + log_area + station_dist_m + river_view_ratio "
    "+ elem_school_m + mid_school_m + high_school_m "
    "+ C(redevelop_stage) + C(gu) + C(quarter)"
)
model = smf.ols(formula, data=df).fit(cov_type="cluster", cov_kwds={"groups": df["apt_seq"]})

print("\n=== 회귀 요약 (핵심 계수만) ===")
key_vars = ["age", "age2", "floor", "log_area", "station_dist_m", "river_view_ratio",
            "elem_school_m", "mid_school_m", "high_school_m"]
summary_rows = []
for v in key_vars:
    coef = model.params[v]
    se = model.bse[v]
    p = model.pvalues[v]
    ci_lo, ci_hi = model.conf_int().loc[v]
    summary_rows.append({"variable": v, "coef": coef, "se": se, "p_value": p,
                          "ci_low": ci_lo, "ci_high": ci_hi})
    sig = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else ""
    print(f"  {v:20s} coef={coef:+.5f}  p={p:.4f} {sig}")

print(f"\n표본 수: {int(model.nobs):,}  |  R^2: {model.rsquared:.3f}  |  Adj R^2: {model.rsquared_adj:.3f}")
print(f"표준오차: apt_seq({df['apt_seq'].nunique()}개 단지) 단위로 군집화")

summary_df = pd.DataFrame(summary_rows)
summary_df.to_csv("../output/13_hedonic_regression_coefs.csv", index=False)

model_stats = pd.DataFrame([{
    "n_obs": int(model.nobs), "n_apt": df["apt_seq"].nunique(),
    "r_squared": model.rsquared, "adj_r_squared": model.rsquared_adj,
}])
model_stats.to_csv("../output/13_hedonic_regression_stats.csv", index=False)

# --- 다중공선성(VIF) 확인: 숫자형 설명변수만 ---
X_num = df[["age", "age2", "floor", "log_area", *num_cols]].copy()
X_num = (X_num - X_num.mean()) / X_num.std()  # 표준화해서 VIF 안정성 확보
X_num["const"] = 1.0
vif_rows = []
for i, col in enumerate(X_num.columns):
    if col == "const":
        continue
    vif = variance_inflation_factor(X_num.values, i)
    vif_rows.append({"variable": col, "vif": vif})
vif_df = pd.DataFrame(vif_rows).sort_values("vif", ascending=False)
print("\n=== 다중공선성(VIF) — 10 넘으면 주의, 5 넘으면 참고 ===")
print(vif_df.round(2).to_string(index=False))
vif_df.to_csv("../output/13_hedonic_regression_vif.csv", index=False)

# --- 정비사업 단계 계수(구역 유형 효과) ---
stage_rows = []
for name, coef in model.params.items():
    if name.startswith("C(redevelop_stage)"):
        stage = name.split("[T.")[1].rstrip("]")
        stage_rows.append({"stage": stage, "coef": coef, "p_value": model.pvalues[name]})
stage_df = pd.DataFrame(stage_rows).sort_values("coef", ascending=False)
print("\n=== 정비사업 단계 효과 (해당없음 대비, 다른 요인 통제 후) ===")
print(stage_df.round(4).to_string(index=False))
stage_df.to_csv("../output/13_hedonic_regression_redevelop.csv", index=False)

# --- 표준편차 저장 (그림에서 "1표준편차 변화 시 효과"로 환산할 때 재사용) ---
std_cols = ["age", "age2", "floor", "log_area", *num_cols]
df[std_cols].std().to_csv("../output/13_hedonic_regression_stds.csv")

print("\nCSV 저장 완료: eda/output/13_hedonic_regression_{coefs,stats,vif,redevelop,stds}.csv")
