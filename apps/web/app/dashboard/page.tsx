"use client";
import { useEffect, useMemo, useState } from "react";
import { StepBanner } from "@/components/Pipeline";
import { useDashboard, useScreener, useSentiment, usePresetLedger, usePositions, useAnalytics } from "@/lib/api";
import { MetricCard } from "@/components/MetricCard";
import { expliqueDrawdown, expliqueSharpe } from "@/lib/plain";
import { RegimeBanner } from "@/components/RegimeBanner";
import { VixPlaybook } from "@/components/VixPlaybook";
import { SentimentBanner } from "@/components/SentimentBanner";
import { EquityChart } from "@/components/EquityChart";
import { PerformancePanel } from "@/components/PerformancePanel";
import { PositionsAlertsTable } from "@/components/PositionsAlertsTable";
import { HonestyStrip, TradeStatsRow } from "@/components/DashboardStrips";
import { TechnicalChart } from "@/components/TechnicalChart";
import { PageSkeleton } from "@/components/ui";
import { statsFrom, rebase } from "@/lib/metrics";
import CompositionModeleVsReel from "@/components/CompositionModeleVsReel";
import EcartReplication from "@/components/EcartReplication";
import { DateArrete } from "@/components/DateArrete";

const pct = (x: number) => `${(x * 100).toFixed(1)}%`;
// Fenêtre lisible à partir du nombre de points quotidiens. Affichée sur CHAQUE ligne : sans
// elle, un rendement de 401 % sur dix ans se lit à côté d'un -1,5 % sur deux mois comme s'ils
// étaient comparables. Ils ne le sont pas.
function fenetre(n?: number): string {
  if (!Number.isFinite(Number(n)) || Number(n) < 1) return "—";
  const j = Number(n), a = j / 252;
  if (a >= 1) return `${a.toFixed(a >= 10 ? 0 : 1)} an${a >= 2 ? "s" : ""}`;
  const m = j / 21;
  return m >= 1 ? `${m.toFixed(0)} mois` : `${j} j`;
}

const PERIODS: [string, number][] = [["1A", 1], ["2A", 2], ["3A", 3], ["5A", 5], ["Tout", 0]];
// Deltas vs période N−1 (même durée) — DISCRETS : signe seul, gris. En points de % ou en absolu (ratios).
const dPts = (cur?: number, prev?: number | null) => (cur == null || prev == null) ? undefined : `${cur - prev >= 0 ? "+" : ""}${((cur - prev) * 100).toFixed(1)} pt`;
const dAbs = (cur?: number, prev?: number | null) => (cur == null || prev == null) ? undefined : `${cur - prev >= 0 ? "+" : ""}${(cur - prev).toFixed(2)}`;


// COMPOSITION — MODÈLE vs RÉEL.
//
// Le portefeuille réel avait un tableau complet ; le portefeuille du backtest était écrasé en
// UNE LIGNE de texte (« QQQ (167%) · AMCR (437%) … »), alors que les mêmes champs existent des
// deux côtés (qty, prix, valeur, P&L). Impossible de comparer ce qu'on ne peut pas aligner.
//
// On compare des POIDS, pas des montants : le backtest part de 10 000 $ et le compte réel en
// vaut 100 000. Mettre « 2 400 $ » face à « 3 700 $ » ne dit rien ; « 24 % contre 3,7 % » dit
// tout. L'écart de poids est la seule quantité qui répond à « est-ce que je réplique ? ».
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
      <DateArrete date={d.as_of} quoi="Chiffres du tableau de bord" />
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
        <span className="text-muted2">simulation de la stratégie sur des prix réels, frais déduits — ce n'est pas de l'argent réel · votre argent réel est sur <a href="/positions" className="text-accent">/positions</a></span>
        {/* La fenêtre EN TOUTES LETTRES sous les tuiles. Sans elle, trois « gain / risque »
            différents cohabitaient sur la même page — 2,43 ici, 1,07 dans le bandeau
            honnêteté, 0,98 pour la stratégie seule — et rien ne disait qu'ils ne portaient
            pas sur la même période. On lisait une contradiction là où il n'y avait que
            trois questions différentes. */}
        <span className="w-full text-muted2">
          Ces cinq chiffres portent sur <b>{fenetre((m as any)?.n)}</b>
          {sliced.length > 1 && <> — du {new Date(sliced[0].t).toLocaleDateString("fr-FR")} au {new Date(sliced[sliced.length - 1].t).toLocaleDateString("fr-FR")}</>}
          {" "}(bouton « Période » ci-dessus). Les autres « gain / risque » de la page portent
          sur d'autres fenêtres : chacun le dit à côté de lui.
        </span>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <MetricCard hero label="Gain total" value={pct(m.total_return)} tone={m.total_return >= 0 ? "pos" : "neg"} delta={dPts(m.total_return, prevStats?.total_return)}
          explication="Depuis le début de la période mesurée." />
        <MetricCard hero label="Gain par an" terme="CAGR" value={pct(m.cagr ?? 0)} tone={(m.cagr ?? 0) >= 0 ? "pos" : "neg"} delta={dPts(m.cagr, prevStats?.cagr)}
          explication="Rythme moyen, une fois lissées les bonnes et les mauvaises années." />
        <MetricCard hero label="Gain / risque" terme="Sharpe" value={m.sharpe?.toFixed(2)} delta={dAbs(m.sharpe, prevStats?.sharpe)}
          explication={expliqueSharpe(m.sharpe).phrase} />
        <MetricCard hero label="Gain / baisses" terme="Sortino" value={m.sortino?.toFixed(2)} delta={dAbs(m.sortino, prevStats?.sortino)}
          explication="Même idée que le rapport gain / risque, mais ne compte que les baisses." />
        <MetricCard hero label="Pire baisse" terme="Max DD" value={pct(m.max_drawdown)} tone="neg" delta={dPts(m.max_drawdown, prevStats?.max_drawdown)}
          explication={expliqueDrawdown(m.max_drawdown).phrase} />
      </div>

      <TradeStatsRow ts={d.trade_stats} />
      <HonestyStrip honesty={d.honesty} />

      <PerformancePanel equity={chartEquity} benchmarks={chartBench} />
      <PositionsAlertsTable positions={d.real_positions} alerts={d.earnings_risk} />

      {/* Comparaison KPI : portefeuille vs benchmarks, sur la période choisie */}
      <section className="card p-4 overflow-x-auto">
        <h2 className="text-sm uppercase tracking-wide text-muted mb-3">Comparé aux grands indices ({PERIODS.find(([, y]) => y === years)?.[0] ?? "Tout"})</h2>
        <table className="w-full text-sm">
          <thead className="text-muted text-xs"><tr>
            <th className="text-left font-normal">Ligne comparée</th>
            <th className="text-right font-normal" title="Durée réellement couverte par cette ligne.">Durée couverte</th>
            <th className="text-right font-normal" title="Gain total sur toute la fenêtre.">Gain total</th>
            <th className="text-right font-normal" title="Gain moyen par an (CAGR), une fois lissées les bonnes et les mauvaises années.">Gain / an</th>
            <th className="text-right font-normal" title="Sharpe : combien de gain pour chaque unité de secousses subies. Plus c'est haut, mieux c'est.">Gain / risque</th>
            <th className="text-right font-normal" title="Sortino : même idée, mais ne compte que les baisses.">Gain / baisses</th>
            <th className="text-right font-normal" title="La pire chute depuis un sommet sur la fenêtre.">Pire baisse</th></tr></thead>
          <tbody className="mono">
            {([["Portefeuille simulé (stratégie)", m, "#22d3ee", "backtest"],
               ...(d.real_portfolio?.available ? [["Portefeuille RÉEL (vos comptes)", d.real_portfolio.stats, "#22c55e", "real"]] : []),
               ...Object.entries(chartBench ?? {}).map(([n, arr]) => [n, statsFrom(arr as any), n === "S&P 500" ? "#f59e0b" : "#a855f7", ""])] as any[])
              .filter((row) => row[1]).map(([name, st, col, kind]: any) => {
                const click = kind === "backtest" ? () => setShowLedger(v => !v) : kind === "real" ? () => setShowReal(v => !v) : undefined;
                const open = kind === "backtest" ? showLedger : kind === "real" ? showReal : false;
                return (
                <tr key={name} className={`border-t border-border ${click ? "cursor-pointer hover:bg-surfaceAlt" : ""}`} onClick={click}>
                  <td className="py-1.5 font-sans" style={{ color: col }}>{name}
                    {click && <span className="ml-1 text-accent border-b border-dotted border-border text-xs">journal {open ? "▲" : "▼"}</span>}
                    {st.flux?.contamine && (
                      <span className="ml-2 text-[10px] px-1.5 py-0.5 rounded border border-border text-muted2"
                        title={st.flux.note}>{st.flux.n_flows} mouvement{st.flux.n_flows > 1 ? "s" : ""} neutralisé{st.flux.n_flows > 1 ? "s" : ""}</span>)}</td>
                  <td className="text-right text-muted2 text-xs">{fenetre(st.n)}</td>
                  <td className="text-right">{(st.total_return * 100).toFixed(1)}%</td>
                  <td className="text-right">{((st.cagr ?? 0) * 100).toFixed(1)}%</td>
                  <td className="text-right">{st.sharpe?.toFixed(2)}</td>
                  <td className="text-right">{st.sortino?.toFixed(2)}</td>
                  <td className="text-right" style={{ color: "#f43f5e" }}>{(st.max_drawdown * 100).toFixed(1)}%</td>
                </tr>);
              })}
          </tbody>
        </table>
        <p className="text-muted2 text-xs mt-2">
          <b>Regardez d'abord « Durée couverte »</b> : ces lignes ne couvrent pas la même période,
          donc leurs gains totaux ne se comparent pas. Le <b>portefeuille simulé</b> rejoue la
          stratégie sur ~10 ans de prix réels ; le <b>portefeuille RÉEL</b> ne compte que depuis
          l'ouverture de vos comptes. Un gain sur dix ans face à un gain sur deux mois ne dit rien —
          seuls le gain par an et le gain / risque restent lisibles côte à côte, et encore : sur une
          période courte, ils bougent énormément d'une semaine à l'autre.
          <br />
          Sur vos comptes réels, vos versements et retraits sont <b>mis de côté</b> dans le calcul :
          virer 1 000 € n'est ni un gain ni une perte, seule la façon dont l'argent a travaillé
          compte. La pastille indique combien de mouvements ont été écartés. Cliquez une ligne pour
          voir le détail de ses achats et ventes.
        </p>
      </section>

      {/* Attribution Alpha / Bêta (vision Citadel) : compétence vs exposition marché */}
      {ana?.available && ana.attribution?.available && (() => {
        const at = ana.attribution, mt = ana.metrics ?? {};
        const aShare = Math.round((at.alpha_share ?? 0) * 100);
        const aPos = (at.alpha_contribution ?? 0) >= 0;
        return (
          <section className="card p-4">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <h2 className="text-sm uppercase tracking-wide text-muted" title="Alpha = la part du résultat qui ne s'explique pas par le marché. Bêta = la part qui s'explique par lui.">Ce qui vient du marché, ce qui vient de la stratégie (face à QQQ)</h2>
              <span className="text-xs mono" style={{ color: (at.alpha_significant && !at.underperforms_benchmark) ? "#22c55e" : "#f59e0b" }}>{at.verdict}</span>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mt-3">
              <div title="Ce que la stratégie ajoute par an au-delà du marché, une fois retiré ce que le marché lui a donné.">
                <div className="text-muted text-xs">Apport propre / an</div>
                <div className="text-lg mono" style={{ color: (mt.alpha_annual ?? 0) >= 0 ? "#22c55e" : "#ef4444" }}>
                  {mt.alpha_annual == null ? "—" : `${(mt.alpha_annual * 100).toFixed(1)}%`}</div></div>
              <div title="À combien le portefeuille suit le marché. 1 = il bouge comme QQQ ; 0,5 = deux fois moins ; 1,5 = une fois et demie plus fort, à la hausse comme à la baisse.">
                <div className="text-muted text-xs">Sensibilité au marché</div><div className="text-lg mono">{mt.beta ?? "—"}</div></div>
              <div title="Part du résultat total venue de la stratégie elle-même.">
                <div className="text-muted text-xs">Dû à la stratégie</div>
                <div className="text-lg mono" style={{ color: aPos ? "#22c55e" : "#ef4444" }}>{(at.alpha_contribution * 100).toFixed(1)}%</div></div>
              <div title="Part du résultat total venue simplement du marché qui montait ou descendait.">
                <div className="text-muted text-xs">Dû au marché</div><div className="text-lg mono">{(at.beta_contribution * 100).toFixed(1)}%</div></div>
              <div title="Calmar : gain par an rapporté à la pire baisse. Corrélation : à quel point le portefeuille et QQQ bougent ensemble (1 = à l'identique, 0 = sans rapport).">
                <div className="text-muted text-xs">Gain / pire baisse · lien avec QQQ</div><div className="text-lg mono">{mt.calmar ?? "—"} / {mt.corr ?? "—"}</div></div>
            </div>
            {/* barre de décomposition alpha vs bêta */}
            <div className="mt-3 h-2 rounded overflow-hidden flex" title={`Part du résultat venue de la stratégie elle-même : ${aShare}%`}>
              <span style={{ width: `${aShare}%`, background: "#22c55e" }} />
              <span style={{ width: `${100 - aShare}%`, background: "#3b82f6" }} />
            </div>
            <p className="text-muted2 text-xs mt-2">
              <span style={{ color: "#22c55e" }}>■</span> La stratégie {aShare}% ·
              <span style={{ color: "#3b82f6" }}> ■</span> Le marché {100 - aShare}%.
              Portefeuille simulé {(at.portfolio_return * 100).toFixed(1)}% contre QQQ {(at.benchmark_return * 100).toFixed(1)}% — frais déduits,
              sur les {at.n_observations ?? "—"} jours de bourse où les deux étaient ouverts.
            </p>
            {at.alignement === "position" && (
              <p className="text-xs mt-1" style={{ color: "#f59e0b" }}>
                ⚠ On n'a pas les dates exactes de l'indice de comparaison : les deux séries ont été alignées à l'aveugle, ligne par ligne. Les deux chiffres ci-dessus ne sont donc pas fiables.
              </p>
            )}
            {(at.underperforms_benchmark || at.alpha_significant === false) && (
              <p className="text-xs mt-1" style={{ color: "#f59e0b" }}>
                ⚠ {at.underperforms_benchmark && `Fait moins bien que QQQ tout court (${(at.portfolio_return * 100).toFixed(0)} % contre ${(at.benchmark_return * 100).toFixed(0)} %).`}
                {at.alpha_significant === false && ` L'apport propre n'est pas assez net pour être distingué du hasard (t = ${at.alpha_tstat}).`} La part « qui ne vient pas de QQQ » ne prouve PAS un savoir-faire : le plus souvent, c'est l'exposition à d'autres choses que QQQ, plus de la chance.
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
            <h2 className="text-sm uppercase tracking-wide text-muted">Graphique — {selSym} <span className="normal-case text-xs">· {mk.length} achats et ventes marqués sur la courbe</span></h2>
            <button onClick={() => setSelSym(null)} className="text-muted hover:text-fg text-sm">✕</button>
          </div>
          <TechnicalChart data={pos!.series[selSym]} markers={mk} />
        </section>);
      })()}

      {/* Journal RÉEL : ordres réellement exécutés + positions réelles */}
      {showReal && (() => {
        const rt = d.real_trades ?? [], rp = d.real_positions ?? [], rps = d.real_portfolio?.stats ?? {};
        const dlt = (x?: number) => (x ?? 0).toLocaleString("fr-FR", { maximumFractionDigits: 2 });
        return (
          <section className="card p-4 overflow-x-auto">
            <h2 className="text-sm uppercase tracking-wide text-muted mb-1">Vos comptes réels — ce qui s'est vraiment passé</h2>
            {rt.length === 0 && rp.length === 0 ? (
              <p className="text-muted text-sm">Aucune position ni aucun ordre réel : soit les comptes ne sont pas connectés, soit rien n'a encore été acheté. Pour passer des ordres en simulation : <code>make live-go</code>.</p>
            ) : (<>
              <p className="text-muted2 text-xs mb-3">Gain réel <b style={{ color: "#22c55e" }}>{((rps.total_return ?? 0) * 100).toFixed(1)}%</b> · {rt.length} ordres passés · {rp.length} positions. Chiffres lus directement chez vos courtiers, rien de simulé.</p>
              {rp.length > 0 && <table className="w-full text-sm mono mb-3"><thead className="text-muted text-xs"><tr>
                <th className="text-left font-normal">Position</th><th className="text-left font-normal">Courtier</th><th className="text-right font-normal">Quantité</th>
                <th className="text-right font-normal" title="Prix moyen auquel vous avez acheté cette ligne.">Prix d'achat moyen</th><th className="text-right font-normal">Prix du jour</th><th className="text-right font-normal">Valeur</th>
                <th className="text-right font-normal" title="Gain ou perte de la ligne, en euros.">Gain / perte</th><th className="text-right font-normal">%</th></tr></thead>
                <tbody>{rp.map((p: any, i: number) => (<tr key={i} className="border-t border-border">
                  <td className="py-1">{p.symbol}</td><td className="font-sans text-xs">{p.broker}</td><td className="text-right">{(p.qty ?? 0).toFixed(4)}</td>
                  <td className="text-right">{p.avg_price == null ? "—" : `$${dlt(p.avg_price)}`}</td><td className="text-right">${dlt(p.price)}</td>
                  <td className="text-right">${dlt(p.market_value)}</td>
                  <td className="text-right" style={{ color: p.pnl == null ? "#9aa1ad" : p.pnl >= 0 ? "#22c55e" : "#ef4444" }}>{p.pnl == null ? "—" : `$${dlt(p.pnl)}`}</td>
                  <td className="text-right" style={{ color: (p.pnl_pct ?? 0) >= 0 ? "#22c55e" : "#ef4444" }}>{p.pnl_pct == null ? "—" : `${(p.pnl_pct * 100).toFixed(1)}%`}</td></tr>))}</tbody></table>}
              {rt.length > 0 && <table className="w-full text-sm mono"><thead className="text-muted text-xs"><tr>
                <th className="text-left font-normal">Date</th><th className="text-left font-normal">Actif</th><th className="text-left font-normal">Courtier</th>
                <th className="text-left font-normal">Sens</th><th className="text-right font-normal">Quantité</th><th className="text-right font-normal">Prix</th>
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
            <h2 className="text-sm uppercase tracking-wide text-muted mb-1">Le détail de la simulation — chaque achat, chaque vente</h2>
            <p className="text-muted2 text-xs mb-2">Simulation en parts entières et en liquidités, sur des prix RÉELS ({sm.start} → {sm.end}). Départ {dlt(sm.init_cap)}$ → arrivée {dlt(sm.final_equity)}$ ·
              gain <b style={{ color: "#22d3ee" }}>{((sm.total_return ?? 0) * 100).toFixed(1)}%</b> ·
              déjà encaissé (lignes vendues) <b style={{ color: (sm.realized_pnl ?? 0) >= 0 ? "#22c55e" : "#ef4444" }}>{dlt(sm.realized_pnl)}$</b> ·
              sur le papier (lignes encore détenues) <b style={{ color: (sm.unrealized_pnl ?? 0) >= 0 ? "#22c55e" : "#ef4444" }}>{dlt(sm.unrealized_pnl)}$</b> · {sm.n_trades} opérations. Ces chiffres retombent exactement sur la courbe.</p>
            {sm.fees_on !== false && (
              <p className="text-muted2 text-xs mb-2">Frais RÉELS déduits : <b style={{ color: "#f59e0b" }}>−{dlt(sm.fees_paid)}$</b> ({((sm.fees_pct ?? 0) * 100).toFixed(2)} %) — commission du courtier, plus l'écart entre le prix visé et le prix réellement obtenu, aux tarifs réels
              ({Object.entries(sm.brokers ?? {}).map(([ac, b]: any) => `${ac}→${b}`).join(", ")}). Sans les frais : {((sm.gross_return ?? 0) * 100).toFixed(1)} % → <b>avec les frais : {((sm.total_return ?? 0) * 100).toFixed(1)} %</b>.</p>
            )}
            <p className="text-muted2 text-xs mb-2">Les comptes tombent juste {sm.reconciles ? <b style={{ color: "#22c55e" }}>✓</b> : <b style={{ color: "#ef4444" }}>≠</b>} : gain total <b>{dlt(sm.total_pnl)}$</b> = déjà encaissé {dlt(sm.realized_pnl)}$ + sur le papier {dlt(sm.unrealized_pnl)}$ = gain lu sur le graphe {dlt(sm.graph_gain)}$ {sm.fees_on !== false ? <>+ frais {dlt(sm.fees_paid)}$</> : null}. Additionnez les colonnes du tableau ci-dessous : vous retrouvez ces totaux.</p>
            <div className="flex items-center gap-2 mb-2">
              <input value={ledgerQ} onChange={(e) => setLedgerQ(e.target.value)} placeholder="filtrer par actif (ex. QQQ)"
                className="text-sm px-2 py-1 rounded bg-surfaceAlt border border-border outline-none w-48" />
              <span className="text-muted2 text-xs">{rows0.length} opérations · cliquez un titre de colonne pour trier</span>
            </div>
            <table className="w-full text-sm mono">
              <thead className="text-muted text-xs"><tr>
                <Th k="date" label="Date" /><Th k="symbol" label="Actif" /><Th k="side" label="Sens" />
                <Th k="qty" label="Quantité" r /><Th k="price" label="Prix" r /><Th k="avg_cost" label="Prix d'achat moyen" r />
                <Th k="notional" label="Montant" r /><Th k="pnl" label="Encaissé" r /><Th k="pnl_pct" label="%" r />
                <Th k="latent" label="Sur le papier" r /><Th k="latent_pct" label="%" r />
                <th className="text-left font-normal pl-3">Pourquoi</th></tr></thead>
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
            <CompositionModeleVsReel modele={ledger.open_positions ?? []} reel={d.real_positions ?? []} />
            <EcartReplication r={d.replication} />
          </section>
        );
      })()}

      {/* Cœur(s) indiciel(s) + satellite preset : blend de production (preset pur vs mélange) */}
      {d.index_core?.enabled && (
        <section className="card p-4 overflow-x-auto">
          <h2 className="text-sm uppercase tracking-wide text-muted mb-1">Un socle d'indices, et la stratégie autour</h2>
          <p className="text-muted2 text-xs mb-3">
            <b>Attention, autre fenêtre</b> : ce tableau compare les deux approches sur tout
            l'historique disponible, pas sur la période choisie en haut de page.{" "}
            L'idée : une grosse part placée sur des indices larges, qui bouge peu, et le reste confié
            à la stratégie. Répartition en cours : <b style={{ color: "#22d3ee" }}>
            {(d.index_core.components ?? []).map((c: any) => `${Math.round(c.pct * 100)}% ${c.kind.toUpperCase()}`).join(" + ")}
            {" + "}{Math.round((1 - d.index_core.core_pct) * 100)}% stratégie</b>. Les 10 plus grosses lignes du socle sont {d.index_core.mc_weighting === "market_cap"
              ? "pondérées par la taille réelle des entreprises" : "pondérées par les montants échangés chaque jour, faute de la taille réelle (lancez make ingest-mktcap pour l'obtenir)"}, et la liste est refaite chaque trimestre.
          </p>
          <table className="w-full text-sm">
            <thead className="text-muted text-xs"><tr>
              <th className="text-left font-normal">Stratégie</th>
              <th className="text-right font-normal" title="Gain moyen par an.">Gain / an</th><th className="text-right font-normal" title="Combien de gain pour chaque unité de secousses subies.">Gain / risque</th>
              <th className="text-right font-normal" title="Même idée, mais ne compte que les baisses.">Gain / baisses</th><th className="text-right font-normal" title="La pire chute depuis un sommet.">Pire baisse</th></tr></thead>
            <tbody className="mono">
              {([["La stratégie seule", d.index_core.base_stats, "#9aa1ab"],
                 ["Socle + stratégie (ce qui tourne)", d.index_core.blended_stats, "#22d3ee"]] as any[])
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
            <p className="text-muted2 text-xs mt-2">Les 10 lignes du socle : {d.index_core.core_holdings.join(", ")}.</p>
          )}
          <p className="text-muted2 text-xs mt-1">Voir tous les chiffres : <code>make index-core</code>. Changer la répartition : <code>QUANT_CORE_SPEC="qqq:0.5"</code> (valeur par défaut) — ajoutez <code>,megacap:0.10</code> ou <code>sector_mom:0.25</code> pour mélanger plusieurs socles.</p>
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
            <h2 className="text-sm uppercase tracking-wide text-muted mb-1">Mes comptes réels face aux indices <span className="text-[11px] normal-case">· tout le monde part de 100 · {ac.window?.[0]} → {ac.window?.[1]}</span></h2>
            {main && <EquityChart series={ac.series[main]} benchmarks={benchmarks} />}
            <table className="w-full text-sm mt-3">
              <thead className="text-muted text-xs"><tr><th className="text-left font-normal">Ligne comparée</th>
                <th className="text-right font-normal">Gain total</th><th className="text-right font-normal" title="Gain moyen par an.">Gain / an</th>
                <th className="text-right font-normal" title="Combien de gain pour chaque unité de secousses subies.">Gain / risque</th><th className="text-right font-normal" title="La pire chute depuis un sommet.">Pire baisse</th></tr></thead>
              <tbody className="mono">{(ac.kpis ?? []).map((k: any) => (
                <tr key={k.name} className="border-t border-border">
                  <td className="py-1.5 font-sans" style={{ color: col[k.name] ?? "#9aa1ab" }}>{k.name}</td>
                  <td className="text-right">{(k.return * 100).toFixed(1)}%</td>
                  <td className="text-right">{(k.cagr * 100).toFixed(1)}%</td>
                  <td className="text-right">{k.sharpe?.toFixed(2)}</td>
                  <td className="text-right" style={{ color: "#f43f5e" }}>{(k.maxdd * 100).toFixed(1)}%</td>
                </tr>))}</tbody>
            </table>
            <p className="text-muted2 text-xs mt-2">Chiffres réels : l'historique de vos comptes chez le courtier, face aux indices (ou aux ETF qui les suivent). Si la série d'un indice n'est plus mise à jour, elle est retirée du tableau — on ne prolonge jamais une courbe avec des valeurs inventées.</p>
          </section>
        );
      })() : (
        <section className="card p-4">
          <h2 className="text-sm uppercase tracking-wide text-muted mb-1">Mes comptes réels vs indices</h2>
          <p className="text-muted text-xs">Il faut quelques jours de suivi pour comparer quoi que ce soit — ou bien les comptes ne sont pas connectés. La comparaison apparaîtra dès qu'il y aura de vrais chiffres.</p>
        </section>
      )}
      <section className="card p-4 overflow-x-auto">
        <h2 className="text-sm uppercase tracking-wide text-muted mb-3">Les mieux notés aujourd'hui, toutes catégories</h2>
        <table className="w-full text-sm">
          <thead className="text-muted text-xs">
            <tr><th className="text-left font-normal">#</th><th className="text-left font-normal">Actif</th>
            <th className="text-left font-normal">Secteur</th><th className="text-right font-normal" title="Note issue du croisement de plusieurs critères de marché.">Note</th>
            <th className="text-right font-normal" title="Probabilité de hausse estimée par le modèle appris sur l'historique. 50 % = il ne sait pas.">Modèle</th><th className="text-left font-normal pl-4">Pourquoi</th></tr>
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
