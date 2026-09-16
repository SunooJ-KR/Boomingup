"""8번 축: 시장 반응이 갈린 이벤트에서 반대로 움직인 동 찾기.

event_summary의 share_same_direction이 낮은(동들의 방향이 크게 갈린)
이벤트를 골라, event_dong_path(k=+4, 4분기 뒤)에서 다수와 반대로
움직인 동을 찾는다.
"""
import pandas as pd

from _db import query_df

pd.set_option("display.width", 120)

events = query_df("""
    select event_id, label, effective_date, category, share_same_direction, share_up
    from app.event_summary
    where pre_observable and post_observable
    order by share_same_direction asc
    limit 5;
""")
print("=== 동 간 방향이 가장 크게 갈린 이벤트 5개 ===")
print(events.to_string(index=False))
events.to_csv("../output/08_low_consensus_events.csv", index=False)

paths = query_df("""
    select edp.event_id, edp.dong, d.gu_name, edp.k, edp.rel_log_change
    from app.event_dong_path edp
    join app.dong d on d.dong = edp.dong
    where edp.event_id in %s and edp.k = 4;
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
