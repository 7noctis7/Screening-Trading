"use client";
import { useState } from "react";
import { useTrades } from "@/lib/api";
import { TechnicalChart } from "@/components/TechnicalChart";
import { PageSkeleton } from "@/components/ui";

const usd = (x?: number) => (x ?? 0).toLocaleString("fr-FR", { maximumFractionDigits: 2 });
const dt = (s?: string) => (s ? String(s).slice(0, 10) : "—");

export default function Trades() {
  const { data } = useTrades();
  const [sel, setSel] = useState<string | null>(null);
  if (!data) return <PageSkeleton />;
  const trades = data.real_trades ?? [];
  const series = data.series ?? {}, markers = data.markers ?? {};
  const acc = data.accounts ?? {};
  const pick = (s: string) => setSel(series[s] ? s : null);
  return (
    <main className="max-w-5xl mx-auto p-6 space-y-4">
      <h1 className="text-xl font-semibold tracking-tight">Trades
        <span className="ml-2 text-xs font-normal px-2 py-0.5 rounded-full align-middle"
          style={{ background: "color-mix(in srgb, #22c55e 16%, transparent)", color: "#22c55e" }}>RÉEL · Alpaca + Bitmart</span></h1>
      <p className="text-muted text-xs">Ordres <b>réellement exécutés</b> sur tes comptes (fills). Aucune donnée modèle, backtest ou synthétique.</p>

      {!data.connected ? (
        <section className="card p-6 text-center">
          <p className="text-sm">Aucun compte connecté.</p>
          <p className="text-muted text-xs mt-1">Renseigne tes clés API dans <code>.env</code> puis relance l'API.</p>
          {(acc.alpaca?.error || acc.bitmart?.error) && (
            <p className="text-muted2 text-[11px] mt-2">Alpaca : {acc.alpaca?.error || "ok"} · Bitmart : {acc.bitmart?.error || "ok"}</p>)}
        </section>
      ) : (
      <>
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
        {trades.length === 0 ? <p className="text-muted text-sm">Aucun ordre exécuté pour l'instant. Passe des ordres en paper : <code>make live-go</code>.</p> : (
        <>
        <p className="text-muted text-xs mb-3">{trades.length} ordres exécutés · clique un actif pour son graphique + signaux.</p>
        <table className="w-full text-sm mono">
          <thead className="text-muted text-xs">
            <tr><th className="text-left font-normal">Date</th><th className="text-left font-normal">Actif</th>
            <th className="text-left font-normal">Broker</th><th className="text-left font-normal">Sens</th>
            <th className="text-right font-normal">Qté</th><th className="text-right font-normal">Prix</th>
            <th className="text-right font-normal">Montant</th><th className="text-left font-normal pl-3">Statut</th></tr>
          </thead>
          <tbody>{trades.map((t: any, i: number) => (
            <tr key={i} className={`border-t border-border ${series[t.symbol] ? "cursor-pointer hover:bg-surfaceAlt" : ""}`} onClick={() => pick(t.symbol)}>
              <td className="py-1.5 text-muted">{dt(t.date)}</td>
              <td><span className={series[t.symbol] ? "text-accent border-b border-dotted border-border" : ""}>{t.symbol}</span></td>
              <td className="font-sans text-xs">{t.broker}</td>
              <td style={{ color: t.side === "buy" ? "#22c55e" : "#f43f5e" }}>{t.side === "buy" ? "▲ achat" : "▼ vente"}</td>
              <td className="text-right">{(t.qty ?? 0).toFixed(4)}</td>
              <td className="text-right">${usd(t.price)}</td>
              <td className="text-right">${usd(t.notional)}</td>
              <td className="pl-3 text-muted font-sans text-xs">{t.status || "filled"}</td>
            </tr>))}</tbody>
        </table>
        </>)}
      </section>
      </>)}
    </main>
  );
}
