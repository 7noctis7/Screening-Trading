// Réglages de l'intro. TOUT ce qui se change sans lire le code est ici.
//
// Le fond, les accents et les couleurs de risque ne sont PAS définis ici : ils sont lus à
// l'exécution depuis les variables CSS du design system (`globals.css`). L'intro suit donc
// la charte ET le thème courant — y compris si l'utilisateur bascule en clair — au lieu de
// figer un noir qui jurerait avec `--bg:#0a1118`.

/** Durée totale, en ms. En dessous de ~2200 les phases deviennent illisibles. */
export const INTRO_DURATION = 75_000;

/** Idem sur petit écran : plus court, parce qu'on y revient plus souvent. */
export const INTRO_DURATION_MOBILE = 60_000;

/** Particules de flux de marché. Réduit automatiquement sur mobile / machine modeste. */
export const PARTICLE_COUNT = 420;
export const PARTICLE_COUNT_MOBILE = 130;

/** Nœuds du graphe neuronal. Au-delà de ~40 la lecture se perd en bruit. */
export const NODE_COUNT = 34;
export const NODE_COUNT_MOBILE = 18;

/** `false` désactive l'intro partout, sans toucher au reste. */
export const ENABLE_INTRO = true;

/**
 * Quand la rejouer.
 *   "session" — une fois par onglet (défaut : impressionne sans jamais lasser)
 *   "day"     — une fois par 24 h
 *   "always"  — à chaque chargement (utile pour la régler)
 *   "never"   — jamais
 */
export const INTRO_SESSION_POLICY: "session" | "day" | "always" | "never" = "session";

/** Baseline sous le nom de marque. Chaîne vide = pas de baseline. */
export const INTRO_BASELINE = "SCREENING · RISQUE · EXÉCUTION";

/** Nom affiché. Repris du `<title>` du site pour rester cohérent. */
export const INTRO_BRAND = "Quant Terminal";

/**
 * LES HUIT ACTES. Bornes en fraction de `INTRO_DURATION`, croissantes, la dernière à 1.
 *
 * POURQUOI HUIT ET NON CINQ. Une séquence de 75 secondes ne s'obtient pas en ralentissant
 * une séquence de 4 : on verrait le ralenti. Il faut du CONTENU — ici, le pipeline réel du
 * produit, un acte par étage. Chacun dure ~9 s, ce qui laisse le temps de lire sans laisser
 * le temps de s'ennuyer.
 *
 * L'acte GATE est le cœur : il rejoue les quatre portes de la landing (placebo, DSR, PBO,
 * sabotage) — et il en montre une qui ÉCHOUE. C'est le seul moment de l'intro où le produit
 * dit quelque chose qu'un concurrent ne dirait pas.
 */
export const ACTS = [
  { cle: "init", fin: 0.07, titre: "INITIALISATION", sous: "chargement des couches" },
  { cle: "market", fin: 0.22, titre: "MARKET DATA", sous: "821 instruments · 2,03 M barres" },
  { cle: "features", fin: 0.33, titre: "FEATURE ENGINE", sous: "10 facteurs · point-in-time" },
  { cle: "ml", fin: 0.48, titre: "MACHINE LEARNING", sous: "CV purgée · embargo" },
  { cle: "gate", fin: 0.66, titre: "VALIDATION", sous: "placebo · DSR · PBO · sabotage" },
  { cle: "risk", fin: 0.80, titre: "RISK ENGINE", sous: "vol target · DD cap · exposition" },
  { cle: "exec", fin: 0.92, titre: "EXECUTION", sous: "portail d'ordres · paper" },
  { cle: "reveal", fin: 1.0, titre: "", sous: "" },
] as const;

export type ActeCle = (typeof ACTS)[number]["cle"];

/** Bornes nommées — sucre pour la scène, dérivé d'`ACTS` : une seule source de vérité. */
export const PHASES = Object.fromEntries(
  ACTS.map((a) => [a.cle, a.fin]),
) as Record<ActeCle, number>;

/** Les quatre portes, avec leur verdict RÉEL. Le DSR échoue : c'est la position du projet. */
export const GATES = [
  { cle: "PLACEBO", metrique: "p = 0,039", passe: true },
  { cle: "DSR", metrique: "DSR = 0,00", passe: false },
  { cle: "PBO", metrique: "PBO = 0,88", passe: false },
  { cle: "SABOTAGE", metrique: "rétention −11,7", passe: false },
] as const;

/** Les dix facteurs de l'acte FEATURE ENGINE. Ceux du modèle, pas des mots inventés. */
export const FACTEURS = [
  "MOMENTUM 1M", "MOMENTUM 3M", "TENDANCE MM50", "RSI", "VOLATILITÉ ATR",
  "MOM. AJUSTÉ RISQUE", "DIST. PLUS-HAUT 52S", "REVERSAL 5J", "PEAD", "RÉGIME DE VOL",
] as const;

/** Micro-étiquettes de la phase d'initialisation. Sobres, jamais « terminal hacker ». */
export const INIT_LABELS = [
  "MARKET DATA — 821 INSTRUMENTS",
  "FEATURE ENGINE — 10 FACTEURS",
  "ML MODEL — CV PURGÉE + EMBARGO",
  "RISK ENGINE — VOL TARGET · DD CAP",
  "EXECUTION — PAPER",
] as const;

/** Colonnes du carnet d'ordres esquissé en phase 2. Purement décoratif, jamais un prix réel. */
export const TAPE_ROWS = 14;

/** Métriques qui s'affichent en phase ML puis se stabilisent. Libellés seulement. */
export const ML_LABELS = ["AUC", "BRIER", "IC"] as const;

/** Étiquettes de la phase risque. Minuscules et secondaires, par construction. */
export const RISK_LABELS = ["GROSS EXPOSURE", "VOL TARGET", "MAX DRAWDOWN"] as const;

/** Courbe d'easing du projet — celle des transitions premium, sans rebond. */
export const EASE = "cubic-bezier(0.16, 1, 0.3, 1)";

/** Plafond de densité de pixels. Au-delà de 2, le coût GPU double sans gain visible. */
export const MAX_DPR = 2;
