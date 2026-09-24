"use client";
// La mini-fiche ouverte au clic sur une crypto, et son mini-graphe 7 jours.
// Le graphe se trace depuis la série DÉJÀ récupérée : aucun appel supplémentaire.
import { useEffect } from "react";
import { usd, pct, tone, cgCoin, EXT } from "./format";

// ---- Mini-graphe 7 j (SVG inline, depuis le sparkline déjà récupéré) ----
export function Sparkline({ data, up }: { data: number[]; up: boolean }) {
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
export function CoinModal({ coin, onClose }: { coin: any; onClose: () => void }) {
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
