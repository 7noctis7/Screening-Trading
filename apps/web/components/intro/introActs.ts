// Les actes de l'intro. Un acte = une fonction pure : reçoit le contexte, l'état, la
// progression LOCALE (0→1 dans l'acte) ; ne connaît ni le temps global ni les autres actes.

import { FACTEURS, GATES, TAPE_ROWS } from "./introConfig";
import {
  Palette, barre, clamp01, easeOut, etiquette, reticule, traitDegrade, verdict,
} from "./introDraw";

export type Geo = { w: number; h: number; petit: boolean };
export type Bougie = { x: number; o: number; c: number; h: number; l: number };
export type Noeud = { x: number; y: number; t: number; couche: number };
export type Particule = {
  x: number; y: number; vx: number; amp: number; ph: number; nx: number; ny: number;
};

/** ACTE 1 — INITIALISATION. Un point, puis les couches du système qui s'annoncent. */
export function acteInit(ctx: CanvasRenderingContext2D, g: Geo, p: number, pal: Palette) {
  const { w, h } = g;
  const pt = easeOut(clamp01(p * 3));
  ctx.save();
  ctx.globalAlpha = pt * 0.9;
  ctx.fillStyle = pal.accent;
  ctx.beginPath();
  ctx.arc(w / 2, h / 2, 1.6 + pt * 1.2, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
  traitDegrade(ctx, w / 2, h / 2, w * 0.42 * easeOut(clamp01((p - 0.2) * 1.6)),
               pal.accent, 0.5);
}

/** ACTE 2 — MARKET DATA. Carnet de profondeur, chandeliers en contour, tape qui défile. */
export function acteMarket(ctx: CanvasRenderingContext2D, g: Geo, p: number, pal: Palette,
                           bougies: Bougie[], carnet: { y: number; t: number; cote: 1 | -1 }[],
                           dt: number, parts: Particule[]) {
  const { w, h, petit } = g;
  const larg = petit ? w * 0.12 : w * 0.09;
  for (const n of carnet) {
    const a = clamp01((p - n.t * 0.3) * 2.4);
    if (a <= 0) continue;
    ctx.save();
    ctx.globalAlpha = a * 0.24;
    ctx.fillStyle = n.cote > 0 ? pal.pos : pal.neg;
    const y = h / 2 + n.cote * n.y * h * 0.34;
    const l = larg * (1 - n.y * 0.5) * easeOut(a);
    ctx.fillRect(w * 0.04, y, l, 1.5);
    ctx.fillRect(w * 0.96 - l, y, l, 1.5);
    ctx.restore();
  }
  etiquette(ctx, "BID", w * 0.04, h / 2 - h * 0.37, pal.muted, clamp01(p * 2) * 0.5);
  etiquette(ctx, "ASK", w * 0.96, h / 2 - h * 0.37, pal.muted, clamp01(p * 2) * 0.5, "right");

  const y0 = h * 0.60, amp = h * 0.17;
  const lb = (w * 0.66) / bougies.length * 0.42;
  ctx.save();
  ctx.lineWidth = 1;
  bougies.forEach((b, i) => {
    const a = clamp01((p - (i / bougies.length) * 0.55) * 2.6);
    if (a <= 0) return;
    const x = w * 0.17 + b.x * w * 0.66;
    const py = (u: number) => y0 - (u - 0.5) * amp * 2;
    ctx.globalAlpha = a * 0.34;
    ctx.strokeStyle = b.c >= b.o ? pal.pos : pal.neg;
    ctx.beginPath(); ctx.moveTo(x, py(b.h)); ctx.lineTo(x, py(b.l)); ctx.stroke();
    ctx.strokeRect(x - lb / 2, py(Math.max(b.o, b.c)), lb,
                   Math.max(1.5, Math.abs(py(b.o) - py(b.c))));
  });
  ctx.restore();

  ctx.save();
  ctx.globalAlpha = clamp01(p * 2) * 0.45;
  ctx.fillStyle = pal.accent2;
  for (const q of parts) {
    q.x += q.vx * dt;
    if (q.x > w) q.x -= w;
    q.ph += dt * 1.4;
    ctx.fillRect(q.x, q.y + Math.sin(q.ph) * q.amp * 0.3, 1.5, 1.5);
  }
  ctx.restore();
}

/** ACTE 3 — FEATURE ENGINE. Les prix se dissolvent en facteurs, un par un. */
export function acteFeatures(ctx: CanvasRenderingContext2D, g: Geo, p: number, pal: Palette) {
  const { w, h, petit } = g;
  const n = petit ? 6 : FACTEURS.length;
  const lw = petit ? w * 0.52 : w * 0.30;
  const x = w / 2 - lw / 2;
  const y0 = h / 2 - (n * 22) / 2;
  for (let i = 0; i < n; i++) {
    const a = clamp01((p - (i / n) * 0.6) * 3.4);
    if (a <= 0) continue;
    const y = y0 + i * 22;
    etiquette(ctx, FACTEURS[i], x, y - 3, pal.muted, a * 0.62);
    // Valeur pseudo-z-score, stable d'un run à l'autre : dérivée de l'indice, pas tirée.
    const v = 0.35 + 0.55 * Math.abs(Math.sin(i * 1.7));
    barre(ctx, x, y + 3, lw, v * easeOut(a), i % 3 === 1 ? pal.accent2 : pal.accent, a * 0.8);
  }
  etiquette(ctx, "Z-SCORE CROSS-SECTIONNEL · POINT-IN-TIME", w / 2, y0 + n * 22 + 22,
            pal.muted, clamp01((p - 0.6) * 3) * 0.5, "center");
}

/** ACTE 4 — MACHINE LEARNING. Bandes de CV purgée + embargo, puis le graphe s'allume. */
export function acteMl(ctx: CanvasRenderingContext2D, g: Geo, p: number, pal: Palette,
                       noeuds: Noeud[], liens: [number, number][]) {
  const { w, h } = g;
  // 1re moitié : les plis de validation, avec leurs trous d'embargo — la rigueur, montrée.
  const cv = clamp01(p * 2.2);
  const y = h * 0.26;
  const lw = w * 0.62, x0 = w / 2 - lw / 2;
  for (let k = 0; k < 5; k++) {
    const a = clamp01((cv - k * 0.14) * 3);
    if (a <= 0) continue;
    const yy = y + k * 9;
    ctx.save();
    ctx.globalAlpha = a * 0.20;
    ctx.fillStyle = pal.muted;
    ctx.fillRect(x0, yy, lw, 3);
    const tx = x0 + (k / 5) * lw;
    const tl = lw / 5;
    ctx.globalAlpha = a * 0.85;
    ctx.fillStyle = pal.accent;
    ctx.fillRect(tx + tl * 0.16, yy, tl * 0.68, 3);      // pli de test
    ctx.restore();
  }
  etiquette(ctx, "CV PURGÉE · EMBARGO", x0, y - 8, pal.muted, cv * 0.55);

  // 2de moitié : le graphe. Les liens naissent couche par couche, le signal passe une fois.
  const gr = clamp01((p - 0.35) * 1.6);
  if (gr <= 0) return;
  ctx.save();
  ctx.globalAlpha = gr * 0.26;
  ctx.strokeStyle = pal.accent;
  ctx.lineWidth = 1;
  for (const [i, j] of liens) {
    const a = noeuds[i], b = noeuds[j];
    const o = clamp01((gr - Math.min(a.t, b.t) * 0.6) * 2.2);
    if (o <= 0) continue;
    ctx.beginPath();
    ctx.moveTo(a.x, a.y);
    ctx.lineTo(a.x + (b.x - a.x) * o, a.y + (b.y - a.y) * o);
    ctx.stroke();
  }
  for (const nd of noeuds) {
    const on = clamp01((gr - nd.couche * 0.22) * 3);
    if (on <= 0) continue;
    ctx.globalAlpha = on * 0.9;
    ctx.fillStyle = pal.accent;
    ctx.beginPath();
    ctx.arc(nd.x, nd.y, 1.7 + on * 1.2, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.restore();
}

/** ACTE 5 — VALIDATION. Les quatre portes, avec leur verdict RÉEL. Trois échouent. */
export function acteGate(ctx: CanvasRenderingContext2D, g: Geo, p: number, pal: Palette) {
  const { w, h, petit } = g;
  const n = GATES.length;
  const lw = petit ? w * 0.78 : w * 0.56;
  const cw = lw / n;
  const x0 = w / 2 - lw / 2;
  const y = h / 2;
  for (let i = 0; i < n; i++) {
    const a = clamp01((p - i * 0.19) * 4.2);
    if (a <= 0) continue;
    const cx = x0 + cw * (i + 0.5);
    const gate = GATES[i];
    const couleur = gate.passe ? pal.accent2 : pal.neg;
    reticule(ctx, cx - cw * 0.36, y - 34, cw * 0.72, 68, pal.muted, a * 0.30);
    etiquette(ctx, `0${i + 1}`, cx, y - 20, pal.muted, a * 0.45, "center");
    etiquette(ctx, gate.cle, cx, y - 6, pal.fg, a * 0.75, "center");
    // Le verdict n'apparaît qu'après la métrique : on lit la mesure, PUIS la conclusion.
    const v = clamp01((a - 0.45) * 2.4);
    etiquette(ctx, gate.metrique, cx, y + 10, couleur, v * 0.8, "center");
    verdict(ctx, cx, y + 26, 5, gate.passe, couleur, v);
  }
  etiquette(ctx, "AUCUNE STRATÉGIE N'EST PUBLIÉE SANS CES QUATRE PORTES", w / 2, y + 62,
            pal.muted, clamp01((p - 0.7) * 3) * 0.55, "center");
}

/** ACTE 6 — RISK ENGINE. L'enveloppe d'exposition se resserre jusqu'à la cible. */
export function acteRisk(ctx: CanvasRenderingContext2D, g: Geo, p: number, pal: Palette) {
  const { w, h } = g;
  const y = h / 2;
  const e = easeOut(clamp01(p * 1.25));
  const large = h * 0.19 * (1 - e * 0.84);
  ctx.save();
  ctx.globalAlpha = 0.14 + 0.10 * (1 - e);
  ctx.fillStyle = e > 0.72 ? pal.accent2 : pal.neg;
  ctx.fillRect(w * 0.16, y - large, w * 0.68, large * 2);
  ctx.globalAlpha = 0.55;
  ctx.strokeStyle = e > 0.72 ? pal.accent2 : pal.neg;
  ctx.lineWidth = 1;
  for (const s of [-1, 1]) {
    ctx.beginPath();
    ctx.moveTo(w * 0.16, y + s * large);
    ctx.lineTo(w * 0.84, y + s * large);
    ctx.stroke();
  }
  ctx.restore();
  etiquette(ctx, "EXPOSITION BRUTE", w * 0.16, y - h * 0.24, pal.muted, clamp01(p * 3) * 0.55);
  etiquette(ctx, e > 0.72 ? "SOUS LE PLAFOND" : "AU-DESSUS DU PLAFOND",
            w * 0.84, y - h * 0.24, e > 0.72 ? pal.accent2 : pal.neg,
            clamp01(p * 3) * 0.7, "right");
  traitDegrade(ctx, w / 2, y, w * 0.34, pal.accent, 0.5);
}

/** ACTE 7 — EXECUTION. Des ordres traversent le portail : acceptés, réduits, refusés. */
export function acteExec(ctx: CanvasRenderingContext2D, g: Geo, p: number, pal: Palette) {
  const { w, h, petit } = g;
  const n = petit ? 6 : TAPE_ROWS;
  const y0 = h / 2 - (n * 16) / 2;
  const lw = petit ? w * 0.72 : w * 0.44;
  const x0 = w / 2 - lw / 2;
  for (let i = 0; i < n; i++) {
    const a = clamp01((p - (i / n) * 0.62) * 4);
    if (a <= 0) continue;
    const y = y0 + i * 16;
    // 1 refus et 1 réduction sur la série : la proportion qu'un portail sain produit.
    const etat = i === 2 ? "REFUSÉ" : i === 5 ? "RÉDUIT" : "OK";
    const c = etat === "REFUSÉ" ? pal.neg : etat === "RÉDUIT" ? pal.accent : pal.accent2;
    const prog = clamp01((a - 0.2) * 1.8);
    ctx.save();
    ctx.globalAlpha = a * 0.3;
    ctx.strokeStyle = pal.muted;
    ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(x0, y); ctx.lineTo(x0 + lw, y); ctx.stroke();
    ctx.globalAlpha = a * 0.9;
    ctx.strokeStyle = c;
    ctx.beginPath();
    ctx.moveTo(x0, y);
    ctx.lineTo(x0 + lw * (etat === "REFUSÉ" ? prog * 0.42 : etat === "RÉDUIT" ? prog * 0.68
                          : prog), y);
    ctx.stroke();
    ctx.restore();
    etiquette(ctx, etat, x0 + lw + 10, y + 3, c, clamp01((a - 0.5) * 3) * 0.7);
  }
  etiquette(ctx, "PAPER — AUCUN ORDRE RÉEL", w / 2, y0 + n * 16 + 24, pal.accent2,
            clamp01((p - 0.55) * 3) * 0.75, "center");
}
