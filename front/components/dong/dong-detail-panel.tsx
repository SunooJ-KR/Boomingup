import { AreaStatsCard } from "@/components/dong/area-stats-card";
import { ComparisonCard } from "@/components/dong/comparison-card";
import { ComplexList } from "@/components/dong/complex-list";
import { EmptyState } from "@/components/dong/empty-state";
import { FactsPanel } from "@/components/dong/facts-panel";
import { PredictionCard } from "@/components/dong/prediction-card";
import { Button } from "@/components/ui/button";
import type { DongDetail, DongSummary, Meta } from "@/lib/types";

export type DetailState = "idle" | "loading" | "error" | "ready";

type DongDetailPanelProps = {
  dong: DongSummary | null;
  detail: DongDetail | null;
  meta: Meta;
  state: DetailState;
  onRetry?: () => void;
};

export function DongDetailPanel({ dong, detail, meta, state, onRetry }: DongDetailPanelProps) {
  if (!dong) {
    return (
      <EmptyState
        title="동을 검색하거나 목록에서 선택하세요."
        description="선택한 동의 추정 변화율과 관측 정보를 함께 보여줍니다."
      />
    );
  }

  const header = (
    <div>
      <p className="text-xs text-muted-foreground">{dong.gu_name}</p>
      <h1 className="text-xl font-bold text-foreground">{dong.umd_name}</h1>
    </div>
  );

  if (state === "loading") {
    return (
      <div className="space-y-3">
        {header}
        <EmptyState title="상세 정보를 불러오는 중입니다." />
      </div>
    );
  }

  if (state === "error" || !detail) {
    return (
      <div className="space-y-3">
        {header}
        <EmptyState
          title="상세 정보를 불러오지 못했습니다."
          description="잠시 후 다시 시도해 주세요."
          action={
            onRetry ? (
              <Button variant="outline" size="sm" onClick={onRetry}>
                다시 시도
              </Button>
            ) : undefined
          }
        />
      </div>
    );
  }

  // 화면 아래에 새로 붙었다는 것을 알리는 등장 효과. 내용이 준비된 이 경로에만 건다.
  // 부모가 선택한 동을 key로 넘기므로 다른 동을 고르면 다시 재생된다.
  return (
    <div className="animate-rise-in space-y-3">
      {header}

      <PredictionCard
        prediction={detail.prediction}
        meta={meta}
        statusReasonText={dong.status_reason}
        nSales4q={detail.facts.n_sales_4q}
      />

      {detail.comparison ? (
        <ComparisonCard
          comparison={detail.comparison}
          dongName={dong.umd_name}
          guName={dong.gu_name}
        />
      ) : null}

      <FactsPanel
        facts={detail.facts}
        permitZone={meta.seoul_apartment_permit_zone}
        regulationAsOf={meta.regulation_as_of}
      />
      {detail.area_stats && detail.area_stats.length > 0 ? (
        <AreaStatsCard stats={detail.area_stats} period={detail.area_stats_period ?? "-"} />
      ) : null}

      <ComplexList complexes={detail.complexes} />
    </div>
  );
}
