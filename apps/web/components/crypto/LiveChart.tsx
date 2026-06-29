"use client";
// Graphe crypto LIVE — bougies 1 h (Coinbase REST) + ticks temps réel (WebSocket NAVIGATEUR).
// 100 % client-direct (site statique, 0 backend, aucune clé). Dégrade en « n/d » si CORS/réseau
// bloque le backfill ; le WS part du navigateur (pas de géoblocage serveur). Éducatif, aucun conseil.
import { useEffect, useRef, useState } from "react";

const PAIRS = ["BTC-USD", "ETH-USD", "SOL-USD"] as const;
type Pair = (typeof PAIRS)[number];
const CDNS = [
  "https://unpkg.com/lightweight-charts/dist/lightweight-charts.standalone.production.js",
  "https://cdn.jsdelivr.net/npm/lightweight-charts/dist/lightweight-charts.standalone.production.js",
];

// Charge la lib TradingView en UMD (lazy, multi-CDN). Résout window.LightweightCharts.
function loadLib(): Promise<any> {
  const w = window as any;
  if (w.LightweightCharts) return Promise.resolve(w.LightweightCharts);
  const tryCdn = (i: number): Promise<any> =>
    new Promise((resolve, reject) => {
      if (i >= CDNS.length) return reject(new Error("CDN KO"));
      const s = document.createElement("script");
      s.src = CDNS[i];
      s.async = true;
      s.onload = () => resolve(w.LightweightCharts);
      s.onerror = () => tryCdn(i + 1).then(resolve, reject);
      document.head.appendChild(s);
    });
  return tryCdn(0);
}

export default function LiveChart() {
  const box = useRef<HTMLDivElement>(null);
  const [pair, setPair] = useState<Pair>("BTC-USD");
  const [live, setLive] = useState(false);
  const [last, setLast] = useState<number | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let chart: any, series: any, ws: WebSocket | null = null, ro: ResizeObserver | null = null;
    let stop = false, backoff = 1000, cur: any = null, raf = 0;
    const el = box.current;
    if (!el) return;

    const start = async () => {
      let LWC: any;
      try {
        LWC = await loadLib();
      } catch {
        setErr("Graphe indisponible (CDN). n/d.");
        return;
      }
      if (stop) return;
      chart = LWC.createChart(el, {
        layout: { background: { color: "transparent" }, textColor: "#8aa0a9" },
        grid: { vertLines: { color: "rgba(255,255,255,.04)" },
                horzLines: { color: "rgba(255,255,255,.04)" } },
        rightPriceScale: { borderColor: "rgba(255,255,255,.08)" },
        timeScale: { borderColor: "rgba(255,255,255,.08)", timeVisible: true },
        height: 360,
      });
      series = chart.addCandlestickSeries({
        upColor: "#22c55e", downColor: "#f43f5e", borderVisible: false,
        wickUpColor: "#22c55e", wickDownColor: "#f43f5e",
      });
      ro = new ResizeObserver(() => chart.applyOptions({ width: el.clientWidth }));
      ro.observe(el);
      await backfill();
      connect();
    };

    // Backfill bougies 1 h via Coinbase REST (client-direct ; n/d si CORS bloque).
    const backfill = async () => {
      try {
        const u = `https://api.exchange.coinbase.com/products/${pair}/candles?granularity=3600`;
        const r = await fetch(u);
        if (!r.ok) throw new Error(String(r.status));
        const raw: number[][] = await r.json();      // [time, low, high, open, close, vol]
        const data = raw
          .map((c) => ({ time: c[0], low: c[1], high: c[2], open: c[3], close: c[4] }))
          .sort((a, b) => a.time - b.time);
        series.setData(data);
        cur = data[data.length - 1] ?? null;
        if (cur) setLast(cur.close);
        chart.timeScale().fitContent();
      } catch {
        setErr("Backfill bougies n/d (CORS) — ticks live seulement.");
      }
    };

    // WebSocket NAVIGATEUR → ticker Coinbase ; met à jour la bougie 1 h en cours.
    const connect = () => {
      if (stop) return;
      try {
        ws = new WebSocket("wss://ws-feed.exchange.coinbase.com");
      } catch {
        setLive(false);
        return;
      }
      ws.onopen = () => {
        setLive(true);
        backoff = 1000;
        ws?.send(JSON.stringify({ type: "subscribe", product_ids: [pair],
                                  channels: ["ticker"] }));
      };
      ws.onmessage = (e) => {
        let m: any;
        try { m = JSON.parse(e.data); } catch { return; }
        if (m.type !== "ticker" || !m.price) return;
        const px = parseFloat(m.price);
        if (!raf) raf = requestAnimationFrame(() => { raf = 0; setLast(px); });
        const bucket = Math.floor(Date.now() / 3600000) * 3600;   // bougie 1 h courante
        if (!cur || bucket > cur.time) {
          cur = { time: bucket, open: px, high: px, low: px, close: px };
        } else {
          cur.high = Math.max(cur.high, px); cur.low = Math.min(cur.low, px); cur.close = px;
        }
        try { series.update(cur); } catch { /* série pas prête */ }
      };
      ws.onclose = () => {
        setLive(false);
        if (stop) return;
        backoff = Math.min(backoff * 2, 30000);       // reconnexion backoff exponentiel
        setTimeout(connect, backoff);
      };
      ws.onerror = () => ws?.close();
    };

    // Pause quand l'onglet est caché (économie batterie/CPU).
    const onVis = () => {
      if (document.hidden) { ws?.close(); }
      else if (!ws || ws.readyState > 1) { connect(); }
    };
    document.addEventListener("visibilitychange", onVis);
    start();

    return () => {
      stop = true;
      document.removeEventListener("visibilitychange", onVis);
      ro?.disconnect();
      try { ws?.close(); } catch { /* noop */ }
      try { chart?.remove(); } catch { /* noop */ }
      if (raf) cancelAnimationFrame(raf);
    };
  }, [pair]);

  return (
    <section className="card p-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h2 className="text-sm uppercase tracking-wide text-muted">Graphe live</h2>
        <div className="flex items-center gap-2">
          {PAIRS.map((p) => (
            <button key={p} onClick={() => setPair(p)}
              className={`text-xs px-2 py-1 rounded-lg border transition-colors ${
                pair === p ? "border-border2 text-fg" : "border-border text-muted hover:text-fg"}`}
              style={{ background: pair === p ? "var(--surface2)" : "var(--surface)" }}>
              {p.replace("-USD", "")}
            </button>
          ))}
        </div>
      </div>
      <div className="flex items-center gap-2 mt-1 text-[11px]">
        <span className="inline-flex items-center gap-1">
          <span className="inline-block w-1.5 h-1.5 rounded-full"
            style={{ background: live ? "#22c55e" : "#6b7d86",
                     boxShadow: live ? "0 0 8px #22c55e" : "none" }} />
          <span className="text-muted2">{live ? "live" : "connexion…"}</span>
        </span>
        {last != null && <span className="mono text-fg">{last.toLocaleString("fr-FR",
          { maximumFractionDigits: 2 })} $</span>}
      </div>
      <div ref={box} className="mt-3 w-full" style={{ minHeight: 360 }} />
      <p className="text-muted2 text-[11px] mt-2">
        Bougies 1 h + ticks temps réel (Coinbase) — WebSocket direct, éducatif. {err ?? ""}
      </p>
    </section>
  );
}
