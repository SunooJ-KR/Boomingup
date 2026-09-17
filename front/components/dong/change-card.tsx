import { Card, CardBody } from "@/components/ui/card";
import { SectionHeading } from "@/components/ui/section-heading";
import {
  changeHeadline,
  deltaSentence,
  FOOTNOTES,
  formatQuarter,
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
        <SectionHeading
          eyebrow="지난 12개월"
          title={changeHeadline(change.dong_12m_pct, change.seoul_12m_pct)}
        />

        {delta ? <p className="text-sm text-foreground">{delta}</p> : null}
        <p className="text-xs text-muted-foreground">{FOOTNOTES.change}</p>

        {peak ? (
          <div className="space-y-1 border-t border-border pt-3">
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
