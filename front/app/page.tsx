import { DongExplorer } from "@/components/dong/dong-explorer";
import { guNamesOf, loadIndex, tagsOf } from "@/lib/data";
import { formatQuarter } from "@/lib/format";

// 동 목록은 자주 바뀌지 않으므로 10분마다 다시 만든다. snapshot이 교체되면 그때 반영된다.
export const revalidate = 600;

export default async function Home() {
  const { meta, dongs, source } = await loadIndex();

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-10 border-b border-border bg-card/95 backdrop-blur">
        <div className="mx-auto flex max-w-[1400px] flex-wrap items-baseline gap-x-3 gap-y-1 px-4 py-3">
          <span className="text-base font-bold text-foreground">Boomingup</span>
          <span className="text-xs text-muted-foreground">
            기준 {formatQuarter(meta.as_of_quarter)} · 매매 {meta.data_period.sale}
          </span>
        </div>
      </header>

      <main className="mx-auto max-w-[1400px] px-4 py-4">
        {source === "sample" ? (
          <p className="mb-3 rounded-md border border-border bg-card px-3 py-2 text-xs text-muted-foreground">
            데이터베이스에 연결하지 못해 샘플 데이터를 보여주고 있습니다. 실제 수치가 아닙니다.
          </p>
        ) : null}

        <DongExplorer
          dongs={dongs}
          meta={meta}
          guNames={guNamesOf(dongs)}
          tags={tagsOf(dongs)}
        />
      </main>
    </div>
  );
}
