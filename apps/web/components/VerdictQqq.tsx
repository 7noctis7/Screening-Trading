"use client";

/** Le premier chiffre du dashboard : face à QQQ, pas le gain brut. */
export function VerdictQqq({ attribution }: { attribution?: any }) {
  const at = attribution;
  if (!at?.available) {
    return (
      <p className="card p-3 text-sm">
        Face à QQQ : <b>non mesuré sur cette vue</b>. Tant qu'un écart n'est pas
        distingué du hasard, le gain plus bas n'est pas un savoir-faire.
      </p>
    );
  }
  const net = at.alpha_significant === true && !at.underperforms_benchmark;
  return (
    <p className="card p-3 text-sm" style={{ borderColor: "var(--warn)" }}>
      Face à QQQ : {net
        ? "l'écart mesuré est significatif — à relire avec le nombre d'essais, pas à prendre pour un alpha."
        : "l'apport propre n'est pas établi. Ce qui suit est surtout le marché."}
      {at.alpha_significant === false && at.alpha_tstat != null ? ` (t = ${at.alpha_tstat}.)` : ""}
      {" "}Les frais de cette simulation sont un modèle, pas un relevé de courtier.
    </p>
  );
}
