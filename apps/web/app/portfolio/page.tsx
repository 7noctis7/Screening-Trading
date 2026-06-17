"use client";
import { usePortfolio } from "@/lib/api";
import { ExpertReview } from "@/components/ExpertReview";
import { CorrelationHeatmap } from "@/components/CorrelationHeatmap";
import { PageSkeleton } from "@/components/ui";

const pct = (x: number) => `${(x * 100).toFixed(1)}%`;

export default function Portfolio() {
  const { data } = usePortfolio();
  if (!data) return <PageSkeleton />;
  const a = data.analysis, rel = a?.relative ?? {}, rm = a?.risk ?? {};
  const rb = a?.risk_budget, lim = a?.limits, stress = a?.stress;
  const maxc = Math.max(0.01, ...(rb?.contrib_pct ?? [0]));
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

      {/* Limites de concentration */}
      {lim && (
        <section className="card p-4">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <h2 className="text-sm uppercase tracking-wide text-muted">Concentration &amp; limites</h2>
            <span className="text-xs mono">HHI {lim.hhi} · N effectif {lim.effective_n} ·
              <span style={{ color: lim.ok ? "#22c55e" : "#f59e0b" }}> {lim.ok ? "conforme" : `${lim.breaches.length} dépassement(s)`}</span>
            </span>
          </div>
          {lim.breaches.length > 0 && (
            <div className="mt-2 space-y-1 text-xs">
              {lim.breaches.map((b: any, i: number) => (
                <div key={i} className="flex justify-between" style={{ color: "#f59e0b" }}>
                  <span>⚠️ {b.type} — {b.label}</span>
                  <span className="mono">{(b.weight * 100).toFixed(1)}% &gt; {(b.limit * 100).toFixed(0)}%</span>
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {/* Budget de risque (contribution à la volatilité) */}
      {rb?.symbols?.length > 0 && (
        <section className="card p-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm uppercase tracking-wide text-muted">Budget de risque (contribution à la vol)</h2>
            <span className="text-xs mono text-muted">vol {pct(rb.portfolio_vol)} · diversif ×{rb.diversification_ratio}</span>
          </div>
          <div className="space-y-1.5 mt-3">
            {rb.symbols.map((s: string, idx: number) => (
              <div key={s} className="flex items-center gap-2 text-xs">
                <span className="w-16 mono">{s}</span>
                <span className="h-2 rounded bg-accent" style={{ width: `${Math.round((rb.contrib_pct[idx] / maxc) * 100)}%`, maxWidth: 360 }} />
                <span className="mono text-muted">{(rb.contrib_pct[idx] * 100).toFixed(1)}%</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Stress-tests macro + couverture */}
      {stress?.scenarios?.length > 0 && (
        <section className="card p-4">
          <h2 className="text-sm uppercase tracking-wide text-muted mb-2">Stress-tests macro</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-muted text-xs">
                <tr><th className="text-left font-normal">Scénario</th>
                <th className="text-right font-normal">Impact P&amp;L</th>
                <th className="text-right font-normal">Valeur après choc</th></tr>
              </thead>
              <tbody>{stress.scenarios.map((s: any) => (
                <tr key={s.name} className="border-t border-border">
                  <td className="py-1.5">{s.name}</td>
                  <td className="text-right mono" style={{ color: s.pnl_pct >= 0 ? "#22c55e" : "#f43f5e" }}>{(s.pnl_pct * 100).toFixed(1)}%</td>
                  <td className="text-right mono text-muted">{((1 + s.pnl_pct) * 100).toFixed(0)}%</td>
                </tr>))}</tbody>
            </table>
          </div>
          {stress.hedge && (
            <div className="mt-3 text-xs p-3 rounded-lg" style={{ background: "var(--surface3)" }}>
              <b>Couverture</b> — pire scénario : <span className="mono" style={{ color: "#f43f5e" }}>{(stress.hedge.worst_pnl_pct * 100).toFixed(1)}%</span> ({stress.hedge.worst_scenario}).{" "}
              {stress.hedge.needed
                ? <>Suggestion : short indiciel ≈ <b className="mono">{(stress.hedge.hedge_pct * 100).toFixed(1)}%</b> du portefeuille pour viser ≤ {(stress.hedge.target_max_loss * 100).toFixed(0)}% — {stress.hedge.rationale}.</>
                : <>{stress.hedge.rationale} (seuil {(stress.hedge.target_max_loss * 100).toFixed(0)}%).</>}
            </div>
          )}
        </section>
      )}

      <CorrelationHeatmap data={a?.correlation} />
      <ExpertReview review={a?.review} />
    </main>
  );
}
