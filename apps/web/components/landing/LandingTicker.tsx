"use client";
// Bandeau « terminal » façon Bloomberg — ticker LIVE (BTC/ETH/SOL) via WebSocket navigateur
// (Coinbase, 0 backend, aucune clé). Monospace, défilement (coupé si prefers-reduced-motion).
// Dégrade en « — » si le flux tombe. Éducatif, aucun conseil.
import { useEffect, useRef, useState } from "react";

const PRODS = ["BTC-USD", "ETH-USD", "SOL-USD"];
type Row = { sym: string; price: number; chg: number | null };

export default function LandingTicker() {
  const [rows, setRows] = useState<Record<string, Row>>({});
  const [reduce, setReduce] = useState(false);

  useEffect(() => {
    setReduce(window.matchMedia("(prefers-reduced-motion: reduce)").matches);
    let ws: WebSocket | null = null, stop = false, backoff = 1000;
    const connect = () => {
      if (stop) return;
      try { ws = new WebSocket("wss://ws-feed.exchange.coinbase.com"); } catch { return; }
      ws.onopen = () => { backoff = 1000;
        ws?.send(JSON.stringify({ type: "subscribe", product_ids: PRODS,
          channels: ["ticker"] })); };
      ws.onmessage = (e) => {
        let m: any; try { m = JSON.parse(e.data); } catch { return; }
        if (m.type !== "ticker" || !m.price) return;
        const price = parseFloat(m.price);
        const open = parseFloat(m.open_24h);
        const chg = open ? (price / open - 1) * 100 : null;
        setRows((r) => ({ ...r, [m.product_id]:
          { sym: m.product_id.replace("-USD", ""), price, chg } }));
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

  const items = PRODS.map((p) => {
    const r = rows[p];
    const sym = p.replace("-USD", "");
    if (!r) return { sym, txt: "—", col: "#6b7d86" };
    const col = r.chg == null ? "#9fb4bd" : r.chg >= 0 ? "#22c55e" : "#f43f5e";
    const arr = r.chg == null ? "" : r.chg >= 0 ? "▲" : "▼";
    const px = r.price.toLocaleString("en-US", { maximumFractionDigits: 2 });
    return { sym, txt: `${px} ${arr}${r.chg == null ? "" : Math.abs(r.chg).toFixed(2) + "%"}`, col };
  });
  const Strip = (
    <span style={{ display: "inline-flex", gap: "2.5rem", paddingRight: "2.5rem" }}>
      {items.map((it, i) => (
        <span key={i} style={{ fontVariantNumeric: "tabular-nums" }}>
          <b style={{ color: "#5eead4", letterSpacing: ".05em" }}>{it.sym}</b>{" "}
          <span style={{ color: it.col }}>{it.txt}</span>
        </span>
      ))}
    </span>
  );

  return (
    <div aria-hidden="true" style={{
      borderBottom: "1px solid rgba(94,234,212,.14)", background: "rgba(5,8,11,.85)",
      overflow: "hidden", whiteSpace: "nowrap", fontFamily: "ui-monospace, monospace",
      fontSize: ".74rem", padding: ".45rem 0", position: "relative", zIndex: 2,
    }}>
      {reduce ? (
        <div style={{ paddingLeft: "1.5rem" }}>{Strip}</div>
      ) : (
        <div style={{ display: "inline-block", animation: "qt-ticker 22s linear infinite" }}>
          {Strip}{Strip}{Strip}
        </div>
      )}
      <style>{"@keyframes qt-ticker{from{transform:translateX(0)}to{transform:translateX(-33.33%)}}"}</style>
    </div>
  );
}
