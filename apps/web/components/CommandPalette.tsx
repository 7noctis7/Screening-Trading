"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";

// Palette de commandes ⌘K / Ctrl+K — navigation rapide + filtre clavier (UX pro).
const PAGES: [string, string][] = [
  ["/accueil", "Accueil"], ["/dashboard", "Dashboard"], ["/data", "Données"], ["/universe", "Univers"],
  ["/macro", "Macro"], ["/crypto", "Crypto"], ["/themes", "Thèmes de marché"], ["/events", "Événements"], ["/fundamentals", "Fondamentaux"], ["/investors", "Investisseurs"],
  ["/ml", "Signaux ML"], ["/sentiment", "Sentiment & news"], ["/conviction", "Conviction"],
  ["/portfolio", "Portefeuille & Analyse"], ["/risk", "Risque"],
  ["/positions", "Positions"], ["/trades", "Trades"], ["/live", "Portefeuille réel"],
];

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [i, setI] = useState(0);
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault(); setOpen((v) => !v);
      } else if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => { if (open) { setQ(""); setI(0); setTimeout(() => inputRef.current?.focus(), 0); } }, [open]);

  const results = useMemo(() => {
    const s = q.trim().toLowerCase();
    return PAGES.filter(([, label]) => !s || label.toLowerCase().includes(s));
  }, [q]);

  if (!open) return null;
  const go = (href: string) => { setOpen(false); router.push(href); };
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[18vh] px-4"
      style={{ background: "rgba(0,0,0,.5)" }} onClick={() => setOpen(false)}>
      <div className="w-full max-w-lg card overflow-hidden" onClick={(e) => e.stopPropagation()}
        style={{ boxShadow: "var(--shadow)" }}>
        <input ref={inputRef} value={q}
          onChange={(e) => { setQ(e.target.value); setI(0); }}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") { e.preventDefault(); setI((x) => Math.min(x + 1, results.length - 1)); }
            else if (e.key === "ArrowUp") { e.preventDefault(); setI((x) => Math.max(x - 1, 0)); }
            else if (e.key === "Enter" && results[i]) go(results[i][0]);
          }}
          placeholder="Aller à…  (⌘K)"
          className="w-full bg-transparent px-4 py-3 text-sm outline-none border-b border-border" />
        <div className="max-h-72 overflow-y-auto py-1">
          {results.length === 0 ? (
            <div className="px-4 py-3 text-muted text-sm">Aucun résultat.</div>
          ) : results.map(([href, label], idx) => (
            <button key={href} onMouseEnter={() => setI(idx)} onClick={() => go(href)}
              className={`w-full text-left px-4 py-2 text-sm flex items-center gap-2 ${
                idx === i ? "bg-surfaceAlt text-fg" : "text-muted"}`}>
              <span className="text-accent2">→</span> {label}
            </button>
          ))}
        </div>
        <div className="px-4 py-2 text-[11px] text-muted2 border-t border-border flex gap-3">
          <span>↑↓ naviguer</span><span>⏎ ouvrir</span><span>Échap fermer</span>
        </div>
      </div>
    </div>
  );
}
