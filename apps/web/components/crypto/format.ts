// Formatage défensif du cockpit crypto — JAMAIS NaN/undefined à l'écran.
// « n/d » tant que la donnée manque : une absence doit se voir, pas se déguiser en zéro.
// Partagé entre la page et ses cartes depuis que celles-ci vivent dans des fichiers séparés.

export const usd = (x: any) =>
  typeof x === "number"
    ? x >= 1e12 ? `$${(x / 1e12).toFixed(2)} T`
      : x >= 1e9 ? `$${(x / 1e9).toFixed(1)} Md`
      : x >= 1e6 ? `$${(x / 1e6).toFixed(1)} M`
      : `$${x.toLocaleString("fr-FR", { maximumFractionDigits: 2 })}`
    : "n/d";

export const pct = (x: any, d = 1) =>
  typeof x === "number" ? `${x >= 0 ? "+" : ""}${x.toFixed(d)}%` : "n/d";

export const tone = (x: any) =>
  typeof x !== "number" ? undefined : x >= 0 ? "var(--pos)" : "#f43f5e";

// Liens vers les fiches OFFICIELLES (infos complètes, fiables, gratuites) — nouvel onglet.
export const cgCoin = (id?: string) =>
  id ? `https://www.coingecko.com/en/coins/${id}` : null;
export const cgCat = (id?: string) =>
  id ? `https://www.coingecko.com/en/categories/${id}` : null;
export const EXT = { target: "_blank", rel: "noopener noreferrer" } as const;
