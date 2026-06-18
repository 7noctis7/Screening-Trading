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
  const rb = a?.risk_budget, lim = a?.limits, stress = a?.stress, opt = a?.optimal_allocation;
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
            <div><div className="text-muted text-xs">VaR Cornish-Fisher 95%</div><div className="text-lg">{pct(rm.var_cornish_fisher_95 ?? 0)}</div></div>
            <div><div className="text-muted text-xs">Vol EWMA</div><div className="text-lg">{pct(rm.vol_ewma ?? 0)}</div></div>
            <div><div className="text-muted text-xs">Sharpe probabiliste</div><div className="text-lg">{pct(rm.psr ?? 0)}</div></div>
            <div><div className="text-muted text-xs">Sharpe déflaté (essais×)</div><div className="text-lg">{pct(rm.dsr ?? 0)}</div></div>
          </div>
        </section>
      </div>

      {/* Modèles de risque : GARCH, backtest VaR (Kupiec), risque factoriel (ACP) */}
      {(rm.garch?.available || rm.var_backtest || rm.factor_risk?.available) && (
        <section className="card p-4">
          <h2 className="text-sm uppercase tracking-wide text-muted mb-2">Modèles de risque</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
            {rm.garch?.available && (
              <div><div className="text-muted text-xs">Vol prévue (GARCH 1,1)</div>
                <div className="text-lg mono">{pct(rm.garch.forecast_vol)}</div>
                <div className="text-muted2 text-xs">persistance {rm.garch.persistence}</div></div>
            )}
            {rm.var_backtest && (
              <div><div className="text-muted text-xs">Backtest VaR (Kupiec)</div>
                <div className="text-lg mono" style={{ color: rm.var_backtest.pass ? "#22c55e" : "#f43f5e" }}>{rm.var_backtest.pass ? "validé" : "rejeté"}</div>
                <div className="text-muted2 text-xs">{rm.var_backtest.breaches}/{rm.var_backtest.n} dépass. (p={rm.var_backtest.p_value})</div></div>
            )}
            {rm.factor_risk?.available && (
              <div><div className="text-muted text-xs">Risque systématique (ACP)</div>
                <div className="text-lg mono">{pct(rm.factor_risk.systematic_pct)}</div>
                <div className="text-muted2 text-xs">{rm.factor_risk.effective_factors} facteurs effectifs</div></div>
            )}
          </div>
        </section>
      )}

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

      {/* Allocation optimale suggérée (HRP / min-variance vs actuelle) */}
      {opt?.symbols?.length > 0 && (
        <section className="card p-4 overflow-x-auto">
          <h2 className="text-sm uppercase tracking-wide text-muted mb-2">Allocation optimale suggérée</h2>
          <table className="w-full text-sm mono">
            <thead className="text-muted text-xs">
              <tr><th className="text-left font-normal">Actif</th><th className="text-right font-normal">Actuelle</th>
              <th className="text-right font-normal">HRP</th><th className="text-right font-normal">Min-var</th>
              <th className="text-right font-normal">Risk parity</th>
              {opt.black_litterman && <th className="text-right font-normal">Black-Litterman</th>}</tr>
            </thead>
            <tbody>{opt.symbols.map((s: string, i: number) => (
              <tr key={s} className="border-t border-border">
                <td className="py-1.5">{s}</td>
                <td className="text-right text-muted">{(opt.current[i] * 100).toFixed(1)}%</td>
                <td className="text-right" style={{ color: "#3b82f6" }}>{(opt.hrp[i] * 100).toFixed(1)}%</td>
                <td className="text-right" style={{ color: "#60a5fa" }}>{(opt.min_variance[i] * 100).toFixed(1)}%</td>
                <td className="text-right" style={{ color: "#a855f7" }}>{((opt.risk_parity?.[i] ?? 0) * 100).toFixed(1)}%</td>
                {opt.black_litterman && <td className="text-right" style={{ color: "#22d3ee" }}>{((opt.black_litterman[i] ?? 0) * 100).toFixed(1)}%</td>}
              </tr>))}</tbody>
          </table>
          <p className="text-muted2 text-xs mt-2">HRP (hierarchical risk parity, López de Prado) &amp; min-variance — robustes sans inversion instable de la covariance.</p>
        </section>
      )}

      {(() => {
        const rec = a?.recommended_allocation, pb = rec?.preset_backtest;
        if (!pb?.available) return null;
        const rows: [string, any, string][] = [
          ["Preset (best practice)", pb.preset, "#22d3ee"],
          ["Swing (actuel)", pb.swing, "#f59e0b"],
          ["Équipondéré (même univers)", pb.benchmark, "#9aa1ab"],
        ].filter((r) => r[1]) as any;
        return (
          <section className="card p-4 overflow-x-auto">
            <h2 className="text-sm uppercase tracking-wide text-muted mb-1">Preset stratégique « best practice » — backtest comparatif</h2>
            <p className="text-muted2 text-xs mb-3">Qualité (top {pb.top_k}) → risk-parity (ERC) → exposition pilotée par drawdown-cible ({pct(pb.dd_target)}) → earnings blackout → bande de non-trading ({pct(pb.band)}). Point-in-time, net de coûts par classe. Turnover {pb.turnover_annual}×/an · exposition brute moy. {pct(pb.avg_gross)}.</p>
            <table className="w-full text-sm">
              <thead className="text-muted text-xs"><tr>
                <th className="text-left font-normal">Stratégie</th>
                <th className="text-right font-normal">Rendement</th><th className="text-right font-normal">Annualisé</th>
                <th className="text-right font-normal">Sharpe</th><th className="text-right font-normal">Max DD</th></tr></thead>
              <tbody className="mono">{rows.map(([lab, st, col]) => (
                <tr key={lab} className="border-t border-border">
                  <td className="py-1.5 font-sans" style={{ color: col }}>{lab}</td>
                  <td className="text-right">{(st.total_return * 100).toFixed(1)}%</td>
                  <td className="text-right">{(st.annualized * 100).toFixed(1)}%</td>
                  <td className="text-right"><b>{st.sharpe}</b></td>
                  <td className="text-right" style={{ color: "#f43f5e" }}>{(st.max_drawdown * 100).toFixed(1)}%</td>
                </tr>))}</tbody>
            </table>
            <p className="text-muted2 text-xs mt-2">💡 Lecture honnête : le preset vise le <b>meilleur rendement ajusté du risque</b> (Sharpe ↑, drawdown ↓), pas le CAGR maximal. Sans edge directionnel prouvé (DSR ≈ 0), réduire le risque et le turnover est le levier le plus fiable. Le swing peut afficher un CAGR brut plus élevé mais avec un drawdown bien supérieur.</p>
          </section>
        );
      })()}

      <CorrelationHeatmap data={a?.correlation} />
      <ExpertReview review={a?.review} />
    </main>
  );
}
