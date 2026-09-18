import { Card, CardBody } from "@/components/ui/card";
import { InfoTooltip } from "@/components/ui/info-tooltip";
import { SectionHeading } from "@/components/ui/section-heading";
import { formatManwon } from "@/lib/format";
import type { AreaStat } from "@/lib/types";

type AreaStatsCardProps = {
  stats: AreaStat[];
  period: string;
};

export function AreaStatsCard({ stats, period }: AreaStatsCardProps) {
  const rows = stats.filter((stat) => stat.n_sales > 0);

  return (
    <Card>
      <CardBody className="space-y-3">
        <SectionHeading
          eyebrow="매매 가격 분포"
          title="면적대별 거래"
          description={`${period}에 실제로 있었던 매매를 모은 값이에요.`}
        />
        {rows.length === 0 ? (
          <p className="text-sm text-muted-foreground">이 기간에는 매매가 없어요.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-muted-foreground">
                <th scope="col" className="pb-1 font-normal">
                  전용면적
                </th>
                <th scope="col" className="pb-1 text-right font-normal">
                  거래 수
                </th>
                <th scope="col" className="pb-1 text-right font-normal">
                  <InfoTooltip
                    label="중위 가격"
                    description="거래가격을 낮은 순서로 놓았을 때 가운데에 있는 값이에요. 평균과 달리 아주 높거나 낮은 한 건의 영향을 덜 받아요."
                    align="right"
                  />
                </th>
                <th scope="col" className="pb-1 text-right font-normal">
                  가격 범위
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {rows.map((stat) => (
                <tr key={stat.band}>
                  <th scope="row" className="py-1.5 text-left font-medium text-foreground">
                    {stat.band}
                  </th>
                  <td className="py-1.5 text-right tabular-nums text-muted-foreground">
                    {stat.n_sales.toLocaleString("ko-KR")}건
                  </td>
                  <td className="py-1.5 text-right tabular-nums text-foreground">
                    {formatManwon(stat.median_price_manwon)}
                  </td>
                  <td className="py-1.5 text-right text-xs tabular-nums text-muted-foreground">
                    {formatManwon(stat.min_price_manwon)} ~ {formatManwon(stat.max_price_manwon)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <p className="text-xs text-muted-foreground">
          거래가 적은 면적대는 중위 가격이 크게 흔들릴 수 있어요.
        </p>
      </CardBody>
    </Card>
  );
}
