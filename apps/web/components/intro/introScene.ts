// Orchestration de l'intro : état de la scène, choix de l'acte, décor commun.
// Les primitives vivent dans `introDraw`, les actes dans `introActs` — trois fichiers
// courts plutôt qu'un seul de sept cents lignes.

import {
  BEATS, MAX_DPR, NODE_COUNT, NODE_COUNT_MOBILE, PARTICLE_COUNT, PARTICLE_COUNT_MOBILE,
} from "./introConfig";
import {
  Geo, Noeud, Particule, beatEchelle, beatPreuve, beatRejet, beatReveal,
} from "./introActs";
import { Palette, clamp01, mulberry, seg } from "./introDraw";

export type { Palette } from "./introDraw";
export { paletteDuTheme } from "./introDraw";

export class SceneIntro {
  private p: Particule[] = [];
  private n: Noeud[] = [];
  private liens: [number, number][] = [];
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

    this.p = Array.from({ length: nb }, () => ({
      x: rnd() * w, y: h * (0.22 + rnd() * 0.56),
      vx: 16 + rnd() * 42, amp: 4 + rnd() * 22, ph: rnd() * Math.PI * 2,
      nx: 0, ny: 0,
    }));
  }

  /** Battement courant + progression LOCALE dedans. Exposé : le DOM s'en sert aussi. */
  battement(t: number): { cle: string; p: number; i: number } {
    let debut = 0;
    for (let i = 0; i < BEATS.length; i++) {
      if (t < BEATS[i].fin || i === BEATS.length - 1) {
        return { cle: BEATS[i].cle, p: clamp01((t - debut) / (BEATS[i].fin - debut)), i };
      }
      debut = BEATS[i].fin;
    }
    return { cle: "reveal", p: 1, i: BEATS.length - 1 };
  }

  /** Peint l'image de `t` ∈ [0,1]. `dt` en secondes, borné par l'appelant. */
  peindre(t: number, dt: number, pal: Palette): void {
    const { ctx } = this;
    const { w, h } = this.g;
    ctx.clearRect(0, 0, w, h);
    this.decor(t, pal);

    const b = this.battement(t);
    // CHAQUE clé de `BEATS` doit être citée. Le `switch` d'origine connaissait encore une
    // clé `resultat` supprimée depuis, et laissait les SEPT battements ajoutés tomber dans
    // `default` — l'acte de révélation, un simple trait. Les deux tiers de l'intro se
    // peignaient donc à vide, sans qu'aucune erreur ne soit levée : un `switch` qui a un
    // `default` ne se plaint jamais d'une clé qu'il ignore.
    switch (b.cle) {
      case "echelle":
        beatEchelle(ctx, this.g, b.p, pal, this.p, this.n, this.liens, dt); break;
      case "rejet": beatRejet(ctx, this.g, b.p, pal); break;
      case "p_ytd": case "p_3a": case "p_5a": case "p_10a": case "p_tout": case "trades":
        beatPreuve(ctx, this.g, b.p, pal, this.p, dt); break;
      case "reveal": beatReveal(ctx, this.g, b.p, pal); break;
      default: beatReveal(ctx, this.g, b.p, pal); break;
    }
  }

  /** La grille : profondeur à la limite du visible, effacée avant la révélation. */
  private decor(t: number, pal: Palette): void {
    const { ctx } = this;
    const { w, h, petit } = this.g;
    const a = seg(t, 0.03, 0.18) * (1 - seg(t, 0.62, 0.82)) * 0.05;
    if (a <= 0.002) return;
    ctx.save();
    ctx.strokeStyle = pal.fg;
    ctx.globalAlpha = a;
    ctx.lineWidth = 1;
    const pas = petit ? 56 : 74;
    ctx.beginPath();
    for (let x = (w / 2) % pas; x < w; x += pas) { ctx.moveTo(x, 0); ctx.lineTo(x, h); }
    for (let y = (h / 2) % pas; y < h; y += pas) { ctx.moveTo(0, y); ctx.lineTo(w, y); }
    ctx.stroke();
    ctx.restore();
  }
}
