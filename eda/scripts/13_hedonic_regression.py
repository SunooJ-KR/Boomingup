"""11번 축(추가): 여러 요인을 동시에 통제하는 다변량 회귀(hedonic 회귀).

1~5번 축은 변수 하나씩만 보는 단순 비교였다(예: "층수만" 봤을 때 가격과의 관계).
이 축은 준공연차·층·면적·역거리·한강조망·학군거리·정비사업단계·구·분기를 **한 회귀식에
동시에 넣어서**, 서로 얽힌 변수들을 통제한 뒤 각 요인의 "조건부 연관성"이 얼마나 남는지 본다.
(codex 검증 후 "순수 효과/인과효과"라는 표현은 과하다고 판단해 "조건부 연관성"으로 낮춤)

설계:
  log(㎡당 단가) ~ age + age^2 + floor + log(면적) + station_dist_m + river_view_ratio
                   + elem/mid/high_school_m + C(정비사업단계) + C(자치구) + C(분기)
  - "자치구×분기 고정효과"가 아니라 **자치구 고정효과 + 분기 고정효과(각각 더해짐)**다.
    구마다 분기별 흐름이 다르게 허용하는 진짜 상호작용은 아니다(2026-09-16 codex 검증에서
    표현 오류로 지적됨) — 상호작용을 쓰려면 C(gu):C(quarter)가 따로 필요하다.
  - 정비사업 단계는 "해당없음"을 기준범주로 명시했다(patsy 기본값은 알파벳/유니코드 순으로
    "건축심의"를 기준으로 잡아서, 이전 버전은 출력 설명("해당없음 대비")과 실제 기준범주가
    달랐다 — codex 검증에서 발견됨).
  - age는 평균을 뺀 중심화값을 쓴다(age_c, age_c^2) — 원 age와 age^2를 그대로 쓰면 표준화를
    해도 VIF가 불필요하게 높게 나온다(다항식의 본질적 공선성). 계수·곡선 모양은 동일하다.
  - far(용적률)·parking_per_hh(세대당 주차)는 거래 기준 결측이 70%가 넘어 제외했다
    (표본이 18만 건 -> 3만 건으로 줄어들어서).
  - 표준오차는 단지(apt_seq) 단위로 군집화한다(같은 단지의 여러 거래는 독립이 아니므로).
  - 다중공선성은 VIF로 확인한다.

한계(codex 검증에서 지적, 아직 고치지 않음): 층·역거리·학교거리를 선형으로만 넣어 임계점·
포화 효과를 못 잡을 수 있음, 단지 규모(total_households)·일조·공원거리 등 원시 상관이
있던 변수가 빠짐, 정비사업 단계는 현재(2026년) 시점 값을 과거 거래에도 그대로 적용.
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
age_mean = df["age"].mean()
df["age_c"] = df["age"] - age_mean  # 중심화: VIF·해석 안정성을 위해(계수·곡선 모양은 동일)
df["age_c2"] = df["age_c"] ** 2
df["log_area"] = np.log(df["exclu_use_ar"].astype(float))
df["floor"] = df["floor"].astype(float)
df["quarter"] = df["deal_year"].astype(str) + "Q" + (((df["deal_month"] - 1) // 3) + 1).astype(str)
df["redevelop_stage"] = df["redevelop_stage"].fillna("해당없음")

num_cols = ["station_dist_m", "river_view_ratio", "elem_school_m", "mid_school_m", "high_school_m"]
for c in num_cols:
    df[c] = df[c].astype(float)
df = df.dropna(subset=["log_price", "age_c", "floor", "log_area", "gu", "quarter", *num_cols])
print(f"회귀 대상(결측 제거 후): {len(df)}건, 단지 {df['apt_seq'].nunique()}개")

formula = (
    "log_price ~ age_c + age_c2 + floor + log_area + station_dist_m + river_view_ratio "
    "+ elem_school_m + mid_school_m + high_school_m "
    '+ C(redevelop_stage, Treatment(reference="해당없음")) + C(gu) + C(quarter)'
)
model = smf.ols(formula, data=df).fit(cov_type="cluster", cov_kwds={"groups": df["apt_seq"]})

print("\n=== 회귀 요약 (핵심 계수만) ===")
key_vars = ["age_c", "age_c2", "floor", "log_area", "station_dist_m", "river_view_ratio",
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
X_num = df[["age_c", "age_c2", "floor", "log_area", *num_cols]].copy()
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
    if name.startswith("C(redevelop_stage") and "[T." in name:
        stage = name.split("[T.")[1].rstrip("]")
        stage_rows.append({"stage": stage, "coef": coef, "p_value": model.pvalues[name]})
stage_df = pd.DataFrame(stage_rows).sort_values("coef", ascending=False)
print("\n=== 정비사업 단계 효과 (해당없음 대비, 다른 요인 통제 후) ===")
print(stage_df.round(4).to_string(index=False))
stage_df.to_csv("../output/13_hedonic_regression_redevelop.csv", index=False)

# --- 표준편차 저장 + 표준화 효과를 정확한 %로 환산 ---
# log 종속변수라서 계수는 "log 변화량"이다. %로 바꿀 때 coef*std*100(선형 근사)이 아니라
# 100*(exp(coef*std)-1)을 써야 정확하다(2026-09-16 codex 검증에서 지적 — 이전엔 근사값이었음).
std_cols = ["age_c", "age_c2", "floor", "log_area", *num_cols]
stds = df[std_cols].std()
stds.to_csv("../output/13_hedonic_regression_stds.csv")

pct_rows = []
for v in key_vars:
    if v in ("age_c", "age_c2"):
        continue  # 이차항은 1SD 단독 환산이 의미 없음 — 아래 연령곡선으로 대체
    coef = model.params[v]
    sd = stds[v]
    pct = 100 * (np.exp(coef * sd) - 1)
    ci_lo, ci_hi = model.conf_int().loc[v]
    pct_lo = 100 * (np.exp(ci_lo * sd) - 1)
    pct_hi = 100 * (np.exp(ci_hi * sd) - 1)
    pct_rows.append({"variable": v, "pct_change_per_1sd": pct,
                      "ci_low_pct": min(pct_lo, pct_hi), "ci_high_pct": max(pct_lo, pct_hi),
                      "p_value": model.pvalues[v]})
pct_df = pd.DataFrame(pct_rows).sort_values("pct_change_per_1sd", key=abs, ascending=False)
print("\n=== 1표준편차 변화당 가격 효과(%), exp(coef*sd)-1 기준 ===")
print(pct_df.round(3).to_string(index=False))
pct_df.to_csv("../output/13_hedonic_regression_pct.csv", index=False)

# --- 준공연차 효과: 선형항만 보면 왜곡됨(이차항 때문에 U자형) ---
# 다른 변수는 표본 평균/기준범주로 고정하고, age만 0~60년으로 움직여 예측 log_price를 구한 뒤
# 임의 기준연차(중앙값) 대비 %변화로 변환한다.
age_grid = np.arange(0, 61, 1.0)
age_c_grid = age_grid - age_mean
pred_log = model.params["Intercept"] + model.params["age_c"] * age_c_grid + model.params["age_c2"] * age_c_grid ** 2
ref_age = 20.0  # 기준연차: 표본에서 흔한 연차대의 대표값
ref_idx = np.argmin(np.abs(age_grid - ref_age))
pct_vs_ref = 100 * (np.exp(pred_log - pred_log[ref_idx]) - 1)
age_curve = pd.DataFrame({"age": age_grid, "pred_log_price_relative": pred_log - pred_log[ref_idx],
                           "pct_vs_age20": pct_vs_ref})
turning_point = age_mean - model.params["age_c"] / (2 * model.params["age_c2"])
print(f"\n준공연차 효과 변곡점(연차): {turning_point:.1f}세 (이 연차까지는 감가, 이후는 재건축 기대 등으로 반등)")
age_curve.to_csv("../output/13_hedonic_regression_age_curve.csv", index=False)

print("\nCSV 저장 완료: eda/output/13_hedonic_regression_{coefs,stats,vif,redevelop,stds,pct,age_curve}.csv")
