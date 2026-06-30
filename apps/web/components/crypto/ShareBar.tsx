"use client";
// M5 — boucle de croissance « encapsulation » (style TradingView), 0 backend, on-brand.
// Partage l'état du cockpit (humeur + score) sur X/Farcaster + lien + snippet d'embed iframe.
// Aucune donnée inventée : le texte reflète le sentiment live affiché. Aucun conseil.
import { useState } from "react";

const URL = "https://7noctis7.github.io/Screening-Trading/crypto/";

export function ShareBar({ sentiment }: { sentiment: any }) {
  const [copied, setCopied] = useState<string | null>(null);
  const s = sentiment?.available
    ? `Cockpit crypto — humeur ${sentiment.label} (${sentiment.score}/100). `
      + "Validé par le gate Placebo→DSR→PBO→Sabotage. Aucun conseil."
    : "Cockpit crypto Quant Terminal — données gratuites, gate à 4 étages. Aucun conseil.";
  const x = `https://twitter.com/intent/tweet?text=${encodeURIComponent(s)}`
    + `&url=${encodeURIComponent(URL)}`;
  const fc = `https://warpcast.com/~/compose?text=${encodeURIComponent(s + " " + URL)}`;
  const embed = `<iframe src="${URL}?embed=1" width="420" height="540" `
    + `style="border:0;border-radius:16px" title="Quant Terminal — Cockpit crypto"></iframe>`;

  const copy = (val: string, key: string) => {
    navigator.clipboard?.writeText(val).then(() => {
      setCopied(key);
      setTimeout(() => setCopied(null), 1600);
    }, () => setCopied(null));
  };
  const btn = "text-xs px-2.5 py-1.5 rounded-lg border border-border hover:border-border2 "
    + "hover:text-fg transition-colors";

  return (
    <div className="flex flex-wrap items-center gap-2">
      <a href={x} target="_blank" rel="noopener noreferrer" className={btn}>Partager sur X</a>
      <a href={fc} target="_blank" rel="noopener noreferrer" className={btn}>Farcaster</a>
      <button onClick={() => copy(URL, "lien")} className={btn}>
        {copied === "lien" ? "Lien copié ✓" : "Copier le lien"}</button>
      <button onClick={() => copy(embed, "embed")} className={btn}>
        {copied === "embed" ? "Embed copié ✓" : "Intégrer (iframe)"}</button>
    </div>
  );
}
