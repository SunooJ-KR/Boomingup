import { Card, CardBody } from "@/components/ui/card";
import { SectionHeading } from "@/components/ui/section-heading";
import { formatPct } from "@/lib/format";
import type { DongComparison } from "@/lib/types";

type ComparisonCardProps = {
  comparison: DongComparison;
  dongName: string;
  guName: string;
};

export function ComparisonCard({ comparison, dongName, guName }: ComparisonCardProps) {
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
        <SectionHeading
          eyebrow="비교"
          title="서울·자치구·동 흐름"
          description="순위가 아니라, 선택한 동이 어디쯤인지 보려고 나란히 놓은 값이에요."
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
          값이 없는 항목은 그 기간의 추정값이 없다는 뜻이에요.
        </p>
      </CardBody>
    </Card>
  );
}
