"use client";
import { StepBanner } from "@/components/Pipeline";
import { useState } from "react";
import { usePositions } from "@/lib/api";
import { TechnicalChart } from "@/components/TechnicalChart";
import { PageSkeleton } from "@/components/ui";

const usd = (x?: number) => (x ?? 0).toLocaleString("fr-FR", { maximumFractionDigits: 2 });

export default function Positions() {
  const { data } = usePositions();
  const [sel, setSel] = useState<string | null>(null);
  if (!data) return <PageSkeleton />;
  const pos = data.real_positions ?? [];
  const series = data.series ?? {}, markers = data.markers ?? {};
  const acc = data.accounts ?? {};
  const aEq = acc.alpaca?.equity ?? 0, bEq = acc.bitmart?.equity ?? 0;
  const mv = pos.reduce((a: number, r: any) => a + (r.market_value ?? 0), 0);
  const pnl = pos.reduce((a: number, r: any) => a + (r.pnl ?? 0), 0);
  const pick = (s: string) => setSel(series[s] ? s : null);
  return (
    <main className="max-w-5xl mx-auto p-6 space-y-4">
      <h1 className="text-xl font-semibold tracking-tight">Positions
        <span className="ml-2 text-xs font-normal px-2 py-0.5 rounded-full align-middle"
          style={{ background: "color-mix(in srgb, #22c55e 16%, transparent)", color: "#22c55e" }}>RÉEL · Alpaca + Bitmart</span></h1>
      <p className="text-muted text-xs">Positions <b>réellement détenues</b> sur tes comptes Alpaca (actions/ETF) et Bitmart (crypto spot). Aucune donnée modèle ou synthétique. Cible & backtest : voir Dashboard.</p>
      <StepBanner active="portfolio" />

      {!data.connected ? (
        <section className="card p-6 text-center">
          <p className="text-sm">Aucun compte connecté.</p>
          <p className="text-muted text-xs mt-1">Renseigne <code>ALPACA_API_KEY</code>/<code>ALPACA_API_SECRET</code> et/ou <code>BITMART_API_KEY</code>/<code>BITMART_API_SECRET</code> dans <code>.env</code>, puis relance l'API.</p>
          {(acc.alpaca?.error || acc.bitmart?.error) && (
            <p className="text-muted2 text-[11px] mt-2">Alpaca : {acc.alpaca?.error || "ok"} · Bitmart : {acc.bitmart?.error || "ok"}</p>)}
        </section>
      ) : (
      <>
      <section className="card p-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div><div className="text-muted text-xs uppercase">Capital réel</div>
            <div className="text-xl mono">${usd(aEq + bEq)}</div>
            <div className="text-muted2 text-[11px] mono">Alpaca ${usd(aEq)} · Bitmart ${usd(bEq)}</div></div>
          <div><div className="text-muted text-xs uppercase">Valeur positions</div><div className="text-xl mono">${usd(mv)}</div></div>
          <div><div className="text-muted text-xs uppercase">P&L latent</div>
            <div className="text-xl mono" style={{ color: pnl >= 0 ? "#22c55e" : "#ef4444" }}>${usd(pnl)}</div></div>
          <div><div className="text-muted text-xs uppercase">Lignes</div><div className="text-xl mono">{pos.length}</div></div>
        </div>
      </section>

      {sel && series[sel] && (
        <section className="card p-4">
          <div className="flex justify-between items-center mb-2">
            <h2 className="text-sm uppercase tracking-wide text-muted">Graphique technique — {sel}</h2>
            <button onClick={() => setSel(null)} className="text-muted hover:text-fg text-sm">✕</button>
          </div>
          <TechnicalChart data={series[sel]} markers={markers[sel] ?? []} />
        </section>
      )}

      <section className="card p-4 overflow-x-auto">
        {pos.length === 0 ? <p className="text-muted text-sm">Aucune position ouverte sur tes comptes. Passe des ordres en paper : <code>make live-go</code>.</p> : (
        <>
        <p className="text-muted text-xs mb-3">Clique un actif pour son graphique + signaux d'achat/vente réels.</p>
        <table className="w-full text-sm mono">
          <thead className="text-muted text-xs">
            <tr><th className="text-left font-normal">Actif</th><th className="text-left font-normal">Broker</th>
            <th className="text-right font-normal">Qté</th><th className="text-right font-normal">Prix moyen</th>
            <th className="text-right font-normal">Prix actuel</th><th className="text-right font-normal">Valeur</th>
            <th className="text-right font-normal">P&L</th><th className="text-right font-normal">P&L %</th></tr>
          </thead>
          <tbody>{pos.map((r: any) => (
            <tr key={`${r.broker}-${r.symbol}`} className={`border-t border-border ${series[r.symbol] ? "cursor-pointer hover:bg-surfaceAlt" : ""}`} onClick={() => pick(r.symbol)}>
              <td className="py-1.5"><span className={series[r.symbol] ? "text-accent border-b border-dotted border-border" : ""}>{r.symbol}</span></td>
              <td className="font-sans text-xs">{r.broker}</td>
              <td className="text-right">{(r.qty ?? 0).toFixed(4)}</td>
              <td className="text-right">${usd(r.avg_price)}</td>
              <td className="text-right">${usd(r.price)}</td>
              <td className="text-right">${usd(r.market_value)}</td>
              <td className="text-right" style={{ color: (r.pnl ?? 0) >= 0 ? "#22c55e" : "#ef4444" }}>${usd(r.pnl)}</td>
              <td className="text-right" style={{ color: (r.pnl_pct ?? 0) >= 0 ? "#22c55e" : "#ef4444" }}>{((r.pnl_pct ?? 0) * 100).toFixed(1)}%</td>
            </tr>))}</tbody>
        </table>
        </>)}
      </section>
      </>)}
    </main>
  );
}
