"use client";
import { StepBanner } from "@/components/Pipeline";
import { useSentiment } from "@/lib/api";
import { PageSkeleton, EmptyState } from "@/components/ui";
import { IR } from "@/lib/ir";

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
  const fil = s.humeur_est_fil === true;
  const mood = s.market_mood;
  const moodPct = mood == null ? null : Math.round(((Number(mood) + 1) / 2) * 100);
  const rows = s.rows ?? [];
  return (
    <main className="max-w-5xl mx-auto p-6 space-y-4">
      <h1 className="text-xl font-semibold tracking-tight">Sentiment &amp; news</h1>
      <StepBanner active="sentiment" />

      <section className="card p-4">
        <div className="text-muted text-xs uppercase tracking-wide">
          {fil ? "Humeur des actualités (positions)" : "Pas de fil — tendance 3 mois"}
        </div>
        {mood == null ? (
          <p className="text-sm mt-2 text-muted">Non mesuré. Ce n'est pas une humeur neutre.</p>
        ) : (
        <div className="flex items-center gap-4 mt-2">
          <div className="text-2xl font-semibold">{fil ? tag(s.market_label) : "n/d"}</div>
          <div className="flex-1">
            <div className="h-2.5 rounded-md overflow-hidden" style={{ background: "color-mix(in srgb, var(--fg) 10%, transparent)" }}>
              <div style={{ height: "100%", width: `${moodPct}%`, background: fil
                ? "linear-gradient(90deg,#f43f5e,#9aa1ad,#22c55e)" : "var(--muted2)" }} />
            </div>
            <div className="text-xs text-muted mt-1.5">
              {fil ? "score des news" : "moyenne de tendance, pas une actualité"}{" "}
              <b className="text-fg">{Number(mood).toFixed(2)}</b>
              {" "}· {s.n_lignes_news ?? 0} ligne(s) avec news
              {" "}· {s.n_lignes_tendance ?? 0} en repli
              {" "}· {s.n_lignes_vides ?? 0} non mesurée(s)
              {" "}· source <b className="text-fg">{s.source}</b>
            </div>
          </div>
        </div>
        )}
      </section>

      {(s.macro_news ?? []).length > 0 && (
        <section className="card p-4">
          <h2 className="text-sm uppercase tracking-wide text-muted mb-3">Macro & banques centrales (FED · BCE · FMI · économie) <span className="text-[11px] normal-case">· année en cours, plus récent d'abord</span></h2>
          <ul className="space-y-1.5 text-sm">
            {s.macro_news.map((h: any, i: number) => (
              <li key={i} className="flex gap-2">
                <span style={{ color: h.score > 0 ? "#22c55e" : h.score < 0 ? "#f43f5e" : "#9aa1ad" }}>
                  {h.score > 0 ? "▲" : h.score < 0 ? "▼" : "–"}</span>
                {h.date && <span className="text-muted2 text-[11px] mono shrink-0">{h.date.slice(5)}</span>}
                {h.link ? <a href={h.link} target="_blank" rel="noopener noreferrer" className="text-accent hover:underline">{h.title}</a> : <span>{h.title}</span>}
              </li>))}
          </ul>
        </section>
      )}

      {(s.market_news ?? []).length > 0 && (
        <section className="card p-4">
          <h2 className="text-sm uppercase tracking-wide text-muted mb-3">Actualité marché <span className="text-[11px] normal-case">· année en cours, plus récent d'abord</span></h2>
          <ul className="space-y-1.5 text-sm">
            {s.market_news.map((h: any, i: number) => (
              <li key={i} className="flex gap-2">
                <span style={{ color: h.score > 0 ? "#22c55e" : h.score < 0 ? "#f43f5e" : "#9aa1ad" }}>
                  {h.score > 0 ? "▲" : h.score < 0 ? "▼" : "–"}</span>
                {h.date && <span className="text-muted2 text-[11px] mono shrink-0">{h.date.slice(5)}</span>}
                {h.link ? <a href={h.link} target="_blank" rel="noopener noreferrer" className="text-accent hover:underline">{h.title}</a> : <span>{h.title}</span>}
              </li>))}
          </ul>
        </section>
      )}

      <section className="card p-4 overflow-x-auto">
        <h2 className="text-sm uppercase tracking-wide text-muted mb-3">{s.portfolio_driven ? "Sentiment de TON portefeuille" : "Sentiment par position"}
          <span className="ml-2 text-xs normal-case font-normal">{s.portfolio_driven ? "(positions réelles des comptes + allocation preset)" : <>(liens d'articles par actif : lance l'API avec <code className="mono">QUANT_NEWS=1</code>)</>}</span></h2>
        <table className="w-full text-sm">
          <thead className="text-muted text-xs">
            <tr><th className="text-left font-normal">Actif</th><th className="text-left font-normal">Sentiment</th>
            <th className="text-right font-normal">Score</th><th className="text-right font-normal">News</th>
            <th className="text-left font-normal pl-4">Titres</th></tr>
          </thead>
          <tbody>{rows.map((r: any) => (
            <tr key={r.symbol} className="border-t border-border align-top">
              <td className="py-1.5 mono"><IR ticker={r.symbol} name={r.name} assetClass={r.asset_class} className="text-accent hover:underline" /></td>
              <td>{r.origine === "news" ? tag(r.label, r.sector) : <span className="text-muted">{r.origine === "momentum" ? "tendance" : "n/d"}</span>}</td>
              <td className="text-right mono" style={{ color: r.origine === "news" ? (r.score > 0 ? "#22c55e" : r.score < 0 ? "#f43f5e" : "#9aa1ad") : "var(--muted)" }}>
                {r.score == null ? "n/d" : Number(r.score).toFixed(2)}</td>
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
        Le ton des actualités récentes sur chaque titre. Sans titre, la ligne est la tendance
        des 3 derniers mois et elle est marquée « tendance » — elle ne prend pas la couleur
        d'une news, et un trou reste <b>n/d</b>, jamais 0. Fil par actif :
        <code> QUANT_NEWS=1</code>.
      </p>
    </main>
  );
}
