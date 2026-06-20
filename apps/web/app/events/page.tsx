"use client";
import { useEvents } from "@/lib/api";
import { PageSkeleton, EmptyState } from "@/components/ui";

// couleur [texte, fond] par étiquette de suivi
const TAGC: Record<string, [string, string]> = {
  position: ["#22c55e", "color-mix(in srgb,#22c55e 16%,transparent)"],
  conviction: ["#a78bfa", "color-mix(in srgb,#8b5cf6 16%,transparent)"],
  ML: ["#22d3ee", "color-mix(in srgb,#22d3ee 16%,transparent)"],
  "fond.": ["#f59e0b", "color-mix(in srgb,#f59e0b 16%,transparent)"],
  "invest.": ["#f472b6", "color-mix(in srgb,#ec4899 16%,transparent)"],
};
const dt = (s?: string) => (s ? String(s).slice(0, 10) : "—");
// montants : BPA en $, revenu en $ (compact : K/M/Md)
const eps = (x?: number | null) => (x == null ? "—" : `$${x.toFixed(2)}`);
const big = (x?: number | null) => {
  if (x == null) return "—";
  const a = Math.abs(x);
  if (a >= 1e9) return `$${(x / 1e9).toFixed(2)} Md`;
  if (a >= 1e6) return `$${(x / 1e6).toFixed(1)} M`;
  if (a >= 1e3) return `$${(x / 1e3).toFixed(0)} K`;
  return `$${x.toFixed(0)}`;
};
const surprise = (est?: number | null, act?: number | null) => {
  if (est == null || act == null || est === 0) return null;
  const d = (act - est) / Math.abs(est);
  return d;
};

export default function Events() {
  const { data } = useEvents();
  if (!data) return <PageSkeleton />;
  const earnings = data.earnings ?? [];
  const ipos = data.ipos ?? [];
  const today = new Date().toISOString().slice(0, 10);
  return (
    <main className="max-w-6xl mx-auto p-6 space-y-4">
      <h1 className="text-xl font-semibold tracking-tight">Événements</h1>
      <p className="text-muted text-xs">
        Résultats trimestriels (BPA &amp; revenu estimés et annoncés) de tes positions réelles, du top 5 % des scores
        (conviction, ML, fondamentaux, investisseurs) et des sociétés de ta base,
        et IPOs US (dépôts S-1/S-1/A SEC EDGAR{data.fmp ? " + calendrier FMP" : ""}). 100 % sources publiques réelles
        {data.fmp ? "." : " — ajoute FMP_API_KEY pour le ticker, la fourchette de prix et la valorisation des IPOs."}
      </p>

      {!data.available ? (
        <EmptyState title="Aucun événement disponible"
          hint="Réseau requis (yfinance / SEC EDGAR). Lance l'API en ligne ; le calendrier se remplit (cache 6 h)." />
      ) : (
      <>
      {/* ===== RÉSULTATS TRIMESTRIELS ===== */}
      <section className="card p-4 overflow-x-auto">
        <h2 className="text-sm uppercase tracking-wide text-muted mb-1">📅 Prochains résultats trimestriels ({earnings.length})</h2>
        <p className="text-muted2 text-xs mb-3">BPA et revenu <b>estimés</b> (consensus) puis <b>annoncés (réels)</b> dès publication. « Surprise » = écart réel vs estimé.</p>
        {earnings.length === 0 ? <p className="text-muted text-sm">Aucun résultat à venir détecté.</p> : (
        <table className="w-full text-sm mono">
          <thead className="text-muted text-xs">
            <tr><th className="text-left font-normal">Date</th><th className="text-left font-normal">Actif</th>
            <th className="text-left font-normal">Société</th><th className="text-left font-normal pl-2">Suivi</th>
            <th className="text-right font-normal">BPA est.</th><th className="text-right font-normal">BPA réel</th>
            <th className="text-right font-normal">Rev. est.</th><th className="text-right font-normal">Rev. réel</th>
            <th className="text-right font-normal">Surprise</th><th className="text-left font-normal pl-2">Quand</th></tr>
          </thead>
          <tbody>{earnings.map((e: any, i: number) => {
            const sp = surprise(e.eps_estimate, e.eps_actual);
            const upcoming = (e.date ?? "") >= today;
            return (
            <tr key={i} className="border-t border-border">
              <td className="py-1.5"><span style={{ color: upcoming ? "#22d3ee" : "#9aa1ad" }}>{dt(e.date)}</span></td>
              <td>{e.symbol}</td>
              <td className="font-sans text-xs text-muted2 max-w-[180px] truncate">{e.name || "—"}</td>
              <td className="pl-2 font-sans">{(e.tags ?? []).length === 0 ? <span className="text-muted2 text-xs">base</span> :
                (e.tags ?? []).map((t: string) => (
                  <span key={t} className="text-[10px] px-1 py-0.5 rounded mr-1 whitespace-nowrap"
                    style={{ background: TAGC[t]?.[1] ?? "color-mix(in srgb,#9aa1ad 16%,transparent)", color: TAGC[t]?.[0] ?? "#9aa1ad" }}>{t}</span>))}</td>
              <td className="text-right">{eps(e.eps_estimate)}</td>
              <td className="text-right" style={{ color: e.eps_actual == null ? "#9aa1ad" : "#e5e7eb" }}>{eps(e.eps_actual)}</td>
              <td className="text-right">{big(e.revenue_estimate)}</td>
              <td className="text-right" style={{ color: e.revenue_actual == null ? "#9aa1ad" : "#e5e7eb" }}>{big(e.revenue_actual)}</td>
              <td className="text-right" style={{ color: sp == null ? "#9aa1ad" : sp >= 0 ? "#22c55e" : "#ef4444" }}>
                {sp == null ? "—" : `${sp >= 0 ? "+" : ""}${(sp * 100).toFixed(1)}%`}</td>
              <td className="pl-2 font-sans text-xs text-muted2">{e.when || (upcoming ? "à venir" : "publié")}</td>
            </tr>);})}</tbody>
        </table>)}
      </section>

      {/* ===== IPOS ===== */}
      <section className="card p-4 overflow-x-auto">
        <h2 className="text-sm uppercase tracking-wide text-muted mb-1">🚀 Prochaines IPOs US ({ipos.length})</h2>
        <p className="text-muted2 text-xs mb-3">Pipeline d'introductions en bourse : dépôts S-1/S-1/A auprès de la SEC (EDGAR){data.fmp ? " + calendrier FMP (ticker, fourchette, valorisation)" : ""}. Cliquer ouvre le dépôt SEC.</p>
        {ipos.length === 0 ? <p className="text-muted text-sm">Aucune IPO détectée (réseau requis).</p> : (
        <table className="w-full text-sm mono">
          <thead className="text-muted text-xs">
            <tr><th className="text-left font-normal">Date</th><th className="text-left font-normal">Ticker</th>
            <th className="text-left font-normal">Société</th><th className="text-left font-normal">Secteur/Bourse</th>
            <th className="text-right font-normal">Fourchette</th><th className="text-right font-normal">Valorisation</th>
            <th className="text-left font-normal pl-2">Statut</th><th className="text-left font-normal pl-2">Source</th></tr>
          </thead>
          <tbody>{ipos.map((p: any, i: number) => (
            <tr key={i} className="border-t border-border">
              <td className="py-1.5">{dt(p.date)}</td>
              <td style={{ color: p.ticker ? "#22d3ee" : "#9aa1ad" }}>{p.ticker || "—"}</td>
              <td className="font-sans text-xs max-w-[220px] truncate">
                {p.link ? <a href={p.link} target="_blank" rel="noopener noreferrer" className="text-accent hover:underline">{p.name || "—"}</a> : (p.name || "—")}</td>
              <td className="font-sans text-xs text-muted2">{p.industry || p.exchange || "—"}</td>
              <td className="text-right text-xs">{p.price_range || "—"}</td>
              <td className="text-right">{big(p.valuation)}</td>
              <td className="pl-2 font-sans text-xs"><span className="px-1.5 py-0.5 rounded-full" style={{ background: "color-mix(in srgb, #8b5cf6 16%, transparent)", color: "#a78bfa" }}>{p.status || "prévue"}</span></td>
              <td className="pl-2 font-sans text-[11px] text-muted2">{p.source}{p.sec_form ? ` · ${p.sec_form}` : ""}</td>
            </tr>))}</tbody>
        </table>)}
      </section>
      </>
      )}
      <p className="text-muted text-xs">Mise à jour ~toutes les 6 h · {dt(data.as_of)} · {data.n_symbols ?? 0} sociétés suivies.</p>
    </main>
  );
}
