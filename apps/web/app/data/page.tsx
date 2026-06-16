"use client";
import { useData } from "@/lib/api";

const nb = (x: number) => x.toLocaleString("fr-FR");
const dt = (s?: string) => (s ? String(s).slice(0, 10) : "—");

export default function DataPage() {
  const { data: d } = useData();
  if (!d) return <div className="p-8 text-muted">Chargement…</div>;
  const q = d.quality ?? {};
  const cards: [string, string][] = [
    ["Provider", d.provider],
    ["Barres collectées", nb(d.total_bars)],
    ["Symboles", String((d.collection ?? []).length)],
    ["Fondamentaux", d.fundamentals_provider ?? "—"],
  ];
  return (
    <main className="max-w-5xl mx-auto p-6 space-y-4">
      <h1 className="text-xl font-semibold tracking-tight">Données</h1>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {cards.map(([lab, val]) => (
          <div key={lab} className="card p-4">
            <div className="text-muted text-xs uppercase tracking-wide">{lab}</div>
            <div className="text-lg mono mt-1">{val}</div>
          </div>
        ))}
      </div>

      <section className="card p-4">
        <div className="flex items-center justify-between mb-1">
          <h2 className="text-sm uppercase tracking-wide text-muted">Collecte OHLCV — univers complet</h2>
          <span className="text-xs text-muted">{(d.collection ?? []).length} symboles</span>
        </div>
        <p className="text-muted text-xs mb-3">
          Ordre de fallback : {(d.fallback_order ?? []).join(" → ") || "—"} · cache {d.cache ? "activé" : "désactivé"}
        </p>
        <div className="max-h-[460px] overflow-auto">
          <table className="w-full text-sm mono">
            <thead className="text-muted text-xs sticky top-0 bg-surface">
              <tr><th className="text-left font-normal">Symbole</th><th className="text-left font-normal">Classe</th>
              <th className="text-right font-normal">Barres</th><th className="text-left font-normal">Début</th>
              <th className="text-left font-normal">Fin</th><th className="text-right font-normal">Dernier cours</th></tr>
            </thead>
            <tbody>{(d.collection ?? []).map((r: any) => (
              <tr key={r.symbol} className="border-t border-border">
                <td className="py-1.5">{r.symbol}</td><td className="text-muted font-sans">{r.asset_class}</td>
                <td className="text-right">{r.bars}</td>
                <td className="text-muted">{dt(r.start)}</td><td className="text-muted">{dt(r.end)}</td>
                <td className="text-right">{r.last_close}</td>
              </tr>))}</tbody>
          </table>
        </div>
      </section>

      <section className="card p-4">
        <div className="flex justify-between items-center mb-2">
          <h2 className="text-sm uppercase tracking-wide text-muted">Contrôle qualité ({q.symbol})</h2>
          <span className="text-xs px-2 py-0.5 rounded-full bg-surfaceAlt" style={{ color: q.ok ? "#22c55e" : "#ef4444" }}>
            {q.ok ? "✓ conforme" : "✗ erreurs"}
          </span>
        </div>
        <p className="text-muted text-xs">
          {q.n_rows ?? 0} lignes validées · prix&gt;0 · cohérence OHLC · timestamps croissants · trous temporels
          {(q.warnings ?? []).length ? ` — ${q.warnings.join("; ")}` : " : aucun"}
          {(q.errors ?? []).length ? ` — ERREURS: ${q.errors.join("; ")}` : ""}
        </p>
      </section>

      <section className="card p-4">
        <h2 className="text-sm uppercase tracking-wide text-muted mb-3">Base de données — couches médaillon</h2>
        <div className="divide-y divide-border">
          {(d.layers ?? []).map((l: any) => (
            <div key={l.name} className="py-2">
              <div className="text-sm">
                <b>{l.name}</b>
                <span className="ml-2 text-xs px-2 py-0.5 rounded-full bg-surfaceAlt mono">{l.store}</span>
              </div>
              <div className="text-muted text-xs mt-0.5">{l.desc}</div>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
