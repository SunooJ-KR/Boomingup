# BoomingUp Railway Postgres 팀 공유 가이드

> 작성: 2026-09-15
> 검증: 2026-09-15, `DATABASE_READONLY_URL`로 실제 DB에 접속해 아래 수치와 명령을 모두 확인했다.
> 목적: 팀원이 각자 로컬 PC에서 같은 Railway Postgres 데이터를 읽기 위한 공통 절차를 정리한다.

## 1. 현재 적재 상태

Railway Postgres에 정제 데이터가 적재되어 있고, `snapshot_id = 1`이 active 상태다.

| 항목 | 값 |
|---|---|
| active `snapshot_id` | 1 |
| `as_of` | 2026-08-16 |
| 적재 시각 | 2026-09-15 03:50 (UTC) |

`app` 스키마의 테이블별 행 수는 다음과 같다.

| 테이블 | 행 수 |
|---|---|
| `complex` | 9,160 |
| `complex_metrics` | 9,160 |
| `horizon_profile` | 19,349 |
| `price_cell` | 40,848 |
| `price_series` | 137,405 |
| `estimate` | 5,207 |
| `comparable` | 120,271 |
| `regulation_summary` | 1 |
| `share` | 0 |

`share`는 공유 링크 정보를 담는 테이블이라 스냅샷 적재 대상이 아니고, 서비스에서 링크를 만들 때 채워진다.

DB에는 원천 데이터 전체가 아니라 서비스와 모델이 공통으로 읽는 정제 테이블만 들어간다. 원천 데이터, 대용량 산출물, 재생성 가능한 payload는 Git에 올리지 않고 DB 또는 공유 스토리지로 관리한다.

## 2. 접속 권한 원칙

DB URL은 비밀번호를 포함하므로 Git, 문서, PR 본문, 메신저 공개 채널에 붙이지 않는다.

| URL | 사용자 | 용도 | 공유 대상 |
|---|---|---|---|
| `DATABASE_PUBLIC_URL` | Railway 기본 관리자 | 스키마 적용, role 관리 | 인프라 담당자만 |
| `DATABASE_LOADER_URL` | `boomingup_loader` | 배치 산출물 적재 | 데이터 적재 담당자만 |
| `DATABASE_READONLY_URL` | `boomingup_readonly` | 로컬 개발, 모델/API 조회 | 일반 팀원 |

일반 개발자는 `DATABASE_READONLY_URL`만 사용한다. 이 계정은 `app` 스키마 테이블에 `SELECT` 권한만 있고 `INSERT`, `UPDATE`, 스키마 `CREATE` 권한이 회수되어 있어서, 세션 설정을 바꿔도 쓰기가 되지 않는다.

## 3. 팀원 로컬 설정

PostgreSQL client가 설치되어 있어야 한다.

```powershell
psql --version
```

프로젝트 루트에 `.env`를 만들고, 본인 역할에 필요한 URL만 넣는다.

```text
DATABASE_READONLY_URL=postgresql://...
```

데이터 적재 담당자와 인프라 담당자만 `DATABASE_LOADER_URL`, `DATABASE_PUBLIC_URL`을 추가로 받는다.

`.env`는 `.gitignore` 대상이다. 절대 커밋하지 않는다.

## 4. 읽기 전용 접속 확인

팀원이 DB 접근을 받으면 먼저 아래 명령으로 read-only 계정인지 확인한다.

```powershell
$line = Get-Content -Encoding UTF8 .env | Where-Object { $_ -match '^DATABASE_READONLY_URL=' } | Select-Object -First 1
if (-not $line) { throw '.env에 DATABASE_READONLY_URL이 없습니다.' }
$dbUrl = $line.Substring('DATABASE_READONLY_URL='.Length).Trim().Trim('"')
psql $dbUrl -v ON_ERROR_STOP=1 -c "select current_user, current_setting('transaction_read_only');"
```

기대 결과:

```text
current_user = boomingup_readonly
transaction_read_only = on
```

쓰기 권한이 실제로 없는지 확인한다.

```powershell
psql $dbUrl -v ON_ERROR_STOP=1 -c "select has_table_privilege('app.complex','SELECT') as sel, has_table_privilege('app.complex','INSERT') as ins;"
```

기대 결과는 `sel = t`, `ins = f`다.

active snapshot의 단지 수 확인:

```powershell
psql $dbUrl -v ON_ERROR_STOP=1 -c "select ds.snapshot_id, ds.as_of, count(*) as complex_rows from app.dataset_snapshot ds join app.complex c on c.snapshot_id = ds.snapshot_id where ds.is_active group by ds.snapshot_id, ds.as_of;"
```

기대 결과:

```text
snapshot_id = 1
as_of = 2026-08-16
complex_rows = 9160
```

## 5. 앱과 모델에서 읽는 방법

항상 active snapshot만 조회한다. `snapshot_id`를 숫자로 직접 박지 않고 `dataset_snapshot`을 join해서 가져와야, 나중에 snapshot이 교체돼도 코드를 고칠 필요가 없다.

```sql
select c.*
from app.dataset_snapshot ds
join app.complex c on c.snapshot_id = ds.snapshot_id
where ds.is_active
  and c.apt_seq = '11110-100';
```

가격 셀 예시:

```sql
select pc.*
from app.dataset_snapshot ds
join app.price_cell pc on pc.snapshot_id = ds.snapshot_id
where ds.is_active
  and pc.apt_seq = '11110-2203'
order by pc.area_type, pc.floor_band;
```

모든 단지에 `price_cell`이 있는 것은 아니다. 거래 이력이 없는 단지는 결과가 비어 있을 수 있으니 호출하는 쪽에서 빈 결과를 처리한다.

API나 모델 코드는 `DATABASE_READONLY_URL`만 사용한다. 즉석 계산 결과는 DB에 저장하지 않고 응답으로만 반환한다.

## 6. 운영 규칙

- Git에는 코드, 문서, 스키마, 작은 fixture/샘플 데이터만 올린다.
- DB 비밀번호가 들어간 URL은 문서와 PR에 쓰지 않는다.
- 일반 팀원에게는 read-only URL만 공유한다.
- 운영 DB를 부분 update로 직접 수정하지 않는다. 정제 산출물을 다시 만들고 새 snapshot으로 통째 교체한다.
- 적재 스크립트와 스키마 정의는 아직 이 저장소에 없다. 옮겨온 뒤에 적재 절차를 이 문서에 다시 추가한다.
