import { Card, CardBody } from "@/components/ui/card";
import { SectionHeading } from "@/components/ui/section-heading";
import { formatShare, indexSeBandSentence, sampleFlagSentences, sampleFootnote } from "@/lib/format";
import type { DongSample, Meta } from "@/lib/types";

type SampleCardProps = {
  sample: DongSample;
  meta: Meta;
};

/**
 * 화면 첫 블록. 변화율을 보기 전에 그 변화율을 얼마나 믿고 읽을지부터 알려 준다.
 * 추정오차 구간 옆에는 항상 매매 건수를 둔다. 오차가 낮은 이유가 거래가 많아서라는 것이 보이게(wording-guide.md §3.2).
 */
export function SampleCard({ sample, meta }: SampleCardProps) {
  const sentences = sampleFlagSentences(sample.flags);
  const band = indexSeBandSentence(sample.index_se_band);

  return (
    <Card>
      <CardBody className="space-y-3">
        <SectionHeading eyebrow="표본 상태" title="이 동의 거래는 얼마나 있었나요" />

        {sentences.length > 0 ? (
          <ul className="space-y-1">
            {sentences.map((sentence) => (
              <li key={sentence} className="text-sm text-foreground">
                {sentence}
              </li>
            ))}
          </ul>
        ) : null}

        <dl className="grid grid-cols-2 gap-3 text-sm">
          <Fact label="최근 1년 매매" value={`${sample.n_sales_4q}건`} />
          <Fact
            label="거래된 단지"
            value={sample.n_complexes_4q === null ? "-" : `${sample.n_complexes_4q}곳`}
          />
          <Fact
            label="가장 많이 거래된 단지 비중"
            value={formatShare(sample.dominant_complex_share_4q)}
          />
          <Fact label="지수 추정오차" value={band ?? "-"} />
        </dl>

        <p className="text-xs text-muted-foreground">{sampleFootnote(meta)}</p>
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
