"use client";
// Composant 2 — JAUGE DE SENTIMENT LIVE (au-dessus du graphe). Normalise des flux hétérogènes
// en un score lissé 0-100 (low-pass 0.25). Client-direct (0 backend, aucune clé) :
//   FG       = (F&G−50)/50                 (alternative.me, refresh 60s)
//   Funding  = clamp(funding%8h · 40)      (Bybit, refresh 60s)
//   ΔOI      = clamp(ΔOI 24h / 8)          (Bybit, refresh 60s)
//   Momentum = clamp((prix/openBougie−1)·50)  (ticks WebSocket BTC, throttle 250ms)
// Poids renormalisés sur les facteurs DISPONIBLES → « n/d » ignoré, jamais inventé. Éducatif.
import { useEffect, useRef, useState } from "react";

const clamp = (x: number) => Math.max(-1, Math.min(1, x));
const W = { fg: 0.35, mom: 0.25, fund: 0.25, oi: 0.15 };

async function j(u: string) {
  const r = await fetch(u);
  if (!r.ok) throw new Error(String(r.status));
  return r.json();
}

export default function LiveGauge() {
  const [score, setScore] = useState<number | null>(null);
  const [f, setF] = useState<{ fg: number | null; fund: number | null; oi: number | null;
    mom: number | null }>({ fg: null, fund: null, oi: null, mom: null });

  // valeurs courantes (refs → pas de re-render à chaque tick)
  const fac = useRef({ fg: null as number | null, fund: null as number | null,
    oi: null as number | null });
  const px = useRef<number | null>(null);
  const hourOpen = useRef<{ bucket: number; open: number } | null>(null);
  const smooth = useRef<number | null>(null);

  // 1) données lentes : F&G + funding + ΔOI (refresh 60s)
  useEffect(() => {
    let alive = true;
    const slow = async () => {
      try {
        const v = (await j("https://api.alternative.me/fng/?limit=1")).data?.[0];
        if (alive && v) fac.current.fg = parseFloat(v.value);
      } catch { /* n/d */ }
      try {
        const t = await j("https://api.bybit.com/v5/market/tickers?category=linear&symbol=BTCUSDT");
        const row = t.result?.list?.[0];
        if (alive && row) fac.current.fund = parseFloat(row.fundingRate) * 100;
        const h = await j("https://api.bybit.com/v5/market/open-interest"
          + "?category=linear&symbol=BTCUSDT&intervalTime=1d&limit=2");
        const l = h.result?.list || [];
        if (alive && l.length >= 2) {
          const a = parseFloat(l[0].openInterest), b = parseFloat(l[1].openInterest);
          if (b) fac.current.oi = ((a - b) / b) * 100;
        }
      } catch { /* n/d */ }
    };
    slow();
    const id = setInterval(() => { if (!document.hidden) slow(); }, 60000);
    return () => { alive = false; clearInterval(id); };
  }, []);

  // 2) ticks WS BTC → prix + open horaire (momentum)
  useEffect(() => {
    let ws: WebSocket | null = null, stop = false, backoff = 1000;
    const connect = () => {
      if (stop) return;
      try { ws = new WebSocket("wss://ws-feed.exchange.coinbase.com"); }
      catch { return; }
      ws.onopen = () => { backoff = 1000;
        ws?.send(JSON.stringify({ type: "subscribe", product_ids: ["BTC-USD"],
          channels: ["ticker"] })); };
      ws.onmessage = (e) => {
        let m: any; try { m = JSON.parse(e.data); } catch { return; }
        if (m.type !== "ticker" || !m.price) return;
        const p = parseFloat(m.price);
        px.current = p;
        const bucket = Math.floor(Date.now() / 3600000);
        if (!hourOpen.current || hourOpen.current.bucket !== bucket)
          hourOpen.current = { bucket, open: p };
      };
      ws.onclose = () => { if (stop) return;
        backoff = Math.min(backoff * 2, 30000); setTimeout(connect, backoff); };
      ws.onerror = () => ws?.close();
    };
    const onVis = () => { if (document.hidden) ws?.close();
      else if (!ws || ws.readyState > 1) connect(); };
    document.addEventListener("visibilitychange", onVis);
    connect();
    return () => { stop = true; document.removeEventListener("visibilitychange", onVis);
      try { ws?.close(); } catch { /* noop */ } };
  }, []);

  // 3) recompose le score toutes les 250ms (throttle momentum) + low-pass 0.25
  useEffect(() => {
    const tick = () => {
      const c = fac.current;
      let mom: number | null = null;
      if (px.current != null && hourOpen.current?.open)
        mom = clamp((px.current / hourOpen.current.open - 1) * 50);
      const parts: [number, number][] = [];           // [poids, valeur normalisée]
      if (c.fg != null) parts.push([W.fg, clamp((c.fg - 50) / 50)]);
      if (mom != null) parts.push([W.mom, mom]);
      if (c.fund != null) parts.push([W.fund, clamp(c.fund * 40)]);
      if (c.oi != null) parts.push([W.oi, clamp(c.oi / 8)]);
      setF({ fg: c.fg, fund: c.fund, oi: c.oi, mom });
      if (!parts.length) return;
      const wsum = parts.reduce((s, [w]) => s + w, 0);
      const raw = parts.reduce((s, [w, v]) => s + w * v, 0) / wsum;
      const target = 50 + 50 * raw;
      smooth.current = smooth.current == null ? target
        : smooth.current + 0.25 * (target - smooth.current);   // low-pass
      setScore(Math.round(smooth.current));
    };
    const id = setInterval(tick, 250);
    return () => clearInterval(id);
  }, []);

  const label = score == null ? "…" : score >= 66 ? "Bullish" : score <= 34 ? "Bearish" : "Neutre";
  const col = score == null ? "#6b7d86" : score >= 66 ? "#22c55e" : score <= 34 ? "#f43f5e" : "#f59e0b";
  const chip = (k: string, v: string) => (
    <span className="text-[11px] px-2 py-0.5 rounded border border-border text-muted2"
      style={{ background: "var(--surface)" }}>{k} {v}</span>
  );

  return (
    <section className="card p-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h2 className="text-sm uppercase tracking-wide text-muted">Jauge de sentiment live</h2>
        <span className="text-lg mono font-semibold" style={{ color: col }}>
          {score ?? "n/d"}<span className="text-muted2 text-xs">/100 · {label}</span></span>
      </div>
      <p className="text-muted2 text-[11px] mt-0.5">sentiment live · sources affichées, aucun conseil</p>

      <div className="relative mt-3 h-3 rounded-full"
        style={{ background: "linear-gradient(90deg,#f43f5e,#f59e0b,#22c55e)" }}>
        {score != null && (
          <div className="absolute top-1/2" style={{ left: `${score}%`,
            transform: "translate(-50%,-50%)" }}>
            <div className="w-3 h-3 rounded-full border-2 border-white"
              style={{ background: col, boxShadow: "0 0 8px rgba(0,0,0,.5)" }} />
          </div>
        )}
      </div>

      <div className="flex flex-wrap gap-2 mt-3">
        {chip("Fear & Greed", f.fg != null ? f.fg.toFixed(0) : "n/d")}
        {chip("Funding 8h", f.fund != null ? `${f.fund >= 0 ? "+" : ""}${f.fund.toFixed(4)}%` : "n/d")}
        {chip("OI 24h", f.oi != null ? `${f.oi >= 0 ? "+" : ""}${f.oi.toFixed(1)}%` : "n/d")}
        {chip("Momentum", f.mom != null ? f.mom.toFixed(2) : "n/d")}
      </div>
    </section>
  );
}
