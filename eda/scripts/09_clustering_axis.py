"""9번 축: 동별 가격지수 경로 clustering - 함께 움직이는 동 묶음 찾기.

김용진 님 EDA 제안 문서(eda_filelist.md) 제안 반영. 2016Q1 이후
분기별 log_index 변화율의 동 간 상관행렬을 구하고, 상관 기반
계층적 클러스터링으로 몇 개 그룹으로 나눈다.

v2 (2026-09-16 재설계): 최초 버전은 eligible=true 분기만 남기고, 조금이라도 결측이 있는
분기를 통째로 버리는 listwise 방식이라 41개 분기 중 24개만 남고 시계열이 끊겨 195개 동 중
167개가 한 클러스터에 쏠렸다. 원인을 다시 보니 두 가지였다.
  ① dong_index.log_index는 eligible=false 분기에도 값이 채워져 있다(표본이 적어 구 지수
     쪽으로 많이 수축된 값일 뿐 결측이 아니다). 상관계수는 pandas corr()이 기본으로 쌍별
     결측 제외(pairwise-complete)를 하므로, listwise로 행을 통째로 버릴 필요가 없었다.
  ② 동 간 평균 상관계수가 0.385(중앙값 0.41)로 매우 높았다 — 서울 부동산 시장 전체가 같이
     움직이는 공통 요인이 강해서, 원본 상관행렬로 클러스터링하면 "전체가 한 덩어리"로
     뭉치는 게 오히려 당연한 결과였다(방법의 결함이 아니라 시장 구조 자체).
이 두 가지를 고쳤다: listwise 삭제 없이 pairwise-complete 상관을 쓰고, 분기별 "그 분기
eligible 동들의 평균 변화(공통 시장 움직임)"를 먼저 뺀 뒤(=시장 대비 상대적 움직임만 남김)
그 잔차로 클러스터링한다.
"""
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform

from _db import query_df

pd.set_option("display.width", 120)

idx = query_df("""
    select di.dong, d.gu_name, di.quarter, di.log_index, di.eligible
    from app.dong_index di
    join app.dong d on d.dong = di.dong and d.snapshot_id = di.snapshot_id
    join app.dataset_snapshot ds on ds.snapshot_id = di.snapshot_id
    where ds.is_active and di.quarter >= '2016Q1';
""")

# eligible(표본기준 통과) 분기만 쓴다 — 수축이 심한 ineligible 값까지 넣으면 "다들 구
# 지수를 따라간다"는 인위적 유사성이 섞일 수 있어서다.
wide = idx[idx["eligible"]].pivot(index="quarter", columns="dong", values="log_index").sort_index()
changes = wide.diff()

# 관측치가 너무 적은(8분기 미만) 동은 상관 추정이 불안정해 제외한다. listwise 삭제(행 통째로
# 버리기)는 하지 않는다 — corr()이 쌍별로 알아서 처리한다.
valid_dongs = changes.columns[changes.notna().sum() >= 8]
changes = changes[valid_dongs]
print(f"클러스터링 대상 동: {len(valid_dongs)}개 / 전체 {wide.shape[1]}개")

# 분기별 공통 시장 움직임(그 분기 eligible 동들의 평균 변화율)을 빼서, "시장 대비 상대적으로
# 더/덜 움직인 정도"만 남긴다. 이게 없으면 강한 공통 요인 때문에 다들 양의 상관을 보여
# 클러스터링이 사실상 "전체=한 그룹"으로 무너진다(v1에서 확인됨, 평균 상관 0.385).
market = changes.mean(axis=1)
excess = changes.sub(market, axis=0)

corr = excess.corr(min_periods=6)  # 공통 관측 6개 미만인 쌍은 상관을 신뢰하지 않는다
n_unstable = corr.isna().sum().sum()
corr = corr.fillna(0)  # 계산 불가능한 쌍은 "무관"으로 취급(클러스터링 알고리즘이 NaN을 못 다룸)
print(f"상관계수 계산 불가능했던 쌍(공통 관측 6개 미만, 0으로 대체): {n_unstable}쌍")

dist_vals = (1 - corr).values.copy()
np.fill_diagonal(dist_vals, 0)
condensed = squareform(dist_vals, checks=False)
Z = linkage(condensed, method="average")

n_clusters = 6
labels = fcluster(Z, t=n_clusters, criterion="maxclust")
cluster_df = pd.DataFrame({"dong": corr.columns, "cluster": labels})

gu_map = idx.drop_duplicates("dong").set_index("dong")["gu_name"]
cluster_df["gu_name"] = cluster_df["dong"].map(gu_map)

print(f"\n=== {n_clusters}개 클러스터 크기 및 구성 자치구(상위 4개) ===")
for c in sorted(cluster_df["cluster"].unique()):
    sub = cluster_df[cluster_df["cluster"] == c]
    top_gu = sub["gu_name"].value_counts().head(4)
    print(f"클러스터 {c} (동 {len(sub)}개): {dict(top_gu)}")

max_share = cluster_df["cluster"].value_counts().max() / len(cluster_df)
print(f"\n최대 클러스터 쏠림: {max_share:.1%} (v1은 85.6%였음)")

# 클러스터별 평균 "시장 대비 초과 변화율" 경로(최근 8분기)
cluster_series = excess.T.join(cluster_df.set_index("dong")["cluster"]).groupby("cluster").mean().T
print("\n=== 클러스터별 평균 시장 대비 초과 변화율(log), 최근 8분기 ===")
print(cluster_series.tail(8).round(4).to_string())

cluster_df.to_csv("../output/09_dong_clusters.csv", index=False)
cluster_series.to_csv("../output/09_cluster_avg_path.csv")

print("\nCSV 저장 완료: eda/output/09_dong_clusters.csv, 09_cluster_avg_path.csv")
