"""14번(추가): 9번 축 동 클러스터의 '성향'(특성) 프로파일링.

사용자 요청: 이 프로젝트는 투자자 대상 "특정 지역 투자 상승폭 예측" 서비스이므로,
동을 그냥 그룹으로 나누는 데서 끝내지 않고 그룹별로 어떤 성향(입지 특성·가격대·
정비사업 비중)을 갖는지까지 보여줘야 한다. 9번 축에서 나눈 6개 클러스터(09_dong_clusters.csv)에
대해, 이미 EDA에서 유의했던 입지 지표(한강조망·역세권·학군거리)와 준공연차·정비사업 강도·
현재 가격 수준을 클러스터별 평균으로 집계해 "이 그룹은 대체로 이런 동네다"를 요약한다.
"""
import pandas as pd

from _db import query_df

pd.set_option("display.width", 140)

clusters = pd.read_csv("../output/09_dong_clusters.csv")
# v2(전체 세대수 기준) 강도를 쓴다 — v1(아파트 재고 기준)은 빌라 비중이 큰 동에서 분모가
# 실제보다 작게 잡혀(19개 동에서 946%까지) 정비사업 비중을 과대평가하는 구조적 문제가 있다
# (2026-09-16 확인, 07b_redevelop_intensity_v2.py).
redevelop = pd.read_csv("../output/07b_redevelop_intensity_v2.csv")[["dong", "intensity_v2"]] \
    .rename(columns={"intensity_v2": "redevelop_intensity"})

# 2024년 이후 거래가 있는 단지만, 단지별 입지지표·준공연차·최근 ㎡당 단가를 동 단위로 모은다
trades = query_df("""
    select t.sgg_cd || '_' || t.umd_nm as dong, t.apt_seq,
           t.deal_amount_manwon::float / t.exclu_use_ar::float as price_per_m2
    from app.trade_sale t
    where t.is_cancelled = false and t.deal_amount_manwon > 0 and t.exclu_use_ar > 0
      and t.deal_year >= 2024 and t.apt_seq is not null;
""")
complex_df = query_df("""
    select c.apt_seq, c.built_year, cm.river_view_ratio, cm.station_dist_m,
           cm.elem_school_m, cm.high_school_m
    from app.complex c
    join app.complex_metrics cm on cm.apt_seq = c.apt_seq and cm.snapshot_id = c.snapshot_id
    join app.dataset_snapshot ds on ds.snapshot_id = c.snapshot_id
    where ds.is_active;
""")

df = trades.merge(complex_df, on="apt_seq", how="inner")
df["age"] = 2026 - df["built_year"].astype(float)

dong_profile = df.groupby("dong").agg(
    price_per_m2_median=("price_per_m2", "median"),
    river_view_ratio=("river_view_ratio", "mean"),
    station_dist_m=("station_dist_m", "mean"),
    elem_school_m=("elem_school_m", "mean"),
    high_school_m=("high_school_m", "mean"),
    age_mean=("age", "mean"),
    n_trades=("price_per_m2", "size"),
).reset_index()

prof = clusters.merge(dong_profile, on="dong", how="left").merge(redevelop, on="dong", how="left")
prof.to_csv("../output/14_cluster_dong_profile.csv", index=False)

summary = prof.groupby("cluster").agg(
    n_dong=("dong", "size"),
    price_per_m2_median=("price_per_m2_median", "median"),
    river_view_ratio=("river_view_ratio", "mean"),
    station_dist_m=("station_dist_m", "mean"),
    elem_school_m=("elem_school_m", "mean"),
    age_mean=("age_mean", "mean"),
    redevelop_intensity=("redevelop_intensity", "mean"),
).round(2)
print("\n=== 클러스터별 평균 성향(입지·가격·정비사업) ===")
print(summary.to_string())
summary.to_csv("../output/14_cluster_profile_summary.csv")

# 상승 경로(09_cluster_avg_path.csv)와 합쳐서 "성향 vs 최근 누적 상승폭" 관계도 확인.
# 각 분기 값은 log 단위 초과 변화율이라, 최근 4개 분기를 합산(log 합=누적 수익률)한 뒤
# %로 환산해야 "최근 1년간 서울 평균보다 몇 %p 더/덜 올랐는지"가 정확히 나온다.
import numpy as np

path = pd.read_csv("../output/09_cluster_avg_path.csv", index_col=0)
path.columns = path.columns.astype(int)
recent_log_sum = path.tail(4).sum()
recent_rise = (100 * (np.exp(recent_log_sum) - 1)).rename("recent_1y_excess_change_pct")
summary2 = summary.join(recent_rise)
print("\n=== 성향 + 최근 1년(4분기 누적) 시장 대비 초과 변화율(%, =투자 관점 상승폭) ===")
print(summary2.round(2).to_string())
summary2.to_csv("../output/14_cluster_profile_with_rise.csv")

print("\nCSV 저장 완료: eda/output/14_cluster_dong_profile.csv, 14_cluster_profile_summary.csv, 14_cluster_profile_with_rise.csv")
