"use client";
import { useEffect, useRef, useState } from "react";

// Info-bulle de glossaire : petit « ⓘ » qui révèle une définition au survol ET au clic
// (clic = tactile/mobile + accessibilité clavier). Aucune donnée inventée : du texte
// pédagogique figé. Se ferme au clic dehors ou Échap.
export function InfoTip({ label, children }: { label: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <span ref={ref} className="relative inline-flex group align-middle">
      <button
        type="button"
        aria-label={`Définition : ${label}`}
        onClick={() => setOpen((v) => !v)}
        className="inline-grid place-items-center w-[15px] h-[15px] rounded-full border border-border text-[10px] text-muted2 hover:text-fg hover:border-border2 transition-colors cursor-help"
      >
        i
      </button>
      <span
        role="tooltip"
        className={`absolute left-1/2 -translate-x-1/2 bottom-full mb-1.5 z-50 w-[240px] rounded-lg border border-border p-2.5 text-[12px] leading-snug text-fg shadow-xl transition-opacity duration-150 ${
          open ? "opacity-100" : "opacity-0 pointer-events-none"
        } group-hover:opacity-100 group-hover:pointer-events-auto`}
        style={{
          background: "color-mix(in srgb, var(--surface) 96%, transparent)",
          backdropFilter: "blur(10px)",
          WebkitBackdropFilter: "blur(10px)",
        }}
      >
        <b className="block mb-0.5 text-[11px] uppercase tracking-wide text-muted">{label}</b>
        <span className="text-muted">{children}</span>
      </span>
    </span>
  );
}
