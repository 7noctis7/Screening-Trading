// La couleur d'une LIGNE COMPARÉE, déclarée UNE fois.
//
// POURQUOI CE FICHIER EXISTE (18/09). Trois endroits nommaient les mêmes séries avec des
// teintes différentes : les deux graphes lisaient les tokens de thème, et le tableau
// « Comparé aux grands indices » codait en dur `S&P 500 → ambre`, tout le reste → violet.
// Le S&P était donc gris sur la courbe et ambre dans le tableau, le CAC jaune ici et
// violet là. Une pastille d'une autre teinte que sa ligne oblige à retrouver la
// correspondance à chaque lecture — et fait douter du chiffre plutôt que de la couleur.
//
// LES TEINTES SONT DES TOKENS DE THÈME (globals.css), jamais des littéraux : codées en
// dur, elles gardent la même valeur en clair et en sombre, où le contraste n'est pas le
// même. Ajouter une référence = une entrée ici et un token dans les DEUX thèmes ; un test
// vérifie que `REFERENCES` et cette table ne divergent pas.
//
// LES CLÉS SONT TOUTES ENTRE GUILLEMETS, même celles qui s'en passeraient :
// `Bitcoin:` et `"Bitcoin":` se lisent pareil en JS et PAS pareil à la relecture
// automatique — une entrée non citée a échappé au test qui garde cette table.
export const COULEUR_LIGNE: Record<string, string> = {
  // Le portefeuille et ses deux lectures — simulée et réelle.
  "Portefeuille": "var(--accent)",
  "Portefeuille simulé (stratégie)": "var(--accent)",
  "Portefeuille RÉEL (vos comptes)": "var(--ok)",
  // Les références de `packages/portfolio/comparaison_benchmark.REFERENCES`.
  "S&P 500": "var(--bench-sp)",
  "Nasdaq 100": "var(--bench-ndx)",
  "Bitcoin": "var(--bench-btc)",
  "CAC 40": "var(--bench-cac)",
  // Les deux poches réelles, sur « Mes comptes réels face aux indices ».
  "Alpaca (réel)": "var(--accent)",
  "Crypto (réel)": "var(--poche-crypto)",
};

/** La teinte d'une ligne, ou le gris neutre — jamais une couleur inventée qui
 *  ressemblerait à celle d'une autre série. */
export const couleurLigne = (nom: string) => COULEUR_LIGNE[nom] ?? "var(--muted)";
