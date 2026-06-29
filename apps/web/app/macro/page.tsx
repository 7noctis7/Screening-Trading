"use client";
import { useMacro, usePredictionMarkets, useCryptoOnchain } from "@/lib/api";
import { PageSkeleton } from "@/components/ui";
import { StepBanner } from "@/components/Pipeline";

// Une valeur peut être un nombre (ancien format) ou {p, p_adj, spread, source}.
type PMVal = number | { p?: number; p_adj?: number; spread?: number | null; source?: string };
const pct = (x?: number | null) => (x == null ? "—" : `${Math.round(x * 100)}%`);
function norm(v: PMVal) {
  return typeof v === "number" ? { p: v } : v;
}

function PredMarkets() {
  const { data: pm } = usePredictionMarkets();
  if (!pm?.available) return null;
  const blocks = ([
    ["Macro", pm.macro ?? {}], ["Actifs détenus", pm.assets ?? {}], ["Résultats", pm.earnings ?? {}],
  ] as [string, Record<string, PMVal>][]).filter(([, o]) => Object.keys(o).length);
  if (!blocks.length) return null;
  const alpha = pm.alpha ?? 1.15;
  return (
    <section className="card p-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h2 className="text-sm uppercase tracking-wide text-muted">Marchés de prédiction (sagesse des foules)</h2>
        <span className="text-[11px] text-muted2">{pm.n_markets} marchés · Kalshi + Polymarket · sans clé</span>
      </div>
      <p className="text-muted2 text-xs mt-1">
        Probas <b>mid-price</b>, dé-biaisées favori-outsider (α={alpha}). <b>brut</b> = prix affiché · <b>±</b> = spread du carnet.
        Forward-looking — overlay de risque, pas un signal d'alpha.
      </p>
      <div className="grid md:grid-cols-3 gap-3 mt-3">
        {blocks.map(([title, obj]) => (
          <div key={title} className="rounded-lg border border-border p-3" style={{ background: "var(--surface)" }}>
            <div className="text-muted text-[11px] uppercase tracking-wide mb-1.5">{title}</div>
            {Object.entries(obj).map(([k, raw]) => {
              const v = norm(raw);
              const adj = v.p_adj ?? v.p;
              const debiased = v.p_adj != null && v.p != null && v.p_adj !== v.p;
              return (
                <div key={k} className="flex items-center justify-between text-sm py-0.5">
                  <span className="text-muted truncate mr-2" title={v.source}>{k}</span>
                  <span className="text-right whitespace-nowrap">
                    <span className="mono" style={{ color: "var(--accent2)" }}>{pct(adj)}</span>
                    {debiased && <span className="text-muted2 text-[10px] ml-1">brut {pct(v.p)}</span>}
                    {v.spread != null && <span className="text-muted2 text-[10px] ml-1">±{pct(v.spread)}</span>}
                  </span>
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </section>
  );
}

const SENTI: Record<string, { c: string; bg: string; label: string }> = {
  BULLISH: { c: "var(--pos)", bg: "color-mix(in srgb, var(--pos) 15%, transparent)", label: "🟢 BULLISH" },
  BEARISH: { c: "#f43f5e", bg: "color-mix(in srgb, #f43f5e 15%, transparent)", label: "🔴 BEARISH" },
  NEUTRE: { c: "var(--warn)", bg: "color-mix(in srgb, var(--warn) 15%, transparent)", label: "🟡 NEUTRE" },
};

function OnchainReport({ report }: { report: any }) {
  if (!report?.available) return null;
  const s = SENTI[report.sentiment] ?? SENTI.NEUTRE;
  const Block = ({ title, items }: { title: string; items?: string[] }) =>
    !items?.length ? null : (
      <div className="mt-3">
        <div className="text-muted text-[11px] uppercase tracking-wide mb-1">{title}</div>
        <ul className="space-y-1">
          {items.map((t, i) => (
            <li key={i} className="text-sm text-muted flex gap-2">
              <span style={{ color: s.c }}>•</span><span>{t}</span>
            </li>
          ))}
        </ul>
      </div>
    );
  const e = report.eth_context;
  return (
    <div className="mt-3 rounded-xl border border-border p-3" style={{ background: "var(--surface)" }}>
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-xs font-semibold px-2 py-0.5 rounded-full"
          style={{ color: s.c, background: s.bg }}>{s.label}</span>
        {e?.available && (
          <span className="text-[11px] text-muted2">
            Ethereum ≈ {e.tps ?? "—"} TPS · frais médian ${e.median_fee_usd ?? "—"} (Growthepie)
          </span>
        )}
      </div>
      <p className="text-sm mt-2" style={{ lineHeight: 1.5 }}>{report.flash}</p>
      <Block title="Décryptage on-chain" items={report.decryptage} />
      <Block title="L'œil de Hasheur" items={report.hasheur} />
      <Block title="⚠ Vigilance" items={report.vigilance} />
    </div>
  );
}

function CryptoOnchain() {
  const { data: oc } = useCryptoOnchain();
  if (!oc?.available || !oc.coins) return null;
  const coins = Object.entries(oc.coins as Record<string, any>);
  if (!coins.length) return null;
  const f = (x: any, nd = 2) => (typeof x === "number" ? x.toFixed(nd) : "—");
  const pc = (x: any) => (typeof x === "number" ? `${(x * 100).toFixed(0)}%` : "—");
  const tvl = (x: any) => (typeof x === "number" ? `${(x / 1e9).toFixed(2)}B` : "—");
  return (
    <section className="card p-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h2 className="text-sm uppercase tracking-wide text-muted">Fondamentaux on-chain (crypto)</h2>
        <span className="text-[11px] text-muted2">CoinGecko + DefiLlama · sans clé</span>
      </div>
      <p className="text-muted2 text-xs mt-1">
        Contexte, pas un signal d'alpha. <b>float</b> bas = overhang d'unlocks · <b>TVL/MCap</b> haut = cap adossée à l'activité.
      </p>
      <OnchainReport report={oc.report} />
      <div className="overflow-x-auto mt-3">
        <table className="w-full text-sm mono">
          <thead className="text-muted2 text-[11px]">
            <tr>
              <th className="text-left font-normal">actif</th>
              <th className="text-right font-normal">turnover</th>
              <th className="text-right font-normal">float</th>
              <th className="text-right font-normal">TVL</th>
              <th className="text-right font-normal">TVL/MCap</th>
              <th className="text-right font-normal">DD-ATH</th>
              <th className="text-right font-normal">mom 30j</th>
            </tr>
          </thead>
          <tbody>
            {coins.map(([sym, d]) => (
              <tr key={sym} className="border-t border-border">
                <td className="py-1.5 font-sans">{sym}</td>
                <td className="text-right">{f(d.turnover, 3)}</td>
                <td className="text-right">{f(d.float_ratio)}</td>
                <td className="text-right">{tvl(d.tvl)}</td>
                <td className="text-right" style={{ color: "var(--accent2)" }}>{f(d.tvl_mcap, 3)}</td>
                <td className="text-right" style={{ color: d.dd_ath < 0 ? "#f43f5e" : undefined }}>{pc(d.dd_ath)}</td>
                <td className="text-right" style={{ color: d.mom_30d >= 0 ? "var(--pos)" : "#f43f5e" }}>{pc(d.mom_30d)}</td>
              </tr>
            ))}
          </tbody>
        </table>
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
      <CryptoOnchain />

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
