// Réglages de l'intro. TOUT ce qui se change sans lire le code est ici.
//
// Les couleurs ne sont PAS ici : elles sont lues à l'exécution depuis les variables CSS du
// design system. L'intro suit donc la charte ET le thème courant, au lieu de figer un noir
// qui jurerait avec `--bg:#0a1118`.

/** Durée totale, en ms. En dessous de ~8 s, le troisième battement devient illisible. */
export const INTRO_DURATION = 10_000;

/** Idem sur petit écran. Un peu plus court : on y revient plus souvent. */
export const INTRO_DURATION_MOBILE = 8_500;

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
export const INTRO_SESSION_POLICY: "session" | "day" | "always" | "never" = "session";

export const INTRO_BRAND = "Quant Terminal";
export const INTRO_BASELINE = "0 € · OPEN SOURCE · PAPER PAR DÉFAUT";

/**
 * LES QUATRE BATTEMENTS. Bornes en fraction de `INTRO_DURATION`, croissantes, la dernière à 1.
 *
 * DIX SECONDES NE RACONTENT PAS UN PIPELINE — elles posent un argument. La version longue
 * déroulait les huit étages du produit ; celle-ci fait le contraire : elle retient QUATRE
 * chiffres, et chacun doit tenir debout seul.
 *
 * L'ordre est celui d'une démonstration, pas d'un flux de données :
 *   1. l'échelle    — ce que la machine regarde
 *   2. l'honnêteté  — ce qu'elle a REJETÉ (l'argument que personne d'autre ne fait)
 *   3. le résultat  — le drawdown comparé, seul chiffre qui parle d'argent
 *   4. la promesse  — gratuit, ouvert, sans ordre réel
 *
 * Le battement 2 est le plus important. Un site de trading qui affiche ses échecs déplace
 * la conversation : on ne vend plus une performance, on vend une méthode.
 */
export const BEATS = [
  {
    cle: "echelle", fin: 0.22,
    sur: "CE QUE LA MACHINE REGARDE",
    chiffre: "821", unite: "INSTRUMENTS",
    sous: "2,03 M de barres · actions · ETF · crypto · forex · commodités",
  },
  {
    cle: "rejet", fin: 0.48,
    sur: "CE QU'ELLE A REJETÉ",
    chiffre: "7 / 7", unite: "PISTES ÉCARTÉES",
    sous: "placebo · Sharpe déflaté · surajustement · sabotage — publiés, pas cachés",
  },
  {
    cle: "resultat", fin: 0.76,
    sur: "PERTE MAXIMALE",
    chiffre: "−9 %", unite: "CONTRE −23 % POUR LE MARCHÉ",
    sous: "le risque d'abord — la performance vient après, ou ne vient pas",
  },
  { cle: "reveal", fin: 1.0, sur: "", chiffre: "", unite: "", sous: "" },
] as const;

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
