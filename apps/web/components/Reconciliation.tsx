"use client";
// Le capital réel se déduit-il du registre ? L'identité comptable, posée en entier.
//
// POURQUOI CE BLOC EXISTE. La question posée le 18/09 était : « la somme des gains/pertes
// de l'historique des positions, plus le gain/perte en cours, doit bien faire le capital
// réel ». Non — et c'est une question de DIMENSION, pas de justesse des chiffres. Un
// réalisé et un latent sont des VARIATIONS ; le capital réel est un NIVEAU. Leur somme
// vaut la variation du compte, pas le compte. L'identité part du capital INITIAL.
//
// CE QU'ON NE FAIT PAS : boucher le résidu. Il est calculé, nommé, rapporté au capital,
// et laissé tel quel. Un rapprochement qui tombe juste parce qu'on y a mis un terme
// d'ajustement ne prouve rien et masque exactement ce qu'il fallait voir.

const usd = (x?: number | null) =>
  x == null ? "—" : `$${x.toLocaleString("fr-FR", { maximumFractionDigits: 2, signDisplay: "exceptZero" })}`;
const niveau = (x?: number | null) =>
  x == null ? "—" : `$${x.toLocaleString("fr-FR", { maximumFractionDigits: 2 })}`;

function Ligne({ label, valeur, signe = true, fort = false, aide }: {
  label: string; valeur: number | null | undefined; signe?: boolean; fort?: boolean; aide?: string;
}) {
  const v = valeur ?? 0;
  return (
    <div className="flex justify-between gap-4" title={aide}>
      <span className={fort ? "text-fg" : "text-muted"}>{label}</span>
      <span className="mono" style={{ color: !signe || v === 0 ? "var(--fg)" : v > 0 ? "var(--pos)" : "#ef4444" }}>
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
    <section className="card p-4 space-y-2 text-xs" style={{ borderColor: ok ? undefined : "#f59e0b" }}>
      <div className="flex flex-wrap items-baseline gap-x-3">
        <h2 className="text-sm uppercase tracking-wide text-muted">Le capital se déduit-il du registre ?</h2>
        <span className="mono text-sm" style={{ color: ok ? "var(--pos)" : "#f59e0b" }}>
          {ok ? "✓ boucle" : `écart ${usd(r.residu)}`}
        </span>
      </div>
      <p className="text-muted2">
        <b>capital(fin) = capital(début) + réalisé + latent(fin) − latent(début) + flux − frais.</b>
        {" "}Un réalisé et un latent sont des <i>variations</i> ; le capital réel est un <i>niveau</i> :
        leur somme vaut la variation du compte, pas le compte.
      </p>
      <div className="space-y-1 mono">
        <Ligne label={`capital initial${r.fenetres?.[0]?.debut ? ` (${r.fenetres[0].debut})` : ""}`}
          valeur={r.capital_initial} signe={false} />
        <Ligne label="+ réalisé, tous lots subis par le compte" valeur={r.realise}
          aide="Somme des round-trips clôturés, import historique compris." />
        <Ligne label="+ latent des positions ouvertes" valeur={r.latent}
          aide="Lu chez le courtier, jamais estimé depuis un prix d'entrée." />
        {r.flux !== 0 && <Ligne label="+ versements / retraits" valeur={r.flux} />}
        <div className="border-t pt-1" style={{ borderColor: "var(--border2)" }}>
          <Ligne label="= attendu sur le compte" valeur={r.attendu} signe={false} fort />
        </div>
        <Ligne label={`capital réel constaté${r.fenetres?.[0]?.fin ? ` (${r.fenetres[0].fin})` : ""}`}
          valeur={r.capital_final} signe={false} fort />
        <Ligne label="écart NON expliqué" valeur={r.residu} fort />
      </div>
      <p style={{ color: ok ? "var(--muted)" : "#f59e0b" }}>{ok ? "✓ " : "⚠ "}{r.explication}</p>
      {r.realise_affiche != null && (
        <p className="text-muted2">
          Le panneau « Historique des positions » n'en montre qu'une part : <b className="mono">{usd(r.realise_affiche)}</b>
          {" "}de réalisé pour les trades du robot, contre <b className="mono">{usd(r.realise)}</b> subis par le compte.
          {" "}L'écart — <b className="mono">{usd(r.hors_panneau)}</b> — est l'import historique, hors périmètre du robot.
          {" "}Additionner ce qu'on voit à l'écran ne peut donc pas retomber sur le compte, et c'est dit ici plutôt que subi.
        </p>
      )}
      {r.memes_fenetres === false && r.fenetres?.length > 1 && (
        <p className="text-muted2">
          ⚠ Les poches n'ont pas la même fenêtre : {r.fenetres.map((f: any) =>
            `${f.compte} ${f.debut}→${f.fin}`).join(" · ")}. La somme porte donc sur des périodes
          différentes — une part de l'écart vient de là.
        </p>
      )}
    </section>
  );
}
