import { Badge } from "@/components/ui/badge";
import { sampleFlagBadges } from "@/lib/format";
import type { SampleFlag } from "@/lib/types";

/**
 * 표본 주의 배지. flag가 없으면 아무것도 그리지 않는다.
 * "주의 없음" 배지를 두지 않는 이유는 없음을 좋음으로 읽기 때문이다(wording-guide.md §3.1).
 */
export function FlagBadges({ flags }: { flags: SampleFlag[] }) {
  const labels = sampleFlagBadges(flags);
  if (labels.length === 0) return null;

  return (
    <div className="flex flex-wrap justify-end gap-1">
      {labels.map((label) => (
        <Badge key={label} variant="neutral">
          {label}
        </Badge>
      ))}
    </div>
  );
}
