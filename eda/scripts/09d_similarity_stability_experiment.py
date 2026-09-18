"""9번 축 후속: "최근 현황 설명"용 유사 동 찾기 — 창 길이·갱신 안정성 실험 (v2).

v1(2026-09-18)을 코덱스가 감사해 지적한 문제를 고쳤다.
  1. 상관 min_periods가 쌍별 공통 관측 기준(창 길이의 75%)을 실제로 강제하지 못했다 ->
     `excess.corr(min_periods=min_common)`으로 직접 강제.
  2. W(8/12/16/20)마다 갱신쌍 수·시작 시점이 달라 비교가 공정하지 않았다 ->
     모든 W가 공통으로 가진 기준 시점 집합에서만 비교.
  3. Jaccard만 보고해 교집합 개수를 못 봤다(비선형이라 착각하기 쉬움) -> intersection_n,
     retention(=교집합/5)도 같이 저장.
  4. 동이 통째로 사라지는 불안정성이 "목록 순위가 바뀌는" 불안정성과 섞여 있었다 ->
     두 시점 모두 서비스 가능했던 동 비율을 별도로 보고.
  5. 부트스트랩이 100회·블록 2분기 하나뿐이었고, 기준 동이 없으면 분모에서 빠져
     불안정성을 과소평가했다 -> 1,000회, 블록 2·4·8분기 비교, 무조건부 빈도도 같이 보고.
  6. leave-one-quarter-out(분기 1개 제거)만 봐서 "1년 갱신"과 직접 비교가 안 됐다 ->
     leave-one-year-block-out(연속 4분기 제거)을 추가.
  7. 5등과 6등의 상관 차이도 확인해 "상위 5개"라는 경계 자체가 임의적인지 점검.
  8. 수천 개 "동-갱신쌍"을 독립 표본처럼 다루지 않고, 갱신 시점별 평균의 분포를 따로 보고.
"""
import numpy as np
import pandas as pd

from _db import query_df

pd.set_option("display.width", 140)
rng = np.random.default_rng(20260918)

idx = query_df("""
    select di.dong, d.gu_name, di.quarter, di.log_index, di.eligible
    from app.dong_index di
    join app.dong d on d.dong = di.dong and d.snapshot_id = di.snapshot_id
    join app.dataset_snapshot ds on ds.snapshot_id = di.snapshot_id
    where ds.is_active and di.quarter >= '2011Q4'
    order by di.dong, di.quarter;
""")

wide = idx[idx["eligible"]].pivot(index="quarter", columns="dong", values="log_index").sort_index()
changes = wide.diff().dropna(how="all")
quarters = changes.index.tolist()
gu_map = idx.drop_duplicates("dong").set_index("dong")["gu_name"]

TOP_N = 5


def top_peers(changes_window, min_common, extra_demean_by_gu=False):
    """쌍별 공통 관측을 min_common으로 실제 강제해서 상위 TOP_N 유사 동을 구한다."""
    valid = changes_window.columns[changes_window.notna().sum() >= min_common]
    cw = changes_window[valid]
    market = cw.mean(axis=1)
    excess = cw.sub(market, axis=0)
    if extra_demean_by_gu:
        gu_of = gu_map.reindex(excess.columns)
        gu_mean = excess.T.groupby(gu_of).transform("mean").T
        excess = excess - gu_mean
    corr = excess.corr(min_periods=min_common)  # 쌍별 공통 관측을 직접 강제(v1의 버그 수정)
    peers, rank6_gap = {}, {}
    for dong in corr.columns:
        s = corr[dong].drop(index=dong).dropna().sort_values(ascending=False)
        if len(s) < TOP_N + 1:
            continue
        peers[dong] = list(s.head(TOP_N).index)
        rank6_gap[dong] = s.iloc[TOP_N - 1] - s.iloc[TOP_N]  # 5등-6등 상관 차이
    return peers, rank6_gap, corr


def jaccard_and_intersection(a, b):
    a, b = set(a), set(b)
    inter = len(a & b)
    union = len(a | b)
    return (inter / union if union else np.nan), inter


# ============================================================
# 1. 모든 W가 공통으로 갖는 기준 시점에서 "1년 갱신" 안정성 비교
# ============================================================
window_lengths = [8, 12, 16, 20]
max_W = max(window_lengths)
snapshot_step = 4  # 1년마다 갱신
# 가장 긴 창(20분기)도 커버 가능한 공통 기준 시점만 쓴다 -> W별 비교가 공정해짐
common_snap_idx = list(range(max_W - 1, len(quarters), snapshot_step))

update_rows = []
for W in window_lengths:
    min_common = int(np.ceil(0.75 * W))
    snap_peers = {}
    snap_n_total = {}
    for si in common_snap_idx:
        end_q = quarters[si]
        start_i = si - W + 1
        win = changes.iloc[start_i:si + 1]
        peers, _, _ = top_peers(win, min_common)
        snap_peers[end_q] = peers
        snap_n_total[end_q] = win.shape[1]  # 참고용

    snap_qs = list(snap_peers.keys())
    for i in range(len(snap_qs) - 1):
        s0, s1 = snap_peers[snap_qs[i]], snap_peers[snap_qs[i + 1]]
        dongs_at_s0 = set(s0)
        both = dongs_at_s0 & set(s1)
        avail_rate = len(both) / len(dongs_at_s0) if dongs_at_s0 else np.nan
        jacs, inters, retentions = [], [], []
        for d in both:
            j, m = jaccard_and_intersection(s0[d], s1[d])
            jacs.append(j)
            inters.append(m)
            retentions.append(m / TOP_N)
        update_rows.append({
            "window": W, "snap_from": snap_qs[i], "snap_to": snap_qs[i + 1],
            "n_dong_both_avail": len(both), "avail_rate": avail_rate,
            "jaccard_mean": np.mean(jacs), "jaccard_median": np.median(jacs),
            "retention_mean": np.mean(retentions), "retention_median": np.median(retentions),
            "intersection_mean": np.mean(inters),
        })

df_update = pd.DataFrame(update_rows)
df_update.to_csv("../output/09d_window_update_stability.csv", index=False)

print("=== 1년 갱신 안정성 (모든 W 공통 기준 시점, 갱신쌍별 요약을 다시 평균) ===")
summary1 = df_update.groupby("window").agg(
    n_update_pairs=("snap_from", "size"),
    avail_rate_mean=("avail_rate", "mean"),
    retention_median_of_medians=("retention_median", "median"),
    jaccard_median_of_medians=("jaccard_median", "median"),
    retention_mean_of_means=("retention_mean", "mean"),
)
print(summary1.round(3).to_string())

# ============================================================
# 2. 가장 최근 공통 창에서 leave-one-quarter-out + leave-one-year-block-out
# ============================================================
loo_rows = []
for W in window_lengths:
    min_common = int(np.ceil(0.75 * W))
    win_full = changes.iloc[-W:]
    peers_full, rank6_gap, _ = top_peers(win_full, min_common)

    # (a) leave-one-quarter-out
    q_jacs, q_rets = [], []
    for drop_i in range(W):
        win_loo = win_full.drop(win_full.index[drop_i])
        min_common_loo = int(np.ceil(0.75 * (W - 1)))
        peers_loo, _, _ = top_peers(win_loo, min_common_loo)
        for d in set(peers_full) & set(peers_loo):
            j, m = jaccard_and_intersection(peers_full[d], peers_loo[d])
            q_jacs.append(j)
            q_rets.append(m / TOP_N)

    # (b) leave-one-year-block-out (연속 4분기 제거, W가 4의 배수인 만큼만 블록 생성)
    b_jacs, b_rets = [], []
    n_blocks = W // 4
    for bi in range(n_blocks):
        drop_idx = list(range(bi * 4, bi * 4 + 4))
        win_lyo = win_full.drop(win_full.index[drop_idx])
        min_common_lyo = int(np.ceil(0.75 * (W - 4)))
        if min_common_lyo < 3:
            continue
        peers_lyo, _, _ = top_peers(win_lyo, min_common_lyo)
        for d in set(peers_full) & set(peers_lyo):
            j, m = jaccard_and_intersection(peers_full[d], peers_lyo[d])
            b_jacs.append(j)
            b_rets.append(m / TOP_N)

    gaps = pd.Series(rank6_gap)
    loo_rows.append({
        "window": W,
        "loo_quarter_retention_median": np.median(q_rets), "loo_quarter_jaccard_median": np.median(q_jacs),
        "loo_year_retention_median": np.median(b_rets) if b_rets else np.nan,
        "loo_year_jaccard_median": np.median(b_jacs) if b_jacs else np.nan,
        "rank5_vs_rank6_gap_median": gaps.median(), "rank5_vs_rank6_gap_lt_0.02_share": (gaps < 0.02).mean(),
    })
    print(f"\nW={W:2d}분기: leave-1분기 retention(중앙값)={np.median(q_rets):.2f}, "
          f"leave-1년블록 retention(중앙값)={np.median(b_rets) if b_rets else float('nan'):.2f}, "
          f"5등-6등 상관차 중앙값={gaps.median():.3f} (0.02 미만 비율={(gaps < 0.02).mean():.1%})")

df_loo = pd.DataFrame(loo_rows)
df_loo.to_csv("../output/09d_leave_one_out_stability.csv", index=False)

# ============================================================
# 3. 블록 부트스트랩 — 블록길이 2·4·8분기 x 1,000회, 무조건부 빈도
# ============================================================
W_boot = 16
min_common_boot = int(np.ceil(0.75 * W_boot))
win_full = changes.iloc[-W_boot:]
peers_full, _, _ = top_peers(win_full, min_common_boot)
n_boot = 1000

boot_rows = []
for block in [2, 4, 8]:
    n_blocks = W_boot // block
    unconditional = {d: 0 for d in peers_full}
    conditional_hits = {d: 0 for d in peers_full}
    conditional_n = {d: 0 for d in peers_full}
    for b in range(n_boot):
        block_starts = rng.integers(0, W_boot - block + 1, size=n_blocks)
        idxs = np.concatenate([np.arange(s, s + block) for s in block_starts])
        win_boot = win_full.iloc[idxs].reset_index(drop=True)
        peers_boot, _, _ = top_peers(win_boot, min_common_boot)
        for d, orig in peers_full.items():
            if d not in peers_boot:
                continue
            conditional_n[d] += 1
            hit = len(set(orig) & set(peers_boot[d]))
            conditional_hits[d] += hit
            unconditional[d] += hit
    for d in peers_full:
        boot_rows.append({
            "block": block, "dong": d,
            "unconditional_mean_hits_of_5": unconditional[d] / n_boot,
            "conditional_mean_hits_of_5": conditional_hits[d] / conditional_n[d] if conditional_n[d] else np.nan,
            "valid_rate": conditional_n[d] / n_boot,
        })
    print(f"\n블록={block}분기, {n_boot}회: 무조건부 평균 유지 개수(5개 중)="
          f"{np.mean([r['unconditional_mean_hits_of_5'] for r in boot_rows if r['block'] == block]):.2f}, "
          f"유효비율 평균={np.mean([r['valid_rate'] for r in boot_rows if r['block'] == block]):.1%}")

df_boot = pd.DataFrame(boot_rows)
df_boot.to_csv("../output/09d_bootstrap_selection_freq.csv", index=False)

# ============================================================
# 4. 구조 점검(정의 민감도로 재해석) — 서울 평균만 제거 vs 구 평균까지 제거
# ============================================================
W_struct = 20
min_common_struct = int(np.ceil(0.75 * W_struct))
win_full = changes.iloc[-W_struct:]
peers_market, _, _ = top_peers(win_full, min_common_struct, extra_demean_by_gu=False)
peers_gu, _, _ = top_peers(win_full, min_common_struct, extra_demean_by_gu=True)
common_dongs = set(peers_market) & set(peers_gu)
jac_struct, ret_struct = [], []
for d in common_dongs:
    j, m = jaccard_and_intersection(peers_market[d], peers_gu[d])
    jac_struct.append(j)
    ret_struct.append(m / TOP_N)
same_gu_share_market = np.mean([
    np.mean([gu_map.get(p) == gu_map.get(d) for p in peers_market[d]]) for d in common_dongs
])
same_gu_share_gu_removed = np.mean([
    np.mean([gu_map.get(p) == gu_map.get(d) for p in peers_gu[d]]) for d in common_dongs
])
n_gu = idx["gu_name"].nunique()
n_dong_struct = len(peers_market)
random_same_gu_share = (n_dong_struct / n_gu - 1) / (n_dong_struct - 1)  # 무작위 기준(구 크기 동일 가정 근사)
print(f"\nW={W_struct}분기, 정의 민감도(시장만 제거 vs 구까지 제거): "
      f"retention 중앙값={np.median(ret_struct):.2f}, Jaccard 중앙값={np.median(jac_struct):.3f}")
print(f"  같은 구 비율: 시장만 제거={same_gu_share_market:.1%}, 구까지 제거={same_gu_share_gu_removed:.1%}, "
      f"무작위 기대치(근사)={random_same_gu_share:.1%}")
pd.DataFrame([{
    "retention_median": np.median(ret_struct), "jaccard_median": np.median(jac_struct),
    "same_gu_share_market_demean": same_gu_share_market,
    "same_gu_share_gu_demean": same_gu_share_gu_removed,
    "random_same_gu_share_approx": random_same_gu_share,
}]).to_csv("../output/09d_gu_structure_check.csv", index=False)

print("\nCSV 저장 완료: 09d_window_update_stability.csv, 09d_leave_one_out_stability.csv, "
      "09d_bootstrap_selection_freq.csv, 09d_gu_structure_check.csv")
