import { Card, CardBody } from "@/components/ui/card";
import { InfoTooltip } from "@/components/ui/info-tooltip";

/** 동을 선택했을 때 숫자보다 먼저 보여 주는 초보자용 읽기 순서. */
export function InterpretationGuide() {
  return (
    <Card className="border-primary/20 bg-primary-soft">
      <CardBody className="space-y-3">
        <div>
          <p className="text-xs font-semibold tracking-wide text-primary">먼저 읽어보세요</p>
          <h2 className="mt-1 text-base font-bold text-foreground">이 화면은 이렇게 해석하세요</h2>
        </div>

        <ol className="grid gap-2 text-sm sm:grid-cols-3">
          <GuideStep number="1" title="표본 상태부터">
            거래가 적거나 한 단지에 몰렸다면 뒤의 변화율도 조심해서 보세요.
          </GuideStep>
          <GuideStep number="2" title="1년 전과 비교">
            <InfoTooltip
              label="가격 지수"
              description="여러 아파트 거래를 모아 이 동의 전반적인 가격 수준을 나타낸 값이에요. 특정 단지의 실제 거래가격과는 달라요."
            />가 1년 전보다 얼마나 달라졌는지 확인하세요. 미래를 말하는 수치가 아니에요.
          </GuideStep>
          <GuideStep number="3" title="사실정보는 따로">
            거래·전세·입주 정보를 함께 보되, 한 수치만으로 변화의 원인을 단정하지 마세요.
          </GuideStep>
        </ol>
      </CardBody>
    </Card>
  );
}

function GuideStep({
  number,
  title,
  children,
}: {
  number: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <li className="rounded-md bg-card/80 p-3">
      <div className="flex items-center gap-2 font-semibold text-foreground">
        <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-primary text-xs text-primary-foreground">
          {number}
        </span>
        {title}
      </div>
      <p className="mt-2 leading-relaxed text-muted-foreground">{children}</p>
    </li>
  );
}
