"use client";
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid } from "recharts";

// Graphique d'equity INTERACTIF : tooltip + crosshair au survol (Recharts).
export function EquityChart({ series, height = 240 }: { series: any[]; height?: number }) {
  if (!series?.length) return null;
  return (
    <div className="card p-4">
      <div className="text-xs uppercase tracking-wide text-muted mb-2">Equity (survole la courbe)</div>
      <ResponsiveContainer width="100%" height={height}>
        <AreaChart data={series} margin={{ top: 6, right: 6, left: -18, bottom: 0 }}>
          <defs>
            <linearGradient id="eq" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.35} />
              <stop offset="100%" stopColor="#3b82f6" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="#262a31" vertical={false} />
          <XAxis dataKey="t" tick={{ fill: "#9aa1ab", fontSize: 11 }} tickLine={false} axisLine={false} minTickGap={40} />
          <YAxis tick={{ fill: "#9aa1ab", fontSize: 11 }} tickLine={false} axisLine={false} width={48}
                 domain={["dataMin", "dataMax"]} />
          <Tooltip
            contentStyle={{ background: "#000", border: "1px solid #262a31", borderRadius: 8, fontSize: 12 }}
            labelStyle={{ color: "#9aa1ab" }} itemStyle={{ color: "#e6e8eb" }}
            formatter={(v: number) => [v.toFixed(2), "Equity"]} labelFormatter={(l) => `Point ${l}`} />
          <Area type="monotone" dataKey="v" stroke="#3b82f6" strokeWidth={2} fill="url(#eq)" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
