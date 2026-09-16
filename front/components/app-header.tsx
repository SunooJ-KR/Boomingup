"use client";

import { useEffect, useRef } from "react";

import { formatQuarter } from "@/lib/format";

type AppHeaderProps = {
  asOfQuarter: string;
  salePeriod: string;
};

/**
 * 화면 맨 위에 붙어 있는 머리말.
 *
 * 좁은 폭에서는 제목과 기준 문구가 두 줄로 접혀 높이가 달라진다(480px 이상 49px, 그 아래 69px).
 * 좌측 열 높이와 sticky 위치, 스크롤 여백이 모두 이 높이를 기준으로 삼기 때문에
 * 값을 코드에 적어 두면 좁은 화면에서 어긋난다. 실제 높이를 재서 --app-header-h에 적어 둔다.
 */
export function AppHeader({ asOfQuarter, salePeriod }: AppHeaderProps) {
  const ref = useRef<HTMLElement>(null);

  useEffect(() => {
    const header = ref.current;
    if (!header) return;

    const publish = () => {
      const height = header.getBoundingClientRect().height;
      document.documentElement.style.setProperty("--app-header-h", `${height}px`);
    };

    publish();
    const observer = new ResizeObserver(publish);
    observer.observe(header);
    return () => observer.disconnect();
  }, []);

  return (
    <header ref={ref} className="sticky top-0 z-10 border-b border-border bg-card/95 backdrop-blur">
      <div className="mx-auto flex max-w-[1400px] flex-wrap items-baseline gap-x-3 gap-y-1 px-4 py-3">
        <span className="text-base font-bold text-foreground">Boomingup</span>
        <span className="text-xs text-muted-foreground">
          기준 {formatQuarter(asOfQuarter)} · 매매 {salePeriod}
        </span>
      </div>
    </header>
  );
}
