"use client";
import { useLive } from "@/lib/api";
import { PageSkeleton } from "@/components/ui";

const eur = (x: number) => Math.round(x).toLocaleString("fr-FR");
const pct = (x?: number) => `${((x ?? 0) * 100).toFixed(1)}%`;

export default function Live() {
  const { data: l } = useLive();
  if (!l) return <PageSkeleton />;
  const brokers = l.brokers ?? [], targets = l.target_orders ?? [], rec = l.reconciliation ?? {};
  return (
    <main className="max-w-5xl mx-auto p-6 space-y-4">
      <h1 className="text-xl font-semibold tracking-tight">Portefeuille réel — exécution</h1>

      {/* Bandeau sécurité */}
      <div className="card p-4" style={{ borderColor: l.connected ? "#22c55e" : "#f59e0b" }}>
        <div className="flex items-center gap-2">
          <span className="inline-block w-2 h-2 rounded-full" style={{ background: l.connected ? "#22c55e" : "#f59e0b" }} />
          <b>{l.connected ? "Broker connecté" : "Aucun broker connecté"}</b>
          <span className="text-muted text-sm">· mode <b style={{ color: "#22c55e" }}>paper</b> par défaut · aucun ordre réel sans confirmation explicite</span>
        </div>
        {!l.connected && <p className="text-muted text-xs mt-2">Renseigne les clés API (variables d'environnement) puis relance l'API. Les actions/ETF passent par <b>Alpaca (paper)</b>, la crypto par <b>Bitmart</b>.</p>}
      </div>

      {/* Brokers */}
      <section className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {brokers.map((b: any) => (
          <div key={b.name} className="card p-4">
            <div className="flex items-center justify-between">
              <div><b>{b.name}</b> <span className="text-muted text-xs">· {b.scope}</span></div>
              <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: "var(--surface3)", color: b.connected ? "#22c55e" : "#9aa1ad" }}>
                {b.connected ? "connecté" : "non connecté"}{b.paper ? " · paper" : ""}
              </span>
            </div>
            <div className="text-muted2 text-xs mt-2 mono">{b.env.join("  ·  ")}</div>
          </div>
        ))}
      </section>

      {/* Comment exécuter */}
      <section className="card p-4">
        <h2 className="text-sm uppercase tracking-wide text-muted mb-2">Comment répliquer le portefeuille modèle</h2>
        <ol className="text-sm space-y-1.5 list-decimal pl-5">
          <li>Crée un fichier <code className="mono">.env</code> à la racine avec tes clés (jamais committé).</li>
          <li>Aperçu sans risque (aucun ordre envoyé) : <code className="mono">make live</code></li>
          <li>Exécution en <b>paper</b> (clés requises) : <code className="mono">make live-go</code></li>
        </ol>
        <p className="text-muted2 text-xs mt-2">Alpaca reste toujours en paper. Bitmart est protégé par un dry-run tant que <code className="mono">--live --yes</code> n'est pas passé. Permissions API minimales, jamais de retrait.</p>
      </section>

      {/* Ordres cibles */}
      <section className="card p-4 overflow-x-auto">
        <h2 className="text-sm uppercase tracking-wide text-muted mb-2">Ordres cibles (allocation modèle à répliquer)</h2>
        <table className="text-sm mono">
          <thead><tr><th>Actif</th><th>Sens</th><th>Broker</th><th style={{ textAlign: "right" }}>Poids cible</th></tr></thead>
          <tbody>{targets.map((o: any) => (
            <tr key={o.symbol}><td>{o.symbol}</td>
              <td style={{ color: o.side === "long" ? "#22c55e" : "#f43f5e" }}>{o.side}</td>
              <td className="text-muted">{o.broker}</td>
              <td style={{ textAlign: "right" }}>{pct(o.weight_pct)}</td></tr>))}</tbody>
        </table>
      </section>

      {/* Réconciliation + coûts */}
      {rec.tca && (
        <section className="card p-4">
          <h2 className="text-sm uppercase tracking-wide text-muted mb-2">Réconciliation & coûts d'exécution (TCA)</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm mono">
            <div><div className="text-muted text-xs">Ordres d'ajustement</div><div className="text-lg">{rec.n_orders}</div></div>
            <div><div className="text-muted text-xs">Drift</div><div className="text-lg">{pct(rec.drift_pct)}</div></div>
            <div><div className="text-muted text-xs">Coût estimé</div><div className="text-lg">{rec.tca.total_bps} bps</div></div>
            <div><div className="text-muted text-xs">dont impact/spread/frais</div><div className="text-sm mt-1">{eur(rec.tca.impact_usd)} / {eur(rec.tca.spread_usd)} / {eur(rec.tca.fees_usd)} $</div></div>
          </div>
          {l.execution && <p className="text-muted2 text-xs mt-2">Plan d'exécution {l.execution.algo} ({l.execution.slices} tranches) sur le plus gros ordre ({l.execution.symbol}) pour limiter l'impact marché.</p>}
        </section>
      )}
    </main>
  );
}
