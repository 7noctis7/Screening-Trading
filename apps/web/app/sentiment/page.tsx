"use client";
import { StepBanner } from "@/components/Pipeline";
import { useSentiment } from "@/lib/api";
import { PageSkeleton, EmptyState } from "@/components/ui";

const SC: Record<string, [string, string]> = {
  bullish: ["#22c55e", "▲"], bearish: ["#f43f5e", "▼"], neutral: ["#9aa1ad", "–"],
};
const tag = (label: string, sector?: string) => {
  const [c, i] = SC[label] ?? SC.neutral;
  return (
    <span><span style={{ color: c }}>{i}</span>{sector ? <span className="text-muted"> {sector}</span> : null}</span>
  );
};

export default function Sentiment() {
  const { data: s } = useSentiment();
  if (!s) return <PageSkeleton />;
  if (!s.available)
    return <main className="max-w-3xl mx-auto p-6"><EmptyState title="Aucune donnée de sentiment" /></main>;
  const mood: number = s.market_mood ?? 0;
  const moodPct = Math.round(((mood + 1) / 2) * 100);
  const rows = s.rows ?? [];
  return (
    <main className="max-w-5xl mx-auto p-6 space-y-4">
      <h1 className="text-xl font-semibold tracking-tight">Sentiment &amp; news</h1>
      <StepBanner active="sentiment" />

      <section className="card p-4">
        <div className="text-muted text-xs uppercase tracking-wide">Humeur de marché (positions)</div>
        <div className="flex items-center gap-4 mt-2">
          <div className="text-2xl font-semibold">{tag(s.market_label)}</div>
          <div className="flex-1">
            <div className="h-2.5 rounded-md overflow-hidden" style={{ background: "#1d212a" }}>
              <div style={{ height: "100%", width: `${moodPct}%`, background: "linear-gradient(90deg,#f43f5e,#9aa1ad,#22c55e)" }} />
            </div>
            <div className="text-xs text-muted mt-1.5">
              score moyen <b className="text-fg">{mood.toFixed(2)}</b>
              {s.mood_change != null && s.mood_change !== 0 && (
                <> · Δ révision <b style={{ color: s.mood_change > 0 ? "#22c55e" : "#f43f5e" }}>
                  {s.mood_change > 0 ? "+" : ""}{s.mood_change.toFixed(2)}</b></>
              )}
              {" "}· moteur <b className="text-fg">{s.engine}</b> · source <b className="text-fg">{s.source}</b>
            </div>
          </div>
        </div>
      </section>

      {(s.macro_news ?? []).length > 0 && (
        <section className="card p-4">
          <h2 className="text-sm uppercase tracking-wide text-muted mb-3">Macro & banques centrales (FED · BCE · FMI · économie)</h2>
          <ul className="space-y-1.5 text-sm">
            {s.macro_news.map((h: any, i: number) => (
              <li key={i} className="flex gap-2">
                <span style={{ color: h.score > 0 ? "#22c55e" : h.score < 0 ? "#f43f5e" : "#9aa1ad" }}>
                  {h.score > 0 ? "▲" : h.score < 0 ? "▼" : "–"}</span>
                {h.link ? <a href={h.link} target="_blank" rel="noopener noreferrer" className="text-accent hover:underline">{h.title}</a> : <span>{h.title}</span>}
              </li>))}
          </ul>
        </section>
      )}

      {(s.market_news ?? []).length > 0 && (
        <section className="card p-4">
          <h2 className="text-sm uppercase tracking-wide text-muted mb-3">Actualité marché</h2>
          <ul className="space-y-1.5 text-sm">
            {s.market_news.map((h: any, i: number) => (
              <li key={i} className="flex gap-2">
                <span style={{ color: h.score > 0 ? "#22c55e" : h.score < 0 ? "#f43f5e" : "#9aa1ad" }}>
                  {h.score > 0 ? "▲" : h.score < 0 ? "▼" : "–"}</span>
                {h.link ? <a href={h.link} target="_blank" rel="noopener noreferrer" className="text-accent hover:underline">{h.title}</a> : <span>{h.title}</span>}
              </li>))}
          </ul>
        </section>
      )}

      <section className="card p-4 overflow-x-auto">
        <h2 className="text-sm uppercase tracking-wide text-muted mb-3">Sentiment par position
          <span className="ml-2 text-xs normal-case font-normal">(liens d'articles par actif : lance l'API avec <code className="mono">QUANT_NEWS=1</code>)</span></h2>
        <table className="w-full text-sm">
          <thead className="text-muted text-xs">
            <tr><th className="text-left font-normal">Actif</th><th className="text-left font-normal">Sentiment</th>
            <th className="text-right font-normal">Score</th><th className="text-right font-normal">News</th>
            <th className="text-left font-normal pl-4">Titres</th></tr>
          </thead>
          <tbody>{rows.map((r: any) => (
            <tr key={r.symbol} className="border-t border-border align-top">
              <td className="py-1.5 mono">{r.symbol}</td>
              <td>{tag(r.label, r.sector)}</td>
              <td className="text-right mono" style={{ color: r.score > 0 ? "#22c55e" : r.score < 0 ? "#f43f5e" : "#9aa1ad" }}>{(r.score ?? 0).toFixed(2)}</td>
              <td className="text-right mono">{r.n_news ?? 0}</td>
              <td className="pl-4 text-xs">
                {(r.headlines ?? []).length === 0 ? <span className="text-muted">—</span> :
                  (r.headlines ?? []).slice(0, 5).map((h: any, i: number) => (
                    <span key={i}>
                      {h.link ? <a href={h.link} target="_blank" rel="noopener noreferrer" className="text-accent">{h.title}</a> : h.title}
                      {i < Math.min(5, r.headlines.length) - 1 ? " · " : ""}
                    </span>
                  ))}
              </td>
            </tr>))}</tbody>
        </table>
      </section>
      <p className="text-muted text-xs">
        Moteur : FinBERT si installé, sinon lexique finance ; hors-ligne → repli sur le momentum 63 j.
        News réelles (RSS gratuit) en lançant l'API avec <code>QUANT_NEWS=1</code>.
      </p>
    </main>
  );
}
