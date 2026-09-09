"use client";
import { StepBanner } from "@/components/Pipeline";
import { useEffect, useMemo, useRef, useState } from "react";
import { useUniverse } from "@/lib/api";
import { PageSkeleton } from "@/components/ui";
import { downloadCsv } from "@/lib/csv";
import { IR } from "@/lib/ir";
import { DateArrete } from "@/components/DateArrete";

const nb = (x?: number) => (x ?? 0).toLocaleString("fr-FR");
// Hauteur de ligne — fixe, parce que la virtualisation calcule les positions avec.
// Deux valeurs : une ligne sur ordinateur, deux lignes sur téléphone (symbole + catégorie,
// puis le nom en entier). Changer l'affichage sans changer CE nombre ferait se chevaucher
// les lignes : la mise en page et le calcul de défilement doivent rester d'accord.
const ROW_H_LARGE = 33;
const ROW_H_ETROIT = 54;
const VIEW_H = 520;          // hauteur de la fenêtre de défilement
const BUFFER = 8;            // lignes hors écran pré-rendues

export default function Universe() {
  const { data: u } = useUniverse();
  const [q, setQ] = useState("");
  const [cls, setCls] = useState("tous");
  const [scrollTop, setScrollTop] = useState(0);
  const [sort, setSort] = useState<{ k: string; d: "asc" | "desc" }>({ k: "symbol", d: "asc" });
  const scroller = useRef<HTMLDivElement>(null);
  // `matchMedia` plutôt qu'une largeur lue au rendu : pas d'écart entre le HTML envoyé par
  // le serveur et celui du navigateur, et la valeur suit une rotation d'écran.
  const [etroit, setEtroit] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(max-width: 639px)");
    const maj = () => setEtroit(mq.matches);
    maj();
    mq.addEventListener("change", maj);
    return () => mq.removeEventListener("change", maj);
  }, []);
  const ROW_H = etroit ? ROW_H_ETROIT : ROW_H_LARGE;
  const all = u?.instruments ?? [];
  const filtered = useMemo(() => {
    const s = q.toLowerCase();
    const f = all.filter((r: any) =>
      (cls === "tous" || r.asset_class === cls) &&
      (!s || `${r.symbol} ${r.name} ${r.venue} ${r.sector ?? ""}`.toLowerCase().includes(s)));
    const key = sort.k === "sector" ? (r: any) => r.sector || r.currency || "" : (r: any) => r[sort.k] ?? "";
    return [...f].sort((a, b) => String(key(a)).localeCompare(String(key(b))) * (sort.d === "asc" ? 1 : -1));
  }, [all, q, cls, sort]);
  const toggleSort = (k: string) =>
    setSort((s) => (s.k === k ? { k, d: s.d === "asc" ? "desc" : "asc" } : { k, d: "asc" }));
  if (!u) return <PageSkeleton />;
  const byClass: [string, number][] = Object.entries(u.by_asset_class ?? {});
  const max = Math.max(1, ...byClass.map(([, v]) => v));
  const classes = ["tous", ...byClass.map(([k]) => k)];
  const cards: [string, string][] = [
    ["Instruments (complet)", nb(u.instruments_total ?? all.length)],
    ["Classes d'actifs", String(byClass.length)],
    ["Sources actives", `${u.sources_enabled} / ${u.sources_total}`],
    ["Rebuild", `${u.rebuild_cadence_days} j`],
  ];
  // fenêtre virtualisée : on ne rend que les lignes visibles (+ buffer)
  const n = filtered.length;
  const start = Math.max(0, Math.floor(scrollTop / ROW_H) - BUFFER);
  const end = Math.min(n, start + Math.ceil(VIEW_H / ROW_H) + 2 * BUFFER);
  const visible = filtered.slice(start, end);

  return (
    <main className="max-w-5xl mx-auto p-6 space-y-4">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Tout ce que le site surveille</h1>
        <p className="text-muted text-sm mt-1 max-w-3xl">
          La liste complète des actifs analysés chaque jour : actions, ETF, cryptos, devises,
          matières premières. Un actif absent de cette liste ne sera jamais proposé — pas parce
          qu'il est mauvais, mais parce qu'on ne le regarde pas.
        </p>
      </div>
      <StepBanner active="universe" />
      <DateArrete date={u.as_of} quoi="Liste des actifs" />
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {cards.map(([lab, val]) => (
          <div key={lab} className="card p-4">
            <div className="text-muted text-xs uppercase tracking-wide">{lab}</div>
            <div className="text-xl mono mt-1">{val}</div>
          </div>
        ))}
      </div>

      <section className="card p-4">
        <h2 className="text-sm uppercase tracking-wide text-muted mb-3">Combien d'actifs dans chaque catégorie</h2>
        <div className="space-y-1.5">
          {byClass.map(([k, v]) => (
            <div key={k} className="flex items-center gap-2 text-xs">
              <span className="w-24 text-muted">{k}</span>
              <span className="h-1.5 rounded bg-accent" style={{ width: `${Math.round((v / max) * 100)}%`, maxWidth: 420 }} />
              <span className="mono">{v}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="card p-4">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm uppercase tracking-wide text-muted">Chercher un actif</h2>
          <div className="flex items-center gap-3">
            <span className="text-xs text-muted">{nb(n)} affichés sur {nb(all.length)}</span>
            <button onClick={() => downloadCsv("univers", ["Symbole", "Nom", "Catégorie", "Place de cotation", "Secteur/Devise"],
              filtered.map((r: any) => [r.symbol, r.name, r.asset_class, r.venue, r.sector || r.currency]))}
              className="text-xs px-3 py-1.5 rounded-lg border border-border text-muted hover:text-fg hover:bg-surfaceAlt whitespace-nowrap">⬇ Télécharger (tableur)</button>
          </div>
        </div>
        <input value={q} onChange={(e) => { setQ(e.target.value); if (scroller.current) scroller.current.scrollTop = 0; setScrollTop(0); }}
          placeholder="Rechercher un symbole, un nom, une place…"
          className="w-full bg-bg border border-border rounded-lg px-3 py-2 text-sm outline-none focus:border-accent mb-3" />
        <div className="sm:hidden flex items-center gap-1.5 flex-wrap mb-2 text-xs">
          <span className="text-muted2">Trier par</span>
          {([["symbol", "symbole"], ["name", "nom"], ["asset_class", "catégorie"], ["venue", "place"]] as const).map(([k, lab]) => (
            <button key={k} onClick={() => toggleSort(k)}
              className={`px-2 py-1 rounded-full border ${sort.k === k ? "border-accent text-fg" : "border-border text-muted"}`}>
              {lab}{sort.k === k ? (sort.d === "asc" ? " ▲" : " ▼") : ""}
            </button>))}
        </div>
        <div className="flex gap-1.5 flex-wrap mb-3">
          {classes.map((c) => (
            <button key={c} onClick={() => { setCls(c); setScrollTop(0); if (scroller.current) scroller.current.scrollTop = 0; }}
              className={`text-xs px-2.5 py-1 rounded-full border ${cls === c ? "bg-accent text-white border-accent" : "border-border text-muted hover:text-fg"}`}>
              {c}
            </button>
          ))}
        </div>
        {/* en-tête fixe + corps virtualisé (gère 900+ lignes sans ralentir) */}
        {/* Sous 640 px, cinq colonnes fixes laissaient « Nom » et « Secteur » à ~50 px : rien
            n'était injoignable (la grille se rétracte, mesuré), mais tout était tronqué à
            quelques caractères. On passe donc à DEUX LIGNES par actif sur téléphone — le
            symbole et sa catégorie d'abord, le nom en dessous, en entier. L'en-tête de tri
            disparaît avec les colonnes qu'il titrait ; le tri reste accessible juste au-dessus. */}
        <div className="hidden sm:grid grid-cols-5 gap-2 text-muted text-xs px-1 pb-1 border-b border-border select-none">
          {([["symbol", "Symbole"], ["name", "Nom"], ["asset_class", "Catégorie"], ["venue", "Place de cotation"], ["sector", "Secteur / Devise"]] as const).map(([k, lab]) => (
            <span key={k} onClick={() => toggleSort(k)} className="cursor-pointer hover:text-fg">
              {lab}{sort.k === k ? <span style={{ color: "var(--accent2)" }}>{sort.d === "asc" ? " ▲" : " ▼"}</span> : <span style={{ opacity: 0.35 }}> ↕</span>}
            </span>
          ))}
        </div>
        <div ref={scroller} onScroll={(e) => setScrollTop((e.target as HTMLDivElement).scrollTop)}
          style={{ height: VIEW_H, overflow: "auto" }}>
          <div style={{ height: n * ROW_H, position: "relative" }}>
            <div style={{ transform: `translateY(${start * ROW_H}px)` }}>
              {visible.map((r: any, i: number) => (
                <div key={`${r.symbol}-${start + i}`}
                  className="border-b border-border text-sm" style={{ height: ROW_H }}>
                  {etroit ? (
                    <div className="flex flex-col justify-center h-full gap-0.5 py-1">
                      <div className="flex items-baseline gap-2">
                        <IR ticker={r.symbol} name={r.name} assetClass={r.asset_class} className="mono text-accent hover:underline" />
                        <span className="text-muted2 text-[11px]">{r.asset_class} · {r.venue}</span>
                      </div>
                      <div className="text-muted text-xs truncate"
                        title={`${r.name}${(r.sector || r.currency) ? ` — ${r.sector || r.currency}` : ""}`}>
                        {r.name}{(r.sector || r.currency) ? ` — ${r.sector || r.currency}` : ""}
                      </div>
                    </div>
                  ) : (
                    <div className="grid grid-cols-5 gap-2 items-center h-full">
                      <IR ticker={r.symbol} name={r.name} assetClass={r.asset_class} className="mono text-accent hover:underline truncate" />
                      <span className="text-muted truncate">{r.name}</span>
                      <span>{r.asset_class}</span>
                      <span className="text-muted">{r.venue}</span>
                      <span className="text-muted truncate">{r.sector || r.currency}</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="card p-4 overflow-x-auto">
        <h2 className="text-sm uppercase tracking-wide text-muted mb-1">D'où vient cette liste</h2>
        <p className="text-muted2 text-xs mb-3">Certaines sources sont des fichiers stockés ici, qui marchent même sans internet ; d'autres vont chercher la liste en ligne. Une source désactivée n'apporte rien à la liste.</p>
        <table className="w-full text-sm">
          <thead className="text-muted text-xs">
            <tr><th className="text-left font-normal">Source</th><th className="text-left font-normal">Type</th>
            <th className="text-left font-normal">Besoin d'internet</th><th className="text-left font-normal">Utilisée</th></tr>
          </thead>
          <tbody>{(u.sources ?? []).map((s: any) => (
            <tr key={s.id} className="border-t border-border">
              <td className="py-1.5 mono">{s.id}</td><td className="text-muted">{s.kind}</td>
              <td style={{ color: s.network ? "#f59e0b" : "#22c55e" }}>{s.network ? "oui" : "non — fichier local"}</td>
              <td style={{ color: s.enabled ? "#22c55e" : "#9aa1ab" }}>{s.enabled ? "oui" : "non"}</td>
            </tr>))}</tbody>
        </table>
      </section>
    </main>
  );
}
