# front

서울 법정동 단위의 추정 변화율과 관측 정보를 보여주는 Next.js 앱이다.

## 실행

```bash
npm install
npm run dev      # 개발 서버 (http://localhost:3000)
npm run typecheck
npm run test     # 필터 로직 단위 테스트
npm run build
```

## 데이터

지금은 `public/data/`의 샘플 JSON을 그대로 import한다.

| 파일 | 내용 |
|---|---|
| `public/data/meta.json` | 기준 분기, 데이터 기간, 예측 기간, 구간 coverage |
| `public/data/dongs.json` | 동 목록과 요약 (검색·필터·목록용) |
| `public/data/dong-details.json` | `dong_id`별 상세 (예측, 사실정보, 비교, 단지) |

실제 데이터로 바꿀 때는 `lib/data.ts`의 함수 본문만 API 호출이나 파일 fetch로 교체하면 된다.
상세 데이터는 샘플 단계라 한 번에 넘기고 있으므로, 동이 300개 넘게 늘어나면 선택 시점에 불러오도록 바꾼다.

필드 정의는 `docs/payload-schema.md`를 따른다. `tags`, `status_reason`, `comparison`은 아직 합의 전 후보라 optional로 두었다.
