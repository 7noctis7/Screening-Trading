"use client";
// Composant 3 — « Analyse experte · data-driven × Hasheur » LIVE, client-direct (0 backend,
// aucune clé). Sources CORS : CoinGecko, alternative.me, DefiLlama, Bybit. Sentiment COMPOSITE
// transparent (chaque facteur ±1) + lecture croisée pro. « n/d » si une source tombe — jamais
// de chiffre inventé. Auto-refresh 90 s UNIQUEMENT si visible + onglet actif. Éducatif.
import { useCallback, useEffect, useRef, useState } from "react";

const STABLE = new Set(["USDT", "USDC", "DAI", "USDE", "USDS", "USD1", "FDUSD", "TUSD",
  "PYUSD", "USDD", "FRAX", "BUSD", "GUSD"]);

const usd = (x: any) => (typeof x !== "number" ? "n/d"
  : x >= 1e12 ? `$${(x / 1e12).toFixed(2)} T` : x >= 1e9 ? `$${(x / 1e9).toFixed(2)} Md`
  : x >= 1e6 ? `$${(x / 1e6).toFixed(0)} M` : `$${x.toFixed(0)}`);
const pc = (x: any, d = 1) => (typeof x === "number" ? `${x >= 0 ? "+" : ""}${x.toFixed(d)}%` : "n/d");

async function j(url: string): Promise<any> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(String(r.status));
  return r.json();
}

async function cgGlobal() {
  try {
    const d = (await j("https://api.coingecko.com/api/v3/global")).data;
    return { totalCap: d.total_market_cap?.usd, cap24h: d.market_cap_change_percentage_24h_usd,
             btcDom: d.market_cap_percentage?.btc, ethDom: d.market_cap_percentage?.eth };
  } catch { return null; }
}
async function cgMarkets() {
  try {
    const u = "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd"
      + "&order=market_cap_desc&per_page=60&page=1&price_change_percentage=24h,7d,30d";
    return await j(u);
  } catch { return null; }
}
async function fngFetch() {
  try {
    const v = (await j("https://api.alternative.me/fng/?limit=1")).data?.[0];
    return v ? { value: parseFloat(v.value), label: v.value_classification } : null;
  } catch { return null; }
}
async function rwaFetch() {
  try {
    const all = await j("https://api.llama.fi/protocols");
    const r = (all as any[]).filter((p) => (p.category || "").toUpperCase() === "RWA");
    const tvl = r.reduce((s, p) => s + (p.tvl || 0), 0);
    if (!tvl) return null;
    const w = r.reduce((s, p) => s + (p.tvl || 0) * (p.change_7d || 0), 0) / tvl;
    return { tvl, change7d: w };
  } catch { return null; }
}
async function derivBtc() {
  try {
    const t = await j("https://api.bybit.com/v5/market/tickers?category=linear&symbol=BTCUSDT");
    const row = t.result?.list?.[0];
    let funding = row ? parseFloat(row.fundingRate) * 100 : null;
    if (funding == null) {                          // repli OKX si Bybit KO
      try {
        const o = await j("https://www.okx.com/api/v5/public/funding-rate?instId=BTC-USD-SWAP");
        const fr = o.data?.[0]?.fundingRate;
        if (fr != null) funding = parseFloat(fr) * 100;
      } catch { /* repli best-effort */ }
    }
    const oiUsd = row?.openInterestValue ? parseFloat(row.openInterestValue) : null;
    let oiChg: number | null = null;
    try {
      const h = await j("https://api.bybit.com/v5/market/open-interest"
        + "?category=linear&symbol=BTCUSDT&intervalTime=1d&limit=2");
      const l = h.result?.list || [];
      if (l.length >= 2) {
        const a = parseFloat(l[0].openInterest), b = parseFloat(l[1].openInterest);
        if (b) oiChg = ((a - b) / b) * 100;
      }
    } catch { /* OI history best-effort */ }
    return { funding, oiUsd, oiChg };
  } catch { return null; }
}

// Sentiment composite + phrases descriptives (règles exactes, transparent).
function compute(g: any, mk: any[] | null, f: any, rwa: any, d: any) {
  const factors: { sentence: string; c: number }[] = [];
  if (f?.value != null) {
    const v = f.value;
    factors.push({ c: v >= 60 ? 1 : v <= 40 ? -1 : 0,
      sentence: v <= 40 ? `Peur dominante (Fear & Greed ${v.toFixed(0)}) — aversion au risque.`
        : v >= 60 ? `Avidité (Fear & Greed ${v.toFixed(0)}) — appétit pour le risque.`
        : `Sentiment neutre (Fear & Greed ${v.toFixed(0)}).` });
  }
  let eth7: number | null = null, eth30: number | null = null, alt: number | null = null;
  if (mk?.length) {
    const eth = mk.find((m) => m.symbol === "eth");
    eth7 = eth?.price_change_percentage_7d_in_currency ?? null;
    eth30 = eth?.price_change_percentage_30d_in_currency ?? null;
    const btc30 = mk.find((m) => m.symbol === "btc")?.price_change_percentage_30d_in_currency;
    const uni = mk.filter((m) => !STABLE.has((m.symbol || "").toUpperCase())
      && m.symbol !== "btc").slice(0, 50)
      .filter((m) => m.price_change_percentage_30d_in_currency != null);
    if (btc30 != null && uni.length >= 10)
      alt = Math.round(100 * uni.filter((m) =>
        m.price_change_percentage_30d_in_currency > btc30).length / uni.length);
  }
  if (eth30 != null)
    factors.push({ c: eth30 > 5 ? 1 : eth30 < -5 ? -1 : 0,
      sentence: eth30 > 5 ? `Momentum ETH solide (${pc(eth30)} sur 30 j).`
        : eth30 < -5 ? `Momentum ETH dégradé (${pc(eth30)} sur 30 j).`
        : `Momentum ETH neutre (${pc(eth30)} sur 30 j).` });
  if (alt != null)
    factors.push({ c: alt >= 60 ? 1 : alt <= 30 ? -1 : 0,
      sentence: alt >= 60 ? `Rotation vers les alts (indice altseason ${alt}/100) — risk-on.`
        : alt <= 30 ? `Marché concentré sur BTC (altseason ${alt}/100).`
        : `Altseason mitigé (${alt}/100).` });
  if (rwa?.change7d != null)
    factors.push({ c: rwa.change7d > 1 ? 1 : rwa.change7d < -1 ? -1 : 0,
      sentence: rwa.change7d > 1 ? `TVL RWA en hausse (${pc(rwa.change7d)} sur 7 j).`
        : rwa.change7d < -1 ? `TVL RWA en repli (${pc(rwa.change7d)} sur 7 j).`
        : `TVL RWA stable (${pc(rwa.change7d)} sur 7 j).` });
  if (g?.cap24h != null)
    factors.push({ c: g.cap24h > 2 ? 1 : g.cap24h < -2 ? -1 : 0,
      sentence: `Capitalisation ${g.cap24h > 0 ? "en hausse" : "en baisse"} (${pc(g.cap24h)} / 24 h).` });
  if (d?.funding != null) {
    const fu = d.funding;
    factors.push({ c: fu > 0.05 ? -1 : fu > 0.005 ? 1 : fu < -0.005 ? -1 : 0,
      sentence: fu > 0.05 ? `Funding BTC élevé (${pc(fu, 4)}/8 h) — surchauffe des longs.`
        : fu > 0.005 ? `Funding BTC positif (${pc(fu, 4)}/8 h) — positionnement haussier mesuré.`
        : fu < -0.005 ? `Funding BTC négatif (${pc(fu, 4)}/8 h) — shorts dominants.`
        : `Funding BTC neutre (${pc(fu, 4)}/8 h).` });
  }
  const score = factors.reduce((s, x) => s + x.c, 0);
  const label = score >= 2 ? "🟢 BULLISH" : score <= -2 ? "🔴 BEARISH" : "🟡 NEUTRE";
  const accroche = score >= 2
    ? "Signaux alignés à la hausse : la dynamique domine, mais gère le risque."
    : score <= -2 ? "Pression vendeuse : prudence, le marché purge le levier."
    : "Marché en consolidation : signaux mitigés, ni euphorie ni capitulation — phase d'attentisme.";
  return { factors, score, label, accroche, g, eth7, eth30, alt, rwa, d, f };
}

export default function ExpertLive() {
  const [s, setS] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [at, setAt] = useState("");
  const ref = useRef<HTMLElement>(null);
  const visible = useRef(true);

  const load = useCallback(async () => {
    setLoading(true);
    const [g, mk, f, r, d] = await Promise.all([
      cgGlobal(), cgMarkets(), fngFetch(), rwaFetch(), derivBtc()]);
    setS(compute(g, mk, f, r, d));
    setAt(new Date().toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" }));
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
    const io = new IntersectionObserver(
      (e) => { visible.current = e[0].isIntersecting; }, { threshold: 0.1 });
    if (ref.current) io.observe(ref.current);
    const t = setInterval(() => {
      if (visible.current && !document.hidden) load();
    }, 90000);
    return () => { io.disconnect(); clearInterval(t); };
  }, [load]);

  const nd = (x: any, suf = "") => (x == null ? "n/d" : `${x}${suf}`);
  const fngZone = (v: number) => v <= 30 ? "zone de capitulation — souvent des zones d'accumulation contrariennes"
    : v >= 70 ? "zone d'avidité — le levier précède souvent les purges" : "ni euphorie ni panique";

  return (
    <section ref={ref} className="card p-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h2 className="text-sm uppercase tracking-wide text-muted">
            Analyse experte · data-driven × Hasheur</h2>
          <p className="text-muted2 text-[11px]">
            Lecture adaptative des signaux on-chain en direct (éducatif, aucun conseil)</p>
        </div>
        <div className="flex items-center gap-2 text-[11px] text-muted2">
          <span>maj {at || "…"}</span>
          <button onClick={load} aria-label="Rafraîchir"
            className="px-1.5 py-0.5 rounded border border-border hover:text-fg">↻</button>
        </div>
      </div>

      {loading && !s ? <div className="shimmer rounded-md bg-surfaceAlt h-40 mt-3" />
        : !s ? <div className="text-muted2 text-sm mt-3">n/d</div> : (
        <>
          <div className="mt-3">
            <span className="text-base font-semibold">{s.label}</span>
            <p className="text-muted text-sm mt-1">{s.accroche}</p>
          </div>

          <div className="mt-3">
            <div className="text-muted text-[11px] uppercase tracking-wide mb-1">
              ⚡ Flash Data — signaux retenus</div>
            <ul className="text-sm text-muted space-y-1">
              {s.factors.map((x: any, i: number) => (
                <li key={i} className="flex gap-2">
                  <span style={{ color: x.c > 0 ? "var(--pos)" : x.c < 0 ? "#f43f5e" : "var(--muted2)" }}>
                    {x.c > 0 ? "▲" : x.c < 0 ? "▼" : "•"}</span>{x.sentence}</li>
              ))}
            </ul>
          </div>

          <div className="mt-3">
            <div className="text-muted text-[11px] uppercase tracking-wide mb-1">
              🔬 Décryptage on-chain & marché</div>
            <ul className="text-sm text-muted space-y-1">
              <li>• Capitalisation crypto totale {usd(s.g?.totalCap)} ({pc(s.g?.cap24h)} / 24 h) ·
                dominance BTC {nd(s.g?.btcDom?.toFixed?.(1), "%")} · ETH {nd(s.g?.ethDom?.toFixed?.(1), "%")}.</li>
              {s.alt != null && <li>• Indice altseason {s.alt}/100 :
                {s.alt >= 60 ? " la liquidité diffuse des majors vers les alts (rotation risk-on)."
                  : s.alt <= 30 ? " le capital reste concentré sur BTC (risk-off)."
                  : " rotation indécise entre BTC et alts."}</li>}
              <li>• ETH {pc(s.eth7)} (7 j) / {pc(s.eth30)} (30 j) : activité réseau → burn EIP-1559
                et capture de valeur {s.eth30 != null && s.eth30 < 0 ? "en retrait" : "en cours"}.</li>
              {s.rwa && <li>• TVL RWA {usd(s.rwa.tvl)} ({pc(s.rwa.change7d)} / 7 j) :
                la valeur réelle réglée on-chain {s.rwa.change7d < 0 ? "marque une pause" : "progresse"}.</li>}
              {s.f?.value != null && <li>• Fear & Greed {s.f.value.toFixed(0)} : {fngZone(s.f.value)}.</li>}
              {s.d && <li>• Dérivés BTC : Open Interest {usd(s.d.oiUsd)} ({pc(s.d.oiChg)} / 24 h) ·
                funding {pc(s.d.funding, 4)}/8 h → {s.d.funding != null && s.d.funding > 0.05
                  ? "levier long surchauffé" : "positionnement stable"}.</li>}
            </ul>
          </div>

          <div className="mt-3">
            <div className="text-muted text-[11px] uppercase tracking-wide mb-1">
              🎯 L'œil de Hasheur — le filtre pragmatique</div>
            <ul className="text-sm text-muted space-y-1">
              <li>• <b>Adoption ou hype ?</b> Hors RWA, méfie-toi du bruit : regarde l'usage réel
                (frais payés, TVL qui tient), pas le prix qui s'agite.</li>
              <li>• <b>La TradFi en coulisses.</b> BlackRock (BUIDL via Securitize), Franklin Templeton
                et Fidelity tokenisent sur Ethereum : ils ne « parient » pas, ils bâtissent la
                plomberie. Suis les émetteurs, pas les influenceurs.</li>
              <li>• <b>Sang-froid.</b> {s.f?.value != null && s.f.value <= 30
                ? "Peur extrême : inconfortable, mais historiquement des zones d'accumulation pour qui a un horizon long. DCA > timing."
                : "Garde un plan : DCA et tailles fixes battent le market-timing émotionnel."}</li>
              <li>• <b>Risque à ne jamais oublier.</b> Une grande partie des RWA et stablecoins dépend
                d'émetteurs centralisés (gel possible, KYC, contrepartie) et de smart contracts
                (failles, oracles). Le rendement « sans risque » on-chain n'est pas sans risque.</li>
            </ul>
          </div>

          <p className="text-muted2 text-[11px] mt-3">
            Sentiment composite calculé sur les signaux affichés (F&G, momentum ETH 30 j,
            altseason, TVL RWA 7 j, cap 24 h, funding BTC). Sources : CoinGecko · alternative.me ·
            DefiLlama · Bybit/OKX (OI/funding) — live. TPS (Growthepie) non intégré.
            Éducatif, aucun conseil en investissement.
          </p>
        </>
      )}
    </section>
  );
}
