"use client";
import { useState } from "react";
import { EquityChart, type Win } from "@/components/EquityChart";
import { usePerformance } from "@/lib/api";

// Courbe du compte RÉEL face au S&P 500, au Nasdaq 100 et au Bitcoin.
//
// EN DOLLARS, PAS EN BASE 100. Chaque référence est replacée sur le capital de DÉPART du
// portefeuille : la courbe répond à « où en serais-je si j'avais mis la même somme
// ailleurs », et l'écart entre deux courbes se lit directement comme un montant.
//
// UNE RÉFÉRENCE ABSENTE EST NOMMÉE. Si un indice manque des bases de prix locales, il
// n'est pas tracé et il est DIT. Un graphe silencieusement amputé laisserait croire à une
// comparaison complète.

const usd = (x: number) => `${Math.round(x).toLocaleString("fr-FR")} $`;
const pct = (x: number | null) => (x == null ? "—" : `${x >= 0 ? "+" : ""}${(x * 100).toFixed(2)} %`);
const COL: Record<string, string> = {
  Portefeuille: "var(--accent)", "S&P 500": "var(--warn)",
  "Nasdaq 100": "#a855f7", Bitcoin: "#f7931a",
};

export function PerformanceVsBenchmarks() {
  const { data, isLoading } = usePerformance();
  const [win, setWin] = useState<Win>(null);

  if (isLoading) return <div className="card p-4 text-muted text-sm">Chargement de la performance…</div>;
  if (!data?.disponible) {
    return (
      <div className="card p-4">
        <div className="text-xs uppercase tracking-wide text-muted mb-2">Performance vs références</div>
        <p className="text-sm text-muted">{data?.motif ?? "Historique d'equity indisponible."}</p>
        <p className="text-[11px] text-muted2 mt-1">
          La courbe se constitue à chaque passage du robot : un point par jour d'exécution.
        </p>
      </div>
    );
  }

  const perfs = data.performances ?? {};
  const pf = perfs["Portefeuille"];
  const lignes = Object.keys(perfs);

  return (
    <div className="flex flex-col gap-3">
      <EquityChart
        series={data.serie} benchmarks={data.benchmarks} height={300} periodes
        win={win} onWin={setWin} syncId="perf-positions"
        title={`Portefeuille vs références — depuis le ${data.depuis} (montants en $)`}
      />

      <div className="card p-4">
        <div className="text-xs uppercase tracking-wide text-muted mb-3">
          Même capital de départ, {data.depuis} → {data.jusqu_a}
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm" style={{ minWidth: 460 }}>
            <thead>
              <tr className="text-muted text-[11px] uppercase tracking-wide">
                <th className="text-left font-medium pb-2">Ligne</th>
                <th className="text-right font-medium pb-2">Départ</th>
                <th className="text-right font-medium pb-2">Aujourd'hui</th>
                <th className="text-right font-medium pb-2">Écart</th>
                <th className="text-right font-medium pb-2">vs portefeuille</th>
              </tr>
            </thead>
            <tbody>
              {lignes.map((nom) => {
                const p = perfs[nom];
                const ecartPf = nom === "Portefeuille" || !pf ? null : pf.fin - p.fin;
                return (
                  <tr key={nom} className="border-t border-border">
                    <td className="py-2">
                      <span className="inline-block w-2 h-2 rounded-full mr-2 align-middle"
                            style={{ background: COL[nom] ?? "var(--muted)" }} />
                      {nom}
                    </td>
                    <td className="text-right tabular-nums py-2">{usd(p.debut)}</td>
                    <td className="text-right tabular-nums py-2">{usd(p.fin)}</td>
                    <td className="text-right tabular-nums py-2"
                        style={{ color: p.variation >= 0 ? "var(--ok)" : "var(--danger)" }}>
                      {usd(p.variation)} <span className="text-muted">({pct(p.variation_pct)})</span>
                    </td>
                    <td className="text-right tabular-nums py-2"
                        style={{ color: ecartPf == null ? undefined : ecartPf >= 0 ? "var(--ok)" : "var(--danger)" }}>
                      {ecartPf == null ? "—" : usd(ecartPf)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {data.ecartees?.length > 0 && (
          <p className="text-[11px] text-muted2 mt-3">
            Non tracé{data.ecartees.length > 1 ? "s" : ""} — historique absent ou démarrant après le
            portefeuille : {data.ecartees.join(", ")}. Ces références ne sont pas simulées.
          </p>
        )}
        <p className="text-[11px] text-muted2 mt-1">
          Les jours sans cotation (week-end pour les actions), la référence garde sa dernière
          clôture connue — jamais la suivante, qui serait une information que le jour n'avait pas.
        </p>
      </div>
    </div>
  );
}
