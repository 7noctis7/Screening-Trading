// Export des publications X VISIBLES à l'écran, vers le JSONL que `make x-ingest` lit.
//
// POURQUOI CETTE VOIE EXISTE. Le palier gratuit de l'API X ne permet pas de lire. Les
// miroirs RSS le permettent mais meurent régulièrement — ils dépendent du bon vouloir de
// X. Cette voie-ci ne dépend de personne : vous êtes déjà connecté, vous regardez déjà
// la page ; ce script ne fait que recopier ce qui est AFFICHÉ dans un fichier.
//
// CE QU'IL NE FAIT PAS, ET C'EST VOULU : il ne fait défiler aucune page, n'ouvre aucun
// onglet, n'appelle aucune API interne, ne tourne pas en boucle. Il lit l'écran à
// l'instant où vous cliquez. Un outil qui parcourt X tout seul est un robot ; celui-ci
// est un presse-papier.
//
// ÉCHOUER FORT, JAMAIS EN SILENCE. X change son balisage sans prévenir. Le jour où les
// sélecteurs ne correspondent plus, un script prudent rendrait « 0 publication » — et ce
// zéro serait indiscernable d'une page vide. Il AVERTIT donc explicitement, en nommant la
// cause probable, plutôt que de laisser croire qu'il n'y avait rien à lire.
//
// Usage : ouvrir le profil ou la liste, faire défiler pour charger ce qui vous intéresse,
// puis exécuter ce script (console du navigateur, ou marque-page — cf. `make x-export`).

(() => {
  const ARTICLES = 'article[data-testid="tweet"]';
  const TEXTE = '[data-testid="tweetText"]';

  // Le lien canonique porte le compte ET l'identifiant : /<compte>/status/<id>.
  // C'est la seule source des deux qui reste juste pour un repost comme pour un
  // message d'origine — le nom affiché en tête, lui, est celui de qui a reposté.
  const LIEN = /^\/([A-Za-z0-9_]{1,15})\/status\/(\d+)/;

  const lire = (article) => {
    const t = article.querySelector("time[datetime]");
    const a = [...article.querySelectorAll('a[href*="/status/"]')]
      .map((x) => x.getAttribute("href"))
      .map((h) => (h || "").match(LIEN))
      .find(Boolean);
    const corps = article.querySelector(TEXTE);
    if (!a || !t || !corps) return null;
    return {
      id: `https://x.com/${a[1]}/status/${a[2]}`,
      compte: a[1],
      ts: t.getAttribute("datetime"),
      texte: corps.innerText.trim(),
      url: `https://x.com/${a[1]}/status/${a[2]}`,
    };
  };

  const articles = [...document.querySelectorAll(ARTICLES)];
  if (articles.length === 0) {
    alert(
      "Aucun bloc de publication trouvé sur cette page.\n\n" +
      "Soit la page n'en contient pas, soit X a changé son balisage et le sélecteur " +
      "`article[data-testid=\"tweet\"]` ne correspond plus.\n\n" +
      "Ce message existe pour que les deux causes ne se confondent pas : un « 0 » " +
      "silencieux vous aurait laissé croire qu'il n'y avait rien à lire.");
    return;
  }

  // Dédoublonnage par identifiant : X réutilise des blocs en recyclant le DOM pendant
  // le défilement, et la même publication peut apparaître deux fois.
  const vues = new Map();
  for (const art of articles) {
    const p = lire(art);
    if (p) vues.set(p.id, p);
  }

  const lignes = [...vues.values()].map((p) => JSON.stringify(p)).join("\n");
  const ignores = articles.length - vues.size;

  const blob = new Blob([lignes + "\n"], { type: "application/x-ndjson" });
  const lien = document.createElement("a");
  lien.href = URL.createObjectURL(blob);
  lien.download = "x_posts.jsonl";
  lien.click();
  URL.revokeObjectURL(lien.href);

  console.log(`${vues.size} publication(s) exportée(s)`
    + (ignores > 0 ? ` · ${ignores} bloc(s) ignoré(s) (doublons ou sans texte)` : ""));
})();
