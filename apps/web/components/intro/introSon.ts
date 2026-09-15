// Son de l'intro — OPT-IN, jamais automatique, jamais persisté.
//
// POURQUOI PAS DE PERSISTANCE. Mémoriser « son activé » ferait démarrer la visite suivante
// avec du son sans qu'on l'ait demandé CETTE fois. Les navigateurs l'interdiraient de toute
// façon sans geste préalable ; plutôt qu'un réglage qui marche une fois sur deux selon
// l'historique d'interaction, le son se demande à chaque intro. L'intro ne joue qu'une fois
// par session : c'est un clic, pas une corvée.
//
// Le contexte audio est créé DANS le gestionnaire de clic — c'est ce geste qui lève la
// politique d'autoplay. Créé au chargement, il naîtrait suspendu et resterait muet.

export type IntroSon = {
  battement(i: number): void;
  final(): void;
  fermer(): void;
};

/** Degrés d'une pentatonique mineure : aucun intervalle ne peut sonner faux avec un autre,
 *  donc deux battements qui se chevauchent restent consonants quoi qu'il arrive. */
const DEGRES = [0, 3, 5, 7, 10, 12, 14, 15, 19];
const RACINE = 220;                     // la3 — sous la voix, au-dessus du grondement
const VOLUME = 0.07;                    // présent à l'écoute, jamais couvrant

const hauteur = (demi: number) => RACINE * Math.pow(2, demi / 12);

/** `null` si le navigateur n'a pas d'API audio : l'intro continue, muette. */
export function creerSon(): IntroSon | null {
  const W = window as unknown as { AudioContext?: typeof AudioContext; webkitAudioContext?: typeof AudioContext };
  const AC = W.AudioContext || W.webkitAudioContext;
  if (!AC) return null;
  let ctx: AudioContext;
  try {
    ctx = new AC();
  } catch {
    return null;                        // contexte refusé (quota, politique) → silence
  }
  void ctx.resume();

  const maitre = ctx.createGain();
  maitre.gain.value = VOLUME;
  maitre.connect(ctx.destination);

  /** Une note : attaque courte, extinction exponentielle. Pas de release linéaire —
   *  elle produit un clic audible à la coupure. */
  const note = (freq: number, t: number, duree: number, gain: number) => {
    const o = ctx.createOscillator();
    const g = ctx.createGain();
    o.type = "sine";
    o.frequency.value = freq;
    g.gain.setValueAtTime(0.0001, t);
    g.gain.linearRampToValueAtTime(gain, t + 0.014);
    g.gain.exponentialRampToValueAtTime(0.0001, t + duree);
    o.connect(g);
    g.connect(maitre);
    o.start(t);
    o.stop(t + duree + 0.02);
  };

  return {
    // Un battement = une note qui MONTE d'un battement à l'autre. La progression seule
    // raconte l'avancement : on entend qu'on approche de la fin sans regarder la barre.
    battement(i: number) {
      const d = DEGRES[Math.min(Math.max(0, i), DEGRES.length - 1)];
      const t = ctx.currentTime;
      note(hauteur(d), t, 0.85, 0.55);
      note(hauteur(d + 12), t, 0.4, 0.14);   // harmonique : du timbre, pas une seconde voix
    },
    // Accord arpégé sur le nom. Quatre notes en 180 ms : une résolution, pas une fanfare.
    final() {
      const t = ctx.currentTime;
      [0, 7, 12, 19].forEach((d, k) => note(hauteur(d), t + k * 0.06, 2.4, 0.3));
    },
    fermer() {
      try {
        void ctx.close();
      } catch {
        /* déjà fermé — rien à faire */
      }
    },
  };
}
