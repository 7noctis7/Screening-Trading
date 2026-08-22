"use client";
// Positions — écran de contrôle de RÉPLICATION : positions réellement détenues
// (Alpaca + place crypto active). Le nom de la place vient des données, jamais du code.
// confrontées à la cible du preset (poids modèle). L'écart dit ce que le prochain rebalancement
// corrigera. 100 % données réelles côté « réel » ; la cible est le modèle (étiquetée comme telle).
import { StepBanner } from "@/components/Pipeline";
import { useMemo, useState } from "react";
import { usePositions } from "@/lib/api";
import { TechnicalChart } from "@/components/TechnicalChart";
import { MetricCard } from "@/components/MetricCard";
import { SortableTable, type Col } from "@/components/SortableTable";
import { PageSkeleton } from "@/components/ui";
import { compteCrypto, envVenue, nomVenue } from "@/lib/venue";

const usd = (x?: number | null) => (x ?? 0).toLocaleString("fr-FR", { maximumFractionDigits: 2 });
const pctf = (x?: number | null, d = 1) => (x == null ? "—" : `${(x * 100).toFixed(d)}%`);
const norm = (s: string) => (s || "").toUpperCase().replace(/[/\-_]/g, "").replace(/(USDT|USDC|USD)$/, "");

// Bande de non-trading du preset (3 %) : en-deçà, l'écart est du bruit qu'on ne trade pas.
const BAND = 0.03;

type Row = {
  symbol: string; broker: string; wReal: number | null; wTarget: number | null;
  gap: number | null; qty: number | null; value: number | null;
  pnl: number | null; pnlPct: number | null; earningsDays: number | null; hasChart: boolean;
};

// Fusionne positions réelles et cible preset par actif (poids par POCHE : chaque poids est
// rapporté au capital de SON broker, comme le fait le preset — comparabilité stricte).
function buildRows(pos: any[], alloc: any[], accounts: any, earnings: any[]): Row[] {
  const aEq = accounts?.alpaca?.equity || 0, bEq = compteCrypto(accounts)?.equity || 0;
  const vName = nomVenue(accounts);
  const capOf = (broker: string) => (broker && vName && broker.toLowerCase() === vName.toLowerCase() ? bEq : aEq);
  const eDays = new Map(earnings.map((e: any) => [norm(e.symbol), e.days]));
  const bySym = new Map<string, Row>();
  for (const p of pos) {
    const cap = capOf(p.broker ?? "");
    bySym.set(norm(p.symbol), {
      symbol: p.symbol, broker: p.broker ?? "—",
      wReal: cap > 0 && p.market_value != null ? p.market_value / cap : null,
      wTarget: null, gap: null, qty: p.qty ?? null, value: p.market_value ?? null,
      pnl: p.pnl ?? null, pnlPct: p.pnl_pct ?? null,
      earningsDays: eDays.get(norm(p.symbol)) ?? null, hasChart: false,
    });
  }
  for (const a of alloc) {
    const k = norm(a.broker_symbol || a.symbol);
    const r = bySym.get(k) ?? bySym.get(norm(a.symbol));
    if (r) r.wTarget = a.weight ?? null;
    else bySym.set(k, {
      symbol: a.symbol, broker: a.broker ?? "—", wReal: 0, wTarget: a.weight ?? null,
      gap: null, qty: null, value: null, pnl: null, pnlPct: null,
      earningsDays: eDays.get(norm(a.symbol)) ?? null, hasChart: false,
    });
  }
  const rows = [...bySym.values()];
  for (const r of rows) r.gap = r.wReal != null && r.wTarget != null ? r.wReal - r.wTarget
    : r.wReal != null && r.wTarget == null ? r.wReal : null;
  return rows.sort((x, y) => (y.value ?? 0) - (x.value ?? 0));
}

// Barre divergente ± centrée (écart de réplication). Orange au-delà de la bande de 3 %.
function GapBar({ gap }: { gap: number | null }) {
  if (gap == null) return <span className="text-muted2">n/d</span>;
  const out = Math.abs(gap) > BAND;
  const w = Math.min(50, Math.abs(gap) * 500);           // 10 % d'écart = barre pleine
  const col = out ? "#f59e0b" : "var(--muted2)";
  return (
    <span className="inline-flex items-center gap-1.5 justify-end w-full">
      <span className="mono text-xs" style={{ color: out ? "#f59e0b" : undefined }}>
        {gap >= 0 ? "+" : ""}{(gap * 100).toFixed(1)}%</span>
      <span className="relative inline-block h-2 w-[104px] rounded-full shrink-0"
        style={{ background: "var(--surface2)" }} title={out ? "Hors bande de non-trading (3 %) → le rebalancement le corrigera" : "Dans la bande de 3 % (bruit, non tradé)"}>
        <span className="absolute top-0 bottom-0 left-1/2 w-px" style={{ background: "var(--border2)" }} />
        <span className="absolute top-0 bottom-0 rounded-full"
          style={gap >= 0 ? { left: "50%", width: `${w}%`, background: col }
            : { right: "50%", width: `${w}%`, background: col }} />
      </span>
    </span>
  );
}

export default function Positions() {
  const { data } = usePositions();
  const [sel, setSel] = useState<string | null>(null);
  const pos = data?.real_positions ?? [];
  // Plancher de ligne, aligné sur packages/execution/rebalance_plan (QUANT_MIN_POSITION).
  const PLANCHER = 500;
  const sousPlancher = pos
    .filter((p: any) => Math.abs(Number(p?.market_value) || 0) < PLANCHER)
    .sort((a: any, b: any) => (Number(b.market_value) || 0) - (Number(a.market_value) || 0));
  const totalPlancher = sousPlancher.reduce(
    (t: number, p: any) => t + (Number(p?.market_value) || 0), 0);
  const alloc = data?.preset_allocation ?? [];
  const earnings = data?.earnings_risk ?? [];
  const series = data?.series ?? {}, markers = data?.markers ?? {};
  const acc = data?.accounts ?? {};
  const rows = useMemo(() => {
    const r = buildRows(pos, alloc, acc, earnings);
    for (const x of r) x.hasChart = !!series[x.symbol];
    return r;
  }, [pos, alloc, acc, earnings, series]);
  if (!data) return <PageSkeleton />;

  const aEq = acc.alpaca?.equity ?? 0, bEq = compteCrypto(acc)?.equity ?? 0;
  const vName = nomVenue(acc), vCrypto = compteCrypto(acc);
  const mv = pos.reduce((a: number, r: any) => a + (r.market_value ?? 0), 0);
  const pnl = pos.reduce((a: number, r: any) => a + (r.pnl ?? 0), 0);
  // Concentration (sur les poids réels, toutes poches confondues rapportées au total)
  const wTot = pos.map((p: any) => (mv > 0 ? (p.market_value ?? 0) / mv : 0));
  const hhi = wTot.reduce((a: number, w: number) => a + w * w, 0);
  const nEff = hhi > 0 ? 1 / hhi : 0;
  const top3 = [...wTot].sort((a, b) => b - a).slice(0, 3).reduce((a, b) => a + b, 0);
  const nOut = rows.filter((r) => r.gap != null && Math.abs(r.gap) > BAND).length;

  const cols: Col[] = [
    { key: "symbol", label: "Actif", render: (v, r) => (
        <span className="inline-flex items-center gap-1.5">
          <span className={r.hasChart ? "text-accent border-b border-dotted border-border" : ""}>{v}</span>
          {r.earningsDays != null && (
            <span className="text-[10px] px-1.5 py-0.5 rounded font-sans"
              style={{ background: "color-mix(in srgb, #f59e0b 18%, transparent)", color: "#f59e0b" }}
              title={`Résultats dans ${r.earningsDays} j — risque binaire (blackout preset)`}>
              📅 {r.earningsDays} j</span>)}
        </span>) },
    { key: "broker", label: "Broker", render: (v) => <span className="font-sans text-xs">{v}</span> },
    { key: "wReal", label: "Poids réel", num: true, align: "right",
      render: (v) => <span className="mono">{pctf(v)}</span>, csv: (v) => v == null ? "" : +(v * 100).toFixed(2) },
    { key: "wTarget", label: "Cible preset", num: true, align: "right",
      render: (v) => v == null ? <span className="text-muted2" title="Hors cible modèle (position héritée ou manuelle)">hors cible</span>
        : <span className="mono">{pctf(v)}</span>, csv: (v) => v == null ? "" : +(v * 100).toFixed(2) },
    { key: "gap", label: "Écart", num: true, align: "right",
      render: (v) => <GapBar gap={v} />, csv: (v) => v == null ? "" : +(v * 100).toFixed(2) },
    { key: "value", label: "Valeur", num: true, align: "right",
      render: (v) => v == null ? <span className="text-muted2">—</span> : <span className="mono">${usd(v)}</span>,
      csv: (v) => v == null ? "" : +v.toFixed(2) },
    { key: "pnl", label: "P&L", num: true, align: "right",
      render: (v, r) => v == null ? <span className="text-muted2">—</span> : (
        <span className="mono" style={{ color: v >= 0 ? "var(--pos)" : "#ef4444" }}>
          ${usd(v)}{r.pnlPct != null && <span className="text-[11px] text-muted2"> · {pctf(r.pnlPct)}</span>}</span>),
      csv: (v) => v == null ? "" : +v.toFixed(2) },
  ];

  return (
    <main className="max-w-5xl mx-auto p-6 space-y-4">
      <h1 className="text-xl font-semibold tracking-tight">Positions
        <span className="ml-2 text-xs font-normal px-2 py-0.5 rounded-full align-middle"
          style={{ background: "color-mix(in srgb, #22c55e 16%, transparent)", color: "#22c55e" }}>RÉEL · Alpaca + {vName}</span></h1>
      <p className="text-muted text-xs">Positions <b>réellement détenues</b>, confrontées à la <b>cible du preset</b> (modèle).
        L'écart montre ce que le prochain rebalancement corrigera (bande de non-trading : {BAND * 100} %). Aucun chiffre inventé : « n/d » si un compte est déconnecté.</p>
      <StepBanner active="portfolio" />

      {!data.connected ? (
        <section className="card p-6 text-center">
          <p className="text-sm">Aucun compte connecté.</p>
          <p className="text-muted text-xs mt-1">Renseigne <code>ALPACA_API_KEY</code>/<code>ALPACA_API_SECRET</code> et/ou <code>{envVenue(acc).join(" / ")}</code> dans <code>.env</code>, puis relance l'API.</p>
          {(acc.alpaca?.error || vCrypto?.error) && (
            <p className="text-muted2 text-[11px] mt-2">Alpaca : {acc.alpaca?.error || "ok"} · {vName} : {vCrypto?.error || "ok"}</p>)}
        </section>
      ) : (
      <>
      <section className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricCard label="Capital réel" value={`$${usd(aEq + bEq)}`} />
        <MetricCard label="Valeur positions" value={`$${usd(mv)}`} />
        <MetricCard label="Gain / perte en cours" terme="P&L latent" value={`$${usd(pnl)}`} tone={pnl >= 0 ? "pos" : "neg"}
          explication="Ce qu'on gagnerait ou perdrait en vendant tout maintenant." />
        <MetricCard label="Vraie diversification" terme="N effectif" value={nEff ? nEff.toFixed(1) : "n/d"}
          explication="Nombre de positions RÉELLEMENT indépendantes. Dix lignes très corrélées en valent trois." />
      </section>
      <section className="card p-3 flex flex-wrap gap-x-6 gap-y-1 text-xs text-muted">
        <span title="Somme des poids au carré (HHI) : 1/N si équipondéré. N effectif = 1/HHI.">
          Concentration : HHI <b className="mono text-fg">{hhi ? hhi.toFixed(3) : "n/d"}</b> · top 3 <b className="mono text-fg">{pctf(top3)}</b> sur {pos.length} lignes</span>
        <span>Poches : Alpaca <b className="mono text-fg">${usd(aEq)}</b> · {vName} <b className="mono text-fg">${usd(bEq)}</b></span>
        <span title="Lignes dont l'écart réel−cible dépasse la bande de non-trading de 3 %">
          Hors bande ({BAND * 100} %) : <b className="mono" style={{ color: nOut ? "#f59e0b" : "var(--pos)" }}>{nOut}</b> ligne{nOut > 1 ? "s" : ""}</span>
      </section>

      {/* LIGNES SOUS LE PLANCHER — répond directement à « pourquoi j'ai ces positions ? ».
          Ce sont des restes d'une allocation précédente : soldées en MONTANT, elles laissaient
          une miette, et la miette passait ensuite sous la bande d'inaction, donc plus jamais
          vendue. Le prochain rééquilibrage les solde en QUANTITÉ. */}
      {sousPlancher.length > 0 && (
        <section className="card p-4" style={{ borderColor: "#f59e0b" }}>
          <div className="flex flex-wrap items-baseline gap-x-3">
            <h2 className="text-sm uppercase tracking-wide text-muted">Lignes trop petites pour compter</h2>
            <span className="mono text-sm" style={{ color: "#f59e0b" }}>
              {sousPlancher.length} ligne{sousPlancher.length > 1 ? "s" : ""} · ${usd(totalPlancher)}
            </span>
          </div>
          <p className="text-muted text-xs mt-1">
            Sous le plancher de <b>${usd(PLANCHER)}</b> par ligne. Ce sont des restes d'allocations
            précédentes : la sortie se faisait en <i>montant</i>, le cours bougeait entre la
            cotation et l'exécution, il restait une miette — et cette miette, plus petite que la
            bande d'inaction, n'était ensuite plus jamais vendue. Le prochain rééquilibrage les
            solde en <i>quantité</i>, donc intégralement.
          </p>
          <div className="flex flex-wrap gap-1.5 mt-3">
            {sousPlancher.map((p: any) => (
              <span key={p.symbol} className="text-xs px-2 py-0.5 rounded-full border border-border mono">
                {p.symbol} <span className="text-muted2">${usd(p.market_value)}</span>
              </span>
            ))}
          </div>
        </section>
      )}

      {sel && series[sel] && (
        <section className="card p-4">
          <div className="flex justify-between items-center mb-2">
            <h2 className="text-sm uppercase tracking-wide text-muted">Graphique technique — {sel}</h2>
            <button onClick={() => setSel(null)} className="text-muted hover:text-fg text-sm">✕</button>
          </div>
          <TechnicalChart data={series[sel]} markers={markers[sel] ?? []} />
        </section>
      )}

      <section className="card p-4">
        <div className="flex items-center justify-between flex-wrap gap-2 mb-1">
          <h2 className="text-sm uppercase tracking-wide text-muted">Réel vs cible — écart de réplication</h2>
          <span className="text-[11px] text-muted2">réel = brokers · cible = preset (poids par poche)</span>
        </div>
        {rows.length === 0 ? (
          <p className="text-muted text-sm">Aucune position ni cible. Passe des ordres en paper : <code>make live-go</code>.</p>
        ) : (
          <div onClickCapture={(e) => {
            const tr = (e.target as HTMLElement).closest("tr");
            const sym = tr?.querySelector("td")?.textContent?.trim().split(/\s/)[0];
            if (sym && series[sym]) setSel(sym);
          }}>
            <SortableTable rows={rows} cols={cols} filterKeys={["symbol", "broker"]}
              csvName="positions_reel_vs_cible.csv" initialSort={{ key: "value", dir: "desc" }} />
          </div>
        )}
        <p className="text-muted2 text-[11px] mt-2">Clique un actif (souligné) pour son graphique + signaux réels.
          « hors cible » = détenu mais absent du modèle (hérité/manuel) — candidat naturel à la sortie.</p>
      </section>
      </>)}
    </main>
  );
}
