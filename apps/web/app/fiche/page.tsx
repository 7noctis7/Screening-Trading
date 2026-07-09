"use client";
// FICHE 360 — l'objet « Instrument » de l'ontologie : UN ticker, TOUTES ses relations
// (score screener, facteurs, fondamentaux, sentiment, position réelle, cible preset) au même
// endroit. Jointures côté client sur les sections déjà chargées → marche en statique comme en
// dynamique, zéro appel nouveau. Donnée absente → « n/d » (jamais inventé).
import { Suspense, useMemo } from "react";
import { useSearchParams } from "next/navigation";
import {
  useFundamentals, usePositions, useScreen, useScreener, useSentiment,
} from "@/lib/api";
import { PageSkeleton, EmptyState } from "@/components/ui";
import { MetricCard } from "@/components/MetricCard";

const usd = (x?: number | null) => (x == null ? "n/d" : `$${x.toLocaleString("fr-FR", { maximumFractionDigits: 2 })}`);
const pct = (x?: number | null) => (x == null ? "n/d" : `${x >= 0 ? "+" : ""}${(x * 100).toFixed(1)}%`);
const norm = (s: string) => (s || "").toUpperCase().replace(/[/\-]/g, "").replace(/(USDT|USDC|USD)$/, "");

function Bloc({ title, source, children }: { title: string; source: string; children: React.ReactNode }) {
  return (
    <section className="card p-4">
      <div className="flex items-center justify-between flex-wrap gap-2 mb-2">
        <h2 className="text-sm uppercase tracking-wide text-muted">{title}</h2>
        <span className="text-[11px] text-muted2">{source}</span>
      </div>
      {children}
    </section>
  );
}

function Fiche() {
  const sym = (useSearchParams().get("sym") || "").toUpperCase();
  const { data: screen } = useScreen();
  const { data: rank } = useScreener();
  const { data: fund } = useFundamentals();
  const { data: sent } = useSentiment();
  const { data: pos } = usePositions();

  const o = useMemo(() => {
    const find = (rows: any[] | undefined, k = "symbol") =>
      (rows ?? []).find((r) => (r?.[k] || "").toUpperCase() === sym) ?? null;
    return {
      screen: find(screen?.rows), rank: find(rank?.rows),
      fund: find(fund?.rows), sent: find(sent?.rows),
      pos: (pos?.real_positions ?? []).find((p: any) => norm(p.symbol) === norm(sym)) ?? null,
      tgt: (pos?.preset_allocation ?? []).find((a: any) => norm(a.symbol) === norm(sym)) ?? null,
    };
  }, [sym, screen, rank, fund, sent, pos]);

  if (!sym) return <EmptyState title="Aucun instrument" hint="Ouvre cette fiche depuis un ticker (screener, positions…) ou ajoute ?sym=NVDA à l'URL." />;
  if (!screen || !pos) return <PageSkeleton />;
  const known = o.screen || o.rank || o.fund || o.pos || o.tgt;

  return (
    <main className="max-w-4xl mx-auto p-6 space-y-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight mono">{sym}
          {o.screen?.name && <span className="ml-3 text-base font-normal text-muted font-sans">{o.screen.name}</span>}</h1>
        <p className="text-muted2 text-xs mt-1">{o.screen?.sector || o.fund?.sector || "—"} · fiche 360 (toutes les relations de l'objet, aucune donnée inventée)</p>
      </div>
      {!known ? (
        <EmptyState title={`${sym} inconnu du snapshot`} hint="Hors univers courant (mobile_universe) — vérifie l'orthographe ou l'univers." />
      ) : (
        <>
          <section className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <MetricCard label="Score screener" value={o.screen?.score != null ? o.screen.score.toFixed(2) : "n/d"} />
            <MetricCard label="Ret 12 m" value={pct(o.screen?.ret_12m)} tone={(o.screen?.ret_12m ?? 0) >= 0 ? "pos" : "neg"} />
            <MetricCard label="Position réelle" value={o.pos ? usd(o.pos.market_value) : "aucune"} />
            <MetricCard label="Cible preset" value={o.tgt?.weight != null ? `${(o.tgt.weight * 100).toFixed(1)}%` : "hors cible"} />
          </section>

          {o.rank?.factors && Object.keys(o.rank.factors).length > 0 && (
            <Bloc title="Pourquoi ce score (facteurs)" source="ranking multi-facteur · z-scores">
              <div className="flex flex-wrap gap-2">
                {Object.entries(o.rank.factors as Record<string, number>)
                  .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))
                  .map(([k, v]) => (
                    <span key={k} className="text-xs px-2.5 py-1 rounded-lg border border-border mono"
                      style={{ color: v >= 0 ? "var(--pos)" : "#f43f5e" }}>{k} {v >= 0 ? "+" : ""}{v.toFixed(2)}</span>
                  ))}
              </div>
            </Bloc>
          )}

          <Bloc title="Fondamentaux" source="DCF · Piotroski · Altman (yfinance/SEC)">
            {o.fund ? (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                <div><div className="text-muted text-[11px]">Note combinée</div><div className="mono text-lg">{o.fund.combined_score ?? "n/d"}</div></div>
                <div><div className="text-muted text-[11px]">Piotroski</div><div className="mono text-lg">{o.fund.piotroski ?? "n/d"}<span className="text-muted2 text-xs">/9</span></div></div>
                <div><div className="text-muted text-[11px]">Altman Z</div><div className="mono text-lg">{o.fund.altman_z ?? "n/d"}</div></div>
                <div><div className="text-muted text-[11px]">Marge de sécurité (DCF)</div><div className="mono text-lg">{pct(o.fund.margin_of_safety)}</div></div>
              </div>
            ) : <p className="text-muted2 text-sm">n/d — pas de fondamentaux pour cet actif (crypto/ETF ou hors couverture).</p>}
          </Bloc>

          <Bloc title="Sentiment & news" source="RSS gratuit · FinBERT/lexique">
            {o.sent ? (
              <p className="text-sm"><span className="mono" style={{ color: (o.sent.score ?? 0) >= 0 ? "var(--pos)" : "#f43f5e" }}>
                score {o.sent.score?.toFixed?.(2) ?? o.sent.score}</span>
                {o.sent.headline && <span className="text-muted"> · {o.sent.headline}</span>}</p>
            ) : <p className="text-muted2 text-sm">n/d — aucune news récente pour cet actif.</p>}
          </Bloc>

          {o.pos && (
            <Bloc title="Ma position (réel broker)" source={`${o.pos.broker ?? "broker"} · paper`}>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm mono">
                <div><div className="text-muted text-[11px] font-sans">Qté</div>{(o.pos.qty ?? 0).toFixed(4)}</div>
                <div><div className="text-muted text-[11px] font-sans">PRU</div>{usd(o.pos.avg_price)}</div>
                <div><div className="text-muted text-[11px] font-sans">Valeur</div>{usd(o.pos.market_value)}</div>
                <div><div className="text-muted text-[11px] font-sans">P&L</div>
                  <span style={{ color: (o.pos.pnl ?? 0) >= 0 ? "var(--pos)" : "#f43f5e" }}>{usd(o.pos.pnl)} ({pct(o.pos.pnl_pct)})</span></div>
              </div>
            </Bloc>
          )}
          <p className="text-muted2 text-[10px]">Aide à la décision — pas un conseil en investissement.</p>
        </>
      )}
    </main>
  );
}

export default function FichePage() {
  return <Suspense fallback={<PageSkeleton />}><Fiche /></Suspense>;
}
