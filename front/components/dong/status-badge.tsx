import { Badge } from "@/components/ui/badge";
import { statusLabel } from "@/lib/format";
import type { PredictionStatus } from "@/lib/types";

export function StatusBadge({ status }: { status: PredictionStatus }) {
  return (
    <Badge variant={status === "PREDICTED" ? "accent" : "neutral"}>
      {status === "PREDICTED" ? "PREDICTED" : statusLabel(status)}
    </Badge>
  );
}
