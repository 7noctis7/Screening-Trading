"use client";
// FICHE D'UN TITRE — l'objet « Instrument » de l'ontologie : UN ticker, TOUTES ses relations
// (score screener, facteurs, fondamentaux, sentiment, conviction, position réelle, cible) au
// même endroit, et surtout LA DÉCISION qui en découle. Jointures côté client sur les sections
// déjà chargées → marche en statique comme en dynamique, zéro appel nouveau. Donnée absente
// → « non mesuré » (jamais inventé, et un étage non mesuré ne vote pas).
import { Suspense, useMemo } from "react";
import { useSearchParams } from "next/navigation";
import {
  useConviction, useFundamentals, usePositions, useScreen, useScreener, useSentiment,
} from "@/lib/api";
import { PageSkeleton, EmptyState } from "@/components/ui";
import { MetricCard } from "@/components/MetricCard";
import { decide, type Decision, type Etage } from "@/lib/decision";
import { VERDICT_LABEL } from "@/lib/plain";

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

const TON: Record<string, string> = { bon: "var(--pos)", moyen: "#eab308", prudence: "#f43f5e", inconnu: "#9aa1ad" };

// Un étage de l'entonnoir : la question posée, ce qu'on a vu, ce qu'on en conclut.
function EtageLigne({ e }: { e: Etage }) {
  const puce = e.vote == null ? "·" : e.vote === 1 ? "✓" : e.vote === -1 ? "✗" : "~";
  const col = e.vote == null ? "#9aa1ad" : e.vote === 1 ? "var(--pos)" : e.vote === -1 ? "#f43f5e" : "#eab308";
  return (
    <li className="flex gap-3 py-2 border-t border-border first:border-t-0">
      <span className="mono w-4 shrink-0 text-center" style={{ color: col }} aria-hidden>{puce}</span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-baseline gap-x-2">
          <span className="text-sm font-medium">{e.titre}</span>
          {e.veto && <span className="text-[10px] uppercase tracking-wide px-1.5 py-0.5 rounded border border-border text-muted2">bloquant</span>}
          <span className="mono text-sm ml-auto" style={{ color: col }}>{e.valeur ?? "non mesuré"}</span>
        </div>
        <div className="text-muted2 text-xs">{e.question}</div>
        <div className="text-muted text-xs mt-0.5">{e.lecture}</div>
      </div>
    </li>
  );
}

// LE BLOC QUI MANQUAIT : de la donnée à l'ordre, en une seule lecture.
function BlocDecision({ d }: { d: Decision }) {
  const col = TON[d.verdict];
  return (
    <section className="card p-5" style={{ borderColor: col }}>
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h2 className="text-sm uppercase tracking-wide text-muted">La décision</h2>
        <span className="text-lg font-semibold" style={{ color: col }}>{d.titre}</span>
        <span className="text-muted2 text-xs ml-auto">{VERDICT_LABEL[d.verdict]} · {d.mesures}/6 étages mesurés</span>
      </div>
      <p className="text-sm mt-2">{d.resume}</p>

      <ol className="mt-3">{d.etages.map((e) => <EtageLigne key={e.cle} e={e} />)}</ol>

      <div className="mt-4 pt-3 border-t border-border">
        <div className="text-muted text-[11px] uppercase tracking-wide mb-1">Et concrètement ?</div>
        <p className="text-sm">{d.ordre.phrase}</p>
        <p className="text-muted2 text-[11px] mt-1">
          Portefeuille modèle en simulation (paper). Un étage sans donnée ne vote pas et n'est jamais
          remplacé par une valeur moyenne — c'est pourquoi le compteur d'étages mesurés est affiché.
        </p>
      </div>
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
  const { data: conv } = useConviction();

  const o = useMemo(() => {
    const find = (rows: any[] | undefined, k = "symbol") =>
      (rows ?? []).find((r) => (r?.[k] || "").toUpperCase() === sym) ?? null;
    return {
      screen: find(screen?.rows), rank: find(rank?.rows),
      fund: find(fund?.rows), sent: find(sent?.rows),
      pos: (pos?.real_positions ?? []).find((p: any) => norm(p.symbol) === norm(sym)) ?? null,
      tgt: (pos?.preset_allocation ?? []).find((a: any) => norm(a.symbol) === norm(sym)) ?? null,
      conv: find(conv?.rows),
      // Valeur investie du portefeuille = somme des positions réelles. Sert uniquement à
      // convertir un écart de poids en euros ; absente, l'écart reste en points.
      valeurPtf: (pos?.real_positions ?? []).reduce(
        (t: number, p: any) => t + (Number(p?.market_value) || 0), 0) || null,
    };
  }, [sym, screen, rank, fund, sent, pos, conv]);

  // Poids détenu aujourd'hui, mesuré sur la même base que la cible (part de l'investi).
  const decision = useMemo(() => decide({
    piotroski: o.fund?.piotroski, altmanZ: o.fund?.altman_z, margeSecurite: o.fund?.margin_of_safety,
    ret12m: o.screen?.ret_12m, conviction: o.conv?.conviction, sentiment: o.sent?.score,
    poidsCible: o.conv?.target_weight ?? o.tgt?.weight ?? null,
    poidsActuel: o.pos && o.valeurPtf ? (Number(o.pos.market_value) || 0) / o.valeurPtf : (o.pos ? null : 0),
    valeurPortefeuille: o.valeurPtf,
  }), [o]);

  if (!sym) return <EmptyState title="Aucun instrument" hint="Ouvre cette fiche depuis un ticker (screener, positions…) ou ajoute ?sym=NVDA à l'URL." />;
  if (!screen || !pos) return <PageSkeleton />;
  const known = o.screen || o.rank || o.fund || o.pos || o.tgt;

  return (
    <main className="max-w-4xl mx-auto p-6 space-y-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight mono">{sym}
          {o.screen?.name && <span className="ml-3 text-base font-normal text-muted font-sans">{o.screen.name}</span>}</h1>
        <p className="text-muted2 text-xs mt-1">{o.screen?.sector || o.fund?.sector || "—"} · toutes les données du site sur ce titre, jusqu'à la décision</p>
      </div>
      {!known ? (
        <EmptyState title={`${sym} inconnu du snapshot`} hint="Hors univers courant (mobile_universe) — vérifie l'orthographe ou l'univers." />
      ) : (
        <>
          <section className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <MetricCard label="Note du filtre" value={o.screen?.score != null ? o.screen.score.toFixed(2) : "n/d"} />
            <MetricCard label="Évolution sur 1 an" value={pct(o.screen?.ret_12m)} tone={(o.screen?.ret_12m ?? 0) >= 0 ? "pos" : "neg"} />
            <MetricCard label="Ce que je détiens" value={o.pos ? usd(o.pos.market_value) : "aucune"} />
            <MetricCard label="Ce que je devrais détenir" value={o.tgt?.weight != null ? `${(o.tgt.weight * 100).toFixed(1)}%` : "hors cible"} />
          </section>

          <BlocDecision d={decision} />

          {o.rank?.factors && Object.keys(o.rank.factors).length > 0 && (
            <Bloc title="Le détail du score" source="ranking multi-facteur · z-scores">
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

          <Bloc title="Santé de l'entreprise" source="valeur estimée (DCF) · qualité des comptes · risque de faillite">
            {o.fund ? (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                <div><div className="text-muted text-[11px]">Note globale</div><div className="mono text-lg">{o.fund.combined_score ?? "n/d"}</div></div>
                <div><div className="text-muted text-[11px]">Qualité des comptes</div><div className="mono text-lg">{o.fund.piotroski ?? "n/d"}<span className="text-muted2 text-xs">/9</span></div></div>
                <div><div className="text-muted text-[11px]">Distance à la faillite</div><div className="mono text-lg">{o.fund.altman_z ?? "n/d"}</div></div>
                <div><div className="text-muted text-[11px]">Décote sur la valeur estimée</div><div className="mono text-lg">{pct(o.fund.margin_of_safety)}</div></div>
              </div>
            ) : <p className="text-muted2 text-sm">n/d — pas de fondamentaux pour cet actif (crypto/ETF ou hors couverture).</p>}
          </Bloc>

          <Bloc title="Ce que disent les nouvelles" source="fils de presse gratuits · analyse automatique du ton">
            {o.sent ? (
              <p className="text-sm"><span className="mono" style={{ color: (o.sent.score ?? 0) >= 0 ? "var(--pos)" : "#f43f5e" }}>
                score {o.sent.score?.toFixed?.(2) ?? o.sent.score}</span>
                {o.sent.headline && <span className="text-muted"> · {o.sent.headline}</span>}</p>
            ) : <p className="text-muted2 text-sm">n/d — aucune news récente pour cet actif.</p>}
          </Bloc>

          {o.pos && (
            <Bloc title="Ma position" source={`${o.pos.broker ?? "broker"} · paper`}>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm mono">
                <div><div className="text-muted text-[11px] font-sans">Quantité</div>{(o.pos.qty ?? 0).toFixed(4)}</div>
                <div><div className="text-muted text-[11px] font-sans">Prix d'achat moyen</div>{usd(o.pos.avg_price)}</div>
                <div><div className="text-muted text-[11px] font-sans">Valeur</div>{usd(o.pos.market_value)}</div>
                <div><div className="text-muted text-[11px] font-sans">Gain / perte</div>
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
