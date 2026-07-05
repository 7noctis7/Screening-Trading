"use client";
import { memo, useMemo } from "react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { lttb, underwater, type Point } from "@/lib/metrics";
import type { Win } from "@/components/EquityChart";

// Underwater plot (drawdown) — dérivé client depuis l'equity (v/running_max − 1 ≤ 0). Placé SOUS l'equity,
// `syncId` identique → axe X et crosshair synchronisés. Downsampling LTTB (~600 pts) recalculé à chaque fenêtre.
// Couleur --neg en faible opacité (contexte défensif, pas une valeur de P&L à lire au chiffre près).
const MAX_PTS = 600;
const MOIS = ["jan", "fév", "mar", "avr", "mai", "juin", "juil", "août", "sep", "oct", "nov", "déc"];
const shortDate = (t: any) => {
  if (typeof t !== "string") return `J${t}`;
  const d = new Date(t);
  return isNaN(+d) ? t.slice(0, 7) : `${MOIS[d.getMonth()]} ${String(d.getFullYear()).slice(2)}`;
};

function DrawdownChartBase({ series, height = 130, syncId, win }:
  { series: Point[]; height?: number; syncId?: string; win?: Win }) {
  const data = useMemo(() => {
    // underwater() porte déjà `.v` (≤ 0) → downsampler DESSUS (LTTB clé sur `.v`), jamais après renommage
    // (sinon aires NaN → LTTB dégénère en 1er-point-par-bucket et perd les creux → pire DD sous-estimé).
    let dd = underwater(series ?? []);
    if (win?.t0 && win?.t1) dd = dd.filter((d) => d.t >= win.t0 && d.t <= win.t1);
    return lttb(dd, MAX_PTS);
  }, [series, win]);
  const worst = useMemo(() => (data.length ? Math.min(...data.map((d) => d.v)) : 0), [data]);
  if (!series?.length) return null;
  return (
    <div className="card p-4">
      <div className="flex items-center justify-between mb-2">
        <div className="text-xs uppercase tracking-wide text-muted">Drawdown (underwater) — profondeur sous les plus-hauts</div>
        <div className="mono text-xs text-muted tnum">pire : <b style={{ color: "var(--neg)" }}>{(worst * 100).toFixed(1)}%</b></div>
      </div>
      <ResponsiveContainer width="100%" height={height}>
        <AreaChart data={data} syncId={syncId} margin={{ top: 4, right: 10, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="dd" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--neg)" stopOpacity={0.02} />
              <stop offset="100%" stopColor="var(--neg)" stopOpacity={0.28} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="var(--border)" vertical={false} />
          <XAxis dataKey="t" tick={{ fill: "var(--muted)", fontSize: 11 }} tickLine={false} axisLine={false}
                 minTickGap={56} tickMargin={8} tickFormatter={shortDate} />
          <YAxis tick={{ fill: "var(--muted)", fontSize: 11 }} tickLine={false} axisLine={false} width={44}
                 tickCount={4} domain={["dataMin", 0]} tickFormatter={(v: number) => `${Math.round(v * 100)}%`} />
          <Tooltip
            contentStyle={{ background: "var(--surface)", border: "1px solid var(--border2)", borderRadius: 10, fontSize: 12 }}
            labelStyle={{ color: "var(--muted)" }} itemStyle={{ color: "var(--neg)" }}
            formatter={(v: number) => [`${(v * 100).toFixed(1)} %`, "Drawdown"]}
            labelFormatter={(l) => (typeof l === "string" ? l.slice(0, 10) : `Point ${l}`)} />
          <Area type="monotone" dataKey="v" stroke="var(--neg)" strokeWidth={1.2} fill="url(#dd)" isAnimationActive={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export const DrawdownChart = memo(DrawdownChartBase);
