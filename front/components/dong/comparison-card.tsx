import { Card, CardBody } from "@/components/ui/card";
import { SectionHeading } from "@/components/ui/section-heading";
import { formatPct, formatQuarter } from "@/lib/format";
import { shiftQuarter } from "@/lib/quarter";
import type { DongComparison, Meta } from "@/lib/types";

type ComparisonCardProps = {
  comparison: DongComparison;
  dongName: string;
  guName: string;
  meta: Meta;
};

export function ComparisonCard({ comparison, dongName, guName, meta }: ComparisonCardProps) {
  // 예측과 같은 길이의 과거 구간을 본다. 기준이 2026Q2면 2025Q2부터 2026Q2까지다.
  const quarters = Math.round(meta.horizon_months / 3);
  const fromQuarter = shiftQuarter(meta.as_of_quarter, -quarters);
  const rows = [
    { label: "서울 전체", value: comparison.seoul_change_pct },
    { label: guName, value: comparison.gu_change_pct },
    { label: dongName, value: comparison.dong_change_pct },
  ];

  // 막대 길이는 세 값의 절댓값 최대치를 기준으로 맞춘다
  const scale = Math.max(1, ...rows.map((row) => Math.abs(row.value ?? 0)));

  return (
    <Card>
      <CardBody className="space-y-3">
        {/* 바로 위 예측 카드와 기간 길이가 같아 추정값으로 읽히기 쉽다.
            제목과 설명에서 지난 기간의 실제 값이라는 것을 먼저 밝힌다. */}
        <SectionHeading
          eyebrow="과거 실적"
          title={`지난 ${meta.horizon_months}개월 실제 변화율`}
          description={`${formatQuarter(fromQuarter)}부터 ${formatQuarter(meta.as_of_quarter)}까지 실제로 일어난 변화예요. 위 카드의 추정값과는 다른 값이에요.`}
        />
        <ul className="space-y-2">
          {rows.map((row) => (
            <li key={row.label} className="flex items-center gap-3">
              <span className="w-20 shrink-0 text-xs text-muted-foreground">{row.label}</span>
              <span className="h-1.5 flex-1 rounded-sm bg-neutral-soft">
                <span
                  className="block h-1.5 rounded-sm bg-primary"
                  style={{ width: `${(Math.abs(row.value ?? 0) / scale) * 100}%` }}
                />
              </span>
              <span className="w-14 shrink-0 text-right text-sm tabular-nums text-foreground">
                {formatPct(row.value)}
              </span>
            </li>
          ))}
        </ul>
        <p className="text-xs text-muted-foreground">
          서울과 자치구는 예측 대상 동을 동 단위로 단순 평균한 값이에요. 거래가 많은 동이 더 크게
          반영되지는 않아요. 값이 없으면 그 기간 지수를 계산하지 못했다는 뜻이에요.
        </p>
      </CardBody>
    </Card>
  );
}
