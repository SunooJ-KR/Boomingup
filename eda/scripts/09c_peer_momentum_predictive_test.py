"""9번 축 후속: 클러스터 peer 모멘텀이 미래 가격 변화를 실제로 더 잘 예측하는가.

코덱스 전략 자문(2026-09-18)에서 "군집 재현성 확인보다, peer 모멘텀이 실제 예측력을
더해주는지 rolling-origin으로 직접 검증하는 게 가장 임팩트 있는 다음 스텝"이라는 의견을
받고 이를 구현한 것. 핵심 질문: "이 동과 같은 클러스터에 속한 다른 동들이 최근 얼마나
움직였는지"를 알면, "그 동 자신의 최근 움직임"과 "서울 전체 평균"과 "같은 구 평균"만 아는
것보다 미래 변화를 더 잘 맞히는가?

설계(코덱스 지적 반영):
  - 클러스터는 2016Q1~2019Q4 데이터만으로 "얼려서"(frozen) 미리 만들어둔다. 이후
    2020Q1~2026Q2 구간에서 이 클러스터 라벨을 그대로 써서 peer 모멘텀을 계산하므로,
    적어도 클러스터 라벨 자체는 평가 구간의 미래 정보를 쓰지 않는다.
  - 다만 dong_index 자체는 전체 기간 거래로 추정된 지수라(모델팀 41.build_vintage_momentum.py
    주석 참고), 완전한 vintage-safe는 아니다 — 이 자체가 이번 EDA 세션에서 새로 만들 수는
    없는 기존 인프라 한계라 한계로 명시하고 진행한다.
  - 평가는 origin < 2023Q1로 모델을 적합하고 origin >= 2023Q1로 평가하는 단일 out-of-time
    분할이다(완전한 rolling-origin 다회 재적합은 이번 스코프 밖 — 한계로 명시).
"""
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform

from _db import query_df

pd.set_option("display.width", 140)

idx = query_df("""
    select di.dong, d.gu_name, di.quarter, di.log_index, di.eligible
    from app.dong_index di
    join app.dong d on d.dong = di.dong and d.snapshot_id = di.snapshot_id
    join app.dataset_snapshot ds on ds.snapshot_id = di.snapshot_id
    where ds.is_active and di.quarter >= '2011Q4'
    order by di.dong, di.quarter;
""")

# ------------------------------------------------------------------
# 1. 2016Q1~2019Q4만으로 "얼린" 클러스터 만들기(사전 기간, 평가 구간 미사용)
# ------------------------------------------------------------------
pre = idx[(idx["quarter"] >= "2016Q1") & (idx["quarter"] <= "2019Q4")]
wide_pre = pre[pre["eligible"]].pivot(index="quarter", columns="dong", values="log_index").sort_index()
changes_pre = wide_pre.diff()
valid_pre = changes_pre.columns[changes_pre.notna().sum() >= 6]
changes_pre = changes_pre[valid_pre]
market_pre = changes_pre.mean(axis=1)
excess_pre = changes_pre.sub(market_pre, axis=0)
corr_pre = excess_pre.corr(min_periods=4).fillna(0)
dist_pre = (1 - corr_pre).values.copy()
np.fill_diagonal(dist_pre, 0)
Z_pre = linkage(squareform(dist_pre, checks=False), method="average")
labels_pre = fcluster(Z_pre, t=6, criterion="maxclust")
frozen_cluster = pd.Series(labels_pre, index=corr_pre.columns, name="cluster")
print(f"얼린 클러스터(2016~2019만 사용): {len(frozen_cluster)}개 동, 클러스터 크기 "
      f"{sorted(frozen_cluster.value_counts().tolist(), reverse=True)}")

# ------------------------------------------------------------------
# 2. h분기 모멘텀·타겟 패널 만들기 (origin 2020Q1~2026Q2-h)
# ------------------------------------------------------------------
wide_all = idx.pivot(index="quarter", columns="dong", values="log_index").sort_index()
elig_all = idx.pivot(index="quarter", columns="dong", values="eligible").sort_index().fillna(False)
quarters = wide_all.index.tolist()
q_pos = {q: i for i, q in enumerate(quarters)}
gu_map = idx.drop_duplicates("dong").set_index("dong")["gu_name"]

results = {}
for h in [2, 4, 8]:
    rows = []
    for t in quarters:
        ti = q_pos[t]
        if ti - h < 0 or ti + h >= len(quarters):
            continue
        t_prev = quarters[ti - h]
        t_next = quarters[ti + h]
        if t < "2020Q1":
            continue
        own_mom = wide_all.loc[t] - wide_all.loc[t_prev]
        target = wide_all.loc[t_next] - wide_all.loc[t]
        elig_t = elig_all.loc[t]
        cand = elig_t[elig_t].index
        cand = cand[own_mom.loc[cand].notna() & target.loc[cand].notna()]
        if len(cand) < 10:
            continue
        om = own_mom.loc[cand]
        tg = target.loc[cand]
        market_mom = om.mean()
        gu_s = gu_map.loc[cand]
        gu_peer = om.groupby(gu_s).transform(lambda s: (s.sum() - s) / max(len(s) - 1, 1))
        cl_s = frozen_cluster.reindex(cand)
        has_cl = cl_s.notna()
        cl_peer = pd.Series(np.nan, index=cand)
        if has_cl.sum() > 0:
            om_cl = om[has_cl]
            cl_peer_vals = om_cl.groupby(cl_s[has_cl]).transform(lambda s: (s.sum() - s) / max(len(s) - 1, 1))
            cl_peer.loc[has_cl] = cl_peer_vals
        rows.append(pd.DataFrame({
            "dong": cand, "origin": t, "own_mom": om.values, "market_mom": market_mom,
            "gu_peer_mom": gu_peer.values, "cluster_peer_mom": cl_peer.values, "target": tg.values,
        }))
    panel = pd.concat(rows, ignore_index=True).dropna(subset=["cluster_peer_mom"])
    print(f"\n=== h={h}분기: 패널 {len(panel):,}행, 동 {panel['dong'].nunique()}개, "
          f"기점 {panel['origin'].nunique()}개 (2020Q1~) ===")

    train = panel[panel["origin"] < "2023Q1"]
    test = panel[panel["origin"] >= "2023Q1"]
    print(f"train {len(train):,}행(~2022Q4) / test {len(test):,}행(2023Q1~)")

    base_f = "target ~ own_mom + market_mom + gu_peer_mom"
    aug_f = "target ~ own_mom + market_mom + gu_peer_mom + cluster_peer_mom"
    m_base = smf.ols(base_f, data=train).fit(cov_type="cluster", cov_kwds={"groups": train["dong"]})
    m_aug = smf.ols(aug_f, data=train).fit(cov_type="cluster", cov_kwds={"groups": train["dong"]})

    pred_base_test = m_base.predict(test)
    pred_aug_test = m_aug.predict(test)
    mae_base = (test["target"] - pred_base_test).abs().mean()
    mae_aug = (test["target"] - pred_aug_test).abs().mean()

    cl_coef = m_aug.params["cluster_peer_mom"]
    cl_p = m_aug.pvalues["cluster_peer_mom"]
    print(f"train 적합: cluster_peer_mom 계수={cl_coef:+.4f}, p={cl_p:.4f}, "
          f"R²(base)={m_base.rsquared:.4f} -> R²(aug)={m_aug.rsquared:.4f}")
    print(f"test(2023Q1~) MAE: base={mae_base:.5f} -> aug={mae_aug:.5f} "
          f"({'개선' if mae_aug < mae_base else '악화'}, 차이 {mae_base - mae_aug:+.5f}, "
          f"상대 {100 * (mae_base - mae_aug) / mae_base:+.1f}%)")

    results[h] = {
        "n_train": len(train), "n_test": len(test), "cluster_peer_coef": cl_coef, "cluster_peer_p": cl_p,
        "r2_base": m_base.rsquared, "r2_aug": m_aug.rsquared,
        "mae_base_test": mae_base, "mae_aug_test": mae_aug,
        "mae_improve_pct": 100 * (mae_base - mae_aug) / mae_base,
    }

summary = pd.DataFrame(results).T
summary.index.name = "h"
summary.to_csv("../output/09c_peer_momentum_predictive_test.csv")
print("\n=== 종합 ===")
print(summary.round(4).to_string())
print("\nCSV 저장 완료: eda/output/09c_peer_momentum_predictive_test.csv")
