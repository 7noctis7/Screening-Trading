"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { ThemeToggle } from "@/components/ThemeToggle";
import { LiveBadge } from "@/components/LiveBadge";
import { useMeta } from "@/lib/api";

// Ordre = flux logique : données → analyses → risque → exécution
const LINKS: [string, string][] = [
  ["/accueil", "Accueil"],
  ["/data", "Données"],
  ["/universe", "Univers"],
  ["/macro", "Macro"],
  ["/themes", "Thèmes de marché"],
  ["/events", "Événements"],
  ["/fundamentals", "Fondamentaux"],
  ["/notes", "Notes d'analyse"],
  ["/investors", "Investisseurs"],
  ["/ml", "Signaux ML"],
  ["/sentiment", "Sentiment & news"],
  ["/conviction", "Conviction"],
  ["/", "Dashboard"],
  ["/portfolio", "Portefeuille & Analyse"],
  ["/risk", "Risque"],
  ["/positions", "Positions"],
  ["/trades", "Trades"],
  ["/live", "Portefeuille réel"],
];

// Regroupement par thème pour le tiroir mobile (lecture premium, style réglages iOS).
const GROUPS: [string, string[]][] = [
  ["Marché", ["/data", "/universe", "/macro", "/themes", "/events"]],
  ["Analyse", ["/fundamentals", "/notes", "/investors", "/ml", "/sentiment", "/conviction"]],
  ["Portefeuille", ["/", "/portfolio", "/risk", "/positions", "/trades", "/live"]],
];
const LABEL: Record<string, string> = Object.fromEntries(LINKS);

const isActive = (href: string, path: string) => (href === "/" ? path === "/" : path.startsWith(href));

function StatusDot({ meta, withLabel = false }: { meta: any; withLabel?: boolean }) {
  if (!meta) return null;
  const synth = meta.data_synthetic;
  const audit = meta.audit;
  const tone = synth ? "#ef4444" : (audit && !audit.ok ? "#f59e0b" : "#22c55e");
  const label = synth ? "synthétique"
    : audit ? (audit.ok ? "données auditées" : `${audit.counts?.critical ?? 0} critique(s)`)
    : "données réelles";
  const title = synth ? "Données synthétiques — démo UI uniquement."
    : audit ? `Audit PwC : ${audit.counts?.critical ?? 0} critiques · ${audit.counts?.major ?? 0} majeures · ${audit.counts?.warning ?? 0} avertissements`
    : "Données réelles (audit non calculé).";
  return (
    <Link href="/data" title={title}
      className={`items-center gap-1.5 text-[11px] text-muted2 mono px-2 py-1 rounded-md border border-border hover:text-fg transition-colors ${withLabel ? "inline-flex" : "hidden md:inline-flex"}`}>
      <span className="inline-block w-1.5 h-1.5 rounded-full" style={{ background: tone, boxShadow: `0 0 8px ${tone}` }} />
      {(withLabel || true) && label}
    </Link>
  );
}

export function Nav() {
  const path = usePathname();
  const { data: meta } = useMeta();
  const [open, setOpen] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => { setMounted(true); }, []);
  // Ferme le tiroir au changement de page + verrouille le scroll du body quand il est ouvert.
  useEffect(() => { setOpen(false); }, [path]);
  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : "";
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    window.addEventListener("keydown", onKey);
    return () => { document.body.style.overflow = ""; window.removeEventListener("keydown", onKey); };
  }, [open]);

  const Brand = (
    <span className="flex items-center gap-2 text-sm font-semibold tracking-tight">
      <span className="inline-block w-[18px] h-[18px] rounded-md"
        style={{ background: "linear-gradient(135deg,#22d3ee,#5eead4 55%,#22c55e)", boxShadow: "0 0 0 1px rgba(255,255,255,.08),0 4px 16px rgba(34,211,238,.5)" }} />
      Quant Terminal
    </span>
  );

  const bar = (
    <nav className="sticky top-0 z-30 border-b border-border nav-safe"
      style={{ background: "color-mix(in srgb, var(--bg) 72%, transparent)", backdropFilter: "saturate(160%) blur(14px)", WebkitBackdropFilter: "saturate(160%) blur(14px)" }}>
      {meta?.data_synthetic && (
        <div className="px-4 py-1 text-[11px] text-center"
          style={{ background: "color-mix(in srgb, var(--warn) 22%, transparent)", color: "var(--warn)" }}>
          ⚠️ Données factices (synthétiques) — démo UI uniquement, ne pas décider.
        </div>
      )}

      {/* ---- Barre MOBILE : compacte (marque + thème + menu) ---- */}
      <div className="md:hidden max-w-6xl mx-auto px-4 h-14 flex items-center gap-2">
        <Link href="/" className="min-w-0">{Brand}</Link>
        <span className="ml-auto" />
        <ThemeToggle />
        <button onClick={() => setOpen(true)} aria-label="Ouvrir le menu" aria-expanded={open}
          className="grid place-items-center w-10 h-10 rounded-[12px] border border-border text-fg active:scale-95 transition-transform"
          style={{ background: "var(--surface)" }}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <line x1="3" y1="7" x2="21" y2="7" /><line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="17" x2="21" y2="17" />
          </svg>
        </button>
      </div>

      {/* ---- Barre DESKTOP : navigation horizontale ---- */}
      <div className="hidden md:flex max-w-6xl mx-auto px-6 py-3 flex-wrap gap-1.5 items-center">
        <Link href="/" className="mr-3">{Brand}</Link>
        {LINKS.map(([href, label]) => {
          const active = isActive(href, path);
          return (
            <Link key={href} href={href}
              className={`px-3 py-1.5 rounded-[10px] text-sm transition-all duration-150 border ${
                active ? "bg-surfaceAlt text-fg border-border2 shadow"
                       : "text-muted hover:text-fg hover:bg-surfaceAlt border-transparent"}`}>
              {active && <span className="inline-block w-1.5 h-1.5 rounded-full mr-2 align-middle"
                style={{ background: "var(--accent)", boxShadow: "0 0 8px var(--accent)" }} />}
              {label}
            </Link>
          );
        })}
        <span className="ml-auto" />
        <StatusDot meta={meta} />
        <LiveBadge />
        <span className="text-[11px] text-muted2 mono px-2 py-1 rounded-md border border-border">⌘K</span>
        <ThemeToggle />
      </div>
    </nav>
  );

  // ---- Tiroir MOBILE (sheet plein écran, style iOS) ----
  // Rendu via PORTAL dans <body> : le <nav> a un backdrop-filter, qui « piège » sinon les éléments
  // position:fixed (ils se positionnent par rapport au nav et non au viewport → tiroir écrasé en haut).
  const drawer = (
    <div className="md:hidden fixed inset-0 z-[60]" onClick={() => setOpen(false)}>
      <div className="absolute inset-0" style={{ background: "rgba(0,0,0,.5)" }} />
      <div onClick={(e) => e.stopPropagation()}
        className="drawer-panel absolute top-0 right-0 h-full w-[86%] max-w-[360px] flex flex-col border-l border-border"
        style={{ background: "var(--bg)", boxShadow: "-20px 0 60px rgba(0,0,0,.45)",
                 paddingTop: "env(safe-area-inset-top)" }}>
        <div className="flex items-center gap-2 px-4 h-14 border-b border-border shrink-0">
          {Brand}
          <button onClick={() => setOpen(false)} aria-label="Fermer le menu"
            className="ml-auto grid place-items-center w-10 h-10 rounded-[12px] border border-border text-fg active:scale-95 transition-transform"
            style={{ background: "var(--surface)" }}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <line x1="6" y1="6" x2="18" y2="18" /><line x1="18" y1="6" x2="6" y2="18" />
            </svg>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-3 py-3 space-y-5">
          <Link href="/accueil" onClick={() => setOpen(false)}
            className={`flex items-center gap-3 px-3 py-3 rounded-[14px] text-[15px] border transition-colors ${
              isActive("/accueil", path) ? "bg-surfaceAlt text-fg border-border2" : "text-fg border-border"}`}
            style={{ background: isActive("/accueil", path) ? undefined : "var(--surface)" }}>
            🏠 Accueil
          </Link>
          {GROUPS.map(([section, hrefs]) => (
            <div key={section}>
              <div className="px-2 mb-1.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-muted2">{section}</div>
              <div className="rounded-[14px] overflow-hidden border border-border" style={{ background: "var(--surface)" }}>
                {hrefs.map((href, idx) => {
                  const active = isActive(href, path);
                  return (
                    <Link key={href} href={href} onClick={() => setOpen(false)}
                      className={`flex items-center gap-2 px-4 py-3 text-[15px] transition-colors ${idx ? "border-t border-border" : ""} ${
                        active ? "text-fg" : "text-muted hover:text-fg"}`}
                      style={{ background: active ? "var(--surface2)" : undefined }}>
                      {active && <span className="inline-block w-1.5 h-1.5 rounded-full"
                        style={{ background: "var(--accent)", boxShadow: "0 0 8px var(--accent)" }} />}
                      <span className={active ? "font-medium" : ""}>{LABEL[href]}</span>
                      <span className="ml-auto text-muted2">›</span>
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </div>

        <div className="shrink-0 border-t border-border px-4 py-3 flex items-center gap-2 nav-safe-bottom">
          <StatusDot meta={meta} withLabel />
          <span className="ml-auto" />
          <LiveBadge />
        </div>
      </div>
    </div>
  );

  return (
    <>
      {bar}
      {mounted && open && createPortal(drawer, document.body)}
    </>
  );
}
