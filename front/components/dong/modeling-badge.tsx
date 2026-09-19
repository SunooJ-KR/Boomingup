import { BrainCircuit } from "lucide-react";

import { Badge } from "@/components/ui/badge";

export function ModelingBadge({ label }: { label: string }) {
  return (
    <Badge variant="accent" className="gap-1.5">
      <BrainCircuit aria-hidden="true" className="size-3.5" />
      데이터 모델링 · {label}
    </Badge>
  );
}
