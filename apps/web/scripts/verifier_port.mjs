#!/usr/bin/env node
/**
 * Refuse de démarrer si le port de développement est déjà pris.
 *
 * POURQUOI CE GARDE EXISTE. `next dev` bascule SILENCIEUSEMENT sur 3001 quand 3000 est
 * occupé — il l'écrit sur une ligne, au milieu du démarrage, et personne ne la lit. On
 * ouvre alors `localhost:3000`, qui répond… servi par L'AUTRE processus : le service
 * `quant-web` sur le VPS, ou un `next-server` orphelin d'une session SSH morte. Le code
 * est juste, l'écran montre autre chose, et rien ne le signale.
 *
 * Mesuré le 16/09 : une intro corrigée et rebâtie restait « absente » parce que le
 * navigateur parlait au service de PRODUCTION sur 3000 pendant que le serveur de
 * développement venait de naître sur 3001. Même famille que le cache `.next` qui ressert
 * l'ancien rendu (CLAUDE.md) : un basculement silencieux coûte plus qu'une erreur.
 */
import { createServer } from "node:net";

const port = Number(process.env.PORT || 3000);

const libre = await new Promise((resolve) => {
  const s = createServer();
  s.once("error", () => resolve(false));
  s.once("listening", () => s.close(() => resolve(true)));
  s.listen(port, "127.0.0.1");
});

if (libre) process.exit(0);

console.error(`\n✗ Le port ${port} est DÉJÀ PRIS.`);
console.error("  `next dev` basculerait en silence sur un autre port, et le navigateur");
console.error(`  continuerait de parler au processus qui tient ${port} — pas à celui-ci.\n`);
console.error("  Qui le tient :");
console.error(`      ss -tanp 'sport = :${port}'    (sudo pour voir le PID d'un autre compte)`);
console.error("  Si c'est le service du VPS, la bonne commande n'est pas `npm run dev` :");
console.error("      make up           # arrête les services, tue les orphelins, rebâtit\n");
console.error("  Pour développer À CÔTÉ du service, choisir un port et le DIRE :");
console.error("      PORT=3001 npm run dev     puis  ssh -L 3001:localhost:3001 …\n");
process.exit(1);
