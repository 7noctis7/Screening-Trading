"use client";
import { useEffect, useRef } from "react";
import s from "./intro.module.css";
import {
  CRISES, bornesDates, cadre, clamp01, easeOut, fondu, graduationMax, indexDeDate,
  ligneBase, marqueurCrise, tracer,
} from "./introCourbeDraw";

export type Reference = {
  nom: string; courbe?: number[] | null; croissance?: number | null; motif?: string;
};

export type Periode = {
  cle: string; libelle: string; disponible: boolean; motif?: string;
  debut?: string; fin?: string;
  croissance?: number; cagr?: number | null; max_drawdown?: number;
  courbe?: number[];
  /** Toutes les références RÉELLES, dans l'ordre d'affichage. */
  references?: Reference[] | null;
  /** Conservés pour le site statique déjà déployé, qui ne connaît pas `references`. */
  reference?: number[] | null; reference_croissance?: number | null;
  annees?: number;
};

/** Couleurs des références, dans l'ordre. La nôtre a la sienne (`--accent`) ; celles-ci
 *  doivent rester DISTINCTES entre elles et plus sourdes que la nôtre — le sujet du
 *  graphique est notre courbe, les indices sont des repères. */
const VARS_REF = ["--muted2", "--warn"];
const REPLIS_REF = ["#637580", "#f59e0b"];

/** Les références réellement traçables. Une série absente n'est pas remplacée : on ne
 *  dessine que ce qui existe, et la légende ne mentionne que ce qui est dessiné. */
export function referencesUtiles(p: Periode | null): Reference[] {
  if (!p) return [];
  const listees = (p.references ?? []).filter((r) => (r.courbe?.length ?? 0) > 1);
  if (listees.length) return listees;
  // Repli sur l'ancienne forme à une seule référence (site statique pas encore rebâti).
  return (p.reference?.length ?? 0) > 1
    ? [{ nom: "référence", courbe: p.reference, croissance: p.reference_croissance }]
    : [];
}

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
  const src = useRef<{ cle: string; nous: number[]; refs: number[][] } | null>(null);

  useEffect(() => {
    const cv = ref.current;
    const d = periode;
    if (!cv || !d?.disponible || !d.courbe?.length) return;
    const ctx = cv.getContext("2d");
    if (!ctx) return;

    const cs = getComputedStyle(document.documentElement);
    const cl = (n: string, r: string) => cs.getPropertyValue(n).trim() || r;
    const cNous = cl("--accent", "#22d3ee");
    const cFg = cl("--fg", "#e6edf3");
    const refs = referencesUtiles(d);
    const cRefs = refs.map((_, i) => cl(VARS_REF[i % VARS_REF.length],
                                        REPLIS_REF[i % REPLIS_REF.length]));

    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const w = cv.clientWidth, h = cv.clientHeight;
    cv.width = Math.round(w * dpr);
    cv.height = Math.round(h * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);

    const prec = src.current;
    const morph = prec !== null && prec.cle !== d.cle;
    const k = morph ? clamp01(p / MORPH) : 1;
    const bruts = refs.map((r) => r.courbe || []);
    const nous = morph ? fondu(prec!.nous, d.courbe, k) : d.courbe;
    // Chaque référence se déforme vers SA remplaçante de même rang. Une référence
    // nouvelle sur cette fenêtre (l'indice ne couvrait pas la précédente) apparaît sans
    // fondu plutôt que de sortir d'une courbe qui n'est pas la sienne.
    const rfs = bruts.map((brut, i) => {
      const avant = morph ? (prec!.refs[i] || []) : [];
      return avant.length === brut.length && avant.length ? fondu(avant, brut, k) : brut;
    });

    const series = [...rfs, nous].filter((x) => x.length > 1);
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

    rfs.forEach((rf, i) => {
      if (rf.length > 1) tracer(ctx, c, rf, cRefs[i], avRef, 1.2);
    });
    tracer(ctx, c, nous, cNous, avNous, 2, true);

    // On ne mémorise la fenêtre qu'une fois qu'elle est VRAIMENT à l'écran : trop tôt, le
    // tracé progressif de la première serait coupé net par un `av` qui saute à 1.
    if (morph ? k >= 1 : p > 0.55) {
      src.current = { cle: d.cle, nous: d.courbe, refs: bruts };
    }
  }, [p, periode]);

  if (!periode?.disponible) return null;
  const refs = referencesUtiles(periode);
  // L'ÉCART CHIFFRÉ, contre CHAQUE référence. Le dessin montre qu'une courbe passe
  // au-dessus d'une autre ; il ne dit pas de combien. En points de pourcentage, parce
  // que c'est une différence de croissances — et nommé, parce qu'avec trois courbes un
  // « écart » anonyme ne désigne plus rien.
  const ecart = (r: Reference) =>
    (periode.croissance != null && r.croissance != null)
      ? (periode.croissance - r.croissance) * 100 : null;
  return (
    <div className={s.courbes}>
      <canvas ref={ref} className={s.courbesCanvas} aria-hidden="true" />
      <div className={s.legende}>
        <span className={s.legItem}>
          <i className={s.legDot} data-k="nous" /> QUANT TERMINAL
          <b>{pct(periode.croissance)}</b>
        </span>
        {refs.map((r, i) => (
          <span key={r.nom} className={s.legItem}>
            <i className={s.legDot} style={{ background: `var(${VARS_REF[i % VARS_REF.length]}, ${REPLIS_REF[i % REPLIS_REF.length]})` }} />
            {(r.nom === "référence" ? nomRef : r.nom).toUpperCase()}
            <b>{pct(r.croissance)}</b>
          </span>
        ))}
        {refs.map((r) => {
          const ec = ecart(r);
          return ec == null ? null : (
            <span key={`e-${r.nom}`} className={s.legEcart} data-signe={ec >= 0 ? "pos" : "neg"}>
              vs {(r.nom === "référence" ? nomRef : r.nom).toUpperCase()}{" "}
              <b>{ec >= 0 ? "+" : "−"}{Math.abs(Math.round(ec)).toLocaleString("fr-FR")} pts</b>
            </span>
          );
        })}
      </div>
    </div>
  );
}

export default IntroCourbes;
