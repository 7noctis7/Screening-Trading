// Design tokens — SOURCE UNIQUE = app/globals.css (variables CSS thème-aware).
// Ce fichier ne DÉFINIT plus de couleurs : il RÉFÉRENCE les CSS vars pour éviter toute dérive
// (l'ancien objet hex figé « dark #0a0b0d / accent bleu » divergeait du thème réel cyan/teal).
// Règle : var(--pos)/var(--neg) = P&L UNIQUEMENT · var(--regime-on)/var(--regime-off) = régime (outline désaturé).
export const cssVar = (name: string) => `var(--${name})`;

export const color = {
  bg: "var(--bg)", surface: "var(--surface)", surfaceAlt: "var(--surface2)", border: "var(--border)",
  fg: "var(--fg)", muted: "var(--muted)", muted2: "var(--muted2)",
  accent: "var(--accent)", accent2: "var(--accent2)", warn: "var(--warn)",
  // P&L (fill plein, vif) — réservé aux valeurs de gain/perte
  pos: "var(--pos)", neg: "var(--neg)",
  // Régime (outline désaturé — jamais le traitement plein du P&L)
  regimeOn: "var(--regime-on)", regimeOff: "var(--regime-off)",
} as const;

export const radius = { sm: "8px", md: "12px", lg: "16px" };
export const space = (n: number) => `${n * 4}px`;
export const font = {
  sans: "-apple-system, BlinkMacSystemFont, 'SF Pro Text', Inter, system-ui, sans-serif",
  mono: "'SF Mono', 'JetBrains Mono', monospace",
} as const;

// Palette du cycle macro (sémantique propre au régime, distincte du P&L).
export const cyclePalette: Record<string, string> = {
  expansion: "var(--regime-on)", recovery: "var(--accent)", slowdown: "var(--warn)", recession: "var(--regime-off)",
};

// Rétro-compat : ancien objet `tokens` conservé en alias (aucun importeur aujourd'hui, mais sans surprise).
export const tokens = { color, radius, space, font } as const;
