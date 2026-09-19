export default function Loading() {
  return (
    <div className="min-h-dvh" aria-busy="true">
      <header className="sticky top-0 z-10 border-b border-border bg-card/95 backdrop-blur">
        <div className="mx-auto flex max-w-[1600px] items-center gap-3 px-4 py-3">
          <span className="text-base font-bold text-foreground">Boomingup</span>
          <Skeleton className="h-3 w-36 rounded-full" />
        </div>
      </header>

      <main className="mx-auto max-w-[1600px] px-4 py-4">
        <div className="grid gap-4 lg:grid-cols-[minmax(18rem,22.5rem)_minmax(0,1fr)] xl:gap-5 2xl:grid-cols-[minmax(20rem,25rem)_minmax(0,1fr)]">
          <section
            aria-label="지역 탐색 준비 중"
            className="space-y-4 lg:flex lg:h-[var(--app-column-h)] lg:flex-col lg:space-y-0 lg:pr-1"
          >
            <div className="rounded-lg border border-border bg-card p-4 shadow-panel lg:mb-3 lg:shrink-0 lg:p-3 2xl:mb-4 2xl:p-4">
              <div role="status" aria-live="polite" className="flex items-start justify-between gap-4">
                <div>
                  <h1 className="text-lg font-bold text-foreground">
                    서울의 동네 정보를 불러오고 있어요
                  </h1>
                  <p className="mt-1 text-sm text-muted-foreground">
                    법정동 목록과 지도를 준비하고 있어요.
                  </p>
                </div>
                <LoadingDots />
              </div>

              <div aria-hidden="true" className="mt-5 space-y-4">
                <div className="space-y-2">
                  <Skeleton className="h-3 w-20 rounded-full" />
                  <Skeleton className="h-12 w-full rounded-md" />
                </div>
                <div className="space-y-2 rounded-md bg-muted p-3">
                  <Skeleton className="h-3 w-16 rounded-full" />
                  <Skeleton className="h-11 w-full rounded-md bg-card" />
                </div>
                <Skeleton className="h-11 w-full rounded-md" />
                <div className="flex items-center justify-between border-t border-border pt-3">
                  <Skeleton className="h-3 w-24 rounded-full" />
                  <Skeleton className="h-7 w-16 rounded-md" />
                </div>
              </div>
            </div>

            <div aria-hidden="true" className="flex items-center gap-2 pb-1.5 lg:shrink-0 2xl:pb-2">
              <Skeleton className="h-8 flex-1 rounded-md bg-card" />
              <Skeleton className="h-7 w-28 rounded-md bg-card" />
            </div>

            <div aria-hidden="true" className="space-y-2 lg:min-h-0 lg:flex-1 lg:overflow-hidden">
              {Array.from({ length: 7 }, (_, index) => (
                <div
                  key={index}
                  className="rounded-lg border border-border bg-card px-3 py-2.5 shadow-panel lg:py-2 2xl:py-2.5"
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                      <Skeleton className="h-4 w-16 rounded-full" />
                      <Skeleton className="h-3 w-12 rounded-full" />
                    </div>
                    {index % 3 === 0 ? <Skeleton className="h-5 w-10 rounded-sm" /> : null}
                  </div>
                  <Skeleton className="mt-2 h-3 w-28 rounded-full" />
                </div>
              ))}
            </div>
          </section>

          <MapSkeleton />
        </div>
      </main>
    </div>
  );
}

function Skeleton({ className }: { className: string }) {
  return <div className={`skeleton-shimmer bg-neutral-soft ${className}`} />;
}

function LoadingDots() {
  return (
    <span aria-hidden="true" className="mt-1 flex h-6 shrink-0 items-center gap-1">
      {[0, 1, 2].map((dot) => (
        <span
          key={dot}
          className="loading-dot size-1.5 rounded-full bg-primary"
          style={{ animationDelay: `${dot * 160}ms` }}
        />
      ))}
    </span>
  );
}

function MapSkeleton() {
  const markers = [
    { left: "21%", top: "31%" },
    { left: "42%", top: "56%" },
    { left: "63%", top: "28%" },
    { left: "77%", top: "66%" },
    { left: "54%", top: "77%" },
  ];

  return (
    <section
      aria-hidden="true"
      className="overflow-hidden rounded-lg border border-border bg-card shadow-panel lg:flex lg:h-[var(--app-column-h)] lg:flex-col"
    >
      <div className="flex items-center justify-between border-b border-border px-3 py-2">
        <Skeleton className="h-3 w-9 rounded-full" />
        <Skeleton className="h-3 w-16 rounded-full" />
      </div>
      <div className="skeleton-shimmer relative h-[var(--map-mobile-h)] overflow-hidden bg-neutral-soft lg:h-auto lg:min-h-0 lg:flex-1">
        <div className="absolute left-[4%] top-[20%] h-2 w-[88%] rotate-6 rounded-full bg-card/75" />
        <div className="absolute left-[12%] top-[58%] h-2 w-[80%] -rotate-12 rounded-full bg-card/70" />
        <div className="absolute left-[30%] top-[-5%] h-[110%] w-2 rotate-12 rounded-full bg-card/65" />
        <div className="absolute left-[68%] top-[-5%] h-[110%] w-2 -rotate-6 rounded-full bg-card/65" />
        {markers.map((marker, index) => (
          <span
            key={`${marker.left}-${marker.top}`}
            className="loading-marker absolute size-3 rounded-full border-2 border-card bg-primary"
            style={{
              left: marker.left,
              top: marker.top,
              animationDelay: `${index * 220}ms`,
            }}
          />
        ))}
      </div>
    </section>
  );
}
