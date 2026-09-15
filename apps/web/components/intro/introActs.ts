// Les quatre battements. Un battement = une fonction pure : contexte, géométrie,
// progression LOCALE (0→1), palette. Aucun ne connaît le temps global ni les autres.
//
// LA TYPOGRAPHIE N'EST PAS ICI. Les grands chiffres sont rendus par le DOM (`IntroBeats`) :
// à cette taille, le texte canvas est plus flou, ignore la police du site et ne se
// sélectionne pas. Le canvas fait le mouvement, le DOM fait les mots.

import { GATES } from "./introConfig";
import { Palette, barre, clamp01, easeOut, etiquette, verdict } from "./introDraw";

export type Geo = { w: number; h: number; petit: boolean };
export type Noeud = { x: number; y: number; t: number; couche: number };
export type Particule = {
  x: number; y: number; vx: number; amp: number; ph: number; nx: number; ny: number;
};

/** BATTEMENT 1 — ÉCHELLE. Les instruments affluent, puis se rangent en réseau. */
export function beatEchelle(ctx: CanvasRenderingContext2D, g: Geo, p: number, pal: Palette,
                            parts: Particule[], noeuds: Noeud[], liens: [number, number][],
                            dt: number) {
  const { w, h } = g;
  const cy = h * 0.5;

  // Le flux. Il se resserre vers l'axe à mesure que le battement avance : la dispersion
  // devient structure, sans qu'aucune particule ne saute.
  const serre = easeOut(clamp01((p - 0.35) * 1.8));
  ctx.save();
  ctx.globalAlpha = clamp01(p * 4) * (1 - clamp01((p - 0.82) * 5)) * 0.5;
  ctx.fillStyle = pal.accent2;
  for (const q of parts) {
    q.x += q.vx * dt;
    if (q.x > w) q.x -= w;
    q.ph += dt * 1.5;
    const yLibre = q.y + Math.sin(q.ph) * q.amp * 0.3;
    ctx.fillRect(q.x, yLibre + (cy - yLibre) * serre * 0.55, 1.5, 1.5);
  }
  ctx.restore();

  // Le réseau n'apparaît qu'en seconde moitié : il CONCLUT le battement, il ne l'encombre pas.
  const gr = clamp01((p - 0.5) * 2.6);
  if (gr <= 0) return;
  ctx.save();
  ctx.globalAlpha = gr * (1 - clamp01((p - 0.88) * 8)) * 0.22;
  ctx.strokeStyle = pal.accent;
  ctx.lineWidth = 1;
  for (const [i, j] of liens) {
    const a = noeuds[i], b = noeuds[j];
    const o = clamp01((gr - Math.min(a.t, b.t) * 0.5) * 2.4);
    if (o <= 0) continue;
    ctx.beginPath();
    ctx.moveTo(a.x, a.y);
    ctx.lineTo(a.x + (b.x - a.x) * o, a.y + (b.y - a.y) * o);
    ctx.stroke();
  }
  for (const nd of noeuds) {
    const on = clamp01((gr - nd.couche * 0.18) * 3.2);
    if (on <= 0) continue;
    ctx.globalAlpha = on * (1 - clamp01((p - 0.88) * 8)) * 0.8;
    ctx.fillStyle = pal.accent;
    ctx.beginPath();
    ctx.arc(nd.x, nd.y, 1.6 + on, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.restore();
}

/** BATTEMENT 2 — REJET. Les quatre portes tombent l'une après l'autre. Trois échouent. */
export function beatRejet(ctx: CanvasRenderingContext2D, g: Geo, p: number, pal: Palette) {
  const { w, h, petit } = g;
  const n = GATES.length;
  const lw = petit ? w * 0.82 : w * 0.52;
  const cw = lw / n;
  const x0 = w / 2 - lw / 2;
  const y = h * 0.64;

  for (let i = 0; i < n; i++) {
    // Cadence serrée : quatre verdicts en ~1,2 s, c'est ce qui rend le battement nerveux.
    const a = clamp01((p - 0.10 - i * 0.16) * 6);
    if (a <= 0) continue;
    const cx = x0 + cw * (i + 0.5);
    const gate = GATES[i];
    const c = gate.passe ? pal.accent2 : pal.neg;

    // Trait vertical : il TOMBE d'en haut, puis le verdict se pose. L'ordre porte le sens.
    ctx.save();
    ctx.globalAlpha = a * 0.5;
    ctx.strokeStyle = c;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(cx, y - 34);
    ctx.lineTo(cx, y - 34 + 24 * easeOut(a));
    ctx.stroke();
    ctx.restore();

    etiquette(ctx, gate.cle, cx, y, pal.fg, a * 0.8, "center");
    const v = clamp01((a - 0.4) * 2.6);
    etiquette(ctx, gate.metrique, cx, y + 15, c, v * 0.85, "center");
    verdict(ctx, cx, y + 31, 5, gate.passe, c, v);
  }
}

/** BATTEMENT 3 — RÉSULTAT. Deux barres de drawdown. Celle du marché part la première. */
export function beatResultat(ctx: CanvasRenderingContext2D, g: Geo, p: number, pal: Palette) {
  const { w, h, petit } = g;
  const lw = petit ? w * 0.74 : w * 0.46;
  const x0 = w / 2 - lw / 2;
  const y = h * 0.64;

  // Le marché d'abord, plus bas, plus long : on VOIT l'écart avant de lire le chiffre.
  const marche = easeOut(clamp01((p - 0.08) * 2.2));
  const nous = easeOut(clamp01((p - 0.30) * 2.2));

  etiquette(ctx, "MARCHÉ ÉQUIPONDÉRÉ", x0, y - 8, pal.muted, marche * 0.6);
  barre(ctx, x0, y, lw, marche * (23 / 23), pal.neg, marche * 0.75, 3);
  etiquette(ctx, "−23 %", x0 + lw + 10, y + 4, pal.neg, clamp01((marche - 0.7) * 4) * 0.85);

  etiquette(ctx, "QUANT TERMINAL", x0, y + 26, pal.muted, nous * 0.6);
  barre(ctx, x0, y + 34, lw, nous * (9 / 23), pal.accent2, nous * 0.95, 3);
  etiquette(ctx, "−9 %", x0 + lw * (9 / 23) + 10, y + 38, pal.accent2,
            clamp01((nous - 0.7) * 4) * 0.95);

  // Le repère du plafond : sans lui, deux barres ne comparent rien.
  ctx.save();
  ctx.globalAlpha = clamp01((p - 0.5) * 3) * 0.28;
  ctx.strokeStyle = pal.muted;
  ctx.lineWidth = 1;
  ctx.setLineDash([2, 4]);
  ctx.beginPath();
  ctx.moveTo(x0 + lw * (9 / 23), y - 14);
  ctx.lineTo(x0 + lw * (9 / 23), y + 48);
  ctx.stroke();
  ctx.restore();
}

/** BATTEMENT 4 — RÉVÉLATION. Le canvas s'efface : la place revient au nom. */
export function beatReveal(ctx: CanvasRenderingContext2D, g: Geo, p: number, pal: Palette) {
  const { w, h } = g;
  const r = 1 - easeOut(clamp01(p * 1.5));
  ctx.save();
  const demi = w * 0.36 * r;
  if (demi > 1) {
    const gr = ctx.createLinearGradient(w / 2 - demi, 0, w / 2 + demi, 0);
    gr.addColorStop(0, "transparent");
    gr.addColorStop(0.5, pal.accent);
    gr.addColorStop(1, "transparent");
    ctx.strokeStyle = gr;
    ctx.globalAlpha = 0.45 + 0.55 * (1 - r);
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(w / 2 - demi, h / 2);
    ctx.lineTo(w / 2 + demi, h / 2);
    ctx.stroke();
  }
  ctx.restore();
}
