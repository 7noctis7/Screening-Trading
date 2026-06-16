"use client";
import { useUniverse } from "@/lib/api";

const nb = (x: number) => x.toLocaleString("fr-FR");

export default function Universe() {
  const { data: u } = useUniverse();
  if (!u) return <div className="p-8 text-muted">Chargement…</div>;
  const byClass: [string, number][] = Object.entries(u.by_asset_class ?? {});
  const max = Math.max(1, ...byClass.map(([, v]) => v));
  const cards: [string, string][] = [
    ["Sources actives", `${u.sources_enabled} / ${u.sources_total}`],
    ["Instruments seed", nb(u.seed_total)],
    ["Classes d'actifs", String(byClass.length)],
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
        <h2 className="text-sm uppercase tracking-wide text-muted mb-3">Répartition par classe d'actifs (seed offline)</h2>
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

      {u.sample?.length > 0 && (
        <section className="card p-4 overflow-x-auto">
          <h2 className="text-sm uppercase tracking-wide text-muted mb-3">Échantillon d'instruments</h2>
          <table className="w-full text-sm">
            <thead className="text-muted text-xs">
              <tr><th className="text-left font-normal">Symbole</th><th className="text-left font-normal">Nom</th>
              <th className="text-left font-normal">Classe</th><th className="text-left font-normal">Place</th></tr>
            </thead>
            <tbody>{u.sample.map((r: any, i: number) => (
              <tr key={`${r.symbol}-${i}`} className="border-t border-border">
                <td className="py-1.5 mono">{r.symbol}</td><td className="text-muted">{r.name}</td>
                <td>{r.asset_class}</td><td className="text-muted">{r.venue}</td>
              </tr>))}</tbody>
          </table>
        </section>
      )}
    </main>
  );
}
