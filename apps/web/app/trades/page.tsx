"use client";
import { useState } from "react";
import { useTrades } from "@/lib/api";
import { TechnicalChart } from "@/components/TechnicalChart";
import { PageSkeleton } from "@/components/ui";

const eur = (x?: number) => Math.round(x ?? 0).toLocaleString("fr-FR");
const pct = (x: number) => `${(x * 100).toFixed(1)}%`;
const dt = (s?: string) => (s ? String(s).slice(0, 10) : "—");

export default function Trades() {
  const { data } = useTrades();
  const [sel, setSel] = useState<string | null>(null);
  if (!data) return <PageSkeleton />;
  const st = data.stats ?? {}, closed = data.trades ?? [], open = data.open_trades ?? [];
  const pt = data.preset_trades ?? {}, ptrades = pt.trades ?? [];
  const series = data.series ?? {}, markers = data.markers ?? {};
  const pick = (sym: string) => setSel(series[sym] ? sym : null);
  const cards: [string, string, string][] = [
    ["Rebalancements", String(pt.n_rebalances ?? 0), ""],
    ["Trades (preset)", String(ptrades.length), ""],
    ["Turnover annualisé", pt.turnover_annual != null ? `${pt.turnover_annual}×` : "—", ""],
    ["Pas de rebal.", "21 j", ""],
  ];
  return (
    <main className="max-w-5xl mx-auto p-6 space-y-4">
      <h1 className="text-xl font-semibold tracking-tight">Trades
        <span className="ml-2 text-xs font-normal px-2 py-0.5 rounded-full align-middle"
          style={{ background: "color-mix(in srgb, var(--accent) 16%, transparent)", color: "var(--accent2)" }}>PRESET · production</span></h1>
      <p className="text-muted text-xs">Rebalancements du <b>preset</b> (risk-parity + DD-target) : achats/ventes à chaque révision mensuelle, sur l'univers négociable. Turnover bas par construction (bande de non-trading).</p>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {cards.map(([lab, val, tone]) => (
          <div key={lab} className="card p-4">
            <div className="text-muted text-xs uppercase tracking-wide">{lab}</div>
            <div className="text-xl mono mt-1" style={{ color: tone === "pos" ? "#22c55e" : tone === "neg" ? "#ef4444" : undefined }}>{val}</div>
          </div>
        ))}
      </div>

      {st.cost_assumptions?.length > 0 && (
        <details className="card p-4">
          <summary className="text-sm uppercase tracking-wide text-muted cursor-pointer">Hypothèses de coûts par classe d'actifs (bps)</summary>
          <div className="overflow-x-auto mt-3">
            <table className="w-full text-sm">
              <thead className="text-muted text-xs"><tr>
                <th className="text-left font-normal">Classe</th><th className="text-right font-normal">Frais</th>
                <th className="text-right font-normal">Slippage</th><th className="text-right font-normal">Aller-retour</th></tr></thead>
              <tbody className="mono">{st.cost_assumptions.map((c: any) => (
                <tr key={c.asset_class} className="border-t border-border">
                  <td className="py-1.5 font-sans">{c.asset_class}</td>
                  <td className="text-right">{c.fee_bps}</td><td className="text-right">{c.slippage_bps}</td>
                  <td className="text-right"><b>{c.round_trip_bps}</b></td>
                </tr>))}</tbody>
            </table>
          </div>
        </details>
      )}

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
        <h2 className="text-sm uppercase tracking-wide text-muted mb-3">Journal des rebalancements du preset <span className="text-xs normal-case">· du plus récent au plus ancien</span></h2>
        {ptrades.length === 0 ? <p className="text-muted text-sm">Aucun rebalancement (échantillon insuffisant).</p> : (
          <table className="w-full text-sm mono">
            <thead className="text-muted text-xs">
              <tr><th className="text-left font-normal">Date</th><th className="text-left font-normal">Actif</th>
              <th className="text-left font-normal">Sens</th><th className="text-right font-normal">Poids avant→après</th>
              <th className="text-right font-normal">Notionnel</th><th className="text-left font-normal pl-4">Motif</th></tr>
            </thead>
            <tbody>{ptrades.map((t: any, i: number) => (
              <tr key={i} onClick={() => pick(t.symbol)}
                className={`border-t border-border ${series[t.symbol] ? "cursor-pointer hover:bg-surfaceAlt" : ""}`}>
                <td className="py-1.5 text-muted">{dt(t.date)}</td>
                <td><span className={series[t.symbol] ? "text-accent border-b border-dotted border-border" : ""}>{t.symbol}</span></td>
                <td style={{ color: t.side === "BUY" ? "#22c55e" : "#f43f5e" }}>{t.side === "BUY" ? "▲ achat" : "▼ vente"}</td>
                <td className="text-right text-muted">{(t.from * 100).toFixed(1)}% → {(t.to * 100).toFixed(1)}%</td>
                <td className="text-right">${eur(t.notional)}</td>
                <td className="pl-4 text-muted font-sans text-xs">{t.reason || "—"}</td>
              </tr>))}</tbody>
          </table>
        )}
      </section>

      <details className="card p-4">
        <summary className="text-sm uppercase tracking-wide text-muted cursor-pointer">
          🗃 Ancienne stratégie swing (référence — remplacée par le preset)</summary>
        <p className="text-muted2 text-xs mt-2 mb-3">Conservée pour transparence. Ses perfs faibles (réussite {((st.win_rate ?? 0) * 100).toFixed(0)}%, P&amp;L {eur(st.pnl_total ?? 0)} €) sont la raison du passage au preset.</p>
        <div className="overflow-x-auto">
          <table className="w-full text-sm mono">
            <thead className="text-muted text-xs"><tr>
              <th className="text-left font-normal">Actif</th><th className="text-left font-normal">Entrée</th>
              <th className="text-left font-normal">Sortie</th><th className="text-right font-normal">P&amp;L</th>
              <th className="text-right font-normal">%</th><th className="text-left font-normal pl-3">Motif entrée</th>
              <th className="text-left font-normal pl-3">Motif sortie</th></tr></thead>
            <tbody>{closed.slice(0, 80).map((t: any) => {
              const win = (t.pnl_net ?? 0) >= 0;
              return (
                <tr key={t.id} className="border-t border-border">
                  <td className="py-1.5">{t.instrument}</td><td className="text-muted">{dt(t.entry_ts)}</td>
                  <td className="text-muted">{dt(t.exit_ts)}</td>
                  <td className="text-right" style={{ color: win ? "#22c55e" : "#ef4444" }}>{eur(t.pnl_net ?? 0)}</td>
                  <td className="text-right" style={{ color: win ? "#22c55e" : "#ef4444" }}>{pct(t.pnl_pct ?? 0)}</td>
                  <td className="pl-3 text-muted font-sans text-xs">{t.entry_reason || "—"}</td>
                  <td className="pl-3 text-muted font-sans text-xs">{t.exit_reason || "—"}</td>
                </tr>);
            })}</tbody>
          </table>
        </div>
      </details>
    </main>
  );
}
