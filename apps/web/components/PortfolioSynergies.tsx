const SOURCES = [
  ["Données & graphiques", "Historiques locaux chargés à la demande et calendriers alignés sans remplissage", "Actif local"],
  ["Données & graphiques", "Scores de marché joints ; historiques et FX restent à raccorder", "Partiel"],
  ["Fondamentaux & résultats", "Qualité, valorisation et calendrier joints par instrument", "Partiel"],
  ["Macro & régimes", "Disponibilité et source visibles ; tilt non calibré", "Partiel"],
  ["ML", "Scores affichés seulement lorsque le gate d'edge est positif", "Partiel"],
  ["Portefeuille & risque", "Covariance, VaR/ES, drawdown, concentration et risk budget", "Moteurs existants"],
];

export function PortfolioSynergies() {
  return <section className="card space-y-4">
    <div>
      <div className="eyebrow">Synergies avec le terminal</div>
      <h2 className="text-lg font-semibold mt-1">Un seul diagnostic, plusieurs sources de preuves</h2>
      <p className="text-xs text-muted mt-1 max-w-3xl">Les premières jointures read-only avec les autres onglets sont actives après confirmation du snapshot. Les statuts ci-dessous distinguent ce qui est déjà projeté de ce qui exige encore un recalcul dédié.</p>
    </div>
    <div className="grid md:grid-cols-2 gap-2">
      {SOURCES.map(([name, purpose, status]) => <div key={name} className="rounded-xl border border-border p-3">
        <div className="flex justify-between gap-3"><strong className="text-sm">{name}</strong><span className="text-[10px] mono text-cyan-500">{status}</span></div>
        <p className="text-xs text-muted mt-1">{purpose}</p>
      </div>)}
    </div>
    <div className="rounded-xl bg-surface3 p-3 text-xs text-muted">
      <b>Principe de décision :</b> les profils prudent, neutre et dynamique seront des objectifs d'optimisation sous contraintes — jamais des labels marketing. Le ML pourra modifier des estimations avec son incertitude, mais ne produira pas directement les poids. En cas de modèle périmé, de couverture faible ou de DSR insuffisant, l'allocation classique restera la référence.
    </div>
  </section>;
}
