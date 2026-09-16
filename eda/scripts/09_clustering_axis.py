"""9번 축: 동별 가격지수 경로 clustering - 함께 움직이는 동 묶음 찾기.

김용진 님 EDA 제안 문서(eda_filelist.md) 제안 반영. 2016Q1 이후
분기별 log_index QoQ 변화율의 동 간 상관행렬을 구하고, 상관 기반
계층적 클러스터링으로 몇 개 그룹으로 나눈다.
"""
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import fcluster, linkage

from _db import query_df

pd.set_option("display.width", 120)

idx = query_df("""
    select di.dong, d.gu_name, di.quarter, di.log_index
    from app.dong_index di
    join app.dong d on d.dong = di.dong and d.snapshot_id = di.snapshot_id
    join app.dataset_snapshot ds on ds.snapshot_id = di.snapshot_id
    where ds.is_active and di.quarter >= '2016Q1' and di.eligible = true;
""")

wide = idx.pivot(index="quarter", columns="dong", values="log_index").sort_index()
changes = wide.diff().dropna(how="all")

# 결측(그 분기 표본 미달로 제외된 동)이 20% 넘는 동은 클러스터링에서 제외
valid_dongs = changes.columns[changes.isna().mean() < 0.2]
changes = changes[valid_dongs].dropna(axis=0, how="any")
print(f"클러스터링 대상 동: {len(valid_dongs)}개 / 전체 {wide.shape[1]}개, 분기 수: {len(changes)}")

corr = changes.corr()
dist = 1 - corr
# 상삼각만 뽑아 pdist 형태로
condensed = dist.values[np.triu_indices_from(dist.values, k=1)]
Z = linkage(condensed, method="average")

n_clusters = 6
labels = fcluster(Z, t=n_clusters, criterion="maxclust")
cluster_df = pd.DataFrame({"dong": corr.columns, "cluster": labels})

gu_map = idx.drop_duplicates("dong").set_index("dong")["gu_name"]
cluster_df["gu_name"] = cluster_df["dong"].map(gu_map)

print(f"\n=== {n_clusters}개 클러스터 크기 및 구성 자치구(상위 3개) ===")
for c in sorted(cluster_df["cluster"].unique()):
    sub = cluster_df[cluster_df["cluster"] == c]
    top_gu = sub["gu_name"].value_counts().head(3)
    print(f"클러스터 {c} (동 {len(sub)}개): {dict(top_gu)}")

# 클러스터별 평균 QoQ 변화율 경로(최근 8분기)
cluster_series = changes.T.join(cluster_df.set_index("dong")["cluster"]).groupby("cluster").mean().T
print("\n=== 클러스터별 평균 분기 변화율(log), 최근 8분기 ===")
print(cluster_series.tail(8).round(4).to_string())

cluster_df.to_csv("../output/09_dong_clusters.csv", index=False)
cluster_series.to_csv("../output/09_cluster_avg_path.csv")

print("\nCSV 저장 완료: eda/output/09_dong_clusters.csv, 09_cluster_avg_path.csv")
