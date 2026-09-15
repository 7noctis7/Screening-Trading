// Réglages de l'intro. TOUT ce qui se change sans lire le code est ici.
//
// Le fond, les accents et les couleurs de risque ne sont PAS définis ici : ils sont lus à
// l'exécution depuis les variables CSS du design system (`globals.css`). L'intro suit donc
// la charte ET le thème courant — y compris si l'utilisateur bascule en clair — au lieu de
// figer un noir qui jurerait avec `--bg:#0a1118`.

/** Durée totale, en ms. En dessous de ~2200 les phases deviennent illisibles. */
export const INTRO_DURATION = 3900;

/** Idem sur petit écran : plus court, parce qu'on y revient plus souvent. */
export const INTRO_DURATION_MOBILE = 2900;

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

/** Bornes des phases, en fraction de `INTRO_DURATION`. Doivent rester croissantes. */
export const PHASES = {
  init: 0.13,      // point → ligne, carnet d'ordres qui s'amorce
  flow: 0.40,      // flux de marché : chandeliers vectoriels, profondeur, tape
  neural: 0.66,    // le flux devient graphe ; un signal le traverse, une probabilité sort
  risk: 0.86,      // enveloppe de risque : l'exposition se resserre, le DD se borne
  reveal: 1.0,     // convergence + nom de marque
} as const;

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
