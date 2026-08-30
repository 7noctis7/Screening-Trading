"use client";

import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { enTetesIA } from "@/lib/ia";
import { ReglagesIA } from "@/components/ReglagesIA";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
type Msg = { role: "user" | "assistant"; text: string; available?: boolean;
  grounded?: boolean; citations?: any[] };

const PAGE_SCOPE: Record<string, string> = {
  "/portfolio": "portfolio", "/positions": "portfolio", "/risk": "risk",
  "/screener": "screener", "/echecs": "research", "/ml": "research",
  "/methode": "vault", "/journal": "vault",
};
const SUGGESTIONS: Record<string, string[]> = {
  portfolio: ["Pourquoi ces poids ?", "Où est le risque de concentration ?"],
  risk: ["Quelles limites sont proches du seuil ?", "Quel stress est le plus dangereux ?"],
  screener: ["Pourquoi ces titres ressortent-ils ?", "Quels filtres réduisent le plus l'univers ?"],
  research: ["Les résultats sont-ils statistiquement crédibles ?", "Quels tests ont échoué ?"],
  vault: ["Pourquoi le système n'est-il pas live-ready ?", "Quelles priorités restent ouvertes ?"],
  overview: ["Résume l'état du système.", "Quelles données sont insuffisantes ?"],
};

export function QuantChat() {
  const path = usePathname();
  const scope = PAGE_SCOPE[path] ?? "overview";
  const [open, setOpen] = useState(false);
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<Msg[]>([]);
  const [loading, setLoading] = useState(false);
  const [details, setDetails] = useState(false);
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => end.current?.scrollIntoView({ behavior: "smooth" }), [messages]);

  async function ask(value?: string) {
    const q = (value ?? question).trim();
    if (q.length < 3 || loading) return;
    setMessages((m) => [...m, { role: "user", text: q }]);
    setQuestion(""); setLoading(true);
    try {
      const r = await fetch(`${BASE}/api/ai/chat`, {
        method: "POST", headers: { "Content-Type": "application/json", ...enTetesIA() },
        body: JSON.stringify({ question: q, scope, include_details: details }),
      });
      const d = await r.json();
      const text = d.available ? d.answer : `IA indisponible : ${d.reason ?? "erreur inconnue"}`;
      setMessages((m) => [...m, { role: "assistant", text, available: d.available,
        grounded: d.grounded,
        citations: d.citations ?? [] }]);
    } catch { setMessages((m) => [...m, { role: "assistant", available: false,
      text: "L'API locale ne répond pas." }]); }
    finally { setLoading(false); }
  }

  return <>
    <button onClick={() => setOpen(true)} aria-label="Interroger Quant Terminal"
      className="fixed right-5 bottom-5 z-40 rounded-full px-4 py-3 text-sm font-semibold shadow-xl border border-border"
      style={{ background: "var(--surface)", color: "var(--accent)" }}>🤖 Interroger</button>
    {open && <div className="fixed inset-0 z-50 flex justify-end" style={{ background: "rgba(0,0,0,.38)" }}>
      <section className="h-full w-full max-w-[480px] border-l border-border flex flex-col"
        style={{ background: "var(--bg)" }} role="dialog" aria-label="Copilote quantitatif">
        <header className="p-4 border-b border-border flex items-start justify-between gap-3">
          <div><h2 className="font-semibold">Copilote Quant Terminal</h2>
            <p className="text-xs text-muted mt-1">Lecture seule · scope {scope} · aucune exécution</p></div>
          <div className="flex items-center gap-2"><ReglagesIA />
            <button onClick={() => setOpen(false)} className="text-xl text-muted" aria-label="Fermer">×</button></div>
        </header>
        <div className="p-3 border-b border-border flex flex-wrap gap-2">
          {SUGGESTIONS[scope].map((s) => <button key={s} onClick={() => ask(s)}
            className="text-xs px-2 py-1 rounded-md border border-border text-muted">{s}</button>)}
        </div>
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {!messages.length && <p className="text-sm text-muted">Pose une question sur la page courante.
            Les réponses quantitatives sont contrôlées et citées.</p>}
          {messages.map((m, i) => <div key={i} className={`p-3 rounded-xl text-sm ${m.role === "user" ? "ml-8" : "mr-4"}`}
            style={{ background: m.role === "user" ? "var(--surface2)" : "var(--surface)" }}>
            <div className="whitespace-pre-wrap">{m.text}</div>
            {m.role === "assistant" && <div className="mt-2 text-[11px] text-muted2">
              {m.available === false ? "✕ CONNEXION ÉCHOUÉE"
                : m.grounded ? "✓ GROUNDED" : "⚠ UNCALIBRATED / rejeté"}
              {m.available !== false && m.citations?.map((c, j) =>
                <span key={j}> · [{j + 1}] {c.path ?? c.file}</span>)}
            </div>}
          </div>)}
          {loading && <p className="text-sm text-muted">Analyse des sources autorisées…</p>}<div ref={end} />
        </div>
        <footer className="p-4 border-t border-border">
          <label className="flex gap-2 text-xs text-muted mb-2"><input type="checkbox" checked={details}
            onChange={(e) => setDetails(e.target.checked)} /> Inclure les positions détaillées dans le contexte cloud</label>
          <div className="flex gap-2"><textarea value={question} onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); ask(); } }}
            maxLength={600} rows={2} placeholder="Interroger les données…"
            className="flex-1 rounded-lg border border-border p-2 text-sm text-fg" style={{ background: "var(--surface)" }} />
          <button onClick={() => ask()} disabled={loading || question.trim().length < 3}
            className="px-3 rounded-lg border border-border disabled:opacity-40">Envoyer</button></div>
          <button onClick={() => setMessages([])} className="text-xs text-muted mt-2">Effacer la conversation locale</button>
        </footer>
      </section>
    </div>}
  </>;
}
