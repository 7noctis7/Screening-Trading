"use client";
import { usePositions } from "@/lib/api";

const eur = (x: number) => x.toLocaleString("fr-FR", { maximumFractionDigits: 0 });

export default function Positions() {
  const { data } = usePositions();
  if (!data) return <div className="p-8 text-muted">Chargement…</div>;
  const rows = data.positions ?? [], t = data.totals ?? {};
  return (
    <main className="max-w-5xl mx-auto p-6 space-y-4">
      <h1 className="text-xl font-semibold tracking-tight">Positions</h1>
      <section className="card p-4 overflow-x-auto">
        {rows.length === 0 ? <p className="text-muted text-sm">Aucune position ouverte.</p> : (
        <table className="w-full text-sm mono">
          <thead className="text-muted text-xs">
            <tr><th className="text-left font-normal">Actif</th><th className="text-left font-normal">Sens</th>
            <th className="text-right font-normal">Qté</th><th className="text-right font-normal">PRU</th>
            <th className="text-right font-normal">Valeur</th><th className="text-right font-normal">P&amp;L</th></tr>
          </thead>
          <tbody>{rows.map((r: any) => (
            <tr key={r.symbol} className="border-t border-border">
              <td className="py-1.5">{r.symbol}</td><td>{r.side}</td>
              <td className="text-right">{r.qty}</td><td className="text-right">{r.avg_price}</td>
              <td className="text-right">{eur(r.current_value)}</td>
              <td className="text-right" style={{ color: r.pnl_abs >= 0 ? "#22c55e" : "#ef4444" }}>
                {eur(r.pnl_abs)} ({(r.pnl_pct * 100).toFixed(1)}%)</td>
            </tr>))}</tbody>
        </table>)}
      </section>
      <div className="card p-4 flex justify-between text-sm">
        <span className="text-muted">Exposition brute {eur(t.gross_exposure ?? 0)} · nette {eur(t.net_exposure ?? 0)}</span>
        <span className="mono" style={{ color: (t.pnl_abs ?? 0) >= 0 ? "#22c55e" : "#ef4444" }}>
          P&amp;L total {eur(t.pnl_abs ?? 0)}</span>
      </div>
    </main>
  );
}
