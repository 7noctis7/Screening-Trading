// CHAÎNE DÉCISIONNELLE — relier toutes les données d'un titre jusqu'à l'ordre.
//
// Le site savait déjà TOUT sur un titre (score, facteurs, fondamentaux, sentiment, position,
// cible) mais s'arrêtait avant la seule chose qui intéresse l'utilisateur : « et donc, j'achète
// ou pas, pour combien ? ». Ce module fait le dernier pas, et RIEN de plus : il ne calcule aucun
// chiffre neuf, il assemble ceux qui existent en un verdict traçable.
//
// Trois règles non négociables :
//  1. Aucune donnée inventée. Un étage sans donnée est déclaré MANQUANT et ne vote pas ; il
//     n'est jamais remplacé par une valeur neutre plausible (ce qui reviendrait à voter).
//  2. Véto de solvabilité. Un critère graduel manqué (cherté, momentum) peut être compensé par
//     la note d'ensemble ; un risque de RUINE ne se compense jamais. Même logique côté Python
//     (`packages/screening/decision_journal.py`) : on compense de la performance, jamais la
//     solvabilité.
//  3. Confiance décroissante avec l'ignorance. Moins il y a d'étages mesurés, plus le verdict
//     est prudent — trois étages sur six ne donnent pas droit à un « achat » ferme.

import type { Verdict } from "./plain";

/** Un étage de l'entonnoir : ce qu'il mesure, ce qu'il a vu, comment il vote. */
export type Etage = {
  cle: string;
  titre: string;
  /** Ce que l'étage vérifie, en français, sans jargon. */
  question: string;
  /** Valeur observée, déjà formatée. `null` = non mesuré. */
  valeur: string | null;
  /** Vote : +1 favorable, 0 neutre, −1 défavorable, `null` si non mesuré. */
  vote: 1 | 0 | -1 | null;
  /** Phrase de lecture. */
  lecture: string;
  /** Véto : un vote défavorable ici bloque, quelle que soit la note d'ensemble. */
  veto?: boolean;
};

export type Ordre = {
  /** "acheter" | "alleger" | "conserver" | "aucune" */
  sens: "acheter" | "alleger" | "conserver" | "aucune";
  /** Écart entre la cible et la détention actuelle, en points de pourcentage du portefeuille. */
  ecartPts: number | null;
  /** Montant correspondant, si la valeur du portefeuille est connue. */
  montant: string | null;
  phrase: string;
};

export type Decision = {
  verdict: Verdict;
  titre: string;
  resume: string;
  etages: Etage[];
  /** Nombre d'étages réellement mesurés (les autres ne votent pas). */
  mesures: number;
  favorables: number;
  bloque: boolean;
  ordre: Ordre;
};

const pctTxt = (x?: number | null, signe = false) =>
  x == null || !Number.isFinite(x) ? null : `${signe && x >= 0 ? "+" : ""}${(x * 100).toFixed(1)} %`;

const eurTxt = (x: number) => `${Math.round(Math.abs(x)).toLocaleString("fr-FR")} €`;

/** Piotroski (0-9) : nombre de signaux comptables sains sur neuf. */
function etageQualite(piotroski?: number | null): Etage {
  const base = { cle: "qualite", titre: "Qualité de l'entreprise",
    question: "Ses comptes s'améliorent-ils ? (9 vérifications comptables)" };
  if (piotroski == null || !Number.isFinite(piotroski))
    return { ...base, valeur: null, vote: null, lecture: "Comptes non analysés pour cet actif." };
  const v = `${piotroski} / 9`;
  if (piotroski >= 7) return { ...base, valeur: v, vote: 1, lecture: "Comptes solides et en amélioration." };
  if (piotroski >= 5) return { ...base, valeur: v, vote: 0, lecture: "Comptes corrects, sans plus." };
  return { ...base, valeur: v, vote: -1, lecture: "Trop de signaux comptables dégradés." };
}

/** Altman Z : distance à la faillite. Seuils d'origine 1,81 / 2,99. VÉTO. */
function etageSolvabilite(z?: number | null): Etage {
  const base = { cle: "solvabilite", titre: "Solidité financière",
    question: "L'entreprise risque-t-elle de faire faillite ?", veto: true };
  if (z == null || !Number.isFinite(z))
    return { ...base, valeur: null, vote: null, lecture: "Solidité non mesurée pour cet actif." };
  const v = z.toFixed(2);
  if (z >= 2.99) return { ...base, valeur: v, vote: 1, lecture: "Aucun signe de détresse financière." };
  if (z >= 1.81) return { ...base, valeur: v, vote: 0, lecture: "Zone grise : à surveiller, sans alarme." };
  return { ...base, valeur: v, vote: -1, lecture: "Zone de détresse financière — critère bloquant." };
}

/** Marge de sécurité DCF : écart entre valeur estimée et prix payé. */
function etageValorisation(mos?: number | null): Etage {
  const base = { cle: "valorisation", titre: "Prix payé",
    question: "Le titre s'achète-t-il en dessous de ce qu'il vaut ?" };
  if (mos == null || !Number.isFinite(mos))
    return { ...base, valeur: null, vote: null, lecture: "Valeur estimée indisponible (pas de flux de trésorerie exploitables)." };
  const v = pctTxt(mos, true);
  if (mos >= 0.20) return { ...base, valeur: v, vote: 1, lecture: "Décote confortable par rapport à la valeur estimée." };
  if (mos >= 0) return { ...base, valeur: v, vote: 0, lecture: "Prix proche de la valeur estimée : rien de bradé." };
  return { ...base, valeur: v, vote: -1, lecture: "Le prix dépasse la valeur estimée." };
}

/** Momentum 12 mois : la tendance longue, le facteur le plus documenté. */
function etageMomentum(ret12m?: number | null): Etage {
  const base = { cle: "momentum", titre: "Tendance",
    question: "Le titre monte-t-il depuis un an ?" };
  if (ret12m == null || !Number.isFinite(ret12m))
    return { ...base, valeur: null, vote: null, lecture: "Historique insuffisant pour juger la tendance." };
  const v = pctTxt(ret12m, true);
  if (ret12m >= 0.10) return { ...base, valeur: v, vote: 1, lecture: "Tendance haussière installée." };
  if (ret12m >= -0.05) return { ...base, valeur: v, vote: 0, lecture: "Sur place depuis un an." };
  return { ...base, valeur: v, vote: -1, lecture: "Tendance baissière sur un an." };
}

/** Conviction : fusion trend + modèle + fondamental + sentiment (déjà calculée côté moteur). */
function etageSignal(conv?: number | null): Etage {
  const base = { cle: "signal", titre: "Signal d'ensemble",
    question: "Que dit la combinaison de tous les signaux ?" };
  if (conv == null || !Number.isFinite(conv))
    return { ...base, valeur: null, vote: null, lecture: "Ce titre n'est pas couvert par le moteur de conviction." };
  const v = conv.toFixed(2);
  if (conv >= 0.30) return { ...base, valeur: v, vote: 1, lecture: "Les signaux convergent dans le sens acheteur." };
  if (conv > -0.30) return { ...base, valeur: v, vote: 0, lecture: "Les signaux se contredisent : pas de direction nette." };
  return { ...base, valeur: v, vote: -1, lecture: "Les signaux convergent contre ce titre." };
}

/** Actualité : le sentiment ne décide pas, il alerte. */
function etageActualite(score?: number | null): Etage {
  const base = { cle: "actualite", titre: "Actualité",
    question: "Les nouvelles récentes sont-elles bonnes ou mauvaises ?" };
  if (score == null || !Number.isFinite(score))
    return { ...base, valeur: null, vote: null, lecture: "Pas de nouvelle récente exploitable." };
  const v = score.toFixed(2);
  if (score >= 0.15) return { ...base, valeur: v, vote: 1, lecture: "Nouvelles récentes plutôt bonnes." };
  if (score > -0.15) return { ...base, valeur: v, vote: 0, lecture: "Nouvelles récentes sans couleur nette." };
  return { ...base, valeur: v, vote: -1, lecture: "Nouvelles récentes défavorables." };
}

/** Bande de non-action : sous ce seuil, l'écart ne paie pas les frais du va-et-vient. */
export const BANDE_PTS = 1.0;

function ordreDepuisEcart(cible: number | null, actuel: number | null, valeurPtf: number | null): Ordre {
  if (cible == null && actuel == null)
    return { sens: "aucune", ecartPts: null, montant: null,
      phrase: "Ce titre n'est ni détenu ni visé par le portefeuille modèle." };
  const c = cible ?? 0, a = actuel ?? 0;
  const ecartPts = (c - a) * 100;
  const montant = valeurPtf != null && Number.isFinite(valeurPtf) ? eurTxt((c - a) * valeurPtf) : null;
  if (Math.abs(ecartPts) < BANDE_PTS)
    return { sens: "conserver", ecartPts, montant,
      phrase: `Détention déjà conforme à la cible (écart ${Math.abs(ecartPts).toFixed(1)} pt, sous la bande de ${BANDE_PTS} pt). Ne rien faire : le va-et-vient coûterait plus qu'il ne rapporte.` };
  if (ecartPts > 0)
    return { sens: "acheter", ecartPts, montant,
      phrase: `Sous-pondéré de ${ecartPts.toFixed(1)} pt par rapport à la cible${montant ? ` — soit ${montant} à acheter` : ""}.` };
  return { sens: "alleger", ecartPts, montant,
    phrase: `Sur-pondéré de ${Math.abs(ecartPts).toFixed(1)} pt par rapport à la cible${montant ? ` — soit ${montant} à alléger` : ""}.` };
}

export type EntreeDecision = {
  piotroski?: number | null;
  altmanZ?: number | null;
  margeSecurite?: number | null;
  ret12m?: number | null;
  conviction?: number | null;
  sentiment?: number | null;
  /** Poids cible du portefeuille modèle (0,05 = 5 %). */
  poidsCible?: number | null;
  /** Poids réellement détenu aujourd'hui. */
  poidsActuel?: number | null;
  /** Valeur du portefeuille, pour convertir l'écart en euros. */
  valeurPortefeuille?: number | null;
};

/**
 * Assemble les étages en une décision. Le verdict tient compte de l'IGNORANCE :
 * la part de favorables est calculée sur les étages MESURÉS, mais un verdict « favorable »
 * exige au moins quatre étages mesurés — sinon on plafonne à « correct ».
 */
export function decide(e: EntreeDecision): Decision {
  const etages: Etage[] = [
    etageQualite(e.piotroski),
    etageSolvabilite(e.altmanZ),
    etageValorisation(e.margeSecurite),
    etageMomentum(e.ret12m),
    etageSignal(e.conviction),
    etageActualite(e.sentiment),
  ];
  const mesuresArr = etages.filter((x) => x.vote != null);
  const mesures = mesuresArr.length;
  const favorables = mesuresArr.filter((x) => x.vote === 1).length;
  const defavorables = mesuresArr.filter((x) => x.vote === -1).length;
  const bloque = etages.some((x) => x.veto && x.vote === -1);
  const ordre = ordreDepuisEcart(e.poidsCible ?? null, e.poidsActuel ?? null, e.valeurPortefeuille ?? null);

  if (bloque)
    return { verdict: "prudence", titre: "Écarté", bloque, mesures, favorables, etages,
      resume: "Un critère bloquant est touché : la solidité financière. Une bonne note ailleurs ne rachète pas un risque de faillite — ce titre reste hors du portefeuille.",
      ordre: { ...ordre, sens: ordre.sens === "acheter" ? "aucune" : ordre.sens,
        phrase: ordre.sens === "acheter" ? "Aucun achat malgré l'écart à la cible : le critère bloquant prime." : ordre.phrase } };

  if (mesures === 0)
    return { verdict: "inconnu", titre: "Pas assez de données", bloque, mesures, favorables, etages,
      resume: "Aucun des six étages n'est mesurable pour cet actif. Le site ne devine pas : sans donnée, il n'y a pas de décision.", ordre };

  const part = favorables / mesures;
  if (part >= 0.6 && defavorables === 0 && mesures >= 4)
    return { verdict: "bon", titre: "Favorable", bloque, mesures, favorables, etages,
      resume: `${favorables} étages favorables sur ${mesures} mesurés, aucun défavorable. Le dossier tient sur plusieurs jambes indépendantes, pas sur une seule.`, ordre };
  if (defavorables > favorables)
    return { verdict: "prudence", titre: "Défavorable", bloque, mesures, favorables, etages,
      resume: `${defavorables} étages défavorables contre ${favorables} favorables (sur ${mesures} mesurés). Le dossier penche du mauvais côté.`, ordre };
  return { verdict: "moyen", titre: "Dossier moyen", bloque, mesures, favorables, etages,
    resume: mesures < 4
      ? `Seuls ${mesures} étages sur six sont mesurés : trop peu pour trancher franchement, quel que soit leur contenu.`
      : `${favorables} favorables, ${defavorables} défavorables sur ${mesures} mesurés. Rien de rédhibitoire, rien d'enthousiasmant.`,
    ordre };
}
