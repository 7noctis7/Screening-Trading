"use client";
// Cockpit crypto — vue marché agrégée, gratuite (sans clé). Chaque section est pédagogique :
// une donnée, sa source, son explication. Aucun chiffre inventé : "n/d" si la source tombe.
import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { useCryptoCockpit } from "@/lib/api";
import { PageSkeleton, EmptyState } from "@/components/ui";
import { ShareBar } from "@/components/crypto/ShareBar";
import { MountWhenVisible } from "@/components/MountWhenVisible";
import { Card } from "@/components/crypto/Card";
import { usd, pct, tone, cgCoin, cgCat, EXT } from "@/components/crypto/format";
import { ThemesRecherches, VolumeTop } from "@/components/crypto/AttentionEtVolume";
import { Label } from "@/components/crypto/glossaire";
import { Stablecoins, Altseason, Halving } from "@/components/crypto/SanteMarche";
import { CoinModal } from "@/components/crypto/FicheCrypto";

// Jauge de sentiment live (au-dessus du graphe) — client-only.
const LiveGauge = dynamic(() => import("@/components/crypto/LiveGauge"), { ssr: false });
// Graphe live (WebSocket navigateur) — client-only, jamais SSR (compatible export statique).
const LiveChart = dynamic(() => import("@/components/crypto/LiveChart"), { ssr: false });
// Sonar — carnet d'ordres en densité (Binance WebSocket), client-only.
const DepthLadder = dynamic(() => import("@/components/crypto/DepthLadder"), { ssr: false });
// Bloc « Analyse experte · Œil de Hasheur » LIVE (client-direct, auto-refresh visible-only).
const ExpertLive = dynamic(() => import("@/components/crypto/ExpertLive"), { ssr: false });

const SENTI: Record<string, { c: string; bg: string; label: string }> = {
  BULLISH: { c: "var(--pos)", bg: "color-mix(in srgb, var(--pos) 15%, transparent)", label: "🟢 BULLISH" },
  BEARISH: { c: "#f43f5e", bg: "color-mix(in srgb, #f43f5e 15%, transparent)", label: "🔴 BEARISH" },
  NEUTRE: { c: "var(--warn)", bg: "color-mix(in srgb, var(--warn) 15%, transparent)", label: "🟡 NEUTRE" },
};

// ---- Aperçu : sentiment marché synthétique (déterministe, dérivé du cockpit) ----
function Overview({ ck }: { ck: any }) {
  const se = ck.sentiment;
  if (!se?.available) return null;
  const s = SENTI[se.label] ?? SENTI.NEUTRE;
  return (
    <Card title="Aperçu — humeur du marché" source="calcul reproductible · aucun chiffre inventé"
      hint="Une note de 0 à 100 : la moyenne des indicateurs disponibles ce jour (l'indice de peur, la variation sur 24 h, la proportion d'actifs en hausse). C'est un thermomètre d'ambiance, pas un signal d'achat.">
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
    <Card title="Est-ce le moment où les gros acheteurs se positionnent ?" source="lecture à contre-courant · calcul reproductible"
      hint="Une note de 0 à 100 qui va à l'inverse de la foule. Haut = tout le monde a peur, beaucoup parient sur la baisse, et de l'argent attend sur le côté : historiquement, le moment où les gros acheteurs se placent. Bas = euphorie générale, plutôt le moment où ils revendent. C'est un contexte, pas un signal d'achat.">
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
      hint="Quand la part du Bitcoin monte, les investisseurs se réfugient sur la crypto la plus établie ; quand elle baisse, ils prennent plus de risques sur les autres. Le « TVL » est l'argent déposé dans les services financiers décentralisés : il mesure leur usage réel.">
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
    <Card title="Les thèmes qui marchent en ce moment" source="CoinGecko · catégories"
      hint="Quelle famille de cryptos monte le plus aujourd'hui (intelligence artificielle, actifs du monde réel, réseaux rapides, memes…). Voir un thème dominer, c'est voir où l'argent se déplace.">
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
    <Card title="Ce que tout le monde cherche" source="CoinGecko · recherches les plus fréquentes"
      hint="Les cryptos les plus recherchées en ce moment. Attention : quand une crypto arrive ici, le mouvement a souvent déjà eu lieu. C'est un thermomètre de l'attention du public, pas un signal d'entrée.">
      <div className="flex flex-wrap gap-2">
        {tr.map((t, i) => {
          const href = cgCoin(t.id);
          // LA VARIATION REND LA THÈSE DE LA CARTE VÉRIFIABLE. Le chapeau affirme que
          // « le mouvement a souvent déjà eu lieu » ; sans chiffre à côté, c'est un
          // slogan. « n/d » est une réponse honnête : la moitié de ces lignes sont des
          // rangs au-delà du 500ᵉ, hors du top 100 et sans variation publiée.
          const body = (
            <>
              <span className="text-muted2">#{t.rank ?? "—"}</span> <b>{t.sym}</b>{" "}
              <span className="text-muted">{t.name}</span>{" "}
              <span style={{ color: tone(t.chg24h) }}>{pct(t.chg24h)}</span>
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
    <Card title="Plus fortes hausses et baisses du jour" source="CoinGecko · les 100 plus grosses cryptos"
      hint="Les mouvements les plus violents des dernières 24 heures parmi les 100 plus grosses cryptos. Ce qui bouge fort peut rapporter gros et faire perdre autant — et ici, jamais d'argent emprunté.">
      <div className="grid md:grid-cols-2 gap-4">
        <Col title="📈 Gagnants" rows={gain} up />
        <Col title="📉 Perdants" rows={lose} up={false} />
      </div>
    </Card>
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
    <Card title="Qui paie qui chez ceux qui jouent avec de l'argent emprunté" source="Bybit · OKX · Binance"
      hint="Sur ces plateformes, ceux qui parient à la hausse et ceux qui parient à la baisse se versent régulièrement de l'argent, selon qui est le plus nombreux. Un chiffre positif : les parieurs à la hausse paient — ils sont trop nombreux, ce qui annonce souvent une correction. Négatif : c'est l'inverse. Moyenne de trois plateformes.">
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
            title="Heure de la dernière reconstruction du site (heure UTC). Il est refait chaque jour ouvré ; si une source ne répond pas, la dernière valeur correcte est conservée plutôt que remplacée par une estimation.">
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
          title="Les données crypto ne sont pas disponibles"
          hint={data?.reason === "QUANT_CRYPTO!=1"
            ? "Données réseau désactivées sur ce build (offline/tests). Activées au build quotidien des Pages."
            : `Sources temporairement injoignables (${data?.reason ?? "réseau"}).`}
        />
      ) : (
        <>
          <MountWhenVisible minHeight={120} label="la jauge de sentiment"><LiveGauge /></MountWhenVisible>
          <MountWhenVisible minHeight={420} label="le graphe live"><LiveChart /></MountWhenVisible>
          <MountWhenVisible minHeight={360} label="le sonar du carnet"><DepthLadder /></MountWhenVisible>
          <MountWhenVisible minHeight={300} label="l'analyse experte"><ExpertLive /></MountWhenVisible>
          <Overview ck={data} />
          <Accumulation ck={data} />
          <Pulse ck={data} />
          <Altseason ck={data} />
          <Derivatives ck={data} />
          <Halving ck={data} />
          <Narratives ck={data} />
          <Movers ck={data} onSelect={setSel} />
          <Trending ck={data} />
          <ThemesRecherches ck={data} />
          <VolumeTop ck={data} />
          <Stablecoins ck={data} />
        </>
      )}
      {sel && <CoinModal coin={sel} onClose={() => setSel(null)} />}
    </main>
  );
}
