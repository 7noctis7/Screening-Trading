"use client";

// ÉCART DE RÉPLICATION — combien du compte réel ne suit PAS le modèle, et quoi faire.
//
// La table « composition modèle vs réel » montrait l'écart sans le chiffrer : on lisait
// « +158 % contre −1,1 % » sur QQQ et on en concluait une sous-performance. C'est faux deux fois.
// D'abord les deux P&L n'ont pas la même durée. Ensuite l'écart n'est pas de performance mais de
// COMPOSITION : une seule ligne commune, un satellite modèle absent du compte, une poche crypto
// que le modèle ne détient pas. La mesure est l'active share (Cremers-Petajisto, 2009).

const pc = (x: number | null | undefined) => (x == null ? "—" : `${(x * 100).toFixed(1)} %`);
const usd = (x: number) => `${Math.round(x).toLocaleString("fr-FR")} $`;

export default function EcartReplication({ r }: { r: any }) {
  if (!r?.available) return null;
  const avant = Number(r.active_share_avant ?? 0);
  const apres = Number(r.active_share_apres ?? 0);
  const poche = Number(r.poche_hors_modele ?? 0);
  const ordres: any[] = r.ordres ?? [];

  return (
    <div className="mt-4 pt-3 border-t border-border">
      <h3 className="text-sm uppercase tracking-wide text-muted mb-1">Écart de réplication</h3>
      <p className="text-muted2 text-xs mb-3">
        <b>Active share</b> = part du capital qui ne réplique pas le modèle (½·Σ|poids modèle −
        poids réel|). C'est de là que viendra l'écart de performance <i>futur</i> — l'écart passé,
        lui, ne se rattrape pas : il appartient à des positions déjà tenues.
      </p>

      <div className="grid gap-3 sm:grid-cols-3 mb-3">
        <div className="rounded-lg border border-border p-3">
          <div className="text-xs text-muted">Aujourd'hui</div>
          <div className="mono text-xl">{pc(avant)}</div>
          <div className="text-[11px] text-muted2">du compte suit autre chose que le modèle</div>
        </div>
        <div className="rounded-lg border border-border p-3">
          <div className="text-xs text-muted">Après le plan ci-dessous</div>
          <div className="mono text-xl">{pc(apres)}</div>
          <div className="text-[11px] text-muted2">
            {apres >= poche - 0.001
              ? "plancher atteint : la poche hors modèle fixe la limite"
              : "écart résiduel"}
          </div>
        </div>
        <div className="rounded-lg border border-border p-3">
          <div className="text-xs text-muted">Poche hors modèle</div>
          <div className="mono text-xl">{pc(poche)}</div>
          <div className="text-[11px] text-muted2">conservée — aucune vente proposée</div>
        </div>
      </div>

      {apres >= poche - 0.001 && poche > 0.01 && (
        <p className="text-xs mb-3" style={{ color: "#f59e0b" }}>
          ⚠️ Acheter tout le satellite du modèle ne fera pas descendre l'écart sous {pc(poche)} :
          c'est exactement le poids de la poche que le modèle ne détient pas. Tant qu'elle est là,
          les deux courbes ne peuvent pas se rejoindre — ce n'est pas un réglage d'exécution,
          c'est une décision d'allocation, et elle vous appartient.
        </p>
      )}

      {(r.non_replicables ?? []).length > 0 && (
        <p className="text-xs text-muted2 mb-3">
          <b>Non réplicables à cette taille de compte</b> ({usd(r.plancher)} minimum par ligne) :{" "}
          {r.non_replicables.join(", ")}. Leur poids modèle est redistribué au prorata sur les
          autres lignes, ce qui conserve les proportions relatives du modèle.
        </p>
      )}

      {ordres.length === 0 ? (
        <p className="text-xs text-muted2">Aucun ordre : tout est dans la bande d'inaction.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-muted text-xs"><tr>
              <th className="text-left font-normal">Actif</th>
              <th className="text-left font-normal">Action</th>
              <th className="text-right font-normal">Montant</th>
              <th className="text-right font-normal">Poids actuel</th>
              <th className="text-right font-normal">Poids cible</th>
            </tr></thead>
            <tbody className="mono">
              {ordres.map((o) => (
                <tr key={o.symbole} className="border-t border-border">
                  <td className="py-1.5">{o.symbole}</td>
                  <td className="font-sans text-xs">
                    {o.action}{o.liquidation && <span className="ml-1 text-muted2">(en quantité)</span>}
                  </td>
                  <td className="text-right">{usd(o.montant)}</td>
                  <td className="text-right text-muted2">{pc(o.poids_actuel)}</td>
                  <td className="text-right">{pc(o.poids_cible)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="text-muted2 text-xs mt-3">
        Bande d'inaction : {usd(r.bande)}. Un écart plus petit ne paie pas son aller-retour.
        Ce plan n'est jamais exécuté automatiquement.
      </p>
    </div>
  );
}
