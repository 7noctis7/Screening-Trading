// Primitives de dessin de l'intro. Aucune règle métier : des formes, un contexte, une palette.
// Séparé de `introScene` pour que ni l'un ni l'autre ne dépasse 400 lignes.

export type Palette = {
  fg: string; accent: string; accent2: string; neg: string; pos: string; muted: string;
};

export const clamp01 = (t: number) => (t < 0 ? 0 : t > 1 ? 1 : t);
export const easeOut = (t: number) => 1 - Math.pow(1 - t, 3);
export const easeInOut = (t: number) =>
  (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
/** Progression LOCALE entre deux bornes : 0 avant `a`, 1 après `b`. */
export const seg = (t: number, a: number, b: number) => clamp01((t - a) / (b - a));
/** Fenêtre d'un acte : monte, tient, redescend. Évite les apparitions/disparitions sèches. */
export const fenetre = (t: number, a: number, b: number, marge = 0.12) => {
  const d = b - a;
  return clamp01((t - a) / (d * marge)) * clamp01((b - t) / (d * marge));
};

/** Lit la charte au lieu de la recopier : l'intro suit le thème courant. */
export function paletteDuTheme(): Palette {
  const cs = getComputedStyle(document.documentElement);
  const v = (n: string, repli: string) => (cs.getPropertyValue(n).trim() || repli);
  return {
    fg: v("--fg", "#eaf2f4"),
    accent: v("--accent", "#22d3ee"),
    accent2: v("--accent2", "#5eead4"),
    neg: v("--neg", "#f43f5e"),
    pos: v("--pos", "#22c55e"),
    muted: v("--muted2", "#637580"),
  };
}

/** PRNG semé : une intro reproductible se règle ; une intro aléatoire se subit. */
export function mulberry(a: number): () => number {
  return () => {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const MONO = '9px ui-monospace, "JetBrains Mono", "IBM Plex Mono", monospace';

/** Étiquette monospace. Toujours petite, toujours secondaire — elle situe, elle ne parle pas. */
export function etiquette(ctx: CanvasRenderingContext2D, txt: string, x: number, y: number,
                          couleur: string, alpha: number, align: CanvasTextAlign = "left") {
  if (alpha <= 0.01) return;
  ctx.save();
  ctx.font = MONO;
  ctx.textAlign = align;
  ctx.globalAlpha = alpha;
  ctx.fillStyle = couleur;
  ctx.letterSpacing = "0.14em";
  ctx.fillText(txt, x, y);
  ctx.restore();
}

/** Trait horizontal en dégradé, transparent aux deux bouts. La signature visuelle de l'intro. */
export function traitDegrade(ctx: CanvasRenderingContext2D, cx: number, y: number,
                             demi: number, couleur: string, alpha: number, ep = 1) {
  if (demi <= 0 || alpha <= 0.01) return;
  ctx.save();
  const g = ctx.createLinearGradient(cx - demi, 0, cx + demi, 0);
  g.addColorStop(0, "transparent");
  g.addColorStop(0.5, couleur);
  g.addColorStop(1, "transparent");
  ctx.strokeStyle = g;
  ctx.globalAlpha = alpha;
  ctx.lineWidth = ep;
  ctx.beginPath();
  ctx.moveTo(cx - demi, y);
  ctx.lineTo(cx + demi, y);
  ctx.stroke();
  ctx.restore();
}

/** Coche / croix, tracées au trait. Servent aux verdicts des quatre portes. */
export function verdict(ctx: CanvasRenderingContext2D, x: number, y: number, r: number,
                        passe: boolean, couleur: string, alpha: number) {
  if (alpha <= 0.01) return;
  ctx.save();
  ctx.globalAlpha = alpha;
  ctx.strokeStyle = couleur;
  ctx.lineWidth = 1.4;
  ctx.beginPath();
  if (passe) {
    ctx.moveTo(x - r, y);
    ctx.lineTo(x - r * 0.25, y + r * 0.7);
    ctx.lineTo(x + r, y - r * 0.7);
  } else {
    ctx.moveTo(x - r * 0.7, y - r * 0.7);
    ctx.lineTo(x + r * 0.7, y + r * 0.7);
    ctx.moveTo(x + r * 0.7, y - r * 0.7);
    ctx.lineTo(x - r * 0.7, y + r * 0.7);
  }
  ctx.stroke();
  ctx.restore();
}

/** Cadre fin, coins seuls — un réticule de terminal, pas une boîte. */
export function reticule(ctx: CanvasRenderingContext2D, x: number, y: number,
                         w: number, h: number, couleur: string, alpha: number) {
  if (alpha <= 0.01) return;
  const c = Math.min(12, w * 0.18, h * 0.3);
  ctx.save();
  ctx.globalAlpha = alpha;
  ctx.strokeStyle = couleur;
  ctx.lineWidth = 1;
  for (const [sx, sy] of [[1, 1], [-1, 1], [1, -1], [-1, -1]] as const) {
    const px = x + (sx < 0 ? w : 0);
    const py = y + (sy < 0 ? h : 0);
    ctx.beginPath();
    ctx.moveTo(px + sx * c, py);
    ctx.lineTo(px, py);
    ctx.lineTo(px, py + sy * c);
    ctx.stroke();
  }
  ctx.restore();
}

/** Barre horizontale, remplie à `v`. Sert aux facteurs et aux métriques de risque. */
export function barre(ctx: CanvasRenderingContext2D, x: number, y: number, w: number,
                      v: number, couleur: string, alpha: number, h = 2) {
  if (alpha <= 0.01) return;
  ctx.save();
  ctx.globalAlpha = alpha * 0.18;
  ctx.fillStyle = couleur;
  ctx.fillRect(x, y, w, h);
  ctx.globalAlpha = alpha;
  ctx.fillRect(x, y, w * clamp01(v), h);
  ctx.restore();
}
