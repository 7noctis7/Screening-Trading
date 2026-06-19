"use client";
import { useMemo, useState } from "react";
import { StepBanner } from "@/components/Pipeline";
import { useDashboard, useScreener, useSentiment } from "@/lib/api";
import { MetricCard } from "@/components/MetricCard";
import { RegimeBanner } from "@/components/RegimeBanner";
import { VixPlaybook } from "@/components/VixPlaybook";
import { SentimentBanner } from "@/components/SentimentBanner";
import { EquityChart } from "@/components/EquityChart";
import { PageSkeleton } from "@/components/ui";

const pct = (x: number) => `${(x * 100).toFixed(1)}%`;
const PERIODS: [string, number][] = [["1A", 1], ["2A", 2], ["3A", 3], ["5A", 5], ["Tout", 0]];

// Recalcule les métriques sur la fenêtre sélectionnée (annualisé, base 252 j).
function statsFrom(eq: { t: string; v: number }[]) {
  if (eq.length < 2) return null;
  const v = eq.map((p) => p.v);
  const r: number[] = [];
  for (let i = 1; i < v.length; i++) if (v[i - 1] > 0) r.push(v[i] / v[i - 1] - 1);
  const mean = r.reduce((a, b) => a + b, 0) / (r.length || 1);
  const sd = Math.sqrt(r.reduce((a, b) => a + (b - mean) ** 2, 0) / (r.length || 1));
  const dn = r.filter((x) => x < 0);
  const dsd = Math.sqrt(dn.reduce((a, b) => a + b * b, 0) / (dn.length || 1));
  let peak = v[0], mdd = 0;
  for (const x of v) { peak = Math.max(peak, x); mdd = Math.min(mdd, x / peak - 1); }
  const total = v[v.length - 1] / v[0] - 1;
  const cagr = r.length > 1 ? Math.pow(1 + total, 252 / r.length) - 1 : total;
  return {
    total_return: total, cagr,
    sharpe: sd > 0 ? (mean / sd) * Math.sqrt(252) : 0,
    sortino: dsd > 0 ? (mean / dsd) * Math.sqrt(252) : 0,
    max_drawdown: mdd,
  };
}

export default function Dashboard() {
  const { data: d } = useDashboard();
  const { data: s } = useScreener();
  const { data: sent } = useSentiment();
  const [years, setYears] = useState(0);   // 0 = tout
  const eqFull: { t: string; v: number }[] = d?.equity ?? [];
  const sliced = useMemo(() => {
    if (!years || !eqFull.length) return eqFull;
    const last = new Date(eqFull[eqFull.length - 1].t);
    const cut = new Date(last); cut.setFullYear(cut.getFullYear() - years);
    return eqFull.filter((p) => new Date(p.t) >= cut);
  }, [eqFull, years]);
  // rebase une série pour qu'elle démarre à 10 000 $ au début de la fenêtre (comparaison équitable)
  const rebase = (arr?: { t: string; v: number }[]) => {
    if (!arr?.length || !arr[0].v) return arr ?? [];
    const f = 10000 / arr[0].v;
    return arr.map((p) => ({ t: p.t, v: Math.round(p.v * f * 100) / 100 }));
  };
  const chartEquity = useMemo(() => rebase(sliced), [sliced]);
  const chartBench = useMemo(() => {
    const src = d?.benchmarks as Record<string, any[]> | undefined;
    if (!src) return src;
    const cutT = sliced[0]?.t ?? "";
    const out: Record<string, any[]> = {};
    for (const [k, arr] of Object.entries(src))
      out[k] = rebase((years ? arr.filter((p) => p.t >= cutT) : arr));
    return out;
  }, [d?.benchmarks, sliced, years]);
  if (!d) return <PageSkeleton />;
  const m = statsFrom(sliced) ?? d.metrics;
  return (
    <main className="max-w-6xl mx-auto p-6 space-y-4">
      <h1 className="text-xl font-semibold tracking-tight">Quant Terminal
        {d.strategy_label && <span className="ml-2 text-xs font-normal px-2 py-0.5 rounded-full align-middle"
          style={{ background: "color-mix(in srgb, var(--accent) 16%, transparent)", color: "var(--accent2)" }}>
          stratégie : {d.strategy_label}</span>}</h1>
      <StepBanner active="screener" />
      <RegimeBanner regime={d.regime} />
      <SentimentBanner sentiment={sent} />
      <VixPlaybook vix={d.vix} playbook={d.vix_playbook} series={d.vix_series} />
      <div className="flex items-center gap-1.5 flex-wrap">
        <span className="text-xs text-muted uppercase tracking-wide mr-1">Période</span>
        {PERIODS.map(([lab, y]) => (
          <button key={lab} onClick={() => setYears(y)}
            className="px-2.5 py-1 text-xs rounded-full border transition-colors"
            style={{ borderColor: years === y ? "var(--accent)" : "var(--border)",
                     color: years === y ? "var(--fg)" : "var(--muted)",
                     background: years === y ? "color-mix(in srgb, var(--accent) 14%, transparent)" : "transparent" }}>
            {lab}
          </button>
        ))}
      </div>
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <MetricCard label="Rendement" value={pct(m.total_return)} tone={m.total_return >= 0 ? "pos" : "neg"} />
        <MetricCard label="CAGR" value={pct(m.cagr ?? 0)} tone={(m.cagr ?? 0) >= 0 ? "pos" : "neg"} />
        <MetricCard label="Sharpe" value={m.sharpe?.toFixed(2)} />
        <MetricCard label="Sortino" value={m.sortino?.toFixed(2)} />
        <MetricCard label="Max DD" value={pct(m.max_drawdown)} tone="neg" />
      </div>
      <EquityChart series={chartEquity} benchmarks={chartBench} />

      {/* Comparaison KPI : portefeuille vs benchmarks, sur la période choisie */}
      <section className="card p-4 overflow-x-auto">
        <h2 className="text-sm uppercase tracking-wide text-muted mb-3">Comparaison vs benchmarks ({PERIODS.find(([, y]) => y === years)?.[0] ?? "Tout"})</h2>
        <table className="w-full text-sm">
          <thead className="text-muted text-xs"><tr>
            <th className="text-left font-normal">Série</th>
            <th className="text-right font-normal">Rendement</th><th className="text-right font-normal">CAGR</th>
            <th className="text-right font-normal">Sharpe</th><th className="text-right font-normal">Sortino</th>
            <th className="text-right font-normal">Max DD</th></tr></thead>
          <tbody className="mono">
            {([["Portefeuille (preset)", m, "#22d3ee"],
               ...Object.entries(chartBench ?? {}).map(([n, arr]) => [n, statsFrom(arr as any), n === "S&P 500" ? "#f59e0b" : "#a855f7"])] as any[])
              .filter((row) => row[1]).map(([name, st, col]: any) => (
                <tr key={name} className="border-t border-border">
                  <td className="py-1.5 font-sans" style={{ color: col }}>{name}</td>
                  <td className="text-right">{(st.total_return * 100).toFixed(1)}%</td>
                  <td className="text-right">{((st.cagr ?? 0) * 100).toFixed(1)}%</td>
                  <td className="text-right">{st.sharpe?.toFixed(2)}</td>
                  <td className="text-right">{st.sortino?.toFixed(2)}</td>
                  <td className="text-right" style={{ color: "#f43f5e" }}>{(st.max_drawdown * 100).toFixed(1)}%</td>
                </tr>))}
          </tbody>
        </table>
        <p className="text-muted2 text-xs mt-2">Indices RÉELS (^GSPC / ^NDX) rebasés à 10 000 $ au début de la période. KPI recalculés sur la fenêtre sélectionnée.</p>
      </section>

      {/* Cœur indiciel + satellite preset : meilleur ratio (sweep) + part adoptée */}
      {d.index_core?.table?.some((r: any) => r.stats?.available) && (
        <section className="card p-4 overflow-x-auto">
          <h2 className="text-sm uppercase tracking-wide text-muted mb-1">Cœur indiciel ({d.index_core.symbol}) + satellite preset</h2>
          <p className="text-muted2 text-xs mb-3">
            {d.index_core.enabled
              ? <>Adopté : <b style={{ color: "#22d3ee" }}>{Math.round(d.index_core.core_pct * 100)}% {d.index_core.symbol} + {Math.round((1 - d.index_core.core_pct) * 100)}% preset</b>{d.index_core.manual ? " (forcé via QUANT_INDEX_CORE)" : " (auto : meilleur Sharpe qui bat le preset pur)"}.</>
              : <>Aucun mélange ne bat le preset pur sur le Sharpe → <b>100% preset</b> conservé. Force un ratio avec <code>QUANT_INDEX_CORE=0.5</code> si tu veux le tester.</>}
          </p>
          <table className="w-full text-sm">
            <thead className="text-muted text-xs"><tr>
              <th className="text-left font-normal">Cœur {d.index_core.symbol}</th><th className="text-left font-normal">Preset</th>
              <th className="text-right font-normal">CAGR</th><th className="text-right font-normal">Sharpe</th>
              <th className="text-right font-normal">Sortino</th><th className="text-right font-normal">Max DD</th>
              <th className="text-right font-normal">Calmar</th></tr></thead>
            <tbody className="mono">
              {d.index_core.table.filter((r: any) => r.stats?.available).map((r: any) => {
                const sel = Math.abs(r.core - (d.index_core.enabled ? d.index_core.core_pct : 0)) < 1e-6;
                return (
                  <tr key={r.core} className="border-t border-border" style={sel ? { background: "rgba(34,211,238,0.08)" } : undefined}>
                    <td className="py-1.5">{Math.round(r.core * 100)}%{sel && <span className="ml-1" style={{ color: "#22d3ee" }}>◀</span>}</td>
                    <td>{Math.round((1 - r.core) * 100)}%</td>
                    <td className="text-right">{(r.stats.cagr * 100).toFixed(1)}%</td>
                    <td className="text-right">{r.stats.sharpe?.toFixed(2)}</td>
                    <td className="text-right">{r.stats.sortino?.toFixed(2)}</td>
                    <td className="text-right" style={{ color: "#f43f5e" }}>{(r.stats.max_drawdown * 100).toFixed(1)}%</td>
                    <td className="text-right">{r.stats.calmar?.toFixed(2)}</td>
                  </tr>);
              })}
            </tbody>
          </table>
          <p className="text-muted2 text-xs mt-2">Mélange rééquilibré quotidiennement (cœur {d.index_core.core_is_real ? "réel" : "repli"}). On n'adopte le cœur que s'il améliore le Sharpe vs preset pur.</p>
        </section>
      )}
      <section className="card p-4 overflow-x-auto">
        <h2 className="text-sm uppercase tracking-wide text-muted mb-3">Top screener — multi-actifs (score facteurs + edge ML)</h2>
        <table className="w-full text-sm">
          <thead className="text-muted text-xs">
            <tr><th className="text-left font-normal">#</th><th className="text-left font-normal">Actif</th>
            <th className="text-left font-normal">Secteur</th><th className="text-right font-normal">Score</th>
            <th className="text-right font-normal">ML</th><th className="text-left font-normal pl-4">Raison</th></tr>
          </thead>
          <tbody className="mono">
            {s?.rows?.slice(0, 10).map((r: any) => (
              <tr key={r.symbol} className="border-t border-border">
                <td className="py-1.5 text-muted">{r.rank}</td><td>{r.symbol}</td>
                <td className="text-muted font-sans text-xs">{r.sector}</td>
                <td className="text-right">{r.score.toFixed(3)}</td>
                <td className="text-right" style={{ color: r.ml_score == null ? "#9aa1ab" : r.ml_score >= 0.5 ? "#22c55e" : "#f43f5e" }}>
                  {r.ml_score == null ? "—" : `${(r.ml_score * 100).toFixed(0)}%`}</td>
                <td className="pl-4 text-muted font-sans">{r.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </main>
  );
}
