"use client";
import { useDashboard, useScreener } from "@/lib/api";
import { MetricCard } from "@/components/MetricCard";
import { RegimeBanner } from "@/components/RegimeBanner";
import { EquityChart } from "@/components/EquityChart";

const pct = (x: number) => `${(x * 100).toFixed(1)}%`;

export default function Dashboard() {
  const { data: d } = useDashboard();
  const { data: s } = useScreener();
  if (!d) return <div className="p-8 text-muted">Chargement…</div>;
  const m = d.metrics;
  return (
    <main className="max-w-6xl mx-auto p-6 space-y-4">
      <h1 className="text-xl font-semibold tracking-tight">Quant Terminal</h1>
      <RegimeBanner regime={d.regime} />
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricCard label="Rendement" value={pct(m.total_return)} tone={m.total_return >= 0 ? "pos" : "neg"} />
        <MetricCard label="Sharpe" value={m.sharpe?.toFixed(2)} />
        <MetricCard label="Sortino" value={m.sortino?.toFixed(2)} />
        <MetricCard label="Max DD" value={pct(m.max_drawdown)} tone="neg" />
      </div>
      <EquityChart series={d.equity} />
      <section className="card p-4">
        <h2 className="text-sm uppercase tracking-wide text-muted mb-3">Top screener</h2>
        <table className="w-full text-sm">
          <thead className="text-muted text-xs">
            <tr><th className="text-left font-normal">#</th><th className="text-left font-normal">Actif</th>
            <th className="text-right font-normal">Score</th><th className="text-left font-normal pl-4">Raison</th></tr>
          </thead>
          <tbody className="mono">
            {s?.rows?.slice(0, 8).map((r: any) => (
              <tr key={r.symbol} className="border-t border-border">
                <td className="py-1.5 text-muted">{r.rank}</td><td>{r.symbol}</td>
                <td className="text-right">{r.score.toFixed(3)}</td>
                <td className="pl-4 text-muted font-sans">{r.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </main>
  );
}
