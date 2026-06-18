"use client";
import { StepBanner } from "@/components/Pipeline";
import { useState } from "react";
import { usePositions, useSentiment } from "@/lib/api";
import { TechnicalChart } from "@/components/TechnicalChart";
import { PageSkeleton } from "@/components/ui";

const eur = (x?: number) => (x ?? 0).toLocaleString("fr-FR", { maximumFractionDigits: 0 });

export default function Positions() {
  const { data } = usePositions();
  const { data: sent } = useSentiment();
  const [sel, setSel] = useState<string | null>(null);
  if (!data) return <PageSkeleton />;
  const sentBy: Record<string, number> = {};
  (sent?.rows ?? []).forEach((r: any) => (sentBy[r.symbol] = r.score));
  const alloc = data.preset_allocation ?? [];
  const series = data.series ?? {}, markers = data.markers ?? {};
  const exposure = alloc.reduce((a: number, r: any) => a + (r.weight ?? 0), 0);
  const invested = alloc.reduce((a: number, r: any) => a + (r.notional ?? 0), 0);
  const cap = data.portfolio?.initial ?? 10000;
  const nTrad = alloc.filter((r: any) => r.tradeable).length;
  return (
    <main className="max-w-5xl mx-auto p-6 space-y-4">
      <h1 className="text-xl font-semibold tracking-tight">Positions
        <span className="ml-2 text-xs font-normal px-2 py-0.5 rounded-full align-middle"
          style={{ background: "color-mix(in srgb, var(--accent) 16%, transparent)", color: "var(--accent2)" }}>PRESET · production</span></h1>
      <p className="text-muted text-xs">Allocation cible du <b>preset</b> (risk-parity + DD-target, plafonnée 10 %/ligne) — cohérente avec le Dashboard et le <b>Portefeuille réel</b>. Univers restreint aux actifs <b>négociables</b> (Alpaca US / Bitmart crypto).</p>
      <StepBanner active="portfolio" />

      <section className="card p-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div><div className="text-muted text-xs uppercase">Capital</div><div className="text-xl mono">${eur(cap)}</div></div>
          <div><div className="text-muted text-xs uppercase">Investi / Cash</div><div className="text-xl mono">${eur(invested)} / ${eur(cap - invested)}</div></div>
          <div><div className="text-muted text-xs uppercase">Exposition</div><div className="text-xl mono">{(exposure * 100).toFixed(0)}% · {alloc.length} lignes</div></div>
          <div><div className="text-muted text-xs uppercase">Négociables</div><div className="text-xl mono">{nTrad}/{alloc.length}</div></div>
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
        {alloc.length === 0 ? <p className="text-muted text-sm">Allocation indisponible.</p> : (
        <>
        <p className="text-muted text-xs mb-3">Clique un actif pour son graphique (si données dispo).</p>
        <table className="w-full text-sm mono">
          <thead className="text-muted text-xs">
            <tr><th className="text-left font-normal">Actif</th><th className="text-left font-normal">Secteur</th>
            <th className="text-left font-normal">Broker</th><th className="text-right font-normal">Sentiment</th>
            <th className="text-right font-normal">Poids</th><th className="text-right font-normal">Notionnel</th>
            <th className="text-right font-normal">Prix</th><th className="text-right font-normal">Qté</th></tr>
          </thead>
          <tbody>{alloc.map((r: any) => (
            <tr key={r.symbol} className="border-t border-border hover:bg-surfaceAlt cursor-pointer" onClick={() => setSel(r.symbol)}>
              <td className="py-1.5"><span className="text-accent border-b border-dotted border-border">{r.symbol}</span>
                {!r.tradeable && <span className="ml-1 text-[10px]" style={{ color: "var(--warn)" }}>⚠︎</span>}</td>
              <td className="font-sans text-xs text-muted">{r.sector || r.asset_class}</td>
              <td className="font-sans text-xs">{r.broker}{r.broker_symbol !== r.symbol ? ` (${r.broker_symbol})` : ""}</td>
              <td className="text-right">{sentBy[r.symbol] == null ? "—" :
                <span style={{ color: sentBy[r.symbol] > 0.05 ? "#22c55e" : sentBy[r.symbol] < -0.05 ? "#f43f5e" : "#9aa1ad" }}>
                  {sentBy[r.symbol].toFixed(2)}</span>}</td>
              <td className="text-right">{(r.weight * 100).toFixed(1)}%</td>
              <td className="text-right">${eur(r.notional)}</td>
              <td className="text-right">{r.price}</td>
              <td className="text-right">{typeof r.qty === "number" ? r.qty.toFixed(3) : r.qty}</td>
            </tr>))}</tbody>
        </table>
        </>)}
      </section>
      <p className="text-muted2 text-xs">Allocation cible (avant exécution) — pas de P&L tant que les ordres ne sont pas passés en paper. Exécution : onglet <b>Portefeuille réel</b> ou <code className="mono">make live</code>.</p>
    </main>
  );
}
