"use client";
// Composant 3 — « Analyse experte · data-driven × Hasheur » LIVE, client-direct (0 backend,
// aucune clé). Sources CORS : CoinGecko, alternative.me, DefiLlama, Bybit. Sentiment COMPOSITE
// transparent (chaque facteur ±1, valeurs réelles affichées). « n/d » si une source tombe —
// jamais de chiffre inventé. Auto-refresh 90 s UNIQUEMENT si visible + onglet actif. Éducatif.
import { useCallback, useEffect, useRef, useState } from "react";

const STABLE = new Set(["USDT", "USDC", "DAI", "USDE", "USDS", "USD1", "FDUSD", "TUSD",
  "PYUSD", "USDD", "FRAX", "BUSD", "GUSD"]);

async function j(url: string): Promise<any> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(String(r.status));
  return r.json();
}

// --- fetchers isolés (null si KO) ---
async function cgGlobal() {
  try {
    const d = (await j("https://api.coingecko.com/api/v3/global")).data;
    return { cap24h: d.market_cap_change_percentage_24h_usd,
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
async function fng() {
  try {
    const v = (await j("https://api.alternative.me/fng/?limit=1")).data?.[0];
    return v ? { value: parseFloat(v.value), label: v.value_classification } : null;
  } catch { return null; }
}
async function rwa7d() {
  try {
    const all = await j("https://api.llama.fi/protocols");
    const r = (all as any[]).filter((p) => (p.category || "").toUpperCase() === "RWA");
    const tvl = r.reduce((s, p) => s + (p.tvl || 0), 0);
    if (!tvl) return null;
    const w = r.reduce((s, p) => s + (p.tvl || 0) * (p.change_7d || 0), 0) / tvl;
    return { tvl, change7d: w };
  } catch { return null; }
}
async function fundingBtc() {
  try {
    const u = "https://api.bybit.com/v5/market/tickers?category=linear&symbol=BTCUSDT";
    const row = (await j(u)).result?.list?.[0];
    return row ? parseFloat(row.fundingRate) * 100 : null;   // en %/8h
  } catch { return null; }
}

// --- sentiment composite (règles exactes, transparent) ---
function compute(g: any, mk: any[] | null, f: any, rwa: any, fund: number | null) {
  const factors: { name: string; value: string; c: number }[] = [];
  const add = (name: string, value: string, c: number) => factors.push({ name, value, c });

  if (f?.value != null)
    add("Fear & Greed", `${f.value.toFixed(0)} (${f.label ?? ""})`,
        f.value >= 60 ? 1 : f.value <= 40 ? -1 : 0);

  let eth30: number | null = null, alt: number | null = null;
  if (mk?.length) {
    const eth = mk.find((m) => m.symbol === "eth");
    eth30 = eth?.price_change_percentage_30d_in_currency ?? null;
    const btc = mk.find((m) => m.symbol === "btc");
    const btc30 = btc?.price_change_percentage_30d_in_currency;
    const uni = mk.filter((m) => !STABLE.has((m.symbol || "").toUpperCase())
      && m.symbol !== "btc").slice(0, 50);
    const valid = uni.filter((m) => m.price_change_percentage_30d_in_currency != null);
    if (btc30 != null && valid.length >= 10) {
      const beat = valid.filter((m) =>
        m.price_change_percentage_30d_in_currency > btc30).length;
      alt = Math.round((100 * beat) / valid.length);
    }
  }
  if (eth30 != null)
    add("Momentum ETH 30j", `${eth30 >= 0 ? "+" : ""}${eth30.toFixed(1)}%`,
        eth30 > 5 ? 1 : eth30 < -5 ? -1 : 0);
  if (alt != null)
    add("Altseason 30j", `${alt}%`, alt >= 60 ? 1 : alt <= 30 ? -1 : 0);
  if (rwa?.change7d != null)
    add("TVL RWA 7j", `${rwa.change7d >= 0 ? "+" : ""}${rwa.change7d.toFixed(1)}%`,
        rwa.change7d > 1 ? 1 : rwa.change7d < -1 ? -1 : 0);
  if (g?.cap24h != null)
    add("Cap 24h", `${g.cap24h >= 0 ? "+" : ""}${g.cap24h.toFixed(1)}%`,
        g.cap24h > 2 ? 1 : g.cap24h < -2 ? -1 : 0);
  if (fund != null)
    add("Funding BTC 8h", `${fund >= 0 ? "+" : ""}${fund.toFixed(4)}%`,
        fund > 0.05 ? -1 : fund > 0.005 ? 1 : fund < -0.005 ? -1 : 0);

  const score = factors.reduce((s, x) => s + x.c, 0);
  const label = score >= 2 ? "🟢 BULLISH" : score <= -2 ? "🔴 BEARISH" : "🟡 NEUTRE";
  return { factors, score, label, g, eth30, alt, rwa, fund, f };
}

function Skel() {
  return <div className="shimmer rounded-md bg-surfaceAlt h-24 mt-3" />;
}

export default function ExpertLive() {
  const [s, setS] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [at, setAt] = useState<string>("");
  const ref = useRef<HTMLElement>(null);
  const visible = useRef(true);

  const load = useCallback(async () => {
    setLoading(true);
    const [g, mk, f, r, fund] = await Promise.all([
      cgGlobal(), cgMarkets(), fng(), rwa7d(), fundingBtc()]);
    setS(compute(g, mk, f, r, fund));
    setAt(new Date().toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" }));
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
    const io = new IntersectionObserver(
      (e) => { visible.current = e[0].isIntersecting; }, { threshold: 0.1 });
    if (ref.current) io.observe(ref.current);
    const t = setInterval(() => {
      if (visible.current && !document.hidden) load();    // 90s visible-only
    }, 90000);
    return () => { io.disconnect(); clearInterval(t); };
  }, [load]);

  const nd = (x: any) => (x == null ? "n/d" : x);
  return (
    <section ref={ref} className="card p-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h2 className="text-sm uppercase tracking-wide text-muted">
          Analyse experte · data-driven × Hasheur</h2>
        <div className="flex items-center gap-2 text-[11px] text-muted2">
          <span>maj {at || "…"}</span>
          <button onClick={load} aria-label="Rafraîchir"
            className="px-1.5 py-0.5 rounded border border-border hover:text-fg">↻</button>
        </div>
      </div>

      {loading && !s ? <Skel /> : !s ? <div className="text-muted2 text-sm mt-3">n/d</div> : (
        <>
          <div className="flex items-center gap-3 mt-3 flex-wrap">
            <span className="text-sm font-semibold px-2.5 py-1 rounded-full"
              style={{ background: "var(--surface2)" }}>{s.label}</span>
            <span className="text-muted2 text-xs">score composite {s.score >= 0 ? "+" : ""}{s.score}
              {" "}sur {s.factors.length} facteurs mesurés</span>
          </div>

          <div className="mt-3">
            <div className="text-muted text-[11px] uppercase tracking-wide mb-1.5">
              ⚡ Flash Data — signaux retenus</div>
            <div className="flex flex-wrap gap-2">
              {s.factors.map((x: any) => (
                <span key={x.name} className="text-xs px-2 py-1 rounded-lg border border-border"
                  style={{ background: "var(--surface)" }}>
                  {x.name} <b style={{ color: x.c > 0 ? "var(--pos)" : x.c < 0 ? "#f43f5e"
                    : "var(--muted)" }}>{x.value} ({x.c >= 0 ? "+" : ""}{x.c})</b>
                </span>
              ))}
            </div>
          </div>

          <div className="mt-3">
            <div className="text-muted text-[11px] uppercase tracking-wide mb-1">
              🔬 Décryptage on-chain & marché</div>
            <ul className="text-sm text-muted space-y-1">
              <li>• Dominance BTC {nd(s.g?.btcDom?.toFixed?.(1))}% · ETH {nd(s.g?.ethDom?.toFixed?.(1))}%
                {" "}— rotation vs concentration de la liquidité.</li>
              <li>• Altseason {nd(s.alt)}% ↔ appétit pour le risque (alts surperforment BTC sur 30 j).</li>
              <li>• Momentum ETH 30j {nd(s.eth30?.toFixed?.(1))}% ↔ activité réseau / burn EIP-1559.</li>
              <li>• TVL RWA 7j {nd(s.rwa?.change7d?.toFixed?.(1))}% ↔ demande de règlement tokenisé.</li>
              <li>• Funding BTC {nd(s.fund?.toFixed?.(4))}%/8h ↔ levier (positif = longs surchauffés).</li>
            </ul>
          </div>

          <div className="mt-3">
            <div className="text-muted text-[11px] uppercase tracking-wide mb-1">
              🎯 L'œil de Hasheur</div>
            <ul className="text-sm text-muted space-y-1">
              <li>• Adoption réelle (TVL/usage) {">"} hype : le marché paie l'usage sur la durée.</li>
              <li>• RWA = la TradFi (BUIDL & co.) migre en coulisses — le rail compte plus que le token.</li>
              <li>• F&G {nd(s.f?.value?.toFixed?.(0))} : {s.f?.value != null && s.f.value <= 30
                ? "peur extrême = sang-froid, zone d'accumulation"
                : s.f?.value != null && s.f.value >= 70
                  ? "avidité = vigilance, le levier précède les purges" : "ni euphorie ni panique"}.</li>
              <li>• Risque : émetteurs centralisés (custodian RWA) & smart contracts. Petites positions, 0 levier.</li>
            </ul>
          </div>

          <p className="text-muted2 text-[11px] mt-3">
            Sentiment composite calculé sur {s.factors.length} facteurs. Sources : CoinGecko ·
            alternative.me · DefiLlama · Bybit — live. TPS (Growthepie) non intégré.
            Éducatif, aucun conseil en investissement.
          </p>
        </>
      )}
    </section>
  );
}
