"use client";
// Screener institutionnel : entonnoir de sélection (univers → investable → candidats),
// score EXPLICABLE (contributions factorielles z-score par titre, croisées avec le ranking),
// répartition sectorielle des candidats, table tri/filtre/CSV. Aucun chiffre inventé.
import { useMemo, useState } from "react";
import { StepBanner } from "@/components/Pipeline";
import { useScreen, useScreener } from "@/lib/api";
import { MetricCard } from "@/components/MetricCard";
import { SortableTable, type Col } from "@/components/SortableTable";
import { PageSkeleton, EmptyState } from "@/components/ui";
import { IR } from "@/lib/ir";

const pct = (x?: number | null) => (x == null ? "—" : `${(x * 100).toFixed(1)}%`);
const money = (x?: number | null) => (x == null ? "—" : `${(x / 1e6).toFixed(1)} M$`);

// Micro-barre divergente pour un z-score factoriel (échelle ±2.5σ).
function ZBar({ z }: { z: number }) {
  const w = Math.min(50, (Math.abs(z) / 2.5) * 50);
  const col = z >= 0 ? "var(--pos)" : "#f43f5e";
  return (
    <span className="relative inline-block h-1.5 w-[72px] rounded-full align-middle"
      style={{ background: "var(--surface2)" }}>
      <span className="absolute top-0 bottom-0 left-1/2 w-px" style={{ background: "var(--border2)" }} />
      <span className="absolute top-0 bottom-0 rounded-full"
        style={z >= 0 ? { left: "50%", width: `${w}%`, background: col }
          : { right: "50%", width: `${w}%`, background: col }} />
    </span>
  );
}

// Étape de l'entonnoir de sélection (largeur ∝ effectif restant).
function FunnelStep({ label, n, base, hint }: { label: string; n: number; base: number; hint: string }) {
  const w = base > 0 ? Math.max(4, (n / base) * 100) : 0;
  return (
    <div title={hint}>
      <div className="flex justify-between text-xs mb-1">
        <span className="text-muted">{label}</span>
        <span className="mono">{n.toLocaleString("fr-FR")}</span>
      </div>
      <div className="h-2.5 rounded-full overflow-hidden" style={{ background: "var(--surface2)" }}>
        <div className="h-full rounded-full" style={{ width: `${w}%`, background: "var(--accent)", opacity: 0.85 }} />
      </div>
    </div>
  );
}

// Fiche détaillée d'un candidat : pourquoi ce score (facteurs), métriques, lien fiche externe.
function CandidateModal({ row, factors, onClose }: { row: any; factors: Record<string, number> | null; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-[70] grid place-items-center p-4" onClick={onClose}
      style={{ background: "rgba(0,0,0,.55)" }}>
      <div onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true"
        className="card p-5 w-full max-w-md" style={{ background: "var(--surface)" }}>
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="text-lg font-semibold mono">#{row.rank} {row.symbol}</div>
            <div className="text-muted2 text-xs">{row.name} · {row.sector || row.asset_class}</div>
          </div>
          <button onClick={onClose} aria-label="Fermer" className="text-muted2 hover:text-fg text-xl leading-none">×</button>
        </div>
        <div className="grid grid-cols-3 gap-3 mt-3 text-sm">
          <div><div className="text-muted text-[11px]">Score</div><div className="mono" style={{ color: "var(--accent2)" }}>{row.score?.toFixed(2)}</div></div>
          <div><div className="text-muted text-[11px]">Ret 12 m</div><div className="mono" style={{ color: (row.ret_12m ?? 0) >= 0 ? "var(--pos)" : "#f43f5e" }}>{pct(row.ret_12m)}</div></div>
          <div><div className="text-muted text-[11px]">Drawdown</div><div className="mono text-muted">{pct(row.drawdown)}</div></div>
        </div>
        <div className="mt-4">
          <div className="text-muted text-[11px] uppercase tracking-wide mb-2">Pourquoi ce score (z-scores factoriels)</div>
          {factors && Object.keys(factors).length ? (
            <div className="space-y-1.5">
              {Object.entries(factors).sort((a, b) => Math.abs(b[1]) - Math.abs(a[1])).map(([k, v]) => (
                <div key={k} className="flex items-center justify-between gap-2 text-xs">
                  <span className="text-muted font-sans">{k}</span>
                  <span className="inline-flex items-center gap-2">
                    <ZBar z={v} /><span className="mono w-12 text-right" style={{ color: v >= 0 ? "var(--pos)" : "#f43f5e" }}>{v >= 0 ? "+" : ""}{v.toFixed(2)}</span>
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-muted2 text-xs">n/d — ce titre passe les filtres mais n'est pas dans le top du ranking factoriel.</p>
          )}
        </div>
        {row.reason && <p className="text-muted2 text-[11px] mt-3">{row.reason}</p>}
        <div className="mt-4 flex items-center justify-between">
          <IR ticker={row.symbol} name={row.name} assetClass={row.asset_class}
            className="text-sm px-3 py-1.5 rounded-lg border border-border hover:border-border2 hover:text-accent transition-colors" />
          <span className="text-[10px] text-muted2">Aide à la décision — pas un conseil.</span>
        </div>
      </div>
    </div>
  );
}

export default function Screener() {
  const { data: s } = useScreen();
  const { data: rk } = useScreener();
  const [sel, setSel] = useState<any>(null);
  const factorsBySym = useMemo(() => {
    const m: Record<string, Record<string, number>> = {};
    for (const r of rk?.rows ?? []) m[r.symbol] = r.factors ?? {};
    return m;
  }, [rk]);
  const rows = useMemo(() => (s?.rows ?? []).map((r: any) => ({
    ...r, _factors: factorsBySym[r.symbol] ?? null,
    _top: topFactor(factorsBySym[r.symbol]),
  })), [s, factorsBySym]);

  if (!s) return <PageSkeleton />;
  const total = (s.universe_size ?? 0) + (s.excluded_non_investable ?? 0);
  const sectors = countBy(rows, (r: any) => r.sector || r.asset_class || "n/d");

  const cols: Col[] = [
    { key: "rank", label: "#", num: true, align: "left",
      render: (v) => <span className="mono text-muted2">{v}</span> },
    { key: "symbol", label: "Symbole", render: (v, r) => (
        <span><span className="mono text-accent border-b border-dotted border-border">{v}</span>
          <span className="text-muted2 ml-2 text-xs font-sans">{r.name}</span></span>) },
    { key: "sector", label: "Secteur", render: (v, r) => <span className="text-muted text-xs font-sans">{v || r.asset_class}</span> },
    { key: "score", label: "Score", num: true, align: "right",
      render: (v) => <span className="mono" style={{ color: "var(--accent2)" }}>{v?.toFixed(2)}</span> },
    { key: "_top", label: "Facteur dominant", render: (v) => v ? (
        <span className="inline-flex items-center gap-1.5 text-xs">
          <span className="text-muted font-sans">{v[0]}</span><ZBar z={v[1]} />
        </span>) : <span className="text-muted2 text-xs">n/d</span> },
    { key: "ret_12m", label: "Ret 12 m", num: true, align: "right",
      render: (v) => <span className="mono" style={{ color: (v ?? 0) >= 0 ? "var(--pos)" : "#f43f5e" }}>{pct(v)}</span>,
      csv: (v) => v == null ? "" : +(v * 100).toFixed(1) },
    { key: "drawdown", label: "Drawdown", num: true, align: "right",
      render: (v) => <span className="mono text-muted">{pct(v)}</span>, csv: (v) => v == null ? "" : +(v * 100).toFixed(1) },
    { key: "dollar_volume", label: "Volume $", num: true, align: "right",
      render: (v) => <span className="mono text-muted">{money(v)}</span>, csv: (v) => v == null ? "" : Math.round(v) },
  ];

  return (
    <main className="max-w-5xl mx-auto p-6 space-y-4">
      <h1 className="text-xl font-semibold tracking-tight">Screener — filtres + score explicable</h1>
      <StepBanner active="screener" />
      {!s.available ? (
        <EmptyState title="Screener indisponible" hint={s.error || "Configuration manquante."} />
      ) : (
        <>
          <section className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <MetricCard label="Candidats retenus" value={String(s.count ?? 0)} />
            <MetricCard label="Univers investable" value={String(s.universe_size ?? 0)} />
            <MetricCard label="Sélectivité" value={s.universe_size ? `${Math.round((100 * (s.count ?? 0)) / s.universe_size)}%` : "n/d"} />
            <MetricCard label="Non investables exclus" value={String(s.excluded_non_investable ?? 0)} />
          </section>

          <section className="card p-4">
            <h2 className="text-sm uppercase tracking-wide text-muted mb-3">Entonnoir de sélection</h2>
            <div className="space-y-3">
              <FunnelStep label="Univers analysé" n={total} base={total}
                hint="Tous les actifs du panel de prix (actions, ETF, crypto, indices)." />
              <FunnelStep label="Investable (hors indices ^…)" n={s.universe_size ?? 0} base={total}
                hint="On ne propose jamais un actif non achetable — les indices servent au régime/benchmark." />
              <FunnelStep label="Passent les filtres durs" n={s.count ?? 0} base={total}
                hint="Filtres YAML (liquidité, tendance, drawdown…) appliqués : voir critères ci-dessous." />
              <FunnelStep label="Top affiché (tri par score)" n={rows.length} base={total}
                hint="Les 50 premiers par composite z-score." />
            </div>
            <div className="flex flex-wrap gap-1.5 mt-4">
              {(s.filters ?? []).map((f: string) => (
                <span key={f} className="text-xs px-2.5 py-1 rounded-full border border-border text-muted mono">{f}</span>
              ))}
            </div>
            <div className="text-xs text-muted mt-2">
              Score = composite z-score pondéré · {Object.entries(s.weights ?? {}).map(([k, v]) => `${k}×${v}`).join(" · ")}
              {rk?.as_of && <span className="text-muted2"> · ranking au {new Date(rk.as_of).toLocaleDateString("fr-FR")}</span>}
            </div>
          </section>

          {sectors.length > 1 && (
            <section className="card p-4">
              <h2 className="text-sm uppercase tracking-wide text-muted mb-2">Où se concentrent les candidats</h2>
              <div className="flex flex-wrap gap-2">
                {sectors.map(([sec, n]) => (
                  <span key={sec} className="text-xs px-2.5 py-1.5 rounded-lg border border-border font-sans"
                    style={{ background: "var(--surface)" }}>{sec} <b className="mono">{n}</b></span>
                ))}
              </div>
              <p className="text-muted2 text-[11px] mt-2">Beaucoup de candidats dans un même secteur = le screen capte peut-être UN thème, pas N opportunités indépendantes (risque de concentration).</p>
            </section>
          )}

          <section className="card p-4">
            <div className="flex items-center justify-between flex-wrap gap-2 mb-1">
              <h2 className="text-sm uppercase tracking-wide text-muted">Candidats — clique une ligne pour le détail factoriel</h2>
            </div>
            {rows.length === 0 ? (
              <EmptyState title="Aucun candidat" hint="Aucun actif ne passe tous les filtres sur l'univers courant." />
            ) : (
              <div onClickCapture={(e) => {
                if ((e.target as HTMLElement).closest("a,button,input")) return;
                const tr = (e.target as HTMLElement).closest("tr");
                const sym = tr?.querySelectorAll("td")[1]?.textContent?.trim().split(/\s/)[0];
                const row = rows.find((r: any) => r.symbol === sym);
                if (row) setSel(row);
              }}>
                <SortableTable rows={rows} cols={cols} filterKeys={["symbol", "name", "sector"]}
                  csvName="screener.csv" initialSort={{ key: "rank", dir: "asc" }} dense />
              </div>
            )}
          </section>
          {sel && <CandidateModal row={sel} factors={sel._factors} onClose={() => setSel(null)} />}
        </>
      )}
    </main>
  );
}

function topFactor(f: Record<string, number> | null | undefined): [string, number] | null {
  if (!f) return null;
  const e = Object.entries(f).sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))[0];
  return e ?? null;
}

function countBy(rows: any[], key: (r: any) => string): [string, number][] {
  const m = new Map<string, number>();
  for (const r of rows) m.set(key(r), (m.get(key(r)) ?? 0) + 1);
  return [...m.entries()].sort((a, b) => b[1] - a[1]).slice(0, 10);
}
