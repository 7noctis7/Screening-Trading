// Dessin des courbes comparées. Aucune donnée, aucun React : des nombres, un contexte.
//
// Séparé du composant pour que la logique de tracé — repères, crises, interpolation — se
// lise et se teste sans monter quoi que ce soit.

export type Repere = { date: string; nom: string };

/** Crises marquées sur les fenêtres longues. C'est là que l'argument se joue vraiment. */
export const CRISES: Repere[] = [
  { date: "2020-03-23", nom: "COVID" },
  { date: "2022-10-12", nom: "2022" },
];

export const clamp01 = (t: number) => (t < 0 ? 0 : t > 1 ? 1 : t);
export const easeOut = (t: number) => 1 - Math.pow(1 - clamp01(t), 3);

/** Interpolation point à point entre deux séries de MÊME longueur. */
export function fondu(a: number[], b: number[], k: number): number[] {
  if (!a.length || a.length !== b.length) return b;
  const e = easeOut(k);
  return b.map((v, i) => a[i] + (v - a[i]) * e);
}

/** Position d'une date dans une série ré-échantillonnée entre `debut` et `fin`. */
export function indexDeDate(d: string, debut: string, fin: string, n: number): number | null {
  const t = Date.parse(d), a = Date.parse(debut), b = Date.parse(fin);
  if (!Number.isFinite(t) || !Number.isFinite(a) || !Number.isFinite(b) || b <= a) return null;
  if (t < a || t > b) return null;
  return ((t - a) / (b - a)) * (n - 1);
}

export type Cadre = {
  w: number; h: number; pad: number; lo: number; hi: number;
  X: (i: number, n: number) => number; Y: (v: number) => number;
};

/** Échelle COMMUNE aux deux séries. Deux échelles séparées feraient se ressembler une
 *  courbe qui double et une qui stagne — c'est le graphique qui doit dire l'écart. */
export function cadre(w: number, h: number, series: number[][], pad = 14): Cadre {
  const tous = series.flat();
  // 100 est TOUJOURS dans l'échelle : c'est le départ commun, donc le seul repère qui
  // permette de lire « au-dessus » ou « en dessous » sans compter les pixels.
  const lo = Math.min(100, ...tous);
  const hi = Math.max(100, ...tous);
  const span = hi - lo || 1;
  return {
    w, h, pad, lo, hi,
    X: (i, n) => pad + (i / Math.max(1, n - 1)) * (w - pad * 2),
    Y: (v) => h - pad - ((v - lo) / span) * (h - pad * 2),
  };
}

/** Ligne de base 100 : le départ commun. Sans elle, on lit une forme, pas une ampleur. */
export function ligneBase(ctx: CanvasRenderingContext2D, c: Cadre, couleur: string,
                          alpha: number) {
  if (alpha <= 0.01) return;
  const y = c.Y(100);
  ctx.save();
  ctx.globalAlpha = alpha * 0.35;
  ctx.strokeStyle = couleur;
  ctx.lineWidth = 1;
  ctx.setLineDash([3, 5]);
  ctx.beginPath();
  ctx.moveTo(c.pad, y);
  ctx.lineTo(c.w - c.pad, y);
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.font = '9px ui-monospace, "JetBrains Mono", monospace';
  ctx.globalAlpha = alpha * 0.5;
  ctx.fillStyle = couleur;
  ctx.textAlign = "left";
  ctx.fillText("DÉPART", c.pad, y - 5);
  ctx.restore();
}

/** Repère vertical d'une crise, nommé. Sur dix ans, c'est là que l'écart se creuse. */
export function marqueurCrise(ctx: CanvasRenderingContext2D, c: Cadre, x: number,
                              nom: string, couleur: string, alpha: number) {
  if (alpha <= 0.01) return;
  ctx.save();
  ctx.globalAlpha = alpha * 0.22;
  ctx.strokeStyle = couleur;
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(x, c.pad);
  ctx.lineTo(x, c.h - c.pad);
  ctx.stroke();
  ctx.globalAlpha = alpha * 0.55;
  ctx.font = '8px ui-monospace, "JetBrains Mono", monospace';
  ctx.fillStyle = couleur;
  ctx.textAlign = "center";
  ctx.fillText(nom, x, c.pad - 3);
  ctx.restore();
}

/** Une courbe, tracée jusqu'à `av` ∈ [0,1], avec un point lumineux en tête. */
export function tracer(ctx: CanvasRenderingContext2D, c: Cadre, vals: number[],
                       couleur: string, av: number, ep: number, tete = false) {
  const n = vals.length;
  const jusqu = Math.max(2, Math.round(n * clamp01(av)));
  if (jusqu < 2) return;
  ctx.save();
  ctx.strokeStyle = couleur;
  ctx.lineWidth = ep;
  ctx.lineJoin = "round";
  ctx.lineCap = "round";
  ctx.beginPath();
  for (let i = 0; i < jusqu; i++) {
    const x = c.X(i, n), y = c.Y(vals[i]);
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  }
  ctx.stroke();
  if (tete && jusqu < n) {
    // Le point de tête ne s'affiche QUE pendant le tracé : une fois la courbe finie, il
    // deviendrait un ornement sans signification.
    ctx.globalAlpha = 0.9;
    ctx.fillStyle = couleur;
    ctx.beginPath();
    ctx.arc(c.X(jusqu - 1, n), c.Y(vals[jusqu - 1]), 2.2, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.restore();
}

/** Une date ISO → `jj/mm/aaaa`. Lue à la MAIN, jamais par `Date`.
 *
 *  `new Date("2016-05-19")` vaut minuit UTC ; `toLocaleDateString` dans un fuseau négatif
 *  afficherait alors le 18/05. Une borne de fenêtre de performance qui recule d'un jour
 *  selon l'endroit d'où on regarde le site n'est pas un détail d'affichage : c'est la
 *  période même de la mesure qui change. On découpe la chaîne, et on rend « » si elle
 *  n'a pas la forme attendue — une date illisible ne s'invente pas. */
export function dateCourte(iso: string | undefined): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || "");
  return m ? `${m[3]}/${m[2]}/${m[1]}` : "";
}

/** Les deux BORNES de la fenêtre, sous le cadre : départ à gauche, arrivée à droite.
 *
 *  Sans elles, « +142 % sur 10 ans » ne dit pas DE QUAND À QUAND. Deux fenêtres de dix ans
 *  qui ne commencent pas la même année ne se comparent pas, et le lecteur n'a aucun moyen
 *  de s'en apercevoir. La position les rend lisibles sans légende : la date de gauche est
 *  sous le début du tracé, celle de droite sous sa fin. */
export function bornesDates(ctx: CanvasRenderingContext2D, c: Cadre,
                            debut: string | undefined, fin: string | undefined,
                            couleur: string, alpha: number) {
  if (alpha <= 0.01) return;
  const d = dateCourte(debut), f = dateCourte(fin);
  if (!d || !f) return;
  ctx.save();
  ctx.globalAlpha = alpha * 0.5;
  ctx.font = '8px ui-monospace, "JetBrains Mono", monospace';
  ctx.fillStyle = couleur;
  const y = c.h - 3;
  ctx.textAlign = "left";
  ctx.fillText(d, c.pad, y);
  ctx.textAlign = "right";
  ctx.fillText(f, c.w - c.pad, y);
  ctx.restore();
}

/** Graduation au HAUT de l'échelle, en multiple du départ.
 *
 *  Sans elle, une courbe qui monte et une courbe qui triple ont la même allure : le cadre
 *  s'ajuste toujours au maximum, donc la pente ne dit RIEN de l'ampleur. « ×4,2 » le dit. */
export function graduationMax(ctx: CanvasRenderingContext2D, c: Cadre, couleur: string,
                              alpha: number) {
  if (alpha <= 0.01 || c.hi <= 100.5) return;
  const y = c.Y(c.hi);
  const mult = c.hi / 100;
  ctx.save();
  ctx.globalAlpha = alpha * 0.16;
  ctx.strokeStyle = couleur;
  ctx.lineWidth = 1;
  ctx.setLineDash([2, 6]);
  ctx.beginPath();
  ctx.moveTo(c.pad, y);
  ctx.lineTo(c.w - c.pad, y);
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.globalAlpha = alpha * 0.6;
  ctx.font = '9px ui-monospace, "JetBrains Mono", monospace';
  ctx.fillStyle = couleur;
  ctx.textAlign = "right";
  ctx.fillText(`×${mult.toFixed(mult >= 10 ? 0 : 1).replace(".", ",")}`, c.w - c.pad, y + 10);
  ctx.restore();
}
