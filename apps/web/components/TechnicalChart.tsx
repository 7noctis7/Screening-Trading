"use client";
import { useEffect, useMemo, useRef, useState } from "react";

// Graphique technique pro (TradingView lightweight-charts) : chandeliers + volumes +
// MM20/50/100/200 + marqueurs achat/vente ▲▼ + cadence Daily / Weekly / Monthly.
// 100 % offline (la lib est bundlée par Next.js, aucun appel réseau au rendu).

type Bar = { t: string; o: number; h: number; l: number; c: number; v?: number };
type Marker = { t: string; side: "buy" | "sell"; price?: number };
type TF = "D" | "W" | "M";

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

export function TechnicalChart({ data, markers = [], height = 360 }:
  { data: Bar[]; markers?: Marker[]; height?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const legendRef = useRef<HTMLDivElement>(null);
  const [tf, setTf] = useState<TF>("D");
  const [showVol, setShowVol] = useState(true);
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

      if (showVol) {
        const vol = chart.addHistogramSeries({ priceScaleId: "vol", priceFormat: { type: "volume" } });
        vol.priceScale().applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
        vol.setData(bars.map((d) => ({
          time: d.t, value: d.v ?? 0,
          color: d.c >= d.o ? "rgba(34,197,94,.5)" : "rgba(244,63,94,.5)",
        })));
      }

      const closes = bars.map((d) => d.c);
      for (const { p, color } of MAS) {
        if (closes.length <= p) continue;
        const vals = sma(closes, p);
        const s = chart.addLineSeries({ color, lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
        s.setData(bars.map((d, i) => ({ time: d.t, value: vals[i] })).filter((x: any) => x.value != null));
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
      const fmt = (n: number) => n.toLocaleString("fr-FR", { maximumFractionDigits: 2 });
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
  }, [bars, dateToTime, markers, height, showVol]);

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
        <button onClick={() => setShowVol((v) => !v)}
          className={`px-3 py-1 text-xs rounded-lg border border-border ${showVol ? "text-fg" : "text-muted"}`}>
          Volume
        </button>
        <span className="text-xs ml-auto">
          {MAS.map((m) => (
            <span key={m.p} className="ml-2" style={{ color: m.color }}>● MM{m.p}</span>
          ))}
        </span>
      </div>
      <div ref={legendRef} className="text-xs mono text-muted mb-1" style={{ minHeight: 16 }} />
      <div ref={ref} className="w-full" style={{ minHeight: height }} />
    </div>
  );
}
