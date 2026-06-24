"use client";
import { useMacro, usePredictionMarkets } from "@/lib/api";
import { PageSkeleton } from "@/components/ui";
import { StepBanner } from "@/components/Pipeline";

function PredMarkets() {
  const { data: pm } = usePredictionMarkets();
  if (!pm?.available) return null;
  const blocks = ([
    ["Macro", pm.macro ?? {}], ["Actifs détenus", pm.assets ?? {}], ["Résultats", pm.earnings ?? {}],
  ] as [string, Record<string, number>][]).filter(([, o]) => Object.keys(o).length);
  if (!blocks.length) return null;
  return (
    <section className="card p-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h2 className="text-sm uppercase tracking-wide text-muted">Marchés de prédiction (sagesse des foules)</h2>
        <span className="text-[11px] text-muted2">{pm.n_markets} marchés · Kalshi + Polymarket · sans clé</span>
      </div>
      <p className="text-muted2 text-xs mt-1">Probas implicites forward-looking. Indicatif (overlay de risque), pas un signal d'alpha.</p>
      <div className="grid md:grid-cols-3 gap-3 mt-3">
        {blocks.map(([title, obj]) => (
          <div key={title} className="rounded-lg border border-border p-3" style={{ background: "var(--surface)" }}>
            <div className="text-muted text-[11px] uppercase tracking-wide mb-1.5">{title}</div>
            {Object.entries(obj).map(([k, v]) => (
              <div key={k} className="flex items-center justify-between text-sm py-0.5">
                <span className="text-muted truncate mr-2">{k}</span>
                <span className="mono" style={{ color: "var(--accent2)" }}>{Math.round((v as number) * 100)}%</span>
              </div>
            ))}
          </div>
        ))}
      </div>
    </section>
  );
}

export default function Macro() {
  const { data } = useMacro();
  if (!data) return <PageSkeleton />;
  const m = data.fred ?? {}, imf = data.imf ?? {};
  return (
    <main className="max-w-5xl mx-auto p-6 space-y-4">
      <h1 className="text-xl font-semibold tracking-tight">Analyse macroéconomique</h1>
      <StepBanner active="macro" />
      <PredMarkets />

      {/* Indicateurs chiffrés (FRED) */}
      {!m.available ? (
        <div className="card p-4 text-sm">
          <b>Indicateurs FRED indisponibles.</b>
          <p className="text-muted mt-1">{m.reason}</p>
          <p className="text-muted2 text-xs mt-2">Clé FRED gratuite : <a className="text-accent" href="https://fred.stlouisfed.org" target="_blank" rel="noopener noreferrer">fred.stlouisfed.org</a> → My Account → API Keys, puis <code className="mono">export FRED_API_KEY="…"</code> et relance l'API.</p>
        </div>
      ) : (
        <>
          <p className="text-muted text-xs">{m.source} · Indicatif, hors score.</p>
          {Object.entries(m.groups).map(([group, items]: any) => (
            <section key={group} className="card p-4">
              <h2 className="text-sm uppercase tracking-wide text-muted mb-3">{group}</h2>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {items.map((it: any) => (
                  <div key={it.label}>
                    <div className="text-muted text-xs">{it.label}</div>
                    <div className="text-lg mono">{it.value}{it.unit}</div>
                    <div className="text-muted2 text-[11px]">{it.date}{it.delta != null ? ` · Δ ${it.delta >= 0 ? "+" : ""}${it.delta}` : ""}</div>
                  </div>
                ))}
              </div>
            </section>
          ))}
        </>
      )}

      {/* Projections FMI (WEO) */}
      {imf.available && (
        <>
          <h2 className="text-sm uppercase tracking-wide text-muted pt-2">📈 Projections FMI (WEO)</h2>
          <p className="text-muted2 text-xs">{imf.source}</p>
          {imf.indicators.map((ind: any) => (
            <section key={ind.key} className="card p-4 overflow-x-auto">
              <h3 className="text-sm font-medium mb-2">{ind.label}</h3>
              <table className="w-full text-sm mono">
                <thead className="text-muted text-xs">
                  <tr><th className="text-left font-normal">Pays</th>
                    {imf.years.map((y: string) => (
                      <th key={y} className="text-right font-normal">{Number(y) >= imf.current_year ? `${y}e` : y}</th>
                    ))}</tr>
                </thead>
                <tbody>{ind.rows.map((r: any) => (
                  <tr key={r.country} className="border-t border-border">
                    <td className="py-1.5 font-sans">{r.country}</td>
                    {r.values.map((v: number | null, i: number) => (
                      <td key={i} className="text-right" style={{ color: v == null ? "var(--muted2)" : v < 0 ? "#f43f5e" : undefined }}>
                        {v == null ? "—" : `${v > 0 && ind.key !== "LUR" ? "+" : ""}${v}%`}</td>
                    ))}
                  </tr>))}</tbody>
              </table>
            </section>
          ))}
        </>
      )}
    </main>
  );
}
