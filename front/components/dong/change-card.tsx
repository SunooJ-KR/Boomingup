import { Card, CardBody } from "@/components/ui/card";
import { ModelingBadge } from "@/components/dong/modeling-badge";
import { SectionHeading } from "@/components/ui/section-heading";
import { InfoTooltip } from "@/components/ui/info-tooltip";
import {
  changeMeaningSentence,
  deltaSentence,
  FOOTNOTES,
  formatQuarter,
  formatPct,
  formatTwelveMonthRange,
  peakSentence,
  referenceSentence,
} from "@/lib/format";
import type { DongChange, Meta } from "@/lib/types";

type ChangeCardProps = {
  change: DongChange;
  reference: { seoul_12m_pct: number | null };
  meta: Meta;
};

/**
 * 지난 12개월 변화와 5년 범위 위치. 값 옆에 오차를 항상 붙인다.
 * 서울 평균과 구분되지 않는 차이는 payload에 아예 없다. 프론트가 계산해 채우지 않는다.
 */
export function ChangeCard({ change, reference, meta }: ChangeCardProps) {
  const delta = deltaSentence(change.delta_state, change.delta_12m_pct, change.delta_se_pct);
  const peak = peakSentence(change.peak_5y_state, change.peak_5y_gap_pct, change.peak_5y_gap_se_pct);

  return (
    <Card>
      <CardBody className="space-y-3">
        <ModelingBadge label="가격 지수" />
        <SectionHeading
          eyebrow="과거 관측 · 1년 전과 비교"
          title="아파트 가격 지수는 얼마나 달라졌을까요?"
          description={formatTwelveMonthRange(meta.support_as_of)}
        />

        <div className="grid grid-cols-2 gap-2" aria-label="선택한 동과 서울의 가격 지수 변화 비교">
          <ChangeValue
            label="선택한 동"
            value={formatPct(change.dong_12m_pct)}
            tooltip="이 동의 여러 아파트 거래를 모아 계산한 가격 지수가 1년 동안 변한 정도예요. 개별 아파트의 실거래가 변화와는 달라요."
          />
          <ChangeValue
            label="서울 전체"
            value={formatPct(change.seoul_12m_pct)}
            tooltip="서울 아파트 가격 지수가 같은 1년 동안 변한 정도예요. 선택한 동과 같은 기간을 비교해요."
            align="right"
          />
        </div>

        <p className="rounded-md bg-muted px-3 py-2 text-sm leading-relaxed text-foreground">
          {changeMeaningSentence(change.dong_12m_pct)} 특정 아파트 가격이 똑같이 변했다는 뜻은
          아니에요.
        </p>

        {delta ? (
          <div className="space-y-1">
            <p className="text-xs text-muted-foreground">
              <InfoTooltip
                label="서울 비교 결과 읽는 법"
                description="선택한 동과 서울 전체의 변화 차이가 계산 오차보다 충분히 큰지 확인한 결과예요. 차이가 작으면 어느 쪽이 더 변했다고 말하지 않아요."
              />
            </p>
            <p className="text-sm text-foreground">{delta}</p>
          </div>
        ) : null}
        <p className="text-xs text-muted-foreground">
          이미 지나간 기간을 정리한 값이며, 이후 가격 방향을 뜻하지 않아요. {FOOTNOTES.change}
        </p>

        {peak ? (
          <div className="space-y-1 border-t border-border pt-3">
            <p className="text-xs text-muted-foreground">
              <InfoTooltip
                label="최근 5년 범위 읽는 법"
                description="현재 가격 지수가 최근 5년 동안 관측된 가장 높은 지수와 얼마나 떨어져 있는지 보여줘요. 개별 단지의 신고가와는 달라요."
              />
            </p>
            <p className="text-sm text-foreground">{peak}</p>
            <p className="text-xs text-muted-foreground">{FOOTNOTES.peak}</p>
          </div>
        ) : null}

        {/* 서울 평균은 이 동의 기준선이 아니라 같은 기간에 일어난 다른 값이라, 접어 둔다 */}
        <details className="border-t border-border pt-3">
          <summary className="cursor-pointer list-none text-sm font-medium text-muted-foreground">
            서울 전체 참고치
          </summary>
          <p className="pt-2 text-sm text-foreground">
            {referenceSentence(reference.seoul_12m_pct)}
          </p>
        </details>

        <p className="text-xs text-muted-foreground">기준 {formatQuarter(meta.support_as_of)}</p>
      </CardBody>
    </Card>
  );
}

function ChangeValue({
  label,
  value,
  tooltip,
  align = "left",
}: {
  label: string;
  value: string;
  tooltip: string;
  align?: "left" | "right";
}) {
  return (
    <div className="rounded-md border border-border bg-card p-3">
      <p className="text-xs text-muted-foreground">
        <InfoTooltip label={label} description={tooltip} align={align} />
      </p>
      <p className="mt-1 text-2xl font-bold tabular-nums text-foreground">{value}</p>
      <p className="mt-1 text-xs text-muted-foreground">가격 지수의 1년 변화</p>
    </div>
  );
}
