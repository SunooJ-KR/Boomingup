"use client";

import { Button } from "@/components/ui/button";

export default function Error({ reset }: { error: Error; reset: () => void }) {
  return (
    <div className="mx-auto max-w-[1400px] space-y-3 px-4 py-10">
      <p className="text-sm text-foreground">화면을 불러오는 중 문제가 생겼습니다.</p>
      <Button variant="outline" size="sm" onClick={reset}>
        다시 시도
      </Button>
    </div>
  );
}
