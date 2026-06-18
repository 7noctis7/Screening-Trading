"use client";
import { useMemo, useState } from "react";
import { Area, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

// Courbe d'equity + benchmarks (S&P 500, Nasdaq) toggleables. Axes lisibles, crosshair au survol.
const MOIS = ["jan", "fév", "mar", "avr", "mai", "juin", "juil", "août", "sep", "oct", "nov", "déc"];
const shortDate = (t: any) => {
  if (typeof t !== "string") return `J${t}`;
  const d = new Date(t);
  return isNaN(+d) ? t.slice(0, 7) : `${MOIS[d.getMonth()]} ${String(d.getFullYear()).slice(2)}`;
};
const compact = (v: number) => (Math.abs(v) >= 1000 ? `${(v / 1000).toFixed(1)}k` : `${Math.round(v)}`);
const BCOL: Record<string, string> = { "S&P 500": "#f59e0b", "Nasdaq 100": "#a855f7" };

export function EquityChart({ series, benchmarks, height = 260 }:
  { series: any[]; benchmarks?: Record<string, { t: string; v: number }[]>; height?: number }) {
  const names = Object.keys(benchmarks ?? {});
  const [on, setOn] = useState<Record<string, boolean>>(() => Object.fromEntries(names.map((n) => [n, true])));
  // fusionne equity + benchmarks par date (overlay)
  const data = useMemo(() => {
    if (!series?.length) return [];
    const idx: Record<string, any> = {};
    series.forEach((p) => (idx[p.t] = { t: p.t, equity: p.v }));
    for (const n of names) (benchmarks![n] ?? []).forEach((p) => { if (idx[p.t]) idx[p.t][n] = p.v; });
    return Object.values(idx);
  }, [series, benchmarks]);
  if (!series?.length) return null;
  return (
    <div className="card p-4">
      <div className="flex items-center justify-between flex-wrap gap-2 mb-3">
        <div className="text-xs uppercase tracking-wide text-muted">Performance — base 10 000 $ (ptf vs benchmarks)</div>
        <div className="flex gap-1.5">
          {names.map((n) => (
            <button key={n} onClick={() => setOn((s) => ({ ...s, [n]: !s[n] }))}
              className="px-2.5 py-1 text-xs rounded-full border transition-colors"
              style={{ borderColor: on[n] ? BCOL[n] : "var(--border)", color: on[n] ? "var(--fg)" : "var(--muted)",
                       background: on[n] ? `color-mix(in srgb, ${BCOL[n]} 14%, transparent)` : "transparent" }}>
              {n}
            </button>
          ))}
        </div>
      </div>
      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart data={data} margin={{ top: 6, right: 10, left: 0, bottom: 0 }}>
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
            <Line key={n} type="monotone" dataKey={n} name={n} stroke={BCOL[n]} strokeWidth={1.4} dot={false} isAnimationActive={false} connectNulls />
          ))}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
