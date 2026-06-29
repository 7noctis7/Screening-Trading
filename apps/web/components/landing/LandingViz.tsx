"use client";
// Mini-visuels SVG premium (épurés, sombres, glassmorphism) pour la landing.
// Abstraits et déterministes — illustrent la méthode sans prétendre à des données réelles.
import type { ReactNode } from "react";

const T = "#5eead4", R = "#f43f5e", G = "#8aa0a9";

function Frame({ children }: { children: ReactNode }) {
  return (
    <div style={{
      borderRadius: 14, border: "1px solid rgba(94,234,212,.14)",
      background: "rgba(10,17,24,.5)", padding: "10px 12px",
      backdropFilter: "blur(6px)", WebkitBackdropFilter: "blur(6px)",
    }}>
      <svg viewBox="0 0 120 56" width="100%" height="64" preserveAspectRatio="none"
        aria-hidden="true">{children}</svg>
    </div>
  );
}

// 01 — Placebo : cloche gaussienne, queue de rejet (hasard) en rouge.
export const VizPlacebo = () => (
  <Frame>
    <path d="M4,52 C34,52 40,6 60,6 C80,6 86,52 116,52" fill="none" stroke={T} strokeWidth="1.6" />
    <path d="M98,52 C103,34 110,52 116,52 Z" fill={R} opacity="0.55" />
    <line x1="98" y1="6" x2="98" y2="52" stroke={R} strokeWidth="1" strokeDasharray="3 3" />
  </Frame>
);

// 02 — DSR : Sharpe brut qui monte, puis s'effondre après déflation data-mining.
export const VizDsr = () => (
  <Frame>
    <polyline points="4,46 26,30 48,16 66,10" fill="none" stroke={T} strokeWidth="1.6" />
    <polyline points="66,10 86,30 104,48 116,51" fill="none" stroke={R} strokeWidth="1.6"
      strokeDasharray="4 3" />
    <circle cx="66" cy="10" r="2.4" fill={T} />
  </Frame>
);

// 03 — PBO : matrice CSCV in/out-of-sample (cases plus claires = rang OOS).
export const VizPbo = () => {
  const op = [0.2, 0.5, 0.15, 0.7, 0.35, 0.6, 0.8, 0.25, 0.45, 0.3, 0.65, 0.5,
    0.55, 0.2, 0.75, 0.4, 0.3, 0.6, 0.25, 0.7];
  return (
    <Frame>
      {op.map((o, i) => (
        <rect key={i} x={6 + (i % 5) * 22} y={6 + Math.floor(i / 5) * 12} width="18"
          height="9" rx="1.5" fill={T} opacity={o} />
      ))}
    </Frame>
  );
};

// 04 — Sabotage : spikes de latence injectée (rouges) sur le flux d'exécution.
export const VizSabotage = () => {
  const h = [14, 8, 30, 10, 6, 38, 12, 9, 26, 7, 44, 11, 16, 8, 34];
  return (
    <Frame>
      {h.map((v, i) => (
        <rect key={i} x={5 + i * 7.6} y={52 - v} width="3.4" height={v} rx="1"
          fill={v > 24 ? R : T} opacity={v > 24 ? 0.8 : 0.5} />
      ))}
    </Frame>
  );
};

// Manifeste — comparaison de drawdown : −9 % (teal) vs −23 % (rouge).
export const VizDrawdown = () => (
  <div style={{
    borderRadius: 16, border: "1px solid rgba(94,234,212,.14)",
    background: "rgba(10,17,24,.5)", padding: "14px 16px",
    backdropFilter: "blur(6px)", WebkitBackdropFilter: "blur(6px)",
  }}>
    <svg viewBox="0 0 240 90" width="100%" height="120" aria-hidden="true">
      <line x1="0" y1="10" x2="240" y2="10" stroke={G} strokeWidth="0.5" opacity="0.3" />
      <path d="M0,10 C50,10 70,32 110,32 C150,32 175,16 240,14" fill="none" stroke={T}
        strokeWidth="2" />
      <path d="M0,10 C45,10 65,76 120,76 C170,76 200,40 240,30" fill="none" stroke={R}
        strokeWidth="2" />
      <text x="244" y="16" fill={T} fontSize="9" fontFamily="ui-monospace">−9%</text>
      <text x="244" y="33" fill={R} fontSize="9" fontFamily="ui-monospace">−23%</text>
    </svg>
  </div>
);

// Card Screening — barres de z-score (au-dessus/au-dessous de la médiane).
export const VizScreen = () => {
  const z = [0.6, -0.3, 0.9, 0.2, -0.7, 0.4, 0.8, -0.2];
  return (
    <Frame>
      <line x1="0" y1="28" x2="120" y2="28" stroke={G} strokeWidth="0.5" opacity="0.4" />
      {z.map((v, i) => (
        <rect key={i} x={6 + i * 14} y={v >= 0 ? 28 - v * 22 : 28} width="8"
          height={Math.abs(v) * 22} rx="1.5" fill={v >= 0 ? T : R} opacity="0.7" />
      ))}
    </Frame>
  );
};

// Card Risque — arbre logique du kill-switch (vol-target → ok / coupe).
export const VizRisk = () => (
  <Frame>
    <circle cx="20" cy="28" r="4" fill={T} />
    <line x1="24" y1="28" x2="52" y2="14" stroke={G} strokeWidth="1" />
    <line x1="24" y1="28" x2="52" y2="42" stroke={G} strokeWidth="1" />
    <circle cx="56" cy="14" r="3.5" fill={T} opacity="0.7" />
    <circle cx="56" cy="42" r="3.5" fill={R} />
    <line x1="60" y1="42" x2="90" y2="42" stroke={R} strokeWidth="1" strokeDasharray="3 3" />
    <text x="94" y="45" fill={R} fontSize="8" fontFamily="ui-monospace">cut</text>
    <text x="94" y="17" fill={T} fontSize="8" fontFamily="ui-monospace">ok</text>
  </Frame>
);

// Card Paper — ordre fictif routé vers le bac à sable (sandbox).
export const VizPaper = () => (
  <Frame>
    <rect x="6" y="22" width="26" height="12" rx="2" fill="none" stroke={T} strokeWidth="1" />
    <text x="9" y="31" fill={T} fontSize="7" fontFamily="ui-monospace">ordre</text>
    <line x1="32" y1="28" x2="78" y2="28" stroke={T} strokeWidth="1.2" strokeDasharray="4 3" />
    <polygon points="78,24 86,28 78,32" fill={T} />
    <rect x="88" y="20" width="28" height="16" rx="2" fill={T} opacity="0.12"
      stroke={T} strokeWidth="1" />
    <text x="91" y="31" fill={T} fontSize="7" fontFamily="ui-monospace">paper</text>
  </Frame>
);
