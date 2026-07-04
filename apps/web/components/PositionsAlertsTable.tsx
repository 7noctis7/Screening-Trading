"use client";
import Link from "next/link";
import { useMemo } from "react";

// Table compacte « dernières positions + alertes ». Positions RÉELLES (broker) triées par exposition ;
// P&L en couleur PLEINE --pos/--neg (c'est bien du P&L). Alertes = earnings_risk (résultats imminents,
// risque binaire). Liens vers les pages détail /positions et /trades. Aucune donnée inventée : si
// earnings_risk est vide (gate QUANT_EARNINGS), on l'indique sobrement.
const fmt = (x?: number, d = 2) => (x ?? 0).toLocaleString("fr-FR", { maximumFractionDigits: d });

export function PositionsAlertsTable({ positions, alerts, limit = 8 }:
  { positions: any[]; alerts?: { symbol: string; days: number }[]; limit?: number }) {
  const rows = useMemo(() =>
    [...(positions ?? [])].sort((a, b) => Math.abs(b.market_value ?? 0) - Math.abs(a.market_value ?? 0)).slice(0, limit),
  [positions, limit]);
  const al = alerts ?? [];
  if (!rows.length && !al.length) return null;

  return (
    <section className="card p-4 overflow-x-auto">
      <div className="flex items-center justify-between flex-wrap gap-2 mb-3">
        <h2 className="text-sm uppercase tracking-wide text-muted">Dernières positions &amp; alertes</h2>
        <div className="flex gap-3 text-xs">
          <Link href="/positions" className="text-accent2 hover:underline">toutes les positions →</Link>
          <Link href="/trades" className="text-accent2 hover:underline">journal des trades →</Link>
        </div>
      </div>

      {al.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-3">
          {al.slice(0, 12).map((a) => (
            <span key={a.symbol} className="badge-regime off" title="Résultats imminents — risque binaire">
              ⚠ {a.symbol} · résultats J−{a.days}
            </span>
          ))}
        </div>
      )}

      {rows.length > 0 ? (
        <table className="w-full text-sm mono dense">
          <thead className="text-muted text-xs"><tr>
            <th className="text-left font-normal">Position</th><th className="text-left font-normal">Broker</th>
            <th className="text-right font-normal">Qté</th><th className="text-right font-normal">Prix</th>
            <th className="text-right font-normal">Valeur</th><th className="text-right font-normal">P&L</th>
            <th className="text-right font-normal">%</th></tr></thead>
          <tbody>
            {rows.map((p, i) => (
              <tr key={`${p.symbol}-${i}`} className="border-t border-border">
                <td className="py-1"><Link href="/positions" className="hover:text-accent2">{p.symbol}</Link></td>
                <td className="font-sans text-xs text-muted">{p.broker}</td>
                <td className="text-right">{fmt(p.qty, 4)}</td>
                <td className="text-right">${fmt(p.price)}</td>
                <td className="text-right">${fmt(p.market_value, 0)}</td>
                <td className="text-right" style={{ color: p.pnl == null ? "var(--muted2)" : p.pnl >= 0 ? "var(--pos)" : "var(--neg)" }}>
                  {p.pnl == null ? "—" : `$${fmt(p.pnl)}`}</td>
                <td className="text-right" style={{ color: (p.pnl_pct ?? 0) >= 0 ? "var(--pos)" : "var(--neg)" }}>
                  {p.pnl_pct == null ? "—" : `${(p.pnl_pct * 100).toFixed(1)}%`}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="text-muted text-xs">Aucune position réelle ouverte.</p>
      )}
      {al.length === 0 && <p className="text-muted2 text-[11px] mt-2">Aucune alerte résultats (gate <code>QUANT_EARNINGS</code> désactivé ou aucune échéance &lt; 7 j).</p>}
    </section>
  );
}
