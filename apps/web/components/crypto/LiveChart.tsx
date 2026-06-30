"use client";
// Graphe crypto LIVE — bougies multi-timeframe (Binance klines REST + kline WebSocket navigateur).
// 100% client-direct (statique, 0 backend, aucune clé). Binance supporte nativement 1h/4h/1j/
// 1sem/1mois (Coinbase non). Dégrade proprement si CORS/réseau bloque. Éducatif, aucun conseil.
import { useEffect, useRef, useState } from "react";

const SYMS = ["BTC", "ETH", "SOL", "LINK", "NEAR", "RENDER"] as const;
const TFS: [string, string][] = [
  ["1h", "1h"], ["4h", "4h"], ["1j", "1d"], ["1sem", "1w"], ["1mois", "1M"]];
const V = "4.2.3";
const CDNS = [
  `https://unpkg.com/lightweight-charts@${V}/dist/lightweight-charts.standalone.production.js`,
  `https://cdn.jsdelivr.net/npm/lightweight-charts@${V}/dist/lightweight-charts.standalone.production.js`,
];

function loadLib(): Promise<any> {
  const w = window as any;
  if (w.LightweightCharts) return Promise.resolve(w.LightweightCharts);
  const tryCdn = (i: number): Promise<any> =>
    new Promise((resolve, reject) => {
      if (i >= CDNS.length) return reject(new Error("CDN KO"));
      const s = document.createElement("script");
      s.src = CDNS[i]; s.async = true;
      s.onload = () => resolve(w.LightweightCharts);
      s.onerror = () => tryCdn(i + 1).then(resolve, reject);
      document.head.appendChild(s);
    });
  return tryCdn(0);
}

export default function LiveChart() {
  const box = useRef<HTMLDivElement>(null);
  const [sym, setSym] = useState<(typeof SYMS)[number]>("BTC");
  const [tf, setTf] = useState("1d");                 // intervalle Binance
  const [live, setLive] = useState(false);
  const [last, setLast] = useState<number | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let chart: any, series: any, ws: WebSocket | null = null;
    let ro: ResizeObserver | null = null, stop = false, backoff = 1000, raf = 0;
    const el = box.current;
    if (!el) return;
    setErr(null); setLive(false); setLast(null);
    const pair = `${sym.toLowerCase()}usdt`;

    const start = async () => {
      let LWC: any;
      try { LWC = await loadLib(); } catch { setErr("graphe indisponible (CDN). n/d"); return; }
      if (stop) return;
      chart = LWC.createChart(el, {
        layout: { background: { color: "transparent" }, textColor: "#8aa0a9" },
        grid: { vertLines: { color: "rgba(255,255,255,.04)" },
                horzLines: { color: "rgba(255,255,255,.04)" } },
        rightPriceScale: { borderColor: "rgba(255,255,255,.08)" },
        timeScale: { borderColor: "rgba(255,255,255,.08)", timeVisible: tf.endsWith("h") },
        height: 360,
      });
      const opts = { upColor: "#22c55e", downColor: "#f43f5e", borderVisible: false,
        wickUpColor: "#22c55e", wickDownColor: "#f43f5e" };
      series = chart.addCandlestickSeries ? chart.addCandlestickSeries(opts)
        : chart.addSeries(LWC.CandlestickSeries, opts);
      ro = new ResizeObserver(() => chart.applyOptions({ width: el.clientWidth }));
      ro.observe(el);
      await backfill();
      connect();
    };

    const backfill = async () => {
      try {
        const u = `https://api.binance.com/api/v3/klines?symbol=${pair.toUpperCase()}`
          + `&interval=${tf}&limit=300`;
        const r = await fetch(u);
        if (!r.ok) throw new Error(String(r.status));
        const raw: any[] = await r.json();
        const data = raw.map((c) => ({ time: Math.floor(c[0] / 1000), open: +c[1],
          high: +c[2], low: +c[3], close: +c[4] }));
        series.setData(data);
        if (data.length) setLast(data[data.length - 1].close);
        chart.timeScale().fitContent();
      } catch { setErr("backfill n/d (CORS) — ticks live seulement"); }
    };

    const connect = () => {
      if (stop) return;
      try { ws = new WebSocket(`wss://stream.binance.com:9443/ws/${pair}@kline_${tf}`); }
      catch { return; }
      ws.onopen = () => { setLive(true); backoff = 1000; };
      ws.onmessage = (e) => {
        let m: any; try { m = JSON.parse(e.data); } catch { return; }
        const k = m.k; if (!k) return;
        const candle = { time: Math.floor(k.t / 1000), open: +k.o, high: +k.h,
          low: +k.l, close: +k.c };
        if (!raf) raf = requestAnimationFrame(() => { raf = 0; setLast(+k.c); });
        try { series.update(candle); } catch { /* série pas prête */ }
      };
      ws.onclose = () => { setLive(false); if (stop) return;
        backoff = Math.min(backoff * 2, 30000); setTimeout(connect, backoff); };
      ws.onerror = () => ws?.close();
    };

    const onVis = () => { if (document.hidden) ws?.close();
      else if (!ws || ws.readyState > 1) connect(); };
    document.addEventListener("visibilitychange", onVis);
    start();
    return () => { stop = true; document.removeEventListener("visibilitychange", onVis);
      ro?.disconnect(); try { ws?.close(); } catch { /* noop */ }
      try { chart?.remove(); } catch { /* noop */ } if (raf) cancelAnimationFrame(raf); };
  }, [sym, tf]);

  const btn = (active: boolean) =>
    `text-xs px-2 py-1 rounded-lg border transition-colors ${active
      ? "border-border2 text-fg" : "border-border text-muted hover:text-fg"}`;

  return (
    <section className="card p-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h2 className="text-sm uppercase tracking-wide text-muted">Graphe live</h2>
        <div className="flex items-center gap-1.5 flex-wrap">
          {SYMS.map((p) => (
            <button key={p} onClick={() => setSym(p)} className={btn(sym === p)}
              style={{ background: sym === p ? "var(--surface2)" : "var(--surface)" }}>{p}</button>
          ))}
          <span className="w-px h-4 bg-border mx-1" />
          {TFS.map(([label, v]) => (
            <button key={v} onClick={() => setTf(v)} className={btn(tf === v)}
              style={{ background: tf === v ? "var(--surface2)" : "var(--surface)" }}>{label}</button>
          ))}
        </div>
      </div>
      <div className="flex items-center gap-2 mt-1 text-[11px]">
        <span className="inline-flex items-center gap-1">
          <span className="inline-block w-1.5 h-1.5 rounded-full"
            style={{ background: live ? "#22c55e" : "#6b7d86", boxShadow: live ? "0 0 8px #22c55e" : "none" }} />
          <span className="text-muted2">{live ? "live" : "connexion…"}</span>
        </span>
        {last != null && <span className="mono text-fg">
          {last.toLocaleString("fr-FR", { maximumFractionDigits: 2 })} $</span>}
      </div>
      <div ref={box} className="mt-3 w-full" style={{ minHeight: 360 }} />
      <p className="text-muted2 text-[11px] mt-2">
        Bougies {TFS.find((t) => t[1] === tf)?.[0]} + ticks temps réel (Binance) — WebSocket direct,
        éducatif. {err ?? ""}
      </p>
    </section>
  );
}
