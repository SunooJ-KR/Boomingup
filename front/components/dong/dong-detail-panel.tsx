import { AreaStatsCard } from "@/components/dong/area-stats-card";
import { ChangeCard } from "@/components/dong/change-card";
import { ComplexList } from "@/components/dong/complex-list";
import { DongDetailLoading } from "@/components/dong/dong-detail-loading";
import { EmptyState } from "@/components/dong/empty-state";
import { FactsPanel } from "@/components/dong/facts-panel";
import { FlowsCard } from "@/components/dong/flows-card";
import { InterpretationGuide } from "@/components/dong/interpretation-guide";
import { PeersCard } from "@/components/dong/peers-card";
import { SampleCard } from "@/components/dong/sample-card";
import { StructureCard } from "@/components/dong/structure-card";
import { Button } from "@/components/ui/button";
import { FOOTNOTES } from "@/lib/format";
import type { DongDetail, DongSummary, Meta } from "@/lib/types";

export type DetailState = "idle" | "loading" | "error" | "ready";

type DongDetailPanelProps = {
  dong: DongSummary | null;
  detail: DongDetail | null;
  meta: Meta;
  state: DetailState;
  onRetry?: () => void;
  onSelect: (dongId: string) => void;
};

export function DongDetailPanel({
  dong,
  detail,
  meta,
  state,
  onRetry,
  onSelect,
}: DongDetailPanelProps) {
  if (!dong) {
    return (
      <EmptyState
        title="동을 검색하거나 목록에서 선택해주세요."
        description="선택한 동의 거래 상태와 관측 정보를 함께 보여드려요."
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
        <DongDetailLoading dongName={dong.umd_name} />
      </div>
    );
  }

  if (state === "error" || !detail) {
    return (
      <div className="space-y-3">
        {header}
        <EmptyState
          title="상세 정보를 불러오지 못했어요."
          description="잠시 후 다시 시도해주세요."
          action={
            onRetry ? (
              <Button variant="outline" size="sm" onClick={onRetry}>
                다시 시도하기
              </Button>
            ) : undefined
          }
        />
      </div>
    );
  }

  // 화면 아래에 새로 붙었다는 것을 알리는 등장 효과. 내용이 준비된 이 경로에만 건다.
  // 부모가 선택한 동을 key로 넘기므로 다른 동을 고르면 다시 재생된다.
  // 블록 순서는 investment-support-plan.md §4.1을 따른다. 표본 상태가 변화율보다 먼저다.
  return (
    <div className="animate-rise-in space-y-3">
      {header}

      <InterpretationGuide />
      <SampleCard sample={detail.sample} meta={meta} />
      <ChangeCard
        change={detail.change}
        reference={detail.reference}
        meta={meta}
        highError={detail.sample.flags.includes("HIGH_INDEX_ERROR")}
      />
      <FlowsCard flows={detail.flows} />

      <FactsPanel
        facts={detail.facts}
        permitZone={meta.seoul_apartment_permit_zone}
        regulationAsOf={meta.regulation_as_of}
      />

      {detail.structure ? <StructureCard structure={detail.structure} meta={meta} /> : null}
      {detail.peers ? <PeersCard peers={detail.peers} onSelect={onSelect} /> : null}

      {detail.area_stats && detail.area_stats.length > 0 ? (
        <AreaStatsCard stats={detail.area_stats} period={detail.area_stats_period ?? "-"} />
      ) : null}

      <ComplexList complexes={detail.complexes} />

      <p className="text-xs text-muted-foreground">{FOOTNOTES.service}</p>
    </div>
  );
}
