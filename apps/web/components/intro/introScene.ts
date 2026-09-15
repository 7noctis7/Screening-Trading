// Rendu de l'intro — math et peinture, sans React ni DOM au-delà du canvas.
//
// Un seul canvas 2D, une seule boucle rAF. Pas de Three.js : la scène est faite de points,
// de segments et de courbes fines — la 3D n'apporterait ici que du poids et une seconde
// pile de rendu à côté de celle que la landing utilise déjà.

import {
  MAX_DPR, NODE_COUNT, NODE_COUNT_MOBILE, PARTICLE_COUNT, PARTICLE_COUNT_MOBILE, PHASES,
  TAPE_ROWS,
} from "./introConfig";

export type Palette = {
  fg: string; accent: string; accent2: string; neg: string; pos: string; muted: string;
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

const easeOut = (t: number) => 1 - Math.pow(1 - t, 3);
const clamp01 = (t: number) => (t < 0 ? 0 : t > 1 ? 1 : t);
/** Progression LOCALE d'une phase : 0 à son début, 1 à sa fin. */
const seg = (t: number, a: number, b: number) => clamp01((t - a) / (b - a));

type Particule = {
  x: number; y: number; vx: number; amp: number; ph: number; nx: number; ny: number;
};
type Noeud = { x: number; y: number; t: number; couche: number };
/** Chandelier vectoriel : corps + mèches, jamais rempli — on suggère, on ne décore pas. */
type Bougie = { x: number; o: number; c: number; h: number; l: number; t: number };
/** Une ligne de profondeur de carnet, côté achat ou vente. */
type Niveau = { y: number; taille: number; cote: 1 | -1; t: number };

export class SceneIntro {
  private p: Particule[] = [];
  private n: Noeud[] = [];
  private liens: [number, number][] = [];
  private bougies: Bougie[] = [];
  private carnet: Niveau[] = [];
  private proba = 0;
  private w = 0;
  private h = 0;
  private dpr = 1;

  constructor(private ctx: CanvasRenderingContext2D, private petit: boolean,
              private modeste: boolean) {}

  /** (Re)dimensionne et régénère la scène. Idempotent : appelable à chaque resize. */
  dimensionner(w: number, h: number): void {
    this.dpr = Math.min(MAX_DPR, window.devicePixelRatio || 1, this.modeste ? 1.5 : MAX_DPR);
    this.w = w;
    this.h = h;
    const cv = this.ctx.canvas;
    cv.width = Math.round(w * this.dpr);
    cv.height = Math.round(h * this.dpr);
    this.ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    this.semer();
  }

  private semer(): void {
    let nb = this.petit ? PARTICLE_COUNT_MOBILE : PARTICLE_COUNT;
    if (this.modeste) nb = Math.round(nb * 0.55);
    const nn = this.petit ? NODE_COUNT_MOBILE : NODE_COUNT;
    const rnd = mulberry(20260914);          // semé : deux chargements donnent la même scène

    // Nœuds sur deux couches — assez pour évoquer un graphe, jamais assez pour faire bruit.
    this.n = Array.from({ length: nn }, (_, i) => {
      const couche = i % 3;
      const parCouche = Math.ceil(nn / 3);
      const k = Math.floor(i / 3);
      return {
        x: this.w * (0.28 + couche * 0.22) + (rnd() - 0.5) * this.w * 0.04,
        y: this.h * (0.28 + (k + 0.5) / parCouche * 0.44) + (rnd() - 0.5) * this.h * 0.035,
        t: couche * 0.3 + rnd() * 0.35,      // allumage COUCHE PAR COUCHE : un passage avant
        couche,
      };
    });

    // Chandeliers vectoriels — corps et mèches en trait, jamais de gros blocs verts/rouges.
    const nb2 = this.petit ? 22 : 46;
    this.bougies = Array.from({ length: nb2 }, (_, i) => {
      const o = 0.5 + (rnd() - 0.5) * 0.30;
      const c = o + (rnd() - 0.5) * 0.22;
      return {
        x: (i + 0.5) / nb2,
        o, c,
        h: Math.max(o, c) + rnd() * 0.09,
        l: Math.min(o, c) - rnd() * 0.09,
        t: i / nb2,                          // apparition de gauche à droite
      };
    });

    // Profondeur de carnet : deux échelles symétriques autour du milieu.
    this.carnet = [];
    for (let i = 0; i < TAPE_ROWS; i++) {
      const f = (i + 1) / TAPE_ROWS;
      for (const cote of [1, -1] as const) {
        this.carnet.push({
          y: f, taille: (1 - f * 0.55) * (0.45 + rnd() * 0.55), cote, t: f,
        });
      }
    }
    this.liens = [];
    for (let i = 0; i < this.n.length; i++) {
      for (let j = i + 1; j < this.n.length; j++) {
        const d = Math.hypot(this.n[i].x - this.n[j].x, this.n[i].y - this.n[j].y);
        if (d < this.w * 0.17) this.liens.push([i, j]);
      }
    }
    // Chaque particule connaît d'avance SA destination : la transition flux → graphe est
    // alors une interpolation, pas une téléportation.
    this.p = Array.from({ length: nb }, () => {
      const cible = this.n[Math.floor(rnd() * this.n.length)] ?? { x: this.w / 2, y: this.h / 2 };
      return {
        x: rnd() * this.w, y: this.h * (0.2 + rnd() * 0.6),
        vx: 18 + rnd() * 46, amp: 4 + rnd() * 26, ph: rnd() * Math.PI * 2,
        nx: cible.x, ny: cible.y,
      };
    });
  }

  /** Peint l'image correspondant à `t` ∈ [0,1]. `dt` en secondes pour le flux. */
  peindre(t: number, dt: number, pal: Palette): void {
    const { ctx, w, h } = this;
    ctx.clearRect(0, 0, w, h);
    this.grille(t, pal);
    this.carnetProfondeur(t, pal);
    this.chandeliers(t, pal);
    this.ligneCentrale(t, pal);
    if (t < PHASES.neural) this.flux(t, dt, pal);
    if (t >= PHASES.flow) this.graphe(t, pal);
    if (t >= PHASES.flow) this.probabilite(t, pal);
    if (t >= PHASES.neural) this.risque(t, pal);
    this.scanline(t, pal);
  }

  /** Profondeur de carnet, en escalier, de part et d'autre du milieu. Le vocabulaire
   *  visuel d'un terminal — pas un graphique de cours de plus. */
  private carnetProfondeur(t: number, pal: Palette): void {
    const v = seg(t, 0.04, PHASES.flow) * (1 - seg(t, PHASES.neural, PHASES.risk));
    if (v <= 0.01) return;
    const { ctx, w, h } = this;
    const larg = this.petit ? w * 0.13 : w * 0.10;
    ctx.save();
    for (const n of this.carnet) {
      const a = clamp01((v - n.t * 0.35) * 2.2);
      if (a <= 0) continue;
      ctx.globalAlpha = a * 0.22;
      ctx.fillStyle = n.cote > 0 ? pal.pos : pal.neg;
      const y = h / 2 + n.cote * n.y * h * 0.36;
      const l = larg * n.taille * easeOut(a);
      ctx.fillRect(w * 0.045, y, l, 1.5);                 // colonne gauche
      ctx.fillRect(w * 0.955 - l, y, l, 1.5);             // colonne droite, en miroir
    }
    ctx.restore();
  }

  /** Chandeliers en TRAIT. Fins, désaturés, à peine là : ils situent, ils ne crient pas. */
  private chandeliers(t: number, pal: Palette): void {
    const v = seg(t, PHASES.init * 0.5, PHASES.flow)
      * (1 - seg(t, PHASES.flow, PHASES.neural));
    if (v <= 0.01) return;
    const { ctx, w, h } = this;
    const y0 = h * 0.62, amp = h * 0.20;
    const larg = (w * 0.72) / this.bougies.length * 0.44;
    ctx.save();
    ctx.lineWidth = 1;
    for (const b of this.bougies) {
      const a = clamp01((v - b.t * 0.5) * 2.4);
      if (a <= 0) continue;
      const x = w * 0.14 + b.x * w * 0.72;
      const py = (u: number) => y0 - (u - 0.5) * amp * 2;
      ctx.globalAlpha = a * 0.30;
      ctx.strokeStyle = b.c >= b.o ? pal.pos : pal.neg;
      ctx.beginPath();                                    // mèche
      ctx.moveTo(x, py(b.h));
      ctx.lineTo(x, py(b.l));
      ctx.stroke();
      ctx.strokeRect(x - larg / 2, py(Math.max(b.o, b.c)),  // corps, en contour
                     larg, Math.max(1.5, Math.abs(py(b.o) - py(b.c))));
    }
    ctx.restore();
  }

  /** La sortie du modèle : une probabilité qui se stabilise. Un arc, pas un chiffre. */
  private probabilite(t: number, pal: Palette): void {
    const v = seg(t, PHASES.flow + 0.04, PHASES.risk) * (1 - seg(t, PHASES.risk, 1));
    if (v <= 0.01) return;
    const { ctx, w, h } = this;
    // Converge vers une valeur crédible pour CE projet : un edge mince, pas 0,9.
    this.proba = 0.5 + 0.12 * easeOut(clamp01(v * 1.4));
    const r = Math.min(w, h) * (this.petit ? 0.105 : 0.085);
    const cx = w / 2, cy = h / 2;
    ctx.save();
    ctx.lineWidth = 1.5;
    ctx.globalAlpha = v * 0.16;
    ctx.strokeStyle = pal.muted;
    ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.stroke();
    ctx.globalAlpha = v * 0.85;
    ctx.strokeStyle = pal.accent;
    ctx.beginPath();
    ctx.arc(cx, cy, r, -Math.PI / 2, -Math.PI / 2 + this.proba * Math.PI * 2);
    ctx.stroke();
    ctx.restore();
  }

  /** Balayage horizontal unique, très faible : la sensation d'un système qui échantillonne. */
  private scanline(t: number, pal: Palette): void {
    const v = seg(t, PHASES.init, PHASES.risk);
    if (v <= 0 || v >= 1) return;
    const { ctx, w, h } = this;
    const y = h * (0.12 + v * 0.76);
    ctx.save();
    const g = ctx.createLinearGradient(0, y - 40, 0, y + 40);
    g.addColorStop(0, "transparent");
    g.addColorStop(0.5, pal.accent);
    g.addColorStop(1, "transparent");
    ctx.globalAlpha = 0.05 * Math.sin(v * Math.PI);
    ctx.fillStyle = g;
    ctx.fillRect(0, y - 40, w, 80);
    ctx.restore();
  }

  /** Grille mathématique, à la limite du visible. Donne la profondeur, jamais le regard. */
  private grille(t: number, pal: Palette): void {
    const a = seg(t, 0.05, PHASES.flow) * (1 - seg(t, PHASES.risk, 1)) * 0.05;
    if (a <= 0.002) return;
    const { ctx, w, h } = this;
    ctx.save();
    ctx.strokeStyle = pal.fg;
    ctx.globalAlpha = a;
    ctx.lineWidth = 1;
    const pas = this.petit ? 56 : 72;
    ctx.beginPath();
    for (let x = (w / 2) % pas; x < w; x += pas) { ctx.moveTo(x, 0); ctx.lineTo(x, h); }
    for (let y = (h / 2) % pas; y < h; y += pas) { ctx.moveTo(0, y); ctx.lineTo(w, y); }
    ctx.stroke();
    ctx.restore();
  }

  /** La ligne d'initialisation. Elle s'ouvre, puis reste : c'est elle qui passe au hero. */
  private ligneCentrale(t: number, pal: Palette): void {
    const ouv = easeOut(seg(t, 0.02, PHASES.init));
    if (ouv <= 0) return;
    const { ctx, w, h } = this;
    const y = h / 2;
    const demi = (w * 0.44) * ouv;
    const fin = seg(t, PHASES.risk, 1);            // se rétracte vers le centre à la fin
    const l = demi * (1 - fin * 0.72);
    ctx.save();
    const g = ctx.createLinearGradient(w / 2 - l, 0, w / 2 + l, 0);
    g.addColorStop(0, "transparent");
    g.addColorStop(0.5, pal.accent);
    g.addColorStop(1, "transparent");
    ctx.strokeStyle = g;
    ctx.globalAlpha = 0.55 + 0.45 * fin;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(w / 2 - l, y);
    ctx.lineTo(w / 2 + l, y);
    ctx.stroke();
    ctx.restore();
  }

  /** Flux de marché : des trajectoires fines qui défilent. Aucune bougie, aucun chiffre. */
  private flux(t: number, dt: number, pal: Palette): void {
    const vis = seg(t, PHASES.init, PHASES.flow) * (1 - seg(t, PHASES.flow, PHASES.neural));
    if (vis <= 0.01) return;
    const { ctx, w, h } = this;
    ctx.save();
    ctx.globalAlpha = vis * 0.5;
    ctx.fillStyle = pal.accent2;
    for (const q of this.p) {
      q.x += q.vx * dt;
      if (q.x > w) q.x -= w;
      q.ph += dt * 1.6;
      const y = q.y + Math.sin(q.ph) * q.amp * 0.35;
      ctx.fillRect(q.x, y, 1.6, 1.6);
    }
    ctx.globalAlpha = vis * 0.16;
    ctx.strokeStyle = pal.accent;
    ctx.lineWidth = 1;
    for (let k = 0; k < (this.petit ? 3 : 6); k++) {
      ctx.beginPath();
      for (let x = 0; x <= w; x += 14) {
        const yy = h * (0.3 + k * 0.08) + Math.sin(x * 0.006 + k + t * 7) * 16;
        x === 0 ? ctx.moveTo(x, yy) : ctx.lineTo(x, yy);
      }
      ctx.stroke();
    }
    ctx.restore();
  }

  /** Le flux se referme en graphe : les particules rejoignent leurs nœuds, les liens naissent. */
  private graphe(t: number, pal: Palette): void {
    const m = easeOut(seg(t, PHASES.flow, PHASES.neural));
    const sortie = seg(t, PHASES.risk, 1);
    if (sortie >= 1) return;
    const { ctx } = this;
    ctx.save();
    ctx.globalAlpha = (1 - sortie) * 0.9;

    ctx.globalAlpha = (1 - sortie) * 0.28 * m;
    ctx.strokeStyle = pal.accent;
    ctx.lineWidth = 1;
    for (const [i, j] of this.liens) {
      const a = this.n[i], b = this.n[j];
      const ouvert = clamp01((m - Math.min(a.t, b.t) * 0.5) * 2);
      if (ouvert <= 0) continue;
      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      ctx.lineTo(a.x + (b.x - a.x) * ouvert, a.y + (b.y - a.y) * ouvert);
      ctx.stroke();
    }

    // Particules aspirées vers leur nœud — le « calcul » se voit dans le mouvement.
    ctx.globalAlpha = (1 - sortie) * 0.45 * m;
    ctx.fillStyle = pal.accent2;
    for (const q of this.p) {
      ctx.fillRect(q.x + (q.nx - q.x) * m, q.y + (q.ny - q.y) * m, 1.6, 1.6);
    }

    // Un signal unique traverse le réseau, de gauche à droite. Une fois. Pas une boucle.
    const sig = seg(t, PHASES.flow + 0.06, PHASES.neural);
    for (const nd of this.n) {
      const allume = clamp01((sig - nd.t * 0.55) * 3.2);
      if (allume <= 0) continue;
      ctx.globalAlpha = (1 - sortie) * allume * 0.95;
      ctx.fillStyle = pal.accent;
      ctx.beginPath();
      ctx.arc(nd.x, nd.y, 1.7 + allume * 1.1, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();
  }

  /** Une bande d'exposition apparaît, puis se resserre. C'est le seul rouge de l'intro. */
  private risque(t: number, pal: Palette): void {
    const p = seg(t, PHASES.neural, PHASES.risk);
    const sortie = seg(t, PHASES.risk, 1);
    if (p <= 0 || sortie >= 1) return;
    const { ctx, w, h } = this;
    const y = h / 2;
    const large = h * 0.17 * (1 - easeOut(p) * 0.82) * (1 - sortie);
    ctx.save();
    ctx.globalAlpha = (1 - sortie) * (0.16 + 0.10 * (1 - p));
    ctx.fillStyle = pal.neg;
    ctx.fillRect(w * 0.16, y - large, w * 0.68, large * 2);
    // Les bords de l'enveloppe, qui convergent : c'est eux qu'on lit, pas le remplissage.
    ctx.globalAlpha = (1 - sortie) * 0.5;
    ctx.strokeStyle = p > 0.75 ? pal.accent2 : pal.neg;
    ctx.lineWidth = 1;
    for (const s of [-1, 1]) {
      ctx.beginPath();
      ctx.moveTo(w * 0.16, y + s * large);
      ctx.lineTo(w * 0.84, y + s * large);
      ctx.stroke();
    }
    ctx.restore();
  }
}

/** PRNG semé — une intro reproductible se règle ; une intro aléatoire se subit. */
function mulberry(a: number): () => number {
  return () => {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
