# ============================================================================
# _dong_weight.py
# ============================================================================
# Author:      yjkim
# Purpose:     동별 세대수 가중치를 만든다. μ(서울 공통 변화)의 가중 기준이다
# Description: 결정 43(재고가중)과 결정 47(bjd_code 매핑)을 구현한다.
#              단지를 동에 붙이는 길이 둘이라 순서를 정해 둔다.
#                (1) 매매 기록의 (sgg_cd, umd_nm) — 여러 동에 걸리면 매매가 많은 쪽
#                (2) (구 코드, bjd_code) 사전 — 매매가 한 번도 없던 단지용
#              커버리지는 세대수 기준 99.3%다(`models/index/64`).
# ============================================================================

import importlib.util

import pandas as pd

COMPLEX_QUERY = """
    select c.apt_seq, c.total_households, c.bjd_code,
           split_part(c.apt_seq, '-', 1) as gu_cd
    from app.complex c
    join app.dataset_snapshot s on s.snapshot_id = c.snapshot_id
    where s.is_active
"""

MAPPING_QUERY = """
    select c.apt_seq, t.sgg_cd || '_' || t.umd_nm as dong, count(*) as n
    from app.complex c
    join app.dataset_snapshot s on s.snapshot_id = c.snapshot_id
    join app.trade_sale t on t.apt_seq = c.apt_seq
    join app.trade_batch b on b.batch_id = t.batch_id
    where s.is_active and b.kind = 'sale' and b.is_active
      and t.sgg_cd is not null and t.umd_nm is not null
    group by 1, 2
"""


def _database_url(work_dir, env_name="DATABASE_READONLY_URL"):
    loader_path = work_dir / "data" / "db" / "50.load_db.py"
    spec = importlib.util.spec_from_file_location("boomingup_load_db", loader_path)
    loader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loader)
    return loader.database_url(env_name)


def dong_households(work_dir):
    """동별 세대수 합계와 커버리지를 돌려준다."""
    import psycopg

    with psycopg.connect(_database_url(work_dir)) as connection:
        complexes = pd.DataFrame(connection.execute(COMPLEX_QUERY).fetchall(),
                                 columns=["apt_seq", "total_households", "bjd_code", "gu_cd"])
        mapping = pd.DataFrame(connection.execute(MAPPING_QUERY).fetchall(),
                               columns=["apt_seq", "dong", "n"])

    complexes["total_households"] = pd.to_numeric(complexes["total_households"], errors="coerce").fillna(0)

    # 경로 1 — 매매가 많은 쪽 동으로 정한다
    primary = (mapping.sort_values("n", ascending=False).drop_duplicates("apt_seq")
               .set_index("apt_seq")["dong"])
    complexes["dong"] = complexes["apt_seq"].map(primary)

    # 경로 2 — (구, bjd_code) 사전으로 나머지를 채운다
    known = complexes[complexes["dong"].notna() & complexes["bjd_code"].notna()]
    vote = known.groupby(["gu_cd", "bjd_code", "dong"])["total_households"].sum().reset_index()
    dictionary = (vote.sort_values("total_households", ascending=False)
                  .drop_duplicates(["gu_cd", "bjd_code"])
                  .set_index(["gu_cd", "bjd_code"])["dong"])
    missing = complexes["dong"].isna()
    filled = pd.MultiIndex.from_frame(complexes.loc[missing, ["gu_cd", "bjd_code"]]).map(dictionary)
    complexes.loc[missing, "dong"] = filled

    total = complexes["total_households"].sum()
    weights = complexes.dropna(subset=["dong"]).groupby("dong")["total_households"].sum()
    return weights.rename("households"), float(weights.sum() / total)
