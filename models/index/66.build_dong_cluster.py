# ============================================================================
# 66.build_dong_cluster.py
# ============================================================================
# Author:      yjkim
# Purpose:     동을 구조 변수로 묶는다 (Track K, K-S). 구를 대신할 pooling 단위다
# Description: 동 구조 클러스터 산출. 현행 사용 기준은 docs/decisions.md 결정 57·65.
#
#              구는 행정 경계지 경제적 경계가 아니다. 가격대·전세가율·재고·신축 비중·
#              위치가 비슷한 동끼리 묶으면 구보다 나은 그룹이 될 수 있다.
#
#              δ 이력은 쓰지 않는다. 그래서 묶는 창과 모멘텀 창의 이중 사용이 없고,
#              거래가 없는 동도 배정된다. 계획이 K-S를 먼저 하라고 한 이유다.
#
#              누수 방지: 기점마다 그 기점의 dong_feature(as_of_quarter)로 다시 묶는다.
#              정비사업(rz_*)은 2026-06 한 시점 파일이라 과거 기점에 쓰면 미래를 아는
#              셈이 되므로 뺀다. 인가일 이벤트(D-3)가 생기면 넣는다.
#
#              K 선택: K ∈ {4, 5, 6}. 성능이 아니라 인접 기점 간 소속 일치도(ARI)가 가장
#              안정적인 K를 고른다. 성능으로 고르면 그 성능은 K 선택에 이미 쓰인 것이다.
# ============================================================================

# ============================================================================
# 0. 환경 설정
# ============================================================================

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import psycopg
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score
from sklearn.preprocessing import StandardScaler

work_dir = Path(__file__).resolve().parents[2]
output_dir = work_dir / "output"

FIRST_AS_OF = pd.Period("2015Q1", freq="Q")
LAST_AS_OF = pd.Period("2026Q2", freq="Q")
K_CANDIDATES = [4, 5, 6]
SEED = 20260917

import argparse
parser = argparse.ArgumentParser(description="동 클러스터링 (Track K)")
parser.add_argument("--input", choices=["structure", "delta"], default="structure",
                    help="structure=K-S 구조 변수, delta=K-δ δ 경로 (K-S로 C-1k가 실패했을 때만)")
args = parser.parse_args()

# K-δ 설정. 묶는 창은 T−8..T−4로, 모멘텀 창(T−4..T)과 겹치지 않는다(계획 §2.5 이중 사용 방지).
# K는 K-S가 안정성으로 고른 값을 그대로 쓴다. 두 번 고르지 않는다
DELTA_WINDOW_END_LAG = 4
DELTA_K = 4
MOMENTUM_Q = 4

# 서울시청, 강남역. 도심·강남 거리는 위치를 한 축으로 줄인 것이다
CBD = (37.5665, 126.9780)
GANGNAM = (37.4979, 127.0276)


def database_url(env_name="DATABASE_READONLY_URL"):
    loader_path = work_dir / "data" / "db" / "50.load_db.py"
    spec = importlib.util.spec_from_file_location("boomingup_load_db", loader_path)
    loader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loader)
    return loader.database_url(env_name)


def km_distance(lat, lng, point):
    """위경도 두 점의 대략 거리(km). 서울 안에서는 평면 근사로 충분하다."""
    return np.sqrt(((lat - point[0]) * 111.0) ** 2 + ((lng - point[1]) * 88.0) ** 2)


# ============================================================================
# K-δ — δ 경로로 묶는다 (--input delta)
# ============================================================================

if args.input == "delta":
    from _dong_weight import dong_households

    vintage_path = output_dir / "67.0.vintage_index.txt"
    ks_path = output_dir / "66.1.dong_cluster.txt"
    if not vintage_path.is_file() or not ks_path.is_file():
        raise SystemExit("67.0 vintage 지수와 66.1 K-S 소속이 먼저 있어야 한다")

    vintage = pd.read_csv(vintage_path, sep="\t")
    vintage["as_of"] = pd.PeriodIndex(vintage["as_of"], freq="Q")
    vintage["quarter"] = pd.PeriodIndex(vintage["quarter"], freq="Q")
    ks = pd.read_csv(ks_path, sep="\t")
    ks["as_of"] = pd.PeriodIndex(ks["as_of"], freq="Q")
    weights, _ = dong_households(work_dir)

    print("===== K-δ. δ 경로 클러스터링 =====")
    print(f"  묶는 창 T−{DELTA_WINDOW_END_LAG + MOMENTUM_Q}..T−{DELTA_WINDOW_END_LAG}, K={DELTA_K} (K-S와 같은 값)")

    labels_delta, ari_vs_ks = {}, []
    for as_of in sorted(vintage["as_of"].unique()):
        block = vintage[vintage["as_of"] == as_of]
        wide = block.pivot_table(index="dong", columns="quarter", values="log_index")
        quarters = [as_of - lag for lag in range(DELTA_WINDOW_END_LAG + MOMENTUM_Q, DELTA_WINDOW_END_LAG - 1, -1)]
        if any(quarter not in wide.columns for quarter in quarters):
            continue
        path = wide[quarters].diff(axis=1).iloc[:, 1:]                      # 분기별 변화 4개
        weight = path.index.map(weights).fillna(0.0).to_numpy()
        common = np.average(path.to_numpy(), axis=0, weights=weight) if weight.sum() > 0 else path.mean().to_numpy()
        path = path - common                                                # 서울 공통 몫을 뺀 δ 경로

        latest = block[block["quarter"] == as_of].set_index("dong")
        eligible = latest["eligible"].reindex(path.index).fillna(False).astype(bool)
        se = latest["log_index_se"].reindex(path.index)
        core = path[eligible & path.notna().all(axis=1)]
        if len(core) < 50:
            continue
        # 측정오차가 큰 동은 덜 믿는다. 잡음을 묶으면 잡음 클러스터가 나온다
        sample_weight = (1.0 / se.loc[core.index] ** 2).to_numpy()
        model = KMeans(n_clusters=DELTA_K, n_init=10, random_state=SEED).fit(core.to_numpy(), sample_weight=sample_weight)
        label = pd.Series(model.labels_, index=core.index)

        # 비eligible 동은 δ 경로가 잡음이라 같은 K-S 클러스터의 eligible 동이 가장 많이 속한 K-δ 클러스터로 보낸다
        ks_now = ks[ks["as_of"] == as_of].set_index("dong")["cluster"]
        rest = [dong for dong in path.index if dong not in label.index and dong in ks_now.index]
        if rest:
            mates = pd.DataFrame({"ks": ks_now.reindex(label.index), "kd": label}).dropna()
            mode_by_ks = mates.groupby("ks")["kd"].agg(lambda values: values.mode().iloc[0])
            fallback = pd.Series(ks_now.loc[rest].map(mode_by_ks), index=rest).dropna().astype(int)
            label = pd.concat([label, fallback])
        label.index.name = "dong"   # 비eligible 배정을 붙이면 index 이름이 사라진다
        labels_delta[as_of] = label

        shared = label.index.intersection(ks_now.index)
        ari_vs_ks.append(adjusted_rand_score(ks_now.loc[shared], label.loc[shared]))

    ordered = sorted(labels_delta)
    adjacent = []
    for previous, current in zip(ordered[:-1], ordered[1:]):
        shared = labels_delta[previous].index.intersection(labels_delta[current].index)
        adjacent.append(adjusted_rand_score(labels_delta[previous].loc[shared], labels_delta[current].loc[shared]))

    print(f"  기점 {len(labels_delta)}개")
    print(f"  인접 기점 간 ARI 중앙값 {np.median(adjacent):.3f}, 최소 {np.min(adjacent):.3f}")
    print(f"  K-S와의 ARI 중앙값 {np.median(ari_vs_ks):.3f} (낮을수록 K-S와 다르게 묶는다)")

    membership = pd.concat(
        [series.rename("cluster").reset_index().assign(as_of=as_of) for as_of, series in labels_delta.items()],
        ignore_index=True)[["as_of", "dong", "cluster"]]
    membership_path = output_dir / "66.4.dong_cluster_delta.txt"
    membership.to_csv(membership_path, sep="\t", index=False, lineterminator="\n")
    print(f"\n소속: {membership_path}")
    raise SystemExit(0)


# ============================================================================
# 1. 구조 변수 적재
# ============================================================================

FEATURE_QUERY = """
    select f.dong, f.as_of_quarter, f.sale_ppm2_med_4q, f.jeonse_ratio_4q,
           f.stock_hh, f.completed_hh_8q
    from app.dong_feature f
    join app.dataset_snapshot s on s.snapshot_id = f.snapshot_id
    where s.is_active and f.as_of_quarter >= %s
"""
BOUNDARY_QUERY = """
    select b.dong, b.centroid_lat, b.centroid_lng
    from app.dong_boundary b
    join app.dataset_snapshot s on s.snapshot_id = b.snapshot_id
    where s.is_active and b.in_index
"""

with psycopg.connect(database_url()) as connection:
    features = pd.DataFrame(connection.execute(FEATURE_QUERY, (str(FIRST_AS_OF),)).fetchall(),
                            columns=["dong", "as_of", "ppm2", "jeonse_ratio", "stock_hh", "completed_hh_8q"])
    boundary = pd.DataFrame(connection.execute(BOUNDARY_QUERY).fetchall(),
                            columns=["dong", "lat", "lng"])

features["as_of"] = pd.PeriodIndex(features["as_of"], freq="Q")
features = features[features["as_of"] <= LAST_AS_OF]
for column in ["ppm2", "jeonse_ratio", "stock_hh", "completed_hh_8q"]:
    features[column] = pd.to_numeric(features[column], errors="coerce")
features["sggCd"] = features["dong"].str.split("_").str[0]
features = features.merge(boundary, on="dong", how="left")

print("===== 1. 구조 변수 적재 =====")
print(f"  {len(features):,}행 = 동 {features['dong'].nunique()}개 × 기점 {features['as_of'].nunique()}개")
print(f"  경계 centroid 없는 동 {int(features['lat'].isna().groupby(features['dong']).first().sum())}개")


# ============================================================================
# 2. 기점별 feature 행렬
# ============================================================================

def feature_matrix(block):
    """한 기점의 동별 구조 변수. 결측은 같은 구의 중앙값으로 채운다."""
    frame = block.copy()
    frame["log_ppm2"] = np.log(frame["ppm2"])
    frame["log_stock"] = np.log1p(frame["stock_hh"])
    frame["new_share"] = frame["completed_hh_8q"] / frame["stock_hh"].replace(0, np.nan)
    frame["dist_cbd"] = km_distance(frame["lat"], frame["lng"], CBD)
    frame["dist_gangnam"] = km_distance(frame["lat"], frame["lng"], GANGNAM)

    columns = ["log_ppm2", "jeonse_ratio", "log_stock", "new_share", "lat", "lng", "dist_cbd", "dist_gangnam"]
    for column in columns:
        by_gu = frame.groupby("sggCd")[column].transform("median")
        frame[column] = frame[column].fillna(by_gu).fillna(frame[column].median())
    return frame[["dong"] + columns].dropna().reset_index(drop=True)


# ============================================================================
# 3. 기점별 클러스터링과 K별 안정성
# ============================================================================

as_of_list = sorted(features["as_of"].unique())
labels = {k: {} for k in K_CANDIDATES}

print(f"\n===== 2. 기점별 k-means ({len(as_of_list)}개 기점 × K {K_CANDIDATES}) =====")
for as_of in as_of_list:
    matrix = feature_matrix(features[features["as_of"] == as_of])
    if len(matrix) < 50:
        continue
    scaled = StandardScaler().fit_transform(matrix.drop(columns="dong"))
    for k in K_CANDIDATES:
        model = KMeans(n_clusters=k, n_init=10, random_state=SEED).fit(scaled)
        labels[k][as_of] = pd.Series(model.labels_, index=matrix["dong"])

# 인접 기점 간 소속 일치도. 라벨 번호는 기점마다 임의라 ARI로 본다
stability = []
for k in K_CANDIDATES:
    ordered = sorted(labels[k])
    scores = []
    for previous, current in zip(ordered[:-1], ordered[1:]):
        common = labels[k][previous].index.intersection(labels[k][current].index)
        scores.append(adjusted_rand_score(labels[k][previous].loc[common], labels[k][current].loc[common]))
    stability.append({"K": k, "ARI 중앙값": float(np.median(scores)),
                      "ARI 하위 10%": float(np.percentile(scores, 10)), "ARI 최소": float(np.min(scores))})
stability = pd.DataFrame(stability)

print("\n  인접 기점 간 소속 일치도:")
print(stability.to_string(index=False, float_format=lambda value: f"{value:.3f}"))

# K는 안정성으로 고정한다. 성능으로 고르지 않는다(계획 §2.5)
chosen_k = int(stability.sort_values(["ARI 중앙값", "ARI 하위 10%"], ascending=False).iloc[0]["K"])
print(f"\n  채택 K = {chosen_k} (ARI 중앙값 기준). 이후 성능을 보고 바꾸지 않는다")


# ============================================================================
# 4. 채택 K의 소속과 클러스터 특성
# ============================================================================

membership = pd.concat(
    [series.rename("cluster").reset_index().assign(as_of=as_of) for as_of, series in labels[chosen_k].items()],
    ignore_index=True)[["as_of", "dong", "cluster"]]

latest = membership[membership["as_of"] == membership["as_of"].max()]
profile = (feature_matrix(features[features["as_of"] == latest["as_of"].iloc[0]])
           .merge(latest[["dong", "cluster"]], on="dong")
           .groupby("cluster")
           .agg(동수=("dong", "size"), 평당가_중앙=("log_ppm2", lambda v: float(np.exp(v.median()))),
                전세가율=("jeonse_ratio", "median"), 신축비중=("new_share", "median"),
                도심거리km=("dist_cbd", "median"), 강남거리km=("dist_gangnam", "median"))
           .reset_index())

print(f"\n===== 3. 최신 기점({latest['as_of'].iloc[0]}) 클러스터 특성 =====")
print(profile.to_string(index=False, float_format=lambda value: f"{value:,.2f}"))

# 구와 얼마나 다르게 묶였는가. 구와 같으면 이 트랙은 할 이유가 없다
gu_of = latest["dong"].str.split("_").str[0]
print(f"\n  최신 기점에서 구 소속과의 ARI: {adjusted_rand_score(gu_of, latest['cluster']):.3f} "
      f"(1이면 구와 같은 묶음, 0이면 무관)")


# ============================================================================
# 5. 저장
# ============================================================================

membership_path = output_dir / "66.1.dong_cluster.txt"
membership.to_csv(membership_path, sep="\t", index=False, lineterminator="\n")
stability_path = output_dir / "66.2.cluster_stability.txt"
stability.assign(채택=lambda frame: frame["K"] == chosen_k).to_csv(
    stability_path, sep="\t", index=False, lineterminator="\n")
profile_path = output_dir / "66.3.cluster_profile.txt"
profile.to_csv(profile_path, sep="\t", index=False, lineterminator="\n")

print(f"\n소속: {membership_path}")
print(f"안정성: {stability_path}")
print(f"특성: {profile_path}")
