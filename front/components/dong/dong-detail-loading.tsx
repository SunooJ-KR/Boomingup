"use client";

import { useEffect, useState } from "react";
import { BrainCircuit, Check, Circle, LoaderCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardBody } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const LOADING_STEPS = [
  "최근 거래와 표본 상태를 불러오고 있어요",
  "머신러닝으로 분류된 지역 구조를 확인하고 있어요",
  "특성이 비슷한 비교 동을 연결하고 있어요",
] as const;

const STEP_INTERVAL_MS = 450;

export function DongDetailLoading({ dongName }: { dongName: string }) {
  const [step, setStep] = useState(0);

  useEffect(() => {
    if (step >= LOADING_STEPS.length - 1) return;

    const timer = window.setTimeout(() => setStep((current) => current + 1), STEP_INTERVAL_MS);

    return () => window.clearTimeout(timer);
  }, [step]);

  return (
    <Card className="border-primary/20">
      <CardBody className="space-y-5">
        <div className="space-y-2">
          <Badge variant="accent" className="gap-1.5">
            <BrainCircuit aria-hidden="true" className="size-3.5" />
            머신러닝 지역 구조 분석
          </Badge>
          <div>
            <h2 className="text-base font-bold text-foreground">
              {dongName}의 비교 기준을 준비하고 있어요
            </h2>
            <p aria-live="polite" className="mt-1 text-sm text-muted-foreground">
              {LOADING_STEPS[step]}
            </p>
          </div>
        </div>

        <ol aria-hidden="true" className="space-y-2">
          {LOADING_STEPS.map((label, index) => {
            const isComplete = index < step;
            const isCurrent = index === step;
            const Icon = isComplete ? Check : isCurrent ? LoaderCircle : Circle;

            return (
              <li
                key={label}
                className={cn(
                  "flex min-h-6 items-center gap-2 text-xs",
                  index <= step ? "text-foreground" : "text-muted-foreground",
                )}
              >
                <span
                  className={cn(
                    "flex size-5 shrink-0 items-center justify-center rounded-full",
                    index <= step ? "bg-primary-soft text-primary" : "bg-neutral-soft",
                  )}
                >
                  <Icon
                    className={cn("size-3", isCurrent && "animate-spin")}
                    strokeWidth={isComplete ? 3 : 2}
                  />
                </span>
                <span>{label}</span>
              </li>
            );
          })}
        </ol>

        <div aria-hidden="true" className="grid gap-3 sm:grid-cols-2">
          <DetailSkeleton />
          <DetailSkeleton />
        </div>
      </CardBody>
    </Card>
  );
}

function DetailSkeleton() {
  return (
    <div className="space-y-3 border-t border-border pt-3">
      <div className="skeleton-shimmer h-3 w-20 rounded-full bg-neutral-soft" />
      <div className="skeleton-shimmer h-5 w-32 max-w-full rounded-full bg-neutral-soft" />
      <div className="space-y-2 pt-1">
        <div className="skeleton-shimmer h-3 w-full rounded-full bg-neutral-soft" />
        <div className="skeleton-shimmer h-3 w-4/5 rounded-full bg-neutral-soft" />
      </div>
    </div>
  );
}
