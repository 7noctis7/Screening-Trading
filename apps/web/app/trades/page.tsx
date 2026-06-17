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
  const turn = st.turnover ?? {};
  const series = data.series ?? {}, markers = data.markers ?? {};
  const pick = (sym: string) => setSel(series[sym] ? sym : null);
  const cards: [string, string, string][] = [
    ["Trades clôturés", String(st.count ?? 0), ""],
    ["Taux de réussite", `${((st.win_rate ?? 0) * 100).toFixed(0)}%`, ""],
    ["P&L cumulé", `${eur(st.pnl_total ?? 0)} €`, (st.pnl_total ?? 0) >= 0 ? "pos" : "neg"],
    ["Profit factor", String(st.profit_factor ?? "—"), ""],
    ["Meilleur", `${eur(st.best ?? 0)} €`, "pos"],
    ["Turnover annualisé", turn.annualized != null ? `${turn.annualized.toFixed(2)}×` : "—", ""],
  ];
  return (
    <main className="max-w-5xl mx-auto p-6 space-y-4">
      <h1 className="text-xl font-semibold tracking-tight">Trades <span className="text-xs font-normal px-2 py-0.5 rounded-full align-middle" style={{ background: "color-mix(in srgb, var(--warn) 18%, transparent)", color: "var(--warn)" }}>FICTIF · démo</span></h1>
      <p className="text-muted text-xs">Journal du portefeuille de démonstration (backtest). Tes ordres réels passent par l'onglet <b>Portefeuille réel</b>.</p>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {cards.map(([lab, val, tone]) => (
          <div key={lab} className="card p-4">
            <div className="text-muted text-xs uppercase tracking-wide">{lab}</div>
            <div className="text-xl mono mt-1" style={{ color: tone === "pos" ? "#22c55e" : tone === "neg" ? "#ef4444" : undefined }}>{val}</div>
          </div>
        ))}
      </div>

      {sel && series[sel] && (
        <section className="card p-4">
          <div className="flex justify-between items-center mb-2">
            <h2 className="text-sm uppercase tracking-wide text-muted">Graphique technique — {sel}
              <span className="ml-2 text-xs"><span style={{ color: "#22c55e" }}>▲ achat</span> <span style={{ color: "#f43f5e" }}>▼ vente</span></span></h2>
            <button onClick={() => setSel(null)} className="text-muted hover:text-fg text-sm">✕</button>
          </div>
          <TechnicalChart data={series[sel]} markers={markers[sel] ?? []} />
        </section>
      )}

      <section className="card p-4 overflow-x-auto">
        <h2 className="text-sm uppercase tracking-wide text-muted mb-3">Trades en cours <span className="text-xs normal-case">· clique un actif pour son graphique</span></h2>
        {open.length === 0 ? <p className="text-muted text-sm">Aucun trade ouvert au dernier pas (stratégie à plat).</p> : (
          <table className="w-full text-sm mono">
            <thead className="text-muted text-xs">
              <tr><th className="text-left font-normal">Actif</th><th className="text-left font-normal">Sens</th>
              <th className="text-right font-normal">Qté</th><th className="text-right font-normal">PRU</th>
              <th className="text-right font-normal">Valeur</th><th className="text-right font-normal">P&amp;L latent</th></tr>
            </thead>
            <tbody>{open.map((r: any) => (
              <tr key={r.symbol} onClick={() => pick(r.symbol)}
                className={`border-t border-border ${series[r.symbol] ? "cursor-pointer hover:bg-surfaceAlt" : ""}`}>
                <td className="py-1.5"><span className={series[r.symbol] ? "text-accent border-b border-dotted border-border" : ""}>{r.symbol}</span></td><td>{r.side}</td>
                <td className="text-right">{r.qty}</td><td className="text-right">{r.avg_price}</td>
                <td className="text-right">{eur(r.current_value)}</td>
                <td className="text-right" style={{ color: r.pnl_abs >= 0 ? "#22c55e" : "#ef4444" }}>{eur(r.pnl_abs)} ({pct(r.pnl_pct)})</td>
              </tr>))}</tbody>
          </table>
        )}
      </section>

      <section className="card p-4 overflow-x-auto">
        <h2 className="text-sm uppercase tracking-wide text-muted mb-3">Historique des trades passés</h2>
        {closed.length === 0 ? <p className="text-muted text-sm">Aucun trade dans le journal.</p> : (
          <table className="w-full text-sm mono">
            <thead className="text-muted text-xs">
              <tr><th className="text-left font-normal">Actif</th><th className="text-left font-normal">Sens</th>
              <th className="text-left font-normal">Entrée</th><th className="text-left font-normal">Sortie</th>
              <th className="text-right font-normal">P&amp;L</th><th className="text-right font-normal">%</th>
              <th className="text-left font-normal pl-4">Motif entrée</th><th className="text-left font-normal pl-4">Motif sortie</th></tr>
            </thead>
            <tbody>{closed.map((t: any) => {
              const win = (t.pnl_net ?? 0) >= 0;
              return (
                <tr key={t.id} onClick={() => pick(t.instrument)}
                  className={`border-t border-border ${series[t.instrument] ? "cursor-pointer hover:bg-surfaceAlt" : ""}`}>
                  <td className="py-1.5"><span className={series[t.instrument] ? "text-accent border-b border-dotted border-border" : ""}>{t.instrument}</span></td><td>{t.side}</td>
                  <td className="text-muted">{dt(t.entry_ts)}</td><td className="text-muted">{dt(t.exit_ts)}</td>
                  <td className="text-right" style={{ color: win ? "#22c55e" : "#ef4444" }}>{eur(t.pnl_net ?? 0)}</td>
                  <td className="text-right" style={{ color: win ? "#22c55e" : "#ef4444" }}>{pct(t.pnl_pct ?? 0)}</td>
                  <td className="pl-4 text-muted font-sans">{t.entry_reason || "—"}</td>
                  <td className="pl-4 text-muted font-sans">{t.exit_reason}</td>
                </tr>);
            })}</tbody>
          </table>
        )}
      </section>
    </main>
  );
}
