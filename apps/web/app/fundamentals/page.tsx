"use client";
import { useState } from "react";
import { useFundamentals } from "@/lib/api";
import { PageSkeleton, EmptyState } from "@/components/ui";
import { downloadCsv } from "@/lib/csv";

const RC: Record<string, string> = { BUY: "#22c55e", HOLD: "#9aa1ad", SELL: "#f43f5e" };
const pct = (x?: number) => (x == null ? "—" : `${(x * 100).toFixed(0)}%`);

export default function Fundamentals() {
  const { data: f } = useFundamentals();
  const [q, setQ] = useState("");
  if (!f) return <PageSkeleton />;
  if (!f.available)
    return <main className="max-w-3xl mx-auto p-6"><EmptyState title="Aucun fondamental disponible" hint="Actifs sans données fondamentales (crypto/forex)." /></main>;
  const rows = (f.rows ?? []).filter((r: any) =>
    !q || r.symbol.toLowerCase().includes(q.toLowerCase()) || (r.name ?? "").toLowerCase().includes(q.toLowerCase()));
  return (
    <main className="max-w-5xl mx-auto p-6 space-y-4">
      <h1 className="text-xl font-semibold tracking-tight">Analyse fondamentale</h1>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="card p-4"><div className="text-muted text-xs uppercase">Source</div><div className="text-lg mt-1">{f.source}</div></div>
        <div className="card p-4"><div className="text-muted text-xs uppercase">Titres analysés</div><div className="text-lg mono mt-1">{f.n}</div></div>
        <div className="card p-4"><div className="text-muted text-xs uppercase">Signaux BUY</div><div className="text-lg mono mt-1" style={{ color: "#22c55e" }}>{f.buys}</div></div>
        <div className="card p-4 flex items-center"><input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filtrer un titre…"
          className="w-full bg-transparent text-sm outline-none border border-border rounded-lg px-3 py-2" /></div>
      </div>
      <div className="flex items-center justify-between">
        <p className="text-muted text-xs">{f.method}</p>
        <button onClick={() => downloadCsv("fondamentaux", ["Actif", "Secteur", "PER", "EV/EBITDA", "P/B", "ROE", "FCF yield", "Marge securite", "F-score", "Altman Z", "Tech", "Fond+Tech", "Reco"],
          rows.map((r: any) => [r.symbol, r.sector, r.per, r.ev_ebitda, r.pb, r.roe, r.fcf_yield, r.margin_of_safety, r.f_score, r.altman_z, r.tech_score, r.combined_score, r.rating]))}
          className="text-xs px-3 py-1.5 rounded-lg border border-border text-muted hover:text-fg hover:bg-surfaceAlt whitespace-nowrap">⬇ Export CSV</button>
      </div>
      <section className="card p-4 overflow-x-auto">
        <table className="w-full text-sm mono">
          <thead className="text-muted text-xs">
            <tr><th className="text-left font-normal">Actif</th><th className="text-left font-normal">Secteur</th>
            <th className="text-right font-normal">PER</th><th className="text-right font-normal">EV/EBITDA</th>
            <th className="text-right font-normal">P/B</th><th className="text-right font-normal">ROE</th>
            <th className="text-right font-normal">Marge brute</th><th className="text-right font-normal">FCF yield</th>
            <th className="text-right font-normal">Marge sécu.</th><th className="text-right font-normal">F-score</th>
            <th className="text-right font-normal">Altman Z</th><th className="text-right font-normal">Tech</th>
            <th className="text-right font-normal">Fond.+Tech</th><th className="text-right font-normal">Reco</th></tr>
          </thead>
          <tbody>{rows.map((r: any) => (
            <tr key={r.symbol} className="border-t border-border">
              <td className="py-1.5">{r.symbol}</td><td className="text-muted font-sans text-xs">{r.sector}</td>
              <td className="text-right">{r.per}</td><td className="text-right">{r.ev_ebitda}</td>
              <td className="text-right">{r.pb}</td><td className="text-right">{pct(r.roe)}</td>
              <td className="text-right">{pct(r.gross_margin)}</td><td className="text-right">{pct(r.fcf_yield)}</td>
              <td className="text-right" style={{ color: r.margin_of_safety == null ? "#9aa1ad" : r.margin_of_safety > 0 ? "#22c55e" : "#f43f5e" }}>
                {r.margin_of_safety == null ? "—" : `${(r.margin_of_safety * 100).toFixed(0)}%`}</td>
              <td className="text-right" style={{ color: r.f_score >= 7 ? "#22c55e" : r.f_score >= 4 ? "#f59e0b" : "#f43f5e" }}>{r.f_score}/9</td>
              <td className="text-right" style={{ color: r.altman_zone === "sûr" ? "#22c55e" : r.altman_zone === "gris" ? "#f59e0b" : "#f43f5e" }}>{r.altman_z}</td>
              <td className="text-right" style={{ color: r.tech_label === "haussier" ? "#22c55e" : r.tech_label === "baissier" ? "#f43f5e" : "#9aa1ad" }}>{r.tech_score}</td>
              <td className="text-right font-medium">{r.combined_score}</td>
              <td className="text-right font-sans font-medium" style={{ color: RC[r.rating] }}>{r.rating}</td>
            </tr>))}</tbody>
        </table>
      </section>
    </main>
  );
}
