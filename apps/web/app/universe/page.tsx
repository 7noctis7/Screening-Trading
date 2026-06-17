"use client";
import { useMemo, useState } from "react";
import { useUniverse } from "@/lib/api";
import { PageSkeleton } from "@/components/ui";

const nb = (x: number) => x.toLocaleString("fr-FR");

export default function Universe() {
  const { data: u } = useUniverse();
  const [q, setQ] = useState("");
  const [cls, setCls] = useState("tous");
  const all = u?.instruments ?? [];
  const filtered = useMemo(() => {
    const s = q.toLowerCase();
    return all.filter((r: any) =>
      (cls === "tous" || r.asset_class === cls) &&
      (!s || `${r.symbol} ${r.name} ${r.venue} ${r.sector ?? ""}`.toLowerCase().includes(s))
    ).slice(0, 500);
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
  return (
    <main className="max-w-5xl mx-auto p-6 space-y-4">
      <h1 className="text-xl font-semibold tracking-tight">Univers</h1>
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
          <span className="text-xs text-muted">{filtered.length} / {all.length}{filtered.length >= 500 ? " (500 affichés)" : ""}</span>
        </div>
        <input value={q} onChange={(e) => setQ(e.target.value)}
          placeholder="Rechercher un symbole, un nom, une place…"
          className="w-full bg-bg border border-border rounded-lg px-3 py-2 text-sm outline-none focus:border-accent mb-3" />
        <div className="flex gap-1.5 flex-wrap mb-3">
          {classes.map((c) => (
            <button key={c} onClick={() => setCls(c)}
              className={`text-xs px-2.5 py-1 rounded-full border ${cls === c ? "bg-accent text-white border-accent" : "border-border text-muted hover:text-fg"}`}>
              {c}
            </button>
          ))}
        </div>
        <div className="max-h-[520px] overflow-auto">
          <table className="w-full text-sm">
            <thead className="text-muted text-xs sticky top-0 bg-surface">
              <tr><th className="text-left font-normal">Symbole</th><th className="text-left font-normal">Nom</th>
              <th className="text-left font-normal">Classe</th><th className="text-left font-normal">Place</th>
              <th className="text-left font-normal">Secteur / Devise</th></tr>
            </thead>
            <tbody>{filtered.map((r: any, i: number) => (
              <tr key={`${r.symbol}-${i}`} className="border-t border-border">
                <td className="py-1.5 mono">{r.symbol}</td><td className="text-muted">{r.name}</td>
                <td>{r.asset_class}</td><td className="text-muted">{r.venue}</td>
                <td className="text-muted">{r.sector || r.currency}</td>
              </tr>))}</tbody>
          </table>
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
