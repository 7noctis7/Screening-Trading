"use client";
import { Area, AreaChart, ResponsiveContainer } from "recharts";

// Playbook VIX : régime de volatilité + action recommandée + mini-courbe du VIX.
const palette: Record<string, string> = {
  calme: "#22c55e", normal: "#3b82f6", tendu: "#f59e0b", panique: "#ef4444",
};

export function VixPlaybook({ vix, playbook, series = [] }:
  { vix: number; playbook: any; series?: number[] }) {
  if (!playbook) return null;
  const c = playbook.color ?? palette[playbook.regime] ?? "#9aa1ab";
  const spark = series.map((v, i) => ({ i, v }));
  return (
    <div className="card p-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="text-muted text-xs uppercase tracking-wide">Playbook VIX</div>
          <div className="flex items-baseline gap-2 mt-1">
            <span className="text-2xl mono">{vix?.toFixed?.(1) ?? "—"}</span>
            <span className="capitalize font-medium" style={{ color: c }}>{playbook.regime}</span>
            <span className="text-muted text-sm">· exposition ×{playbook.exposure}</span>
          </div>
        </div>
        {spark.length > 1 && (
          <div className="w-32 h-12">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={spark} margin={{ top: 4, right: 0, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="vixg" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={c} stopOpacity={0.4} />
                    <stop offset="100%" stopColor={c} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <Area type="monotone" dataKey="v" stroke={c} strokeWidth={1.5} fill="url(#vixg)" isAnimationActive={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
      <p className="text-sm text-muted mt-2 font-sans" style={{ borderLeft: `3px solid ${c}`, paddingLeft: 10 }}>
        {playbook.action}
      </p>
    </div>
  );
}
