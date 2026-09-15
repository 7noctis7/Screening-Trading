"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import s from "./intro.module.css";
import {
  INTRO_BASELINE, INTRO_BRAND, INTRO_DURATION, INTRO_DURATION_MOBILE, PHASES,
} from "./introConfig";
import { IntroBeats } from "./IntroBeats";
import { useIntro } from "@/lib/api";
import { Palette, SceneIntro, paletteDuTheme } from "./introScene";
import { machineModeste, marquerVue, useIntroGate } from "./useIntroGate";

const SORTIE_MS = 620;      // doit valoir la transition CSS de `.overlay`

/**
 * Rideau d'entrée : flux de marché → graphe → enveloppe de risque → nom → landing.
 *
 * Ce composant ne rend RIEN tant que `useIntroGate` n'a pas tranché — la décision dépend de
 * `sessionStorage` et de `prefers-reduced-motion`, qui n'existent pas au rendu serveur. Sur un
 * export statique, rendre l'intro au SSR la ferait clignoter chez qui l'a déjà vue.
 *
 * Il ne bloque jamais l'accès : la landing est montée DESSOUS dès le premier rendu, le rideau
 * se contente d'être au-dessus. Passer l'intro ne charge donc rien — ça retire un calque.
 */
export function IntroSequence({ onFini }: { onFini?: () => void }) {
  const { jouer, reduit } = useIntroGate();
  // Les chiffres viennent du snapshot, pas du code. Absents → les battements de
  // période se sautent d'eux-mêmes : l'intro raccourcit, elle n'invente pas.
  const { data: intro } = useIntro();
  const [monte, setMonte] = useState(false);
  const [sortie, setSortie] = useState(false);
  const [reveal, setReveal] = useState(false);
  const [beat, setBeat] = useState<{ i: number; p: number }>({ i: 0, p: 0 });
  // Avancement partagé avec le HUD. Un état par frame serait 60 rendus React par
  // seconde ; on n'écrit que par pas de 1 % — invisible à l'œil, dix fois moins cher.
  const [avance, setAvance] = useState(0);
  const cvRef = useRef<HTMLCanvasElement>(null);
  const fini = useRef(false);

  useEffect(() => { if (jouer) setMonte(true); }, [jouer]);

  const terminer = useCallback(() => {
    if (fini.current) return;
    fini.current = true;
    marquerVue();
    setSortie(true);
    window.setTimeout(() => { setMonte(false); onFini?.(); }, SORTIE_MS);
  }, [onFini]);

  // Échap passe l'intro : un rideau dont on ne peut pas sortir au clavier est un piège.
  useEffect(() => {
    if (!monte) return;
    const k = (e: KeyboardEvent) => { if (e.key === "Escape") terminer(); };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [monte, terminer]);

  // Mouvement réduit : ni canvas ni phases — le nom, puis la landing.
  useEffect(() => {
    if (!monte || !reduit) return;
    setReveal(true);
    const t = window.setTimeout(terminer, 900);
    return () => window.clearTimeout(t);
  }, [monte, reduit, terminer]);

  useEffect(() => {
    if (!monte || reduit) return;
    const cv = cvRef.current;
    if (!cv) return;
    const ctx = cv.getContext("2d", { alpha: true });
    if (!ctx) { terminer(); return; }     // pas de 2D → on ne bloque pas l'entrée

    const petit = window.innerWidth < 760;
    const duree = petit ? INTRO_DURATION_MOBILE : INTRO_DURATION;
    const scene = new SceneIntro(ctx, petit, machineModeste());
    let pal: Palette = paletteDuTheme();
    const redim = () => scene.dimensionner(window.innerWidth, window.innerHeight);
    redim();
    window.addEventListener("resize", redim);

    let raf = 0;
    let t0 = 0;
    let precedent = 0;
    const boucle = (ts: number) => {
      if (!t0) { t0 = ts; precedent = ts; pal = paletteDuTheme(); }
      const t = Math.min(1, (ts - t0) / duree);
      const dt = Math.min(0.05, (ts - precedent) / 1000);   // borné : un onglet réveillé
      precedent = ts;                                        // ne doit pas téléporter le flux
      scene.peindre(t, dt, pal);
      setAvance((a) => (Math.abs(t - a) > 0.008 ? t : a));
      // Le DOM ne suit PAS le canvas image par image : on n'écrit l'état du battement que
      // lorsqu'il change, ou par pas de 2 % à l'intérieur. Soixante rendus React par
      // seconde pour quatre mots serait le seul vrai coût de cette intro.
      setBeat((b) => {
        const n = scene.battement(t);
        return n.i !== b.i || Math.abs(n.p - b.p) > 0.02 ? { i: n.i, p: n.p } : b;
      });
      if (t >= PHASES.trades) setReveal(true);
      if (t >= 1) { terminer(); return; }
      raf = requestAnimationFrame(boucle);
    };
    raf = requestAnimationFrame(boucle);
    return () => { cancelAnimationFrame(raf); window.removeEventListener("resize", redim); };
  }, [monte, reduit, terminer]);

  if (!monte) return null;
  return (
    <div className={s.overlay} data-sortie={sortie ? "1" : "0"} role="presentation"
         aria-hidden="true">
      {!reduit && <canvas ref={cvRef} className={s.canvas} />}
      {!reduit && (
        <IntroBeats i={beat.i} p={beat.p} sortie={sortie} data={intro} />
      )}
      {!reduit && (
        <div className={s.progress} aria-hidden="true">
          <div className={s.progressFill} style={{ width: `${avance * 100}%` }} />
        </div>
      )}
      <div className={s.centre} data-reveal={reveal ? "1" : "0"}>
        <h1 className={s.brand}>{INTRO_BRAND}</h1>
        {INTRO_BASELINE && <div className={s.baseline}>{INTRO_BASELINE}</div>}
      </div>
      <button className={s.skip} onClick={terminer}
              aria-label="Passer l'introduction et entrer sur le site">
        PASSER →
      </button>
    </div>
  );
}

export default IntroSequence;
