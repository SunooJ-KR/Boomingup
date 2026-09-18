"use client";

import { ChevronUp } from "lucide-react";
import { useEffect, useState } from "react";

const SHOW_AFTER_PX = 320;

export function ScrollToTop() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const update = () => setVisible(window.scrollY > SHOW_AFTER_PX);
    update();
    window.addEventListener("scroll", update, { passive: true });
    return () => window.removeEventListener("scroll", update);
  }, []);

  const moveToTop = () => {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    window.scrollTo({ top: 0, behavior: reduced ? "auto" : "smooth" });
  };

  return (
    <button
      type="button"
      aria-label="맨 위로 이동"
      onClick={moveToTop}
      className={`fixed bottom-5 right-5 z-40 flex size-10 items-center justify-center rounded-full border border-border bg-card text-foreground shadow-float transition-[opacity,transform] duration-200 hover:-translate-y-0.5 hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 sm:bottom-6 sm:right-6 ${
        visible ? "pointer-events-auto translate-y-0 opacity-100" : "pointer-events-none translate-y-2 opacity-0"
      }`}
    >
      <ChevronUp aria-hidden="true" className="size-5" strokeWidth={2.25} />
    </button>
  );
}
