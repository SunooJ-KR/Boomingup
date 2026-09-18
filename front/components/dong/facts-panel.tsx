import { Badge } from "@/components/ui/badge";
import { Card, CardBody } from "@/components/ui/card";
import { InfoTooltip } from "@/components/ui/info-tooltip";
import { SectionHeading } from "@/components/ui/section-heading";
import type { DongFacts } from "@/lib/types";

const STAGE_LABEL: Record<string, string> = {
  designated: "구역지정",
  association: "조합설립",
  management: "관리처분",
  construction: "착공",
};

type FactsPanelProps = {
  facts: DongFacts;
  /** 서울 전체 아파트 토지거래허가구역 지정 여부 (regulation_summary 기준) */
  permitZone: boolean;
  regulationAsOf: string;
};

export function FactsPanel({ facts, permitZone, regulationAsOf }: FactsPanelProps) {
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
          description="같이 보면 좋은 관측 값이에요."
        />
        <dl className="grid grid-cols-2 gap-3 text-sm">
          <Fact
            label="최근 1년 매매"
            value={`${facts.n_sales_4q}건`}
            tooltip="기준 분기까지 1년 동안 신고된 아파트 매매 건수예요."
          />
          <Fact
            label="전세 비중(최근 1년)"
            value={
              facts.jeonse_ratio_4q === null
                ? "-"
                : `${Math.round(facts.jeonse_ratio_4q * 100)}%`
            }
            tooltip="최근 1년 전월세 신고 중 전세가 차지한 비율이에요. 이 값만으로 주거 수요의 이유를 판단할 수는 없어요."
            align="right"
          />
          <Fact
            label="최근 2년 입주 세대"
            value={
              facts.completed_households_8q === null
                ? "-"
                : `${facts.completed_households_8q.toLocaleString("ko-KR")}세대`
            }
            tooltip="최근 2년 동안 사용승인된 아파트의 세대수를 더한 값이에요. 앞으로 입주할 물량은 포함하지 않아요."
          />
          <Fact
            label={`아파트 토지거래허가 (${regulationAsOf} 기준)`}
            value={permitZone ? "서울 전체 지정" : "지정 없음"}
            tooltip="아파트 거래 전에 관할 구청의 허가가 필요한 지역인지 보여줘요. 표시된 기준일의 지정 상태예요."
            align="right"
          />
        </dl>

        <div className="space-y-1.5">
          <p className="text-xs font-medium text-muted-foreground">
            <InfoTooltip
              label="정비사업 구역"
              description="재개발·재건축 등 정비사업 단계가 연결된 구역 수예요. 사업의 진행 속도나 가격 영향을 뜻하지 않아요."
            />
          </p>
          {zoneEntries.length > 0 ? (
            <div className="flex flex-wrap gap-1.5">
              {zoneEntries.map(([stage, count]) => (
                <Badge key={stage} variant="neutral">
                  {STAGE_LABEL[stage] ?? stage} {count}곳
                </Badge>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">연결된 정비사업 구역이 없어요.</p>
          )}
        </div>
      </CardBody>
    </Card>
  );
}

function Fact({
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
    <div>
      <dt className="text-xs text-muted-foreground">
        <InfoTooltip label={label} description={tooltip} align={align} />
      </dt>
      <dd className="text-sm font-medium tabular-nums text-foreground">{value}</dd>
    </div>
  );
}
