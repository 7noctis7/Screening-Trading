"use client";
import { useMl } from "@/lib/api";
import { PageSkeleton, EmptyState } from "@/components/ui";

const nb = (x: number) => x.toLocaleString("fr-FR");

export default function Ml() {
  const { data: ml } = useMl();
  if (!ml) return <PageSkeleton />;
  if (!ml.available)
    return <main className="max-w-3xl mx-auto p-6"><EmptyState title="Modèle ML indisponible" hint="Échantillon insuffisant pour entraîner le modèle." /></main>;
  const cal = ml.calibration, drift = ml.drift, conf = ml.conformal;
  const cards: [string, string][] = [
    ["Modèle", ml.model],
    ["AUC (out-of-time)", ml.auc != null ? String(ml.auc) : "—"],
    ["Échantillon (train)", nb(ml.n_train)],
    ["Horizon", `${ml.horizon_days} j`],
  ];
  const maxw = Math.max(0.01, ...ml.feature_importance.map((f: any) => f.weight));
  return (
    <main className="max-w-5xl mx-auto p-6 space-y-4">
      <h1 className="text-xl font-semibold tracking-tight">Signaux ML</h1>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {cards.map(([lab, val]) => (
          <div key={lab} className="card p-4">
            <div className="text-muted text-xs uppercase tracking-wide">{lab}</div>
            <div className="text-lg mono mt-1">{val}</div>
          </div>
        ))}
      </div>
      <p className="text-muted text-xs">
        Régression logistique entraînée en cross-section sur tout l'univers (momentum 1m/3m,
        tendance vs MM50, RSI, volatilité). Score = probabilité de hausse à ~{ml.horizon_days} jours,
        validée hors-échantillon (AUC). Démonstration synthétique : edge volontairement modeste.
      </p>

      <section className="card p-4 overflow-x-auto">
        <h2 className="text-sm uppercase tracking-wide text-muted mb-3">Top convictions ML</h2>
        <table className="w-full text-sm">
          <thead className="text-muted text-xs">
            <tr><th className="text-left font-normal">Actif</th><th className="text-left font-normal">Nom</th>
            <th className="text-left font-normal">Secteur</th><th className="text-right font-normal">Proba hausse</th></tr>
          </thead>
          <tbody>{ml.top_conviction.map((a: any) => (
            <tr key={a.symbol} className="border-t border-border">
              <td className="py-1.5 mono">{a.symbol}</td><td className="text-muted">{a.name}</td>
              <td className="text-muted">{a.sector}</td>
              <td className="text-right mono" style={{ color: a.ml_score >= 0.5 ? "#22c55e" : "#f43f5e" }}>
                {(a.ml_score * 100).toFixed(1)}%</td>
            </tr>))}</tbody>
        </table>
      </section>

      <section className="card p-4">
        <h2 className="text-sm uppercase tracking-wide text-muted mb-3">Importance des variables</h2>
        <div className="space-y-1.5">
          {ml.feature_importance.map((f: any) => (
            <div key={f.feature} className="flex items-center gap-2 text-xs">
              <span className="w-36 text-muted">{f.feature}</span>
              <span className="h-1.5 rounded bg-accent" style={{ width: `${Math.round((f.weight / maxw) * 100)}%`, maxWidth: 360 }} />
              <span className="mono">{f.weight.toFixed(3)}</span>
            </div>
          ))}
        </div>
      </section>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {cal?.available && (
          <section className="card p-4">
            <h2 className="text-sm uppercase tracking-wide text-muted mb-2">Calibration des probabilités</h2>
            <div className="grid grid-cols-2 gap-3 mono text-sm">
              <div><div className="text-muted text-xs">Brier (brut)</div><div className="text-lg">{cal.brier_raw}</div></div>
              <div><div className="text-muted text-xs">Brier (calibré)</div>
                <div className="text-lg" style={{ color: cal.brier_calibrated <= cal.brier_raw ? "#22c55e" : "#f59e0b" }}>{cal.brier_calibrated}</div></div>
            </div>
            <p className="text-muted2 text-xs mt-2 font-sans">Plus bas = mieux. La calibration (Platt) aligne la proba prédite sur la fréquence observée.</p>
            {conf?.available && (
              <div className="mt-3 pt-3 border-t border-border text-sm">
                <div className="text-muted text-xs uppercase tracking-wide mb-1">Conformal prediction</div>
                <div className="mono">couverture <b style={{ color: conf.empirical_coverage >= conf.target_coverage - 0.03 ? "#22c55e" : "#f59e0b" }}>{(conf.empirical_coverage * 100).toFixed(0)}%</b>
                  <span className="text-muted"> (cible {(conf.target_coverage * 100).toFixed(0)}%) · taille moy. d'ensemble {conf.avg_set_size}</span></div>
              </div>
            )}
          </section>
        )}
        {drift?.available && (
          <section className="card p-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm uppercase tracking-wide text-muted">Drift des features (PSI)</h2>
              <span className="text-xs" style={{ color: drift.drift_detected ? "#f59e0b" : "#22c55e" }}>
                {drift.drift_detected ? `${drift.flagged.length} dérive(s) forte(s)` : "stable"}</span>
            </div>
            <table className="w-full text-sm mt-2"><tbody>
              {Object.entries(drift.by_feature ?? {}).map(([f, d]: any) => (
                <tr key={f} className="border-t border-border">
                  <td className="py-1 text-muted">{f}</td>
                  <td className="text-right mono">{d.psi}</td>
                  <td className="text-right text-xs" style={{ color: d.status === "fort" ? "#f43f5e" : d.status === "modéré" ? "#f59e0b" : "#22c55e" }}>{d.status}</td>
                </tr>))}
            </tbody></table>
          </section>
        )}
      </div>
    </main>
  );
}
