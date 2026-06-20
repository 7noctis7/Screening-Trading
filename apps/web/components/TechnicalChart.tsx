"use client";
import { useEffect, useMemo, useRef, useState } from "react";

// Graphique technique pro (TradingView lightweight-charts) : chandeliers + volumes +
// MM20/50/100/200 + marqueurs achat/vente ▲▼ + cadence Daily / Weekly / Monthly.
// 100 % offline (la lib est bundlée par Next.js, aucun appel réseau au rendu).

type Bar = { t: string; o: number; h: number; l: number; c: number; v?: number };
type Marker = { t: string; side: "buy" | "sell"; price?: number };
type TF = "D" | "W" | "M";
// Overlays pilotés par le serveur MCP TradingView (cônes de risque + blackouts résultats).
type RiskBand = { time: string; upper: number; lower: number };
type Blackout = { start: string; end: string; label?: string };
type Overlays = { bands?: RiskBand[]; blackouts?: Blackout[] };

function sma(v: number[], p: number): (number | undefined)[] {
  const o: (number | undefined)[] = []; let s = 0;
  for (let i = 0; i < v.length; i++) { s += v[i]; if (i >= p) s -= v[i - p]; o.push(i >= p - 1 ? s / p : undefined); }
  return o;
}

// Clé de regroupement : semaine ISO (année-semaine) ou mois (année-mois).
function bucketKey(t: string, tf: TF): string {
  if (tf === "M") return t.slice(0, 7);
  const d = new Date(t + "T00:00:00Z");
  const day = (d.getUTCDay() + 6) % 7;                 // lundi = 0
  d.setUTCDate(d.getUTCDate() - day);                  // début de semaine
  return d.toISOString().slice(0, 10);
}

// Agrège des barres daily en W/M (OHLC + volume). Renvoie aussi date d'origine → temps de barre.
function aggregate(data: Bar[], tf: TF): { bars: Bar[]; dateToTime: Record<string, string> } {
  const dateToTime: Record<string, string> = {};
  if (tf === "D") { data.forEach((d) => (dateToTime[d.t] = d.t)); return { bars: data, dateToTime }; }
  const groups: Record<string, Bar[]> = {};
  const order: string[] = [];
  for (const d of data) {
    const k = bucketKey(d.t, tf);
    if (!groups[k]) { groups[k] = []; order.push(k); }
    groups[k].push(d);
  }
  const bars: Bar[] = order.map((k) => {
    const g = groups[k];
    const time = g[g.length - 1].t;                     // la barre porte la date de fin de période
    g.forEach((d) => (dateToTime[d.t] = time));
    return {
      t: time, o: g[0].o, c: g[g.length - 1].c,
      h: Math.max(...g.map((x) => x.h)), l: Math.min(...g.map((x) => x.l)),
      v: g.reduce((s, x) => s + (x.v ?? 0), 0),
    };
  });
  return { bars, dateToTime };
}

const TFS: { id: TF; label: string }[] = [
  { id: "D", label: "Daily" }, { id: "W", label: "Weekly" }, { id: "M", label: "Monthly" },
];
const MAS: { p: number; color: string }[] = [
  { p: 20, color: "#3b82f6" }, { p: 50, color: "#f59e0b" },
  { p: 100, color: "#a855f7" }, { p: 200, color: "#ef4444" },
];

export function TechnicalChart({ data, markers = [], height = 360, overlays }:
  { data: Bar[]; markers?: Marker[]; height?: number; overlays?: Overlays }) {
  const ref = useRef<HTMLDivElement>(null);
  const legendRef = useRef<HTMLDivElement>(null);
  const [tf, setTf] = useState<TF>("D");
  const [vis, setVis] = useState<Record<string, boolean>>({
    vol: true, ma20: true, ma50: true, ma100: false, ma200: true, boll: false, rsi: false,
  });
  const showVol = vis.vol;
  const { bars, dateToTime } = useMemo(() => aggregate(data ?? [], tf), [data, tf]);

  useEffect(() => {
    if (!ref.current || !bars.length) return;
    let chart: any; let disposed = false;
    (async () => {
      const lc: any = await import("lightweight-charts");
      if (disposed || !ref.current) return;
      chart = lc.createChart(ref.current, {
        height, autoSize: true,
        layout: { background: { color: "transparent" }, textColor: "#9aa1ab", fontSize: 11 },
        grid: { vertLines: { color: "#23272f" }, horzLines: { color: "#23272f" } },
        timeScale: { borderColor: "#23272f" }, rightPriceScale: { borderColor: "#23272f" },
        crosshair: { mode: 1 },
      });
      const candles = chart.addCandlestickSeries({
        upColor: "#22c55e", downColor: "#f43f5e", borderVisible: false,
        wickUpColor: "#22c55e", wickDownColor: "#f43f5e",
      });
      candles.setData(bars.map((d) => ({ time: d.t, open: d.o, high: d.h, low: d.l, close: d.c })));

      const closes = bars.map((d) => d.c);
      const tOf = (i: number) => bars[i].t;
      // --- panneaux bas EMPILÉS sans chevauchement (volume / RSI / MACD) ---
      const PANE = 0.17;                                   // hauteur d'un sous-panneau
      const subs = ["vol", "rsi", "macd"].filter((k) => vis[k] && closes.length > 26);
      const mainBottom = subs.length * PANE;
      candles.priceScale().applyOptions({ scaleMargins: { top: 0.05, bottom: Math.min(0.6, mainBottom) || 0.05 } });
      const paneMargins = (k: string) => {
        const j = subs.indexOf(k);                         // 0 = le plus bas
        return { top: 1 - (j + 1) * PANE, bottom: j * PANE };
      };

      if (vis.vol && closes.length > 1) {
        const vol = chart.addHistogramSeries({ priceScaleId: "vol", priceFormat: { type: "volume" } });
        vol.priceScale().applyOptions({ scaleMargins: paneMargins("vol") });
        vol.setData(bars.map((d) => ({ time: d.t, value: d.v ?? 0,
          color: d.c >= d.o ? "rgba(34,197,94,.5)" : "rgba(244,63,94,.5)" })));
      }

      for (const { p, color } of MAS) {
        if (!vis[`ma${p}`] || closes.length <= p) continue;
        const vals = sma(closes, p);
        const s = chart.addLineSeries({ color, lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
        s.setData(bars.map((d, i) => ({ time: d.t, value: vals[i] })).filter((x: any) => x.value != null));
      }
      // Bandes de Bollinger (20, 2σ) — overlay sur le prix
      if (vis.boll && closes.length > 20) {
        const mid = sma(closes, 20);
        const band = (mult: number) => closes.map((_, i) => {
          if (i < 19 || mid[i] == null) return undefined;
          const win = closes.slice(i - 19, i + 1);
          const m = mid[i] as number;
          const sd = Math.sqrt(win.reduce((a, x) => a + (x - m) ** 2, 0) / 20);
          return m + mult * sd;
        });
        for (const mult of [2, -2]) {
          const s = chart.addLineSeries({ color: "rgba(34,211,238,.5)", lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
          s.setData(bars.map((d, i) => ({ time: d.t, value: band(mult)[i] })).filter((x: any) => x.value != null));
        }
      }
      // RSI(14) — panneau propre
      if (vis.rsi && closes.length > 15) {
        const rsi: (number | undefined)[] = [];
        for (let i = 0; i < closes.length; i++) {
          if (i < 14) { rsi.push(undefined); continue; }
          let g = 0, l = 0;
          for (let j = i - 13; j <= i; j++) { const d = closes[j] - closes[j - 1]; if (d > 0) g += d; else l -= d; }
          rsi.push(l === 0 ? 100 : 100 - 100 / (1 + (g / 14) / (l / 14)));
        }
        const s = chart.addLineSeries({ color: "#a855f7", lineWidth: 1, priceScaleId: "rsi", lastValueVisible: false });
        s.priceScale().applyOptions({ scaleMargins: paneMargins("rsi") });
        s.setData(bars.map((d, i) => ({ time: d.t, value: rsi[i] })).filter((x: any) => x.value != null));
        // zones de surachat/survente : 70 en rouge, 30 en vert
        s.createPriceLine({ price: 70, color: "#f43f5e", lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: "70" });
        s.createPriceLine({ price: 30, color: "#22c55e", lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: "30" });
      }
      // MACD (12,26,9) — panneau propre : ligne MACD + signal
      if (vis.macd && closes.length > 26) {
        const ema = (arr: number[], p: number) => {
          const k = 2 / (p + 1); const out: number[] = []; let e = arr[0];
          arr.forEach((v, i) => { e = i ? v * k + e * (1 - k) : v; out.push(e); }); return out;
        };
        const e12 = ema(closes, 12), e26 = ema(closes, 26);
        const macd = closes.map((_, i) => e12[i] - e26[i]);
        const sig = ema(macd, 9);
        const mLine = chart.addLineSeries({ color: "#22d3ee", lineWidth: 1, priceScaleId: "macd", lastValueVisible: false });
        const sLine = chart.addLineSeries({ color: "#f59e0b", lineWidth: 1, priceScaleId: "macd", lastValueVisible: false });
        mLine.priceScale().applyOptions({ scaleMargins: paneMargins("macd") });
        mLine.setData(bars.map((d, i) => ({ time: d.t, value: macd[i] })));
        sLine.setData(bars.map((d, i) => ({ time: d.t, value: sig[i] })));
      }
      // Fibonacci (retracement sur toute la fenêtre) — lignes de prix.
      // 0.25 vert · 0.5 neutre · 0.618 & 0.75 bleu · 0.886 rouge (0 et 1 masqués).
      if (vis.fib && closes.length > 2) {
        const hi = Math.max(...bars.map((d) => d.h)), lo = Math.min(...bars.map((d) => d.l));
        const FIB: { lvl: number; color: string }[] = [
          { lvl: 0.25, color: "#22c55e" }, { lvl: 0.5, color: "rgba(245,158,11,.45)" },
          { lvl: 0.618, color: "#3b82f6" }, { lvl: 0.75, color: "#3b82f6" },
          { lvl: 0.886, color: "#f43f5e" },
        ];
        for (const { lvl, color } of FIB) {
          candles.createPriceLine({ price: hi - (hi - lo) * lvl, color,
            lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: `Fib ${lvl}` });
        }
      }
      // FRVP (profil de volume, simplifié) : POC = prix au volume max ; VaL/VaH = bornes de
      // la « value area » (70 % du volume autour du POC), tracées en bleu clair.
      if (vis.frvp && closes.length > 5) {
        const lo = Math.min(...bars.map((d) => d.l)), hi = Math.max(...bars.map((d) => d.h));
        const nb = 24, step = (hi - lo) / nb || 1; const buckets = new Array(nb).fill(0);
        bars.forEach((d) => { const b = Math.min(nb - 1, Math.max(0, Math.floor((d.c - lo) / step))); buckets[b] += d.v ?? 0; });
        const pocIdx = buckets.indexOf(Math.max(...buckets));
        const poc = lo + (pocIdx + 0.5) * step;
        candles.createPriceLine({ price: poc, color: "#5eead4", lineWidth: 2, lineStyle: 0,
          axisLabelVisible: true, title: "POC" });
        // value area : expansion bidirectionnelle depuis le POC jusqu'à 70 % du volume
        const total = buckets.reduce((a, b) => a + b, 0);
        if (total > 0) {
          let loI = pocIdx, hiI = pocIdx, acc = buckets[pocIdx];
          while (acc < total * 0.7 && (loI > 0 || hiI < nb - 1)) {
            const below = loI > 0 ? buckets[loI - 1] : -1;
            const above = hiI < nb - 1 ? buckets[hiI + 1] : -1;
            if (above >= below) { hiI++; acc += above; } else { loI--; acc += below; }
          }
          const vaL = lo + loI * step, vaH = lo + (hiI + 1) * step;
          candles.createPriceLine({ price: vaH, color: "#7dd3fc", lineWidth: 1, lineStyle: 2,
            axisLabelVisible: true, title: "VaH" });
          candles.createPriceLine({ price: vaL, color: "#7dd3fc", lineWidth: 1, lineStyle: 2,
            axisLabelVisible: true, title: "VaL" });
        }
      }
      void tOf;

      // === Overlays MCP TradingView : cônes de risque (VaR/EVT, no-trade band) + blackouts ===
      if (overlays?.bands?.length) {
        const up = chart.addLineSeries({ color: "rgba(245,158,11,.8)", lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false });
        const lo = chart.addLineSeries({ color: "rgba(245,158,11,.8)", lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false });
        const pt = (k: "upper" | "lower") => overlays.bands!
          .map((b) => ({ time: dateToTime[b.time] ?? b.time, value: b[k] }))
          .filter((x: any) => x.value != null)
          .sort((a: any, b: any) => (a.time < b.time ? -1 : 1));
        up.setData(pt("upper")); lo.setData(pt("lower"));
      }
      if (overlays?.blackouts?.length) {
        const maxHi = Math.max(...bars.map((d) => d.h)) * 1.05;
        const covered = (t: string) => overlays.blackouts!.some((z) => t >= z.start && t <= z.end);
        const bo = chart.addHistogramSeries({ priceScaleId: "blackout", priceLineVisible: false, lastValueVisible: false });
        bo.priceScale().applyOptions({ scaleMargins: { top: 0.05, bottom: 0.0 }, visible: false });
        bo.setData(bars.filter((d) => covered(d.t)).map((d) => ({ time: d.t, value: maxHi, color: "rgba(245,158,11,.12)" })));
      }

      if (markers.length) {
        const mk = markers
          .map((m) => {
            const time = dateToTime[m.t];                 // mappe le marqueur sur la barre de sa période
            if (!time) return null;
            return m.side === "buy"
              ? { time, position: "belowBar", color: "#22c55e", shape: "arrowUp", text: "Achat" }
              : { time, position: "aboveBar", color: "#f43f5e", shape: "arrowDown", text: "Vente" };
          })
          .filter(Boolean)
          .sort((a: any, b: any) => (a.time < b.time ? -1 : 1));
        if (mk.length) candles.setMarkers(mk as any);
        // ligne de prix d'entrée (1er achat visible) — repère "ligne d'info"
        const firstBuy = markers.find((m) => m.side === "buy" && m.price);
        if (firstBuy?.price) {
          candles.createPriceLine({
            price: firstBuy.price, color: "#22c55e", lineWidth: 1, lineStyle: 2,
            axisLabelVisible: true, title: "PRU",
          });
        }
      }

      // ligne d'info : lecture O/H/L/C + variation au survol (crosshair)
      const fmt = (n: number) => (n ?? 0).toLocaleString("fr-FR", { maximumFractionDigits: 2 });
      const setLegend = (b: any) => {
        if (!legendRef.current || !b) return;
        const up = b.close >= b.open;
        const chg = ((b.close / b.open - 1) * 100).toFixed(2);
        legendRef.current.innerHTML =
          `<b>${b.time ?? ""}</b> &nbsp; O ${fmt(b.open)} · H ${fmt(b.high)} · B ${fmt(b.low)} · ` +
          `C <span style="color:${up ? "#22c55e" : "#f43f5e"}">${fmt(b.close)} (${up ? "+" : ""}${chg}%)</span>`;
      };
      setLegend(bars[bars.length - 1] && { ...bars[bars.length - 1], time: bars[bars.length - 1].t });
      chart.subscribeCrosshairMove((param: any) => {
        const d = param?.seriesData?.get(candles);
        if (d) setLegend({ ...d, time: param.time });
      });
      chart.timeScale().fitContent();
    })();
    return () => { disposed = true; if (chart) chart.remove(); };
  }, [bars, dateToTime, markers, height, vis, overlays]);

  return (
    <div>
      <div className="flex items-center gap-2 mb-2 flex-wrap">
        <div className="inline-flex rounded-lg border border-border overflow-hidden">
          {TFS.map((x) => (
            <button key={x.id} onClick={() => setTf(x.id)}
              className={`px-3 py-1 text-xs ${tf === x.id ? "bg-surfaceAlt text-fg" : "text-muted hover:text-fg"}`}>
              {x.label}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-1.5 flex-wrap">
          {([
            ["ma20", "MM20", "#3b82f6"], ["ma50", "MM50", "#f59e0b"],
            ["ma100", "MM100", "#a855f7"], ["ma200", "MM200", "#ef4444"],
            ["boll", "Bollinger", "#22d3ee"], ["rsi", "RSI", "#a855f7"], ["macd", "MACD", "#22d3ee"],
            ["fib", "Fibonacci", "#f59e0b"], ["frvp", "FRVP (POC)", "#5eead4"], ["vol", "Volume", "#9aa1ab"],
          ] as const).map(([k, label, color]) => (
            <button key={k} onClick={() => setVis((s) => ({ ...s, [k]: !s[k] }))}
              className={`px-2.5 py-1 text-xs rounded-full border transition-colors ${vis[k] ? "text-fg" : "text-muted"}`}
              style={{ borderColor: vis[k] ? color : "var(--border)", background: vis[k] ? "color-mix(in srgb,"+color+" 14%, transparent)" : "transparent" }}>
              {label}
            </button>
          ))}
        </div>
      </div>
      <div ref={legendRef} className="text-xs mono text-muted mb-1" style={{ minHeight: 16 }} />
      <div ref={ref} className="w-full" style={{ minHeight: height }} />
    </div>
  );
}
