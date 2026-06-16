"use client";
import { useTrades } from "@/lib/api";

const eur = (x: number) => Math.round(x).toLocaleString("fr-FR");
const pct = (x: number) => `${(x * 100).toFixed(1)}%`;
const dt = (s?: string) => (s ? String(s).slice(0, 10) : "—");

export default function Trades() {
  const { data } = useTrades();
  if (!data) return <div className="p-8 text-muted">Chargement…</div>;
  const st = data.stats ?? {}, closed = data.trades ?? [], open = data.open_trades ?? [];
  const cards: [string, string, string][] = [
    ["Trades clôturés", String(st.count ?? 0), ""],
    ["Taux de réussite", `${((st.win_rate ?? 0) * 100).toFixed(0)}%`, ""],
    ["P&L cumulé", `${eur(st.pnl_total ?? 0)} €`, (st.pnl_total ?? 0) >= 0 ? "pos" : "neg"],
    ["Profit factor", String(st.profit_factor ?? "—"), ""],
    ["Meilleur", `${eur(st.best ?? 0)} €`, "pos"],
    ["Pire", `${eur(st.worst ?? 0)} €`, "neg"],
  ];
  return (
    <main className="max-w-5xl mx-auto p-6 space-y-4">
      <h1 className="text-xl font-semibold tracking-tight">Trades</h1>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {cards.map(([lab, val, tone]) => (
          <div key={lab} className="card p-4">
            <div className="text-muted text-xs uppercase tracking-wide">{lab}</div>
            <div className="text-xl mono mt-1" style={{ color: tone === "pos" ? "#22c55e" : tone === "neg" ? "#ef4444" : undefined }}>{val}</div>
          </div>
        ))}
      </div>

      <section className="card p-4 overflow-x-auto">
        <h2 className="text-sm uppercase tracking-wide text-muted mb-3">Trades en cours</h2>
        {open.length === 0 ? <p className="text-muted text-sm">Aucun trade ouvert au dernier pas (stratégie à plat).</p> : (
          <table className="w-full text-sm mono">
            <thead className="text-muted text-xs">
              <tr><th className="text-left font-normal">Actif</th><th className="text-left font-normal">Sens</th>
              <th className="text-right font-normal">Qté</th><th className="text-right font-normal">PRU</th>
              <th className="text-right font-normal">Valeur</th><th className="text-right font-normal">P&amp;L latent</th></tr>
            </thead>
            <tbody>{open.map((r: any) => (
              <tr key={r.symbol} className="border-t border-border">
                <td className="py-1.5">{r.symbol}</td><td>{r.side}</td>
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
              <th className="text-left font-normal pl-4">Motif sortie</th></tr>
            </thead>
            <tbody>{closed.map((t: any) => {
              const win = (t.pnl_net ?? 0) >= 0;
              return (
                <tr key={t.id} className="border-t border-border">
                  <td className="py-1.5">{t.instrument}</td><td>{t.side}</td>
                  <td className="text-muted">{dt(t.entry_ts)}</td><td className="text-muted">{dt(t.exit_ts)}</td>
                  <td className="text-right" style={{ color: win ? "#22c55e" : "#ef4444" }}>{eur(t.pnl_net ?? 0)}</td>
                  <td className="text-right" style={{ color: win ? "#22c55e" : "#ef4444" }}>{pct(t.pnl_pct ?? 0)}</td>
                  <td className="pl-4 text-muted font-sans">{t.exit_reason}</td>
                </tr>);
            })}</tbody>
          </table>
        )}
      </section>
    </main>
  );
}
