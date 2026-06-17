"use client";
import { useLive } from "@/lib/api";
import { PageSkeleton } from "@/components/ui";
import { StepBanner } from "@/components/Pipeline";

const eur = (x?: number) => Math.round(x ?? 0).toLocaleString("fr-FR");

function BrokerCard({ b }: { b: any }) {
  const ok = b?.ok, configured = b?.configured;
  const color = ok ? "#22c55e" : configured ? "#f43f5e" : "#9aa1ad";
  return (
    <div className="card p-4" style={{ borderColor: `color-mix(in srgb, ${color} 45%, transparent)` }}>
      <div className="flex items-center justify-between">
        <b>{b.name}</b>
        <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: "var(--surface3)", color }}>
          {ok ? "connecté ✓" : configured ? "erreur" : "non configuré"}
        </span>
      </div>
      {ok ? (
        <>
          <div className="mono text-lg mt-2">{eur(b.equity)} $ <span className="text-muted text-xs">equity</span></div>
          {b.positions.length === 0 ? (
            <p className="text-muted text-sm mt-2">Aucune position ouverte chez {b.name}.</p>
          ) : (
            <table className="text-sm mono mt-2 w-full">
              <thead><tr><th>Actif</th><th>Sens</th><th style={{ textAlign: "right" }}>Qté</th><th style={{ textAlign: "right" }}>PRU</th></tr></thead>
              <tbody>{b.positions.map((p: any, i: number) => (
                <tr key={i}><td>{p.symbol}</td>
                  <td style={{ color: p.side === "long" ? "#22c55e" : "#f43f5e" }}>{p.side}</td>
                  <td style={{ textAlign: "right" }}>{p.qty}</td><td style={{ textAlign: "right" }}>{p.avg_price}</td></tr>))}</tbody>
            </table>
          )}
        </>
      ) : (
        <p className="text-xs mt-2" style={{ color }}>
          {configured ? <>⚠️ Connexion échouée : <span className="mono">{b.error}</span></> : <>Renseigne les clés dans <code className="mono">.env</code> puis relance l'API.</>}
        </p>
      )}
    </div>
  );
}

export default function Live() {
  const { data: l } = useLive();
  if (!l) return <PageSkeleton />;
  const real = l.real ?? {};
  const a = real.alpaca, b = real.bitmart;
  return (
    <main className="max-w-5xl mx-auto p-6 space-y-4">
      <h1 className="text-xl font-semibold tracking-tight">Portefeuille réel</h1>
      <StepBanner active="live" />
      <p className="text-muted text-xs">Données <b>réelles</b> de tes comptes Alpaca / Bitmart uniquement (aucun fictif). KPI &amp; positions séparés par broker.</p>

      {/* KPI globaux */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="card p-4"><div className="text-muted text-xs uppercase">Equity totale</div><div className="text-xl mono mt-1">{eur(real.equity)} $</div></div>
        <div className="card p-4"><div className="text-muted text-xs uppercase">Alpaca</div><div className="text-lg mono mt-1">{eur(a?.equity)} $</div></div>
        <div className="card p-4"><div className="text-muted text-xs uppercase">Bitmart</div><div className="text-lg mono mt-1">{eur(b?.equity)} $</div></div>
        <div className="card p-4"><div className="text-muted text-xs uppercase">Positions réelles</div><div className="text-lg mono mt-1">{(real.positions ?? []).length}</div></div>
      </div>

      {/* Détail par broker + diagnostic */}
      <section className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {a && <BrokerCard b={a} />}
        {b && <BrokerCard b={b} />}
      </section>

      {/* Diagnostic / "comment être sûr que ça marche" */}
      <section className="card p-4 text-sm">
        <h2 className="text-sm uppercase tracking-wide text-muted mb-2">Diagnostic</h2>
        <ul className="text-muted space-y-1 list-disc pl-5">
          <li><b>connecté ✓</b> = l'API a bien lu ton compte (même sans position ouverte).</li>
          <li><b>erreur</b> = clés présentes mais l'appel a échoué → le message exact est affiché (souvent : permissions API, IP non autorisée, ou Bitmart « spot » vs « futures »).</li>
          <li><b>non configuré</b> = clés absentes du <code className="mono">.env</code>.</li>
          <li>« Aucune position » est <b>normal</b> si tu n'as pas encore passé d'ordre — répliquer le modèle en paper : <code className="mono">make live</code> (aperçu) puis <code className="mono">make live-go</code>.</li>
        </ul>
      </section>
    </main>
  );
}
