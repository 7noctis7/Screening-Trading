"use client";
import { useState } from "react";
import { useLive } from "@/lib/api";
import { PageSkeleton } from "@/components/ui";
import { StepBanner } from "@/components/Pipeline";
import { EquityChart } from "@/components/EquityChart";
import { TechnicalChart } from "@/components/TechnicalChart";

const eur = (x?: number) => Math.round(x ?? 0).toLocaleString("fr-FR");
const pct = (x?: number) => `${((x ?? 0) * 100).toFixed(1)}%`;

function Perf({ p, accent }: { p: any; accent: string }) {
  if (!p?.available) return null;
  const kpis: [string, string, string][] = [
    ["CAGR", pct(p.cagr), (p.cagr ?? 0) >= 0 ? "#22c55e" : "#f43f5e"],
    ["Sharpe", String(p.sharpe), ""], ["Sortino", String(p.sortino), ""],
    ["Max DD", pct(p.max_drawdown), "#f43f5e"],
    ["Win rate", pct(p.win_rate), ""], ["Profit factor", String(p.profit_factor), ""],
  ];
  return (
    <>
      <div className="grid grid-cols-3 gap-2 mt-3">
        {kpis.map(([k, v, c]) => (
          <div key={k}><div className="text-muted text-[10px] uppercase">{k}</div>
            <div className="mono text-sm" style={{ color: c || undefined }}>{v}</div></div>
        ))}
      </div>
      {p.curve?.length > 5 && <div className="mt-3"><EquityChart series={p.curve} height={150} /></div>}
      <p className="text-muted2 text-[11px] mt-1">Backtest du sleeve (point-in-time). Style {accent ? "" : ""}.</p>
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
          {ok ? "connecté ✓" : configured ? "erreur" : "non configuré"}
        </span>
      </div>
      {ok ? (
        <>
          <div className="grid grid-cols-3 gap-2 mt-3">
            <div><div className="text-muted text-[10px] uppercase">Equity</div><div className="mono text-base">{eur(b.equity)} $</div></div>
            <div><div className="text-muted text-[10px] uppercase">Investi</div><div className="mono text-base">{eur(invested)} $</div></div>
            <div><div className="text-muted text-[10px] uppercase">Positions</div><div className="mono text-base">{pos.length}</div></div>
          </div>
          {pos.length > 0 && (
            <table className="text-sm mono mt-3 w-full">
              <thead className="text-muted text-xs"><tr><th className="text-left font-normal">Actif</th><th className="text-left font-normal">Sens</th>
                <th className="text-right font-normal">Qté</th><th className="text-right font-normal">PRU</th><th className="text-right font-normal">Poids</th></tr></thead>
              <tbody>{pos.sort((x: any, y: any) => y.val - x.val).map((p: any, i: number) => (
                <tr key={i} onClick={() => onPick(p.symbol)}
                  className={`border-t border-border ${series?.[p.symbol] ? "cursor-pointer hover:bg-surfaceAlt" : ""}`}>
                  <td className="py-1"><span className={series?.[p.symbol] ? "text-accent border-b border-dotted border-border" : ""}>{p.symbol}</span></td>
                  <td style={{ color: p.side === "long" ? "#22c55e" : "#f43f5e" }}>{p.side}</td>
                  <td className="text-right">{p.qty}</td><td className="text-right">{p.avg_price}</td>
                  <td className="text-right text-muted">{((p.val / tot) * 100).toFixed(0)}%</td></tr>))}</tbody>
            </table>
          )}
          <Perf p={perf} accent={accent} />
        </>
      ) : (
        <p className="text-xs mt-2" style={{ color }}>
          {configured ? <>⚠️ Connexion échouée : <span className="mono">{b.error}</span></> : <>Renseigne les clés dans <code className="mono">.env</code> puis relance l'API.</>}
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
  const a = real.alpaca, b = real.bitmart;
  const pick = (s: string) => setSel(series[s] ? s : null);
  return (
    <main className="max-w-5xl mx-auto p-6 space-y-4">
      <h1 className="text-xl font-semibold tracking-tight">Portefeuille réel</h1>
      <StepBanner active="live" />
      <p className="text-muted text-xs">Données <b>réelles</b> de tes comptes Alpaca / Bitmart. KPI, perf &amp; positions séparés par broker.</p>
      <div className="card p-3 text-xs" style={{ borderColor: "color-mix(in srgb, var(--accent) 35%, transparent)" }}>
        ℹ️ <b>Comptes distincts</b> : actions/ETF → <b>Alpaca</b> (capital Alpaca) · crypto → <b>Bitmart</b> (capital Bitmart). Trading <b>SPOT uniquement</b>. Les KPI de perf sont le backtest du sleeve de chaque compte.
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="card p-4"><div className="text-muted text-xs uppercase">Equity totale</div><div className="text-xl mono mt-1">{eur(real.equity)} $</div></div>
        <div className="card p-4"><div className="text-muted text-xs uppercase">Alpaca</div><div className="text-lg mono mt-1">{eur(a?.equity)} $</div></div>
        <div className="card p-4"><div className="text-muted text-xs uppercase">Bitmart</div><div className="text-lg mono mt-1">{eur(b?.equity)} $</div></div>
        <div className="card p-4"><div className="text-muted text-xs uppercase">Positions réelles</div><div className="text-lg mono mt-1">{(real.positions ?? []).length}</div></div>
      </div>

      {sel && series[sel] && (
        <section className="card p-4">
          <div className="flex justify-between items-center mb-2">
            <h2 className="text-sm uppercase tracking-wide text-muted">Graphique technique — {sel}</h2>
            <button onClick={() => setSel(null)} className="text-muted hover:text-fg text-sm">✕</button>
          </div>
          <TechnicalChart data={series[sel]} />
        </section>
      )}

      <section className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {a && <BrokerCard b={a} perf={l.alpaca_perf} accent="#3b82f6" series={series} onPick={pick} />}
        {b && <BrokerCard b={b} perf={l.bitmart_perf} accent="#f59e0b" series={series} onPick={pick} />}
      </section>

      <section className="card p-4 text-sm">
        <h2 className="text-sm uppercase tracking-wide text-muted mb-2">Diagnostic</h2>
        <ul className="text-muted space-y-1 list-disc pl-5">
          <li><b>connecté ✓</b> = l'API a lu ton compte. <b>erreur</b> = clés présentes mais appel échoué (permissions/IP/spot vs futures). <b>non configuré</b> = clés absentes du <code className="mono">.env</code>.</li>
          <li>« Aucune position » est normal avant le 1er ordre : <code className="mono">make live</code> (aperçu) puis <code className="mono">python scripts/run_live.py --live --yes</code>.</li>
        </ul>
      </section>
    </main>
  );
}
