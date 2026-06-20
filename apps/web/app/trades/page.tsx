"use client";
import { useState } from "react";
import { useTrades, useOverlays } from "@/lib/api";
import { TechnicalChart } from "@/components/TechnicalChart";
import { PageSkeleton } from "@/components/ui";

const usd = (x?: number) => (x ?? 0).toLocaleString("fr-FR", { maximumFractionDigits: 2 });
const dt = (s?: string) => (s ? String(s).slice(0, 10) : "—");

export default function Trades() {
  const { data } = useTrades();
  const [sel, setSel] = useState<string | null>(null);
  const { data: ov } = useOverlays(sel);                 // overlays MCP TradingView du symbole sélectionné
  if (!data) return <PageSkeleton />;
  const trades = data.real_trades ?? [];
  const openOrders = data.real_open_orders ?? [];
  const series = data.series ?? {}, markers = data.markers ?? {};
  const acc = data.accounts ?? {};
  const pick = (s: string) => setSel(series[s] ? s : null);
  return (
    <main className="max-w-5xl mx-auto p-6 space-y-4">
      <h1 className="text-xl font-semibold tracking-tight">Trades
        <span className="ml-2 text-xs font-normal px-2 py-0.5 rounded-full align-middle"
          style={{ background: "color-mix(in srgb, #22c55e 16%, transparent)", color: "#22c55e" }}>RÉEL · Alpaca + Bitmart</span></h1>
      <p className="text-muted text-xs">Ordres <b>réellement exécutés</b> (fills) <b>et ordres en attente</b> (non encore exécutés, ex. marché fermé) sur tes comptes. Aucune donnée modèle, backtest ou synthétique.</p>

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
          <TechnicalChart data={series[sel]} markers={markers[sel] ?? []}
            overlays={ov ? { bands: ov.bands, blackouts: ov.blackouts } : undefined} />
        </section>
      )}

      {openOrders.length > 0 && (
      <section className="card p-4 overflow-x-auto" style={{ borderColor: "color-mix(in srgb, #f59e0b 40%, transparent)" }}>
        <h2 className="text-sm uppercase tracking-wide mb-1" style={{ color: "#f59e0b" }}>⏳ Ordres en attente d'exécution ({openOrders.length})</h2>
        <p className="text-muted2 text-xs mb-3">Ordres soumis mais <b>non encore remplis</b> (marché fermé, ordre limite non atteint, etc.). Ils ne sont pas dans la courbe de perf tant qu'ils ne sont pas exécutés.</p>
        <table className="w-full text-sm mono">
          <thead className="text-muted text-xs">
            <tr><th className="text-left font-normal">Soumis le</th><th className="text-left font-normal">Actif</th>
            <th className="text-left font-normal">Broker</th><th className="text-left font-normal">Sens</th>
            <th className="text-right font-normal">Qté</th><th className="text-right font-normal">Rempli</th>
            <th className="text-right font-normal">Prix</th><th className="text-left font-normal pl-2">Type</th>
            <th className="text-right font-normal">Montant</th><th className="text-left font-normal pl-3">Statut</th></tr>
          </thead>
          <tbody>{openOrders.map((t: any, i: number) => (
            <tr key={i} className={`border-t border-border ${series[t.symbol] ? "cursor-pointer hover:bg-surfaceAlt" : ""}`} onClick={() => pick(t.symbol)}>
              <td className="py-1.5 text-muted">{dt(t.date)}</td>
              <td><span className={series[t.symbol] ? "text-accent border-b border-dotted border-border" : ""}>{t.symbol}</span></td>
              <td className="font-sans text-xs">{t.broker}</td>
              <td style={{ color: t.side === "buy" ? "#22c55e" : "#f43f5e" }}>{t.side === "buy" ? "▲ achat" : "▼ vente"}</td>
              <td className="text-right">{t.notional_order ? <span className="text-muted2">en $</span> : (t.qty ?? 0).toFixed(4)}</td>
              <td className="text-right text-muted2">{(t.filled_qty ?? 0).toFixed(4)}</td>
              <td className="text-right">{t.price ? `$${usd(t.price)}` : "marché"}</td>
              <td className="pl-2 font-sans text-xs text-muted2">{t.order_type || "—"}</td>
              <td className="text-right">{t.notional ? `$${usd(t.notional)}` : "—"}</td>
              <td className="pl-3 font-sans text-xs"><span className="px-1.5 py-0.5 rounded-full" style={{ background: "color-mix(in srgb, #f59e0b 16%, transparent)", color: "#f59e0b" }}>{t.status || "en attente"}</span></td>
            </tr>))}</tbody>
        </table>
      </section>
      )}

      <section className="card p-4 overflow-x-auto">
        {trades.length === 0 ? <p className="text-muted text-sm">Aucun ordre exécuté pour l'instant. Passe des ordres en paper : <code>make live-go</code>.</p> : (
        <>
        <h2 className="text-sm uppercase tracking-wide mb-1" style={{ color: "#22c55e" }}>✓ Ordres exécutés ({trades.length})</h2>
        <p className="text-muted text-xs mb-3">Fills réels · clique un actif pour son graphique + signaux.</p>
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
