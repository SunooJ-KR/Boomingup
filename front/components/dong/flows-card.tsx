import { Card, CardBody } from "@/components/ui/card";
import { SectionHeading } from "@/components/ui/section-heading";
import { formatQuarter, formatShare } from "@/lib/format";
import type { DongFlow } from "@/lib/types";

/**
 * 최근 8분기 거래 흐름. 값의 크기보다 분기별로 늘고 줄었는지가 보이게 막대를 같이 그린다.
 * 막대 길이는 8분기 안에서 가장 많았던 분기를 기준으로 맞춘다.
 */
export function FlowsCard({ flows }: { flows: DongFlow[] }) {
  if (flows.length === 0) return null;
  const scale = Math.max(1, ...flows.map((flow) => Math.max(flow.n_sales, flow.n_jeonse)));

  return (
    <Card>
      <CardBody className="space-y-3">
        <SectionHeading eyebrow="거래 흐름" title="분기별 거래 건수" />
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-muted-foreground">
              <th scope="col" className="pb-1 font-normal">
                분기
              </th>
              <th scope="col" className="pb-1 text-right font-normal">
                매매
              </th>
              <th scope="col" className="pb-1 text-right font-normal">
                전세
              </th>
              <th scope="col" className="pb-1 text-right font-normal">
                월세 비중
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {flows.map((flow) => (
              <tr key={flow.quarter}>
                <th scope="row" className="py-1.5 text-left font-medium text-foreground">
                  {formatQuarter(flow.quarter)}
                </th>
                <td className="py-1.5 text-right tabular-nums text-foreground">
                  <Bar value={flow.n_sales} scale={scale} />
                </td>
                <td className="py-1.5 text-right tabular-nums text-muted-foreground">
                  <Bar value={flow.n_jeonse} scale={scale} />
                </td>
                <td className="py-1.5 text-right tabular-nums text-muted-foreground">
                  {formatShare(flow.monthly_rent_share)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="text-xs text-muted-foreground">
          분기별 신고 건수예요. 신고가 늦어지면 최근 분기가 낮게 보일 수 있어요.
        </p>
      </CardBody>
    </Card>
  );
}

function Bar({ value, scale }: { value: number; scale: number }) {
  return (
    <span className="flex items-center justify-end gap-1.5">
      <span className="h-1.5 w-12 rounded-sm bg-neutral-soft">
        <span
          className="block h-1.5 rounded-sm bg-primary"
          style={{ width: `${(value / scale) * 100}%` }}
        />
      </span>
      <span className="w-10 text-right">{value.toLocaleString("ko-KR")}</span>
    </span>
  );
}
