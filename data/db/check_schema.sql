-- 001_boomingup_tables.sql 및 002_dong_boundary.sql 적용 뒤 관리자/readonly 연결에서 실행합니다.
-- 변경 없이 신규 테이블의 컬럼·PK·FK·CHECK 기대값 충족 여부를 반환합니다.

with expected_columns(table_name, column_name, data_type) as (
    values
        ('dong', 'snapshot_id', 'bigint'), ('dong', 'dong', 'text'), ('dong', 'sgg_cd', 'text'), ('dong', 'umd_nm', 'text'), ('dong', 'gu_name', 'text'),
        ('dong_index', 'snapshot_id', 'bigint'), ('dong_index', 'dong', 'text'), ('dong_index', 'quarter', 'text'), ('dong_index', 'log_index', 'double precision'), ('dong_index', 'n_sales', 'integer'), ('dong_index', 'n_sales_4q', 'integer'), ('dong_index', 'eligible', 'boolean'),
        ('dong_feature', 'snapshot_id', 'bigint'), ('dong_feature', 'dong', 'text'), ('dong_feature', 'as_of_quarter', 'text'), ('dong_feature', 'sale_n_all_4q', 'integer'), ('dong_feature', 'cancel_share_4q', 'double precision'), ('dong_feature', 'median_age_4q', 'double precision'), ('dong_feature', 'old30_share_4q', 'double precision'), ('dong_feature', 'sale_ppm2_med_4q', 'double precision'), ('dong_feature', 'rent_n_4q', 'integer'), ('dong_feature', 'jeonse_share_4q', 'double precision'), ('dong_feature', 'jeonse_ppm2_med_4q', 'double precision'), ('dong_feature', 'rz_designated_n', 'integer'), ('dong_feature', 'rz_committee_n', 'integer'), ('dong_feature', 'rz_association_n', 'integer'), ('dong_feature', 'rz_implementation_n', 'integer'), ('dong_feature', 'rz_management_n', 'integer'), ('dong_feature', 'rz_construction_n', 'integer'), ('dong_feature', 'rz_active_households', 'integer'), ('dong_feature', 'rz_events_4q', 'integer'), ('dong_feature', 'completed_hh_4q', 'integer'), ('dong_feature', 'completed_hh_8q', 'integer'), ('dong_feature', 'stock_hh', 'integer'), ('dong_feature', 'jeonse_ratio_4q', 'double precision'), ('dong_feature', 'completed_share_8q', 'double precision'), ('dong_feature', 'sale_n_log_change_4q', 'double precision'), ('dong_feature', 'rent_n_log_change_4q', 'double precision'),
        ('market_event', 'snapshot_id', 'bigint'), ('market_event', 'event_id', 'text'), ('market_event', 'effective_date', 'date'), ('market_event', 'category', 'text'), ('market_event', 'direction', 'text'), ('market_event', 'label', 'text'), ('market_event', 'verified', 'boolean'), ('market_event', 'source', 'text'),
        ('event_summary', 'snapshot_id', 'bigint'), ('event_summary', 'event_id', 'text'), ('event_summary', 'effective_date', 'date'), ('event_summary', 'category', 'text'), ('event_summary', 'label', 'text'), ('event_summary', 'event_quarter', 'text'), ('event_summary', 'base_quarter', 'text'), ('event_summary', 'n_dongs', 'integer'), ('event_summary', 'n_dongs_post', 'integer'), ('event_summary', 'pre_change_4q', 'double precision'), ('event_summary', 'post_change_4q', 'double precision'), ('event_summary', 'post_median', 'double precision'), ('event_summary', 'post_p10', 'double precision'), ('event_summary', 'post_p90', 'double precision'), ('event_summary', 'share_same_direction', 'double precision'), ('event_summary', 'share_up', 'double precision'), ('event_summary', 'pre_observable', 'boolean'), ('event_summary', 'post_observable', 'boolean'), ('event_summary', 'overlapping_events', 'text'), ('event_summary', 'note', 'text'),
        ('event_dong_path', 'snapshot_id', 'bigint'), ('event_dong_path', 'event_id', 'text'), ('event_dong_path', 'dong', 'text'), ('event_dong_path', 'k', 'integer'), ('event_dong_path', 'quarter', 'text'), ('event_dong_path', 'rel_log_change', 'double precision'),
        ('dong_prediction', 'snapshot_id', 'bigint'), ('dong_prediction', 'dong', 'text'), ('dong_prediction', 'horizon_q', 'integer'), ('dong_prediction', 'origin', 'text'), ('dong_prediction', 'status', 'text'), ('dong_prediction', 'n_sales_4q', 'integer'), ('dong_prediction', 'market_hat', 'double precision'), ('dong_prediction', 'relative_hat', 'double precision'), ('dong_prediction', 'gamma', 'double precision'), ('dong_prediction', 'y_hat', 'double precision'), ('dong_prediction', 'change_pct_est', 'double precision'), ('dong_prediction', 'lower_pct', 'double precision'), ('dong_prediction', 'upper_pct', 'double precision'), ('dong_prediction', 'model_version', 'text'),
        ('dong_boundary', 'snapshot_id', 'bigint'), ('dong_boundary', 'dong', 'text'), ('dong_boundary', 'emd_cd', 'text'), ('dong_boundary', 'sgg_cd', 'text'), ('dong_boundary', 'umd_nm', 'text'), ('dong_boundary', 'eng_nm', 'text'), ('dong_boundary', 'in_index', 'boolean'), ('dong_boundary', 'geometry', 'jsonb'), ('dong_boundary', 'min_lng', 'double precision'), ('dong_boundary', 'min_lat', 'double precision'), ('dong_boundary', 'max_lng', 'double precision'), ('dong_boundary', 'max_lat', 'double precision'), ('dong_boundary', 'centroid_lng', 'double precision'), ('dong_boundary', 'centroid_lat', 'double precision'), ('dong_boundary', 'source', 'text'),
        ('trade_batch', 'batch_id', 'bigint'), ('trade_batch', 'kind', 'text'), ('trade_batch', 'period_start', 'text'), ('trade_batch', 'period_end', 'text'), ('trade_batch', 'source_file', 'text'), ('trade_batch', 'source_sha256', 'text'), ('trade_batch', 'row_count', 'bigint'), ('trade_batch', 'loaded_at', 'timestamp with time zone'), ('trade_batch', 'is_active', 'boolean'), ('trade_batch', 'note', 'text'),
        ('trade_sale', 'batch_id', 'bigint'), ('trade_sale', 'row_no', 'bigint'), ('trade_sale', 'apt_seq', 'text'), ('trade_sale', 'apt_nm', 'text'), ('trade_sale', 'apt_dong', 'text'), ('trade_sale', 'umd_nm', 'text'), ('trade_sale', 'jibun', 'text'), ('trade_sale', 'bonbun', 'text'), ('trade_sale', 'bubun', 'text'), ('trade_sale', 'road_nm', 'text'), ('trade_sale', 'road_nm_bonbun', 'text'), ('trade_sale', 'road_nm_bubun', 'text'), ('trade_sale', 'build_year', 'integer'), ('trade_sale', 'exclu_use_ar', 'double precision'), ('trade_sale', 'floor', 'integer'), ('trade_sale', 'deal_year', 'integer'), ('trade_sale', 'deal_month', 'integer'), ('trade_sale', 'deal_day', 'integer'), ('trade_sale', 'sgg_cd', 'text'), ('trade_sale', 'deal_amount', 'text'), ('trade_sale', 'cdeal_type', 'text'), ('trade_sale', 'deal_ym', 'text'), ('trade_sale', 'gu', 'text'), ('trade_sale', 'is_cancelled', 'boolean'), ('trade_sale', 'deal_amount_manwon', 'numeric'),
        ('trade_rent', 'batch_id', 'bigint'), ('trade_rent', 'row_no', 'bigint'), ('trade_rent', 'apt_seq', 'text'), ('trade_rent', 'apt_nm', 'text'), ('trade_rent', 'umd_nm', 'text'), ('trade_rent', 'jibun', 'text'), ('trade_rent', 'road_nm', 'text'), ('trade_rent', 'road_nm_bonbun', 'text'), ('trade_rent', 'road_nm_bubun', 'text'), ('trade_rent', 'build_year', 'integer'), ('trade_rent', 'exclu_use_ar', 'double precision'), ('trade_rent', 'floor', 'integer'), ('trade_rent', 'deal_year', 'integer'), ('trade_rent', 'deal_month', 'integer'), ('trade_rent', 'deal_day', 'integer'), ('trade_rent', 'sgg_cd', 'text'), ('trade_rent', 'deposit', 'text'), ('trade_rent', 'monthly_rent', 'text'), ('trade_rent', 'deal_ym', 'text'), ('trade_rent', 'gu', 'text'), ('trade_rent', 'deposit_manwon', 'numeric'), ('trade_rent', 'monthly_rent_manwon', 'numeric'), ('trade_rent', 'is_jeonse', 'boolean')
), actual_columns as (
    select c.relname as table_name, a.attname as column_name, format_type(a.atttypid, a.atttypmod) as data_type, a.attnotnull as not_null
    from pg_class c join pg_namespace n on n.oid = c.relnamespace join pg_attribute a on a.attrelid = c.oid
    where n.nspname = 'app' and c.relname in (select distinct table_name from expected_columns)
      and a.attnum > 0 and not a.attisdropped
), expected_not_null(table_name, column_name) as (
    values
        ('dong', 'snapshot_id'), ('dong', 'dong'), ('dong', 'sgg_cd'), ('dong', 'umd_nm'), ('dong', 'gu_name'),
        ('dong_index', 'snapshot_id'), ('dong_index', 'dong'), ('dong_index', 'quarter'), ('dong_index', 'log_index'), ('dong_index', 'n_sales'), ('dong_index', 'eligible'),
        ('dong_feature', 'snapshot_id'), ('dong_feature', 'dong'), ('dong_feature', 'as_of_quarter'),
        ('market_event', 'snapshot_id'), ('market_event', 'event_id'), ('market_event', 'effective_date'), ('market_event', 'category'), ('market_event', 'direction'), ('market_event', 'label'), ('market_event', 'verified'),
        ('event_summary', 'snapshot_id'), ('event_summary', 'event_id'), ('event_summary', 'effective_date'), ('event_summary', 'category'), ('event_summary', 'label'), ('event_summary', 'event_quarter'), ('event_summary', 'base_quarter'),
        ('event_dong_path', 'snapshot_id'), ('event_dong_path', 'event_id'), ('event_dong_path', 'dong'), ('event_dong_path', 'k'), ('event_dong_path', 'quarter'),
        ('dong_prediction', 'snapshot_id'), ('dong_prediction', 'dong'), ('dong_prediction', 'horizon_q'), ('dong_prediction', 'origin'), ('dong_prediction', 'status'), ('dong_prediction', 'model_version'),
        ('dong_boundary', 'snapshot_id'), ('dong_boundary', 'dong'), ('dong_boundary', 'emd_cd'), ('dong_boundary', 'sgg_cd'), ('dong_boundary', 'umd_nm'), ('dong_boundary', 'in_index'), ('dong_boundary', 'geometry'), ('dong_boundary', 'min_lng'), ('dong_boundary', 'min_lat'), ('dong_boundary', 'max_lng'), ('dong_boundary', 'max_lat'), ('dong_boundary', 'centroid_lng'), ('dong_boundary', 'centroid_lat'), ('dong_boundary', 'source'),
        ('trade_batch', 'batch_id'), ('trade_batch', 'kind'), ('trade_batch', 'period_start'), ('trade_batch', 'period_end'), ('trade_batch', 'source_file'), ('trade_batch', 'source_sha256'), ('trade_batch', 'row_count'), ('trade_batch', 'loaded_at'), ('trade_batch', 'is_active'),
        ('trade_sale', 'batch_id'), ('trade_sale', 'row_no'),
        ('trade_rent', 'batch_id'), ('trade_rent', 'row_no')
), expected_column_definitions as (
    select e.table_name, e.column_name, e.data_type, (n.column_name is not null) as not_null
    from expected_columns e left join expected_not_null n using (table_name, column_name)
), expected_pk(table_name, columns) as (
    values ('dong', 'snapshot_id,dong'), ('dong_index', 'snapshot_id,dong,quarter'), ('dong_feature', 'snapshot_id,dong,as_of_quarter'), ('market_event', 'snapshot_id,event_id'), ('event_summary', 'snapshot_id,event_id'), ('event_dong_path', 'snapshot_id,event_id,dong,k'), ('dong_prediction', 'snapshot_id,dong,horizon_q'), ('dong_boundary', 'snapshot_id,dong'), ('trade_batch', 'batch_id'), ('trade_sale', 'batch_id,row_no'), ('trade_rent', 'batch_id,row_no')
), actual_pk as (
    select c.relname as table_name, string_agg(a.attname, ',' order by k.ordinality) as columns
    from pg_constraint con join pg_class c on c.oid = con.conrelid join pg_namespace n on n.oid = c.relnamespace
    join unnest(con.conkey) with ordinality k(attnum, ordinality) on true join pg_attribute a on a.attrelid = c.oid and a.attnum = k.attnum
    where n.nspname = 'app' and c.relname in (select distinct table_name from expected_columns) and con.contype = 'p' group by c.relname
), expected_fk(table_name, columns, ref_table, ref_columns) as (
    values
        ('dong', 'snapshot_id', 'dataset_snapshot', 'snapshot_id'),
        ('dong_index', 'snapshot_id', 'dataset_snapshot', 'snapshot_id'),
        ('dong_index', 'snapshot_id,dong', 'dong', 'snapshot_id,dong'),
        ('dong_feature', 'snapshot_id', 'dataset_snapshot', 'snapshot_id'),
        ('dong_feature', 'snapshot_id,dong', 'dong', 'snapshot_id,dong'),
        ('market_event', 'snapshot_id', 'dataset_snapshot', 'snapshot_id'),
        ('event_summary', 'snapshot_id', 'dataset_snapshot', 'snapshot_id'),
        ('event_summary', 'snapshot_id,event_id', 'market_event', 'snapshot_id,event_id'),
        ('event_dong_path', 'snapshot_id', 'dataset_snapshot', 'snapshot_id'),
        ('event_dong_path', 'snapshot_id,dong', 'dong', 'snapshot_id,dong'),
        ('event_dong_path', 'snapshot_id,event_id', 'market_event', 'snapshot_id,event_id'),
        ('dong_prediction', 'snapshot_id', 'dataset_snapshot', 'snapshot_id'),
        ('dong_prediction', 'snapshot_id,dong', 'dong', 'snapshot_id,dong'),
        ('dong_boundary', 'snapshot_id', 'dataset_snapshot', 'snapshot_id'),
        ('trade_sale', 'batch_id', 'trade_batch', 'batch_id'),
        ('trade_rent', 'batch_id', 'trade_batch', 'batch_id')
), actual_fk as (
    select c.relname as table_name, string_agg(a.attname, ',' order by k.ordinality) as columns, rc.relname as ref_table, string_agg(ra.attname, ',' order by k.ordinality) as ref_columns, con.confdeltype as delete_action
    from pg_constraint con join pg_class c on c.oid = con.conrelid join pg_namespace n on n.oid = c.relnamespace join pg_class rc on rc.oid = con.confrelid
    join unnest(con.conkey) with ordinality k(attnum, ordinality) on true join pg_attribute a on a.attrelid = c.oid and a.attnum = k.attnum
    join unnest(con.confkey) with ordinality rk(attnum, ordinality) on rk.ordinality = k.ordinality join pg_attribute ra on ra.attrelid = rc.oid and ra.attnum = rk.attnum
    where n.nspname = 'app' and c.relname in (select distinct table_name from expected_columns) and con.contype = 'f' group by c.relname, rc.relname, con.oid, con.confdeltype
), expected_checks(table_name, definition) as (
    -- 001의 정의는 2026-09-15 운영 DB(readonly)의 pg_get_constraintdef() 출력과 6개 모두 일치함을 확인한 정규형입니다.
    -- dong_boundary는 아직 미적용이므로 002 DDL의 PostgreSQL 정규형을 추정했습니다.
    values
        ('dong', 'CHECK ((dong = ((sgg_cd || ''_''::text) || umd_nm)))'),
        ('dong_prediction', 'CHECK ((status = ANY (ARRAY[''PREDICTED''::text, ''INSUFFICIENT_SALES''::text])))'),
        ('dong_boundary', 'CHECK ((dong = ((sgg_cd || ''_''::text) || umd_nm)))'),
        ('dong_boundary', 'CHECK ((((geometry ->> ''type''::text) = ANY (ARRAY[''Polygon''::text, ''MultiPolygon''::text])) IS TRUE))'),
        ('trade_batch', 'CHECK ((kind = ANY (ARRAY[''sale''::text, ''rent''::text])))'),
        ('trade_batch', 'CHECK ((period_start ~ ''^[0-9]{6}$''::text))'),
        ('trade_batch', 'CHECK ((period_end ~ ''^[0-9]{6}$''::text))'),
        ('trade_batch', 'CHECK ((row_count >= 0))')
), actual_checks as (
    select c.relname as table_name, regexp_replace(pg_get_constraintdef(con.oid), '\\s+', ' ', 'g') as definition
    from pg_constraint con join pg_class c on c.oid = con.conrelid join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'app' and c.relname in (select distinct table_name from expected_columns) and con.contype = 'c'
)
select 'column' as check_kind, e.table_name, e.column_name as expected, e.data_type || case when e.not_null then ', NOT NULL' else ', nullable' end as expected_detail, coalesce(a.data_type || case when a.not_null then ', NOT NULL' else ', nullable' end, '<missing>') as actual_detail, (a.data_type = e.data_type and a.not_null = e.not_null) as matches from expected_column_definitions e left join actual_columns a using (table_name, column_name)
union all select 'unexpected_column', a.table_name, a.column_name, '<none>', a.data_type || case when a.not_null then ', NOT NULL' else ', nullable' end, false from actual_columns a left join expected_column_definitions e using (table_name, column_name) where e.column_name is null
union all select 'primary_key', e.table_name, e.columns, e.columns, coalesce(a.columns, '<missing>'), (a.columns = e.columns) from expected_pk e left join actual_pk a using (table_name)
union all select 'foreign_key', e.table_name, e.columns || ' -> ' || e.ref_table, e.ref_columns || ' on delete cascade', coalesce(a.ref_columns || ' on delete ' || case a.delete_action when 'c' then 'cascade' else a.delete_action::text end, '<missing>'), (a.columns = e.columns and a.ref_table = e.ref_table and a.ref_columns = e.ref_columns and a.delete_action = 'c') from expected_fk e left join actual_fk a on a.table_name = e.table_name and a.columns = e.columns and a.ref_table = e.ref_table
union all select 'unexpected_foreign_key', a.table_name, a.columns || ' -> ' || a.ref_table, '<none>', a.ref_columns || ' on delete ' || case a.delete_action when 'c' then 'cascade' else a.delete_action::text end, false from actual_fk a left join expected_fk e on e.table_name = a.table_name and e.columns = a.columns and e.ref_table = a.ref_table and e.ref_columns = a.ref_columns where e.table_name is null
union all select 'check', e.table_name, e.definition, e.definition, coalesce(a.definition, '<missing>'), (a.definition = e.definition) from expected_checks e left join actual_checks a using (table_name, definition)
union all select 'unexpected_check', a.table_name, a.definition, '<none>', a.definition, false from actual_checks a left join expected_checks e using (table_name, definition) where e.table_name is null
order by check_kind, table_name, expected;
