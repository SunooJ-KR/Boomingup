import { Badge } from "@/components/ui/badge";
import { Card, CardBody } from "@/components/ui/card";
import { SectionHeading } from "@/components/ui/section-heading";
import { formatManwon } from "@/lib/format";
import type { Complex } from "@/lib/types";

export function ComplexList({ complexes }: { complexes: Complex[] }) {
  return (
    <Card>
      <CardBody className="space-y-3">
        <SectionHeading eyebrow="단지" title="단지와 최근 거래" />
        {complexes.length === 0 ? (
          <p className="text-sm text-muted-foreground">표시할 단지 정보가 없습니다.</p>
        ) : (
          <ul className="divide-y divide-border">
            {complexes.map((complex) => (
              <li key={complex.apt_seq} className="py-3 first:pt-0 last:pb-0">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="text-sm font-medium text-foreground">{complex.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {[
                        complex.built_year ? `${complex.built_year}년 준공` : null,
                        complex.households
                          ? `${complex.households.toLocaleString("ko-KR")}세대`
                          : null,
                        complex.far_pct ? `용적률 ${complex.far_pct}%` : null,
                      ]
                        .filter(Boolean)
                        .join(" · ")}
                    </p>
                  </div>
                  {complex.redevelop ? (
                    <Badge variant="neutral">{complex.redevelop.stage}</Badge>
                  ) : null}
                </div>
                {complex.last_sale ? (
                  <p className="mt-1.5 text-xs text-muted-foreground">
                    최근 거래 {complex.last_sale.date} ·{" "}
                    {complex.last_sale.area_m2 ? `${complex.last_sale.area_m2}㎡ · ` : ""}
                    {complex.last_sale.floor ? `${complex.last_sale.floor}층 · ` : ""}
                    {formatManwon(complex.last_sale.price_manwon)}
                  </p>
                ) : (
                  <p className="mt-1.5 text-xs text-muted-foreground">최근 매매 기록이 없습니다.</p>
                )}
              </li>
            ))}
          </ul>
        )}
      </CardBody>
    </Card>
  );
}
