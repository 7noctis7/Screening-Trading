"use client";
import { usePortfolio } from "@/lib/api";
import { ExpertReview } from "@/components/ExpertReview";
import { CorrelationHeatmap } from "@/components/CorrelationHeatmap";

const pct = (x: number) => `${(x * 100).toFixed(1)}%`;

export default function Portfolio() {
  const { data } = usePortfolio();
  if (!data) return <div className="p-8 text-muted">Chargement…</div>;
  const a = data.analysis, rel = a?.relative ?? {}, rm = a?.risk ?? {};
  return (
    <main className="max-w-5xl mx-auto p-6 space-y-4">
      <h1 className="text-xl font-semibold tracking-tight">Portefeuille &amp; Analyse</h1>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <section className="card p-4">
          <h2 className="text-sm uppercase tracking-wide text-muted mb-2">Mesures relatives</h2>
          <table className="w-full text-sm mono">
            <tbody>{Object.entries(rel).map(([k, v]) => (
              <tr key={k} className="border-t border-border"><td className="py-1.5 text-muted">{k}</td>
              <td className="text-right">{String(v)}</td></tr>))}</tbody>
          </table>
        </section>
        <section className="card p-4">
          <h2 className="text-sm uppercase tracking-wide text-muted mb-2">Risque</h2>
          <div className="grid grid-cols-2 gap-3 mono">
            <div><div className="text-muted text-xs">VaR 95%</div><div className="text-lg">{pct(rm.var_95 ?? 0)}</div></div>
            <div><div className="text-muted text-xs">CVaR 95%</div><div className="text-lg">{pct(rm.cvar_95 ?? 0)}</div></div>
            <div><div className="text-muted text-xs">Vol</div><div className="text-lg">{pct(rm.vol ?? 0)}</div></div>
            <div><div className="text-muted text-xs">Proba ruine</div><div className="text-lg">{pct(a?.monte_carlo?.p_ruin ?? 0)}</div></div>
          </div>
        </section>
      </div>
      <CorrelationHeatmap data={a?.correlation} />
      <ExpertReview review={a?.review} />
    </main>
  );
}
