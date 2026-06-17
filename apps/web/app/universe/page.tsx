"use client";
import { StepBanner } from "@/components/Pipeline";
import { useMemo, useRef, useState } from "react";
import { useUniverse } from "@/lib/api";
import { PageSkeleton } from "@/components/ui";
import { downloadCsv } from "@/lib/csv";

const nb = (x?: number) => (x ?? 0).toLocaleString("fr-FR");
const ROW_H = 33;            // hauteur de ligne fixe (virtualisation)
const VIEW_H = 520;          // hauteur de la fenêtre de défilement
const BUFFER = 8;            // lignes hors écran pré-rendues

export default function Universe() {
  const { data: u } = useUniverse();
  const [q, setQ] = useState("");
  const [cls, setCls] = useState("tous");
  const [scrollTop, setScrollTop] = useState(0);
  const scroller = useRef<HTMLDivElement>(null);
  const all = u?.instruments ?? [];
  const filtered = useMemo(() => {
    const s = q.toLowerCase();
    return all.filter((r: any) =>
      (cls === "tous" || r.asset_class === cls) &&
      (!s || `${r.symbol} ${r.name} ${r.venue} ${r.sector ?? ""}`.toLowerCase().includes(s))
    );
  }, [all, q, cls]);
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
      <h1 className="text-xl font-semibold tracking-tight">Univers</h1>
      <StepBanner active="universe" />
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {cards.map(([lab, val]) => (
          <div key={lab} className="card p-4">
            <div className="text-muted text-xs uppercase tracking-wide">{lab}</div>
            <div className="text-xl mono mt-1">{val}</div>
          </div>
        ))}
      </div>

      <section className="card p-4">
        <h2 className="text-sm uppercase tracking-wide text-muted mb-3">Répartition par classe d'actifs</h2>
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
          <h2 className="text-sm uppercase tracking-wide text-muted">Univers complet — explorateur</h2>
          <div className="flex items-center gap-3">
            <span className="text-xs text-muted">{nb(n)} / {nb(all.length)} (virtualisé)</span>
            <button onClick={() => downloadCsv("univers", ["Symbole", "Nom", "Classe", "Place", "Secteur/Devise"],
              filtered.map((r: any) => [r.symbol, r.name, r.asset_class, r.venue, r.sector || r.currency]))}
              className="text-xs px-3 py-1.5 rounded-lg border border-border text-muted hover:text-fg hover:bg-surfaceAlt whitespace-nowrap">⬇ Export CSV</button>
          </div>
        </div>
        <input value={q} onChange={(e) => { setQ(e.target.value); if (scroller.current) scroller.current.scrollTop = 0; setScrollTop(0); }}
          placeholder="Rechercher un symbole, un nom, une place…"
          className="w-full bg-bg border border-border rounded-lg px-3 py-2 text-sm outline-none focus:border-accent mb-3" />
        <div className="flex gap-1.5 flex-wrap mb-3">
          {classes.map((c) => (
            <button key={c} onClick={() => { setCls(c); setScrollTop(0); if (scroller.current) scroller.current.scrollTop = 0; }}
              className={`text-xs px-2.5 py-1 rounded-full border ${cls === c ? "bg-accent text-white border-accent" : "border-border text-muted hover:text-fg"}`}>
              {c}
            </button>
          ))}
        </div>
        {/* en-tête fixe + corps virtualisé (gère 900+ lignes sans ralentir) */}
        <div className="grid grid-cols-5 gap-2 text-muted text-xs px-1 pb-1 border-b border-border">
          <span>Symbole</span><span>Nom</span><span>Classe</span><span>Place</span><span>Secteur / Devise</span>
        </div>
        <div ref={scroller} onScroll={(e) => setScrollTop((e.target as HTMLDivElement).scrollTop)}
          style={{ height: VIEW_H, overflow: "auto" }}>
          <div style={{ height: n * ROW_H, position: "relative" }}>
            <div style={{ transform: `translateY(${start * ROW_H}px)` }}>
              {visible.map((r: any, i: number) => (
                <div key={`${r.symbol}-${start + i}`}
                  className="grid grid-cols-5 gap-2 text-sm border-b border-border items-center"
                  style={{ height: ROW_H }}>
                  <span className="mono">{r.symbol}</span>
                  <span className="text-muted truncate">{r.name}</span>
                  <span>{r.asset_class}</span>
                  <span className="text-muted">{r.venue}</span>
                  <span className="text-muted truncate">{r.sector || r.currency}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="card p-4 overflow-x-auto">
        <h2 className="text-sm uppercase tracking-wide text-muted mb-3">Sources déclaratives (offline + réseau)</h2>
        <table className="w-full text-sm">
          <thead className="text-muted text-xs">
            <tr><th className="text-left font-normal">Source</th><th className="text-left font-normal">Type</th>
            <th className="text-left font-normal">Accès</th><th className="text-left font-normal">Statut</th></tr>
          </thead>
          <tbody>{(u.sources ?? []).map((s: any) => (
            <tr key={s.id} className="border-t border-border">
              <td className="py-1.5 mono">{s.id}</td><td className="text-muted">{s.kind}</td>
              <td style={{ color: s.network ? "#f59e0b" : "#22c55e" }}>{s.network ? "réseau" : "offline"}</td>
              <td style={{ color: s.enabled ? "#22c55e" : "#9aa1ab" }}>{s.enabled ? "activée" : "désactivée"}</td>
            </tr>))}</tbody>
        </table>
      </section>
    </main>
  );
}
