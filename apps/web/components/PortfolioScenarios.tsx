"use client";

import { useMemo, useState } from "react";
import { useMl, usePortfolio } from "@/lib/api";
import { PortfolioSnapshot } from "@/lib/portfolio-import";
import { buildScenario, ScenarioKind } from "@/lib/portfolio-scenarios";

const money = (value: number | null) => 
  value == null 
    ? "—" 
    : new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR", maximumFractionDigits: 0 }).format(value);

export function PortfolioScenarios({ snapshot, analysis }: { snapshot: PortfolioSnapshot | null; analysis?: any }) {
  const { data: portfolio } = usePortfolio(); 
  const { data: ml } = useMl();
  
  const [selected, setSelected] = useState<ScenarioKind>("prudent"); 
  const [value, setValue] = useState(100000);
  const [costBps, setCostBps] = useState(15); 
  const [maxPct, setMaxPct] = useState(20);
  
  const scenarios = useMemo(() => {
    const calculated = analysis?.available 
      ? { 
          symbols: analysis.symbols, 
          prudent: analysis.scenarios?.prudent ?? analysis.scenarios?.min_variance,
          neutre: analysis.scenarios?.neutre ?? analysis.scenarios?.risk_parity, 
          dynamique: analysis.scenarios?.dynamique ?? analysis.scenarios?.hrp ?? analysis.scenarios?.black_litterman 
        } 
      : portfolio?.analysis?.optimal_allocation;
      
    return snapshot 
      ? (["prudent", "neutre", "dynamique"] as ScenarioKind[]).map((kind) => 
          buildScenario(snapshot, calculated, kind, value > 0 ? value : null, costBps, maxPct / 100, Boolean(ml?.edge_ok))
        ) 
      : [];
  }, [snapshot, analysis, portfolio, ml, value, costBps, maxPct]);

  // --- LOGIQUE DE RECOMMANDATION INTELLIGENTE ---
  const suggestions = useMemo(() => {
    if (!ml?.scores || !snapshot) return [];

    const currentTickers = new Set(snapshot.positions.map(p => p.ticker));
    const missingTickers = new Set(analysis?.missing || []);

    // 1. Identifier les actifs bloquants ou faibles
    const weakAssets = snapshot.positions
      .map(p => {
        const cleanTicker = p.ticker.replace("-USD", "");
        const isMissing = missingTickers.has(p.ticker) || missingTickers.has(cleanTicker);
        const score = (ml.scores as Record<string, number>)[p.ticker] ?? (ml.scores as Record<string, number>)[cleanTicker];
        return { ticker: p.ticker, weight: p.weight, score, isMissing };
      })
      .filter(p => p.isMissing || (p.score !== undefined && p.score < 0.5));

    if (weakAssets.length === 0) return [];

    // 2. Trouver les meilleures alternatives dans le ML ayant les meilleurs scores
    const availableCandidates = Object.entries(ml.scores as Record<string, number>)
      .filter(([ticker, score]) => !currentTickers.has(ticker) && !currentTickers.has(ticker.replace("-USD", "")) && typeof score === "number")
      .map(([ticker, score]) => ({ ticker, score }))
      .sort((a, b) => b.score - a.score);

    // 3. Associer chaque actif faible à un remplaçant du top ML
    return weakAssets.map((weak, index) => {
      const replacement = availableCandidates[index];
      return {
        current: weak.ticker,
        currentWeight: weak.weight,
        reason: weak.isMissing ? "Historique ou covariance rejeté par l'API" : `Score ML faible (${((weak.score ?? 0) * 100).toFixed(1)}%)`,
        replacement: replacement?.ticker,
        replacementScore: replacement?.score
      };
    }).filter(s => s.replacement);
  }, [snapshot, analysis, ml]);
  // ----------------------------------------------

  if (!snapshot) return null;
  
  const active = scenarios.find((scenario) => scenario.kind === selected)!;
  
  return (
    <section className="card space-y-5">
      <div className="flex flex-wrap justify-between gap-3">
        <div>
          <div className="eyebrow">Étape 4 · Améliorer</div>
          <h2 className="text-lg font-semibold mt-1">Scénarios sous contraintes</h2>
          <p className="text-xs text-muted mt-1">Exploratoires, calculés par les moteurs existants sur le même univers uniquement.</p>
        </div>
        <span className="text-[10px] mono rounded-full border border-border px-3 py-1 h-fit">AUCUN ORDRE</span>
      </div>
      
      <div className="grid md:grid-cols-3 gap-3">
        <label className="text-xs text-muted">Valeur indicative (€)
          <input type="number" min="0" value={value} onChange={(event) => setValue(Number(event.target.value))} className="block w-full mt-1 rounded-lg border border-border bg-surface p-2 mono text-fg" />
        </label>
        <label className="text-xs text-muted">Coûts aller simple (bps)
          <input type="number" min="0" value={costBps} onChange={(event) => setCostBps(Number(event.target.value))} className="block w-full mt-1 rounded-lg border border-border bg-surface p-2 mono text-fg" />
        </label>
        <label className="text-xs text-muted">Poids maximal (%)
          <input type="number" min="1" max="100" value={maxPct} onChange={(event) => setMaxPct(Number(event.target.value))} className="block w-full mt-1 rounded-lg border border-border bg-surface p-2 mono text-fg" />
        </label>
      </div>
      
      <div className="grid md:grid-cols-3 gap-2">
        {scenarios.map((scenario) => (
          <button key={scenario.kind} onClick={() => setSelected(scenario.kind)} className={`text-left rounded-xl border p-3 ${selected === scenario.kind ? "border-cyan-500 bg-surface3" : "border-border"}`}>
            <div className="flex justify-between">
              <b>{scenario.label}</b><span>{scenario.available ? "✓" : "—"}</span>
            </div>
            <p className="text-xs text-muted mt-1">{scenario.method}</p>
          </button>
        ))}
      </div>
      
      {!active.available ? (
        <div className="space-y-4">
          <div className="rounded-xl p-4 text-sm text-amber-500" style={{ background: "color-mix(in srgb,var(--warn) 10%,transparent)" }}>
            ⚠️ {active.reason}
          </div>
          
          {suggestions.length > 0 && (
            <div className="rounded-xl border border-border bg-surface p-4">
              <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
                <span>💡</span> Suggestions de substitution par le moteur ML
              </h3>
              <div className="overflow-x-auto">
                <table>
                  <thead>
                    <tr>
                      <th>Actif bloquant</th>
                      <th>Problème détecté</th>
                      <th>Alternative suggérée</th>
                      <th>Score ML (OOS)</th>
                      <th className="text-right">Poids libéré réallouable</th>
                    </tr>
                  </thead>
                  <tbody>
                    {suggestions.map((s, i) => (
                      <tr key={i}>
                        <td className="mono text-amber-500">{s.current}</td>
                        <td className="text-xs text-muted">{s.reason}</td>
                        <td className="mono text-green-500">{s.replacement?.replace("-USD", "")}</td>
                        <td className="mono text-right">{s.replacementScore != null ? (s.replacementScore * 100).toFixed(1) + "%" : "—"}</td>
                        <td className="mono text-right">{s.currentWeight != null ? `${s.currentWeight} %` : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="text-xs text-muted mt-3">
                Intégrez ces alternatives à l'Étape 1 pour permettre aux moteurs Prudent, Neutre et Dynamique de calculer une matrice de covariance valide.
              </p>
            </div>
          )}
        </div>
      ) : (
        <>
          <div className="grid grid-cols-3 gap-2">
            <div className="rounded-xl bg-surface3 p-3">
              <div className="text-xs text-muted">Turnover</div>
              <b className="mono">{(active.turnover * 100).toFixed(1)}%</b>
            </div>
            <div className="rounded-xl bg-surface3 p-3">
              <div className="text-xs text-muted">Coûts estimés</div>
              <b className="mono">{money(active.estimatedCost)}</b>
            </div>
            <div className="rounded-xl bg-surface3 p-3">
              <div className="text-xs text-muted">Veto plafond</div>
              <b className="mono">{active.breaches}</b>
            </div>
          </div>
          
          <div className="overflow-x-auto">
            <table>
              <thead>
                <tr>
                  <th>Actif ({active.label})</th>
                  <th>Poids Actuel</th>
                  <th>Poids Proposé</th>
                  <th>Écart</th>
                  <th>Montant indicatif</th>
                </tr>
              </thead>
              <tbody>
                {active.weights.map((row) => (
                  <tr key={row.symbol}>
                    <td className="mono">{row.symbol}</td>
                    <td className="text-right mono">{(row.current * 100).toFixed(1)}%</td>
                    <td className="text-right mono">{(row.proposed * 100).toFixed(1)}%</td>
                    <td className="text-right mono">{row.delta >= 0 ? "+" : ""}{(row.delta * 100).toFixed(1)} pt</td>
                    <td className="text-right mono">{money(value > 0 ? row.proposed * value : null)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
      
      <details className="rounded-xl border border-border p-3 text-xs text-muted">
        <summary className="cursor-pointer text-fg">Méthodologie et limites</summary>
        <p className="mt-2">Les coûts sont une hypothèse linéaire en points de base appliquée au turnover. Spread dynamique, fiscalité, impact racine carrée et borrow ne sont pas encore modélisés. Un scénario qui viole le plafond est refusé, jamais corrigé silencieusement. « Dynamique » reste indisponible sans edge ML validé.</p>
      </details>
    </section>
  );
}
