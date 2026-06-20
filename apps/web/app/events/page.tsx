"use client";
import { useMemo, useState } from "react";
import { useEvents } from "@/lib/api";
import { PageSkeleton, EmptyState } from "@/components/ui";

// étiquettes de suivi : couleur, emoji et description (pour la légende + filtre)
const TAGS: Record<string, { c: string; bg: string; emoji: string; desc: string }> = {
  position: { c: "#22c55e", bg: "color-mix(in srgb,#22c55e 16%,transparent)", emoji: "💼", desc: "Tu détiens ce titre (Alpaca / Bitmart)" },
  conviction: { c: "#a78bfa", bg: "color-mix(in srgb,#8b5cf6 16%,transparent)", emoji: "⭐", desc: "Top 5 % de la note de conviction (fusion des lentilles)" },
  ML: { c: "#22d3ee", bg: "color-mix(in srgb,#22d3ee 16%,transparent)", emoji: "🤖", desc: "Top 5 % du score Machine Learning" },
  "fond.": { c: "#f59e0b", bg: "color-mix(in srgb,#f59e0b 16%,transparent)", emoji: "📊", desc: "Top 5 % du score fondamental" },
  "invest.": { c: "#60a5fa", bg: "color-mix(in srgb,#3b82f6 16%,transparent)", emoji: "🏦", desc: "Top 5 % du score investisseurs (13F / superinvestisseurs)" },
  base: { c: "#9aa1ad", bg: "color-mix(in srgb,#9aa1ad 16%,transparent)", emoji: "•", desc: "Présent dans ta base, hors top scores" },
};
const TAGC = (t: string): [string, string] => [TAGS[t]?.c ?? "#9aa1ad", TAGS[t]?.bg ?? "color-mix(in srgb,#9aa1ad 16%,transparent)"];
const dt = (s?: string) => (s ? String(s).slice(0, 10) : "—");
const eps = (x?: number | null) => (x == null ? "—" : `$${x.toFixed(2)}`);
const big = (x?: number | null) => {
  if (x == null) return "—";
  const a = Math.abs(x);
  if (a >= 1e9) return `$${(x / 1e9).toFixed(2)} Md`;
  if (a >= 1e6) return `$${(x / 1e6).toFixed(1)} M`;
  if (a >= 1e3) return `$${(x / 1e3).toFixed(0)} K`;
  return `$${x.toFixed(0)}`;
};
const surprise = (est?: number | null, act?: number | null) =>
  (est == null || act == null || est === 0 ? null : (act - est) / Math.abs(est));

// tri générique : nombres et chaînes, valeurs nulles en dernier
function sortRows<T extends Record<string, any>>(rows: T[], k: string, dir: number): T[] {
  return [...rows].sort((a, b) => {
    const av = a[k], bv = b[k];
    if (av == null && bv == null) return 0;
    if (av == null) return 1;
    if (bv == null) return -1;
    return typeof av === "number" && typeof bv === "number"
      ? dir * (av - bv) : dir * String(av).localeCompare(String(bv));
  });
}

export default function Events() {
  const { data } = useEvents();
  const [eQ, setEQ] = useState("");
  const [eScope, setEScope] = useState<"top" | "all">("top");   // défaut : top 5 % ; "all" = toute la base
  const [eTag, setETag] = useState("tout");
  const [eWhen, setEWhen] = useState("tout");
  const [eSort, setESort] = useState<{ k: string; dir: number }>({ k: "date", dir: 1 });
  const [iQ, setIQ] = useState("");
  const [iSort, setISort] = useState<{ k: string; dir: number }>({ k: "date", dir: 1 });

  const earnings = data?.earnings ?? [];
  const ipos = data?.ipos ?? [];
  const today = new Date().toISOString().slice(0, 10);

  const earnRows = useMemo(() => {
    const q = eQ.trim().toUpperCase();
    let r = earnings.map((e: any) => ({ ...e, _sp: surprise(e.eps_estimate, e.eps_actual),
      _when: (e.date ?? "") >= today ? "à venir" : "publié" }));
    // par défaut on n'affiche QUE le top 5 % (lignes étiquetées) ; "Toute la base" lève ce filtre.
    // une recherche explicite donne aussi accès à toute la base.
    if (eScope === "top" && !q) r = r.filter((e: any) => (e.tags ?? []).length > 0);
    if (q) r = r.filter((e: any) => `${e.symbol} ${e.name}`.toUpperCase().includes(q));
    if (eTag === "base") r = r.filter((e: any) => !(e.tags ?? []).length);
    else if (eTag !== "tout") r = r.filter((e: any) => (e.tags ?? []).includes(eTag));
    if (eWhen !== "tout") r = r.filter((e: any) => e._when === eWhen);
    return sortRows(r, eSort.k, eSort.dir);
  }, [earnings, eQ, eScope, eTag, eWhen, eSort, today]);

  const ipoRows = useMemo(() => {
    const q = iQ.trim().toUpperCase();
    let r = ipos;
    if (q) r = r.filter((p: any) => `${p.ticker} ${p.name} ${p.industry} ${p.exchange}`.toUpperCase().includes(q));
    return sortRows(r, iSort.k, iSort.dir);
  }, [ipos, iQ, iSort]);

  if (!data) return <PageSkeleton />;

  // en-tête de colonne cliquable (tri)
  const Th = ({ k, label, r, sort, set }: { k: string; label: string; r?: boolean; sort: { k: string; dir: number }; set: (s: { k: string; dir: number }) => void }) => (
    <th className={`font-normal cursor-pointer select-none hover:text-fg ${r ? "text-right" : "text-left"} ${r ? "" : "pr-2"}`}
      onClick={() => set({ k, dir: sort.k === k ? -sort.dir : 1 })}>
      {label}{sort.k === k ? (sort.dir < 0 ? " ▼" : " ▲") : ""}</th>);

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
        <h2 className="text-sm uppercase tracking-wide text-muted mb-1">📅 Prochains résultats trimestriels ({earnRows.length}/{earnings.length})</h2>
        <p className="text-muted2 text-xs mb-2">BPA et revenu <b>estimés</b> (consensus) puis <b>annoncés (réels)</b> dès publication. « Surprise » = écart réel vs estimé (donc « — » pour les rapports à venir, c'est normal).
        {!data.fmp_earnings && <> · <span className="text-muted2">Source yfinance : le <b>revenu réel</b> n'est renseigné que pour le dernier trimestre publié ; le calendrier FMP (plan payant) le fournit pour tous.</span></>}</p>
        {/* LÉGENDE des étiquettes « Suivi » */}
        <div className="flex flex-wrap gap-x-4 gap-y-1 mb-3 text-xs">
          <span className="text-muted2 uppercase tracking-wide">Légende :</span>
          {Object.entries(TAGS).map(([k, v]) => (
            <span key={k} className="flex items-center gap-1">
              <span className="text-[10px] px-1 py-0.5 rounded whitespace-nowrap" style={{ background: v.bg, color: v.c }}>{v.emoji} {k}</span>
              <span className="text-muted2">{v.desc}</span>
            </span>))}
        </div>
        {/* RECHERCHE + FILTRES */}
        <div className="flex flex-wrap items-center gap-2 mb-3">
          <div className="flex rounded overflow-hidden border border-border text-sm">
            <button onClick={() => setEScope("top")}
              className={`px-2.5 py-1 ${eScope === "top" ? "bg-accent text-bg" : "bg-surfaceAlt text-muted hover:text-fg"}`}>⭐ Top 5 %</button>
            <button onClick={() => setEScope("all")}
              className={`px-2.5 py-1 ${eScope === "all" ? "bg-accent text-bg" : "bg-surfaceAlt text-muted hover:text-fg"}`}>Toute la base</button>
          </div>
          <input value={eQ} onChange={(e) => setEQ(e.target.value)} placeholder="rechercher (ticker ou société)"
            className="text-sm px-2 py-1 rounded bg-surfaceAlt border border-border outline-none w-56" />
          <select value={eTag} onChange={(e) => setETag(e.target.value)}
            className="text-sm px-2 py-1 rounded bg-surfaceAlt border border-border outline-none">
            <option value="tout">Tous les suivis</option>
            {Object.keys(TAGS).map((k) => <option key={k} value={k}>{TAGS[k].emoji} {k}</option>)}
          </select>
          <select value={eWhen} onChange={(e) => setEWhen(e.target.value)}
            className="text-sm px-2 py-1 rounded bg-surfaceAlt border border-border outline-none">
            <option value="tout">À venir + publiés</option>
            <option value="à venir">À venir</option>
            <option value="publié">Publiés</option>
          </select>
          <span className="text-muted2 text-xs">clique un en-tête pour trier{eScope === "all" ? " · « Toute la base » = sociétés au calendrier disponible (échantillon yfinance le plus large ; FMP plan = exhaustif)" : ""}</span>
        </div>
        {earnRows.length === 0 ? <p className="text-muted text-sm">Aucun résultat ne correspond.</p> : (
        <table className="w-full text-sm mono">
          <thead className="text-muted text-xs"><tr>
            <Th k="date" label="Date" sort={eSort} set={setESort} /><Th k="symbol" label="Actif" sort={eSort} set={setESort} />
            <Th k="name" label="Société" sort={eSort} set={setESort} /><th className="text-left font-normal pl-2">Suivi</th>
            <Th k="eps_estimate" label="BPA est." r sort={eSort} set={setESort} /><Th k="eps_actual" label="BPA réel" r sort={eSort} set={setESort} />
            <Th k="revenue_estimate" label="Rev. est." r sort={eSort} set={setESort} /><Th k="revenue_actual" label="Rev. réel" r sort={eSort} set={setESort} />
            <Th k="_sp" label="Surprise" r sort={eSort} set={setESort} /><Th k="_when" label="Quand" sort={eSort} set={setESort} />
          </tr></thead>
          <tbody>{earnRows.map((e: any, i: number) => (
            <tr key={i} className="border-t border-border">
              <td className="py-1.5"><span style={{ color: e._when === "à venir" ? "#22d3ee" : "#9aa1ad" }}>{dt(e.date)}</span></td>
              <td>{e.symbol}</td>
              <td className="font-sans text-xs text-muted2 max-w-[180px] truncate">{e.name || "—"}</td>
              <td className="pl-2 font-sans">{((e.tags ?? []).length === 0 ? ["base"] : e.tags).map((t: string) => (
                <span key={t} className="text-[10px] px-1 py-0.5 rounded mr-1 whitespace-nowrap"
                  style={{ background: TAGC(t)[1], color: TAGC(t)[0] }}>{TAGS[t]?.emoji} {t}</span>))}</td>
              <td className="text-right">{eps(e.eps_estimate)}</td>
              <td className="text-right" style={{ color: e.eps_actual == null ? "#9aa1ad" : "#e5e7eb" }}>{eps(e.eps_actual)}</td>
              <td className="text-right">{big(e.revenue_estimate)}</td>
              <td className="text-right" style={{ color: e.revenue_actual == null ? "#9aa1ad" : "#e5e7eb" }}>{big(e.revenue_actual)}</td>
              <td className="text-right" style={{ color: e._sp == null ? "#9aa1ad" : e._sp >= 0 ? "#22c55e" : "#ef4444" }}>
                {e._sp == null ? "—" : `${e._sp >= 0 ? "+" : ""}${(e._sp * 100).toFixed(1)}%`}</td>
              <td className="pl-2 font-sans text-xs text-muted2">{e.when || e._when}</td>
            </tr>))}</tbody>
        </table>)}
      </section>

      {/* ===== IPOS ===== */}
      <section className="card p-4 overflow-x-auto">
        <h2 className="text-sm uppercase tracking-wide text-muted mb-1">🚀 Prochaines IPOs US ({ipoRows.length}/{ipos.length})</h2>
        <p className="text-muted2 text-xs mb-3">Pipeline d'introductions en bourse : dépôts S-1/S-1/A auprès de la SEC (EDGAR){data.fmp ? " + calendrier FMP (ticker, fourchette, valorisation)" : ""}. Cliquer ouvre le dépôt SEC.</p>
        <div className="flex flex-wrap items-center gap-2 mb-3">
          <input value={iQ} onChange={(e) => setIQ(e.target.value)} placeholder="rechercher (société, ticker, secteur)"
            className="text-sm px-2 py-1 rounded bg-surfaceAlt border border-border outline-none w-64" />
          <span className="text-muted2 text-xs">clique un en-tête pour trier</span>
        </div>
        {ipoRows.length === 0 ? <p className="text-muted text-sm">Aucune IPO ne correspond.</p> : (
        <table className="w-full text-sm mono">
          <thead className="text-muted text-xs"><tr>
            <Th k="date" label="Date" sort={iSort} set={setISort} /><Th k="ticker" label="Ticker" sort={iSort} set={setISort} />
            <Th k="name" label="Société" sort={iSort} set={setISort} /><Th k="industry" label="Secteur/Bourse" sort={iSort} set={setISort} />
            <th className="text-right font-normal">Fourchette</th><Th k="valuation" label="Valorisation" r sort={iSort} set={setISort} />
            <Th k="status" label="Statut" sort={iSort} set={setISort} /><Th k="source" label="Source" sort={iSort} set={setISort} />
          </tr></thead>
          <tbody>{ipoRows.map((p: any, i: number) => (
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
