-- 법정동(읍면동) 경계 테이블입니다. 관리자 권한으로 한 번 적용합니다.

begin;

create table app.dong_boundary (
    snapshot_id bigint not null references app.dataset_snapshot(snapshot_id) on delete cascade,
    dong text not null,
    emd_cd text not null,
    sgg_cd text not null,
    umd_nm text not null,
    eng_nm text,
    in_index boolean not null,
    geometry jsonb not null, -- GeoJSON geometry 객체를 그대로 저장합니다.
    min_lng double precision not null,
    min_lat double precision not null,
    max_lng double precision not null,
    max_lat double precision not null,
    centroid_lng double precision not null,
    centroid_lat double precision not null,
    source text not null,
    primary key (snapshot_id, dong),
    check (dong = sgg_cd || '_' || umd_nm),
    check (((geometry->>'type') in ('Polygon', 'MultiPolygon')) is true)
);

grant select on app.dong_boundary to boomingup_readonly;
grant select, insert, update, delete on app.dong_boundary to boomingup_loader;

commit;
