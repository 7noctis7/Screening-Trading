"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS: [string, string][] = [
  ["/", "Dashboard"],
  ["/themes", "Thèmes de marché"],
  ["/ml", "Signaux ML"],
  ["/sentiment", "Sentiment & news"],
  ["/universe", "Univers"],
  ["/data", "Données"],
  ["/portfolio", "Portefeuille & Analyse"],
  ["/positions", "Positions"],
  ["/trades", "Trades"],
];

export function Nav() {
  const path = usePathname();
  return (
    <nav className="border-b border-border bg-surface/60 backdrop-blur sticky top-0 z-10">
      <div className="max-w-6xl mx-auto px-6 py-3 flex flex-wrap gap-2 items-center">
        <span className="text-sm font-semibold tracking-tight mr-3">Quant Terminal</span>
        {LINKS.map(([href, label]) => {
          const active = href === "/" ? path === "/" : path.startsWith(href);
          return (
            <Link key={href} href={href}
              className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
                active ? "bg-accent text-white" : "text-muted hover:text-fg hover:bg-surfaceAlt"
              }`}>
              {label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
