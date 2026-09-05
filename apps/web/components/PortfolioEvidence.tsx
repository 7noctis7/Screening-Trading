"use client";

import { useMemo } from "react";
import {
  useEvents,
  useFundamentals,
  useMacro,
  useMl,
  usePortfolio,
  usePositions,
  useScreen,
  useScreener
} from "@/lib/api";
import { PortfolioSnapshot } from "@/lib/portfolio-import";

const symbol = (value: unknown) => String(value ?? "").toUpperCase().replace(/[-/]/g, "").replace(/(USDT|USDC|USD)$/, "");
const rowsBySymbol = (rows: any[] = []) => new Map(rows.map((row) => [symbol(row.symbol), row]));
const show = (value: unknown, digits = 2) => typeof value === "number" && Number.isFinite(value) ? value.toFixed(digits) : "—";

function Coverage({ label, count, total }: { label: string; count: number; total: number }) {
  const ratio = total ? count / total : 0;
  return (
    <div className="rounded-xl border border-border p-3">
      <div className="flex justify-between text-xs">
        <span>{label}</span>
        <b className="mono">{count}/{total}</b>
      </div>
      <div className="h-1.5 bg-surface3 rounded mt-2">
        <div className="h-full bg-accent rounded" style={{ width: `${ratio * 100}%` }} />
      </div>
    </div>
  );
}

function concentration(snapshot: PortfolioSnapshot) {
  const weights = snapshot.positions.map((position) => (position.weight ?? 0) / 100);
  const hhi = weights.reduce((sum, weight) => sum + weight * weight, 0);
  return { hhi, effective: hhi > 0 ? 1 / hhi : null, largest: Math.max(0, ...weights) };
}

export function PortfolioEvidence({ snapshot, analysis, loading }: { snapshot: PortfolioSnapshot | null; analysis?: any; loading?: boolean }) {
  const { data: screen } = useScreen(); 
  const { data: fundamentals } = useFundamentals();
  const { data: screener } = useScreener(); 
  const { data: positions } = usePositions();
  const { data: ml } = useMl(); 
  const { data: events } = useEvents();
  const { data: macro } = useMacro(); 
  const { data: portfolio } = usePortfolio();

  const evidence = useMemo(() => {
    if (!snapshot) return null;
    
    const screens = rowsBySymbol([...(screen?.rows ?? []), ...(screener?.rows ?? [])]);
    const funds = rowsBySymbol(fundamentals?.rows);
    const earnings = rowsBySymbol([...(events?.earnings ?? []), ...(positions?.earnings_risk ?? [])]);
    const scores = new Map(Object.entries(ml?.scores ?? {}).map(([name, score]) => [symbol(name), score]));
    
    const rows = snapshot.positions.map((position) => {
      const key = symbol(position.ticker); 
      const s = screens.get(key); 
      const f = funds.get(key); 
      const e = earnings.get(key);
      const mlScore = scores.get(key) ?? (ml?.scores as any)?.[position.ticker];
      
      return { position, screen: s, fund: f, earnings: e, ml: mlScore };
    });
    
    return { 
      rows, 
      risk: concentration(snapshot), 
      counts: {
        market: rows.filter((row) => row.screen).length, 
        fundamentals: rows.filter((row) => row.fund).length,
        ml: rows.filter((row) => typeof row.ml === "number").length, 
        events: rows.filter((row) => row.earnings).length,
      }
    };
  }, [snapshot, screen, screener, fundamentals, events, positions, ml]);

  if (!snapshot || !evidence) return null;

  const total = snapshot.positions.length; 
  const optimal = portfolio?.analysis?.optimal_allocation; 
  const imported = new Set(snapshot.positions.map((p) => symbol(p.ticker)));
  const reusable = optimal?.symbols?.length === imported.size && optimal.symbols.every((item: string) => imported.has(symbol(item)));

  return (
    <section className="card space-y-4">
      <div>
        <div className="eyebrow">Diagnostic croisé</div>
        <h2 className="text-lg font-semibold mt-1">Preuves disponibles pour ce snapshot</h2>
        <p className="text-xs text-muted mt-1">Jointure prudente avec les snapshots des autres onglets. « — » signifie indisponible, jamais zéro.</p>
      </div>
      
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
        <Coverage label="Marché / screening" count={evidence.counts.market} total={total} />
        <Coverage label="Fondamentaux" count={evidence.counts.fundamentals} total={total} />
        <Coverage label="ML" count={evidence.counts.ml} total={total} />
        <Coverage label="Résultats" count={evidence.counts.events} total={total} />
      </div>
      
      <div className="grid grid-cols-3 gap-2">
        <div className="rounded-xl bg-surface3 p-3">
          <span className="text-xs text-muted">HHI</span>
          <div className="mono text-lg">{show(evidence.risk.hhi, 3)}</div>
        </div>
        <div className="rounded-xl bg-surface3 p-3">
          <span className="text-xs text-muted">Positions effectives</span>
          <div className="mono text-lg">{show(evidence.risk.effective, 1)}</div>
        </div>
        <div className="rounded-xl bg-surface3 p-3">
          <span className="text-xs text-muted">Plus grande ligne</span>
          <div className="mono text-lg">{show(evidence.risk.largest * 100, 1)}%</div>
        </div>
      </div>
      
      {loading && (
        <div className="rounded-xl bg-surface3 p-4 text-sm text-muted">
          Chargement et alignement des historiques réels…
        </div>
      )}
      
      {!loading && analysis?.available && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          <div className="rounded-xl bg-surface3 p-3">
            <span className="text-xs text-muted">Vol annualisée</span>
            <div className="mono text-lg">{show(analysis.metrics?.vol_annual * 100, 1)}%</div>
          </div>
          <div className="rounded-xl bg-surface3 p-3">
            <span className="text-xs text-muted">Max drawdown simulé</span>
            <div className="mono text-lg">{show(analysis.metrics?.max_drawdown * 100, 1)}%</div>
          </div>
          <div className="rounded-xl bg-surface3 p-3">
            <span className="text-xs text-muted">Sharpe historique</span>
            <div className="mono text-lg">{show(analysis.metrics?.sharpe)}</div>
          </div>
          <div className="rounded-xl bg-surface3 p-3">
            <span className="text-xs text-muted">ES 95% · 1 jour</span>
            <div className="mono text-lg">{show(analysis.metrics?.expected_shortfall_95_1d * 100, 2)}%</div>
          </div>
        </div>
      )}
      
      {!loading && analysis && !analysis.available && (
        <div className="rounded-xl p-4 text-sm text-amber-500" style={{ background: "color-mix(in srgb,var(--warn) 10%,transparent)" }}>
          ⚠️ Analyse historique indisponible : {analysis.reason}. {analysis.missing?.length ? `Séries manquantes : ${analysis.missing.join(", ")}.` : ""} Couverture {(Number(analysis.coverage ?? 0) * 100).toFixed(0)}%.
        </div>
      )}
      
      <div className="overflow-x-auto">
        <table>
          <thead>
            <tr>
              <th>Actif</th>
              <th>Poids</th>
              <th>Score screening</th>
              <th>Score fondamental</th>
              <th>ML OOS</th>
              <th>Prochain résultat</th>
            </tr>
          </thead>
          <tbody>
            {evidence.rows.map(({ position, screen: s, fund, ml: score, earnings }) => (
              <tr key={position.id}>
                <td className="mono">{position.ticker}</td>
                <td className="mono text-right">{show(position.weight, 1)}%</td>
                <td className="mono text-right">{show(s?.score ?? s?.composite_score)}</td>
                <td className="mono text-right">{show(fund?.combined_score)}</td>
                <td className="mono text-right">{typeof score === "number" && ml?.edge_ok ? `${(score * 100).toFixed(1)}%` : "—"}</td>
                <td className="mono text-right">{earnings?.date ? String(earnings.date).slice(0, 10) : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      
      <div className="rounded-xl border border-border p-3 text-xs text-muted">
        <b>Régime macro :</b> {macro?.fred?.available ? `${macro.fred.source ?? "FRED"} disponible, mais pas encore transformé en tilt d'allocation.` : "indisponible ou non calibré."} 
        <b className="ml-2">ML :</b> {ml?.edge_ok ? `gate actif (${ml.edge_message ?? "edge validé"})` : "non utilisé : edge absent, indisponible ou rejeté."}
      </div>
      
      <div className="rounded-xl p-3 text-xs" style={{ background: analysis?.available || reusable ? "color-mix(in srgb,var(--accent) 10%,transparent)" : "var(--surface3)" }}>
        <b>Allocations prudent / neutre / dynamique :</b> {analysis?.available ? `recalculées sur ${analysis.n_observations} observations communes (${analysis.start} → ${analysis.as_of}), sans remplissage.` : reusable ? "les moteurs min-variance, HRP et risk-parity disposent exactement du même univers ; leur comparaison peut être affichée à l'étape suivante après validation des coûts et contraintes utilisateur." : "non publiées : l'univers importé ne correspond pas exactement à l'univers déjà calculé. Recalculer avec ses historiques et ses coûts est obligatoire ; réutiliser des poids d'un autre portefeuille serait faux."}
      </div>
    </section>
  );
}
