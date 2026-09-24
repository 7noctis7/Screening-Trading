// Le MÊME filtrage que `packages/social/filtres.py`, côté navigateur.
//
// POURQUOI DEUX FOIS. Le site est publié en STATIQUE (GitHub Pages, sans API) : là-bas
// il n'y a aucun serveur pour filtrer. Et même avec l'API, refaire un aller-retour à
// chaque lettre tapée rendrait la recherche poussive. Le navigateur reçoit donc la liste
// une fois et filtre en mémoire — instantané, et identique en ligne comme en local.
//
// La contrepartie est réelle : deux implémentations peuvent diverger en silence. Elles
// partagent donc une sémantique ÉCRITE, tenue des deux côtés, et c'est le module Python
// qui fait foi (il est testé sur les mêmes exemples) :
//   · une sélection vide veut dire TOUS, jamais aucun ;
//   · la recherche ignore la casse ET les accents (contenu bilingue) ;
//   · plusieurs mots se combinent en ET, ce n'est pas une phrase exacte ;
//   · elle porte sur texte, ticker, symbole, classification, direction et niveaux.

export type Publication = {
  id: string; compte: string; ts: string; texte: string;
  classification: string; ticker: string | null; symbole: string | null;
  direction: string | null; extraits: Record<string, number>; url: string | null;
  images?: string[];
};

export type Criteres = {
  comptes: string[]; requete: string; classifications: string[];
  directions: string[]; symboles: string[];
};

export const CRITERES_VIDES: Criteres = {
  comptes: [], requete: "", classifications: [], directions: [], symboles: [],
};

// Minuscules + accents retirés : « resistance » doit trouver « résistance ».
export const normaliser = (s: string) =>
  s.toLowerCase().normalize("NFD").replace(/\p{Mn}/gu, "");

// « 65000 » doit retrouver un niveau stocké 65000.0 — donc les deux écritures.
const nombre = (v: number) => (Number.isInteger(v) ? `${v} ${v}.0` : `${v}`);

function champsCherchables(p: Publication): string[] {
  const champs = [p.texte, p.classification];
  if (p.ticker) champs.push(p.ticker);
  if (p.symbole) champs.push(p.symbole);
  if (p.direction) champs.push(p.direction);
  for (const [cle, val] of Object.entries(p.extraits ?? {})) {
    champs.push(cle);
    if (typeof val === "number") champs.push(nombre(val));
  }
  return champs;
}

export function contient(p: Publication, requete: string): boolean {
  const mots = normaliser(requete).split(/\s+/).filter(Boolean);
  if (mots.length === 0) return true;
  const foin = champsCherchables(p).map(normaliser).join(" \u0000 ");
  return mots.every((m) => foin.includes(m));
}

// Un critère vide laisse TOUT passer. Une valeur absente ne passe que si le critère
// est vide — une publication sans direction n'est ni LONG ni SHORT.
const dans = (valeur: string | null, choix: string[]) =>
  choix.length === 0 ? true
    : valeur === null ? false
    : choix.some((c) => normaliser(c) === normaliser(valeur));

export const actif = (c: Criteres) =>
  c.comptes.length > 0 || c.requete.trim() !== "" || c.classifications.length > 0 ||
  c.directions.length > 0 || c.symboles.length > 0;

export function appliquer(pubs: Publication[], c: Criteres): Publication[] {
  return pubs
    .filter((p) =>
      dans(p.compte, c.comptes) &&
      dans(p.classification, c.classifications) &&
      dans(p.direction, c.directions) &&
      dans(p.symbole, c.symboles) &&
      contient(p, c.requete))
    .sort((a, b) => (a.ts < b.ts ? 1 : a.ts > b.ts ? -1 : 0));
}

// Bascule une valeur dans une sélection multiple (clic = cocher / décocher).
export const basculer = (liste: string[], v: string) =>
  liste.includes(v) ? liste.filter((x) => x !== v) : [...liste, v];
