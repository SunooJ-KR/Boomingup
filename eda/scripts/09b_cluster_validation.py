"""9번 축 검증: 클러스터링이 객관적으로 타당한지 확인.

09_clustering_axis.py와 동일한 방식(시장 평균을 뺀 "초과 변화율"의 분기별 시계열
간 피어슨 상관계수)으로 상관행렬과 클러스터를 재현한 뒤, 다음을 확인한다.
  1. "비슷하게 움직인다"의 정의 자체가 이 상관계수라는 걸 재확인.
  2. 같은 클러스터로 묶인 동끼리의 상관계수가, 다른 클러스터 동끼리의 상관계수보다
     실제로 더 높은지(그렇지 않다면 클러스터링이 무의미한 것).
  3. 클러스터 개수 6개가 임의로 고른 값인지, 실루엣 점수(클러스터링 품질을 재는
     표준 지표) 기준으로 다른 개수보다 나은지.

그림은 10_team_meeting_figures.py가 여기서 저장한 CSV를 읽어서 그린다(이 스크립트는
계산만 담당 — 프로젝트 관례).
"""
import numpy as np
import pandas as pd
from scipy import stats
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform

from _db import query_df


def silhouette_score(dist, labels):
    """scikit-learn 없이 실루엣 점수를 직접 계산한다(사전 계산된 거리행렬 기준).
    각 점 i에 대해 a(i)=같은 클러스터 내 평균거리, b(i)=가장 가까운 다른 클러스터까지
    평균거리, s(i)=(b-a)/max(a,b). 전체 평균이 실루엣 점수(-1~+1, 클수록 좋음)."""
    labels = np.asarray(labels)
    n = len(labels)
    scores = np.zeros(n)
    for i in range(n):
        same = (labels == labels[i])
        same[i] = False
        if same.sum() == 0:
            scores[i] = 0
            continue
        a = dist[i, same].mean()
        b = np.inf
        for c in set(labels) - {labels[i]}:
            mask = labels == c
            b = min(b, dist[i, mask].mean())
        scores[i] = (b - a) / max(a, b) if max(a, b) > 0 else 0
    return scores.mean()


pd.set_option("display.width", 120)

idx = query_df("""
    select di.dong, d.gu_name, di.quarter, di.log_index, di.eligible
    from app.dong_index di
    join app.dong d on d.dong = di.dong and d.snapshot_id = di.snapshot_id
    join app.dataset_snapshot ds on ds.snapshot_id = di.snapshot_id
    where ds.is_active and di.quarter >= '2016Q1';
""")

wide = idx[idx["eligible"]].pivot(index="quarter", columns="dong", values="log_index").sort_index()
changes = wide.diff()
valid_dongs = changes.columns[changes.notna().sum() >= 8]
changes = changes[valid_dongs]
market = changes.mean(axis=1)
excess = changes.sub(market, axis=0)
corr = excess.corr(min_periods=6).fillna(0)

dist_vals = (1 - corr).values.copy()
np.fill_diagonal(dist_vals, 0)
condensed = squareform(dist_vals, checks=False)
Z = linkage(condensed, method="average")

cluster_df = pd.read_csv("../output/09_dong_clusters.csv").set_index("dong")
labels = cluster_df.loc[corr.columns, "cluster"].values

# --- 검증 1: 실루엣 점수 ---
sil_by_k = {}
for k in range(2, 13):
    lab_k = fcluster(Z, t=k, criterion="maxclust")
    if len(set(lab_k)) < 2:
        continue
    sil_by_k[k] = silhouette_score(dist_vals, lab_k)
print("=== 클러스터 개수(k)별 실루엣 점수 ===")
for k, s in sil_by_k.items():
    marker = "  <- 이번에 쓴 k=6" if k == 6 else ""
    print(f"k={k:2d}: {s:+.4f}{marker}")
best_k = max(sil_by_k, key=sil_by_k.get)
print(f"실루엣 점수가 가장 높은 k: {best_k} (점수 {sil_by_k[best_k]:.4f})")
pd.DataFrame({"k": list(sil_by_k.keys()), "silhouette": list(sil_by_k.values())}).to_csv(
    "../output/09b_silhouette_by_k.csv", index=False)

# --- 검증 2: 같은 클러스터 쌍 vs 다른 클러스터 쌍의 상관계수 비교 ---
n = len(corr)
iu = np.triu_indices(n, k=1)
same = labels[iu[0]] == labels[iu[1]]
corr_vals = corr.values[iu]
within = corr_vals[same]
between = corr_vals[~same]
print(f"\n=== 같은 클러스터 쌍 vs 다른 클러스터 쌍의 상관계수 ===")
print(f"같은 클러스터({same.sum()}쌍): 평균 {within.mean():.3f}, 중앙값 {np.median(within):.3f}")
print(f"다른 클러스터({(~same).sum()}쌍): 평균 {between.mean():.3f}, 중앙값 {np.median(between):.3f}")
_, p = stats.mannwhitneyu(within, between, alternative="greater")
print(f"단측 검정(같은 클러스터가 더 높다): p={p:.2e}")
pd.concat([
    pd.DataFrame({"group": "같은 클러스터", "corr": within}),
    pd.DataFrame({"group": "다른 클러스터", "corr": between}),
]).to_csv("../output/09b_within_vs_between_corr.csv", index=False)
pd.DataFrame([{
    "within_mean": within.mean(), "within_median": np.median(within), "within_n": same.sum(),
    "between_mean": between.mean(), "between_median": np.median(between), "between_n": (~same).sum(),
    "p_value": p,
}]).to_csv("../output/09b_within_vs_between_summary.csv", index=False)

# --- 상관행렬(클러스터 순서로 정렬) 저장 — 히트맵용 ---
order = cluster_df.loc[corr.columns].sort_values("cluster").index
corr_sorted = corr.loc[order, order]
corr_sorted.to_csv("../output/09b_corr_matrix_sorted.csv")
cluster_df.loc[order, "cluster"].to_csv("../output/09b_corr_matrix_order.csv")

print("\nCSV 저장 완료: eda/output/09b_silhouette_by_k.csv, 09b_within_vs_between_corr.csv, "
      "09b_within_vs_between_summary.csv, 09b_corr_matrix_sorted.csv, 09b_corr_matrix_order.csv")
