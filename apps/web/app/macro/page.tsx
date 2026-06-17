"use client";
import { useMacro } from "@/lib/api";
import { PageSkeleton } from "@/components/ui";
import { StepBanner } from "@/components/Pipeline";

export default function Macro() {
  const { data } = useMacro();
  if (!data) return <PageSkeleton />;
  const m = data.fred ?? {}, imf = data.imf ?? {};
  return (
    <main className="max-w-5xl mx-auto p-6 space-y-4">
      <h1 className="text-xl font-semibold tracking-tight">Analyse macroéconomique</h1>
      <StepBanner active="macro" />

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
