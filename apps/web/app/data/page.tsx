"use client";
import { StepBanner } from "@/components/Pipeline";
import { useData } from "@/lib/api";
import { PageSkeleton } from "@/components/ui";
import { IR } from "@/lib/ir";
import { DateArrete } from "@/components/DateArrete";

const nb = (x?: number) => (x ?? 0).toLocaleString("fr-FR");
const dt = (s?: string) => (s ? String(s).slice(0, 10) : "—");

export default function DataPage() {
  const { data: d } = useData();
  if (!d) return <PageSkeleton />;
  const q = d.quality ?? {};
  const h = d.health ?? {};
  const scoreColor = h.score >= 80 ? "#22c55e" : h.score >= 60 ? "#f59e0b" : "#f43f5e";
  const cards: [string, string][] = [
    ["Source des prix", d.provider],
    ["Journées de cotation collectées", nb(d.total_bars)],
    ["Actifs suivis", String((d.collection ?? []).length)],
    ["Source des comptes d'entreprises", d.fundamentals_provider ?? "—"],
  ];
  return (
    <main className="max-w-5xl mx-auto p-6 space-y-4">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Les données — d'où viennent les chiffres</h1>
        <p className="text-muted text-sm mt-1 max-w-3xl">
          Tout le site repose sur des historiques de prix. Cette page dit combien il y en a,
          d'où ils viennent, ce qui manque et ce qui cloche. Une analyse ne vaut jamais mieux
          que les chiffres qui la nourrissent : c'est pour ça qu'on les montre.
        </p>
      </div>
      <StepBanner active="data" />
      <DateArrete date={d.as_of} quoi="Historiques de prix" />
      {d.survivorship?.available && (
        <div className="card p-3 text-sm flex items-start gap-2"
          style={{ borderColor: d.survivorship.corrected ? "var(--pos)" : "var(--warn)" }}>
          <span>{d.survivorship.corrected ? "✅" : "⚠️"}</span>
          <span><b>Sociétés disparues prises en compte : {d.survivorship.severity}.</b>{" "}
            <span className="text-muted">{d.survivorship.n_active} actifs encore cotés · {d.survivorship.n_delisted} actifs qui ont disparu de la cote, remis dans les calculs. Ne garder que les survivants ferait croire que tout finit par monter. {d.survivorship.note}</span></span>
        </div>
      )}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {cards.map(([lab, val]) => (
          <div key={lab} className="card p-4">
            <div className="text-muted text-xs uppercase tracking-wide">{lab}</div>
            <div className="text-lg mono mt-1">{val}</div>
          </div>
        ))}
      </div>

      {/* Santé & couverture des données */}
      {h.score != null && (
        <section className="card p-4">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <h2 className="text-sm uppercase tracking-wide text-muted">Est-ce que l'historique est complet ?</h2>
            <span className="mono text-sm">Note de qualité <b style={{ color: scoreColor }}>{h.score}/100</b>
              <span className="text-muted text-xs"> · {h.complete} historiques complets sur {h.n_series} · {h.outliers} valeurs aberrantes · {h.n_bad} valeurs impossibles</span>
            </span>
          </div>
          <div className="overflow-x-auto mt-3">
            <table className="w-full text-sm mono">
              <thead className="text-muted text-xs">
                <tr><th className="text-left font-normal">Catégorie</th><th className="text-right font-normal">Actifs</th>
                <th className="text-right font-normal">Historique complet</th><th className="text-right font-normal">% complet</th>
                <th className="text-right font-normal" title="Nombre moyen de journées de cotation par actif.">Journées en moyenne</th></tr>
              </thead>
              <tbody>{(h.coverage ?? []).map((c: any) => (
                <tr key={c.asset_class} className="border-t border-border">
                  <td className="py-1.5 font-sans">{c.asset_class}</td>
                  <td className="text-right">{c.n}</td><td className="text-right">{c.complete}</td>
                  <td className="text-right" style={{ color: c.complete_pct >= 0.8 ? "#22c55e" : c.complete_pct >= 0.5 ? "#f59e0b" : "#f43f5e" }}>{(c.complete_pct * 100).toFixed(0)}%</td>
                  <td className="text-right">{c.avg_bars}</td>
                </tr>))}</tbody>
            </table>
          </div>
        </section>
      )}

      {/* SPC / Six Sigma — taux de défaut du pipeline OHLCV */}
      {d.spc?.available && (
        <section className="card p-4">
          <h2 className="text-sm uppercase tracking-wide text-muted mb-1">Taux d'erreur de la collecte</h2>
          <p className="text-muted2 text-xs mb-3">Sur des millions de journées de cotation collectées, combien contiennent une anomalie ? On mesure ça comme une usine mesure ses défauts de fabrication.</p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {([
              ["Niveau de fiabilité", `${d.spc.sigma_level}σ`,
                d.spc.sigma_level >= 6 ? "#22c55e" : d.spc.sigma_level >= 4.5 ? "#f59e0b" : "#f43f5e"],
              ["Défauts par million", nb(Math.round(d.spc.dpmo)), undefined],
              ["Objectif", `${d.spc.target_dpmo} par million`, "#94a3b8"],
              ["Journées contrôlées", nb(d.spc.p_chart?.n ?? 0), undefined],
            ] as [string, string, string | undefined][]).map(([lab, val, col]) => (
              <div key={lab} className="rounded-lg border border-border p-3" style={{ background: "var(--surface)" }}>
                <div className="text-muted text-[11px] uppercase tracking-wide">{lab}</div>
                <div className="text-xl mono mt-1" style={col ? { color: col } : undefined}>{val}</div>
              </div>
            ))}
          </div>
          <div className="text-xs text-muted2 mt-2">
            Une journée est comptée en défaut si elle rate un de ces contrôles : {d.spc.checks}.
            Taux observé : {((d.spc.p_chart?.p ?? 0) * 100).toFixed(5)} %. L'objectif industriel de référence
            est 3,4 défauts par million, ce qu'on appelle le niveau 6σ.
          </div>
        </section>
      )}

      {/* Audit PwC — complétude / exactitude / point-in-time */}
      {d.audit && (
        <section className="card p-4">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <h2 className="text-sm uppercase tracking-wide text-muted">Contrôle d'intégrité, comme un audit comptable</h2>
            <span className="text-xs px-2 py-0.5 rounded-full bg-surfaceAlt"
              style={{ color: d.audit.ok ? "#22c55e" : "#ef4444" }}>
              {d.audit.ok ? "✓ aucune anomalie critique" : `✗ ${d.audit.counts?.critical ?? 0} critique(s)`}
            </span>
          </div>
          <div className="grid grid-cols-3 gap-3 mt-3">
            {([["Bloquantes", d.audit.counts?.critical ?? 0, "#ef4444"],
               ["Sérieuses", d.audit.counts?.major ?? 0, "#f59e0b"],
               ["À surveiller", d.audit.counts?.warning ?? 0, "#94a3b8"]] as [string, number, string][])
              .map(([lab, val, col]) => (
                <div key={lab}>
                  <div className="text-muted text-xs">{lab}</div>
                  <div className="text-lg mono" style={{ color: val > 0 ? col : "var(--muted)" }}>{val}</div>
                </div>))}
          </div>
          <p className="text-muted text-xs mt-2">
            {nb(d.audit.n_symbols)} actifs · {nb(d.audit.n_bars)} journées de cotation passées au crible : rien ne manque · les prix d'une journée sont cohérents entre eux (le plus haut est bien le plus haut) · aucun chiffre du futur n'a fui dans le passé · les sociétés disparues sont comptées
          </p>
          {(d.audit.anomalies ?? []).length > 0 && (
            <div className="max-h-[220px] overflow-auto mt-2">
              <table className="w-full text-xs mono">
                <thead className="text-muted sticky top-0 bg-surface">
                  <tr><th className="text-left font-normal">Symbole</th><th className="text-left font-normal">Type d'anomalie</th>
                  <th className="text-left font-normal">Gravité</th><th className="text-left font-normal">Détail</th></tr>
                </thead>
                <tbody>{d.audit.anomalies.slice(0, 100).map((an: any, i: number) => (
                  <tr key={i} className="border-t border-border">
                    <td className="py-1">{an.symbol}</td><td className="text-muted font-sans">{an.kind}</td>
                    <td style={{ color: an.severity === "critical" ? "#ef4444" : an.severity === "major" ? "#f59e0b" : "#94a3b8" }}>{an.severity}</td>
                    <td className="text-muted font-sans">{an.detail}</td>
                  </tr>))}</tbody>
              </table>
            </div>
          )}
        </section>
      )}

      <section className="card p-4">
        <div className="flex items-center justify-between mb-1">
          <h2 className="text-sm uppercase tracking-wide text-muted">Tous les actifs suivis, un par un</h2>
          <span className="text-xs text-muted">{(d.collection ?? []).length} actifs</span>
        </div>
        <p className="text-muted text-xs mb-3">
          Si une source ne répond pas, on passe à la suivante, dans cet ordre : {(d.fallback_order ?? []).join(" → ") || "—"} · réutilisation des données déjà téléchargées {d.cache ? "activée" : "désactivée"}
        </p>
        <div className="max-h-[460px] overflow-auto">
          <table className="w-full text-sm mono">
            <thead className="text-muted text-xs sticky top-0 bg-surface">
              <tr><th className="text-left font-normal">Symbole</th><th className="text-left font-normal">Catégorie</th>
              <th className="text-right font-normal" title="Nombre de journées de cotation disponibles.">Journées</th><th className="text-left font-normal">Historique depuis</th>
              <th className="text-left font-normal">Jusqu'au</th><th className="text-right font-normal">Dernier cours</th></tr>
            </thead>
            <tbody>{(d.collection ?? []).map((r: any) => (
              <tr key={r.symbol} className="border-t border-border">
                <td className="py-1.5"><IR ticker={r.symbol} assetClass={r.asset_class} className="text-accent hover:underline" /></td><td className="text-muted font-sans">{r.asset_class}</td>
                <td className="text-right">{r.bars}</td>
                <td className="text-muted">{dt(r.start)}</td><td className="text-muted">{dt(r.end)}</td>
                <td className="text-right">{r.last_close}</td>
              </tr>))}</tbody>
          </table>
        </div>
      </section>

      <section className="card p-4">
        <div className="flex justify-between items-center mb-2">
          <h2 className="text-sm uppercase tracking-wide text-muted">Exemple détaillé : {q.symbol}</h2>
          <span className="text-xs px-2 py-0.5 rounded-full bg-surfaceAlt" style={{ color: q.ok ? "#22c55e" : "#ef4444" }}>
            {q.ok ? "✓ tout est bon" : "✗ des erreurs"}
          </span>
        </div>
        <p className="text-muted text-xs">
          {q.n_rows ?? 0} journées vérifiées : aucun prix nul ou négatif · les prix d'une même journée sont cohérents entre eux · les dates se suivent dans le bon ordre · trous dans le calendrier
          {(q.warnings ?? []).length ? ` — ${q.warnings.join("; ")}` : " : aucun"}
          {(q.errors ?? []).length ? ` — ERREURS: ${q.errors.join("; ")}` : ""}
        </p>
      </section>

      <section className="card p-4">
        <h2 className="text-sm uppercase tracking-wide text-muted mb-1">Comment les données sont rangées</h2>
        <p className="text-muted2 text-xs mb-3">Trois étages : ce qui arrive brut de la source, ce qui a été nettoyé et vérifié, puis ce qui est prêt à servir aux calculs. Rien ne saute d'étage.</p>
        <div className="divide-y divide-border">
          {(d.layers ?? []).map((l: any) => (
            <div key={l.name} className="py-2">
              <div className="text-sm">
                <b>{l.name}</b>
                <span className="ml-2 text-xs px-2 py-0.5 rounded-full bg-surfaceAlt mono">{l.store}</span>
              </div>
              <div className="text-muted text-xs mt-0.5">{l.desc}</div>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
