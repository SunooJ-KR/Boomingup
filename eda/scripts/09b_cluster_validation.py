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


def adjusted_rand_index(labels_a, labels_b):
    """scikit-learn 없이 ARI(Adjusted Rand Index)를 직접 계산한다. 두 클러스터링이 얼마나
    일치하는지 0(무작위 수준 일치)~1(완전 일치)로 나타낸다(음수도 가능, 무작위보다 못 맞을 때)."""
    labs_a = np.asarray(labels_a)
    labs_b = np.asarray(labels_b)
    cats_a = np.unique(labs_a)
    cats_b = np.unique(labs_b)
    contingency = np.zeros((len(cats_a), len(cats_b)), dtype=np.int64)
    idx_a = {c: i for i, c in enumerate(cats_a)}
    idx_b = {c: i for i, c in enumerate(cats_b)}
    for x, y in zip(labs_a, labs_b):
        contingency[idx_a[x], idx_b[y]] += 1
    comb2 = lambda x: x * (x - 1) / 2
    sum_comb_c = comb2(contingency).sum()
    a_sums = contingency.sum(axis=1)
    b_sums = contingency.sum(axis=0)
    sum_comb_a = comb2(a_sums).sum()
    sum_comb_b = comb2(b_sums).sum()
    n = len(labs_a)
    total_comb = comb2(n)
    expected = sum_comb_a * sum_comb_b / total_comb if total_comb > 0 else 0
    max_index = (sum_comb_a + sum_comb_b) / 2
    denom = max_index - expected
    if denom == 0:
        return 1.0
    return (sum_comb_c - expected) / denom


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
U, p = stats.mannwhitneyu(within, between, alternative="greater")
# U/(n1*n2) = AUC(임의의 같은-클러스터 쌍이 다른-클러스터 쌍보다 상관이 높을 확률).
# rank-biserial = 2*AUC-1 (0=차이 없음, 1=완전히 분리). 이 통계량들은 유의성(p값)과 달리
# 표본 크기에 영향받지 않는 "효과 크기"라 아래 비독립성 문제에서도 해석 가치가 있다.
auc = U / (len(within) * len(between))
rank_biserial = 2 * auc - 1
print(f"단측 검정(같은 클러스터가 더 높다): p={p:.2e} (동 251개에서 나온 쌍이라 서로 독립이 "
      "아니므로 이 p값 자체는 과신하면 안 됨 — 참고용)")
print(f"효과 크기: rank-biserial={rank_biserial:.3f}, AUC={auc:.3f} "
      "(표본 크기에 영향받지 않는 지표라 더 신뢰할 만함)")
pd.concat([
    pd.DataFrame({"group": "같은 클러스터", "corr": within}),
    pd.DataFrame({"group": "다른 클러스터", "corr": between}),
]).to_csv("../output/09b_within_vs_between_corr.csv", index=False)
pd.DataFrame([{
    "within_mean": within.mean(), "within_median": np.median(within), "within_n": same.sum(),
    "between_mean": between.mean(), "between_median": np.median(between), "between_n": (~same).sum(),
    "p_value": p, "rank_biserial": rank_biserial, "auc": auc,
}]).to_csv("../output/09b_within_vs_between_summary.csv", index=False)

# --- 검증 3: 순환성(circularity) 점검 — 같은 파이프라인을 순수 잡음에 적용해도
# "같은 클러스터가 더 높다"는 결과가 저절로 나오는지 시뮬레이션으로 확인한다.
# (2026-09-18 codex 검증에서 지적: 클러스터를 만든 바로 그 상관행렬로 검증하면
# 진짜 구조가 없어도 이 결과가 나올 수 있다 — 실제로 그런지 직접 확인한다.)
rng = np.random.default_rng(42)
n_quarters, n_dongs = changes.shape
null_diffs, null_ps = [], []
for _ in range(50):
    noise = pd.DataFrame(rng.standard_normal((n_quarters, n_dongs)), columns=changes.columns)
    noise_market = noise.mean(axis=1)
    noise_excess = noise.sub(noise_market, axis=0)
    noise_corr = noise_excess.corr(min_periods=6).fillna(0)
    noise_dist = (1 - noise_corr).values.copy()
    np.fill_diagonal(noise_dist, 0)
    noise_Z = linkage(squareform(noise_dist, checks=False), method="average")
    noise_labels = fcluster(noise_Z, t=6, criterion="maxclust")
    n_iu = np.triu_indices(len(noise_corr), k=1)
    n_same = noise_labels[n_iu[0]] == noise_labels[n_iu[1]]
    n_vals = noise_corr.values[n_iu]
    if n_same.sum() == 0 or (~n_same).sum() == 0:
        continue
    null_diffs.append(n_vals[n_same].mean() - n_vals[~n_same].mean())
    _, np_p = stats.mannwhitneyu(n_vals[n_same], n_vals[~n_same], alternative="greater")
    null_ps.append(np_p)
null_diffs = np.array(null_diffs)
observed_diff = within.mean() - between.mean()
print(f"\n=== 검증 3: 순수 잡음에 같은 파이프라인을 적용했을 때(50회 시뮬레이션) ===")
print(f"잡음에서도 나온 '같은-다른 클러스터' 평균차이: 중앙값 {np.median(null_diffs):.3f} "
      f"(관측값 {observed_diff:.3f})")
print(f"잡음에서도 p<0.001이 나온 비율: {(np.array(null_ps) < 0.001).mean():.0%} "
      "(즉 이 방식의 p값은 구조가 없어도 거의 항상 유의하게 나오므로 신뢰도가 낮다는 뜻)")
pd.DataFrame({"null_diff": null_diffs}).to_csv("../output/09b_null_simulation.csv", index=False)

# --- 검증 4: k=6과 이웃 k의 클러스터가 실제로 얼마나 비슷한지(ARI) ---
labels_by_k = {k: fcluster(Z, t=k, criterion="maxclust") for k in [3, 4, 5, 6, 7]}
ari_vs_6 = {k: adjusted_rand_index(labels_by_k[6], labels_by_k[k]) for k in [3, 4, 5, 7]}
print(f"\n=== k=6 클러스터와 이웃 k의 일치도(ARI, 1=완전 일치, 0=무작위 수준) ===")
for k, ari in sorted(ari_vs_6.items()):
    print(f"k={k} vs k=6: ARI={ari:.3f}")
pd.DataFrame({"k": list(ari_vs_6.keys()), "ari_vs_k6": list(ari_vs_6.values())}).to_csv(
    "../output/09b_ari_vs_k6.csv", index=False)

# --- 상관행렬(클러스터 순서로 정렬) 저장 — 히트맵용 ---
order = cluster_df.loc[corr.columns].sort_values("cluster").index
corr_sorted = corr.loc[order, order]
corr_sorted.to_csv("../output/09b_corr_matrix_sorted.csv")
cluster_df.loc[order, "cluster"].to_csv("../output/09b_corr_matrix_order.csv")

# --- 동별 누적 초과 변화율 경로 저장 — "실제로 같은 클러스터 동끼리 비슷하게 움직이는지"를
# 눈으로 보여주는 그림(클러스터별 소그림)용. 상관계수는 분기별 변화량(excess)으로 계산했지만,
# 그걸 그대로 그리면 분기마다 들쭉날쭉해서 눈으로 추세를 보기 어렵다. 그래서 분기별 excess를
# 누적합(cumsum)한 "그 동이 2016Q1 이후 시장 대비 얼마나 앞서/뒤처졌는지" 경로로 바꿔서 그린다
# (클러스터를 만든 지표 자체는 분기별 excess이고, 이 누적합은 그 지표를 보기 좋게 바꾼 것일 뿐
# 새로운 지표가 아니다).
cum_excess = excess.cumsum()
cum_long = cum_excess.reset_index().melt(id_vars="quarter", var_name="dong", value_name="cum_excess")
cum_long["cluster"] = cum_long["dong"].map(cluster_df["cluster"])
cum_long = cum_long.dropna(subset=["cluster"])
cum_long.to_csv("../output/09b_dong_cum_excess_path.csv", index=False)

print("\nCSV 저장 완료: eda/output/09b_silhouette_by_k.csv, 09b_within_vs_between_corr.csv, "
      "09b_within_vs_between_summary.csv, 09b_corr_matrix_sorted.csv, 09b_corr_matrix_order.csv, "
      "09b_null_simulation.csv, 09b_ari_vs_k6.csv, 09b_dong_cum_excess_path.csv")
