"use client";
// Bandeau « terminal » façon Bloomberg — UNE ligne défilant en continu.
// ACTIONS (top 20) : dernière clôture + variation J, bakées au build (useTicker) — pas de live
// actions gratuit/CORS navigateur. CRYPTOS (top 10) : prix + 24h LIVE via WebSocket navigateur
// (Coinbase, 0 backend, aucune clé). PERF : ticks crypto bufferisés, flush 500 ms (1 re-render).
// Dégrade en « … » si une source manque. Éducatif, aucun conseil.
import { useEffect, useRef, useState } from "react";
import { useTicker } from "@/lib/api";

const CRYPTO = ["BTC", "ETH", "SOL", "XRP", "ADA", "DOGE", "AVAX", "LINK", "DOT", "LTC"];
const PRODS = CRYPTO.map((s) => `${s}-USD`);
type Row = { price: number; chg: number | null };

export default function LandingTicker() {
  const { data: tk } = useTicker();                  // actions (clôture J), build-time
  const buf = useRef<Record<string, Row>>({});       // ticks crypto (mutable)
  const [crypto, setCrypto] = useState<Record<string, Row>>({});
  const [reduce, setReduce] = useState(false);
  const [paused, setPaused] = useState(false);       // pause au survol → cliquable

  useEffect(() => {
    setReduce(window.matchMedia("(prefers-reduced-motion: reduce)").matches);
    let ws: WebSocket | null = null, stop = false, backoff = 1000;
    const connect = () => {
      if (stop) return;
      try { ws = new WebSocket("wss://ws-feed.exchange.coinbase.com"); } catch { return; }
      ws.onopen = () => { backoff = 1000;
        ws?.send(JSON.stringify({ type: "subscribe", product_ids: PRODS,
          channels: ["ticker"] })); };
      ws.onmessage = (e) => {                          // BUFFER seulement
        let m: any; try { m = JSON.parse(e.data); } catch { return; }
        if (m.type !== "ticker" || !m.price || !m.product_id) return;
        const price = parseFloat(m.price), open = parseFloat(m.open_24h);
        buf.current[m.product_id] = { price, chg: open ? (price / open - 1) * 100 : null };
      };
      ws.onclose = () => { if (stop) return;
        backoff = Math.min(backoff * 2, 30000); setTimeout(connect, backoff); };
      ws.onerror = () => ws?.close();
    };
    const onVis = () => { if (document.hidden) ws?.close();
      else if (!ws || ws.readyState > 1) connect(); };
    document.addEventListener("visibilitychange", onVis);
    connect();
    const flush = setInterval(() => setCrypto({ ...buf.current }), 500);
    return () => { stop = true; clearInterval(flush);
      document.removeEventListener("visibilitychange", onVis);
      try { ws?.close(); } catch { /* noop */ } };
  }, []);

  // Clic → fiche société/crypto sur TradingView (nouvel onglet).
  const href = (sym: string, live: boolean) =>
    `https://www.tradingview.com/symbols/${live ? sym + "USD" : sym.replace("-", ".")}/`;
  const cell = (sym: string, r: Row | null | undefined, live: boolean) => {
    // Vert si en gain sur la journée, rouge si en baisse (gris si donnée absente).
    const col = !r || r.chg == null ? "#9fb4bd" : r.chg >= 0 ? "#22c55e" : "#f43f5e";
    const arr = !r || r.chg == null ? "" : r.chg >= 0 ? "▲" : "▼";
    const px = r ? r.price.toLocaleString("en-US",
      { maximumFractionDigits: r.price >= 100 ? 2 : 4 }) : "…";
    const pct = r && r.chg != null ? ` ${arr}${Math.abs(r.chg).toFixed(2)}%` : "";
    return (
      <a key={(live ? "c-" : "s-") + sym} href={href(sym, live)} target="_blank"
        rel="noopener noreferrer" title={`${sym} — plus d'informations`}
        style={{ marginRight: "2.2rem", color: col, textDecoration: "none",
          fontVariantNumeric: "tabular-nums" }}>
        <b style={{ letterSpacing: ".04em" }}>{sym}</b> {px}{pct}
      </a>
    );
  };

  const stocks = (tk?.available ? tk.stocks : []) as { sym: string; price: number; chg: number | null }[];
  const Strip = (
    <span style={{ display: "inline-block" }}>
      {stocks.map((s) => cell(s.sym, { price: s.price, chg: s.chg }, false))}
      {CRYPTO.map((s) => cell(s, crypto[`${s}-USD`], true))}
    </span>
  );
  // Durée CONSTANTE (ne dépend PAS du nombre d'items) → l'animation ne redémarre jamais
  // quand les actions chargent ou que les prix changent (sinon : saut/bug de défilement).
  const dur = "75s";

  return (
    <div onMouseEnter={() => setPaused(true)} onMouseLeave={() => setPaused(false)}
      title="Survol = pause · clic sur un actif = plus d'infos" style={{
        borderBottom: "1px solid rgba(94,234,212,.14)", background: "rgba(5,8,11,.85)",
        overflow: "hidden", whiteSpace: "nowrap", fontFamily: "ui-monospace, monospace",
        fontSize: ".74rem", padding: ".45rem 0", position: "relative", zIndex: 2,
      }}>
      {reduce ? (
        <div style={{ paddingLeft: "1.5rem", overflowX: "auto" }}>{Strip}</div>
      ) : (
        <div style={{ display: "inline-block", willChange: "transform",
          animation: `qt-ticker ${dur} linear infinite`,
          animationPlayState: paused ? "paused" : "running" }}>
          {Strip}{Strip}
        </div>
      )}
      <style>{"@keyframes qt-ticker{from{transform:translateX(0)}to{transform:translateX(-50%)}}"}</style>
    </div>
  );
}
