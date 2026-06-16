// Design tokens — source unique (cf. vault/11_DESIGN_SYSTEM.md).
// Philosophie Apple : clarté, déférence (l'UI s'efface), sobriété. Vert/rouge = P&L UNIQUEMENT.
export const tokens = {
  color: {
    bg: "#0a0b0d", surface: "#141619", surfaceAlt: "#1b1e23", border: "#262a31",
    text: "#e6e8eb", textMuted: "#9aa1ab", accent: "#3b82f6",
    pnlPos: "#22c55e", pnlNeg: "#ef4444",
    riskOn: "#22c55e", riskOff: "#ef4444", neutral: "#9aa1ab",
  },
  radius: { sm: "8px", md: "12px", lg: "16px" },
  space: (n: number) => `${n * 4}px`,
  font: { sans: "-apple-system, BlinkMacSystemFont, 'SF Pro Text', Inter, system-ui, sans-serif",
          mono: "'SF Mono', 'JetBrains Mono', monospace" },
} as const;

export const cyclePalette: Record<string, string> = {
  expansion: "#22c55e", recovery: "#3b82f6", slowdown: "#f59e0b", recession: "#ef4444",
};
