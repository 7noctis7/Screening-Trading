"use client";
// Le cadre commun des cartes du cockpit crypto : titre, SOURCE, explication, contenu.
// La source n'est pas décorative — une carte sans source est une affirmation sans preuve.
import { useEffect, useRef, useState } from "react";

// Révélation au scroll (lazy, IntersectionObserver) — neutralisée si prefers-reduced-motion.
export function Reveal({ children }: { children: React.ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  const [shown, setShown] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) { setShown(true); return; }
    const io = new IntersectionObserver(
      (es) => es.forEach((e) => e.isIntersecting && (setShown(true), io.disconnect())),
      { threshold: 0.12 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);
  return (
    <div ref={ref} style={{
      opacity: shown ? 1 : 0,
      transform: shown ? "none" : "translateY(20px)",
      transition: "opacity .6s cubic-bezier(.16,1,.3,1), transform .6s cubic-bezier(.16,1,.3,1)",
    }}>{children}</div>
  );
}

export function Card({ title, source, hint, children }: {
  title: string; source: string; hint: string; children: React.ReactNode;
}) {
  return (
    <Reveal>
      <section className="card p-4">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <h2 className="text-sm uppercase tracking-wide text-muted">{title}</h2>
          <span className="text-[11px] text-muted2">{source}</span>
        </div>
        <p className="text-muted2 text-xs mt-1">{hint}</p>
        <div className="mt-3">{children}</div>
      </section>
    </Reveal>
  );
}
