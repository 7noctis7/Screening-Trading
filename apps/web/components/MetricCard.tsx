"use client";
import { useEffect, useRef, useState } from "react";

// Carte KPI avec compteur animé (count-up) sur la partie numérique, préfixe/suffixe préservés.
// Respecte prefers-reduced-motion (affichage direct). tone = couleur sémantique P&L/risque.
export function MetricCard({ label, value, tone, hero }:
  { label: string; value: string; tone?: "pos" | "neg"; hero?: boolean }) {
  const color = tone === "pos" ? "text-pos" : tone === "neg" ? "text-neg" : "text-fg";
  const display = useCountUp(value);
  return (
    <div className={`card ${hero ? "p-5" : "p-4"}`}>
      <div className="text-muted text-[11px] uppercase tracking-[0.08em]">{label}</div>
      <div className={`mono mt-1 ${color} ${hero ? "text-3xl md:text-4xl font-semibold tracking-tight" : "text-2xl"}`}>
        {display}
      </div>
    </div>
  );
}

// Anime la 1ʳᵉ valeur numérique trouvée dans la chaîne (ex. "+12.3%" → 0…12.3), garde le reste.
function useCountUp(value: string, dur = 650): string {
  const [out, setOut] = useState(value);
  const raf = useRef(0);
  useEffect(() => {
    const m = value.match(/-?\d+(?:[.,]\d+)?/);
    const reduced = typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (!m || reduced) { setOut(value); return; }
    const raw = m[0].replace(",", ".");
    const target = parseFloat(raw);
    const decimals = (raw.split(".")[1] || "").length;
    const pre = value.slice(0, m.index), post = value.slice((m.index ?? 0) + m[0].length);
    const t0 = performance.now();
    const tick = (now: number) => {
      const k = Math.min(1, (now - t0) / dur);
      const e = 1 - Math.pow(1 - k, 3);                 // ease-out cubic
      setOut(`${pre}${(target * e).toFixed(decimals)}${post}`);
      if (k < 1) raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf.current);
  }, [value, dur]);
  return out;
}
