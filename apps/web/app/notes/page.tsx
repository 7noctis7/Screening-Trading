"use client";
import { useState } from "react";
import { useNotes } from "@/lib/api";
import { PageSkeleton } from "@/components/ui";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function NotesPage() {
  const { data } = useNotes();
  const [q, setQ] = useState("");
  const [gen, setGen] = useState("");
  if (!data) return <PageSkeleton />;
  const notes: any[] = data.notes ?? [];
  const filtered = notes.filter((n) => !q || String(n.symbol).toUpperCase().includes(q.toUpperCase()));
  const byDate: Record<string, any[]> = {};
  for (const n of filtered) (byDate[n.date] ??= []).push(n);

  return (
    <main className="max-w-4xl mx-auto p-6 space-y-4">
      <h1 className="text-xl font-semibold tracking-tight">Notes d'analyse</h1>
      <p className="text-muted text-xs">Notes fondamentales (Vernimmen + Damodaran, intrants audités PwC) — archivées chaque nuit, ou générées à la demande pour n'importe quel ticker.</p>

      {/* génération à la demande */}
      <section className="card p-4">
        <h2 className="text-sm uppercase tracking-wide text-muted mb-2">Générer une note</h2>
        <div className="flex items-center gap-2 flex-wrap">
          <input value={gen} onChange={(e) => setGen(e.target.value.toUpperCase())}
            placeholder="ticker (ex. AAPL)" className="text-sm px-2 py-1 rounded bg-surfaceAlt border border-border outline-none w-44" />
          {([["HTML sombre", "html", "dark"], ["HTML clair", "html", "light"], ["PDF sombre", "pdf", "dark"], ["PDF clair", "pdf", "light"]] as [string, string, string][]).map(([lab, fmt, th]) => (
            <a key={lab} href={gen ? `${BASE}/api/company_report?ticker=${encodeURIComponent(gen)}&format=${fmt}&theme=${th}` : undefined}
              target="_blank" rel="noopener noreferrer"
              className={`text-sm px-3 py-1 rounded-md border border-border ${gen ? "text-accent hover:bg-surfaceAlt" : "text-muted2 pointer-events-none opacity-50"}`}>
              {lab}</a>
          ))}
        </div>
      </section>

      {/* archives */}
      <section className="card p-4">
        <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
          <h2 className="text-sm uppercase tracking-wide text-muted">Notes archivées</h2>
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="filtrer par ticker"
            className="text-sm px-2 py-1 rounded bg-surfaceAlt border border-border outline-none w-44" />
        </div>
        {!data.available ? (
          <p className="text-muted text-sm">Aucune note archivée pour l'instant. Elles sont générées chaque nuit (<code className="mono">make reports</code>) ou à la demande ci-dessus.</p>
        ) : (
          <div className="space-y-4">
            {Object.entries(byDate).map(([date, items]) => (
              <div key={date}>
                <div className="text-xs text-muted2 mono mb-1">{date} · {items.length} notes</div>
                <div className="flex flex-wrap gap-2">
                  {items.sort((a, b) => a.symbol.localeCompare(b.symbol)).map((n) => (
                    <span key={n.symbol} className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md border border-border text-sm">
                      <span className="mono">{n.symbol}</span>
                      {n.html && <a href={`${BASE}${n.html}`} target="_blank" rel="noopener noreferrer" className="text-accent hover:underline text-xs">HTML</a>}
                      {n.pdf && <a href={`${BASE}${n.pdf}`} target="_blank" rel="noopener noreferrer" className="text-accent hover:underline text-xs">PDF</a>}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
