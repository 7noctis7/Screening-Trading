"use client";
import { useState } from "react";
import { useLive } from "@/lib/api";
import { PageSkeleton } from "@/components/ui";
import { nomVenue } from "@/lib/venue";
import { StepBanner } from "@/components/Pipeline";
import { EquityChart } from "@/components/EquityChart";
import { TechnicalChart } from "@/components/TechnicalChart";

const eur = (x?: number) => Math.round(x ?? 0).toLocaleString("fr-FR");
const pct = (x?: number) => `${((x ?? 0) * 100).toFixed(1)}%`;

function Perf({ p, name }: { p: any; name: string }) {
  // historique réel encore trop court → message au lieu d'un graphe trompeur
  if (!p?.available) {
    return p?.source === "réel-court"
      ? <p className="text-muted2 text-[11px] mt-3">📈 Pas encore assez d'historique pour tracer une courbe honnête. {p.note}</p> : null;
  }
  const real = p.source === "réel";
  const kpis: [string, string, string][] = [
    ["Gain / an", pct(p.cagr), (p.cagr ?? 0) >= 0 ? "#22c55e" : "#f43f5e"],
    ["Gain / risque", String(p.sharpe), ""], ["Gain / baisses", String(p.sortino), ""],
    ["Pire baisse", pct(p.max_drawdown), "#f43f5e"],
    ["Trades gagnants", pct(p.win_rate), ""], ["Gains ÷ pertes", String(p.profit_factor), ""],
  ];
  const aide: Record<string, string> = {
    "Gain / an": "Gain moyen par an, une fois lissées les bonnes et les mauvaises années.",
    "Gain / risque": "Combien de gain pour chaque unité de secousses subies. Plus c'est haut, mieux c'est.",
    "Gain / baisses": "Même idée, mais ne compte que les baisses.",
    "Pire baisse": "La pire chute depuis un sommet.",
    "Trades gagnants": "Part des opérations qui ont fini dans le vert.",
    "Gains ÷ pertes": "Total gagné divisé par total perdu. Au-dessus de 1, on gagne plus qu'on ne perd.",
  };
  return (
    <>
      <div className="flex items-center gap-2 mt-3">
        <span className="text-muted text-[10px] uppercase tracking-wide">Résultats</span>
        <span className="text-[10px] px-1.5 py-0.5 rounded-full"
          style={{ background: `color-mix(in srgb, ${real ? "#22c55e" : "#f59e0b"} 18%, transparent)`,
                   color: real ? "#22c55e" : "#f59e0b" }}>
          {real ? "chiffres réels du compte" : "simulation — le compte n'est pas connecté"}
        </span>
      </div>
      <div className="grid grid-cols-3 gap-2 mt-2">
        {kpis.map(([k, v, c]) => (
          <div key={k} title={aide[k]}><div className="text-muted text-[10px] uppercase">{k}</div>
            <div className="mono text-sm" style={{ color: c || undefined }}>{v}</div></div>
        ))}
      </div>
      {p.curve?.length > 5 && <div className="mt-3">
        <EquityChart series={p.curve} height={150}
          title={real ? `Valeur réelle du compte — ${name}` : `Simulation — ${name}`} /></div>}
    </>
  );
}

function BrokerCard({ b, perf, accent, series, onPick }: any) {
  const ok = b?.ok, configured = b?.configured;
  const color = ok ? "#22c55e" : configured ? "#f43f5e" : "#9aa1ad";
  const pos = (b?.positions ?? []).map((p: any) => ({ ...p, val: (p.qty || 0) * (p.avg_price || 0) }));
  const tot = pos.reduce((a: number, p: any) => a + p.val, 0) || 1;
  const invested = pos.reduce((a: number, p: any) => a + p.val, 0);
  return (
    <div className="card p-4" style={{ borderColor: `color-mix(in srgb, ${color} 45%, transparent)` }}>
      <div className="flex items-center justify-between">
        <b style={{ color: accent }}>{b.name}</b>
        <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: "var(--surface3)", color }}>
          {ok ? "connecté ✓" : configured ? "erreur" : "pas encore configuré"}
        </span>
      </div>
      {ok ? (
        <>
          <div className="grid grid-cols-3 gap-2 mt-3">
            <div title="Tout ce que vaut le compte : les positions plus les liquidités."><div className="text-muted text-[10px] uppercase">Valeur du compte</div><div className="mono text-base">{eur(b.equity)} $</div></div>
            <div title="La part déjà placée sur des actifs (le reste dort en liquidités)."><div className="text-muted text-[10px] uppercase">Placé</div><div className="mono text-base">{eur(invested)} $</div></div>
            <div><div className="text-muted text-[10px] uppercase">Positions</div><div className="mono text-base">{pos.length}</div></div>
          </div>
          {pos.length > 0 && (
            <table className="text-sm mono mt-3 w-full">
              <thead className="text-muted text-xs"><tr><th className="text-left font-normal">Actif</th><th className="text-left font-normal">Sens</th>
                <th className="text-right font-normal">Quantité</th><th className="text-right font-normal" title="Prix moyen auquel vous avez acheté cette ligne.">Prix d'achat moyen</th><th className="text-right font-normal" title="Part de cette ligne dans tout ce qui est placé sur ce compte.">Part</th></tr></thead>
              <tbody>{pos.sort((x: any, y: any) => y.val - x.val).map((p: any, i: number) => (
                <tr key={i} onClick={() => onPick(p.symbol)}
                  className={`border-t border-border ${series?.[p.symbol] ? "cursor-pointer hover:bg-surfaceAlt" : ""}`}>
                  <td className="py-1"><span className={series?.[p.symbol] ? "text-accent border-b border-dotted border-border" : ""}>{p.symbol}</span></td>
                  <td style={{ color: p.side === "long" ? "#22c55e" : "#f43f5e" }}>{p.side}</td>
                  <td className="text-right">{p.qty}</td><td className="text-right">{p.avg_price}</td>
                  <td className="text-right text-muted">{((p.val / tot) * 100).toFixed(0)}%</td></tr>))}</tbody>
            </table>
          )}
          <Perf p={perf} name={b.name} />
        </>
      ) : (
        <p className="text-xs mt-2" style={{ color }}>
          {configured ? <>⚠️ Impossible de joindre le compte : <span className="mono">{b.error}</span></> : <>Ajoutez vos clés d'accès dans le fichier <code className="mono">.env</code>, puis relancez l'API.</>}
        </p>
      )}
    </div>
  );
}

export default function Live() {
  const { data: l } = useLive();
  const [sel, setSel] = useState<string | null>(null);
  if (!l) return <PageSkeleton />;
  const real = l.real ?? {}, series = l.series ?? {};
  const a = real.alpaca, b = real.crypto ?? real.bitmart;
  const vName = nomVenue(real);
  const pick = (s: string) => setSel(series[s] ? s : null);
  return (
    <main className="max-w-5xl mx-auto p-6 space-y-4">
      <h1 className="text-xl font-semibold tracking-tight">Mes comptes chez les courtiers</h1>
      <StepBanner active="live" />
      <p className="text-muted text-xs">Ce que contiennent <b>vraiment</b> vos comptes Alpaca et {vName}, lu directement chez eux. Chaque courtier a sa carte, avec ses chiffres et ses positions.</p>
      <div className="card p-3 text-xs" style={{ borderColor: "color-mix(in srgb, var(--accent) 35%, transparent)" }}>
        ℹ️ <b>Deux comptes séparés</b> : les actions et ETF sont chez <b>Alpaca</b>, les cryptos chez <b>{vName}</b>. Chacun a son propre argent, ils ne communiquent pas. On achète et on vend <b>comptant uniquement</b> : jamais d'argent emprunté, jamais de pari à la baisse. Quand un compte n'est pas connecté, les résultats affichés sont ceux d'une simulation, pas les vôtres.
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="card p-4" title="Les deux comptes additionnés : positions plus liquidités."><div className="text-muted text-xs uppercase">Total des deux comptes</div><div className="text-xl mono mt-1">{eur(real.equity)} $</div></div>
        <div className="card p-4"><div className="text-muted text-xs uppercase">Alpaca</div><div className="text-lg mono mt-1">{eur(a?.equity)} $</div></div>
        <div className="card p-4"><div className="text-muted text-xs uppercase">{vName}</div><div className="text-lg mono mt-1">{eur(b?.equity)} $</div></div>
        <div className="card p-4"><div className="text-muted text-xs uppercase">Lignes détenues</div><div className="text-lg mono mt-1">{(real.positions ?? []).length}</div></div>
      </div>

      {sel && series[sel] && (
        <section className="card p-4">
          <div className="flex justify-between items-center mb-2">
            <h2 className="text-sm uppercase tracking-wide text-muted">Graphique — {sel}</h2>
            <button onClick={() => setSel(null)} className="text-muted hover:text-fg text-sm">✕</button>
          </div>
          <TechnicalChart data={series[sel]} />
        </section>
      )}

      <section className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {a && <BrokerCard b={a} perf={l.alpaca_perf} accent="#3b82f6" series={series} onPick={pick} />}
        {b && <BrokerCard b={b} perf={l.crypto_perf ?? l.bitmart_perf} accent="#f59e0b" series={series} onPick={pick} />}
      </section>

      <section className="card p-4 text-sm">
        <h2 className="text-sm uppercase tracking-wide text-muted mb-2">Si quelque chose ne s'affiche pas</h2>
        <ul className="text-muted space-y-1 list-disc pl-5">
          <li><b>connecté ✓</b> = le site a bien lu votre compte. <b>erreur</b> = les clés sont là mais le courtier a refusé (droits insuffisants, adresse IP non autorisée, ou mauvais type de compte). <b>pas encore configuré</b> = aucune clé dans le fichier <code className="mono">.env</code>.</li>
          <li>« Aucune position » est normal tant qu'aucun ordre n'a été passé : <code className="mono">make live</code> montre ce qui serait acheté, sans rien acheter ; <code className="mono">python scripts/run_live.py --live --yes</code> passe réellement les ordres.</li>
        </ul>
      </section>
    </main>
  );
}
