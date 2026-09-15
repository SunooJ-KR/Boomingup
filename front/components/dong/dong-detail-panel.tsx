import { ComparisonCard } from "@/components/dong/comparison-card";
import { ComplexList } from "@/components/dong/complex-list";
import { EmptyState } from "@/components/dong/empty-state";
import { FactsPanel } from "@/components/dong/facts-panel";
import { PredictionCard } from "@/components/dong/prediction-card";
import type { DongDetail, DongSummary, Meta } from "@/lib/types";

type DongDetailPanelProps = {
  dong: DongSummary | null;
  detail: DongDetail | null;
  meta: Meta;
};

export function DongDetailPanel({ dong, detail, meta }: DongDetailPanelProps) {
  if (!dong) {
    return (
      <EmptyState
        title="동을 검색하거나 목록에서 선택하세요."
        description="선택한 동의 추정 변화율과 관측 정보를 함께 보여줍니다."
      />
    );
  }

  if (!detail) {
    return (
      <EmptyState
        title="상세 정보를 불러오지 못했습니다."
        description="잠시 후 다시 선택해 주세요."
      />
    );
  }

  return (
    <div className="space-y-3">
      <div>
        <p className="text-xs text-muted-foreground">{dong.gu_name}</p>
        <h1 className="text-xl font-bold text-foreground">{dong.umd_name}</h1>
      </div>

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

      <FactsPanel facts={detail.facts} />
      <ComplexList complexes={detail.complexes} />
    </div>
  );
}
