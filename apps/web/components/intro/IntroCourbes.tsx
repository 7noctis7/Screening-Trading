"use client";
import { useEffect, useRef } from "react";
import s from "./intro.module.css";
import {
  CRISES, bornesDates, cadre, clamp01, easeOut, fondu, graduationMax, indexDeDate,
  ligneBase, marqueurCrise, tracer,
} from "./introCourbeDraw";

export type Periode = {
  cle: string; libelle: string; disponible: boolean; motif?: string;
  debut?: string; fin?: string;
  croissance?: number; cagr?: number | null; max_drawdown?: number;
  courbe?: number[]; reference?: number[] | null; reference_croissance?: number | null;
  annees?: number;
};

const pct = (v: number | null | undefined) =>
  v == null ? "n/d" : `${v >= 0 ? "+" : ""}${(v * 100).toFixed(v > 1 || v < -1 ? 0 : 1)} %`;

/** Fraction du battement consacrée à la déformation d'une fenêtre vers la suivante.
 *
 *  Une FRACTION, donc elle s'allonge avec le battement — ce qui n'est pas souhaitable :
 *  la transition doit rester brève pour laisser du temps de LECTURE. À 3,4 s de battement,
 *  0,22 donne 0,75 s de déformation puis 2,6 s de courbe immobile. C'est le bon partage :
 *  la transition explique la continuité, elle n'est pas le sujet. */
const MORPH = 0.22;

/**
 * Robot contre référence, sur UNE fenêtre. Les deux courbes sont déjà en base 100 au même
 * jour : le serveur les a normalisées, le front ne recalcule rien — sinon deux définitions
 * de « départ » finiraient par diverger sans que personne ne s'en aperçoive.
 *
 * Canvas plutôt que SVG : une courbe de soixante points redessinée à chaque frame ferait
 * soixante mutations DOM par image. Ici, un seul élément.
 *
 * TROIS REPÈRES, parce qu'une courbe seule ne dit qu'« ça monte » :
 *   — la ligne à 100, départ commun, qui seule permet de lire « au-dessus » ;
 *   — la graduation du haut en multiple (« ×4,2 »), qui donne l'AMPLEUR ;
 *   — les crises nommées, parce que c'est là que l'écart se creuse ou se perd.
 *
 * Et la fenêtre suivante ne REMPLACE pas la précédente, elle la DÉFORME : cinq coupes
 * remplacées d'un coup se lisent comme cinq stratégies ; la même courbe qui s'étire se lit
 * comme une seule, observée plus longtemps.
 */
export function IntroCourbes({ p, periode, nomRef }: {
  p: number; periode: Periode | null; nomRef: string;
}) {
  const ref = useRef<HTMLCanvasElement>(null);
  // Séries SOURCES de la fenêtre déjà affichée — jamais les valeurs interpolées, sinon
  // chaque image morpherait depuis la précédente et la transition n'arriverait jamais.
  const src = useRef<{ cle: string; nous: number[]; ref: number[] } | null>(null);

  useEffect(() => {
    const cv = ref.current;
    const d = periode;
    if (!cv || !d?.disponible || !d.courbe?.length) return;
    const ctx = cv.getContext("2d");
    if (!ctx) return;

    const cs = getComputedStyle(document.documentElement);
    const cl = (n: string, r: string) => cs.getPropertyValue(n).trim() || r;
    const cNous = cl("--accent", "#22d3ee");
    const cRef = cl("--muted2", "#637580");
    const cFg = cl("--fg", "#e6edf3");

    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const w = cv.clientWidth, h = cv.clientHeight;
    cv.width = Math.round(w * dpr);
    cv.height = Math.round(h * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);

    const prec = src.current;
    const morph = prec !== null && prec.cle !== d.cle;
    const k = morph ? clamp01(p / MORPH) : 1;
    const brutRef = d.reference || [];
    const nous = morph ? fondu(prec!.nous, d.courbe, k) : d.courbe;
    const rf = morph && prec!.ref.length ? fondu(prec!.ref, brutRef, k) : brutRef;

    const series = [rf, nous].filter((x) => x.length > 1);
    if (!series.length) return;
    const c = cadre(w, h, series);

    // La PREMIÈRE fenêtre se trace (on voit l'écart se creuser) ; les suivantes sont déjà
    // entières et se déforment — deux animations simultanées ne se liraient ni l'une ni l'autre.
    // Tracé de la PREMIÈRE fenêtre. Plus vif qu'avant : sur un battement de 3,4 s, un
    // tracé qui s'étire jusqu'aux deux tiers mangerait le temps de lecture qu'on vient
    // d'ajouter. Il se termine désormais vers 1,5 s, laissant 1,9 s de courbe posée.
    const avRef = prec ? 1 : easeOut((p - 0.03) * 2.6);
    const avNous = prec ? 1 : easeOut((p - 0.07) * 2.6);
    const aRepere = easeOut(clamp01((p - (prec ? MORPH : 0.45)) * 3));

    ligneBase(ctx, c, cFg, prec ? 1 : easeOut(p * 4));
    graduationMax(ctx, c, cFg, aRepere);
    // Les bornes suivent `aRepere`, donc elles n'apparaissent qu'une fois la courbe
    // POSÉE. Pendant la déformation d'une fenêtre vers la suivante, des dates qui
    // sauteraient d'un coup pendant que le tracé glisse se liraient comme une erreur.
    bornesDates(ctx, c, d.debut, d.fin, cFg, aRepere);

    if (d.debut && d.fin) {
      for (const cr of CRISES) {
        const i = indexDeDate(cr.date, d.debut, d.fin, nous.length);
        if (i == null) continue;
        marqueurCrise(ctx, c, c.X(i, nous.length), cr.nom, cFg, aRepere);
      }
    }

    if (rf.length > 1) tracer(ctx, c, rf, cRef, avRef, 1.2);
    tracer(ctx, c, nous, cNous, avNous, 2, true);

    // On ne mémorise la fenêtre qu'une fois qu'elle est VRAIMENT à l'écran : trop tôt, le
    // tracé progressif de la première serait coupé net par un `av` qui saute à 1.
    if (morph ? k >= 1 : p > 0.55) {
      src.current = { cle: d.cle, nous: d.courbe, ref: brutRef };
    }
  }, [p, periode]);

  if (!periode?.disponible) return null;
  // L'ÉCART CHIFFRÉ. Le dessin montre que l'une passe au-dessus de l'autre ; il ne dit pas
  // de combien. En points de pourcentage, parce que c'est une différence de croissances.
  const ec = (periode.croissance != null && periode.reference_croissance != null)
    ? (periode.croissance - periode.reference_croissance) * 100 : null;
  return (
    <div className={s.courbes}>
      <canvas ref={ref} className={s.courbesCanvas} aria-hidden="true" />
      <div className={s.legende}>
        <span className={s.legItem}>
          <i className={s.legDot} data-k="nous" /> QUANT TERMINAL
          <b>{pct(periode.croissance)}</b>
        </span>
        <span className={s.legItem}>
          <i className={s.legDot} data-k="ref" /> {nomRef}
          <b>{pct(periode.reference_croissance)}</b>
        </span>
        {ec != null && (
          <span className={s.legEcart} data-signe={ec >= 0 ? "pos" : "neg"}>
            ÉCART <b>{ec >= 0 ? "+" : "−"}{Math.abs(Math.round(ec)).toLocaleString("fr-FR")} pts</b>
          </span>
        )}
      </div>
    </div>
  );
}

export default IntroCourbes;
