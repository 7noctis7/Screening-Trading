// Réglages de l'intro. TOUT ce qui se change sans lire le code est ici.
//
// Les couleurs ne sont PAS ici : elles sont lues à l'exécution depuis les variables CSS du
// design system. L'intro suit donc la charte ET le thème courant, au lieu de figer un noir
// qui jurerait avec `--bg:#0a1118`.

/** Durée totale, en ms. En dessous de ~8 s, le troisième battement devient illisible. */
export const INTRO_DURATION = 18_000;

/** Idem sur petit écran. Un peu plus court : on y revient plus souvent. */
export const INTRO_DURATION_MOBILE = 15_000;

/** Particules de fond. Réduit automatiquement sur mobile / machine modeste. */
export const PARTICLE_COUNT = 340;
export const PARTICLE_COUNT_MOBILE = 110;

/** Nœuds du graphe. Décor du premier battement, jamais le sujet. */
export const NODE_COUNT = 30;
export const NODE_COUNT_MOBILE = 16;

/** `false` désactive l'intro partout, sans toucher au reste. */
export const ENABLE_INTRO = true;

/**
 * Quand la rejouer.
 *   "session" — une fois par onglet (défaut)
 *   "day"     — une fois par 24 h
 *   "always"  — à chaque chargement (pour la régler)
 *   "never"   — jamais
 */
// L'accueil est une destination explicite, pas une modale injectée dans les pages de travail :
// y revenir signifie demander à revoir le rideau. `session` le faisait disparaître après le
// premier passage de l'onglet et donnait l'impression d'une régression après déploiement.
export const INTRO_SESSION_POLICY: "session" | "day" | "always" | "never" = "always";

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
  { cle: "echelle", fin: 0.12, genre: "chiffre",
    sur: "CE QUE LA MACHINE REGARDE", fenetre: null },
  { cle: "rejet", fin: 0.22, genre: "chiffre",
    sur: "CE QU'ELLE A REJETÉ", fenetre: null },
  { cle: "p_ytd", fin: 0.33, genre: "periode", sur: "", fenetre: "ytd" },
  { cle: "p_3a", fin: 0.44, genre: "periode", sur: "", fenetre: "3a" },
  { cle: "p_5a", fin: 0.55, genre: "periode", sur: "", fenetre: "5a" },
  { cle: "p_10a", fin: 0.66, genre: "periode", sur: "", fenetre: "10a" },
  { cle: "p_tout", fin: 0.77, genre: "periode", sur: "", fenetre: "tout" },
  { cle: "trades", fin: 0.88, genre: "trades",
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

/** Repli quand `/api/intro` est indisponible : on n'affiche RIEN plutôt qu'un chiffre
 *  inventé. Les battements `periode` se sautent d'eux-mêmes, l'intro raccourcit. */
export const SANS_DONNEES_SAUTE_PERIODES = true;

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
