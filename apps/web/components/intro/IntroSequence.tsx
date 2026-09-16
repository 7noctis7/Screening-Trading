"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import s from "./intro.module.css";
import {
  INTRO_BASELINE, INTRO_BRAND, INTRO_DURATION, INTRO_DURATION_MOBILE, PHASES,
} from "./introConfig";
import { IntroBeats } from "./IntroBeats";
import { useIntro } from "@/lib/api";
import { IntroSon, creerSon } from "./introSon";
import { Palette, SceneIntro, paletteDuTheme } from "./introScene";
import { machineModeste, marquerVue, useIntroGate } from "./useIntroGate";

const SORTIE_MS = 620;      // doit valoir la transition CSS de `.overlay`

/** Combien de temps on ATTEND les chiffres avant de jouer quand même.
 *
 * L'intro ne raconte rien sans eux : cinq fenêtres de performance et la qualité des trades
 * sont SEPT de ses neuf battements. Jouée trop tôt, elle déroule un décor et deux chiffres
 * fixes — ce que l'utilisateur a vu le 15/09 après un `make up`, et qui ressemble à un bug
 * sans en être un : l'API venait de redémarrer, son cache disque était invalidé par le
 * changement de code, et elle reconstruisait le snapshot pendant une à trois minutes.
 *
 * Deux secondes et demie couvrent une API tiède et le site statique (JSON déjà sur disque).
 * Au-delà, on joue sans : un rideau qui ne se lève jamais serait pire qu'une intro courte.
 */
const ATTENTE_DONNEES_MS = 2_500;

/**
 * Rideau d'entrée : flux de marché → graphe → enveloppe de risque → nom → landing.
 *
 * Ce composant ne rend RIEN tant que `useIntroGate` n'a pas tranché — la décision dépend de
 * `sessionStorage` et de `prefers-reduced-motion`, qui n'existent pas au rendu serveur. Sur un
 * export statique, rendre l'intro au SSR la ferait clignoter chez qui l'a déjà vue.
 *
 * Il ne bloque jamais l'accès : la landing est montée DESSOUS dès le premier rendu, le rideau
 * se contente d'être au-dessus. Passer l'intro ne charge donc rien — ça retire un calque.
 *
 * ACCESSIBILITÉ. WCAG 2.2.2 (« Pause, Stop, Hide ») EXIGE un moyen de mettre en pause tout
 * mouvement automatique qui dure plus de cinq secondes. Dix-huit secondes sans pause ne sont
 * pas un choix de style, c'est un manquement — d'où le bouton et la barre d'espace. Et les
 * commandes ne sont PAS dans un `aria-hidden` : un bouton focusable à l'intérieur d'une
 * région masquée est atteignable au clavier mais invisible au lecteur d'écran, ce qui est
 * pire que pas de bouton du tout. Seul le décor est masqué.
 */
export function IntroSequence({ onFini }: { onFini?: () => void }) {
  const { jouer, reduit, rejeu } = useIntroGate();
  // Les chiffres viennent du snapshot, pas du code. Absents → les battements de
  // période se sautent d'eux-mêmes : l'intro raccourcit, elle n'invente pas.
  const { data: intro } = useIntro();
  const [monte, setMonte] = useState(false);
  const [sortie, setSortie] = useState(false);
  const [reveal, setReveal] = useState(false);
  const [pause, setPause] = useState(false);
  const [son, setSon] = useState(false);
  const [beat, setBeat] = useState<{ i: number; p: number }>({ i: 0, p: 0 });
  // Avancement partagé avec le HUD. Un état par frame serait 60 rendus React par
  // seconde ; on n'écrit que par pas de 1 % — invisible à l'œil, dix fois moins cher.
  const [avance, setAvance] = useState(0);
  const [attenteEcoulee, setAttenteEcoulee] = useState(false);
  const cvRef = useRef<HTMLCanvasElement>(null);
  const fini = useRef(false);
  // La boucle rAF est montée une seule fois : elle lit la pause par référence plutôt que
  // par dépendance, sinon chaque bascule la redémarrerait et l'intro repartirait de zéro.
  const enPause = useRef(false);
  const audio = useRef<IntroSon | null>(null);

  // Le rideau SE LÈVE tout de suite (sinon la landing apparaîtrait puis serait recouverte,
  // ce qui est exactement le clignotement que `useIntroGate` évite par ailleurs)…
  //
  // REJOUER, C'EST REPARTIR DE ZÉRO. `fini` est une RÉFÉRENCE : elle survit au premier
  // passage. Sans remise à zéro, le second se lancerait bien, mais `terminer()` ne ferait
  // plus rien à la fin — le rideau resterait baissé sur la landing, et il faudrait
  // recharger la page pour s'en sortir. `rejeu` est dans les dépendances parce que
  // `jouer` reste vrai d'un passage à l'autre et ne déclencherait donc jamais.
  useEffect(() => {
    if (!jouer) return;
    fini.current = false;
    setSortie(false);
    setReveal(false);
    setPause(false);
    setBeat({ i: 0, p: 0 });
    setAvance(0);
    setAttenteEcoulee(false);
    setMonte(true);
  }, [jouer, rejeu]);
  // …mais l'ANIMATION attend les chiffres, au plus `ATTENTE_DONNEES_MS`.
  useEffect(() => {
    if (!monte) return;
    const t = window.setTimeout(() => setAttenteEcoulee(true), ATTENTE_DONNEES_MS);
    return () => window.clearTimeout(t);
  }, [monte]);
  useEffect(() => { enPause.current = pause; }, [pause]);

  const terminer = useCallback(() => {
    if (fini.current) return;
    fini.current = true;
    marquerVue();
    setSortie(true);
    window.setTimeout(() => { setMonte(false); onFini?.(); }, SORTIE_MS);
  }, [onFini]);

  // Échap passe l'intro, Espace la met en pause : un rideau dont on ne peut ni sortir ni
  // arrêter le mouvement au clavier est un piège.
  useEffect(() => {
    if (!monte) return;
    const k = (e: KeyboardEvent) => {
      if (e.key === "Escape") terminer();
      if (e.key === " " || e.code === "Space") {
        const cible = e.target as HTMLElement | null;
        if (cible?.tagName === "BUTTON") return;   // le bouton gère déjà son propre espace
        e.preventDefault();
        setPause((v) => !v);
      }
    };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [monte, terminer]);

  // Le son n'existe QUE tant qu'il est demandé : coupé, le contexte est fermé, pas
  // seulement mis en sourdine — un contexte audio ouvert garde le matériel réveillé.
  useEffect(() => {
    if (!son) { audio.current?.fermer(); audio.current = null; return; }
    audio.current = creerSon();
    return () => { audio.current?.fermer(); audio.current = null; };
  }, [son]);
  useEffect(() => { if (!sortie) audio.current?.battement(beat.i); }, [beat.i, sortie]);
  useEffect(() => { if (reveal) audio.current?.final(); }, [reveal]);

  // Mouvement réduit : ni canvas ni phases — le nom, puis la landing.
  useEffect(() => {
    if (!monte || !reduit) return;
    setReveal(true);
    const t = window.setTimeout(terminer, 900);
    return () => window.clearTimeout(t);
  }, [monte, reduit, terminer]);

  // `intro` défini = la requête a répondu, disponible ou non. `undefined` = elle court
  // encore : c'est CE cas qu'on attend, pas une donnée absente (qu'on sait déjà afficher).
  const pret = intro !== undefined || attenteEcoulee;

  useEffect(() => {
    if (!monte || reduit || !pret) return;
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
      const ecoule = ts - precedent;
      precedent = ts;
      // EN PAUSE, on décale l'origine du même pas : le temps écoulé n'entre pas dans `t`,
      // donc rien n'avance. Repeindre quand même (avec `dt` nul) garde la toile correcte
      // après un redimensionnement, sans faire bouger une seule particule.
      if (enPause.current) t0 += ecoule;
      const t = Math.min(1, (ts - t0) / duree);
      const dt = enPause.current ? 0 : Math.min(0.05, ecoule / 1000);   // borné : un onglet
      scene.peindre(t, dt, pal);                                        // réveillé ne doit
      setAvance((a) => (Math.abs(t - a) > 0.008 ? t : a));              // pas téléporter le flux
      // Le DOM ne suit PAS le canvas image par image : on n'écrit l'état du battement que
      // lorsqu'il change, ou par pas de 1 % à l'intérieur. Un pas plus large hacherait le
      // compteur de `IntroBeats`, qui monte précisément sur cette valeur.
      setBeat((b) => {
        const n = scene.battement(t);
        return n.i !== b.i || Math.abs(n.p - b.p) > 0.01 ? { i: n.i, p: n.p } : b;
      });
      if (t >= PHASES.trades) setReveal(true);
      if (t >= 1) { terminer(); return; }
      raf = requestAnimationFrame(boucle);
    };
    raf = requestAnimationFrame(boucle);
    return () => { cancelAnimationFrame(raf); window.removeEventListener("resize", redim); };
  }, [monte, reduit, pret, terminer]);

  if (!monte) return null;
  return (
    <div className={s.overlay} data-sortie={sortie ? "1" : "0"} role="region"
         aria-label="Introduction animée">
      {!reduit && <canvas ref={cvRef} className={s.canvas} aria-hidden="true" />}
      {!reduit && !pret && (
        // L'attente se DIT. Un rideau noir muet pendant deux secondes se lit comme une
        // panne ; une ligne de terminal se lit comme un chargement.
        <div className={s.attente} aria-hidden="true">LECTURE DU SNAPSHOT…</div>
      )}
      {!reduit && pret && (
        <div className={s.decor} aria-hidden="true">
          <IntroBeats i={beat.i} p={beat.p} sortie={sortie} data={intro} />
        </div>
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
      <div className={s.controles}>
        {!reduit && (
          <>
            <button className={s.ctrl} onClick={() => setSon((v) => !v)}
                    aria-pressed={son}
                    aria-label={son ? "Couper le son de l'introduction"
                                    : "Activer le son de l'introduction"}>
              {son ? "SON ■" : "SON ▶"}
            </button>
            <button className={s.ctrl} onClick={() => setPause((v) => !v)}
                    aria-pressed={pause}
                    aria-label={pause ? "Reprendre l'introduction"
                                      : "Mettre l'introduction en pause"}>
              {pause ? "REPRENDRE ▶" : "PAUSE ❚❚"}
            </button>
          </>
        )}
        <button className={s.skip} onClick={terminer}
                aria-label="Passer l'introduction et entrer sur le site">
          PASSER →
        </button>
      </div>
    </div>
  );
}

export default IntroSequence;
