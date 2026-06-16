"use client";
import { useThemes } from "@/lib/api";

const pct = (x: number) => `${(x * 100).toFixed(1)}%`;
const STANCE: Record<string, [string, string]> = {
  bullish: ["#22c55e", "▲ bullish"],
  bearish: ["#ef4444", "▼ bearish"],
  neutral: ["#9aa1ab", "– neutre"],
};

export default function Themes() {
  const { data: th } = useThemes();
  if (!th) return <div className="p-8 text-muted">Chargement…</div>;
  const sectors = th.sectors ?? [];
  const maxAbs = Math.max(0.01, ...sectors.map((s: any) => Math.abs(s.ytd)));
  return (
    <main className="max-w-5xl mx-auto p-6 space-y-4">
      <h1 className="text-xl font-semibold tracking-tight">Thèmes de marché</h1>

      <div className="card p-4 flex flex-wrap justify-between gap-2 text-sm">
        <div><span style={{ color: "#22c55e" }}>▲ Bullish :</span> {(th.bullish ?? []).join(" · ") || "—"}</div>
        <div><span style={{ color: "#ef4444" }}>▼ Bearish :</span> {(th.bearish ?? []).join(" · ") || "—"}</div>
      </div>

      <section className="card p-4">
        <h2 className="text-sm uppercase tracking-wide text-muted mb-3">Performance YTD par secteur</h2>
        <div className="space-y-1.5">
          {sectors.map((s: any) => {
            const col = STANCE[s.stance]?.[0] ?? "#9aa1ab";
            return (
              <div key={s.sector} className="flex items-center gap-2 text-xs">
                <span className="w-40">{s.sector}</span>
                <span className="h-1.5 rounded" style={{ width: `${Math.round((Math.abs(s.ytd) / maxAbs) * 100)}%`, maxWidth: 360, background: col }} />
                <span className="mono w-16 text-right" style={{ color: col }}>{pct(s.ytd)}</span>
              </div>
            );
          })}
        </div>
      </section>

      <section className="card p-4 overflow-x-auto">
        <h2 className="text-sm uppercase tracking-wide text-muted mb-3">Meilleurs setups par secteur (momentum + tendance vs MM50)</h2>
        <table className="w-full text-sm">
          <thead className="text-muted text-xs">
            <tr><th className="text-left font-normal">Secteur</th><th className="text-right font-normal">YTD</th>
            <th className="text-left font-normal pl-3">Top actifs / setup</th></tr>
          </thead>
          <tbody>{sectors.map((s: any) => {
            const col = STANCE[s.stance]?.[0] ?? "#9aa1ab";
            return (
              <tr key={s.sector} className="border-t border-border align-top">
                <td className="py-2">
                  <span className="text-[11px]" style={{ color: col }}>{STANCE[s.stance]?.[1]}</span>
                  <br /><b>{s.sector}</b>
                </td>
                <td className="text-right mono" style={{ color: col }}>{pct(s.ytd)}</td>
                <td className="pl-3">
                  {(s.top_assets ?? []).map((a: any) => (
                    <span key={a.symbol} className="inline-block mr-1.5 mb-1 px-2 py-0.5 rounded-full bg-surfaceAlt text-xs">
                      <b>{a.symbol}</b> {pct(a.ytd)} · {a.setup}
                    </span>
                  ))}
                </td>
              </tr>);
          })}</tbody>
        </table>
      </section>

      <p className="text-muted text-xs">
        Données synthétiques reproductibles. Lecture : privilégier les setups haussiers dans les secteurs bullish ;
        éviter les contre-tendances dans les secteurs bearish.
      </p>
    </main>
  );
}
