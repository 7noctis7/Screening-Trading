"use client";
import { useConviction } from "@/lib/api";
import { PageSkeleton, EmptyState } from "@/components/ui";
import { SortableTable, type Col } from "@/components/SortableTable";
import { StepBanner } from "@/components/Pipeline";

const z = (v?: number) => (v == null ? "—" : <span style={{ color: v > 0 ? "#22c55e" : v < 0 ? "#f43f5e" : "#9aa1ad" }}>{v.toFixed(2)}</span>);

export default function Conviction() {
  const { data: c } = useConviction();
  if (!c) return <PageSkeleton />;
  if (!c.available)
    return <main className="max-w-3xl mx-auto p-6"><EmptyState title="Conviction indisponible" hint="Signaux insuffisants." /></main>;

  const cols: Col[] = [
    { key: "symbol", label: "Actif" },
    { key: "sector", label: "Secteur", render: (v) => <span className="text-muted text-xs">{v}</span> },
    { key: "trend", label: "Tendance", num: true, render: z, csv: (v) => v },
    { key: "ml", label: "ML", num: true, render: z, csv: (v) => v },
    { key: "fundamental", label: "Fondam.", num: true, render: z, csv: (v) => v },
    { key: "sentiment", label: "Sentiment", num: true, render: z, csv: (v) => v },
    { key: "conviction", label: "Conviction", num: true, render: (v) => <b style={{ color: v > 0 ? "#22c55e" : "#f43f5e" }}>{v.toFixed(2)}</b> },
    { key: "target_weight", label: "Poids cible", num: true, align: "right",
      render: (v) => (v > 0 ? `${(v * 100).toFixed(1)}%` : "—"), csv: (v) => v },
  ];

  return (
    <main className="max-w-6xl mx-auto p-6 space-y-4">
      <h1 className="text-xl font-semibold tracking-tight">Conviction — signaux fusionnés</h1>
      <StepBanner active="screener" />
      {c.backtest?.available && (
        <section className="card p-4">
          <h2 className="text-sm uppercase tracking-wide text-muted mb-1">Backtest point-in-time — conviction vs équipondéré</h2>
          <p className="text-muted2 text-xs mb-3">Poids calculés uniquement avec le passé (anti-fuite), rendements réalisés ensuite. {c.backtest.n_rebalances} rebalancements ({c.backtest.step_days} j).</p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-muted text-xs"><tr>
                <th className="text-left font-normal">Stratégie</th>
                <th className="text-right font-normal">Rendement</th><th className="text-right font-normal">Annualisé</th>
                <th className="text-right font-normal">Sharpe</th><th className="text-right font-normal">Sharpe déflaté</th>
                <th className="text-right font-normal">Max DD</th></tr></thead>
              <tbody className="mono">
                {[["Conviction", c.backtest.strategy, "#22d3ee"], ["Équipondéré (bench)", c.backtest.benchmark, "#9aa1ab"]].map(([lab, s, col]: any) => (
                  <tr key={lab} className="border-t border-border">
                    <td className="py-1.5 font-sans" style={{ color: col }}>{lab}</td>
                    <td className="text-right">{(s.total_return * 100).toFixed(1)}%</td>
                    <td className="text-right">{(s.annualized * 100).toFixed(1)}%</td>
                    <td className="text-right">{s.sharpe}</td>
                    <td className="text-right" style={{ color: s.dsr >= 0.9 ? "#22c55e" : undefined }}>{(s.dsr * 100).toFixed(0)}%</td>
                    <td className="text-right" style={{ color: "#f43f5e" }}>{(s.max_drawdown * 100).toFixed(1)}%</td>
                  </tr>))}
              </tbody>
            </table>
          </div>
          <p className="text-sm mt-2">Alpha annualisé : <b style={{ color: c.backtest.alpha >= 0 ? "#22c55e" : "#f43f5e" }}>{(c.backtest.alpha * 100).toFixed(1)}%</b>
            <span className="text-muted"> · turnover {c.backtest.turnover_annual}×/an. Le <b>Sharpe déflaté</b> (proba que l'edge soit réel après essais multiples) est le juge de paix.</span></p>
        </section>
      )}
      {c.lens_backtest?.available && (
        <section className="card p-4">
          <h2 className="text-sm uppercase tracking-wide text-muted mb-1">Top 10 par lentille — quelle catégorie a le mieux performé&nbsp;?</h2>
          <p className="text-muted2 text-xs mb-3">Panier <b>équipondéré des 10 meilleurs</b> de chaque lentille, rejoué sur l'historique (rebalancement {c.lens_backtest.step_days} j, rendements réalisés).</p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-muted text-xs"><tr>
                <th className="text-left font-normal">Lentille (top 10)</th>
                <th className="text-right font-normal">Rendement</th><th className="text-right font-normal">Annualisé</th>
                <th className="text-right font-normal">Sharpe</th><th className="text-right font-normal">Sharpe déflaté</th>
                <th className="text-right font-normal">Max DD</th></tr></thead>
              <tbody className="mono">
                {Object.entries(c.lens_backtest.lenses)
                  .sort((a: any, b: any) => b[1].annualized - a[1].annualized)
                  .map(([lab, s]: any) => (
                    <tr key={lab} className="border-t border-border">
                      <td className="py-1.5 font-sans">{lab}</td>
                      <td className="text-right">{(s.total_return * 100).toFixed(1)}%</td>
                      <td className="text-right">{(s.annualized * 100).toFixed(1)}%</td>
                      <td className="text-right">{s.sharpe}</td>
                      <td className="text-right" style={{ color: s.dsr >= 0.9 ? "#22c55e" : undefined }}>{(s.dsr * 100).toFixed(0)}%</td>
                      <td className="text-right" style={{ color: "#f43f5e" }}>{(s.max_drawdown * 100).toFixed(1)}%</td>
                    </tr>))}
              </tbody>
            </table>
          </div>
          <p className="text-muted2 text-xs mt-2">⚠️ Sélection figée sur le snapshot courant. <b>Fondamentaux</b> et <b>Investisseurs</b> sont neutres vis-à-vis des prix (factor sleeve, sans fuite) ; <b>Signaux ML</b> et <b>Toutes catégories</b> encodent le momentum récent → à lire comme <b>indicatif</b>. Le Sharpe déflaté reste le juge de paix.</p>
        </section>
      )}
      <div className="card p-4 text-sm">
        <b>La synthèse de toutes les fenêtres en une seule note.</b>
        <p className="text-muted mt-1">{c.method}</p>
        <p className="text-muted2 text-xs mt-2">Les colonnes Tendance/ML/Fondam./Sentiment sont des <b>z-scores</b> (écart à la moyenne de l'univers). La <b>conviction</b> est leur moyenne. Le <b>poids cible</b> = allocation conviction × inverse-volatilité, plafonnée à 20 % — c'est l'allocation « best practice » qui fait converger les lentilles sous contrôle du risque.</p>
      </div>
      <section className="card p-4">
        <SortableTable rows={c.rows} cols={cols} filterKeys={["symbol", "sector"]} csvName="conviction"
          initialSort={{ key: "conviction", dir: "desc" }} />
      </section>
    </main>
  );
}
