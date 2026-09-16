"use client";
import { useEffect, useState } from "react";
import { ENABLE_INTRO, INTRO_SESSION_POLICY } from "./introConfig";

const CLE = "qt:intro:vu";
const JOUR_MS = 86_400_000;

/** Le navigateur demande-t-il moins d'animation ? */
export function motionReduit(): boolean {
  if (typeof window === "undefined") return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/** Machine modeste ? Sert à réduire le nombre de particules, jamais à couper l'intro. */
export function machineModeste(): boolean {
  if (typeof navigator === "undefined") return false;
  const coeurs = (navigator as { hardwareConcurrency?: number }).hardwareConcurrency ?? 8;
  const memoire = (navigator as { deviceMemory?: number }).deviceMemory ?? 8;
  return coeurs <= 4 || memoire <= 4;
}

/** Forçage par l'URL : `?intro=1` rejoue, `?intro=0` saute. `null` = rien de demandé.
 *
 *  POURQUOI C'EST NÉCESSAIRE. La politique « session » ne joue l'intro qu'une fois par
 *  onglet — ce qui est le bon comportement pour un visiteur, et un enfer pour qui la
 *  RÈGLE : chaque essai demande un nouvel onglet, et on finit par croire qu'un correctif
 *  n'a pas pris alors qu'on regarde une page qui n'a simplement pas rejoué. */
export function forcageUrl(): boolean | null {
  if (typeof window === "undefined") return null;
  const v = new URLSearchParams(window.location.search).get("intro");
  if (v === "1" || v === "true") return true;
  if (v === "0" || v === "false") return false;
  return null;
}

/** Une demande de rejeu EN ATTENTE, au niveau du module.
 *
 *  POURQUOI PAS UN SIMPLE ÉVÉNEMENT. Cliquer la marque depuis `/trades` déclenche une
 *  navigation : le rideau n'est pas encore monté quand le clic part, donc personne
 *  n'écoute. Un état de module survit à la navigation côté client (même bundle, aucun
 *  rechargement) et se fait consommer par le rideau quand IL arrive. L'événement sert
 *  l'autre cas — on est DÉJÀ sur la landing, et il n'y a pas de navigation du tout. */
let rejeuEnAttente = false;
const abonnes = new Set<() => void>();

/** Rejouer le rideau, depuis n'importe où. Efface d'abord la marque « déjà vu ». */
export function rejouerIntro(): void {
  try {
    sessionStorage.removeItem(CLE);
    localStorage.removeItem(CLE);
  } catch {
    /* stockage indisponible : le rejeu marche quand même, il ne dépend que du drapeau */
  }
  rejeuEnAttente = true;
  abonnes.forEach((prevenir) => prevenir());
}

function dejaVu(): boolean {
  try {
    if (INTRO_SESSION_POLICY === "always") return false;
    if (INTRO_SESSION_POLICY === "never") return true;
    if (INTRO_SESSION_POLICY === "session") return sessionStorage.getItem(CLE) === "1";
    const t = Number(localStorage.getItem(CLE) || 0);
    return Number.isFinite(t) && Date.now() - t < JOUR_MS;
  } catch {
    return false;      // stockage refusé (navigation privée) → on joue, sans insister
  }
}

/** Marque l'intro comme vue, selon la politique en vigueur. */
export function marquerVue(): void {
  try {
    if (INTRO_SESSION_POLICY === "session") sessionStorage.setItem(CLE, "1");
    else if (INTRO_SESSION_POLICY === "day") localStorage.setItem(CLE, String(Date.now()));
  } catch {
    /* stockage indisponible : l'intro rejouera, ce qui est préférable à une erreur */
  }
}

/** `rejeu` s'incrémente à chaque demande : c'est LUI qui relance un rideau déjà joué,
 *  puisque `jouer` reste vrai et ne changerait donc plus de valeur. */
export type Etat = { jouer: boolean | null; reduit: boolean; rejeu: number };

/**
 * Faut-il jouer l'intro ? `null` tant qu'on ne sait pas.
 *
 * La décision est prise APRÈS le montage, jamais au rendu serveur : `sessionStorage` et
 * `prefers-reduced-motion` n'existent pas côté serveur, et un export statique sert le même
 * HTML à tout le monde. Rendre l'intro au SSR produirait un flash chez qui l'a déjà vue.
 */
export function useIntroGate(): Etat {
  const [etat, setEtat] = useState<Etat>({ jouer: null, reduit: false, rejeu: 0 });
  useEffect(() => {
    // Le drapeau est consommé HORS du `setEtat` : en mode strict, React invoque deux
    // fois la fonction de mise à jour, et un effet de bord glissé dedans se jouerait
    // — ou se perdrait — une fois de trop.
    const decider = () => {
      const demande = rejeuEnAttente;
      rejeuEnAttente = false;
      const force = forcageUrl();
      const jouer = demande || (force !== null ? force : ENABLE_INTRO && !dejaVu());
      setEtat((p) => ({ jouer, reduit: motionReduit(),
                        rejeu: demande ? p.rejeu + 1 : p.rejeu }));
    };
    decider();
    abonnes.add(decider);
    return () => { abonnes.delete(decider); };
  }, []);
  return etat;
}
