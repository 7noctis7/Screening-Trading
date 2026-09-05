import { PortfolioSnapshot } from "@/lib/portfolio-import";

export type ScenarioKind = "prudent" | "neutre" | "dynamique";
export type ScenarioResult = {
  kind: ScenarioKind; label: string; method: string; weights: { symbol: string; current: number; proposed: number; delta: number }[];
  turnover: number; estimatedCost: number | null; breaches: number; available: boolean; reason?: string;
};

const LABELS: Record<ScenarioKind, [string, string]> = {
  prudent: ["Prudent", "Minimum variance robuste sur l'univers disponible"],
  neutre: ["Neutre", "Equal Risk Contribution, budgets de risque équilibrés"],
  dynamique: ["Dynamique", "Black-Litterman avec vues seulement si l'edge ML est validé"],
};

const norm = (value: string) => value.toUpperCase().replace(/[-/]/g, "");

export function buildScenario(snapshot: PortfolioSnapshot, optimal: any, kind: ScenarioKind,
  portfolioValue: number | null, costBps: number, maxWeight: number, mlEdge: boolean): ScenarioResult {
  const [label, method] = LABELS[kind];
  const imported = new Map(snapshot.positions.map((position) => [norm(position.ticker), (position.weight ?? 0) / 100]));
  const keys: Record<ScenarioKind, string> = { prudent: "min_variance", neutre: "risk_parity", dynamique: "black_litterman" };
  const proposed = optimal?.[keys[kind]]; const symbols: string[] = optimal?.symbols ?? [];
  const exact = symbols.length === imported.size && symbols.every((item) => imported.has(norm(item)));
  if (!exact || !Array.isArray(proposed) || proposed.length !== symbols.length)
    return { kind, label, method, weights: [], turnover: 0, estimatedCost: null, breaches: 0, available: false, reason: "Historique/covariance indisponible pour cet univers exact." };
  if (kind === "dynamique" && !mlEdge)
    return { kind, label, method, weights: [], turnover: 0, estimatedCost: null, breaches: 0, available: false, reason: "UNCALIBRATED — edge ML non validé." };
  const weights = symbols.map((item, index) => ({ symbol: item, current: imported.get(norm(item)) ?? 0, proposed: Number(proposed[index]), delta: Number(proposed[index]) - (imported.get(norm(item)) ?? 0) }));
  const turnover = weights.reduce((sum, row) => sum + Math.abs(row.delta), 0) / 2;
  const breaches = weights.filter((row) => row.proposed > maxWeight + 1e-9).length;
  return { kind, label, method, weights, turnover, estimatedCost: portfolioValue == null ? null : portfolioValue * turnover * costBps / 10_000, breaches, available: breaches === 0, reason: breaches ? `${breaches} poids dépassent le plafond utilisateur ; scénario refusé sans relaxation.` : undefined };
}
