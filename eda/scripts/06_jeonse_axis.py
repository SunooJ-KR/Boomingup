"""6번 축: 전세가율이 이후 매매가 상승을 선행하는지.

dong_feature의 기점 분기 전세가율(jeonse_ratio_4q)과 dong_index의
이후 h=4분기(1년) 뒤 log 변화율의 상관을 본다.

v2 (2026-09-16 codex 검증 후 수정): idx를 eligible=true로만 가져와 현재·미래 양쪽에
쓰면, 기점(t)뿐 아니라 미래(t+4)에도 표본이 충분한 동만 남는다 — 이건 "기점 당시 알 수
있는 정보"가 아니라 미래 결과를 보고 표본을 고르는 선택 편향이다(docs/decisions.md
결정 7은 기점 직전 4분기 기준만 요구함). eligible 필터를 빼고 log_index를 전부 가져온 뒤,
기점 적격성은 이미 있던 sale_n_all_4q>=20 조건 하나로만 건다.
"""
import numpy as np
import pandas as pd
from scipy import stats

from _db import query_df

pd.set_option("display.width", 120)

feat = query_df("""
    select f.dong, f.as_of_quarter, f.jeonse_ratio_4q, f.sale_n_all_4q
    from app.dong_feature f
    join app.dataset_snapshot ds on ds.snapshot_id = f.snapshot_id
    where ds.is_active and f.jeonse_ratio_4q is not null;
""")

idx = query_df("""
    select di.dong, di.quarter, di.log_index
    from app.dong_index di
    join app.dataset_snapshot ds on ds.snapshot_id = di.snapshot_id
    where ds.is_active;
""")

def add_quarters(q, n):
    y, qq = int(q[:4]), int(q[5])
    total = y * 4 + (qq - 1) + n
    return f"{total // 4}Q{total % 4 + 1}"

feat["future_quarter"] = feat["as_of_quarter"].apply(lambda q: add_quarters(q, 4))

idx_now = idx.rename(columns={"quarter": "as_of_quarter", "log_index": "log_index_now"})
idx_future = idx.rename(columns={"quarter": "future_quarter", "log_index": "log_index_future"})

m = feat.merge(idx_now[["dong", "as_of_quarter", "log_index_now"]], on=["dong", "as_of_quarter"], how="inner")
m = m.merge(idx_future[["dong", "future_quarter", "log_index_future"]], on=["dong", "future_quarter"], how="inner")
m["future_change_1y"] = m["log_index_future"] - m["log_index_now"]

# 최소 표본 조건 (기점 직전 4분기 거래 20건 이상, docs/decisions.md 결정 7과 동일)
m = m[m["sale_n_all_4q"] >= 20]

print(f"분석 대상 행 수: {len(m)} (동x기점 조합, {m['dong'].nunique()}개 동 반복관측 포함)")

jeonse_ratio = m["jeonse_ratio_4q"].astype(float)
future_change = m["future_change_1y"].astype(float)
corr, p_value = stats.pearsonr(jeonse_ratio, future_change)
print(f"\n전세가율(기점) vs 1년 뒤 매매지수 변화의 상관계수(pooled, 동 반복관측 포함): "
      f"{corr:.3f} (p={p_value:.4f}, n={len(m)})")

# 재현 가능하도록 상관계수·n·p값을 CSV로 저장한다 (이전 버전은 콘솔 출력만 하고 저장하지
# 않아 독립 검증이 불가능했다 — 2026-09-16 codex 검증에서 지적됨)
corr_summary = pd.DataFrame([{
    "n": len(m), "n_dong": m["dong"].nunique(), "pearson_r": corr, "p_value": p_value,
    "note": "pooled correlation, 동 반복관측·시장 국면 공통효과 미분리(한계로 명시 필요)",
}])
corr_summary.to_csv("../output/06_jeonse_correlation_summary.csv", index=False)

# 참고: 연도별로 쪼개 봐도 방향이 일관되는지 (국면 공통효과와 구분하기 위한 최소 확인)
m["origin_year"] = m["as_of_quarter"].str[:4].astype(int)
by_year = m.groupby("origin_year").apply(
    lambda g: pd.Series({"n": len(g), "corr": g["jeonse_ratio_4q"].astype(float).corr(g["future_change_1y"].astype(float))}),
    include_groups=False,
)
print("\n=== 연도별(기점 연도) 상관계수 — 국면 공통효과로 전체 상관이 부풀려졌는지 참고용 ===")
print(by_year.round(3).to_string())
by_year.to_csv("../output/06_jeonse_correlation_by_year.csv")

# 전세가율 5분위별 이후 1년 변화율
# future_change_1y는 log 변화량이라 그대로 ×100 하면 실제 %가 아니다 — 행마다 먼저
# expm1(실제 상승률)로 바꾼 뒤 평균낸다(2026-09-16, codex 재검증에서 지적됨. 02번 축과 같은
# log-vs-percent 문제가 이 스크립트에는 반영이 안 돼 있었다).
m["future_change_1y_pct"] = np.expm1(m["future_change_1y"]) * 100
m["jeonse_bin"] = pd.qcut(m["jeonse_ratio_4q"], 5, labels=["Q1(낮음)", "Q2", "Q3", "Q4", "Q5(높음)"])
bin_summary = m.groupby("jeonse_bin", observed=True)["future_change_1y"].agg(n="size", median="median", mean="mean")
bin_summary["mean_pct"] = m.groupby("jeonse_bin", observed=True)["future_change_1y_pct"].mean()
print("\n=== 전세가율 5분위별 1년 뒤 매매지수 변화(mean/median은 log, mean_pct는 실제 %) ===")
print(bin_summary.round(4).to_string())
bin_summary.to_csv("../output/06_jeonse_ratio_vs_future_change.csv")

print("\nCSV 저장 완료: eda/output/06_jeonse_ratio_vs_future_change.csv, "
      "06_jeonse_correlation_summary.csv, 06_jeonse_correlation_by_year.csv")
