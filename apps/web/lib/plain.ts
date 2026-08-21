// Traduction des métriques quantitatives en LANGAGE COURANT.
//
// Le terminal affichait « Sharpe 1,32 · maxDD −14,6 % · DSR 0,03 ». Ces nombres sont justes,
// mais ils ne disent rien à qui n'a pas fait de finance quantitative. Ce module donne, pour
// chaque métrique : un VERDICT (bon / moyen / prudence), une PHRASE en français simple, et
// quand c'est possible l'équivalent EN EUROS — la conversion qui rend un pourcentage concret.
//
// Règle : on n'invente aucun chiffre, on ne fait que reformuler celui qu'on reçoit. Une valeur
// absente reste absente (`null`), jamais remplacée par une valeur plausible.

export type Verdict = "bon" | "moyen" | "prudence" | "inconnu";

export const VERDICT_LABEL: Record<Verdict, string> = {
  bon: "Favorable",
  moyen: "Correct",
  prudence: "Vigilance",
  inconnu: "Non mesuré",
};

/** Capital de référence par défaut pour les conversions en euros (montant rond, lisible). */
export const CAPITAL_REF = 10_000;

/** Convertit un pourcentage (0,146 = 14,6 %) en montant sur un capital de référence. */
export function euros(fraction: number | null | undefined, capital = CAPITAL_REF): string | null {
  if (fraction == null || !Number.isFinite(fraction)) return null;
  const v = Math.round(Math.abs(fraction) * capital);
  return `${v.toLocaleString("fr-FR")} €`;
}

export type Explication = { verdict: Verdict; phrase: string; euros?: string | null };

const INCONNU = (quoi: string): Explication => ({
  verdict: "inconnu",
  phrase: `${quoi} n'est pas mesuré pour l'instant.`,
});

/** Sharpe : rapport entre le gain et les secousses subies pour l'obtenir. */
export function expliqueSharpe(v: number | null | undefined): Explication {
  if (v == null || !Number.isFinite(v)) return INCONNU("Le rapport gain / risque");
  if (v >= 1.5) return { verdict: "bon", phrase: "Très bon rapport entre le gain obtenu et les secousses traversées." };
  if (v >= 0.8) return { verdict: "bon", phrase: "Bon rapport entre le gain obtenu et les secousses traversées." };
  if (v >= 0.3) return { verdict: "moyen", phrase: "Le gain compense à peine les secousses traversées." };
  return { verdict: "prudence", phrase: "Les secousses ne sont pas payées par le gain sur cette période." };
}

/** Drawdown : la pire chute depuis un sommet — la question que tout le monde se pose vraiment. */
export function expliqueDrawdown(v: number | null | undefined, capital = CAPITAL_REF): Explication {
  if (v == null || !Number.isFinite(v)) return INCONNU("La pire baisse");
  const p = Math.abs(v);
  const montant = euros(p, capital);
  const phrase = `Pire baisse traversée depuis un sommet : ${(p * 100).toFixed(1)} %. `
    + `Sur ${capital.toLocaleString("fr-FR")} €, cela veut dire voir ${montant} partir avant que ça remonte.`;
  if (p <= 0.10) return { verdict: "bon", phrase, euros: montant };
  if (p <= 0.25) return { verdict: "moyen", phrase, euros: montant };
  return { verdict: "prudence", phrase, euros: montant };
}

/** Volatilité annuelle : l'amplitude habituelle des variations. */
export function expliqueVolatilite(v: number | null | undefined, capital = CAPITAL_REF): Explication {
  if (v == null || !Number.isFinite(v)) return INCONNU("L'agitation");
  const montant = euros(v, capital);
  const phrase = `Une année ordinaire fait bouger la valeur d'environ ${(v * 100).toFixed(0)} % `
    + `dans un sens ou dans l'autre, soit à peu près ${montant} sur ${capital.toLocaleString("fr-FR")} €.`;
  if (v <= 0.15) return { verdict: "bon", phrase, euros: montant };
  if (v <= 0.30) return { verdict: "moyen", phrase, euros: montant };
  return { verdict: "prudence", phrase, euros: montant };
}

/** DSR : la probabilité que le résultat ne soit pas dû à la chance. */
export function expliqueDSR(v: number | null | undefined): Explication {
  if (v == null || !Number.isFinite(v)) return INCONNU("La solidité du résultat");
  const pct = Math.round(v * 100);
  if (v >= 0.95) return { verdict: "bon", phrase: `${pct} % de chances que ce résultat ne soit pas un coup de chance.` };
  if (v >= 0.5) return { verdict: "moyen", phrase: `${pct} % de chances que ce résultat ne soit pas un coup de chance : encourageant, pas prouvé.` };
  return { verdict: "prudence", phrase: `Seulement ${pct} % de chances que ce résultat ne soit pas un simple coup de chance. On ne s'appuie pas dessus.` };
}

/** Taux de réussite : part des opérations gagnantes. */
export function expliqueTauxReussite(v: number | null | undefined): Explication {
  if (v == null || !Number.isFinite(v)) return INCONNU("Le taux de réussite");
  const pct = Math.round(v * 100);
  const phrase = `${pct} opérations sur 100 se terminent en gain. `
    + "Un taux bas n'est pas un problème si les gains sont plus gros que les pertes.";
  if (v >= 0.55) return { verdict: "bon", phrase };
  if (v >= 0.40) return { verdict: "moyen", phrase };
  return { verdict: "prudence", phrase };
}

/** Rotation : à quelle fréquence le portefeuille est remplacé (donc les frais payés). */
export function expliqueRotation(v: number | null | undefined): Explication {
  if (v == null || !Number.isFinite(v)) return INCONNU("La rotation");
  const phrase = `Le portefeuille est renouvelé environ ${v.toFixed(1)} fois par an. `
    + "Plus il tourne, plus les frais et l'écart de prix grignotent le résultat.";
  if (v <= 3) return { verdict: "bon", phrase };
  if (v <= 8) return { verdict: "moyen", phrase };
  return { verdict: "prudence", phrase };
}

/** Perte moyenne dans les pires 5 % des cas (CVaR / Expected Shortfall). */
export function expliquePerteExtreme(v: number | null | undefined, capital = CAPITAL_REF): Explication {
  if (v == null || !Number.isFinite(v)) return INCONNU("La perte des mauvais jours");
  const p = Math.abs(v);
  const montant = euros(p, capital);
  return {
    verdict: p <= 0.02 ? "bon" : p <= 0.05 ? "moyen" : "prudence",
    euros: montant,
    phrase: `Lors des 5 % de journées les plus mauvaises, la perte moyenne est de ${(p * 100).toFixed(1)} %, `
      + `soit environ ${montant} sur ${capital.toLocaleString("fr-FR")} €.`,
  };
}

/** Formate un pourcentage de façon lisible, avec le signe. */
export function pct(v: number | null | undefined, decimales = 1): string {
  if (v == null || !Number.isFinite(v)) return "—";
  const s = (v * 100).toFixed(decimales).replace(".", ",");
  return `${v > 0 ? "+" : ""}${s} %`;
}
