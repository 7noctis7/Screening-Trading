"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ThemeToggle } from "@/components/ThemeToggle";
import { LiveBadge } from "@/components/LiveBadge";

const LINKS: [string, string][] = [
  ["/", "Dashboard"],
  ["/themes", "Thèmes de marché"],
  ["/ml", "Signaux ML"],
  ["/fundamentals", "Fondamentaux"],
  ["/sentiment", "Sentiment & news"],
  ["/universe", "Univers"],
  ["/data", "Données"],
  ["/portfolio", "Portefeuille & Analyse"],
  ["/risk", "Risque"],
  ["/positions", "Positions"],
  ["/trades", "Trades"],
];

export function Nav() {
  const path = usePathname();
  return (
    <nav className="sticky top-0 z-20 border-b border-border"
      style={{ background: "rgba(10,12,16,.72)", backdropFilter: "saturate(160%) blur(14px)" }}>
      <div className="max-w-6xl mx-auto px-6 py-3 flex flex-wrap gap-1.5 items-center">
        <span className="flex items-center gap-2 text-sm font-semibold tracking-tight mr-3">
          <span className="inline-block w-[18px] h-[18px] rounded-md"
            style={{ background: "linear-gradient(135deg,#3b82f6,#22d3ee)", boxShadow: "0 0 0 1px rgba(255,255,255,.08),0 4px 14px rgba(59,130,246,.45)" }} />
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
        <LiveBadge />
        <span className="hidden md:inline text-[11px] text-muted2 mono px-2 py-1 rounded-md border border-border">⌘K</span>
        <ThemeToggle />
      </div>
    </nav>
  );
}
