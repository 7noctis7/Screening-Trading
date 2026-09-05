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
          min_variance: analysis.scenarios?.prudent,
          risk_parity: analysis.scenarios?.neutre, 
          hrp: analysis.scenarios?.hrp 
        } 
      : portfolio?.analysis?.optimal_allocation;
      
    return snapshot 
      ? (["prudent", "neutre", "dynamique"] as ScenarioKind[]).map((kind) => 
          buildScenario(snapshot, calculated, kind, value > 0 ? value : null, costBps, maxPct / 100, Boolean(ml?.edge_ok))
        ) 
      : [];
  }, [snapshot, analysis, portfolio, ml, value, costBps, maxPct]);

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
        <div className="rounded-xl p-4 text-sm text-amber-500" style={{ background: "color-mix(in srgb,var(--warn) 10%,transparent)" }}>
          ⚠️ {active.reason}
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
                  <th>Actif</th>
                  <th>Actuel</th>
                  <th>Proposé</th>
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
