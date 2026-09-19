import { BrainCircuit } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardBody } from "@/components/ui/card";
import { SectionHeading } from "@/components/ui/section-heading";
import { structureFootnote } from "@/lib/format";
import type { DongStructure, Meta } from "@/lib/types";

/**
 * 구조 유형. 번호(0~3)는 화면에 내지 않고 자동 설명만 보여 준다.
 * 이름을 붙이면 동을 줄 세우는 것으로 읽히기 때문이다(wording-guide.md §3.6).
 */
export function StructureCard({
  structure,
  meta,
}: {
  structure: DongStructure;
  meta: Meta;
}) {
  return (
    <Card>
      <CardBody className="space-y-2">
        <Badge variant="accent" className="gap-1.5">
          <BrainCircuit aria-hidden="true" className="size-3.5" />
          머신러닝 군집화
        </Badge>
        <SectionHeading title="클러스터 성질" />
        <p className="text-sm text-foreground">{structure.desc}</p>
        <p className="text-xs text-muted-foreground">{structureFootnote(meta)}</p>
      </CardBody>
    </Card>
  );
}
