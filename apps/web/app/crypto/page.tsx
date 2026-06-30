"use client";
// Cockpit crypto — vue marché agrégée, gratuite (sans clé). Chaque section est pédagogique :
// une donnée, sa source, son explication. Aucun chiffre inventé : "n/d" si la source tombe.
import { useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { useCryptoCockpit } from "@/lib/api";
import { PageSkeleton, EmptyState } from "@/components/ui";
import { InfoTip } from "@/components/InfoTip";
import { ShareBar } from "@/components/crypto/ShareBar";

// Jauge de sentiment live (au-dessus du graphe) — client-only.
const LiveGauge = dynamic(() => import("@/components/crypto/LiveGauge"), { ssr: false });
// Graphe live (WebSocket navigateur) — client-only, jamais SSR (compatible export statique).
const LiveChart = dynamic(() => import("@/components/crypto/LiveChart"), { ssr: false });
// Bloc « Analyse experte · Œil de Hasheur » LIVE (client-direct, auto-refresh visible-only).
const ExpertLive = dynamic(() => import("@/components/crypto/ExpertLive"), { ssr: false });

// Liens vers les fiches OFFICIELLES (infos complètes, fiables, gratuites) — nouvel onglet.
const cgCoin = (id?: string) => (id ? `https://www.coingecko.com/en/coins/${id}` : null);
const cgCat = (id?: string) => (id ? `https://www.coingecko.com/en/categories/${id}` : null);
const EXT = { target: "_blank", rel: "noopener noreferrer" } as const;

// Glossaire pédagogique (définitions factuelles, pas de chiffre inventé).
const GLOSSARY: Record<string, string> = {
  "Capitalisation totale":
    "Valeur de marché cumulée de toutes les cryptos (prix × offre en circulation). Le « PIB » du marché crypto.",
  "Variation cap 24 h":
    "Évolution de cette capitalisation sur 24 h. Positif = le marché global monte.",
  "Dominance BTC":
    "Part de Bitcoin dans la capitalisation totale. En hausse = repli vers la valeur refuge ; en baisse = appétit pour les altcoins (« altseason »).",
  "Dominance ETH":
    "Part d'Ethereum dans la capitalisation totale. Référence de l'écosystème des smart contracts.",
  "Fear & Greed":
    "Indice 0-100 d'humeur du marché (alternative.me). 0 = peur extrême (souvent un creux), 100 = avidité (souvent un sommet). Indicateur contrarian.",
  "TVL DeFi totale":
    "Total Value Locked : capital déposé dans les protocoles de finance décentralisée. Mesure l'usage réel de la DeFi.",
  breadth:
    "Ampleur du marché : combien d'actifs montent vs descendent. Une hausse « large » (beaucoup d'actifs verts) est plus saine qu'une hausse portée par quelques-uns.",
  peg:
    "Ancrage d'un stablecoin à sa valeur cible (en général 1,00 $). Un écart durable (≠ 0 %) signale un stress de liquidité ou de confiance.",
};

function Label({ text }: { text: string }) {
  const def = GLOSSARY[text];
  return (
    <span className="inline-flex items-center gap-1">
      {text}
      {def && <InfoTip label={text}>{def}</InfoTip>}
    </span>
  );
}

const SENTI: Record<string, { c: string; bg: string; label: string }> = {
  BULLISH: { c: "var(--pos)", bg: "color-mix(in srgb, var(--pos) 15%, transparent)", label: "🟢 BULLISH" },
  BEARISH: { c: "#f43f5e", bg: "color-mix(in srgb, #f43f5e 15%, transparent)", label: "🔴 BEARISH" },
  NEUTRE: { c: "var(--warn)", bg: "color-mix(in srgb, var(--warn) 15%, transparent)", label: "🟡 NEUTRE" },
};

// Formatage défensif — jamais NaN/undefined à l'écran : "n/d" tant que la donnée manque.
const usd = (x: any) =>
  typeof x === "number"
    ? x >= 1e12 ? `$${(x / 1e12).toFixed(2)} T`
      : x >= 1e9 ? `$${(x / 1e9).toFixed(1)} Md`
      : x >= 1e6 ? `$${(x / 1e6).toFixed(1)} M`
      : `$${x.toLocaleString("fr-FR", { maximumFractionDigits: 2 })}`
    : "n/d";
const pct = (x: any, d = 1) => (typeof x === "number" ? `${x >= 0 ? "+" : ""}${x.toFixed(d)}%` : "n/d");
const tone = (x: any) => (typeof x !== "number" ? undefined : x >= 0 ? "var(--pos)" : "#f43f5e");

// Révélation au scroll (lazy, IntersectionObserver) — neutralisée si prefers-reduced-motion.
function Reveal({ children }: { children: React.ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  const [shown, setShown] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) { setShown(true); return; }
    const io = new IntersectionObserver(
      (es) => es.forEach((e) => e.isIntersecting && (setShown(true), io.disconnect())),
      { threshold: 0.12 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);
  return (
    <div ref={ref} style={{
      opacity: shown ? 1 : 0,
      transform: shown ? "none" : "translateY(20px)",
      transition: "opacity .6s cubic-bezier(.16,1,.3,1), transform .6s cubic-bezier(.16,1,.3,1)",
    }}>{children}</div>
  );
}

function Card({ title, source, hint, children }: {
  title: string; source: string; hint: string; children: React.ReactNode;
}) {
  return (
    <Reveal>
      <section className="card p-4">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <h2 className="text-sm uppercase tracking-wide text-muted">{title}</h2>
          <span className="text-[11px] text-muted2">{source}</span>
        </div>
        <p className="text-muted2 text-xs mt-1">{hint}</p>
        <div className="mt-3">{children}</div>
      </section>
    </Reveal>
  );
}

// ---- Aperçu : sentiment marché synthétique (déterministe, dérivé du cockpit) ----
function Overview({ ck }: { ck: any }) {
  const se = ck.sentiment;
  if (!se?.available) return null;
  const s = SENTI[se.label] ?? SENTI.NEUTRE;
  return (
    <Card title="Aperçu — humeur du marché" source="synthèse déterministe · 0 chiffre inventé"
      hint="Score 0–100 = moyenne des signaux disponibles (Fear & Greed, variation 24 h, breadth). Contexte, pas un signal d'alpha.">
      <div className="flex items-center gap-3 flex-wrap">
        <span className="text-sm font-semibold px-2.5 py-1 rounded-full"
          style={{ color: s.c, background: s.bg }}>{s.label}</span>
        <span className="text-2xl mono font-semibold" style={{ color: s.c }}>{se.score}<span className="text-muted2 text-sm">/100</span></span>
      </div>
      <ul className="mt-2 space-y-0.5">
        {(se.drivers ?? []).map((d: string, i: number) => (
          <li key={i} className="text-sm text-muted flex gap-2"><span style={{ color: s.c }}>•</span>{d}</li>
        ))}
      </ul>
    </Card>
  );
}

// ---- Score d'Accumulation Institutionnelle (0-100, contrarian, déterministe) ----
function Accumulation({ ck }: { ck: any }) {
  const a = ck.accumulation;
  if (!a?.available) return null;
  const col = a.score >= 60 ? "var(--pos)" : a.score <= 40 ? "#f43f5e" : "var(--warn)";
  return (
    <Card title="Score d'Accumulation Institutionnelle" source="synthèse contrarian · déterministe"
      hint="0–100 contrarian : haut = conditions d'accumulation (peur, shorts surchauffés, poudre sèche stablecoins élevée) ; bas = euphorie/distribution. Contexte, pas un signal d'alpha.">
      <div className="flex items-center gap-3 flex-wrap">
        <span className="text-sm font-semibold px-2.5 py-1 rounded-full"
          style={{ color: col, background: "color-mix(in srgb, " + col + " 15%, transparent)" }}>{a.label}</span>
        <span className="text-2xl mono font-semibold" style={{ color: col }}>{a.score}<span className="text-muted2 text-sm">/100</span></span>
      </div>
      <div className="mt-3 h-2 rounded-full overflow-hidden" style={{ background: "var(--surface2)" }}>
        <div className="h-full rounded-full" style={{ width: `${a.score}%`, background: col }} />
      </div>
      <ul className="mt-2 space-y-0.5">
        {(a.drivers ?? []).map((d: string, i: number) => (
          <li key={i} className="text-sm text-muted flex gap-2"><span style={{ color: col }}>•</span>{d}</li>
        ))}
      </ul>
    </Card>
  );
}

// ---- Pouls : Fear & Greed, capitalisation, TVL DeFi, dominance ----
function Pulse({ ck }: { ck: any }) {
  const g = ck.global ?? {};
  const fng = ck.fng ?? {};
  const defi = ck.defi ?? {};
  const stats: [string, string, string | undefined][] = [
    ["Capitalisation totale", usd(g.total_mcap), undefined],
    ["Variation cap 24 h", pct(g.mcap_chg_24h), tone(g.mcap_chg_24h)],
    ["Dominance BTC", typeof g.btc_dom === "number" ? `${g.btc_dom.toFixed(1)}%` : "n/d", undefined],
    ["Dominance ETH", typeof g.eth_dom === "number" ? `${g.eth_dom.toFixed(1)}%` : "n/d", undefined],
    ["Fear & Greed", fng.available ? `${fng.value?.toFixed(0)} · ${fng.label ?? ""}` : "n/d", undefined],
    ["TVL DeFi totale", usd(defi.total_tvl), undefined],
  ];
  return (
    <Card title="Pouls du marché" source="CoinGecko · DefiLlama · alternative.me"
      hint="Dominance BTC ↑ = repli vers la valeur refuge crypto ; ↓ = appétit pour le risque (altcoins). TVL = capital verrouillé en DeFi.">
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        {stats.map(([l, v, c]) => (
          <div key={l}>
            <div className="text-muted text-xs"><Label text={l} /></div>
            <div className="text-lg mono" style={{ color: c }}>{v}</div>
          </div>
        ))}
      </div>
    </Card>
  );
}

// ---- Narratifs : catégories par performance 24 h (où va l'argent) ----
function Narratives({ ck }: { ck: any }) {
  const cats = (ck.categories ?? []) as any[];
  if (!cats.length) return null;
  return (
    <Card title="Narratifs du moment" source="CoinGecko · catégories"
      hint="Quelle thématique surperforme aujourd'hui (IA, RWA, L2, memes…). Rotation sectorielle = où la liquidité se déplace.">
      <div className="flex flex-wrap gap-2">
        {cats.map((c) => {
          const href = cgCat(c.id);
          const body = <>{c.name} <b style={{ color: tone(c.chg24h) }}>{pct(c.chg24h)}</b></>;
          return href ? (
            <a key={c.name} href={href} {...EXT}
              title={`${c.name} — voir les actifs de cette catégorie sur CoinGecko`}
              className="text-xs px-2.5 py-1.5 rounded-lg border border-border hover:border-border2 hover:text-accent transition-colors"
              style={{ background: "var(--surface)" }}>{body}</a>
          ) : (
            <span key={c.name} className="text-xs px-2.5 py-1.5 rounded-lg border border-border"
              style={{ background: "var(--surface)" }}>{body}</span>
          );
        })}
      </div>
    </Card>
  );
}

// ---- Tendances : recherches en hausse (sentiment retail) ----
function Trending({ ck }: { ck: any }) {
  const tr = (ck.trending ?? []) as any[];
  if (!tr.length) return null;
  return (
    <Card title="Tendances (attention retail)" source="CoinGecko · search/trending"
      hint="Les actifs les plus recherchés. Signal d'attention, souvent tardif — à lire comme un thermomètre du retail, pas un signal d'entrée.">
      <div className="flex flex-wrap gap-2">
        {tr.map((t, i) => {
          const href = cgCoin(t.id);
          const body = (
            <>
              <span className="text-muted2">#{t.rank ?? "—"}</span> <b>{t.sym}</b>{" "}
              <span className="text-muted">{t.name}</span>
            </>
          );
          return href ? (
            <a key={t.sym + i} href={href} {...EXT}
              title={`${t.name} — ouvrir la fiche complète sur CoinGecko`}
              className="text-xs px-2.5 py-1.5 rounded-lg border border-border hover:border-border2 hover:text-accent transition-colors"
              style={{ background: "var(--surface)" }}>{body}</a>
          ) : (
            <span key={t.sym + i} className="text-xs px-2.5 py-1.5 rounded-lg border border-border"
              style={{ background: "var(--surface)" }}>{body}</span>
          );
        })}
      </div>
    </Card>
  );
}

// ---- Gagnants / Perdants 24 h (top 100 cap) ----
function Movers({ ck, onSelect }: { ck: any; onSelect: (m: any) => void }) {
  const gain = (ck.gainers ?? []) as any[];
  const lose = (ck.losers ?? []) as any[];
  if (!gain.length && !lose.length) return null;
  const Col = ({ title, rows, up }: { title: string; rows: any[]; up: boolean }) => (
    <div>
      <div className="text-muted text-[11px] uppercase tracking-wide mb-1.5">{title}</div>
      <div className="space-y-1">
        {rows.map((m) => (
          <button key={m.id ?? m.sym} onClick={() => onSelect(m)}
            title={`${m.name ?? m.sym} — voir le détail`}
            className="group w-full flex items-center justify-between text-sm border-t border-border py-1 hover:bg-surfaceAlt rounded px-1 -mx-1 transition-colors text-left">
            <span className="font-medium group-hover:text-accent transition-colors">{m.sym}</span>
            <span className="text-muted2 text-xs mono">{usd(m.price)}</span>
            <span className="mono" style={{ color: up ? "var(--pos)" : "#f43f5e" }}>{pct(m.chg24h)}</span>
          </button>
        ))}
      </div>
    </div>
  );
  return (
    <Card title="Gagnants / Perdants 24 h" source="CoinGecko · top 100 cap"
      hint="Mouvements extrêmes du jour parmi les 100 plus grosses capitalisations. Volatilité = opportunité et risque ; jamais de levier en paper.">
      <div className="grid md:grid-cols-2 gap-4">
        <Col title="📈 Gagnants" rows={gain} up />
        <Col title="📉 Perdants" rows={lose} up={false} />
      </div>
    </Card>
  );
}

// ---- Stablecoins : taille + écart au peg (santé de la liquidité) ----
function Stablecoins({ ck }: { ck: any }) {
  const st = (ck.stablecoins ?? []) as any[];
  if (!st.length) return null;
  return (
    <Card title="Stablecoins — liquidité & peg" source="DefiLlama · stablecoins"
      hint="La capitalisation stablecoin = poudre sèche prête à entrer. Un écart au peg (≠ $1.00) signale un stress de liquidité ou de confiance.">
      <div className="overflow-x-auto">
        <table className="w-full text-sm mono">
          <thead className="text-muted2 text-[11px]">
            <tr>
              <th className="text-left font-normal">stablecoin</th>
              <th className="text-right font-normal">capitalisation</th>
              <th className="text-right font-normal">prix</th>
              <th className="text-right font-normal">
                <span className="inline-flex items-center gap-1">écart au <InfoTip label="peg">{GLOSSARY.peg}</InfoTip></span>
              </th>
            </tr>
          </thead>
          <tbody>
            {st.map((s) => {
              const isYield = s.kind === "yield";
              const off = !isYield && typeof s.peg_dev === "number" && Math.abs(s.peg_dev) > 0.005;
              return (
                <tr key={s.sym} className="border-t border-border">
                  <td className="py-1.5 font-sans">
                    {s.sym}
                    {isYield && (
                      <span className="ml-1.5 text-[10px] px-1.5 py-0.5 rounded align-middle"
                        style={{ background: "var(--surface2)", color: "var(--muted2)" }}
                        title="Token à rendement : sa valeur (NAV) dérive volontairement de 1 $ — ce n'est pas un dépeg.">
                        rendement
                      </span>
                    )}
                  </td>
                  <td className="text-right">{usd(s.mcap)}</td>
                  <td className="text-right">{typeof s.price === "number" ? `$${s.price.toFixed(4)}` : "n/d"}</td>
                  <td className="text-right" style={{ color: off ? "#f43f5e" : "var(--muted2)" }}>
                    {isYield ? "—" : typeof s.peg_dev === "number" ? `${(s.peg_dev * 100).toFixed(2)}%` : "n/d"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

// ---- Jauge altseason (part du top 50 battant BTC sur 7 j) ----
function Altseason({ ck }: { ck: any }) {
  const a = ck.altseason;
  if (!a?.available) return null;
  const col = a.label === "Altseason" ? "var(--pos)" : a.label === "Bitcoin" ? "#f59e0b" : "var(--muted)";
  return (
    <Card title="Saison — Bitcoin vs Altcoins" source="dérivé CoinGecko · 7 j"
      hint="Part du top 50 (hors stablecoins) qui surperforme BTC sur 7 jours. ≥75 % = « altseason » (l'argent va vers les altcoins) ; ≤25 % = domination Bitcoin.">
      <div className="flex items-center gap-3 flex-wrap">
        <span className="text-sm font-semibold px-2.5 py-1 rounded-full"
          style={{ color: col, background: "color-mix(in srgb, " + col + " 15%, transparent)" }}>
          {a.label}
        </span>
        <span className="text-2xl mono font-semibold" style={{ color: col }}>
          {a.pct}%<span className="text-muted2 text-sm"> battent BTC</span>
        </span>
      </div>
      <div className="mt-3 h-2 rounded-full overflow-hidden" style={{ background: "var(--surface2)" }}>
        <div className="h-full rounded-full" style={{ width: `${a.pct}%`, background: col }} />
      </div>
      <div className="text-muted2 text-[11px] mt-1.5">
        sur {a.n} actifs · BTC {pct((a.btc_ret7d ?? 0) * 100)} sur 7 j
      </div>
    </Card>
  );
}

// ---- Compte à rebours du halving BTC ----
function Halving({ ck }: { ck: any }) {
  const h = ck.halving;
  if (!h?.available) return null;
  const eta = new Date(Date.now() + h.days_left * 86400_000);
  return (
    <Card title={`Halving Bitcoin — le ${h.number}ᵉ`} source="blockchain.info · hauteur de bloc réelle"
      hint="Tous les 210 000 blocs (~4 ans), la récompense de minage est divisée par deux → choc d'offre. Estimation à ~10 min/bloc.">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div><div className="text-muted text-xs">Dans</div><div className="text-lg mono">≈ {h.days_left} j</div></div>
        <div><div className="text-muted text-xs">Blocs restants</div><div className="text-lg mono">{h.blocks_left.toLocaleString("fr-FR")}</div></div>
        <div><div className="text-muted text-xs">Bloc du halving</div><div className="text-lg mono">{h.halving_block.toLocaleString("fr-FR")}</div></div>
        <div><div className="text-muted text-xs">Date estimée</div><div className="text-lg mono">{eta.toLocaleDateString("fr-FR", { month: "short", year: "numeric" })}</div></div>
      </div>
      <div className="mt-3 h-2 rounded-full overflow-hidden" style={{ background: "var(--surface2)" }}>
        <div className="h-full rounded-full" style={{ width: `${(h.progress * 100).toFixed(1)}%`, background: "var(--accent)" }} />
      </div>
      <div className="text-muted2 text-[11px] mt-1.5">{(h.progress * 100).toFixed(1)} % du cycle parcouru · hauteur {h.height.toLocaleString("fr-FR")}</div>
    </Card>
  );
}

// ---- Mini-graphe 7 j (SVG inline, depuis le sparkline déjà récupéré) ----
function Sparkline({ data, up }: { data: number[]; up: boolean }) {
  if (!data || data.length < 2) return null;
  const w = 320, h = 64;
  const min = Math.min(...data), max = Math.max(...data), rng = max - min || 1;
  const pts = data.map((v, i) =>
    `${(i / (data.length - 1)) * w},${h - ((v - min) / rng) * h}`).join(" ");
  const col = up ? "var(--pos)" : "#f43f5e";
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full" style={{ height: 64 }} preserveAspectRatio="none">
      <polyline points={pts} fill="none" stroke={col} strokeWidth="2"
        vectorEffect="non-scaling-stroke" strokeLinejoin="round" />
    </svg>
  );
}

// ---- Mini-fiche intégrée (clic sur une crypto → détail sans quitter le site) ----
function CoinModal({ coin, onClose }: { coin: any; onClose: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);
  if (!coin) return null;
  const sp = (coin.spark7d ?? []) as number[];
  const ret7 = sp.length >= 2 ? sp[sp.length - 1] / sp[0] - 1 : null;
  const href = cgCoin(coin.id);
  return (
    <div className="fixed inset-0 z-[70] grid place-items-center p-4" onClick={onClose}
      style={{ background: "rgba(0,0,0,.55)" }}>
      <div onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true"
        className="card p-5 w-full max-w-md" style={{ background: "var(--surface)" }}>
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="text-lg font-semibold">{coin.name ?? coin.sym}</div>
            <div className="text-muted2 text-xs mono">{coin.sym}</div>
          </div>
          <button onClick={onClose} aria-label="Fermer"
            className="text-muted2 hover:text-fg text-xl leading-none">×</button>
        </div>
        <div className="grid grid-cols-3 gap-3 mt-3">
          <div><div className="text-muted text-[11px]">Prix</div><div className="mono">{usd(coin.price)}</div></div>
          <div><div className="text-muted text-[11px]">24 h</div><div className="mono" style={{ color: tone(coin.chg24h) }}>{pct(coin.chg24h)}</div></div>
          <div><div className="text-muted text-[11px]">7 j</div><div className="mono" style={{ color: tone(ret7 == null ? null : ret7 * 100) }}>{ret7 == null ? "n/d" : pct(ret7 * 100)}</div></div>
        </div>
        {coin.mcap != null && (
          <div className="mt-2 text-[11px] text-muted2">Capitalisation : {usd(coin.mcap)}</div>
        )}
        {sp.length >= 2 ? (
          <div className="mt-3"><div className="text-muted text-[11px] mb-1">Prix 7 jours</div>
            <Sparkline data={sp} up={(ret7 ?? 0) >= 0} /></div>
        ) : (
          <div className="mt-3 text-muted2 text-xs">Pas de série 7 j pour cet actif.</div>
        )}
        {href && (
          <a href={href} {...EXT}
            className="mt-4 inline-block text-sm px-3 py-1.5 rounded-lg border border-border hover:border-border2 hover:text-accent transition-colors">
            Fiche complète sur CoinGecko →
          </a>
        )}
        <div className="mt-3 text-[10px] text-muted2">Contexte de marché — pas un conseil financier.</div>
      </div>
    </div>
  );
}

// ---- Dérivés : funding multi-CEX normalisé + sentiment levier ----
function Derivatives({ ck }: { ck: any }) {
  const d = ck.derivatives;
  if (!d?.available || !d.rows?.length) return null;
  const se = d.sentiment;
  const fpct = (x: any) => (typeof x === "number" ? `${(x * 100).toFixed(4)}%` : "n/d");
  const apct = (x: any) => (typeof x === "number" ? `${(x * 100).toFixed(1)}%` : "n/d");
  return (
    <Card title="Dérivés & levier — funding multi-CEX" source="Bybit · OKX · Binance (perp)"
      hint="Le funding des perpétuels : positif = les longs paient les shorts (longs surchauffés, biais contrarian baissier) ; négatif = shorts surchauffés. Normalisé sur 3 exchanges.">
      {se?.available && (
        <div className="mb-3 flex items-center gap-2 flex-wrap">
          <span className="text-sm font-semibold px-2.5 py-1 rounded-full"
            style={{ color: tone(-se.avg), background: "var(--surface2)" }}>{se.label}</span>
          <span className="text-muted2 text-xs">funding moyen {fpct(se.avg)} /8h · annualisé {apct(se.annualized)}</span>
        </div>
      )}
      <div className="overflow-x-auto">
        <table className="w-full text-sm mono">
          <thead className="text-muted2 text-[11px]">
            <tr>
              <th className="text-left font-normal">actif</th>
              <th className="text-right font-normal">Bybit</th>
              <th className="text-right font-normal">OKX</th>
              <th className="text-right font-normal">Binance</th>
              <th className="text-right font-normal">moyen /8h</th>
              <th className="text-right font-normal">annualisé</th>
            </tr>
          </thead>
          <tbody>
            {d.rows.map((r: any) => (
              <tr key={r.symbol} className="border-t border-border">
                <td className="py-1.5 font-sans font-medium">{r.symbol}</td>
                <td className="text-right text-muted2">{fpct(r.venues?.bybit)}</td>
                <td className="text-right text-muted2">{fpct(r.venues?.okx)}</td>
                <td className="text-right text-muted2">{fpct(r.venues?.binance)}</td>
                <td className="text-right" style={{ color: tone(-r.mean) }}>{fpct(r.mean)}</td>
                <td className="text-right" style={{ color: tone(-r.annualized) }}>{apct(r.annualized)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

export default function Crypto() {
  const { data, isLoading } = useCryptoCockpit();
  const [sel, setSel] = useState<any>(null);
  const [embed, setEmbed] = useState(false);
  useEffect(() => {                                  // mode embed (?embed=1) → vue compacte
    setEmbed(new URLSearchParams(window.location.search).get("embed") === "1");
  }, []);
  if (isLoading) return <PageSkeleton />;
  if (embed) {                                       // widget embarquable read-only (M5)
    return (
      <main className="max-w-xl mx-auto p-4 space-y-4">
        <LiveGauge />
        <ExpertLive />
        <a href="/Screening-Trading/crypto/" target="_blank" rel="noopener noreferrer"
          className="block text-center text-sm px-3 py-2 rounded-lg border border-border hover:border-border2 hover:text-accent transition-colors">
          Ouvrir dans Quant Terminal →
        </a>
      </main>
    );
  }
  return (
    <main className="max-w-5xl mx-auto p-6 space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h1 className="text-xl font-semibold tracking-tight">Cockpit crypto</h1>
        {data?.generated_at && (
          <span className="text-[11px] text-muted2 mono px-2 py-1 rounded-md border border-border"
            title="Horodatage du build (UTC). Le site est reconstruit chaque jour ouvré ; en cas de source indisponible, la dernière donnée valide est réutilisée.">
            ⟳ {new Date(data.generated_at).toLocaleString("fr-FR", {
              day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" })}
          </span>
        )}
      </div>
      <p className="text-muted text-sm">
        Vue marché agrégée, 100 % gratuite et sans clé — reconstruite chaque jour ouvré.
        Contexte de marché, <b>pas un conseil financier</b>.
      </p>
      <ShareBar sentiment={data?.sentiment} />
      {!data?.available ? (
        <EmptyState
          title="Cockpit crypto indisponible"
          hint={data?.reason === "QUANT_CRYPTO!=1"
            ? "Données réseau désactivées sur ce build (offline/tests). Activées au build quotidien des Pages."
            : `Sources temporairement injoignables (${data?.reason ?? "réseau"}).`}
        />
      ) : (
        <>
          <LiveGauge />
          <LiveChart />
          <ExpertLive />
          <Overview ck={data} />
          <Accumulation ck={data} />
          <Pulse ck={data} />
          <Altseason ck={data} />
          <Derivatives ck={data} />
          <Halving ck={data} />
          <Narratives ck={data} />
          <Movers ck={data} onSelect={setSel} />
          <Trending ck={data} />
          <Stablecoins ck={data} />
        </>
      )}
      {sel && <CoinModal coin={sel} onClose={() => setSel(null)} />}
    </main>
  );
}
