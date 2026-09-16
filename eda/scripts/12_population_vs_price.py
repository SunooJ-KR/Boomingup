"""10번 축(추가): 인구·세대수 변화가 2번 축의 "구 평균과 동별 흐름이 다르다" 미스터리를 설명하는지 확인.

행정안전부 법정동 인구통계(2025Q2, 2026Q2)를 02번 축의 동별 가격 상승률(2025Q2->2026Q2)과 합쳐서
인구 증감과 가격 증감의 관계를 본다.
"""
import pandas as pd
from scipy import stats

pd.set_option("display.width", 140)

pop = pd.read_csv("../output/11_population_dong_monthly.csv", dtype={"stats_ym": str})
pop["quarter"] = pop["stats_ym"].apply(lambda ym: f"{ym[:4]}Q{(int(ym[4:6]) - 1) // 3 + 1}")
q_avg = pop.groupby(["dong", "gu_name", "umd_nm", "quarter"], as_index=False).agg(
    hh_cnt=("hh_cnt", "mean"), tot_nmpr_cnt=("tot_nmpr_cnt", "mean"),
)

wide = q_avg.pivot(index=["dong", "gu_name", "umd_nm"], columns="quarter", values=["hh_cnt", "tot_nmpr_cnt"])
wide.columns = ["_".join(c) for c in wide.columns]
wide = wide.dropna(subset=["tot_nmpr_cnt_2025Q2", "tot_nmpr_cnt_2026Q2"])
wide["pop_change_pct"] = (wide["tot_nmpr_cnt_2026Q2"] / wide["tot_nmpr_cnt_2025Q2"] - 1) * 100
wide["hh_change_pct"] = (wide["hh_cnt_2026Q2"] / wide["hh_cnt_2025Q2"] - 1) * 100
wide = wide.reset_index()

price = pd.read_csv("../output/02_dong_yoy_ranked.csv")
merged = wide.merge(price[["dong", "yoy_change_pct"]], on="dong", how="inner")
print(f"인구·가격 둘 다 있는 동: {len(merged)}개")

corr, p_value = stats.pearsonr(merged["pop_change_pct"], merged["yoy_change_pct"])
corr_hh, p_hh = stats.pearsonr(merged["hh_change_pct"], merged["yoy_change_pct"])
print(f"인구 변화율 vs 가격 변화율 상관계수: {corr:.3f} (p={p_value:.4f}, n={len(merged)})")
print(f"세대수 변화율 vs 가격 변화율 상관계수: {corr_hh:.3f} (p={p_hh:.4f})")

# 보광동이 이상치인지 확인 — 7번 축(정비사업 강도)과 같은 패턴(이상치 하나가 상관을 만드는지)이
# 있는지 점검한다 (2026-09-16, codex 검증 이후 다른 축에서 반복 발견된 문제라 여기서도 확인)
no_outlier = merged[merged["dong"] != "11170_보광동"]
corr_wo, p_wo = stats.pearsonr(no_outlier["pop_change_pct"], no_outlier["yoy_change_pct"])
print(f"보광동 제외 상관계수: {corr_wo:.3f} (p={p_wo:.4f}, n={len(no_outlier)})")

corr_summary = pd.DataFrame([{
    "n": len(merged), "pearson_r": corr, "p_value": p_value,
    "pearson_r_excl_bogwangdong": corr_wo, "p_value_excl_bogwangdong": p_wo,
}])
corr_summary.to_csv("../output/12_population_correlation_summary.csv", index=False)
merged.to_csv("../output/12_population_vs_price.csv", index=False)

# 2번 축에서 짚었던 동들 직접 확인
watch = ["11170_보광동", "11680_역삼동", "11680_대치동", "11680_압구정동", "11680_수서동"]
print("\n=== 2번 축에서 언급한 동들의 인구 변화 vs 가격 변화 ===")
cols = ["dong", "gu_name", "umd_nm", "tot_nmpr_cnt_2025Q2", "tot_nmpr_cnt_2026Q2", "pop_change_pct", "yoy_change_pct"]
print(merged[merged["dong"].isin(watch)][cols].to_string(index=False))
