# Boomingup DB 적재

`001_boomingup_tables.sql`은 신규 정제 테이블과 거래 원장 테이블만 만들며 기존 테이블을 변경하지 않습니다. 이어서 `002_dong_boundary.sql`로 법정동 경계 테이블을, `003_dong_index_se.sql`로 동 지수 추정오차 컬럼을, `004_dong_support.sql`로 판단 보조 화면이 읽는 `app.dong_support` 테이블을 적용합니다. 각 파일은 `begin`/`commit`으로 전체 DDL을 하나의 transaction으로 적용합니다. 관리자 권한으로 Railway의 SQL 실행 화면에서 번호순으로 먼저 적용하고, 다음 적재 전에는 읽기 전용 `check_schema.sql`로 신규 테이블의 schema를 확인합니다. 적재 role에는 DDL 권한이 필요 없습니다.

법정동 경계는 GIS Developer의 행정구역(읍면동) 2023-07 자료를 사용하며, 원본은 도로명주소 DB입니다. 화면·문서 출처 표기는 `행정구역 경계: GIS Developer(gisdeveloper.co.kr), 원본 도로명주소 DB`를 사용합니다.

정제 snapshot 적재는 기본적으로 rollback하는 dry-run입니다. 판단 보조 산출물 `output/69.1.dong_support.txt`도 다른 정제 테이블과 같은 snapshot에 함께 들어갑니다.

```bash
.venv/bin/python data/db/50.load_db.py
.venv/bin/python data/db/50.load_db.py --as-of 2026-08-31 --note "2026년 8월 정제 데이터" --commit
```

`--commit`은 기존 active snapshot의 기존 데이터 테이블 8개(`complex`, `complex_metrics`, `horizon_profile`, `price_cell`, `price_series`, `estimate`, `comparable`, `regulation_summary`)를 새 snapshot으로 복사하고, 정제 테이블을 적재·검증한 뒤에만 active를 전환합니다. `share`는 `snapshot_id`가 없어 snapshot 복사 대상이 아니며 거래 원장도 별도 batch로 관리합니다. 예측 파일이 준비되면 `--predictions PATH`에 탭 구분 파일을 지정합니다.

거래 원장은 kind별 batch로 관리합니다. 기본 dry-run은 각 파일 앞 10,000행을 적재한 뒤 rollback합니다.

```bash
.venv/bin/python data/db/51.load_trades.py
.venv/bin/python data/db/51.load_trades.py --kind sale --commit
.venv/bin/python data/db/51.load_trades.py --kind rent --commit
```

`--commit` 시에는 해당 kind의 새 batch만 active로 남기고 이전 batch와 그 행을 cascade 삭제합니다. URL은 `.env` 또는 환경변수의 `DATABASE_LOADER_URL`에만 두며, 스크립트는 URL을 출력하지 않습니다.

일반 dry-run은 최종 행을 rollback하지만 실제 DB에 연결해 INSERT/COPY를 수행합니다. 따라서 sequence 증가, WAL, lock 및 vacuum 부담이 생길 수 있습니다. DB 접속 없이 파일만 검증하려면 `--validate-only`를 사용합니다.

```bash
.venv/bin/python data/db/50.load_db.py --validate-only
.venv/bin/python data/db/51.load_trades.py --validate-only --kind sale
```

DB 없이 원천 형식과 변환을 점검하려면 다음을 실행합니다.

```bash
.venv/bin/python data/db/test_load_db.py
```
