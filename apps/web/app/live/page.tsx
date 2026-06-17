"use client";
import { useLive } from "@/lib/api";
import { PageSkeleton } from "@/components/ui";

const eur = (x?: number) => Math.round(x ?? 0).toLocaleString("fr-FR");

export default function Live() {
  const { data: l } = useLive();
  if (!l) return <PageSkeleton />;
  const brokers = l.brokers ?? [], real = l.real ?? { connected: false, equity: 0, positions: [] };
  return (
    <main className="max-w-5xl mx-auto p-6 space-y-4">
      <h1 className="text-xl font-semibold tracking-tight">Portefeuille réel</h1>
      <p className="text-muted text-sm">Cette page n'affiche que tes <b>données réelles</b> Alpaca / Bitmart. Rien de fictif ici.</p>

      {/* Statut */}
      <div className="card p-4" style={{ borderColor: real.connected ? "#22c55e" : "#f59e0b" }}>
        <div className="flex items-center gap-2">
          <span className="inline-block w-2 h-2 rounded-full" style={{ background: real.connected ? "#22c55e" : "#f59e0b" }} />
          <b>{real.connected ? "Broker connecté — données réelles" : "Aucun broker connecté"}</b>
          <span className="text-muted text-sm">· mode <b style={{ color: "#22c55e" }}>paper</b> par défaut</span>
        </div>
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

      {real.connected ? (
        <section className="card p-4 overflow-x-auto">
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-sm uppercase tracking-wide text-muted">Tes positions réelles</h2>
            <span className="mono text-sm">Equity : <b>{eur(real.equity)} $</b></span>
          </div>
          {real.positions.length === 0 ? (
            <p className="text-muted text-sm">Aucune position ouverte chez le broker.</p>
          ) : (
            <table className="text-sm mono">
              <thead><tr><th>Actif</th><th>Broker</th><th>Sens</th><th style={{ textAlign: "right" }}>Qté</th><th style={{ textAlign: "right" }}>PRU</th></tr></thead>
              <tbody>{real.positions.map((p: any, i: number) => (
                <tr key={`${p.symbol}-${i}`}><td>{p.symbol}</td><td className="text-muted">{p.broker}</td>
                  <td style={{ color: p.side === "long" ? "#22c55e" : "#f43f5e" }}>{p.side}</td>
                  <td style={{ textAlign: "right" }}>{p.qty}</td><td style={{ textAlign: "right" }}>{p.avg_price}</td></tr>))}</tbody>
            </table>
          )}
        </section>
      ) : (
        <section className="card p-4">
          <h2 className="text-sm uppercase tracking-wide text-muted mb-2">Connecter tes comptes</h2>
          <ol className="text-sm space-y-1.5 list-decimal pl-5">
            <li>Crée un fichier <code className="mono">.env</code> à la racine du projet (jamais committé).</li>
            <li>Ajoute tes clés (voir <code className="mono">.env.example</code>).</li>
            <li>Relance l'API : <code className="mono">make api</code> → tes positions réelles apparaîtront ici.</li>
          </ol>
          <p className="text-muted2 text-xs mt-2">Pour répliquer le portefeuille modèle en paper : <code className="mono">make live</code> (aperçu) puis <code className="mono">make live-go</code> (exécution paper). Alpaca reste paper ; Bitmart protégé par dry-run.</p>
        </section>
      )}
    </main>
  );
}
