"use client";
import { useEffect, useRef } from "react";

// Graphique technique en chandeliers (TradingView lightweight-charts) + MM20/MM50.
function sma(v: number[], p: number): (number | undefined)[] {
  const o: (number | undefined)[] = []; let s = 0;
  for (let i = 0; i < v.length; i++) { s += v[i]; if (i >= p) s -= v[i - p]; o.push(i >= p - 1 ? s / p : undefined); }
  return o;
}

export function TechnicalChart({ data, height = 320 }: { data: any[]; height?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref.current || !data?.length) return;
    let chart: any;
    let disposed = false;
    (async () => {
      const lc: any = await import("lightweight-charts");
      if (disposed || !ref.current) return;
      chart = lc.createChart(ref.current, {
        height, autoSize: true,
        layout: { background: { color: "transparent" }, textColor: "#9aa1ab", fontSize: 11 },
        grid: { vertLines: { color: "#23272f" }, horzLines: { color: "#23272f" } },
        timeScale: { borderColor: "#23272f" }, rightPriceScale: { borderColor: "#23272f" },
        crosshair: { mode: 0 },
      });
      const candles = chart.addCandlestickSeries({
        upColor: "#22c55e", downColor: "#f43f5e", borderVisible: false,
        wickUpColor: "#22c55e", wickDownColor: "#f43f5e",
      });
      candles.setData(data.map((d) => ({ time: d.t, open: d.o, high: d.h, low: d.l, close: d.c })));
      const closes = data.map((d) => d.c);
      const line = (vals: (number | undefined)[], color: string) => {
        const s = chart.addLineSeries({ color, lineWidth: 1, priceLineVisible: false });
        s.setData(data.map((d, i) => ({ time: d.t, value: vals[i] })).filter((x: any) => x.value != null));
      };
      line(sma(closes, 20), "#3b82f6");
      line(sma(closes, 50), "#f59e0b");
      chart.timeScale().fitContent();
    })();
    return () => { disposed = true; if (chart) chart.remove(); };
  }, [data, height]);
  return <div ref={ref} className="w-full" style={{ minHeight: height }} />;
}
