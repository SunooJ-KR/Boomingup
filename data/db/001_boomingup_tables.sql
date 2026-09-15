-- Boomingup 정제 데이터와 원천 거래 원장 테이블입니다.
-- 기존 app 테이블은 변경하지 않습니다. 관리자 권한으로 한 번 적용합니다.

begin;

create table if not exists app.dong (
    snapshot_id bigint not null references app.dataset_snapshot(snapshot_id) on delete cascade,
    dong text not null,
    sgg_cd text not null,
    umd_nm text not null,
    gu_name text not null,
    primary key (snapshot_id, dong),
    check (dong = sgg_cd || '_' || umd_nm)
);

create table if not exists app.dong_index (
    snapshot_id bigint not null references app.dataset_snapshot(snapshot_id) on delete cascade,
    dong text not null,
    quarter text not null,
    log_index double precision not null,
    n_sales integer not null,
    n_sales_4q integer,
    eligible boolean not null,
    primary key (snapshot_id, dong, quarter),
    foreign key (snapshot_id, dong) references app.dong(snapshot_id, dong) on delete cascade
);

create table if not exists app.dong_feature (
    snapshot_id bigint not null references app.dataset_snapshot(snapshot_id) on delete cascade,
    dong text not null,
    as_of_quarter text not null,
    sale_n_all_4q integer,
    cancel_share_4q double precision,
    median_age_4q double precision,
    old30_share_4q double precision,
    sale_ppm2_med_4q double precision,
    rent_n_4q integer,
    jeonse_share_4q double precision,
    jeonse_ppm2_med_4q double precision,
    rz_designated_n integer,
    rz_committee_n integer,
    rz_association_n integer,
    rz_implementation_n integer,
    rz_management_n integer,
    rz_construction_n integer,
    rz_active_households integer,
    rz_events_4q integer,
    completed_hh_4q integer,
    completed_hh_8q integer,
    stock_hh integer,
    jeonse_ratio_4q double precision,
    completed_share_8q double precision,
    sale_n_log_change_4q double precision,
    rent_n_log_change_4q double precision,
    primary key (snapshot_id, dong, as_of_quarter),
    foreign key (snapshot_id, dong) references app.dong(snapshot_id, dong) on delete cascade
);

create table if not exists app.market_event (
    snapshot_id bigint not null references app.dataset_snapshot(snapshot_id) on delete cascade,
    event_id text not null,
    effective_date date not null,
    category text not null,
    direction text not null,
    label text not null,
    verified boolean not null,
    source text,
    primary key (snapshot_id, event_id)
);

create table if not exists app.event_summary (
    snapshot_id bigint not null references app.dataset_snapshot(snapshot_id) on delete cascade,
    event_id text not null,
    effective_date date not null,
    category text not null,
    label text not null,
    event_quarter text not null,
    base_quarter text not null,
    n_dongs integer,
    n_dongs_post integer,
    pre_change_4q double precision,
    post_change_4q double precision,
    post_median double precision,
    post_p10 double precision,
    post_p90 double precision,
    share_same_direction double precision,
    share_up double precision,
    pre_observable boolean,
    post_observable boolean,
    overlapping_events text,
    note text,
    primary key (snapshot_id, event_id),
    foreign key (snapshot_id, event_id) references app.market_event(snapshot_id, event_id) on delete cascade
);

create table if not exists app.event_dong_path (
    snapshot_id bigint not null references app.dataset_snapshot(snapshot_id) on delete cascade,
    event_id text not null,
    dong text not null,
    k integer not null,
    quarter text not null,
    rel_log_change double precision,
    primary key (snapshot_id, event_id, dong, k),
    foreign key (snapshot_id, dong) references app.dong(snapshot_id, dong) on delete cascade,
    foreign key (snapshot_id, event_id) references app.market_event(snapshot_id, event_id) on delete cascade
);

create table if not exists app.dong_prediction (
    snapshot_id bigint not null references app.dataset_snapshot(snapshot_id) on delete cascade,
    dong text not null,
    horizon_q integer not null,
    origin text not null,
    status text not null check (status in ('PREDICTED', 'INSUFFICIENT_SALES')),
    n_sales_4q integer,
    market_hat double precision,
    relative_hat double precision,
    gamma double precision,
    y_hat double precision,
    change_pct_est double precision,
    lower_pct double precision,
    upper_pct double precision,
    model_version text not null,
    primary key (snapshot_id, dong, horizon_q),
    foreign key (snapshot_id, dong) references app.dong(snapshot_id, dong) on delete cascade
);

create index if not exists dong_index_snapshot_dong_quarter_idx
    on app.dong_index (snapshot_id, dong, quarter);
create index if not exists event_dong_path_snapshot_event_k_idx
    on app.event_dong_path (snapshot_id, event_id, k);

create table if not exists app.trade_batch (
    batch_id bigserial primary key,
    kind text not null check (kind in ('sale', 'rent')),
    period_start text not null check (period_start ~ '^[0-9]{6}$'),
    period_end text not null check (period_end ~ '^[0-9]{6}$'),
    source_file text not null,
    source_sha256 text not null,
    row_count bigint not null check (row_count >= 0),
    loaded_at timestamptz not null default now(),
    is_active boolean not null default false,
    note text
);
create unique index if not exists trade_batch_one_active_per_kind
    on app.trade_batch (kind) where is_active;

create table if not exists app.trade_sale (
    batch_id bigint not null references app.trade_batch(batch_id) on delete cascade,
    row_no bigint not null,
    apt_seq text,
    apt_nm text,
    apt_dong text,
    umd_nm text,
    jibun text,
    bonbun text,
    bubun text,
    road_nm text,
    road_nm_bonbun text,
    road_nm_bubun text,
    build_year integer,
    exclu_use_ar double precision,
    floor integer,
    deal_year integer,
    deal_month integer,
    deal_day integer,
    sgg_cd text,
    deal_amount text,
    cdeal_type text,
    deal_ym text,
    gu text,
    is_cancelled boolean,
    deal_amount_manwon numeric,
    primary key (batch_id, row_no)
);
create index if not exists trade_sale_batch_apt_ym_idx
    on app.trade_sale (batch_id, apt_seq, deal_ym);
create index if not exists trade_sale_batch_dong_ym_idx
    on app.trade_sale (batch_id, sgg_cd, umd_nm, deal_ym);

create table if not exists app.trade_rent (
    batch_id bigint not null references app.trade_batch(batch_id) on delete cascade,
    row_no bigint not null,
    apt_seq text,
    apt_nm text,
    umd_nm text,
    jibun text,
    road_nm text,
    road_nm_bonbun text,
    road_nm_bubun text,
    build_year integer,
    exclu_use_ar double precision,
    floor integer,
    deal_year integer,
    deal_month integer,
    deal_day integer,
    sgg_cd text,
    deposit text,
    monthly_rent text,
    deal_ym text,
    gu text,
    deposit_manwon numeric,
    monthly_rent_manwon numeric,
    is_jeonse boolean,
    primary key (batch_id, row_no)
);
create index if not exists trade_rent_batch_apt_ym_idx
    on app.trade_rent (batch_id, apt_seq, deal_ym);
create index if not exists trade_rent_batch_dong_ym_idx
    on app.trade_rent (batch_id, sgg_cd, umd_nm, deal_ym);

grant select on app.dong, app.dong_index, app.dong_feature, app.market_event,
    app.event_summary, app.event_dong_path, app.dong_prediction, app.trade_batch,
    app.trade_sale, app.trade_rent to boomingup_readonly;
grant select, insert, update, delete on app.dong, app.dong_index, app.dong_feature,
    app.market_event, app.event_summary, app.event_dong_path, app.dong_prediction,
    app.trade_batch, app.trade_sale, app.trade_rent to boomingup_loader;
grant usage, select on sequence app.trade_batch_batch_id_seq to boomingup_loader;

commit;
