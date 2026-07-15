"use client";
import { useEffect, useMemo, useState } from "react";
import { StepBanner } from "@/components/Pipeline";
import { useDashboard, useScreener, useSentiment, usePresetLedger, usePositions, useAnalytics } from "@/lib/api";
import { MetricCard } from "@/components/MetricCard";
import { RegimeBanner } from "@/components/RegimeBanner";
import { VixPlaybook } from "@/components/VixPlaybook";
import { SentimentBanner } from "@/components/SentimentBanner";
import { EquityChart } from "@/components/EquityChart";
import { PerformancePanel } from "@/components/PerformancePanel";
import { PositionsAlertsTable } from "@/components/PositionsAlertsTable";
import { TechnicalChart } from "@/components/TechnicalChart";
import { PageSkeleton } from "@/components/ui";
import { statsFrom, rebase } from "@/lib/metrics";

const pct = (x: number) => `${(x * 100).toFixed(1)}%`;
const PERIODS: [string, number][] = [["1A", 1], ["2A", 2], ["3A", 3], ["5A", 5], ["Tout", 0]];
// Deltas vs période N−1 (même durée) — DISCRETS : signe seul, gris. En points de % ou en absolu (ratios).
const dPts = (cur?: number, prev?: number | null) => (cur == null || prev == null) ? undefined : `${cur - prev >= 0 ? "+" : ""}${((cur - prev) * 100).toFixed(1)} pt`;
const dAbs = (cur?: number, prev?: number | null) => (cur == null || prev == null) ? undefined : `${cur - prev >= 0 ? "+" : ""}${(cur - prev).toFixed(2)}`;

export default function Dashboard() {
  const { data: d } = useDashboard();
  const { data: s } = useScreener();
  const { data: sent } = useSentiment();
  const [years, setYears] = useState(0);   // 0 = tout
  // Route sobre : coupe le décor animé global sur le dashboard (la donnée est la star).
  useEffect(() => {
    document.documentElement.classList.add("plain");
    return () => document.documentElement.classList.remove("plain");
  }, []);
  const [showLedger, setShowLedger] = useState(false);
  const [showReal, setShowReal] = useState(false);
  const [ledgerQ, setLedgerQ] = useState("");
  const [ledgerSort, setLedgerSort] = useState<{ k: string; dir: number }>({ k: "date", dir: -1 });
  const [selSym, setSelSym] = useState<string | null>(null);
  const { data: ledger } = usePresetLedger();
  const { data: pos } = usePositions();
  const { data: ana } = useAnalytics();
  const eqFull: { t: string; v: number }[] = d?.equity ?? [];
  const sliced = useMemo(() => {
    if (!years || !eqFull.length) return eqFull;
    const last = new Date(eqFull[eqFull.length - 1].t);
    const cut = new Date(last); cut.setFullYear(cut.getFullYear() - years);
    return eqFull.filter((p) => new Date(p.t) >= cut);
  }, [eqFull, years]);
  const chartEquity = useMemo(() => rebase(sliced), [sliced]);
  // Fenêtre N−1 (même durée, juste avant) → deltas KPI. Nulle si période = « Tout » (pas d'antérieur).
  const prevStats = useMemo(() => {
    if (!years || eqFull.length < 2) return null;
    const last = new Date(eqFull[eqFull.length - 1].t);
    const curCut = new Date(last); curCut.setFullYear(curCut.getFullYear() - years);
    const prevCut = new Date(last); prevCut.setFullYear(prevCut.getFullYear() - 2 * years);
    const win = eqFull.filter((p) => { const dt = new Date(p.t); return dt >= prevCut && dt < curCut; });
    return statsFrom(win);
  }, [eqFull, years]);
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
      {/* NATURE des chiffres AVANT les chiffres (audit 07/15 F4) : les KPIs héros sont un
          BACKTEST — sans étiquette, un visiteur les lisait comme de l'argent réel. */}
      <div className="flex items-center gap-2 flex-wrap text-[11px]">
        <span className="px-2 py-0.5 rounded-full uppercase tracking-[0.08em] font-semibold"
          style={{ background: "color-mix(in srgb, var(--warn) 18%, transparent)", color: "var(--warn)" }}>
          Modélisé
        </span>
        <span className="text-muted2">backtest preset ~10 ans, net de frais — pas un compte réel · le réel est sur <a href="/positions" className="text-accent">/positions</a></span>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <MetricCard hero label="Rendement" value={pct(m.total_return)} tone={m.total_return >= 0 ? "pos" : "neg"} delta={dPts(m.total_return, prevStats?.total_return)} />
        <MetricCard hero label="CAGR" value={pct(m.cagr ?? 0)} tone={(m.cagr ?? 0) >= 0 ? "pos" : "neg"} delta={dPts(m.cagr, prevStats?.cagr)} />
        <MetricCard hero label="Sharpe" value={m.sharpe?.toFixed(2)} delta={dAbs(m.sharpe, prevStats?.sharpe)} />
        <MetricCard hero label="Sortino" value={m.sortino?.toFixed(2)} delta={dAbs(m.sortino, prevStats?.sortino)} />
        <MetricCard hero label="Max DD" value={pct(m.max_drawdown)} tone="neg" delta={dPts(m.max_drawdown, prevStats?.max_drawdown)} />
      </div>

      {/* Honnêteté statistique (manifeste) : PSR affiché, DSR multi-essais ≈ 0 assumé. */}
      {d.honesty?.available && (
        <div className="card p-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs" title={d.honesty.note}>
          <span className="px-2 py-0.5 rounded-full text-[10px] uppercase tracking-[0.08em] font-semibold"
            style={{ background: "color-mix(in srgb, var(--accent) 18%, transparent)", color: "var(--accent2)" }}>
            Honnêteté
          </span>
          <span className="mono">PSR <b className="text-fg">{Math.round((d.honesty.psr ?? 0) * 100)}%</b>{" "}
            <span className="text-muted2">P(Sharpe&gt;0)</span></span>
          <span className="mono text-muted">Sharpe ann. {d.honesty.sharpe_annualized}</span>
          <span className="mono text-muted">n={d.honesty.n_obs}</span>
          <span className="text-muted2 basis-full md:basis-auto md:flex-1 md:min-w-0">{d.honesty.note}</span>
        </div>
      )}

      <PerformancePanel equity={chartEquity} benchmarks={chartBench} />
      <PositionsAlertsTable positions={d.real_positions} alerts={d.earnings_risk} />

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
            {([["Portefeuille (backtest preset)", m, "#22d3ee", "backtest"],
               ...(d.real_portfolio?.available ? [["Portefeuille RÉEL (Alpaca+Bitmart)", d.real_portfolio.stats, "#22c55e", "real"]] : []),
               ...Object.entries(chartBench ?? {}).map(([n, arr]) => [n, statsFrom(arr as any), n === "S&P 500" ? "#f59e0b" : "#a855f7", ""])] as any[])
              .filter((row) => row[1]).map(([name, st, col, kind]: any) => {
                const click = kind === "backtest" ? () => setShowLedger(v => !v) : kind === "real" ? () => setShowReal(v => !v) : undefined;
                const open = kind === "backtest" ? showLedger : kind === "real" ? showReal : false;
                return (
                <tr key={name} className={`border-t border-border ${click ? "cursor-pointer hover:bg-surfaceAlt" : ""}`} onClick={click}>
                  <td className="py-1.5 font-sans" style={{ color: col }}>{name}
                    {click && <span className="ml-1 text-accent border-b border-dotted border-border text-xs">journal {open ? "▲" : "▼"}</span>}</td>
                  <td className="text-right">{(st.total_return * 100).toFixed(1)}%</td>
                  <td className="text-right">{((st.cagr ?? 0) * 100).toFixed(1)}%</td>
                  <td className="text-right">{st.sharpe?.toFixed(2)}</td>
                  <td className="text-right">{st.sortino?.toFixed(2)}</td>
                  <td className="text-right" style={{ color: "#f43f5e" }}>{(st.max_drawdown * 100).toFixed(1)}%</td>
                </tr>);
              })}
          </tbody>
        </table>
        <p className="text-muted2 text-xs mt-2"><b>Backtest preset</b> = simulation de la stratégie sur prix RÉELS (~10 ans). <b>Portefeuille RÉEL</b> = ton compte Alpaca+Bitmart (historique court car récent). Clique une ligne pour son journal de trades.</p>
      </section>

      {/* Attribution Alpha / Bêta (vision Citadel) : compétence vs exposition marché */}
      {ana?.available && ana.attribution?.available && (() => {
        const at = ana.attribution, mt = ana.metrics ?? {};
        const aShare = Math.round((at.alpha_share ?? 0) * 100);
        const aPos = (at.alpha_contribution ?? 0) >= 0;
        return (
          <section className="card p-4">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <h2 className="text-sm uppercase tracking-wide text-muted">Performance &amp; attribution (Alpha / Bêta vs QQQ)</h2>
              <span className="text-xs mono" style={{ color: (at.alpha_significant && !at.underperforms_benchmark) ? "#22c55e" : "#f59e0b" }}>{at.verdict}</span>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mt-3">
              <div><div className="text-muted text-xs">Alpha annualisé</div>
                <div className="text-lg mono" style={{ color: (mt.alpha_annual ?? 0) >= 0 ? "#22c55e" : "#ef4444" }}>
                  {mt.alpha_annual == null ? "—" : `${(mt.alpha_annual * 100).toFixed(1)}%`}</div></div>
              <div><div className="text-muted text-xs">Bêta (QQQ)</div><div className="text-lg mono">{mt.beta ?? "—"}</div></div>
              <div><div className="text-muted text-xs">Contrib. Alpha</div>
                <div className="text-lg mono" style={{ color: aPos ? "#22c55e" : "#ef4444" }}>{(at.alpha_contribution * 100).toFixed(1)}%</div></div>
              <div><div className="text-muted text-xs">Contrib. Bêta</div><div className="text-lg mono">{(at.beta_contribution * 100).toFixed(1)}%</div></div>
              <div><div className="text-muted text-xs">Calmar / Corr</div><div className="text-lg mono">{mt.calmar ?? "—"} / {mt.corr ?? "—"}</div></div>
            </div>
            {/* barre de décomposition alpha vs bêta */}
            <div className="mt-3 h-2 rounded overflow-hidden flex" title={`Part de la perf attribuable à l'algo (alpha) : ${aShare}%`}>
              <span style={{ width: `${aShare}%`, background: "#22c55e" }} />
              <span style={{ width: `${100 - aShare}%`, background: "#3b82f6" }} />
            </div>
            <p className="text-muted2 text-xs mt-2">
              <span style={{ color: "#22c55e" }}>■</span> Hors-QQQ {aShare}% ·
              <span style={{ color: "#3b82f6" }}> ■</span> Bêta (marché) {100 - aShare}%.
              Perf preset {(at.portfolio_return * 100).toFixed(1)}% vs QQQ {(at.benchmark_return * 100).toFixed(1)}% — net de frais.
            </p>
            {(at.underperforms_benchmark || at.alpha_significant === false) && (
              <p className="text-xs mt-1" style={{ color: "#f59e0b" }}>
                ⚠ {at.underperforms_benchmark && `Sous-performe QQQ en absolu (${(at.portfolio_return * 100).toFixed(0)}% vs ${(at.benchmark_return * 100).toFixed(0)}%).`}
                {at.alpha_significant === false && ` Alpha non significatif (t=${at.alpha_tstat}).`} Le rendement « hors-QQQ » n'est PAS une preuve de compétence (DSR≈0) — souvent d'autres bêtas + chance.
              </p>
            )}
          </section>
        );
      })()}

      {/* Graphique technique de l'actif cliqué dans un journal (indicateurs + signaux achat/vente) */}
      {selSym && (pos?.series ?? {})[selSym] && (() => {
        // marqueurs = trades du JOURNAL lui-même (cohérence garantie graphe ↔ journal)
        const mk = [
          ...((ledger?.trades ?? []).filter((t: any) => t.symbol === selSym)
            .map((t: any) => ({ t: String(t.date).slice(0, 10), side: t.side === "BUY" ? "buy" : "sell" }))),
          ...((d.real_trades ?? []).filter((t: any) => t.symbol === selSym)
            .map((t: any) => ({ t: String(t.date).slice(0, 10), side: t.side === "buy" ? "buy" : "sell" }))),
        ];
        return (
        <section className="card p-4">
          <div className="flex justify-between items-center mb-2">
            <h2 className="text-sm uppercase tracking-wide text-muted">Graphique technique — {selSym} <span className="normal-case text-xs">· {mk.length} signaux achat/vente du journal</span></h2>
            <button onClick={() => setSelSym(null)} className="text-muted hover:text-fg text-sm">✕</button>
          </div>
          <TechnicalChart data={pos!.series[selSym]} markers={mk} />
        </section>);
      })()}

      {/* Journal RÉEL : ordres réellement exécutés (Alpaca+Bitmart) + positions réelles */}
      {showReal && (() => {
        const rt = d.real_trades ?? [], rp = d.real_positions ?? [], rps = d.real_portfolio?.stats ?? {};
        const dlt = (x?: number) => (x ?? 0).toLocaleString("fr-FR", { maximumFractionDigits: 2 });
        return (
          <section className="card p-4 overflow-x-auto">
            <h2 className="text-sm uppercase tracking-wide text-muted mb-1">Journal RÉEL — compte Alpaca + Bitmart</h2>
            {rt.length === 0 && rp.length === 0 ? (
              <p className="text-muted text-sm">Aucun trade/position réel (comptes non connectés ou aucun ordre passé). Passe des ordres en paper : <code>make live-go</code>.</p>
            ) : (<>
              <p className="text-muted2 text-xs mb-3">Rendement réel <b style={{ color: "#22c55e" }}>{((rps.total_return ?? 0) * 100).toFixed(1)}%</b> · {rt.length} ordres exécutés · {rp.length} positions. 100 % données réelles brokers.</p>
              {rp.length > 0 && <table className="w-full text-sm mono mb-3"><thead className="text-muted text-xs"><tr>
                <th className="text-left font-normal">Position</th><th className="text-left font-normal">Broker</th><th className="text-right font-normal">Qté</th>
                <th className="text-right font-normal">PRU</th><th className="text-right font-normal">Prix</th><th className="text-right font-normal">Valeur</th>
                <th className="text-right font-normal">P&L</th><th className="text-right font-normal">%</th></tr></thead>
                <tbody>{rp.map((p: any, i: number) => (<tr key={i} className="border-t border-border">
                  <td className="py-1">{p.symbol}</td><td className="font-sans text-xs">{p.broker}</td><td className="text-right">{(p.qty ?? 0).toFixed(4)}</td>
                  <td className="text-right">{p.avg_price == null ? "—" : `$${dlt(p.avg_price)}`}</td><td className="text-right">${dlt(p.price)}</td>
                  <td className="text-right">${dlt(p.market_value)}</td>
                  <td className="text-right" style={{ color: p.pnl == null ? "#9aa1ad" : p.pnl >= 0 ? "#22c55e" : "#ef4444" }}>{p.pnl == null ? "—" : `$${dlt(p.pnl)}`}</td>
                  <td className="text-right" style={{ color: (p.pnl_pct ?? 0) >= 0 ? "#22c55e" : "#ef4444" }}>{p.pnl_pct == null ? "—" : `${(p.pnl_pct * 100).toFixed(1)}%`}</td></tr>))}</tbody></table>}
              {rt.length > 0 && <table className="w-full text-sm mono"><thead className="text-muted text-xs"><tr>
                <th className="text-left font-normal">Date</th><th className="text-left font-normal">Actif</th><th className="text-left font-normal">Broker</th>
                <th className="text-left font-normal">Sens</th><th className="text-right font-normal">Qté</th><th className="text-right font-normal">Prix</th>
                <th className="text-right font-normal">Montant</th></tr></thead>
                <tbody>{rt.slice(0, 200).map((t: any, i: number) => (<tr key={i} className="border-t border-border">
                  <td className="py-1 text-muted">{String(t.date).slice(0, 10)}</td><td><span className="text-accent border-b border-dotted border-border cursor-pointer" onClick={() => setSelSym(t.symbol)}>{t.symbol}</span></td><td className="font-sans text-xs">{t.broker}</td>
                  <td style={{ color: t.side === "buy" ? "#22c55e" : "#f43f5e" }}>{t.side === "buy" ? "▲ achat" : "▼ vente"}</td>
                  <td className="text-right">{(t.qty ?? 0).toFixed(4)}</td><td className="text-right">${dlt(t.price)}</td><td className="text-right">${dlt(t.notional)}</td></tr>))}</tbody></table>}
            </>)}
          </section>
        );
      })()}

      {/* Journal de trades du portefeuille de production (P&L réel) — justifie la performance */}
      {showLedger && ledger?.available && (() => {
        const sm = ledger.summary ?? {}; const dlt = (x?: number) => (x ?? 0).toLocaleString("fr-FR", { maximumFractionDigits: 0 });
        const q = ledgerQ.trim().toUpperCase();
        const rows0 = (ledger.trades ?? []).filter((t: any) => !q || String(t.symbol).toUpperCase().includes(q));
        const sorted = [...rows0].sort((a: any, b: any) => {
          let av = a[ledgerSort.k], bv = b[ledgerSort.k];
          av = av == null ? -Infinity : av; bv = bv == null ? -Infinity : bv;
          return typeof av === "string" ? ledgerSort.dir * String(av).localeCompare(String(bv)) : ledgerSort.dir * (av - bv);
        }).slice(0, 400);
        const sortBy = (k: string) => setLedgerSort(s => ({ k, dir: s.k === k ? -s.dir : -1 }));
        const Th = ({ k, label, r }: any) => (
          <th className={`${r ? "text-right" : "text-left"} font-normal cursor-pointer hover:text-fg select-none`} onClick={() => sortBy(k)}>
            {label}{ledgerSort.k === k ? (ledgerSort.dir < 0 ? " ▼" : " ▲") : ""}</th>);
        return (
          <section className="card p-4 overflow-x-auto">
            <h2 className="text-sm uppercase tracking-wide text-muted mb-1">Journal de trades — portefeuille de production (P&L réel)</h2>
            <p className="text-muted2 text-xs mb-2">Backtest discret parts/cash sur prix RÉELS ({sm.start} → {sm.end}). Capital {dlt(sm.init_cap)}$ → {dlt(sm.final_equity)}$ ·
              rendement <b style={{ color: "#22d3ee" }}>{((sm.total_return ?? 0) * 100).toFixed(1)}%</b> ·
              P&L réalisé <b style={{ color: (sm.realized_pnl ?? 0) >= 0 ? "#22c55e" : "#ef4444" }}>{dlt(sm.realized_pnl)}$</b> ·
              latent <b style={{ color: (sm.unrealized_pnl ?? 0) >= 0 ? "#22c55e" : "#ef4444" }}>{dlt(sm.unrealized_pnl)}$</b> · {sm.n_trades} trades. Réconcilie la courbe.</p>
            {sm.fees_on !== false && (
              <p className="text-muted2 text-xs mb-2">Frais RÉELS déduits : <b style={{ color: "#f59e0b" }}>−{dlt(sm.fees_paid)}$</b> ({((sm.fees_pct ?? 0) * 100).toFixed(2)}%) — commission + slippage aux barèmes courtiers
              ({Object.entries(sm.brokers ?? {}).map(([ac, b]: any) => `${ac}→${b}`).join(", ")}). Rendement brut (sans frais) {((sm.gross_return ?? 0) * 100).toFixed(1)}% → <b>net {((sm.total_return ?? 0) * 100).toFixed(1)}%</b>.</p>
            )}
            <p className="text-muted2 text-xs mb-2">Réconciliation {sm.reconciles ? <b style={{ color: "#22c55e" }}>✓</b> : <b style={{ color: "#ef4444" }}>≠</b>} : P&L total <b>{dlt(sm.total_pnl)}$</b> = réalisé {dlt(sm.realized_pnl)}$ + latent {dlt(sm.unrealized_pnl)}$ = gain du graphe {dlt(sm.graph_gain)}$ {sm.fees_on !== false ? <>+ frais {dlt(sm.fees_paid)}$</> : null}. La somme des colonnes du journal (réalisé sur ventes, latent sur achats) égale ces totaux.</p>
            <div className="flex items-center gap-2 mb-2">
              <input value={ledgerQ} onChange={(e) => setLedgerQ(e.target.value)} placeholder="filtrer par actif (ex. QQQ)"
                className="text-sm px-2 py-1 rounded bg-surfaceAlt border border-border outline-none w-48" />
              <span className="text-muted2 text-xs">{rows0.length} trades · clique un en-tête pour trier</span>
            </div>
            <table className="w-full text-sm mono">
              <thead className="text-muted text-xs"><tr>
                <Th k="date" label="Date" /><Th k="symbol" label="Actif" /><Th k="side" label="Sens" />
                <Th k="qty" label="Qté" r /><Th k="price" label="Prix" r /><Th k="avg_cost" label="PRU" r />
                <Th k="notional" label="Montant" r /><Th k="pnl" label="P&L réalisé" r /><Th k="pnl_pct" label="%" r />
                <Th k="latent" label="P&L latent" r /><Th k="latent_pct" label="% lat." r />
                <th className="text-left font-normal pl-3">Motif</th></tr></thead>
              <tbody>{sorted.map((t: any, i: number) => (
                <tr key={i} className="border-t border-border">
                  <td className="py-1 text-muted">{String(t.date).slice(0, 10)}</td>
                  <td><span className="text-accent border-b border-dotted border-border cursor-pointer" onClick={() => setSelSym(t.symbol)}>{t.symbol}</span></td>
                  <td style={{ color: t.side === "BUY" ? "#22c55e" : "#f43f5e" }}>{t.side === "BUY" ? "▲ achat" : "▼ vente"}</td>
                  <td className="text-right">{t.qty}</td><td className="text-right">${t.price}</td>
                  <td className="text-right text-muted">{t.avg_cost != null ? `$${t.avg_cost}` : "—"}</td>
                  <td className="text-right">${dlt(t.notional)}</td>
                  <td className="text-right" style={{ color: t.pnl == null ? "#9aa1ad" : t.pnl >= 0 ? "#22c55e" : "#ef4444" }}>{t.pnl == null ? "—" : `$${dlt(t.pnl)}`}</td>
                  <td className="text-right" style={{ color: t.pnl_pct == null ? "#9aa1ad" : t.pnl_pct >= 0 ? "#22c55e" : "#ef4444" }}>{t.pnl_pct == null ? "—" : `${(t.pnl_pct * 100).toFixed(1)}%`}</td>
                  <td className="text-right" style={{ color: t.latent == null ? "#9aa1ad" : t.latent >= 0 ? "#22c55e" : "#ef4444" }}>{t.latent == null ? "—" : `$${dlt(t.latent)}`}</td>
                  <td className="text-right" style={{ color: t.latent_pct == null ? "#9aa1ad" : t.latent_pct >= 0 ? "#22c55e" : "#ef4444" }}>{t.latent_pct == null ? "—" : `${(t.latent_pct * 100).toFixed(1)}%`}</td>
                  <td className="pl-3 text-muted font-sans text-xs">{t.reason}</td>
                </tr>))}</tbody>
            </table>
            <p className="text-muted2 text-xs mt-2">Positions ouvertes : {(ledger.open_positions ?? []).map((p: any) => `${p.symbol} (${(p.pnl_pct != null ? (p.pnl_pct * 100).toFixed(0) : "—")}%)`).join(" · ")}</p>
          </section>
        );
      })()}

      {/* Cœur(s) indiciel(s) + satellite preset : blend de production (preset pur vs mélange) */}
      {d.index_core?.enabled && (
        <section className="card p-4 overflow-x-auto">
          <h2 className="text-sm uppercase tracking-wide text-muted mb-1">Cœur indiciel + satellite preset</h2>
          <p className="text-muted2 text-xs mb-3">
            Allocation active : <b style={{ color: "#22d3ee" }}>
            {(d.index_core.components ?? []).map((c: any) => `${Math.round(c.pct * 100)}% ${c.kind.toUpperCase()}`).join(" + ")}
            {" + "}{Math.round((1 - d.index_core.core_pct) * 100)}% preset</b>. Top-10 {d.index_core.mc_weighting === "market_cap"
              ? "pondéré par market cap réelle" : "pondéré par proxy dollar-volume (lance make ingest-mktcap)"}, re-classé chaque trimestre.
          </p>
          <table className="w-full text-sm">
            <thead className="text-muted text-xs"><tr>
              <th className="text-left font-normal">Stratégie</th>
              <th className="text-right font-normal">CAGR</th><th className="text-right font-normal">Sharpe</th>
              <th className="text-right font-normal">Sortino</th><th className="text-right font-normal">Max DD</th></tr></thead>
            <tbody className="mono">
              {([["Preset pur", d.index_core.base_stats, "#9aa1ab"],
                 ["Mélange (production)", d.index_core.blended_stats, "#22d3ee"]] as any[])
                .filter((r) => r[1]?.available).map(([name, st, col]: any) => (
                  <tr key={name} className="border-t border-border">
                    <td className="py-1.5 font-sans" style={{ color: col }}>{name}</td>
                    <td className="text-right">{(st.cagr * 100).toFixed(1)}%</td>
                    <td className="text-right">{st.sharpe?.toFixed(2)}</td>
                    <td className="text-right">{st.sortino?.toFixed(2)}</td>
                    <td className="text-right" style={{ color: "#f43f5e" }}>{(st.max_drawdown * 100).toFixed(1)}%</td>
                  </tr>))}
            </tbody>
          </table>
          {d.index_core.core_holdings?.length > 0 && (
            <p className="text-muted2 text-xs mt-2">Panier top-10 : {d.index_core.core_holdings.join(", ")}.</p>
          )}
          <p className="text-muted2 text-xs mt-1">Détail des ratios : <code>make index-core</code>. Changer le blend : <code>QUANT_CORE_SPEC="qqq:0.5"</code> (défaut) — ajoute <code>,megacap:0.10</code> ou <code>sector_mom:0.25</code> pour un cœur mixte.</p>
        </section>
      )}

      {/* Comparaison comptes RÉELS (Alpaca / Crypto) vs indices */}
      {d.account_compare?.available ? (() => {
        const ac = d.account_compare; const col: Record<string, string> = { "Alpaca (réel)": "#22d3ee", "Crypto (réel)": "#a855f7", "S&P 500": "#f59e0b", "Nasdaq 100": "#8b5cf6" };
        const names = Object.keys(ac.series ?? {});
        const main = names[0]; const benchNames = names.slice(1);
        const benchmarks = Object.fromEntries(benchNames.map((n) => [n, ac.series[n]]));
        return (
          <section className="card p-4 overflow-x-auto">
            <h2 className="text-sm uppercase tracking-wide text-muted mb-1">Mes comptes réels vs indices <span className="text-[11px] normal-case">· base 100 · {ac.window?.[0]} → {ac.window?.[1]}</span></h2>
            {main && <EquityChart series={ac.series[main]} benchmarks={benchmarks} />}
            <table className="w-full text-sm mt-3">
              <thead className="text-muted text-xs"><tr><th className="text-left font-normal">Série</th>
                <th className="text-right font-normal">Rendement</th><th className="text-right font-normal">CAGR</th>
                <th className="text-right font-normal">Sharpe</th><th className="text-right font-normal">Max DD</th></tr></thead>
              <tbody className="mono">{(ac.kpis ?? []).map((k: any) => (
                <tr key={k.name} className="border-t border-border">
                  <td className="py-1.5 font-sans" style={{ color: col[k.name] ?? "#9aa1ab" }}>{k.name}</td>
                  <td className="text-right">{(k.return * 100).toFixed(1)}%</td>
                  <td className="text-right">{(k.cagr * 100).toFixed(1)}%</td>
                  <td className="text-right">{k.sharpe?.toFixed(2)}</td>
                  <td className="text-right" style={{ color: "#f43f5e" }}>{(k.maxdd * 100).toFixed(1)}%</td>
                </tr>))}</tbody>
            </table>
            <p className="text-muted2 text-xs mt-2">Données 100 % réelles (historique broker + indices ^GSPC/^NDX). L'historique réel des comptes est court au début et s'étoffe chaque jour.</p>
          </section>
        );
      })() : (
        <section className="card p-4">
          <h2 className="text-sm uppercase tracking-wide text-muted mb-1">Mes comptes réels vs indices</h2>
          <p className="text-muted text-xs">Historique réel des comptes en constitution (quelques jours de suivi nécessaires) ou comptes non connectés. La comparaison s'affichera dès que des données réelles seront disponibles.</p>
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
