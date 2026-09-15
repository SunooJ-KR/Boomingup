import { Badge } from "@/components/ui/badge";
import { Card, CardBody } from "@/components/ui/card";
import { SectionHeading } from "@/components/ui/section-heading";
import type { DongFacts } from "@/lib/types";

const STAGE_LABEL: Record<string, string> = {
  designated: "구역지정",
  association: "조합설립",
  management: "관리처분",
  construction: "착공",
};

export function FactsPanel({ facts }: { facts: DongFacts }) {
  const zones = facts.redevelop_zones;
  const zoneEntries = zones
    ? Object.entries(zones).filter(([, count]) => count > 0)
    : [];

  return (
    <Card>
      <CardBody className="space-y-3">
        <SectionHeading
          eyebrow="관측 정보"
          title="사실정보"
          description="예측의 근거가 아니라, 같이 보면 좋은 관측값입니다."
        />
        <dl className="grid grid-cols-2 gap-3 text-sm">
          <Fact label="최근 1년 매매" value={`${facts.n_sales_4q}건`} />
          <Fact
            label="전세 비중(최근 1년)"
            value={
              facts.jeonse_ratio_4q === null
                ? "-"
                : `${Math.round(facts.jeonse_ratio_4q * 100)}%`
            }
          />
          <Fact
            label="최근 2년 입주 세대"
            value={
              facts.completed_households_8q === null
                ? "-"
                : `${facts.completed_households_8q.toLocaleString("ko-KR")}세대`
            }
          />
          <Fact
            label="투기과열지구"
            value={facts.reg_overheated === null ? "-" : facts.reg_overheated ? "해당" : "해당 없음"}
          />
        </dl>

        <div className="space-y-1.5">
          <p className="text-xs font-medium text-muted-foreground">정비사업 구역</p>
          {zoneEntries.length > 0 ? (
            <div className="flex flex-wrap gap-1.5">
              {zoneEntries.map(([stage, count]) => (
                <Badge key={stage} variant="neutral">
                  {STAGE_LABEL[stage] ?? stage} {count}곳
                </Badge>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">매칭된 정비사업 구역이 없습니다.</p>
          )}
        </div>
      </CardBody>
    </Card>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="text-sm font-medium tabular-nums text-foreground">{value}</dd>
    </div>
  );
}
