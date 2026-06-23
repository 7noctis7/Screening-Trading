"use client";
import { useMemo, useState } from "react";
import { StepBanner } from "@/components/Pipeline";
import { useScreen } from "@/lib/api";
import { PageSkeleton, EmptyState } from "@/components/ui";
import { downloadCsv } from "@/lib/csv";
import { IR } from "@/lib/ir";

const pct = (x?: number | null) =>
  x === null || x === undefined ? "—" : `${(x * 100).toFixed(1)}%`;
const money = (x?: number | null) =>
  x === null || x === undefined ? "—" : `${(x / 1e6).toFixed(1)} M$`;
const num = (x?: number | null) =>
  x === null || x === undefined ? "—" : x.toFixed(2);

export default function Screener() {
  const { data: s } = useScreen();
  const [q, setQ] = useState("");
  const rows = useMemo(() => {
    const all = s?.rows ?? [];
    const t = q.toLowerCase();
    return t
      ? all.filter((r: any) => `${r.symbol} ${r.name} ${r.sector ?? ""}`.toLowerCase().includes(t))
      : all;
  }, [s, q]);

  if (!s) return <PageSkeleton />;

  return (
    <main className="max-w-5xl mx-auto p-6 space-y-4">
      <h1 className="text-xl font-semibold tracking-tight">Screener — filtres + score</h1>
      <StepBanner active="screener" />

      {!s.available ? (
        <EmptyState title="Screener indisponible" hint={s.error || "Configuration manquante."} />
      ) : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            <div className="card p-4">
              <div className="text-muted text-xs uppercase tracking-wide">Candidats retenus</div>
              <div className="text-2xl mono mt-1 text-accent">{s.count ?? 0}</div>
            </div>
            <div className="card p-4">
              <div className="text-muted text-xs uppercase tracking-wide">Univers analysé</div>
              <div className="text-2xl mono mt-1">{s.universe_size ?? 0}</div>
            </div>
            <div className="card p-4">
              <div className="text-muted text-xs uppercase tracking-wide">Sélectivité</div>
              <div className="text-2xl mono mt-1">
                {s.universe_size ? `${Math.round((100 * (s.count ?? 0)) / s.universe_size)}%` : "—"}
              </div>
            </div>
          </div>

          <section className="card p-4">
            <h2 className="text-sm uppercase tracking-wide text-muted mb-2">Critères appliqués</h2>
            <div className="flex flex-wrap gap-1.5 mb-3">
              {(s.filters ?? []).map((f: string) => (
                <span key={f} className="text-xs px-2.5 py-1 rounded-full border border-border text-muted mono">
                  {f}
                </span>
              ))}
            </div>
            <div className="text-xs text-muted">
              Score = composite z-score pondéré ·{" "}
              {Object.entries(s.weights ?? {})
                .map(([k, v]) => `${k}×${v}`)
                .join(" · ")}
            </div>
          </section>

          <section className="card p-4 overflow-x-auto">
            <div className="flex items-center justify-between mb-3 gap-3">
              <h2 className="text-sm uppercase tracking-wide text-muted">Candidats (triés par score)</h2>
              <button
                onClick={() =>
                  downloadCsv(
                    "screener",
                    ["Rang", "Symbole", "Nom", "Classe", "Secteur", "Score", "Ret 12m", "Drawdown", "Volume $"],
                    rows.map((r: any) => [r.rank, r.symbol, r.name, r.asset_class, r.sector, r.score, r.ret_12m, r.drawdown, r.dollar_volume]),
                  )
                }
                className="text-xs px-3 py-1.5 rounded-lg border border-border text-muted hover:text-fg hover:bg-surfaceAlt whitespace-nowrap"
              >
                ⬇ Export CSV
              </button>
            </div>
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Rechercher un symbole, un nom, un secteur…"
              className="w-full bg-bg border border-border rounded-lg px-3 py-2 text-sm outline-none focus:border-accent mb-3"
            />
            {rows.length === 0 ? (
              <EmptyState
                title="Aucun candidat"
                hint="Aucun actif ne passe tous les filtres sur l'univers courant."
              />
            ) : (
              <table className="w-full text-sm">
                <thead className="text-muted text-xs">
                  <tr>
                    <th className="text-left font-normal">#</th>
                    <th className="text-left font-normal">Symbole</th>
                    <th className="text-left font-normal">Secteur</th>
                    <th className="text-right font-normal">Score</th>
                    <th className="text-right font-normal">Ret 12m</th>
                    <th className="text-right font-normal">Drawdown</th>
                    <th className="text-right font-normal">Volume $</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r: any) => (
                    <tr key={r.symbol} className="border-t border-border" title={r.reason}>
                      <td className="py-1.5 mono text-muted2">{r.rank}</td>
                      <td>
                        <IR ticker={r.symbol} name={r.name} assetClass={r.asset_class}
                          className="mono text-accent hover:underline" />
                        <span className="text-muted2 ml-2 truncate">{r.name}</span>
                      </td>
                      <td className="text-muted">{r.sector || r.asset_class}</td>
                      <td className="text-right mono" style={{ color: "var(--accent2)" }}>{num(r.score)}</td>
                      <td className="text-right mono" style={{ color: (r.ret_12m ?? 0) >= 0 ? "var(--pos)" : "var(--neg)" }}>{pct(r.ret_12m)}</td>
                      <td className="text-right mono text-muted">{pct(r.drawdown)}</td>
                      <td className="text-right mono text-muted">{money(r.dollar_volume)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        </>
      )}
    </main>
  );
}
