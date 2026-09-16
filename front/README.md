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

개발 서버를 켜 둔 채로 build를 돌리면 같은 `.next`를 덮어써서, 새로고침할 때
`__webpack_modules__[moduleId] is not a function`이 난다. 이럴 때는 build만 따로 둔다.

```bash
NEXT_DIST_DIR=.next-build npm run build
```

이미 났다면 개발 서버를 끄고 `rm -rf front/.next` 뒤 다시 켜면 된다.

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

지도는 두 단계다(결정 43). 넓게 보면 자치구 경계와 자치구 이름만 나오고, 자치구를 누르면
그 자치구로 확대되면서 동 경계와 동 이름이 나온다. 갈리는 기준은 Kakao 확대 수준 7이라
손으로 확대해도 같은 규칙이 적용된다. 자치구를 누르면 자치구 필터가 걸려 왼쪽 목록도 함께 좁혀진다.

동 대표 좌표는 그대로 단지 좌표 평균을 쓰고(결정 21) 그 위에 경계를 덧그린다. 경계는 동을 고르는
넓은 클릭 영역이자 위치를 알아보는 밑그림이고, 예측값으로 색을 칠하지는 않는다(결정 41).
경계 파일은 아래 두 스크립트로 만들어 commit한다. 배포는 저장소 파일을 그대로 쓰므로
commit하지 않으면 배포 화면에 경계가 없다.

```bash
python models/index/52.build_dong_boundary.py      # output/52.1.seoul_bjd_boundary.geojson
python models/index/53.export_front_boundary.py    # front/public/data/{dong,gu}-boundary.geojson
```

두 파일 모두 법정동 경계에서 나온다(결정 45). 자치구 경계는 53이 자치구 안쪽 선을 지워
합친 것이라 동 경계와 선이 정확히 겹친다.

원천 SHP가 없으면 52 대신 `app.dong_boundary`에서 52.1을 내려받으면 된다. SQL은
`docs/data-sources.md` §6에 있다.

경계 원천 SHP는 `output/raw/boundary/emd_20230729/`에 있어야 한다(`docs/data-sources.md` §6).
파일이 없으면 지도는 경계 없이 마커만 그리므로, 아직 만들지 않은 환경에서도 화면은 그대로 돈다.
경계가 그려질 때는 출처 표기가 지도 아래에 함께 뜬다(결정 40).
