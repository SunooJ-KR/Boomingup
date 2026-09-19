"use client";

import { BrainCircuit } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardBody } from "@/components/ui/card";
import { SectionHeading } from "@/components/ui/section-heading";
import type { DongPeer } from "@/lib/types";

type PeersCardProps = {
  peers: DongPeer[];
  onSelect: (dongId: string) => void;
};

/**
 * 함께 볼 동. 표시 조건을 못 채운 동은 payload에서 peers가 null이라 이 카드를 아예 그리지 않는다.
 * "비교할 동이 없어요" 같은 문장도 쓰지 않는다(wording-guide.md §3.7).
 */
export function PeersCard({ peers, onSelect }: PeersCardProps) {
  return (
    <Card>
      <CardBody className="space-y-3">
        <div className="space-y-2">
          <Badge variant="accent" className="gap-1.5">
            <BrainCircuit aria-hidden="true" className="size-3.5" />
            머신러닝 유사도 탐색
          </Badge>
          <SectionHeading
            title="함께 볼 동"
            description="같은 묶음 안에서 특성이 가장 비슷한 동이에요."
          />
        </div>
        <ul className="space-y-1.5">
          {peers.map((peer) => (
            <li key={peer.dong_id}>
              <button
                type="button"
                onClick={() => onSelect(peer.dong_id)}
                className="flex w-full items-baseline justify-between gap-2 break-keep rounded-md border border-border bg-card px-3 py-2 text-left transition-transform duration-150 ease-[var(--ease-out-soft)] hover:-translate-y-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <span className="text-sm font-medium text-foreground">
                  {peer.gu_name} {peer.umd_name}
                </span>
                <span className="shrink-0 text-xs text-muted-foreground">{peer.reason}</span>
              </button>
            </li>
          ))}
        </ul>
      </CardBody>
    </Card>
  );
}
