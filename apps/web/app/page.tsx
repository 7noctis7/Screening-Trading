"use client";
import { StepBanner } from "@/components/Pipeline";
import { useDashboard, useScreener, useSentiment } from "@/lib/api";
import { MetricCard } from "@/components/MetricCard";
import { RegimeBanner } from "@/components/RegimeBanner";
import { VixPlaybook } from "@/components/VixPlaybook";
import { SentimentBanner } from "@/components/SentimentBanner";
import { EquityChart } from "@/components/EquityChart";
import { PageSkeleton } from "@/components/ui";

const pct = (x: number) => `${(x * 100).toFixed(1)}%`;

export default function Dashboard() {
  const { data: d } = useDashboard();
  const { data: s } = useScreener();
  const { data: sent } = useSentiment();
  if (!d) return <PageSkeleton />;
  const m = d.metrics;
  return (
    <main className="max-w-6xl mx-auto p-6 space-y-4">
      <h1 className="text-xl font-semibold tracking-tight">Quant Terminal
        {d.strategy_label && <span className="ml-2 text-xs font-normal px-2 py-0.5 rounded-full align-middle"
          style={{ background: "color-mix(in srgb, var(--accent) 16%, transparent)", color: "var(--accent2)" }}>
          stratégie : {d.strategy_label}</span>}</h1>
      <StepBanner active="screener" />
      <RegimeBanner regime={d.regime} />
      <SentimentBanner sentiment={sent} />
      <VixPlaybook vix={d.vix} playbook={d.vix_playbook} series={d.vix_series} />
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricCard label="Rendement" value={pct(m.total_return)} tone={m.total_return >= 0 ? "pos" : "neg"} />
        <MetricCard label="Sharpe" value={m.sharpe?.toFixed(2)} />
        <MetricCard label="Sortino" value={m.sortino?.toFixed(2)} />
        <MetricCard label="Max DD" value={pct(m.max_drawdown)} tone="neg" />
      </div>
      <EquityChart series={d.equity} benchmarks={d.benchmarks} />
      <section className="card p-4 overflow-x-auto">
        <h2 className="text-sm uppercase tracking-wide text-muted mb-3">Top screener — multi-actifs (score facteurs + edge ML)</h2>
        <table className="w-full text-sm">
          <thead className="text-muted text-xs">
            <tr><th className="text-left font-normal">#</th><th className="text-left font-normal">Actif</th>
            <th className="text-left font-normal">Secteur</th><th className="text-right font-normal">Score</th>
            <th className="text-right font-normal">ML</th><th className="text-left font-normal pl-4">Raison</th></tr>
          </thead>
          <tbody className="mono">
            {s?.rows?.slice(0, 10).map((r: any) => (
              <tr key={r.symbol} className="border-t border-border">
                <td className="py-1.5 text-muted">{r.rank}</td><td>{r.symbol}</td>
                <td className="text-muted font-sans text-xs">{r.sector}</td>
                <td className="text-right">{r.score.toFixed(3)}</td>
                <td className="text-right" style={{ color: r.ml_score == null ? "#9aa1ab" : r.ml_score >= 0.5 ? "#22c55e" : "#f43f5e" }}>
                  {r.ml_score == null ? "—" : `${(r.ml_score * 100).toFixed(0)}%`}</td>
                <td className="pl-4 text-muted font-sans">{r.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </main>
  );
}
