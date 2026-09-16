import { StatusBadge } from "@/components/dong/status-badge";
import { Card, CardBody } from "@/components/ui/card";
import { SectionHeading } from "@/components/ui/section-heading";
import {
  formatCoverage,
  formatHorizon,
  formatInterval,
  formatPct,
  formatQuarter,
  statusReason,
} from "@/lib/format";
import type { Meta, Prediction } from "@/lib/types";

type PredictionCardProps = {
  prediction: Prediction;
  meta: Meta;
  statusReasonText?: string | null;
  nSales4q: number;
};

export function PredictionCard({
  prediction,
  meta,
  statusReasonText,
  nSales4q,
}: PredictionCardProps) {
  const interval = formatInterval(prediction.lower_pct, prediction.upper_pct, meta.as_of_quarter);

  return (
    <Card>
      <CardBody className="space-y-3">
        <div className="flex items-start justify-between gap-2">
          <SectionHeading eyebrow="추정" title={formatHorizon(meta)} />
          <StatusBadge status={prediction.status} />
        </div>

        {prediction.status === "PREDICTED" ? (
          <>
            <p className="text-3xl font-bold tabular-nums text-foreground">
              {formatPct(prediction.change_pct_est)}
            </p>
            {interval ? <p className="text-sm text-muted-foreground">{interval}</p> : null}
            <p className="text-xs text-muted-foreground">{formatCoverage(meta)}</p>
          </>
        ) : (
          <p className="text-sm text-muted-foreground">
            {statusReason(prediction.status, statusReasonText)}
          </p>
        )}

        <p className="text-xs text-muted-foreground">
          기준 {formatQuarter(meta.as_of_quarter)} · 최근 1년 매매 {nSales4q}건
        </p>
      </CardBody>
    </Card>
  );
}
