"use client";
import { useState } from "react";
import { usePositions, useSentiment } from "@/lib/api";
import { TechnicalChart } from "@/components/TechnicalChart";
import { PageSkeleton } from "@/components/ui";

const eur = (x: number) => x.toLocaleString("fr-FR", { maximumFractionDigits: 0 });
const SC: Record<string, [string, string]> = {
  bullish: ["#22c55e", "▲"], bearish: ["#f43f5e", "▼"], neutral: ["#9aa1ad", "–"],
};

export default function Positions() {
  const { data } = usePositions();
  const { data: sent } = useSentiment();
  const [sel, setSel] = useState<string | null>(null);
  if (!data) return <PageSkeleton />;
  const sentBy: Record<string, number> = {};
  (sent?.rows ?? []).forEach((r: any) => (sentBy[r.symbol] = r.score));
  const rows = data.positions ?? [], t = data.totals ?? {}, k = data.portfolio ?? {}, series = data.series ?? {}, markers = data.markers ?? {};
  const bull = rows.filter((r: any) => r.stance === "bullish").length;
  const pos = (k.pnl_abs ?? 0) >= 0;
  return (
    <main className="max-w-5xl mx-auto p-6 space-y-4">
      <h1 className="text-xl font-semibold tracking-tight">Positions <span className="text-xs font-normal px-2 py-0.5 rounded-full align-middle" style={{ background: "color-mix(in srgb, var(--warn) 18%, transparent)", color: "var(--warn)" }}>FICTIF · démo 10 000 $</span></h1>
      <p className="text-muted text-xs">Portefeuille de démonstration (modèle). Pour tes positions réelles → onglet <b>Portefeuille réel</b>.</p>

      <section className="card p-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div><div className="text-muted text-xs uppercase">Valeur portefeuille</div><div className="text-xl mono">${eur(k.value ?? 0)}</div></div>
          <div><div className="text-muted text-xs uppercase">Gain / perte</div><div className="text-xl mono" style={{ color: pos ? "#22c55e" : "#f43f5e" }}>{pos ? "+" : ""}${eur(k.pnl_abs ?? 0)} ({((k.pnl_pct ?? 0) * 100).toFixed(1)}%)</div></div>
          <div><div className="text-muted text-xs uppercase">Investi / Cash</div><div className="text-xl mono">${eur(k.invested ?? 0)} / ${eur(k.cash ?? 0)}</div></div>
          <div><div className="text-muted text-xs uppercase">Exposition</div><div className="text-xl mono">{((k.exposure_pct ?? 0) * 100).toFixed(0)}% · {k.n_positions ?? rows.length} lignes</div></div>
        </div>
      </section>

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
        {rows.length === 0 ? <p className="text-muted text-sm">Aucune position ouverte.</p> : (
        <>
        <p className="text-muted text-xs mb-3">{bull}/{rows.length} positions dans des secteurs <span style={{ color: "#22c55e" }}>bullish</span> · clique un actif pour son graphique</p>
        <table className="w-full text-sm mono">
          <thead className="text-muted text-xs">
            <tr><th className="text-left font-normal">Actif</th><th className="text-left font-normal">Secteur / tendance</th>
            <th className="text-right font-normal">ML</th><th className="text-right font-normal">Sentiment</th>
            <th className="text-right font-normal">Qté</th><th className="text-right font-normal">PRU</th>
            <th className="text-right font-normal">Valeur</th><th className="text-right font-normal">P&amp;L</th></tr>
          </thead>
          <tbody>{rows.map((r: any) => (
            <tr key={r.symbol} className="border-t border-border hover:bg-surfaceAlt cursor-pointer" onClick={() => setSel(r.symbol)}>
              <td className="py-1.5"><span className="text-accent border-b border-dotted border-border">{r.symbol}</span></td>
              <td className="font-sans text-xs">
                <span style={{ color: (SC[r.stance] ?? SC.neutral)[0] }}>{(SC[r.stance] ?? SC.neutral)[1]}</span>{" "}
                <span className="text-muted">{r.sector}</span>
              </td>
              <td className="text-right">{r.ml_score == null ? "—" : `${(r.ml_score * 100).toFixed(0)}%`}</td>
              <td className="text-right">{sentBy[r.symbol] == null ? "—" :
                <span style={{ color: sentBy[r.symbol] > 0.05 ? "#22c55e" : sentBy[r.symbol] < -0.05 ? "#f43f5e" : "#9aa1ad" }}>
                  {sentBy[r.symbol] > 0.05 ? "▲" : sentBy[r.symbol] < -0.05 ? "▼" : "–"} {sentBy[r.symbol].toFixed(2)}</span>}</td>
              <td className="text-right">{typeof r.qty === "number" ? r.qty.toFixed(2) : r.qty}</td><td className="text-right">{r.avg_price}</td>
              <td className="text-right">{eur(r.current_value)}</td>
              <td className="text-right" style={{ color: r.pnl_abs >= 0 ? "#22c55e" : "#ef4444" }}>
                {eur(r.pnl_abs)} ({(r.pnl_pct * 100).toFixed(1)}%)</td>
            </tr>))}</tbody>
        </table>
        </>)}
      </section>
      <div className="card p-4 flex justify-between text-sm">
        <span className="text-muted">Exposition brute {eur(t.gross_exposure ?? 0)} · nette {eur(t.net_exposure ?? 0)}</span>
        <span className="mono" style={{ color: (t.pnl_abs ?? 0) >= 0 ? "#22c55e" : "#ef4444" }}>
          P&amp;L total {eur(t.pnl_abs ?? 0)}</span>
      </div>
    </main>
  );
}
