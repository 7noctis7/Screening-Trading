// Orchestration de l'intro : état de la scène, choix de l'acte, décor commun.
// Les primitives vivent dans `introDraw`, les actes dans `introActs` — trois fichiers
// courts plutôt qu'un seul de sept cents lignes.

import {
  ACTS, MAX_DPR, NODE_COUNT, NODE_COUNT_MOBILE, PARTICLE_COUNT, PARTICLE_COUNT_MOBILE,
  PHASES, TAPE_ROWS,
} from "./introConfig";
import {
  Bougie, Geo, Noeud, Particule, acteExec, acteFeatures, acteGate, acteInit, acteMarket,
  acteMl, acteRisk,
} from "./introActs";
import { Palette, clamp01, etiquette, mulberry, seg, traitDegrade } from "./introDraw";

export type { Palette } from "./introDraw";
export { paletteDuTheme } from "./introDraw";

export class SceneIntro {
  private p: Particule[] = [];
  private n: Noeud[] = [];
  private liens: [number, number][] = [];
  private bougies: Bougie[] = [];
  private carnet: { y: number; t: number; cote: 1 | -1 }[] = [];
  private g: Geo = { w: 0, h: 0, petit: false };
  private dpr = 1;

  constructor(private ctx: CanvasRenderingContext2D, petit: boolean,
              private modeste: boolean) {
    this.g.petit = petit;
  }

  /** (Re)dimensionne et régénère. Idempotent : appelable à chaque redimensionnement. */
  dimensionner(w: number, h: number): void {
    this.dpr = Math.min(MAX_DPR, window.devicePixelRatio || 1, this.modeste ? 1.5 : MAX_DPR);
    this.g = { w, h, petit: this.g.petit };
    const cv = this.ctx.canvas;
    cv.width = Math.round(w * this.dpr);
    cv.height = Math.round(h * this.dpr);
    this.ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    this.semer();
  }

  private semer(): void {
    const { w, h, petit } = this.g;
    let nb = petit ? PARTICLE_COUNT_MOBILE : PARTICLE_COUNT;
    if (this.modeste) nb = Math.round(nb * 0.55);
    const nn = petit ? NODE_COUNT_MOBILE : NODE_COUNT;
    const rnd = mulberry(20260914);

    this.n = Array.from({ length: nn }, (_, i) => {
      const couche = i % 3;
      const parCouche = Math.ceil(nn / 3);
      const k = Math.floor(i / 3);
      return {
        x: w * (0.30 + couche * 0.20) + (rnd() - 0.5) * w * 0.035,
        y: h * (0.52 + ((k + 0.5) / parCouche - 0.5) * 0.34) + (rnd() - 0.5) * h * 0.03,
        t: couche * 0.3 + rnd() * 0.3,
        couche,
      };
    });
    this.liens = [];
    for (let i = 0; i < this.n.length; i++) {
      for (let j = i + 1; j < this.n.length; j++) {
        if (Math.hypot(this.n[i].x - this.n[j].x, this.n[i].y - this.n[j].y) < w * 0.17) {
          this.liens.push([i, j]);
        }
      }
    }

    const nb2 = petit ? 20 : 44;
    this.bougies = Array.from({ length: nb2 }, (_, i) => {
      const o = 0.5 + (rnd() - 0.5) * 0.3;
      const c = o + (rnd() - 0.5) * 0.22;
      return { x: (i + 0.5) / nb2, o, c,
               h: Math.max(o, c) + rnd() * 0.09, l: Math.min(o, c) - rnd() * 0.09 };
    });

    this.carnet = [];
    for (let i = 0; i < TAPE_ROWS; i++) {
      const f = (i + 1) / TAPE_ROWS;
      for (const cote of [1, -1] as const) this.carnet.push({ y: f, t: f, cote });
    }

    this.p = Array.from({ length: nb }, () => ({
      x: rnd() * w, y: h * (0.22 + rnd() * 0.56),
      vx: 16 + rnd() * 42, amp: 4 + rnd() * 22, ph: rnd() * Math.PI * 2,
      nx: 0, ny: 0,
    }));
  }

  /** Acte courant + progression LOCALE dans cet acte. */
  private acte(t: number): { cle: string; p: number; i: number } {
    let debut = 0;
    for (let i = 0; i < ACTS.length; i++) {
      if (t < ACTS[i].fin || i === ACTS.length - 1) {
        return { cle: ACTS[i].cle, p: clamp01((t - debut) / (ACTS[i].fin - debut)), i };
      }
      debut = ACTS[i].fin;
    }
    return { cle: "reveal", p: 1, i: ACTS.length - 1 };
  }

  /** Peint l'image de `t` ∈ [0,1]. `dt` en secondes, borné par l'appelant. */
  peindre(t: number, dt: number, pal: Palette): void {
    const { ctx } = this;
    const { w, h } = this.g;
    ctx.clearRect(0, 0, w, h);
    this.decor(t, pal);

    const a = this.acte(t);
    switch (a.cle) {
      case "init": acteInit(ctx, this.g, a.p, pal); break;
      case "market":
        acteMarket(ctx, this.g, a.p, pal, this.bougies, this.carnet, dt, this.p); break;
      case "features": acteFeatures(ctx, this.g, a.p, pal); break;
      case "ml": acteMl(ctx, this.g, a.p, pal, this.n, this.liens); break;
      case "gate": acteGate(ctx, this.g, a.p, pal); break;
      case "risk": acteRisk(ctx, this.g, a.p, pal); break;
      case "exec": acteExec(ctx, this.g, a.p, pal); break;
      default: this.convergence(a.p, pal); break;
    }
    this.titreActe(a.i, a.p, pal);
  }

  /** Grille et ligne centrale : le décor persistant, à la limite du visible. */
  private decor(t: number, pal: Palette): void {
    const { ctx } = this;
    const { w, h, petit } = this.g;
    const aG = seg(t, 0.02, PHASES.market) * (1 - seg(t, PHASES.exec, 1)) * 0.045;
    if (aG > 0.002) {
      ctx.save();
      ctx.strokeStyle = pal.fg;
      ctx.globalAlpha = aG;
      ctx.lineWidth = 1;
      const pas = petit ? 56 : 74;
      ctx.beginPath();
      for (let x = (w / 2) % pas; x < w; x += pas) { ctx.moveTo(x, 0); ctx.lineTo(x, h); }
      for (let y = (h / 2) % pas; y < h; y += pas) { ctx.moveTo(0, y); ctx.lineTo(w, y); }
      ctx.stroke();
      ctx.restore();
    }
    // La ligne centrale ne vit que pendant les actes qui ne l'utilisent pas eux-mêmes :
    // deux traits superposés à la même hauteur se liraient comme un défaut de rendu.
    if (t > PHASES.init && t < PHASES.features) {
      traitDegrade(ctx, w / 2, h / 2, w * 0.42, pal.accent, 0.22);
    }
  }

  /** Titre de l'acte, en bas au centre. Apparaît, tient, s'efface — jamais de coupure. */
  private titreActe(i: number, p: number, pal: Palette): void {
    const acte = ACTS[i];
    if (!acte.titre) return;
    const a = clamp01(p * 6) * clamp01((1 - p) * 6);
    const { w, h } = this.g;
    etiquette(this.ctx, acte.titre, w / 2, h - 58, pal.fg, a * 0.85, "center");
    etiquette(this.ctx, acte.sous, w / 2, h - 42, pal.muted, a * 0.5, "center");
  }

  /** ACTE 8 — tout se rétracte vers le centre. Le nom de marque est rendu par le DOM. */
  private convergence(p: number, pal: Palette): void {
    const { w, h } = this.g;
    const r = 1 - clamp01(p * 1.4);
    traitDegrade(this.ctx, w / 2, h / 2, w * 0.42 * r, pal.accent, 0.5 + 0.5 * (1 - r));
  }
}
