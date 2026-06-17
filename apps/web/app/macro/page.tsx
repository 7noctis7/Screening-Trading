"use client";
import { useMacro } from "@/lib/api";
import { PageSkeleton } from "@/components/ui";
import { StepBanner } from "@/components/Pipeline";

export default function Macro() {
  const { data: m } = useMacro();
  if (!m) return <PageSkeleton />;
  return (
    <main className="max-w-5xl mx-auto p-6 space-y-4">
      <h1 className="text-xl font-semibold tracking-tight">Analyse macroéconomique</h1>
      <StepBanner active="macro" />
      {!m.available ? (
        <div className="card p-4 text-sm">
          <b>Données macro indisponibles.</b>
          <p className="text-muted mt-1">{m.reason}</p>
          <p className="text-muted2 text-xs mt-2">Clé FRED gratuite : <a className="text-accent" href="https://fred.stlouisfed.org" target="_blank" rel="noopener noreferrer">fred.stlouisfed.org</a> → My Account → API Keys, puis <code className="mono">echo 'export FRED_API_KEY="ta_clé"' &gt;&gt; ~/.zshrc</code> et relance l'API.</p>
        </div>
      ) : (
        <>
          <p className="text-muted text-xs">{m.source} · Indicatif, hors score de sélection.</p>
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
    </main>
  );
}
