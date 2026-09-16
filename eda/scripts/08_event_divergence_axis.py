"""8번 축: 시장 반응이 갈린 이벤트에서 반대로 움직인 동 찾기.

event_summary에서 상승한 동 비율(share_up)이 50%에 가장 가까운(=반반으로 갈린)
이벤트를 골라, event_dong_path(k=+4, 4분기 뒤)에서 다수와 반대로 움직인 동을 찾는다.

v2 (2026-09-16 codex 검증 후 수정): 원래는 share_same_direction(=평균 변화와 같은
부호로 움직인 동 비율)이 작은 순으로 골랐다. 그런데 이 값은 평균이 한쪽으로 치우쳐 있으면
"반반으로 갈렸다"가 아니라 "평균과 다르게 움직인 동이 많다"는 뜻이 될 수 있다(예: P19는
share_same_direction=share_up=0.454로 우연히 같았는데, 이는 평균 부호가 다수 방향과
반대라서 생긴 값이다). 우리가 차트·설명에서 실제로 쓰는 정의("상승한 동 비율이 50%에
가까울수록 반반")에 맞게 |share_up-0.5| 오름차순으로 고르도록 고쳤다.
"""
import pandas as pd

from _db import query_df

pd.set_option("display.width", 120)

events = query_df("""
    select es.event_id, es.label, es.effective_date, es.category, es.share_same_direction,
           es.share_up, es.overlapping_events
    from app.event_summary es
    join app.dataset_snapshot ds on ds.snapshot_id = es.snapshot_id
    where ds.is_active and es.pre_observable and es.post_observable;
""")
events["dist_from_half"] = (events["share_up"].astype(float) - 0.5).abs()
# 동률일 때도 항상 같은 순서가 나오도록 event_id를 2차 정렬 기준으로 둔다
events = events.sort_values(["dist_from_half", "event_id"]).head(5)
print("=== 상승한 동 비율이 50%에 가장 가까운(=반반으로 갈린) 이벤트 5개 ===")
print(events[["event_id", "label", "effective_date", "share_up", "overlapping_events"]].to_string(index=False))
events.to_csv("../output/08_low_consensus_events.csv", index=False)

has_overlap = events["overlapping_events"].fillna("").str.len() > 0
print(f"\n선택된 5개 중 다른 이벤트와 ±4분기 내에 겹치는 것: {has_overlap.sum()}개 "
      f"({', '.join(events.loc[has_overlap, 'event_id'])})")

paths = query_df("""
    select edp.event_id, edp.dong, d.gu_name, edp.k, edp.rel_log_change
    from app.event_dong_path edp
    join app.dong d on d.dong = edp.dong and d.snapshot_id = edp.snapshot_id
    join app.dataset_snapshot ds on ds.snapshot_id = edp.snapshot_id
    where ds.is_active and edp.event_id in %s and edp.k = 4;
""", (tuple(events["event_id"]),))

results = []
for _, ev in events.iterrows():
    eid = ev["event_id"]
    sub = paths[paths["event_id"] == eid].copy()
    if sub.empty:
        continue
    majority_up = ev["share_up"] >= 0.5
    # 다수 방향과 반대로 움직인 동 중, 변화폭이 큰 순
    if majority_up:
        opposite = sub[sub["rel_log_change"] < 0].sort_values("rel_log_change")
    else:
        opposite = sub[sub["rel_log_change"] > 0].sort_values("rel_log_change", ascending=False)
    top5 = opposite.head(5)
    top5 = top5.assign(event_label=ev["label"], majority_direction="상승" if majority_up else "하락")
    results.append(top5[["event_id", "event_label", "majority_direction", "dong", "gu_name", "rel_log_change"]])
    print(f"\n=== {eid} ({ev['label']}) — 다수는 '{'상승' if majority_up else '하락'}', "
          f"반대로 가장 크게 움직인 동 5개 ===")
    print(top5[["dong", "gu_name", "rel_log_change"]].to_string(index=False))

if results:
    out = pd.concat(results, ignore_index=True)
    out.to_csv("../output/08_divergent_dongs.csv", index=False)
    print("\nCSV 저장 완료: eda/output/08_low_consensus_events.csv, 08_divergent_dongs.csv")
