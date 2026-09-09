"use client";
import { memo, useMemo, useState } from "react";
import { Area, CartesianGrid, ComposedChart, Line, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { lttb } from "@/lib/metrics";

// Courbe d'equity + benchmarks toggleables. Downsampling LTTB (~MAX_PTS) recalculé à chaque fenêtre → 60 fps
// sur 2600+ points. Zoom par glisser-sélection (recalcule le downsampling sur la fenêtre). `syncId` synchronise
// le crosshair avec le graphe underwater. Rétrocompatible : sans onWin, le zoom est simplement désactivé.
const MAX_PTS = 600;
const MOIS = ["jan", "fév", "mar", "avr", "mai", "juin", "juil", "août", "sep", "oct", "nov", "déc"];
const shortDate = (t: any) => {
  if (typeof t !== "string") return `J${t}`;
  const d = new Date(t);
  return isNaN(+d) ? t.slice(0, 7) : `${MOIS[d.getMonth()]} ${String(d.getFullYear()).slice(2)}`;
};
const compact = (v: number) => (Math.abs(v) >= 1000 ? `${(v / 1000).toFixed(1)}k` : `${Math.round(v)}`);
// Une référence sans couleur se traçait en `undefined` : ligne invisible, bouton actif —
// le pire des deux mondes, l'utilisateur croit l'avoir affichée. Repli explicite.
// Les teintes sont des TOKENS DE THÈME (globals.css), pas des littéraux : codées en dur,
// elles gardaient la même valeur en clair et en sombre, où le contraste n'est pas le même.
const BCOL: Record<string, string> = {
  "S&P 500": "var(--bench-sp)", "Nasdaq 100": "var(--bench-ndx)", "Bitcoin": "var(--bench-btc)",
};
const col = (n: string) => BCOL[n] ?? "var(--muted)";

// Périodes en JOURS CALENDAIRES, pas en nombre de points : le portefeuille n'est valorisé
// que les jours de passage du cron, donc « 30 points » ne fait pas un mois.
const PERIODES: [string, number][] = [["1M", 30], ["3M", 91], ["6M", 182], ["1A", 365]];

export type Win = { t0: string; t1: string } | null;

function EquityChartBase({ series, benchmarks, height = 260, title, syncId, win, onWin, periodes }:
  { series: any[]; benchmarks?: Record<string, { t: string; v: number }[]>; height?: number; title?: string;
    syncId?: string; win?: Win; onWin?: (w: Win) => void; periodes?: boolean }) {
  const names = Object.keys(benchmarks ?? {});
  const [on, setOn] = useState<Record<string, boolean>>(() => Object.fromEntries(names.map((n) => [n, true])));
  const [sel, setSel] = useState<{ a: string | null; b: string | null }>({ a: null, b: null });

  // fusionne equity + benchmarks par date, applique la fenêtre de zoom, puis downsample.
  const data = useMemo(() => {
    if (!series?.length) return [];
    const idx: Record<string, any> = {};
    series.forEach((p) => (idx[p.t] = { t: p.t, equity: p.v }));
    for (const n of names) (benchmarks![n] ?? []).forEach((p) => { if (idx[p.t]) idx[p.t][n] = p.v; });
    let arr = Object.values(idx) as any[];
    if (win?.t0 && win?.t1) arr = arr.filter((d) => d.t >= win.t0 && d.t <= win.t1);
    return lttb(arr, MAX_PTS);
  }, [series, benchmarks, names, win]);

  if (!series?.length) return null;
  const zoomable = !!onWin;
  const commit = () => {
    if (zoomable && sel.a && sel.b && sel.a !== sel.b) {
      const [t0, t1] = sel.a < sel.b ? [sel.a, sel.b] : [sel.b, sel.a];
      onWin!({ t0, t1 });
    }
    setSel({ a: null, b: null });
  };

  return (
    <div className="card p-4">
      <div className="flex items-center justify-between flex-wrap gap-2 mb-3">
        <div className="text-xs uppercase tracking-wide text-muted">{title ?? "Performance — base 10 000 $ (ptf vs benchmarks)"}</div>
        <div className="flex gap-1.5 items-center">
          {periodes && zoomable && series.length > 1 && (
            <div className="flex gap-1 mr-1">
              {PERIODES.map(([lbl, jours]) => {
                const fin = series[series.length - 1].t as string;
                const t0 = new Date(new Date(fin).getTime() - jours * 864e5).toISOString().slice(0, 10);
                // Une période plus longue que l'historique afficherait « 1A » sur trois
                // mois de données : le bouton est masqué plutôt que trompeur.
                if (t0 < (series[0].t as string)) return null;
                const actif = win?.t0 === t0 && win?.t1 === fin;
                return (
                  <button key={lbl} onClick={() => onWin!({ t0, t1: fin })}
                    className="px-2 py-1 text-xs rounded-full border transition-colors"
                    style={{ borderColor: actif ? "var(--accent)" : "var(--border)",
                             color: actif ? "var(--fg)" : "var(--muted)" }}>{lbl}</button>
                );
              })}
              <button onClick={() => onWin!(null)}
                className="px-2 py-1 text-xs rounded-full border transition-colors"
                style={{ borderColor: !win ? "var(--accent)" : "var(--border)",
                         color: !win ? "var(--fg)" : "var(--muted)" }}>Tout</button>
            </div>
          )}
          {win && zoomable && !periodes && (
            <button onClick={() => onWin!(null)} className="px-2 py-1 text-xs rounded-full border border-border text-muted hover:text-fg transition-colors">
              ↺ zoom
            </button>
          )}
          {names.map((n) => (
            <button key={n} onClick={() => setOn((s) => ({ ...s, [n]: !s[n] }))}
              className="px-2.5 py-1 text-xs rounded-full border transition-colors"
              style={{ borderColor: on[n] ? col(n) : "var(--border)", color: on[n] ? "var(--fg)" : "var(--muted)",
                       background: on[n] ? `color-mix(in srgb, ${col(n)} 14%, transparent)` : "transparent" }}>
              {n}
            </button>
          ))}
        </div>
      </div>
      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart data={data} syncId={syncId} margin={{ top: 6, right: 10, left: 0, bottom: 0 }}
          onMouseDown={zoomable ? (e: any) => e?.activeLabel && setSel({ a: e.activeLabel, b: null }) : undefined}
          onMouseMove={zoomable ? (e: any) => sel.a && e?.activeLabel && setSel((s) => ({ ...s, b: e.activeLabel })) : undefined}
          onMouseUp={zoomable ? commit : undefined}>
          <defs>
            <linearGradient id="eq" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--accent)" stopOpacity={0.35} />
              <stop offset="100%" stopColor="var(--accent)" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="var(--border)" vertical={false} />
          <XAxis dataKey="t" tick={{ fill: "var(--muted)", fontSize: 11 }} tickLine={false} axisLine={false}
                 minTickGap={56} tickMargin={8} tickFormatter={shortDate} />
          <YAxis tick={{ fill: "var(--muted)", fontSize: 11 }} tickLine={false} axisLine={false} width={44}
                 tickCount={5} domain={["dataMin", "dataMax"]} tickFormatter={compact} />
          <Tooltip
            contentStyle={{ background: "var(--surface)", border: "1px solid var(--border2)", borderRadius: 10, fontSize: 12 }}
            labelStyle={{ color: "var(--muted)" }} itemStyle={{ color: "var(--fg)" }}
            formatter={(v: number, n: string) => [`${(v ?? 0).toLocaleString("fr-FR", { maximumFractionDigits: 0 })} $`, n === "equity" ? "Portefeuille" : n]}
            labelFormatter={(l) => (typeof l === "string" ? l.slice(0, 10) : `Point ${l}`)} />
          <Area type="monotone" dataKey="equity" name="Portefeuille" stroke="var(--accent)" strokeWidth={2} fill="url(#eq)" isAnimationActive={false} />
          {names.filter((n) => on[n]).map((n) => (
            <Line key={n} type="monotone" dataKey={n} name={n} stroke={col(n)} strokeWidth={1.4} dot={false} isAnimationActive={false} connectNulls />
          ))}
          {zoomable && sel.a && sel.b && <ReferenceArea x1={sel.a} x2={sel.b} strokeOpacity={0.3} fill="var(--accent)" fillOpacity={0.12} />}
        </ComposedChart>
      </ResponsiveContainer>
      {zoomable && <p className="text-muted2 text-[11px] mt-1.5">Glisse sur le graphe pour zoomer (le tracé se recalcule sur la fenêtre).</p>}
    </div>
  );
}

export const EquityChart = memo(EquityChartBase);
