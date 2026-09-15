import { DongExplorer } from "@/components/dong/dong-explorer";
import { getAllDongDetails, getDongs, getGuNames, getMeta, getTags } from "@/lib/data";
import { formatQuarter } from "@/lib/format";

export default function Home() {
  const meta = getMeta();

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
        <DongExplorer
          dongs={getDongs()}
          details={getAllDongDetails()}
          meta={meta}
          guNames={getGuNames()}
          tags={getTags()}
        />
      </main>
    </div>
  );
}
