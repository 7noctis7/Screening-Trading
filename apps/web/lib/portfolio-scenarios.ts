import { PortfolioSnapshot } from "@/lib/portfolio-import";

export type ScenarioKind = "prudent" | "neutre" | "dynamique";
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
};

const norm = (value: string) => value.toUpperCase().replace(/[-/]/g, "");

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
  portfolioValue: number | null, costBps: number, maxWeight: number): ScenarioResult {
  const [label, method] = LABELS[kind];
  const imported = new Map(snapshot.positions.map((position) => [norm(position.ticker), (position.weight ?? 0) / 100]));
  const keys: Record<ScenarioKind, string> = { prudent: "min_variance", neutre: "risk_parity", dynamique: "hrp" };
  const proposed = optimal?.[keys[kind]]; const symbols: string[] = optimal?.symbols ?? [];
  const exact = symbols.length === imported.size && symbols.every((item) => imported.has(norm(item)));
  const vide = { kind, label, method, weights: [], turnover: 0, estimatedCost: null, breaches: 0, averageCapEffect: 0, available: false };
  // TROIS causes distinctes, TROIS messages. L'ancien code les fondait toutes dans
  // « Historique/covariance indisponible », qui accusait la donnée même quand elle
  // était parfaitement chargée et que seule une clé manquait (06/09).
  if (!symbols.length) return { ...vide, reason: "Aucune allocation calculée : l'analyse de l'univers n'a rien renvoyé." };
  if (!exact) return { ...vide, reason: `Univers calculé (${symbols.length} actifs) différent de l'univers importé (${imported.size}).` };
  if (!Array.isArray(proposed) || proposed.length !== symbols.length)
    return { ...vide, reason: `Scénario « ${label} » non renvoyé par le calcul (clé « ${keys[kind]} » absente).` };
  // Plus de verrou ML sur « dynamique » : le HRP se calcule sur la seule covariance,
  // il n'a besoin d'aucun rendement attendu. Le verrou protégeait un Black-Litterman
  // qui n'a jamais été calculé ici.
  const constrained = capWeights(proposed, maxWeight);
  if (!constrained) return { kind, label, method, weights: [], turnover: 0, estimatedCost: null, breaches: 0, averageCapEffect: 0, available: false, reason: `Contrainte infaisable : ${symbols.length} actifs × ${(maxWeight * 100).toFixed(1)}% < 100%.` };
  const weights = symbols.map((item, index) => ({ symbol: item, current: imported.get(norm(item)) ?? 0, proposed: constrained.weights[index], delta: constrained.weights[index] - (imported.get(norm(item)) ?? 0) }));
  const turnover = weights.reduce((sum, row) => sum + Math.abs(row.delta), 0) / 2;
  return { kind, label, method, weights, turnover, estimatedCost: portfolioValue == null ? null : portfolioValue * turnover * costBps / 10_000,
    breaches: constrained.triggers, averageCapEffect: constrained.averageEffect, available: true };
}
