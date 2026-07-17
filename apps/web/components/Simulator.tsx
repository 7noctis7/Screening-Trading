"use client";
import { useMemo, useState } from "react";
import { useDashboard } from "@/lib/api";
import { McFan, type FanData } from "@/components/McFan";

// SIMULATEUR MONTE CARLO — 100 % NAVIGATEUR (marche aussi sur le site statique, 0 API).
// Bootstrap par BLOCS des rendements quotidiens PASSÉS (blocs = préserve le clustering
// de volatilité ; iid le casse et sous-estime les queues). Une distribution
// d'incertitude conditionnelle au passé — PAS une prédiction. Aucune donnée inventée :
// sources = courbe backtest du preset (modélisé) ou courbe réelle broker si assez longue.

function mulberry32(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const q = (sorted: number[], p: number) =>
  sorted[Math.min(sorted.length - 1, Math.max(0, Math.round((p / 100) * (sorted.length - 1))))];

type SimOut = { fan: FanData; median: number; p5: number; p95: number; es95: number;
  cagrMed: number; pLoss: number; pRuin: number; pRuinSe: number;
  ddMed: number; ddP95: number; ddWorst: number };

function simulate(rets: number[], horizon: number, nSims: number, block: number,
                  capital: number, feesPct: number, ruin: number, seed: number): SimOut {
  const rng = mulberry32(seed);
  const drag = Math.pow(1 + feesPct / 100, 1 / 252) - 1;      // frais annuels → ponction/jour
  const nPts = Math.min(40, horizon);
  const idx = Array.from({ length: nPts }, (_, k) => Math.round(((k + 1) / nPts) * horizon) - 1);
  const bands: number[][] = idx.map(() => []);
  const finals: number[] = [], dds: number[] = [];
  const n = rets.length, pNew = 1 / Math.max(1, block);
  let ruined = 0;
  for (let s = 0; s < nSims; s++) {
    let v = capital, peak = capital, dd = 0, j = 0, i = 0;
    for (let t = 0; t < horizon; t++) {
      // Bootstrap STATIONNAIRE (Politis-Romano) : longueur de bloc géométrique
      // d'espérance `block` — pas d'artefact de bord des blocs fixes. block=1 ⇔ iid.
      i = t === 0 || rng() < pNew ? Math.floor(rng() * n) : (i + 1) % n;
      v *= 1 + rets[i] - drag;
      if (v > peak) peak = v;
      const d = v / peak - 1;
      if (d < dd) dd = d;
      if (j < nPts && t === idx[j]) { bands[j].push(v); j++; }
    }
    finals.push(v); dds.push(dd);
    if (dd <= ruin) ruined++;
  }
  for (const b of bands) b.sort((a, z) => a - z);
  finals.sort((a, z) => a - z); dds.sort((a, z) => a - z);
  const tail = finals.slice(0, Math.max(1, Math.ceil(0.05 * nSims)));   // pires 5 %
  const pR = ruined / nSims, med = q(finals, 50);
  return {
    fan: { steps: idx.map((i2) => i2 + 1),
      p5: bands.map((b) => q(b, 5)), p25: bands.map((b) => q(b, 25)),
      p50: bands.map((b) => q(b, 50)), p75: bands.map((b) => q(b, 75)),
      p95: bands.map((b) => q(b, 95)) },
    median: med, p5: q(finals, 5), p95: q(finals, 95),
    es95: tail.reduce((a, z) => a + z, 0) / tail.length,       // CVaR : moyenne de la queue 5 %
    cagrMed: Math.pow(med / capital, 252 / horizon) - 1,
    pLoss: finals.filter((v) => v < capital).length / nSims,
    pRuin: pR,
    pRuinSe: Math.sqrt(Math.max(0, pR * (1 - pR)) / nSims),    // erreur d'échantillonnage MC
    ddMed: q(dds, 50), ddP95: q(dds, 5),                       // p95 du PIRE cas = 5e centile
    ddWorst: dds[0],
  };
}

const Sel = ({ label, value, onChange, opts }: {
  label: string; value: string; onChange: (v: string) => void; opts: [string, string][] }) => (
  <label className="flex items-center gap-1.5 text-xs text-muted">
    {label}
    <select value={value} onChange={(e) => onChange(e.target.value)}
      className="rounded-md border border-border px-1.5 py-1 text-xs mono text-fg"
      style={{ background: "var(--surface)" }}>
      {opts.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
    </select>
  </label>
);

const pctF = (x: number) => `${(x * 100).toFixed(1)}%`;
const usd = (x: number) => `${Math.round(x).toLocaleString("fr-FR")} $`;

export function Simulator() {
  const { data: d } = useDashboard();
  const [src, setSrc] = useState("model");
  const [horizon, setHorizon] = useState("252");
  const [nSims, setNSims] = useState("1000");
  const [block, setBlock] = useState("10");
  const [fees, setFees] = useState("0");
  const [capital, setCapital] = useState("10000");
  const [seed, setSeed] = useState(1);
  const [table, setTable] = useState(false);

  const real: number[] = (d?.real_portfolio?.curve ?? [])
    .map((p: any) => Number(p?.v)).filter((v: number) => v > 0);
  const model: number[] = (d?.equity ?? []).filter((v: number) => v > 0);
  const curve = src === "real" ? real : model;
  const rets = useMemo(() => curve.slice(1).map((v, i) => v / curve[i] - 1), [curve]);

  const out = useMemo(() => {
    if (rets.length < 60) return null;
    return simulate(rets, +horizon, +nSims, +block, +capital || 10000, +fees || 0, -0.5, seed);
  }, [rets, horizon, nSims, block, capital, fees, seed]);

  if (!d) return null;
  return (
    <section className="card p-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h2 className="text-sm uppercase tracking-wide text-muted">Simulateur Monte Carlo (navigateur)</h2>
        <span className="text-[11px] px-2 py-0.5 rounded-full uppercase tracking-[0.08em] font-semibold"
          style={{ background: "color-mix(in srgb, var(--warn) 18%, transparent)", color: "var(--warn)" }}>
          {src === "real" ? "Rendements réels (historique court)" : "Modélisé (backtest)"}
        </span>
      </div>
      {/* filtres : une seule rangée au-dessus du graphe */}
      <div className="flex items-center gap-3 flex-wrap mt-3">
        <Sel label="Source" value={src} onChange={setSrc}
          opts={[["model", "Backtest preset"], ...(real.length >= 60 ? [["real", "Portefeuille réel"] as [string, string]] : [])]} />
        <Sel label="Horizon" value={horizon} onChange={setHorizon}
          opts={[["63", "3 mois"], ["126", "6 mois"], ["252", "1 an"], ["504", "2 ans"]]} />
        <Sel label="Itérations" value={nSims} onChange={setNSims}
          opts={[["500", "500"], ["1000", "1 000"], ["2000", "2 000"]]} />
        <Sel label="Bootstrap" value={block} onChange={setBlock}
          opts={[["10", "stationnaire ~10 j"], ["21", "stationnaire ~21 j"], ["1", "iid (naïf)"]]} />
        <label className="flex items-center gap-1.5 text-xs text-muted">Capital
          <input value={capital} onChange={(e) => setCapital(e.target.value.replace(/[^\d]/g, ""))}
            className="w-20 rounded-md border border-border px-1.5 py-1 text-xs mono text-fg"
            style={{ background: "var(--surface)" }} inputMode="numeric" /> $</label>
        <label className="flex items-center gap-1.5 text-xs text-muted">Frais/an
          <input value={fees} onChange={(e) => setFees(e.target.value.replace(/[^\d.]/g, ""))}
            className="w-12 rounded-md border border-border px-1.5 py-1 text-xs mono text-fg"
            style={{ background: "var(--surface)" }} inputMode="decimal" /> %</label>
        <button onClick={() => setSeed((s) => s + 1)}
          className="px-2.5 py-1 rounded-md border border-border text-xs hover:bg-surfaceAlt transition-colors"
          title="Nouveau tirage aléatoire (seed suivante)">↻ Relancer (seed {seed})</button>
        <button onClick={() => setTable((t) => !t)} aria-pressed={table}
          className="px-2.5 py-1 rounded-md border border-border text-xs hover:bg-surfaceAlt transition-colors"
          title="Basculer graphique / table des percentiles (accessibilité)">{table ? "graphique" : "table"}</button>
      </div>
      {!out ? (
        <p className="text-muted2 text-sm mt-3">Historique insuffisant pour simuler (≥ 60 jours requis).</p>
      ) : (
        <>
          {table ? <FanTable fan={out.fan} /> :
            <div className="mt-3"><McFan data={out.fan} startValue={+capital || 10000} /></div>}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-3 text-sm">
            <div><div className="text-muted text-[11px]">Médiane (CAGR)</div>
              <div className="mono text-lg">{usd(out.median)} <span className="text-muted2 text-xs">({pctF(out.cagrMed)}/an)</span></div></div>
            <div><div className="text-muted text-[11px]">p5 / ES 95 (CVaR)</div>
              <div className="mono text-lg" style={{ color: "#f43f5e" }}>{usd(out.p5)} <span className="text-muted2 text-xs">/ {usd(out.es95)}</span></div></div>
            <div><div className="text-muted text-[11px]">p95 (favorable)</div>
              <div className="mono text-lg" style={{ color: "var(--pos)" }}>{usd(out.p95)}</div></div>
            <div><div className="text-muted text-[11px]">Proba de perte</div>
              <div className="mono text-lg">{pctF(out.pLoss)}</div></div>
            <div><div className="text-muted text-[11px]">Proba ruine (−50 %)</div>
              <div className="mono text-lg" style={{ color: out.pRuin > 0.05 ? "#f43f5e" : undefined }}>
                {pctF(out.pRuin)} <span className="text-muted2 text-xs">± {(out.pRuinSe * 100).toFixed(1)} pt</span></div></div>
            <div><div className="text-muted text-[11px]">DD médian</div><div className="mono text-lg">{pctF(out.ddMed)}</div></div>
            <div><div className="text-muted text-[11px]">DD p95</div><div className="mono text-lg" style={{ color: "#f43f5e" }}>{pctF(out.ddP95)}</div></div>
            <div><div className="text-muted text-[11px]">Pire DD simulé</div><div className="mono text-lg" style={{ color: "#f43f5e" }}>{pctF(out.ddWorst)}</div></div>
          </div>
          <p className="text-muted2 text-[11px] mt-2">
            Bootstrap <b>stationnaire</b> (Politis-Romano, blocs d&apos;espérance {block} j) de rendements <b>passés</b>
            {" "}({src === "real" ? "compte réel" : "backtest preset"}, {rets.length} j) — distribution d&apos;incertitude
            conditionnelle au passé, <b>pas une prédiction</b>. Les blocs préservent le clustering de volatilité ;
            le mode iid le casse et sous-estime les queues. ES 95 = moyenne des 5 % pires finals. ± = erreur
            d&apos;échantillonnage Monte Carlo. Frais déduits au prorata quotidien. Aide à la décision — pas un conseil
            en investissement.
          </p>
        </>
      )}
    </section>
  );
}

// Vue TABLE des percentiles (accessibilité / lecteurs d'écran / export œil nu) — même donnée que le fan.
function FanTable({ fan }: { fan: FanData }) {
  const rows = fan.steps.map((_, i) => i).filter((i) => i % 5 === 4 || i === fan.steps.length - 1);
  return (
    <div className="overflow-x-auto mt-3">
      <table className="w-full text-sm mono">
        <thead className="text-muted text-xs"><tr>
          <th className="text-left font-normal">Jour</th>
          {["p5", "p25", "médiane", "p75", "p95"].map((h) => <th key={h} className="text-right font-normal">{h}</th>)}
        </tr></thead>
        <tbody>
          {rows.map((i) => (
            <tr key={i} className="border-t border-border">
              <td className="py-1">j+{fan.steps[i]}</td>
              {[fan.p5, fan.p25, fan.p50, fan.p75, fan.p95].map((arr, k) => (
                <td key={k} className="text-right">{Math.round(arr[i]).toLocaleString("fr-FR")}</td>))}
            </tr>))}
        </tbody>
      </table>
    </div>
  );
}
