"use client";
import { useEffect, useRef } from "react";
import s from "./intro.module.css";

export type Periode = {
  cle: string; libelle: string; disponible: boolean;
  croissance?: number; cagr?: number | null; max_drawdown?: number;
  courbe?: number[]; reference?: number[] | null; reference_croissance?: number | null;
  annees?: number;
};

const pct = (v: number | null | undefined) =>
  v == null ? "n/d" : `${v >= 0 ? "+" : ""}${(v * 100).toFixed(v > 1 || v < -1 ? 0 : 1)} %`;

/**
 * Robot contre référence, sur UNE fenêtre. Les deux courbes sont déjà en base 100 au même
 * jour : le serveur les a normalisées, le front ne recalcule rien — sinon deux définitions
 * de « départ » finiraient par diverger sans que personne ne s'en aperçoive.
 *
 * Canvas plutôt que SVG : une courbe de soixante points redessinée à chaque frame ferait
 * soixante mutations DOM par image. Ici, un seul élément.
 */
export function IntroCourbes({ p, periode, nomRef }: {
  p: number; periode: Periode | null; nomRef: string;
}) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const cv = ref.current;
    const d = periode;
    if (!cv || !d?.disponible || !d.courbe?.length) return;
    const ctx = cv.getContext("2d");
    if (!ctx) return;

    const cs = getComputedStyle(document.documentElement);
    const cl = (n: string, r: string) => cs.getPropertyValue(n).trim() || r;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const w = cv.clientWidth, h = cv.clientHeight;
    cv.width = Math.round(w * dpr);
    cv.height = Math.round(h * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);

    const series = [d.reference || [], d.courbe].filter((x) => x.length > 1);
    if (!series.length) return;
    // Échelle COMMUNE aux deux courbes : deux échelles séparées feraient se ressembler
    // une série qui double et une qui stagne. C'est le graphique qui doit dire l'écart.
    const tous = series.flat();
    const lo = Math.min(...tous), hi = Math.max(...tous);
    const span = hi - lo || 1;
    const pad = 10;
    const X = (i: number, n: number) => pad + (i / (n - 1)) * (w - pad * 2);
    const Y = (v: number) => h - pad - ((v - lo) / span) * (h - pad * 2);

    // Tracé progressif : la référence part en premier, la nôtre la rattrape. On VOIT
    // l'écart se creuser au lieu de le lire une fois posé.
    const dessiner = (vals: number[], couleur: string, av: number, ep: number) => {
      const n = vals.length;
      const jusqu = Math.max(2, Math.round(n * Math.min(1, av)));
      ctx.save();
      ctx.strokeStyle = couleur;
      ctx.lineWidth = ep;
      ctx.lineJoin = "round";
      ctx.beginPath();
      for (let i = 0; i < jusqu; i++) {
        const x = X(i, n), y = Y(vals[i]);
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
      }
      ctx.stroke();
      ctx.restore();
    };

    const e = (t: number) => 1 - Math.pow(1 - Math.max(0, Math.min(1, t)), 3);
    if (d.reference?.length) {
      dessiner(d.reference, cl("--muted2", "#637580"), e((p - 0.06) * 1.5), 1.2);
    }
    dessiner(d.courbe, cl("--accent", "#22d3ee"), e((p - 0.16) * 1.5), 2);
  }, [p, periode]);

  if (!periode?.disponible) return null;
  return (
    <div className={s.courbes} aria-hidden="true">
      <canvas ref={ref} className={s.courbesCanvas} />
      <div className={s.legende}>
        <span className={s.legItem}>
          <i className={s.legDot} data-k="nous" /> QUANT TERMINAL
          <b>{pct(periode.croissance)}</b>
        </span>
        <span className={s.legItem}>
          <i className={s.legDot} data-k="ref" /> {nomRef}
          <b>{pct(periode.reference_croissance)}</b>
        </span>
      </div>
    </div>
  );
}

export default IntroCourbes;
