// Réglages de l'intro. TOUT ce qui se change sans lire le code est ici.
//
// Les couleurs ne sont PAS ici : elles sont lues à l'exécution depuis les variables CSS du
// design system. L'intro suit donc la charte ET le thème courant, au lieu de figer un noir
// qui jurerait avec `--bg:#0a1118`.

/** Durée totale, en ms.
 *
 * 26 s, et la raison tient en une phrase : LIRE UNE COURBE PREND DU TEMPS. À 18 s, chaque
 * fenêtre de performance durait 2,0 s — dont 0,6 s de déformation depuis la fenêtre
 * précédente et 0,7 s de compteur qui monte. Il restait moins d'une seconde pour regarder
 * réellement le graphique, c'est-à-dire pas assez pour en tirer quoi que ce soit.
 *
 * Une intro qui montre une preuve trop vite pour qu'on la lise ne montre pas une preuve :
 * elle montre qu'elle en a une. C'est le contraire de l'intention.
 *
 * Chaque fenêtre dispose maintenant de 3,4 s — environ 2 s de lecture nette une fois la
 * transition passée — et les cinq fenêtres occupent 65 % de la séquence. Le reste a été
 * resserré plutôt qu'allongé : la révélation du nom perd 0,6 s, elle n'a rien à démontrer.
 */
export const INTRO_DURATION = 26_000;

/** Idem sur petit écran. Un peu plus court : on y revient plus souvent — mais PAS assez
 *  court pour retomber sous le seuil de lisibilité (2,9 s par fenêtre ici). */
export const INTRO_DURATION_MOBILE = 22_000;

/** Plancher de lisibilité d'un battement de période, en ms. En dessous, la courbe défile
 *  sans qu'on ait le temps de la lire — c'est le défaut corrigé le 16/09. Un test le
 *  vérifie sur les DEUX durées, mobile comprise. */
export const MIN_BATTEMENT_PERIODE_MS = 2_800;

/** Particules de fond. Réduit automatiquement sur mobile / machine modeste. */
export const PARTICLE_COUNT = 340;
export const PARTICLE_COUNT_MOBILE = 110;

/** Nœuds du graphe. Décor du premier battement, jamais le sujet. */
export const NODE_COUNT = 30;
export const NODE_COUNT_MOBILE = 16;

/** `false` désactive l'intro partout, sans toucher au reste. */
export const ENABLE_INTRO = true;

export type PolitiqueIntro = "session" | "day" | "always" | "never";

/**
 * Quand la rejouer.
 *   "session" — une fois par onglet
 *   "day"     — une fois par 24 h
 *   "always"  — à chaque chargement
 *   "never"   — jamais
 *
 * EN DÉVELOPPEMENT, C'EST TOUJOURS "always", ET CE N'EST PAS UN CONFORT. Avec "session",
 * l'intro ne rejoue qu'une fois par ONGLET : on recharge, rien ne se passe, et on conclut
 * que le correctif n'a pas pris. C'est la même famille de piège que le cache `.next` qui
 * ressert l'ancien rendu — le code est juste, l'écran montre autre chose, et RIEN ne le
 * signale. Le 16/09 elle a coûté une conversation entière.
 *
 * En production (`make site`, `next build`) la politique redevient "session" : un visiteur
 * qui recharge une page n'a pas à revoir le rideau d'entrée.
 */
export const INTRO_SESSION_POLICY: PolitiqueIntro =
  process.env.NODE_ENV === "production" ? "session" : "always";

export const INTRO_BRAND = "Quant Terminal";
export const INTRO_BASELINE = "0 € · OPEN SOURCE · PAPER PAR DÉFAUT";

/**
 * LES NEUF BATTEMENTS. Bornes en fraction de `INTRO_DURATION`, croissantes, la dernière à 1.
 *
 * DEUX AFFIRMATIONS, CINQ PREUVES, UN BILAN. Les deux premiers battements posent ce que la
 * machine regarde et ce qu'elle a rejeté ; les cinq suivants MONTRENT — une fenêtre chacun,
 * courbe contre référence ; le huitième donne la qualité des trades ; le dernier le nom.
 *
 * Aucun chiffre n'est écrit ici. Les battements `periode` et `trades` lisent `/api/intro`,
 * régénéré à chaque construction du snapshot — donc chaque jour ouvré. Un nombre saisi dans
 * un composant se détache de ce qu'il mesure, et d'autant plus vite qu'il flatte.
 */
export const BEATS = [
  // Bornes calculées pour 26 s : 2,6 · 2,2 · 3,4 × 5 · 2,6 · 1,6 secondes.
  { cle: "echelle", fin: 0.100, genre: "chiffre",
    sur: "CE QUE LA MACHINE REGARDE", fenetre: null },
  { cle: "rejet", fin: 0.185, genre: "chiffre",
    sur: "CE QU'ELLE A REJETÉ", fenetre: null },
  { cle: "p_ytd", fin: 0.315, genre: "periode", sur: "", fenetre: "ytd" },
  { cle: "p_3a", fin: 0.446, genre: "periode", sur: "", fenetre: "3a" },
  { cle: "p_5a", fin: 0.577, genre: "periode", sur: "", fenetre: "5a" },
  { cle: "p_10a", fin: 0.708, genre: "periode", sur: "", fenetre: "10a" },
  { cle: "p_tout", fin: 0.838, genre: "periode", sur: "", fenetre: "tout" },
  { cle: "trades", fin: 0.938, genre: "trades",
    sur: "QUALITÉ DES TRADES", fenetre: null },
  { cle: "reveal", fin: 1.0, genre: "reveal", sur: "", fenetre: null },
] as const;

/** Les deux chiffres qui ne viennent PAS de l'API : ils décrivent le dispositif, pas la
 *  performance. `929` est la taille des seeds, vérifiable par `make audit`. */
export const CHIFFRES_FIXES: Record<string, {
  chiffre: string; unite: string; sous: string;
  /** Valeur NUMÉRIQUE quand le chiffre peut être compté de zéro. « 7 / 7 » n'en a pas :
   *  un compteur qui monte vers une fraction afficherait des états qui n'existent pas. */
  valeur?: number;
}> = {
  echelle: {
    chiffre: "929", valeur: 929, unite: "INSTRUMENTS",
    sous: "757 actions · 111 ETF · 108 crypto · 20 forex · 20 commodités · 20 indices",
  },
  rejet: {
    chiffre: "7 / 7", unite: "PISTES ÉCARTÉES",
    sous: "placebo · Sharpe déflaté · surajustement · sabotage — publiés, pas cachés",
  },
};

export type BeatCle = (typeof BEATS)[number]["cle"];

/** Bornes nommées, dérivées de `BEATS` : une seule source de vérité. */
export const PHASES = Object.fromEntries(
  BEATS.map((b) => [b.cle, b.fin]),
) as Record<BeatCle, number>;

/** Les quatre portes, avec leur verdict RÉEL. Une seule passe. */
export const GATES = [
  { cle: "PLACEBO", metrique: "p 0,039", passe: true },
  { cle: "DSR", metrique: "0,00", passe: false },
  { cle: "PBO", metrique: "0,88", passe: false },
  { cle: "SABOTAGE", metrique: "−11,7", passe: false },
] as const;

/** Courbe d'easing du projet — premium, sans rebond. */
export const EASE = "cubic-bezier(0.16, 1, 0.3, 1)";

/** Plafond de densité de pixels. Au-delà de 2, le coût GPU double sans gain visible. */
export const MAX_DPR = 2;
