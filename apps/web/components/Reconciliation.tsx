"use client";
// Combien le compte a-t-il gagné ? — et ENSUITE, d'où ça vient.
//
// CE QUI A ÉTÉ CORRIGÉ LE 18/09. Ce bloc ouvrait sur l'identité comptable et sur son
// résidu : la première chose lue était « écart NON expliqué +2 669,06 $ », là où la
// question posée était « je suis parti de 100 k, j'en ai 100 734, ça donne quoi ? ».
// Un rapprochement est un outil de DIAGNOSTIC du registre ; il ne remplace pas le
// résultat, il l'explique. L'ordre est donc : le résultat d'abord, sa décomposition
// ensuite, l'identité en note.
//
// LA DÉCOMPOSITION SE LIT DANS LE BON SENS. On part des composantes et on arrive à la
// variation RÉELLE du compte, le résidu étant une ligne nommée parmi les autres :
//
//     réalisé robot + réalisé import + latent + résidu = variation du compte
//
// C'est la même identité que `capital(fin) = capital(début) + …`, réarrangée. Lue dans
// ce sens, elle répond à « pourquoi 331 trades à +0,23 $ ne font pas +1 129 $ » —
// parce que trois autres lignes existent, et qu'elles sont plus grosses.
//
// CE QU'ON NE FAIT PAS : boucher le résidu. Il est calculé, nommé, rapporté au capital,
// et laissé tel quel. Un rapprochement qui tombe juste parce qu'on y a mis un terme
// d'ajustement ne prouve rien et masque exactement ce qu'il fallait voir.

const usd = (x?: number | null) =>
  x == null ? "—" : `$${x.toLocaleString("fr-FR", { maximumFractionDigits: 2, signDisplay: "exceptZero" })}`;
const niveau = (x?: number | null) =>
  x == null ? "—" : `$${x.toLocaleString("fr-FR", { maximumFractionDigits: 2 })}`;
const pct = (x?: number | null) =>
  x == null ? "—" : `${(x * 100).toLocaleString("fr-FR", { maximumFractionDigits: 2, signDisplay: "exceptZero" })} %`;

const couleur = (v?: number | null) =>
  v == null || v === 0 ? "var(--fg)" : v > 0 ? "var(--pos)" : "#ef4444";

function Ligne({ label, valeur, signe = true, fort = false, aide }: {
  label: string; valeur: number | null | undefined; signe?: boolean; fort?: boolean; aide?: string;
}) {
  return (
    <div className="flex justify-between gap-4" title={aide}>
      <span className={fort ? "text-fg" : "text-muted"}>{label}</span>
      <span className="mono" style={{ color: signe ? couleur(valeur) : "var(--fg)" }}>
        {signe ? usd(valeur) : niveau(valeur)}
      </span>
    </div>
  );
}

export function Reconciliation({ r }: { r: any }) {
  if (!r) return null;
  if (!r.disponible) {
    return (
      <section className="card p-3 text-xs text-muted2">
        Rapprochement capital ↔ registre indisponible : {r.motif ?? "motif non renseigné"}.
        {" "}Un silence ici se lirait comme un rapprochement réussi — il est donc dit.
      </section>
    );
  }
  const ok = r.boucle;
  return (
    <section className="card p-4 space-y-3 text-xs">
      {/* ── LE RÉSULTAT, en premier et en gros ─────────────────────────── */}
      <div>
        <h2 className="text-sm uppercase tracking-wide text-muted">Résultat du compte</h2>
        <div className="mt-1 flex flex-wrap items-baseline gap-x-3 mono">
          <span className="text-muted2">{niveau(r.capital_initial)}</span>
          <span className="text-muted2">→</span>
          <span className="text-base">{niveau(r.capital_final)}</span>
          <span className="text-base" style={{ color: couleur(r.variation) }}>
            {usd(r.variation)}
          </span>
          <span className="text-base" style={{ color: couleur(r.variation) }}>
            {pct(r.variation_part)}
          </span>
          {r.jours ? <span className="text-muted2">en {r.jours} jours</span> : null}
        </div>
        {r.fenetres?.[0] && (
          <p className="text-muted2 mt-1">
            du {r.fenetres[0].debut} au {r.fenetres[0].fin} · capital réel chez le courtier,
            aucun chiffre estimé.
          </p>
        )}
      </div>

      {/* ── D'OÙ VIENT CE MONTANT ──────────────────────────────────────── */}
      <div className="space-y-1 mono border-t pt-2" style={{ borderColor: "var(--border2)" }}>
        <div className="text-muted mb-1">D&apos;où vient ce {usd(r.variation)} ?</div>
        {r.realise_affiche != null && (
          <Ligne label="trades du robot, clôturés" valeur={r.realise_affiche}
            aide="Ce que montre le panneau « Historique des positions »." />
        )}
        {r.hors_panneau != null && (
          <Ligne label="lots importés, clôturés (hors robot)" valeur={r.hors_panneau}
            aide="Import historique, sans features de décision : subi par le compte, absent du panneau." />
        )}
        {r.realise_affiche == null && <Ligne label="réalisé, tous lots" valeur={r.realise} />}
        <Ligne label="latent des positions encore ouvertes" valeur={r.latent}
          aide="Lu chez le courtier, jamais estimé depuis un prix d'entrée." />
        {r.flux !== 0 && <Ligne label="versements / retraits" valeur={r.flux} />}
        <div className="border-t pt-1" style={{ borderColor: "var(--border2)" }}>
          <Ligne label="= ce que le registre explique" valeur={r.explique} fort />
        </div>
        <Ligne label="+ ce qu'il n'explique PAS" valeur={r.residu} fort
          aide="Résidu nommé, jamais comblé." />
        <div className="border-t pt-1" style={{ borderColor: "var(--border2)" }}>
          <Ligne label="= variation réelle du compte" valeur={r.variation} fort />
        </div>
      </div>

      {/* ── LES RÉSERVES, en note ──────────────────────────────────────── */}
      <div className="space-y-1 text-muted2 border-t pt-2" style={{ borderColor: "var(--border2)" }}>
        <p style={{ color: ok ? undefined : "#f59e0b" }}>{ok ? "✓ " : "⚠ "}{r.explication}</p>
        <p>
          Les {usd(r.realise_affiche)} du panneau « Historique des positions » ne sont donc
          <b> qu&apos;une ligne sur quatre</b> : les additionner ne peut pas retomber sur le compte.
          {" "}L&apos;identité complète s&apos;écrit <b>capital(fin) = capital(début) + réalisé
          + latent(fin) − latent(début) + flux − frais</b> ; un réalisé et un latent sont des
          <i> variations</i>, le capital est un <i>niveau</i>.
        </p>
        {r.memes_fenetres === false && r.fenetres?.length > 1 && (
          <p>
            ⚠ Les poches n&apos;ont pas la même fenêtre : {r.fenetres.map((f: any) =>
              `${f.compte} ${f.debut}→${f.fin}`).join(" · ")}. La somme porte donc sur des
            périodes différentes — une part de l&apos;écart vient de là.
          </p>
        )}
      </div>
    </section>
  );
}
