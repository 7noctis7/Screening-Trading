"use client";
import { useLive } from "@/lib/api";
import { PageSkeleton } from "@/components/ui";
import { StepBanner } from "@/components/Pipeline";

const eur = (x?: number) => Math.round(x ?? 0).toLocaleString("fr-FR");

function BrokerCard({ b, accent }: { b: any; accent: string }) {
  const ok = b?.ok, configured = b?.configured;
  const color = ok ? "#22c55e" : configured ? "#f43f5e" : "#9aa1ad";
  const pos = (b?.positions ?? []).map((p: any) => ({ ...p, val: (p.qty || 0) * (p.avg_price || 0) }));
  const tot = pos.reduce((a: number, p: any) => a + p.val, 0) || 1;
  const invested = pos.reduce((a: number, p: any) => a + p.val, 0);
  const cash = Math.max(0, (b?.equity ?? 0) - invested);
  return (
    <div className="card p-4" style={{ borderColor: `color-mix(in srgb, ${color} 45%, transparent)` }}>
      <div className="flex items-center justify-between">
        <b style={{ color: accent }}>{b.name}</b>
        <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: "var(--surface3)", color }}>
          {ok ? "connecté ✓" : configured ? "erreur" : "non configuré"}
        </span>
      </div>
      {ok ? (
        <>
          <div className="grid grid-cols-3 gap-2 mt-3">
            <div><div className="text-muted text-[10px] uppercase">Equity</div><div className="mono text-base">{eur(b.equity)} $</div></div>
            <div><div className="text-muted text-[10px] uppercase">Investi</div><div className="mono text-base">{eur(invested)} $</div></div>
            <div><div className="text-muted text-[10px] uppercase">Positions</div><div className="mono text-base">{pos.length}</div></div>
          </div>
          {pos.length === 0 ? (
            <p className="text-muted text-sm mt-3">Aucune position ouverte chez {b.name}.</p>
          ) : (
            <>
              {/* barres d'allocation (poids par position) */}
              <div className="mt-3 space-y-1.5">
                {pos.sort((x: any, y: any) => y.val - x.val).slice(0, 10).map((p: any, i: number) => (
                  <div key={i} className="flex items-center gap-2 text-xs">
                    <span className="mono w-24 truncate">{p.symbol}</span>
                    <div className="flex-1 h-2 rounded-full" style={{ background: "var(--surface3)" }}>
                      <div style={{ width: `${(p.val / tot) * 100}%`, height: "100%", borderRadius: 999,
                        background: `linear-gradient(90deg, ${accent}, color-mix(in srgb, ${accent} 50%, #22c55e))` }} />
                    </div>
                    <span className="mono w-12 text-right text-muted">{((p.val / tot) * 100).toFixed(0)}%</span>
                  </div>
                ))}
              </div>
              <table className="text-sm mono mt-3 w-full">
                <thead className="text-muted text-xs"><tr><th className="text-left font-normal">Actif</th><th className="text-left font-normal">Sens</th>
                  <th className="text-right font-normal">Qté</th><th className="text-right font-normal">PRU</th><th className="text-right font-normal">Valeur</th></tr></thead>
                <tbody>{pos.map((p: any, i: number) => (
                  <tr key={i} className="border-t border-border"><td className="py-1">{p.symbol}</td>
                    <td style={{ color: p.side === "long" ? "#22c55e" : "#f43f5e" }}>{p.side}</td>
                    <td className="text-right">{p.qty}</td><td className="text-right">{p.avg_price}</td>
                    <td className="text-right">{eur(p.val)} $</td></tr>))}</tbody>
              </table>
            </>
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
      <div className="card p-3 text-xs" style={{ borderColor: "color-mix(in srgb, var(--accent) 35%, transparent)" }}>
        ℹ️ <b>Comptes distincts</b> : actions/ETF → <b>Alpaca</b> (dimensionnées sur ton capital Alpaca) · crypto → <b>Bitmart</b> (dimensionnée sur ton capital Bitmart, sleeve risk-parity si <code className="mono">QUANT_CRYPTO_PCT</code> &gt; 0). Trading <b>SPOT uniquement</b> (jamais de futures/levier).
      </div>

      {/* KPI globaux */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="card p-4"><div className="text-muted text-xs uppercase">Equity totale</div><div className="text-xl mono mt-1">{eur(real.equity)} $</div></div>
        <div className="card p-4"><div className="text-muted text-xs uppercase">Alpaca</div><div className="text-lg mono mt-1">{eur(a?.equity)} $</div></div>
        <div className="card p-4"><div className="text-muted text-xs uppercase">Bitmart</div><div className="text-lg mono mt-1">{eur(b?.equity)} $</div></div>
        <div className="card p-4"><div className="text-muted text-xs uppercase">Positions réelles</div><div className="text-lg mono mt-1">{(real.positions ?? []).length}</div></div>
      </div>

      {/* Détail par broker + diagnostic */}
      <section className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {a && <BrokerCard b={a} accent="#3b82f6" />}
        {b && <BrokerCard b={b} accent="#f59e0b" />}
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
