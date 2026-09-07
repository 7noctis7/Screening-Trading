import { PortfolioSnapshot } from "@/lib/portfolio-import";

export type ScenarioKind = "prudent" | "neutre" | "dynamique" | "conviction";
// D'où vient l'univers : les lignes que l'utilisateur DÉTIENT, ou la sélection que le
// screening du jour propose. Deux questions différentes — « comment mieux répartir ce que
// j'ai » et « que devrais-je détenir » — donc deux règles de validation différentes.
export type ScenarioSource = "portefeuille" | "recommandation";
export type ScenarioResult = {
  kind: ScenarioKind; label: string; method: string; weights: { symbol: string; current: number; proposed: number; delta: number }[];
  turnover: number; estimatedCost: number | null; breaches: number; averageCapEffect: number;
  available: boolean; reason?: string;
};

const LABELS: Record<ScenarioKind, [string, string]> = {
  prudent: ["Prudent", "Minimum variance robuste sur l'univers disponible"],
  neutre: ["Neutre", "Equal Risk Contribution, budgets de risque équilibrés"],
  // Le backend calcule un HRP (hiérarchie de risque sur la covariance). Annoncer
  // « Black-Litterman » promettait des rendements attendus (μ) que rien ne calibre :
  // un nom que le calcul n'aurait jamais honoré. On nomme ce qui est calculé.
  dynamique: ["Dynamique", "Hierarchical Risk Parity — grappes de corrélation, sans rendement attendu"],
  // Le SEUL profil qui utilise un rendement attendu. Il n'apparaît que si l'IC du score a
  // été mesuré ET tient hors échantillon ; l'amplitude des vues vaut IC × σ × z (Grinold),
  // donc un IC faible ramène mécaniquement le résultat sur le prior ERC.
  conviction: ["Conviction", "Black-Litterman — vues calibrées par l'IC MESURÉ du score"],
};

const norm = (value: string) => value.toUpperCase().replace(/[-/]/g, "");
// Libellé de la ligne de trésorerie. Nommé une fois : le turnover DOIT pouvoir l'exclure,
// et une chaîne recopiée à deux endroits finit par diverger de son test.
export const LIQUIDITES = "Liquidités";

function capWeights(raw: number[], cap: number): { weights: number[]; triggers: number; averageEffect: number } | null {
  if (raw.length * cap < 1 - 1e-9) return null;
  const base = raw.map((value) => Math.max(0, Number(value) || 0));
  const weights = Array(base.length).fill(0); const active = new Set(base.map((_, index) => index));
  let remaining = 1;
  while (active.size) {
    const total = [...active].reduce((sum, index) => sum + base[index], 0);
    const fallback = remaining / active.size;
    const capped = [...active].filter((index) => (total > 0 ? remaining * base[index] / total : fallback) > cap + 1e-9);
    if (!capped.length) { for (const index of active) weights[index] = total > 0 ? remaining * base[index] / total : fallback; break; }
    for (const index of capped) { weights[index] = cap; active.delete(index); remaining -= cap; }
  }
  const effects = weights.map((value, index) => Math.abs(value - base[index]));
  const triggers = base.filter((value) => value > cap + 1e-9).length;
  return { weights, triggers, averageEffect: triggers ? effects.reduce((sum, value) => sum + value, 0) / effects.length : 0 };
}

export function buildScenario(snapshot: PortfolioSnapshot, optimal: any, kind: ScenarioKind,
  portfolioValue: number | null, costBps: number, maxWeight: number,
  source: ScenarioSource = "portefeuille", precontraint?: any): ScenarioResult {
  const [label, method] = LABELS[kind];
  const imported = new Map(snapshot.positions.map((position) =>
    [norm(position.ticker), { ticker: position.ticker, weight: (position.weight ?? 0) / 100 }]));
  const poidsActuel = (symbol: string) => imported.get(norm(symbol))?.weight ?? 0;
  const keys: Record<ScenarioKind, string> = { prudent: "min_variance", neutre: "risk_parity", dynamique: "hrp", conviction: "conviction" };
  const proposed = optimal?.[keys[kind]]; const symbols: string[] = optimal?.symbols ?? [];
  const exact = symbols.length === imported.size && symbols.every((item) => imported.has(norm(item)));
  const vide = { kind, label, method, weights: [], turnover: 0, estimatedCost: null, breaches: 0, averageCapEffect: 0, available: false };
  // TROIS causes distinctes, TROIS messages. L'ancien code les fondait toutes dans
  // « Historique/covariance indisponible », qui accusait la donnée même quand elle
  // était parfaitement chargée et que seule une clé manquait (06/09).
  if (!symbols.length) return { ...vide, reason: "Aucune allocation calculée : l'analyse de l'univers n'a rien renvoyé." };
  // En mode recommandation l'univers DIFFÈRE par construction : exiger qu'il coïncide
  // interdirait la seule chose que cette carte apporte — proposer des actifs non détenus.
  if (source === "portefeuille" && !exact)
    return { ...vide, reason: `Univers calculé (${symbols.length} actifs) différent de l'univers importé (${imported.size}).` };
  if (!Array.isArray(proposed) || proposed.length !== symbols.length)
    return { ...vide, reason: `Scénario « ${label} » non renvoyé par le calcul (clé « ${keys[kind]} » absente).` };
  // Plus de verrou ML sur « dynamique » : le HRP se calcule sur la seule covariance,
  // il n'a besoin d'aucun rendement attendu. Le verrou protégeait un Black-Litterman
  // qui n'a jamais été calculé ici.
  // En mode recommandation, le plafond ET l'exposition ont été appliqués côté serveur, là où
  // vit la covariance : replafonner ici renormaliserait la somme à 1 et effacerait les
  // liquidités que le budget de perte impose. On prend les poids tels qu'ils arrivent.
  const constrained = source === "recommandation"
    ? { weights: proposed as number[], triggers: precontraint?.plafonds_actives ?? 0,
        averageEffect: precontraint?.effet_moyen_plafond ?? 0 }
    : capWeights(proposed, maxWeight);
  if (!constrained) return { kind, label, method, weights: [], turnover: 0, estimatedCost: null, breaches: 0, averageCapEffect: 0, available: false, reason: `Contrainte infaisable : ${symbols.length} actifs × ${(maxWeight * 100).toFixed(1)}% < 100%.` };
  const weights = symbols.map((item, index) => ({ symbol: item, current: poidsActuel(item),
    proposed: constrained.weights[index], delta: constrained.weights[index] - poidsActuel(item) }));
  // Les lignes DÉTENUES et absentes de la sélection sortent à 0 %. Les omettre sous-estimerait
  // le turnover et, surtout, cacherait la moitié de la décision : ce qu'il faut vendre.
  if (source === "recommandation") {
    // Les liquidités sont une LIGNE, pas un reste implicite. Le budget de perte déclaré peut
    // laisser 30 % hors du marché : afficher un tableau qui somme à 70 % sans le dire se
    // lirait comme une erreur d'arrondi plutôt que comme la contrainte qu'on a demandée.
    const cash = Number(precontraint?.cash ?? 0);
    if (cash > 1e-6)
      weights.push({ symbol: LIQUIDITES, current: 0, proposed: cash, delta: cash });
    const retenus = new Set(symbols.map(norm));
    for (const [cle, position] of imported)
      if (!retenus.has(cle) && position.weight > 0)
        weights.push({ symbol: position.ticker, current: position.weight, proposed: 0, delta: -position.weight });
  }
  // LES LIQUIDITÉS NE SE NÉGOCIENT PAS. Ajouter la ligne cash au tableau — pour rendre
  // visible l'exposition réduite par le profil — l'a fait compter comme un ACHAT : le
  // turnover ressortait à 100 % sur les trois profils alors qu'ils investissent de 37 % à
  // 81 %, et le coût estimé était surévalué d'autant (07/09). Le cash est ce qui RESTE
  // après les ventes, pas un instrument qu'on acquiert.
  const negociees = weights.filter((row) => row.symbol !== LIQUIDITES);
  const turnover = negociees.reduce((sum, row) => sum + Math.abs(row.delta), 0) / 2;
  return { kind, label, method, weights, turnover, estimatedCost: portfolioValue == null ? null : portfolioValue * turnover * costBps / 10_000,
    breaches: constrained.triggers, averageCapEffect: constrained.averageEffect, available: true };
}
