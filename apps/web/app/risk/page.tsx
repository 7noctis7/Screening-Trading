"use client";
import { StepBanner } from "@/components/Pipeline";
import { usePortfolio, useMeta } from "@/lib/api";
import { PageSkeleton } from "@/components/ui";
import { Simulator } from "@/components/Simulator";

const pct = (x?: number) => `${((x ?? 0) * 100).toFixed(1)}%`;

function HealthChip({ label, value, tone, title }: { label: string; value: string; tone: string; title?: string }) {
  return (
    <div className="flex items-center gap-2" title={title}>
      <span className="inline-block w-2 h-2 rounded-full" style={{ background: tone }} />
      <span className="text-xs text-muted">{label}</span>
      <span className="text-xs mono" style={{ color: tone, fontWeight: 600 }}>{value}</span>
    </div>
  );
}

function SystemHealth({ meta, cd }: { meta: any; cd: any }) {
  if (!meta) return null;
  const synth = meta.data_synthetic;
  const audit = meta.audit;
  const cache = meta.cov_cache;
  const kappa = cd?.cond_used;
  // données : rouge si synthétique, ambre si audit non-ok, vert sinon
  const dataTone = synth ? "#ef4444" : (audit && !audit.ok ? "#f59e0b" : "#22c55e");
  const dataVal = synth ? "synthétique" : (audit ? (audit.ok ? "réelles ✓ auditées" : `${(audit.counts?.critical ?? 0)} critique(s)`) : "réelles");
  const kTone = kappa == null ? "#64748b" : kappa < 50 ? "#22c55e" : kappa < 500 ? "#f59e0b" : "#ef4444";
  const hr = cache?.hit_rate;
  const hrTone = hr == null ? "#64748b" : hr >= 0.6 ? "#22c55e" : hr >= 0.3 ? "#f59e0b" : "#94a3b8";
  return (
    <section className="card p-4">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm uppercase tracking-wide text-muted">Santé système</h2>
        {meta.generated_at && <span className="text-[11px] mono text-muted">maj {String(meta.generated_at).slice(0, 16).replace("T", " ")}</span>}
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <HealthChip label="Données" value={dataVal} tone={dataTone}
          title="État de l'intégrité des données (audit PwC : complétude / exactitude / point-in-time)." />
        <HealthChip label="Conditionnement κ" value={kappa == null ? "n/a" : Math.round(kappa).toString()} tone={kTone}
          title="Nombre de condition de la covariance après shrinkage. Vert <50 (stable), ambre <500, rouge >500." />
        <HealthChip label="Cache covariance" value={hr == null ? "n/a" : `${Math.round(hr * 100)}%`} tone={hrTone}
          title={`Hit-rate du cache de covariance${cache?.builds ? ` sur ${cache.builds} builds` : ""}.`} />
        <HealthChip label="Mode" value={meta.strategy ?? "—"} tone="#64748b"
          title={`Délai flux : ${meta.delay_minutes ?? 0} min · univers ${meta.universe_size ?? "?"} titres.`} />
      </div>
    </section>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div><div className="text-muted text-xs">{label}</div>
      <div className="text-lg mono" style={{ color: tone }}>{value}</div></div>
  );
}

export default function Risk() {
  const { data } = usePortfolio();
  const { data: meta } = useMeta();
  if (!data) return <PageSkeleton />;
  const a = data.analysis ?? {};
  const rm = a.risk ?? {}, rb = a.risk_budget, lim = a.limits, stress = a.stress;
  const opt = a.optimal_allocation, ms = a.multi_strategy, g = rm.garch, vb = rm.var_backtest, fr = rm.factor_risk;
  const reco = a.recommended_allocation;
  const maxc = Math.max(0.01, ...(rb?.contrib_pct ?? [0]));
  return (
    <main className="max-w-5xl mx-auto p-6 space-y-4">
      <h1 className="text-xl font-semibold tracking-tight">Risque — vue institutionnelle
        {data.strategy_label && <span className="ml-2 text-xs font-normal px-2 py-0.5 rounded-full align-middle"
          style={{ background: "color-mix(in srgb, var(--accent) 16%, transparent)", color: "var(--accent2)" }}>
          {data.strategy_label}</span>}</h1>
      <p className="text-muted text-xs">Risque de l'<b>allocation de production</b> (preset + cœur), cohérent avec le Dashboard et Positions.</p>
      <StepBanner active="risk" />

      <SystemHealth meta={meta} cd={rb?.covariance_diagnostics} />

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
          {rm.evt?.available && <Stat label="VaR 99.9% (EVT)" value={pct(rm.evt.var)} tone="#f43f5e" />}
          {rm.evt?.available && <Stat label="ES 99.9% (EVT)" value={pct(rm.evt.es)} tone="#f43f5e" />}
          {rm.liquidity?.available && <Stat label="Liquidation (jours pond.)" value={String(rm.liquidity.weighted_days)} />}
          {rm.liquidity?.available && <Stat label="Part illiquide" value={pct(rm.liquidity.illiquid_pct)} tone={rm.liquidity.illiquid_pct > 0.2 ? "#f59e0b" : undefined} />}
        </div>
        {rm.var_horizons?.length > 0 && (
          <div className="mt-3 flex flex-wrap items-center gap-x-6 gap-y-1 text-sm">
            <span className="text-muted text-xs uppercase tracking-wide">VaR 95% multi-horizon</span>
            {rm.var_horizons.map((h: any) => (
              <span key={h.days} className="mono">
                <span className="text-muted">{h.days} j :</span> <b style={{ color: "#f43f5e" }}>{pct(h.var_95)}</b>
              </span>
            ))}
            <span className="text-muted2 text-xs">(mise à l'échelle racine-du-temps ; 10 j = horizon Bâle)</span>
          </div>
        )}
        <p className="text-muted2 text-xs mt-2">EVT = théorie des valeurs extrêmes (Peaks-Over-Threshold + GPD) pour le risque de queue ; liquidité estimée via l'ADV (participation 10 %).</p>
      </section>

      <Simulator />

      {rm.vol_managed?.available && (
        <section className="card p-4 overflow-x-auto">
          <h2 className="text-sm uppercase tracking-wide text-muted mb-1">Volatilité gérée (Moreira-Muir) — overlay</h2>
          <p className="text-muted2 text-xs mb-3">Exposition ∝ vol-cible ({pct(rm.vol_managed.target_vol)}) / vol réalisée récente (connue à t−1, anti-fuite). Exposition moyenne {pct(rm.vol_managed.avg_exposure)} · sans levier.</p>
          <table className="w-full text-sm">
            <thead className="text-muted text-xs"><tr>
              <th className="text-left font-normal">Série</th>
              <th className="text-right font-normal">CAGR</th><th className="text-right font-normal">Vol</th>
              <th className="text-right font-normal">Sharpe</th><th className="text-right font-normal">Max DD</th></tr></thead>
            <tbody className="mono">
              {[["Brute", rm.vol_managed.raw, "#9aa1ab"], ["Vol. gérée", rm.vol_managed.managed, "#22d3ee"]].map(([lab, st, col]: any) => (
                <tr key={lab} className="border-t border-border">
                  <td className="py-1.5 font-sans" style={{ color: col }}>{lab}</td>
                  <td className="text-right">{(st.cagr * 100).toFixed(1)}%</td>
                  <td className="text-right">{(st.vol * 100).toFixed(1)}%</td>
                  <td className="text-right"><b>{st.sharpe}</b></td>
                  <td className="text-right" style={{ color: "#f43f5e" }}>{(st.max_drawdown * 100).toFixed(1)}%</td>
                </tr>))}
            </tbody>
          </table>
          <p className="text-muted2 text-xs mt-2">Gain Sharpe {rm.vol_managed.sharpe_gain >= 0 ? "+" : ""}{rm.vol_managed.sharpe_gain} · Δ CAGR {(rm.vol_managed.cagr_gain * 100).toFixed(1)} pts · DD {(rm.vol_managed.dd_reduction * 100).toFixed(1)} pts. ⚠️ Le bénéfice de Moreira-Muir vient du <b>clustering de volatilité</b> des marchés réels ; sur données synthétiques (quasi-IID) il est marginal voire nul. Recherche : Moreira &amp; Muir, <i>Volatility-Managed Portfolios</i> (JF 2017).</p>
        </section>
      )}

      {rm.vol_regime?.available && (
        <section className="card p-4">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <h2 className="text-sm uppercase tracking-wide text-muted">Régime de volatilité</h2>
            <span className="text-xs mono px-2 py-0.5 rounded-full" style={{
              background: `color-mix(in srgb, ${rm.vol_regime.state === "stress" ? "#f43f5e" : rm.vol_regime.state === "calme" ? "#22c55e" : "#f59e0b"} 18%, transparent)`,
              color: rm.vol_regime.state === "stress" ? "#f43f5e" : rm.vol_regime.state === "calme" ? "#22c55e" : "#f59e0b" }}>
              {rm.vol_regime.state.toUpperCase()} · exposition ×{rm.vol_regime.exposure_multiplier}
            </span>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-2 text-sm mono">
            <div><div className="text-muted text-xs">Vol réalisée</div><div className="text-lg">{pct(rm.vol_regime.current_vol)}</div></div>
            <div><div className="text-muted text-xs">Percentile historique</div><div className="text-lg">{pct(rm.vol_regime.percentile)}</div></div>
            <div><div className="text-muted text-xs">Seuil calme &lt;</div><div className="text-lg">{pct(rm.vol_regime.thresholds["calme<"])}</div></div>
            <div><div className="text-muted text-xs">Seuil stress &gt;</div><div className="text-lg">{pct(rm.vol_regime.thresholds["stress>"])}</div></div>
          </div>
          <p className="text-muted2 text-xs mt-2">{rm.vol_regime.note} · méthode : {rm.vol_regime.method}.</p>
        </section>
      )}

      {rm.fragility?.available && (
        <section className="card p-4">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <h2 className="text-sm uppercase tracking-wide text-muted">Fragilité (Taleb · Incerto)</h2>
            <span className="text-xs mono" style={{ color: rm.fragility.fragile ? "#f43f5e" : "#22c55e" }}>{rm.fragility.verdict}</span>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-2 text-sm mono">
            <div><div className="text-muted text-xs">Asymétrie (skew)</div><div className="text-lg" style={{ color: rm.fragility.skew >= 0 ? "#22c55e" : "#f43f5e" }}>{rm.fragility.skew}</div></div>
            <div><div className="text-muted text-xs">Excès de kurtosis</div><div className="text-lg" style={{ color: rm.fragility.excess_kurtosis > 3 ? "#f43f5e" : undefined }}>{rm.fragility.excess_kurtosis}</div></div>
            <div><div className="text-muted text-xs">Ratio de queue (CVaR/VaR)</div><div className="text-lg">{rm.fragility.tail_ratio}</div></div>
            <div><div className="text-muted text-xs">Pire jour</div><div className="text-lg" style={{ color: "#f43f5e" }}>{pct(rm.fragility.worst_day)}</div></div>
          </div>
          <p className="text-muted2 text-xs mt-2">Principes : le risque vit dans les <b>queues</b> (kurtosis, pire jour), pas la vol moyenne ; viser une <b>convexité</b> (skew ≥ 0) ; approche <b>barbell</b> (très sûr + très risqué) ; <b>éviter la ruine</b> avant tout. Asymétrie négative + kurtosis élevé = profil fragile à couvrir (stops, hedging, exposition réduite).</p>
        </section>
      )}

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

      {reco?.available && (
        <section className="card p-4" style={{ borderColor: "color-mix(in srgb, var(--accent) 40%, transparent)" }}>
          <div className="flex items-center justify-between flex-wrap gap-2">
            <h2 className="text-sm uppercase tracking-wide text-muted">⭐ Allocation recommandée — risk-parity · DD-cible</h2>
            <span className="text-xs mono">DD-cible {(reco.dd_target * 100).toFixed(0)}% · vol-cible {pct(reco.target_vol)} · exposition <b>{pct(reco.gross_exposure)}</b> · cash {pct(reco.cash_pct)}</span>
          </div>
          <p className="text-muted2 text-xs mt-1">{reco.note} Pilote l'exposition via <code className="mono">QUANT_DD_TARGET</code> (ex. 0.25). Bande {(reco.band * 100).toFixed(0)}%.</p>
          <div className="overflow-x-auto mt-2">
            <table className="w-full text-sm mono"><thead className="text-muted text-xs">
              <tr><th className="text-left font-normal">Actif</th><th className="text-right font-normal">Actuelle</th>
              <th className="text-right font-normal">Risk-parity</th><th className="text-right font-normal">Cible (DD {(reco.dd_target * 100).toFixed(0)}%)</th></tr></thead>
              <tbody>{reco.rows.map((r: any) => (
                <tr key={r.symbol} className="border-t border-border"><td className="py-1.5">{r.symbol}</td>
                  <td className="text-right text-muted">{(r.current * 100).toFixed(1)}%</td>
                  <td className="text-right">{(r.risk_parity * 100).toFixed(1)}%</td>
                  <td className="text-right" style={{ color: "var(--accent2)" }}>{(r.target * 100).toFixed(1)}%</td></tr>))}</tbody>
            </table>
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
          {rb.covariance_diagnostics?.cond_used != null && (() => {
            const k = rb.covariance_diagnostics.cond_used;
            const col = k < 50 ? "#22c55e" : k < 500 ? "#f59e0b" : "#ef4444";   // vert / ambre / rouge
            return (
              <div className="mt-1 text-[11px] mono" title="Nombre de condition de la matrice de covariance (avant → après shrinkage Ledoit-Wolf) et intensité de régularisation. Vert <50 (stable), ambre <500, rouge >500 (risque mal estimé : univers trop concentré ou historique trop court).">
                <span className="text-muted">κ {Math.round(rb.covariance_diagnostics.cond_raw)} → </span>
                <span style={{ color: col, fontWeight: 600 }}>{Math.round(k)}</span>
                {rb.covariance_diagnostics.delta > 0 && <span className="text-muted"> · shrinkage {Math.round(rb.covariance_diagnostics.delta * 100)}%</span>}
              </div>
            );
          })()}
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
