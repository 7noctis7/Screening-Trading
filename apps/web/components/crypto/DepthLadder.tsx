"use client";
// Pilier 5 « sonar » — carnet d'ordres en DENSITÉ live (depth ladder). WebSocket navigateur
// Binance (gratuit, sans clé, 0 backend). Asks (rouge) au-dessus du mid, bids (vert) en dessous ;
// largeur de barre ∝ taille → on VOIT les murs de liquidité. Buffer + flush 200ms (pas de lag).
// Dégrade proprement si le flux tombe. Éducatif, aucun conseil.
import { useEffect, useRef, useState } from "react";

const SYMS = ["BTC", "ETH", "SOL"] as const;
type Lvl = [number, number];                         // [prix, taille]

export default function DepthLadder() {
  const [sym, setSym] = useState<(typeof SYMS)[number]>("BTC");
  const buf = useRef<{ bids: Lvl[]; asks: Lvl[] } | null>(null);
  const [book, setBook] = useState<{ bids: Lvl[]; asks: Lvl[] } | null>(null);
  const [live, setLive] = useState(false);

  useEffect(() => {
    buf.current = null; setBook(null); setLive(false);
    let ws: WebSocket | null = null, stop = false, backoff = 1000;
    const url = `wss://stream.binance.com:9443/ws/${sym.toLowerCase()}usdt@depth20@100ms`;
    const connect = () => {
      if (stop) return;
      try { ws = new WebSocket(url); } catch { return; }
      ws.onopen = () => { setLive(true); backoff = 1000; };
      ws.onmessage = (e) => {
        let m: any; try { m = JSON.parse(e.data); } catch { return; }
        const bids = (m.bids || m.b || []).map((l: string[]) => [+l[0], +l[1]] as Lvl);
        const asks = (m.asks || m.a || []).map((l: string[]) => [+l[0], +l[1]] as Lvl);
        if (bids.length && asks.length) buf.current = { bids, asks };
      };
      ws.onclose = () => { setLive(false); if (stop) return;
        backoff = Math.min(backoff * 2, 30000); setTimeout(connect, backoff); };
      ws.onerror = () => ws?.close();
    };
    const onVis = () => { if (document.hidden) ws?.close();
      else if (!ws || ws.readyState > 1) connect(); };
    document.addEventListener("visibilitychange", onVis);
    connect();
    const flush = setInterval(() => { if (buf.current) setBook({ ...buf.current }); }, 200);
    return () => { stop = true; clearInterval(flush);
      document.removeEventListener("visibilitychange", onVis);
      try { ws?.close(); } catch { /* noop */ } };
  }, [sym]);

  const N = 12;
  const asks = (book?.asks ?? []).slice(0, N);
  const bids = (book?.bids ?? []).slice(0, N);
  const maxSz = Math.max(1e-9, ...asks.map((l) => l[1]), ...bids.map((l) => l[1]));
  const mid = asks.length && bids.length ? (asks[0][0] + bids[0][0]) / 2 : null;
  const fmtP = (p: number) => p.toLocaleString("en-US", { maximumFractionDigits: p >= 100 ? 1 : 4 });
  const fmtS = (s: number) => s.toLocaleString("en-US", { maximumFractionDigits: 3 });

  const Row = ({ l, side }: { l: Lvl; side: "ask" | "bid" }) => {
    const col = side === "ask" ? "#f43f5e" : "#22c55e";
    const w = `${Math.max(2, (l[1] / maxSz) * 100)}%`;
    return (
      <div style={{ position: "relative", display: "flex", justifyContent: "space-between",
        padding: "1px 6px", fontSize: ".72rem", fontVariantNumeric: "tabular-nums" }}>
        <div style={{ position: "absolute", inset: 0, width: w,
          [side === "ask" ? "right" : "left"]: 0,
          background: `color-mix(in srgb, ${col} 22%, transparent)` } as any} />
        <span style={{ position: "relative", color: col }}>{fmtP(l[0])}</span>
        <span style={{ position: "relative", color: "var(--muted2)" }}>{fmtS(l[1])}</span>
      </div>
    );
  };

  return (
    <section className="card p-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h2 className="text-sm uppercase tracking-wide text-muted">Carnet d'ordres — densité (sonar)</h2>
        <div className="flex items-center gap-2">
          {SYMS.map((p) => (
            <button key={p} onClick={() => setSym(p)}
              className={`text-xs px-2 py-1 rounded-lg border transition-colors ${
                sym === p ? "border-border2 text-fg" : "border-border text-muted hover:text-fg"}`}
              style={{ background: sym === p ? "var(--surface2)" : "var(--surface)" }}>{p}</button>
          ))}
          <span className="inline-block w-1.5 h-1.5 rounded-full" title={live ? "live" : "connexion"}
            style={{ background: live ? "#22c55e" : "#6b7d86", boxShadow: live ? "0 0 8px #22c55e" : "none" }} />
        </div>
      </div>
      <p className="text-muted2 text-[11px] mt-1">
        Murs de liquidité en direct (Binance WebSocket). Barre large = grosse taille passive.</p>
      {!book ? (
        <div className="shimmer rounded-md bg-surfaceAlt h-64 mt-3" />
      ) : (
        <div className="mt-3 font-mono">
          {asks.slice().reverse().map((l, i) => <Row key={"a" + i} l={l} side="ask" />)}
          {mid != null && (
            <div className="text-center text-xs py-1 my-0.5 rounded"
              style={{ background: "var(--surface2)", color: "var(--accent2)" }}>
              mid {fmtP(mid)} · spread {fmtP(asks[0][0] - bids[0][0])}
            </div>
          )}
          {bids.map((l, i) => <Row key={"b" + i} l={l} side="bid" />)}
        </div>
      )}
    </section>
  );
}
