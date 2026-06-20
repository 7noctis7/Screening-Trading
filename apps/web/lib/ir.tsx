"use client";
// Lien « Relations investisseurs » universel par actif : ouvre la page IR de la société.
// Source fiable pour TOUT ticker (recherche ciblée → 1er résultat = site IR officiel) ;
// pour la crypto, renvoie vers le site officiel du projet.

export function irUrl(ticker?: string, name?: string, assetClass?: string): string {
  const t = (ticker || "").trim();
  const n = (name || "").trim();
  const ac = (assetClass || "").toLowerCase();
  if (ac === "crypto") {
    const base = (n || t).replace(/[/:].*$/, "").trim();
    return `https://www.google.com/search?q=${encodeURIComponent(`${base} crypto site officiel`)}`;
  }
  if (ac === "forex" || ac === "commodity" || ac === "index") {
    return `https://www.google.com/search?q=${encodeURIComponent(`${n || t}`)}`;
  }
  // actions / ETF → relations investisseurs
  return `https://www.google.com/search?q=${encodeURIComponent(`${n || t} ${t} investor relations`)}`;
}

// Rend un ticker/nom cliquable vers sa page Relations investisseurs (nouvel onglet).
export function IR({ ticker, name, assetClass, className, children }: {
  ticker?: string; name?: string; assetClass?: string; className?: string; children?: React.ReactNode;
}) {
  return (
    <a href={irUrl(ticker, name, assetClass)} target="_blank" rel="noopener noreferrer"
      title={`Relations investisseurs — ${name || ticker}`}
      className={className ?? "text-accent hover:underline"}>
      {children ?? ticker} <span aria-hidden className="text-muted2 text-[10px]">↗</span>
    </a>
  );
}
