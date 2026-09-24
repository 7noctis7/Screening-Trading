// Export des messages Discord VISIBLES à l'écran, vers le JSONL que `make x-ingest` lit.
//
// POURQUOI CETTE VOIE EXISTE. Lire un salon avec un bot demande qu'un ADMINISTRATEUR
// l'ait invité sur le serveur ; un salon d'annonces peut se suivre depuis son propre
// serveur, mais un salon ordinaire non. Quand ni l'un ni l'autre n'est possible, il
// reste ceci : vous êtes déjà membre, déjà connecté, déjà en train de lire la page.
// Ce script ne fait que recopier ce qui est AFFICHÉ.
//
// CE QU'IL NE FAIT PAS, ET C'EST LA DIFFÉRENCE QUI COMPTE. Il n'utilise pas votre jeton,
// n'appelle aucune API, ne fait défiler aucune page, ne tourne pas en boucle, n'ouvre
// aucune connexion. C'est ce qui sépare un presse-papier d'un « self-bot » — et c'est le
// self-bot, l'automatisation d'un compte utilisateur, que Discord détecte et sanctionne
// par le bannissement.
//
// ÉCHOUER FORT, JAMAIS EN SILENCE. Discord change ses classes CSS sans prévenir. Le jour
// où les sélecteurs ne correspondent plus, un script prudent rendrait « 0 message » — et
// ce zéro serait indiscernable d'un salon calme. Il AVERTIT en nommant la cause probable.
//
// LIMITE À CONNAÎTRE : Discord ne rend que les messages autour de la zone visible (liste
// virtualisée). L'export capture donc ce que vous avez FAIT DÉFILER, pas tout l'historique.
// Remonter puis réexporter complète le fichier — les identifiants étant stables, la
// réingestion ne duplique rien.
//
// Usage : ouvrir le salon, faire défiler jusqu'à ce qui vous intéresse, puis exécuter ce
// script (console du navigateur, ou marque-page — cf. `make x-export ARGS=--discord`).

(() => {
  // L'identifiant de la ligne porte le salon ET le message : chat-messages-<sal>-<msg>.
  // C'est la seule source stable des deux — l'ordre d'affichage, lui, change au défilement.
  const LIGNE = /^chat-messages-(\d+)-(\d+)$/;

  const auteur = (li) => {
    const n = li.querySelector('[id^="message-username-"] > span, h3 span[class*="username"]');
    return n ? n.innerText.trim() : "";
  };

  // Même raison que pour X : sur un salon de signaux, l'image PORTE le message. On
  // relève les adresses, jamais les fichiers — rien n'est téléchargé ni réhébergé.
  const visuels = (li) => [...li.querySelectorAll("img, a[data-role='img']")]
    .map((n) => n.getAttribute("src") || n.getAttribute("href") || "")
    .filter((s) => s.includes("cdn.discordapp.com") || s.includes("media.discordapp.net"))
    .map((s) => s.split("?")[0])
    .filter((s, i, tout) => tout.indexOf(s) === i);

  const lire = (li) => {
    const m = (li.id || "").match(LIGNE);
    const t = li.querySelector("time[datetime]");
    const corps = li.querySelector('[id^="message-content-"]');
    if (!m || !t) return null;
    const images = visuels(li);
    const texte = corps ? corps.innerText.trim() : "";
    if (!texte && images.length === 0) return null;   // ni propos ni visuel
    return {
      id: `discord:${m[1]}/${m[2]}`,
      compte: auteur(li) || `salon-${m[1]}`,
      ts: t.getAttribute("datetime"),
      texte: texte || `[${images.length} image(s) sans texte]`,
      url: `https://discord.com/channels/@me/${m[1]}/${m[2]}`,
      images,
    };
  };

  const lignes = [...document.querySelectorAll('li[id^="chat-messages-"]')];
  if (lignes.length === 0) {
    alert(
      "Aucun message trouvé sur cette page.\n\n" +
      "Soit le salon est vide à l'écran, soit Discord a changé son balisage et le " +
      "sélecteur `li[id^=\"chat-messages-\"]` ne correspond plus.\n\n" +
      "Ce message existe pour que les deux causes ne se confondent pas : un « 0 » " +
      "silencieux vous aurait laissé croire qu'il n'y avait rien à lire.");
    return;
  }

  // L'auteur n'est rendu que sur le PREMIER message d'un groupe : Discord masque le nom
  // sur les suivants du même auteur. Sans report, ces messages partiraient sans compte.
  const vues = new Map();
  let dernier = "";
  for (const li of lignes) {
    const p = lire(li);
    if (!p) continue;
    if (p.compte.startsWith("salon-") && dernier) p.compte = dernier;
    else dernier = p.compte;
    vues.set(p.id, p);
  }

  const contenu = [...vues.values()].map((p) => JSON.stringify(p)).join("\n");
  const blob = new Blob([contenu + "\n"], { type: "application/x-ndjson" });
  const lien = document.createElement("a");
  lien.href = URL.createObjectURL(blob);
  lien.download = "x_posts.jsonl";
  lien.click();
  URL.revokeObjectURL(lien.href);

  console.log(`${vues.size} message(s) exporté(s) sur ${lignes.length} bloc(s) visibles.`
    + " Discord ne rend que la zone visible : remonter puis réexporter complète le fichier.");
})();
