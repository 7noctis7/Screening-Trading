"use client";
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid } from "recharts";

// Courbe d'equity interactive — axes lisibles (dates courtes, montants compacts), crosshair au survol.
const MOIS = ["jan", "fév", "mar", "avr", "mai", "juin", "juil", "août", "sep", "oct", "nov", "déc"];
const shortDate = (t: any) => {
  if (typeof t !== "string") return `J${t}`;
  const d = new Date(t);
  return isNaN(+d) ? t.slice(0, 7) : `${MOIS[d.getMonth()]} ${String(d.getFullYear()).slice(2)}`;
};
const compact = (v: number) =>
  Math.abs(v) >= 1000 ? `${(v / 1000).toFixed(1)}k` : `${Math.round(v)}`;

export function EquityChart({ series, height = 260 }: { series: any[]; height?: number }) {
  if (!series?.length) return null;
  return (
    <div className="card p-4">
      <div className="text-xs uppercase tracking-wide text-muted mb-3">Performance du portefeuille ($)</div>
      <ResponsiveContainer width="100%" height={height}>
        <AreaChart data={series} margin={{ top: 6, right: 10, left: 0, bottom: 0 }}>
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
            formatter={(v: number) => [`${v.toLocaleString("fr-FR", { maximumFractionDigits: 0 })} $`, "Equity"]}
            labelFormatter={(l) => (typeof l === "string" ? l.slice(0, 10) : `Point ${l}`)} />
          <Area type="monotone" dataKey="v" stroke="var(--accent)" strokeWidth={2} fill="url(#eq)" isAnimationActive={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
