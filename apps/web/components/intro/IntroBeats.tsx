"use client";
import s from "./intro.module.css";
import { BEATS } from "./introConfig";

/**
 * Les mots de l'intro, rendus par le DOM — pas par le canvas.
 *
 * À cette taille, du texte canvas est plus flou (rastérisé au DPR, sans hinting), ignore la
 * police du site et ne se sélectionne pas. Le canvas fait le MOUVEMENT ; le DOM fait les
 * MOTS. C'est aussi ce qui permet aux chiffres d'hériter de la charte typographique sans
 * la recopier.
 *
 * Un seul battement est monté à la fois : pas de pile de nœuds cachés qui grossit.
 */
export function IntroBeats({ i, p, sortie }: { i: number; p: number; sortie: boolean }) {
  const b = BEATS[i];
  if (!b || !b.chiffre) return null;
  // Entrée franche, sortie anticipée : le texte part AVANT la fin du battement pour que le
  // suivant ne le heurte pas. Sans ce recouvrement, dix secondes donnent quatre saccades.
  const on = p > 0.04 && p < 0.88 && !sortie;
  return (
    <div className={s.beat} data-on={on ? "1" : "0"} key={b.cle} aria-hidden="true">
      <div className={s.beatSur}>{b.sur}</div>
      <div className={s.beatNum}>{b.chiffre}</div>
      <div className={s.beatUnite}>{b.unite}</div>
      <div className={s.beatSous}>{b.sous}</div>
    </div>
  );
}

export default IntroBeats;
