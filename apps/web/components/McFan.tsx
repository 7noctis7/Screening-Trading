"use client";
import { useMemo, useState } from "react";

// FAN CHART Monte Carlo — bandes de percentiles d'UNE même série (incertitude, pas
// des séries distinctes) → une seule teinte (accent), opacités décroissantes :
// p5–p95 léger, p25–p75 moyen, médiane en trait plein 2px. Un seul axe. Labels
// directs des finals à droite (le texte reste en tokens texte, jamais colorés).
// Survol : crosshair + tooltip (jour + valeurs des 5 percentiles).
export type FanData = {
  steps: number[]; p5: number[]; p25: number[]; p50: number[]; p75: number[]; p95: number[];
};

const fmt = (v: number) =>
  v >= 1000 ? `${(v / 1000).toFixed(v >= 10000 ? 0 : 1)}k` : v.toFixed(0);

function path(xs: number[], ys: number[], X: (i: number) => number, Y: (v: number) => number) {
  return xs.map((_, i) => `${i ? "L" : "M"}${X(i).toFixed(1)},${Y(ys[i]).toFixed(1)}`).join("");
}

function band(xs: number[], lo: number[], hi: number[], X: (i: number) => number, Y: (v: number) => number) {
  const up = xs.map((_, i) => `${i ? "L" : "M"}${X(i).toFixed(1)},${Y(hi[i]).toFixed(1)}`).join("");
  const dn = [...xs.keys()].reverse().map((i) => `L${X(i).toFixed(1)},${Y(lo[i]).toFixed(1)}`).join("");
  return `${up}${dn}Z`;
}

export function McFan({ data, startValue, height = 240 }:
  { data: FanData; startValue: number; height?: number }) {
  const [hov, setHov] = useState<number | null>(null);
  const W = 720, H = height, padL = 8, padR = 64, padT = 10, padB = 22;
  const g = useMemo(() => {
    const all = [...data.p5, ...data.p95, startValue];
    const lo = Math.min(...all), hi = Math.max(...all);
    const span = Math.max(1e-9, hi - lo);
    const X = (i: number) => padL + (i / Math.max(1, data.steps.length - 1)) * (W - padL - padR);
    const Y = (v: number) => padT + (1 - (v - lo) / span) * (H - padT - padB);
    const ticks = [lo, lo + span / 2, hi];
    return { X, Y, ticks };
  }, [data, startValue, H]);
  if (!data?.steps?.length) return null;
  const { X, Y, ticks } = g;
  const last = data.steps.length - 1;
  const onMove = (e: React.MouseEvent<SVGSVGElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    const x = ((e.clientX - r.left) / r.width) * W;
    const i = Math.round(((x - padL) / (W - padL - padR)) * last);
    setHov(Math.max(0, Math.min(last, i)));
  };
  return (
    <div className="relative">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ height }}
        onMouseMove={onMove} onMouseLeave={() => setHov(null)} role="img"
        aria-label="Éventail Monte Carlo : bandes de percentiles p5 à p95 de la valeur projetée">
        {ticks.map((t, i) => (
          <g key={i}>
            <line x1={padL} x2={W - padR} y1={Y(t)} y2={Y(t)} stroke="var(--border)" strokeWidth="1" />
            <text x={padL + 2} y={Y(t) - 3} fontSize="9" fill="var(--muted2)" className="mono">{fmt(t)}</text>
          </g>
        ))}
        <line x1={padL} x2={W - padR} y1={Y(startValue)} y2={Y(startValue)}
          stroke="var(--muted2)" strokeWidth="1" strokeDasharray="4 4" opacity="0.6" />
        <path d={band(data.steps, data.p5, data.p95, X, Y)} fill="var(--accent)" opacity="0.10" />
        <path d={band(data.steps, data.p25, data.p75, X, Y)} fill="var(--accent)" opacity="0.20" />
        <path d={path(data.steps, data.p50, X, Y)} fill="none" stroke="var(--accent)" strokeWidth="2" />
        {/* labels directs des finals — texte en tokens texte (identité = position, pas couleur) */}
        {([["p95", data.p95[last]], ["médiane", data.p50[last]], ["p5", data.p5[last]]] as const).map(([lab, v]) => (
          <text key={lab} x={W - padR + 4} y={Y(v) + 3} fontSize="10" fill="var(--muted)" className="mono">
            {lab} {fmt(v)}
          </text>
        ))}
        {hov != null && (
          <line x1={X(hov)} x2={X(hov)} y1={padT} y2={H - padB} stroke="var(--muted2)" strokeWidth="1" opacity="0.7" />
        )}
        <text x={padL} y={H - 6} fontSize="9" fill="var(--muted2)">j+{data.steps[0]}</text>
        <text x={W - padR} y={H - 6} fontSize="9" fill="var(--muted2)" textAnchor="end">j+{data.steps[last]}</text>
      </svg>
      {hov != null && (
        <div className="absolute top-2 pointer-events-none rounded-lg border border-border px-2.5 py-1.5 text-[11px] mono"
          style={{ left: `${(X(hov) / W) * 100}%`, transform: X(hov) > W / 2 ? "translateX(-105%)" : "translateX(8px)",
                   background: "var(--surface)", boxShadow: "0 4px 16px rgba(0,0,0,.35)" }}>
          <div className="text-muted2">jour +{data.steps[hov]}</div>
          {([["p95", data.p95], ["p75", data.p75], ["médiane", data.p50], ["p25", data.p25], ["p5", data.p5]] as const)
            .map(([lab, arr]) => (
              <div key={lab} className="flex justify-between gap-3">
                <span className="text-muted">{lab}</span><span>{fmt(arr[hov])}</span>
              </div>
            ))}
        </div>
      )}
    </div>
  );
}
