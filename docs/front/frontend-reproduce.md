# 테마·지도 UI 이식 가이드

## 목적

이 문서는 현재 `front/`의 화면 스타일과 지도 연동 방식을 다른 프로젝트에 재사용하기 위한 가이드다. 특정 서비스 데이터나 임앤장 도메인 로직을 옮기는 문서가 아니라, 비슷한 UI 톤을 만드는 데 필요한 최소 요소를 정리한다.

핵심 이식 대상은 두 가지다.

- 테마: 색상 토큰, radius, shadow, animation, 기본 typography
- 지도: Kakao Maps JavaScript SDK 로딩, 커스텀 마커, 클러스터, 실패 시 좌표 미리보기 폴백

## 기술 스택

현재 프론트는 다음 조합이다.

```text
Next.js 15 App Router
React 19
TypeScript
Tailwind CSS v4
class-variance-authority
clsx
tailwind-merge
```

새 프로젝트에서 같은 스타일을 빠르게 재현하려면 위 조합을 그대로 쓰는 편이 가장 쉽다. 핵심 코드는 Tailwind v4의 `@theme inline`과 CSS 변수에 기대고 있으므로 Tailwind v3 프로젝트라면 토큰 연결 방식을 따로 바꿔야 한다.

## 가져갈 파일

테마와 기본 UI만 필요하면 다음 파일이 최소 세트다.

```text
front/app/globals.css
front/components/ui/button.tsx
front/components/ui/card.tsx
front/components/ui/badge.tsx
front/components/ui/input.tsx
front/components/ui/section-heading.tsx
front/lib/utils.ts
```

지도까지 필요하면 다음 파일을 참고해 새 프로젝트 데이터 구조에 맞게 분리한다.

```text
front/components/map-preview.tsx
front/lib/data.ts      # 지도 상수와 projectToMap만 참고
front/lib/types.ts     # IndexComplex 형태만 참고
front/lib/format.ts    # isFailed 같은 상태 판정만 참고
```

`SearchPanel`, `DetailPanel`, `BasketBar`, `CompareSection`은 현재 화면 흐름에 묶여 있으므로 그대로 가져가기보다 레이아웃 예시로만 본다.

## 테마 토큰

테마의 중심은 `front/app/globals.css`의 `:root`와 `@theme inline`이다.

```css
:root {
  --background: #ffffff;
  --foreground: #1d2433;
  --card: #ffffff;
  --muted: #f6f7f9;
  --muted-foreground: #697386;
  --primary: #4136e8;
  --primary-foreground: #ffffff;
  --primary-hover: #2f25c9;
  --primary-soft: #eeedff;
  --border: #e6e8ee;
  --input: #f6f7f9;
  --ring: #4136e8;
  --neutral-soft: #f0f1f4;
  --neutral-strong: #858b98;
  --radius: 12px;
}
```

UI 톤은 다음 규칙으로 맞춘다.

- 주요 행동, 선택, 활성 상태는 `--primary` 하나로 모은다.
- 경고·성공·오류를 초록/주황/빨강으로 강하게 나누지 않는다.
- 상태 구분은 회색 톤, 라벨, border 변화로 처리한다.
- 배경은 `body`에 `bg-muted`, 실제 패널은 `bg-card`를 쓴다.
- 카드는 `border`, 얕은 shadow, 10~14px radius 정도로 유지한다.
- animation은 `opacity`와 `transform`만 사용한다.

Tailwind v4에서 CSS 변수를 유틸리티 색상으로 쓰려면 `@theme inline`에 연결한다.

```css
@theme inline {
  --color-background: var(--background);
  --color-foreground: var(--foreground);
  --color-card: var(--card);
  --color-muted: var(--muted);
  --color-muted-foreground: var(--muted-foreground);
  --color-primary: var(--primary);
  --color-primary-foreground: var(--primary-foreground);
  --color-primary-hover: var(--primary-hover);
  --color-primary-soft: var(--primary-soft);
  --color-border: var(--border);
  --color-input: var(--input);
  --color-ring: var(--ring);
  --color-neutral-soft: var(--neutral-soft);
  --color-neutral-strong: var(--neutral-strong);

  --radius-sm: 10px;
  --radius-md: 12px;
  --radius-lg: 14px;

  --shadow-panel: 0 1px 2px rgb(29 36 51 / 0.04), 0 6px 20px rgb(29 36 51 / 0.05);
  --shadow-float: 0 2px 6px rgb(29 36 51 / 0.06), 0 16px 40px rgb(29 36 51 / 0.09);
  --ease-out-soft: cubic-bezier(0.2, 0.7, 0.3, 1);
}
```

## 기본 컴포넌트

`components/ui`의 primitive는 얇게 유지한다. 새 프로젝트에서도 이 정도만 있으면 비슷한 화면 밀도를 낼 수 있다.

```text
Button
  default: primary 배경
  outline: 흰 배경 + border
  soft: primary-soft 배경
  ghost: 배경 없이 hover 때만 primary-soft

Card
  rounded-lg border bg-card shadow-panel

Badge
  default/accent/neutral 세 변형

SectionHeading
  작은 uppercase eyebrow + 굵은 제목
```

`class-variance-authority`를 쓰면 버튼과 배지 variant를 현재처럼 깔끔하게 유지할 수 있다. `cn()`은 `clsx`와 `tailwind-merge` 조합이면 충분하다.

## 지도 데이터 계약

지도 컴포넌트는 도메인 이름 대신 다음처럼 일반화된 item 배열을 받게 만들면 된다.

```ts
export interface MapItem {
  id: string;
  title: string;
  subtitle?: string;
  lat: number | null;
  lng: number | null;
  status?: "default" | "muted";
}
```

컴포넌트 props는 다음 정도면 다른 프로젝트에 붙이기 쉽다.

```ts
type MapViewProps = {
  items: MapItem[];
  selectedId: string | null;
  onSelect: (id: string) => void;
};
```

현재 `map-preview.tsx`의 `IndexComplex` 의존성은 `MapItem`으로 바꾸고, `item.n`은 `item.title`, `isFailed(item)`은 `item.status === "muted"` 같은 판정으로 바꾸면 된다.

## Kakao 지도 연동

환경변수 이름은 현재 코드처럼 공개키임을 드러내는 이름을 쓴다.

```text
NEXT_PUBLIC_KAKAO_JS_KEY=
```

Kakao SDK는 클라이언트에서만 로드한다. Next.js App Router에서는 지도 컴포넌트 파일 상단에 `"use client";`가 필요하다.

SDK URL은 다음 형태다.

```ts
script.src =
  `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${encodeURIComponent(key)}&autoload=false&libraries=clusterer`;
```

연동 흐름은 다음 순서다.

1. `process.env.NEXT_PUBLIC_KAKAO_JS_KEY`가 없으면 fallback으로 전환한다.
2. `<script>`를 한 번만 삽입하고 전역 `window.kakao`를 기다린다.
3. `kakao.maps.load()` 콜백 안에서 `new kakao.maps.Map()`을 만든다.
4. item별로 `CustomOverlay`에 버튼 DOM을 넣어 접근 가능한 마커를 만든다.
5. 넓은 줌에서는 `MarkerClusterer`에 오버레이를 넣어 숫자 묶음으로 표시한다.
6. 선택한 법정동이 있으면 `map.setLevel(5)`로 확대하고 `map.panTo()`로 중심을 옮긴다. 사용자가 이미 더 확대했다면 현재 수준을 유지한다.
7. SDK 로드 실패 또는 timeout이면 좌표 미리보기로 폴백한다.

Kakao 개발자 콘솔에는 실행 도메인을 등록해야 한다.

```text
http://localhost:3000
https://운영-도메인
https://고정-preview-도메인
```

Vercel preview처럼 URL이 매번 바뀌는 환경은 지도 확인이 어렵다. 지도까지 확인하려면 고정 preview alias를 만들고 그 도메인을 Kakao 콘솔에 등록한다.

## 지도 폴백

Kakao SDK가 없어도 화면이 빈 영역이 되지 않게 좌표 미리보기를 둔다. 현재 코드는 서울 경계를 기준으로 위도·경도를 퍼센트 좌표로 투영한다.

```ts
const BOUNDS = {
  minLng: 126.74,
  maxLng: 127.2,
  minLat: 37.42,
  maxLat: 37.72,
};

function projectToMap(lat: number, lng: number) {
  const x = ((lng - BOUNDS.minLng) / (BOUNDS.maxLng - BOUNDS.minLng)) * 100;
  const y = (1 - (lat - BOUNDS.minLat) / (BOUNDS.maxLat - BOUNDS.minLat)) * 100;
  return {
    x: Math.max(4, Math.min(96, x)),
    y: Math.max(12, Math.min(94, y)),
  };
}
```

다른 지역 프로젝트라면 `BOUNDS`만 해당 지역으로 바꾸면 된다. 전국 단위나 여러 국가를 다룬다면 fallback도 단순 투영 대신 정적 지도 이미지, SVG 경계, 또는 tile 없는 canvas 좌표계로 바꾸는 편이 낫다.

## 마커 스타일

현재 마커는 `CustomOverlay` 안에 실제 `button`을 넣는다. 그래서 클릭, 키보드 포커스, `aria-label`, `title`을 모두 줄 수 있다.

```ts
const marker = document.createElement("button");
marker.type = "button";
marker.title = item.title;
marker.setAttribute("aria-label", `${item.title} 선택`);
marker.addEventListener("click", () => onSelectRef.current(item.id));
```

마커 색상은 테마와 맞춰 두 가지로만 구분한다.

```text
default: bg-primary
muted: bg-neutral-strong
selected: scale + primary-hover + 더 큰 ring shadow
```

선택 상태는 `overlay.setZIndex(selected ? 10 : 1)`로 위에 오게 한다.

## 클러스터와 성능

`MarkerClusterer`는 많은 마커를 다룰 때 필요하다. 현재 구조는 지도 이동이 끝나는 `idle` 이벤트마다 보이는 영역 근처의 item만 clusterer에 다시 넣는다.

```text
CLUSTER_MIN_LEVEL = 6
VIEWPORT_PADDING = 0.2
```

성능상 중요한 점은 다음과 같다.

- item별 마커 DOM과 `CustomOverlay`는 한 번 만들고 `Map`에 캐시한다.
- 검색 결과가 바뀌어도 캐시된 overlay를 재사용한다.
- 지도 bounds보다 사방 20% 넓게 렌더링해 가장자리 마커가 갑자기 사라지는 느낌을 줄인다.
- 선택된 item은 화면 밖이어도 항상 렌더 대상에 포함한다.

## 화면 구조 예시

비슷한 UI를 만들 때 첫 화면은 다음 3패널 구조가 잘 맞는다.

```text
desktop:
  [검색/필터 패널] [지도] [선택 상세 패널]

tablet:
  [검색/필터 패널] [지도]
  [선택 상세 패널]

mobile:
  [검색/필터]
  [지도]
  [선택 상세]
```

상단 header는 얇고 sticky로 두고, 검색 패널도 데스크톱에서만 sticky 처리한다. 하단 고정 action bar가 필요하다면 `BasketBar`의 레이아웃만 참고하되 문구와 저장 로직은 새 프로젝트에 맞춘다.

## 이식 순서

1. 새 프로젝트에 Tailwind v4와 `globals.css` 토큰을 먼저 적용한다.
2. `Button`, `Card`, `Badge`, `Input`, `SectionHeading`, `cn()`을 옮긴다.
3. 샘플 `MapItem[]` 5~10개로 지도 컴포넌트를 먼저 붙인다.
4. Kakao 키 없이 fallback이 보이는지 확인한다.
5. `NEXT_PUBLIC_KAKAO_JS_KEY`를 넣고 실제 지도, 마커 클릭, 선택 이동을 확인한다.
6. 실제 데이터 API 또는 정적 JSON을 `MapItem[]`으로 변환하는 adapter를 만든다.
7. 검색·필터·상세 패널은 새 프로젝트 도메인에 맞게 별도 구현한다.

## 확인 체크리스트

- `npm run typecheck`가 통과한다.
- `npm run build`가 통과한다.
- Kakao 키가 없을 때 fallback이 보인다.
- Kakao 키가 있을 때 실제 지도와 마커가 보인다.
- 현재 도메인이 Kakao JavaScript SDK 도메인에 등록되어 있다.
- 마커 클릭 시 `selectedId`가 바뀐다.
- 법정동을 선택하면 지도 레벨이 5 이하로 확대되고 `panTo()`로 중심이 이동한다.
- 모바일 폭에서 검색, 지도, 상세 영역이 겹치지 않는다.
- `prefers-reduced-motion: reduce`에서 애니메이션이 사실상 꺼진다.
