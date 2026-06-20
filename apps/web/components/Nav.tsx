"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
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

function SystemStatus({ meta }: { meta: any }) {
  if (!meta) return null;
  const synth = meta.data_synthetic;
  const audit = meta.audit;
  // vert = réelles & saines · ambre = anomalies non critiques · rouge = critiques/synthétique
  const tone = synth ? "#ef4444" : (audit && !audit.ok ? "#f59e0b" : "#22c55e");
  const label = synth ? "synthétique"
    : audit ? (audit.ok ? "données auditées" : `${audit.counts?.critical ?? 0} critique(s)`)
    : "données réelles";
  const title = synth ? "Données synthétiques — démo UI uniquement."
    : audit ? `Audit PwC : ${audit.counts?.critical ?? 0} critiques · ${audit.counts?.major ?? 0} majeures · ${audit.counts?.warning ?? 0} avertissements`
    : "Données réelles (audit non calculé).";
  return (
    <Link href="/data" title={title}
      className="hidden md:flex items-center gap-1.5 text-[11px] text-muted2 mono px-2 py-1 rounded-md border border-border hover:text-fg transition-colors">
      <span className="inline-block w-1.5 h-1.5 rounded-full" style={{ background: tone, boxShadow: `0 0 8px ${tone}` }} />
      {label}
    </Link>
  );
}

export function Nav() {
  const path = usePathname();
  const { data: meta } = useMeta();
  return (
    <nav className="sticky top-0 z-20 border-b border-border"
      style={{ background: "rgba(10,12,16,.72)", backdropFilter: "saturate(160%) blur(14px)" }}>
      {meta?.data_synthetic && (
        <div className="px-6 py-1 text-[11px] text-center"
          style={{ background: "color-mix(in srgb, var(--warn) 22%, transparent)", color: "var(--warn)" }}>
          ⚠️ Données factices (synthétiques) — démo UI uniquement, ne pas décider. Branche <code className="mono">QUANT_PRICE_DB</code>.
        </div>
      )}
      <div className="max-w-6xl mx-auto px-6 py-3 flex flex-wrap gap-1.5 items-center">
        <span className="flex items-center gap-2 text-sm font-semibold tracking-tight mr-3">
          <span className="inline-block w-[18px] h-[18px] rounded-md"
            style={{ background: "linear-gradient(135deg,#22d3ee,#5eead4 55%,#22c55e)", boxShadow: "0 0 0 1px rgba(255,255,255,.08),0 4px 16px rgba(34,211,238,.5)" }} />
          Quant Terminal
        </span>
        {LINKS.map(([href, label]) => {
          const active = href === "/" ? path === "/" : path.startsWith(href);
          return (
            <Link key={href} href={href}
              className={`px-3 py-1.5 rounded-[10px] text-sm transition-all duration-150 border ${
                active
                  ? "bg-surfaceAlt text-fg border-border2 shadow"
                  : "text-muted hover:text-fg hover:bg-surfaceAlt border-transparent"
              }`}>
              {active && <span className="inline-block w-1.5 h-1.5 rounded-full mr-2 align-middle"
                style={{ background: "var(--accent)", boxShadow: "0 0 8px var(--accent)" }} />}
              {label}
            </Link>
          );
        })}
        <span className="ml-auto" />
        <SystemStatus meta={meta} />
        <LiveBadge />
        <span className="hidden md:inline text-[11px] text-muted2 mono px-2 py-1 rounded-md border border-border">⌘K</span>
        <ThemeToggle />
      </div>
    </nav>
  );
}
