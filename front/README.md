# front

서울 법정동 단위의 추정 변화율과 관측 정보를 보여주는 Next.js 앱이다.

## 실행

```bash
npm install
npm run dev      # 개발 서버 (http://localhost:3000)
npm run typecheck
npm run test     # 필터·파생 로직 단위 테스트
npm run build
```

## 데이터

Railway Postgres의 active snapshot을 먼저 읽고, 접속이 없거나 조회가 실패하면
`public/data/`의 샘플 JSON으로 폴백한다(결정 19). 폴백 중에는 화면 상단에 안내 문구가 뜨고,
API 응답의 `source`가 `sample`이 된다.

DB URL과 Kakao 키는 저장소 루트 `.env`에서 읽는다. `front/.env.local`을 따로 만들지 않아도 된다.

```text
DATABASE_READONLY_URL=postgresql://...   # 읽기 전용 계정만 쓴다
KAKAO_JS_KEY=...                         # 없으면 지도는 좌표 미리보기로 폴백한다
```

접속 절차는 `docs/railway-postgres-onboarding.md`를 따른다.

### API

| 경로 | 내용 |
|---|---|
| `GET /api/meta` | 기준 분기, 데이터 기간, 예측 기간, 구간 coverage, 규제 기준일 |
| `GET /api/dongs` | 동 목록, 지역 태그, 동 대표 좌표 |
| `GET /api/dong/{dong_id}?asOf=2026Q2` | 예측, 사실정보, 비교, 단지 목록 |

첫 화면은 서버에서 목록과 메타를 읽어 내려보내고, 상세는 동을 선택할 때 API로 가져온다(결정 20).

### 읽는 테이블

| 테이블 | 쓰임 |
|---|---|
| `app.dong`, `app.dong_index` | 동 목록, 매매 건수, 예측 대상 여부, 최근 4분기 변화율 비교 |
| `app.dong_feature` | 전세 비중, 정비사업 구역 수, 입주 세대, 지역 태그 |
| `app.dong_prediction` | 추정 변화율과 추정 구간 (아직 비어 있음) |
| `app.trade_sale`, `app.complex` | 단지 목록, 최근 매매, 동 대표 좌표 |
| `app.regulation_summary` | 아파트 토지거래허가구역 지정 여부와 기준일 |

`snapshot_id`는 코드에 박지 않고 항상 `dataset_snapshot.is_active`를 join해서 읽는다.

`app.dong_prediction`이 비어 있는 동안에는 모든 동이 `INSUFFICIENT_SALES` 또는 `NOT_SERVED`로
표시된다(결정 22). 예측이 적재되면 같은 경로로 값이 채워진다.

## 지도

법정동 경계 GeoJSON 대신 최근 매매가 있는 단지 좌표의 평균을 동 대표 좌표로 쓴다(결정 21).
Kakao SDK는 클라이언트에서만 불러오고, 키가 없거나 로딩이 실패하면 좌표 미리보기로 폴백한다.
실제 지도를 확인하려면 Kakao 개발자 콘솔에 실행 도메인(`http://localhost:3000` 등)을 등록해야 한다.
