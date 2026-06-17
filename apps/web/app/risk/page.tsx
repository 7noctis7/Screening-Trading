"use client";
import { usePortfolio } from "@/lib/api";
import { PageSkeleton } from "@/components/ui";

const pct = (x?: number) => `${((x ?? 0) * 100).toFixed(1)}%`;

function Stat({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div><div className="text-muted text-xs">{label}</div>
      <div className="text-lg mono" style={{ color: tone }}>{value}</div></div>
  );
}

export default function Risk() {
  const { data } = usePortfolio();
  if (!data) return <PageSkeleton />;
  const a = data.analysis ?? {};
  const rm = a.risk ?? {}, rb = a.risk_budget, lim = a.limits, stress = a.stress;
  const opt = a.optimal_allocation, ms = a.multi_strategy, g = rm.garch, vb = rm.var_backtest, fr = rm.factor_risk;
  const maxc = Math.max(0.01, ...(rb?.contrib_pct ?? [0]));
  return (
    <main className="max-w-5xl mx-auto p-6 space-y-4">
      <h1 className="text-xl font-semibold tracking-tight">Risque — vue institutionnelle</h1>

      <section className="card p-4">
        <h2 className="text-sm uppercase tracking-wide text-muted mb-3">Mesures de risque</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Stat label="VaR 95%" value={pct(rm.var_95)} tone="#f43f5e" />
          <Stat label="CVaR 95%" value={pct(rm.cvar_95)} tone="#f43f5e" />
          <Stat label="VaR Cornish-Fisher" value={pct(rm.var_cornish_fisher_95)} />
          <Stat label="Volatilité" value={pct(rm.vol)} />
          <Stat label="Vol EWMA" value={pct(rm.vol_ewma)} />
          {g?.available && <Stat label="Vol prévue (GARCH)" value={pct(g.forecast_vol)} />}
          <Stat label="Proba ruine (MC)" value={pct(a.monte_carlo?.p_ruin)} />
          <Stat label="Sharpe probabiliste" value={pct(rm.psr)} />
          <Stat label="Sharpe déflaté" value={pct(rm.dsr)} tone={rm.dsr >= 0.9 ? "#22c55e" : undefined} />
        </div>
      </section>

      {(vb || fr?.available) && (
        <section className="card p-4">
          <h2 className="text-sm uppercase tracking-wide text-muted mb-3">Validation & structure</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
            {vb && <div><div className="text-muted text-xs">Backtest VaR (Kupiec + Christoffersen)</div>
              <div className="text-lg mono" style={{ color: vb.pass && vb.independent ? "#22c55e" : "#f59e0b" }}>{vb.pass ? "couverture OK" : "couverture KO"} · {vb.independent ? "indép." : "groupés"}</div>
              <div className="text-muted2 text-xs">{vb.breaches}/{vb.n} dépass. (p={vb.p_value})</div></div>}
            {fr?.available && <div><div className="text-muted text-xs">Risque systématique (ACP)</div>
              <div className="text-lg mono">{pct(fr.systematic_pct)}</div>
              <div className="text-muted2 text-xs">{fr.effective_factors} facteurs effectifs</div></div>}
            {g?.available && <div><div className="text-muted text-xs">GARCH persistance</div>
              <div className="text-lg mono">{g.persistence}</div>
              <div className="text-muted2 text-xs">α={g.alpha} · β={g.beta}</div></div>}
          </div>
        </section>
      )}

      {lim && (
        <section className="card p-4">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <h2 className="text-sm uppercase tracking-wide text-muted">Concentration & limites</h2>
            <span className="text-xs mono">HHI {lim.hhi} · N effectif {lim.effective_n} ·
              <span style={{ color: lim.ok ? "#22c55e" : "#f59e0b" }}> {lim.ok ? "conforme" : `${lim.breaches.length} dépassement(s)`}</span></span>
          </div>
          {lim.breaches.length > 0 && <div className="mt-2 space-y-1 text-xs">
            {lim.breaches.map((b: any, i: number) => (
              <div key={i} className="flex justify-between" style={{ color: "#f59e0b" }}>
                <span>⚠️ {b.type} — {b.label}</span><span className="mono">{(b.weight * 100).toFixed(1)}% &gt; {(b.limit * 100).toFixed(0)}%</span></div>))}
          </div>}
        </section>
      )}

      {rb?.symbols?.length > 0 && (
        <section className="card p-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm uppercase tracking-wide text-muted">Budget de risque (contribution à la vol)</h2>
            <span className="text-xs mono text-muted">vol {pct(rb.portfolio_vol)} · diversif ×{rb.diversification_ratio}</span>
          </div>
          <div className="space-y-1.5 mt-3">
            {rb.symbols.map((s: string, i: number) => (
              <div key={s} className="flex items-center gap-2 text-xs">
                <span className="w-16 mono">{s}</span>
                <span className="h-2 rounded bg-accent" style={{ width: `${Math.round((rb.contrib_pct[i] / maxc) * 100)}%`, maxWidth: 360 }} />
                <span className="mono text-muted">{(rb.contrib_pct[i] * 100).toFixed(1)}%</span></div>))}
          </div>
        </section>
      )}

      {stress?.scenarios?.length > 0 && (
        <section className="card p-4">
          <h2 className="text-sm uppercase tracking-wide text-muted mb-2">Stress-tests macro & couverture</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm"><thead className="text-muted text-xs">
              <tr><th className="text-left font-normal">Scénario</th><th className="text-right font-normal">Impact P&amp;L</th></tr></thead>
              <tbody>{stress.scenarios.map((s: any) => (
                <tr key={s.name} className="border-t border-border"><td className="py-1.5">{s.name}</td>
                  <td className="text-right mono" style={{ color: s.pnl_pct >= 0 ? "#22c55e" : "#f43f5e" }}>{(s.pnl_pct * 100).toFixed(1)}%</td></tr>))}</tbody>
            </table>
          </div>
          {stress.hedge && <div className="mt-3 text-xs p-3 rounded-lg" style={{ background: "var(--surface3)" }}>
            <b>Couverture</b> — pire : <span className="mono" style={{ color: "#f43f5e" }}>{(stress.hedge.worst_pnl_pct * 100).toFixed(1)}%</span> ({stress.hedge.worst_scenario}).{" "}
            {stress.hedge.needed ? <>Short indiciel ≈ <b className="mono">{(stress.hedge.hedge_pct * 100).toFixed(1)}%</b>.</> : stress.hedge.rationale}</div>}
        </section>
      )}

      {ms?.available && (
        <section className="card p-4 overflow-x-auto">
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-sm uppercase tracking-wide text-muted">Backtest multi-stratégie (indice équipondéré)</h2>
            <span className="text-xs text-muted">meilleure : <b className="text-fg">{ms.best}</b></span>
          </div>
          <table className="w-full text-sm mono"><thead className="text-muted text-xs">
            <tr><th className="text-left font-normal">Stratégie</th><th className="text-right font-normal">Rendement</th>
            <th className="text-right font-normal">Sharpe</th><th className="text-right font-normal">Max DD</th><th className="text-right font-normal">Exposition</th></tr></thead>
            <tbody>{[...ms.strategies, ms.combined].map((s: any) => (
              <tr key={s.name} className="border-t border-border">
                <td className="py-1.5 font-sans">{s.name}</td>
                <td className="text-right" style={{ color: s.total_return >= 0 ? "#22c55e" : "#f43f5e" }}>{pct(s.total_return)}</td>
                <td className="text-right">{s.sharpe}</td>
                <td className="text-right" style={{ color: "#f43f5e" }}>{pct(s.max_drawdown)}</td>
                <td className="text-right text-muted">{pct(s.exposure)}</td></tr>))}</tbody>
          </table>
        </section>
      )}

      {opt?.symbols?.length > 0 && (
        <section className="card p-4 overflow-x-auto">
          <h2 className="text-sm uppercase tracking-wide text-muted mb-2">Allocation optimale suggérée</h2>
          <table className="w-full text-sm mono"><thead className="text-muted text-xs">
            <tr><th className="text-left font-normal">Actif</th><th className="text-right font-normal">Actuelle</th>
            <th className="text-right font-normal">HRP</th><th className="text-right font-normal">Min-var</th><th className="text-right font-normal">Risk parity</th></tr></thead>
            <tbody>{opt.symbols.map((s: string, i: number) => (
              <tr key={s} className="border-t border-border"><td className="py-1.5">{s}</td>
                <td className="text-right text-muted">{(opt.current[i] * 100).toFixed(1)}%</td>
                <td className="text-right" style={{ color: "#3b82f6" }}>{(opt.hrp[i] * 100).toFixed(1)}%</td>
                <td className="text-right" style={{ color: "#60a5fa" }}>{(opt.min_variance[i] * 100).toFixed(1)}%</td>
                <td className="text-right" style={{ color: "#a855f7" }}>{((opt.risk_parity?.[i] ?? 0) * 100).toFixed(1)}%</td></tr>))}</tbody>
          </table>
        </section>
      )}
    </main>
  );
}
