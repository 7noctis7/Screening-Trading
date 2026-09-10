# 04 — JOURNAL

## Session 2026-09-10 — Un bug inventé, un bug trouvé

**J'ai signalé hier un bug qui n'existe pas.** `fast_swing` marque bien tous les symboles
à chaque barre (`fast_swing.py:182-185`) ; j'avais lu la boucle de sortie sans voir celle
d'avant. Demandé de le corriger, j'ai d'abord vérifié — et il n'y avait rien à corriger.

**Mais la vérification en a trouvé un vrai.** `_sortie` rend un prix de stop ou de cible ;
`broker.submit` encaissait au dernier prix marqué, la clôture. **150 $ d'écart sur un seul
trade, à coûts nuls** — mesuré, pas déduit. Toute sortie par stop ou cible était
concernée. Corrigé dans les deux moteurs.

**Estimation marquée (décision utilisateur).** `broker_charge()` estime commission +
réglementaire **sans slippage**, et le journal porte `fees_source="estimated"`. Nouveau
champ, migration additive : le schéma ne faisait que `CREATE TABLE IF NOT EXISTS`, un
INSERT sur colonne neuve aurait cassé la journalisation de production sans un bruit.

**Déduplication livrée, fail-closed.** `make dedupliquer-journal` — simulation par défaut,
sauvegarde horodatée, et une ligne `-R` n'est supprimée QUE si sa base existe avec une
économie identique au centime. Tout le reste est conservé et signalé.

**Limite assumée.** L'estimation crypto utilise le barème BitMart (25 bps) alors que le
crypto est tradé sur Alpaca : elle est majorée. Marquée `estimated`, révisable dès que le
vrai taux est connu — je ne l'invente pas.

**Mesuré.** 2 531 passés (+23), certification et contracts verts.

## Session 2026-09-09 (28ᵉ) — P0-1 : le coût existait, personne ne le portait

**Fait.** Audit puis réparation de l'instrumentation des coûts. Objet `Fill` (domaine),
`packages/execution/fills.py` (convention unique), `SimBroker` émetteur de fills, les
deux moteurs de backtest câblés, production rendue honnête, `turnover_audit` qui
distingue « mesuré » de « jamais renseigné ». **33 tests ajoutés — 2 508 au vert.**

**Ce que la donnée réelle a corrigé, deux fois.**
1. Mon diagnostic disait « le coût du turnover n'est pas compté ». Faux pour le
   slippage : il est déjà dans les prix de fill, donc déjà dans le P&L. La seule fuite
   est la commission. J'ai failli faire retrancher deux fois le même coût.
2. Le « slippage moyen de 12 bps » mesuré sur le journal n'existe pas : **15 doublons
   sur 66**, dont un AAVE triplé (`-R1`, `-R2`, suffixes posés par un script de
   réparation qui contourne l'identifiant déterministe). Dédupliqué : **−0,16 bps**. Le
   signe s'inverse. Ces suffixes échappent aussi au regroupement `-X` de
   `turnover_audit` : ils comptent comme des positions distinctes, donc P0-2 mesurait un
   journal contaminé.

**Un test m'a corrigé.** `shortfall_amount` doit se rapporter au notionnel de RÉFÉRENCE :
sur celui du fill, +5 bps rendait 0,50025 $ au lieu de 0,50 $. Le test avait raison.

**Mesuré, après.** Aller-retour de 5 000 $ à +2 % : commission 2,02 $ en actions, 1,51 $
en ETF, **10,10 $ en crypto** — soit 12 % du gain brut, jusqu'ici invisible.

**Trouvé en passant (HORS SCOPE).** `SimBroker.equity()` marque les positions ouvertes au
dernier prix VU, que la boucle de sortie de `fast_swing` ne rafraîchit jamais. L'equity de
backtest est marquée à des prix périmés — donc le vol-targeting aussi. Consigné, non
corrigé.

**Suite.** P0-1 câblé et testé ; reste à décider la politique d'estimation des
commissions en production (modèle documenté vs `None`), et la déduplication du journal.

## Session 2026-09-09 (27ᵉ) — La vitrine annonçait trois nombres de tests différents

**Fait.** README réécrit et `docs/COMMANDES.md` créé (référence des 125 cibles `make`, groupées
par intention, avec les variables d'environnement). Cible `make help` ajoutée : la convention
`##` du Makefile existait depuis toujours mais rien ne l'exposait.

**Ce que l'état des lieux a trouvé.** Le README annonçait **825 tests** dans son badge, **825**
dans le texte et **1160** dans « État du projet ». Le vrai chiffre est **2 475**. Trois nombres
faux dans un même fichier, dont deux se contredisent : la vitrine du dépôt public avait dérivé
sans que rien ne le signale.

**Deux affirmations que j'allais reprendre sans vérifier.** J'avais écrit « PAPER TRADING READY
✅ » sur la foi du cron vert de ce soir — or `docs/ROADMAP.md` porte encore **P0-3 ouvert**, et
sa propre règle de lecture dit qu'un P0 ouvert interdit ce verdict. Et j'avais recopié « le test
de biais du survivant ne mesure rien », alors que **P0-2 est fermé depuis le 25/08**. Les deux
corrigées après lecture de la source. Reprendre le texte d'un ancien README est exactement le
même défaut que reprendre un agrégat d'un autre contexte (ADR-0129) : ça a l'air vérifié parce
que c'était écrit.

**Chiffres publiés, tous re-mesurés** : 381 modules, 351 fichiers de test, 41 routes API, 28
pages front, 129 ADR, 125 cibles `make`, 121 scripts.

**Anonymisation.** Le dépôt suivi était déjà propre — aucune IP, aucun hostname, aucun email,
que des placeholders. Les nouveaux fichiers ont été passés au même filtre (chemins, adresses,
montants de compte) : rien. La section Sécurité l'énonce désormais explicitement.

**Limites connues réécrites** pour dire ce que le projet ne sait PAS faire, dont le coût du
turnover non instrumenté (colonnes `fees`/`slippage` jamais alimentées par l'exécution) mesuré
ce soir.

**Suite.** 2 475 passés, 7 ignorés. Vault lint vert.

## Session 2026-09-09 (26ᵉ) — Le premier appel réel a montré un chiffre sans référent

**Fait.** Services relancés sur le VPS (`make up`, build `ce52253`). Premier appel réel de
`/api/portfolio/sentiment` : chemin complet vert — `couverture_news: 1.0`, 12 titres sur
AAPL, `poids_mesure: 1.0`. **Mais `mood_change: -0.1979` était faux.**

**Le défaut.** `history.mood_delta` soustrait la moyenne des scores REÇUS à la moyenne des
scores HISTORISÉS — l'historique étant celui du robot, sur SES positions. Pour un
portefeuille tiers, ça soustrait deux paniers sans rapport. Corrigé par
`_revision_ponderee` : chaque actif comparé à SON propre passé, puis pondéré comme
l'humeur ; les lignes sans historique exclues et comptées (`n_revisions`). Sans ligne
comparable, `mood_change` vaut `None` — inconnu, pas nul (ADR-0129).

**Ce que ça dit de ma méthode.** Aucun de mes tests ne l'attrapait : tous partageaient un
historique cohérent avec le portefeuille testé. C'est la sortie réelle, lue sur la machine,
qui l'a montrée — le chiffre était plausible, jamais aberrant. Un agrégat repris d'un autre
contexte doit être re-justifié dans le nouveau, pas seulement re-testé.

**Aussi.** Correction du `QUANT_NEWS=1` que j'avais mis en préfixe de `make start` :
`scripts/env_quant.sh:11` le met déjà à `1`, et `svc_api.sh` le source — les news étaient
déjà actives. Un import inutilisé (`timezone`), laissé par un correctif automatique dans
`ce52253`, supprimé.

**Mesuré.** Suite : **2 475 passés, 7 ignorés** (+3). Sabotage vérifié : rebrancher
`mood_delta` fait tomber le nouveau test. Build Next OK. `engine: "lexique"` sur le VPS —
FinBERT n'est pas installé, les scores viennent de la liste de mots-clés.

## Session 2026-09-09 (25ᵉ) — Le sentiment du capital, pas celui des lignes

**Fait.** « Pouls du portefeuille » livré dans *Analyser mon portefeuille* : sentiment &
actualités du portefeuille IMPORTÉ, pondérés par ses poids. Nouveau module
`packages/sentiment/portefeuille.py`, route locale `POST /api/portfolio/sentiment`,
panneau `SentimentPulse` + primitives `SentimentJauge` (jauge à aiguille, barres signées,
filtre segmenté avec compteurs, cartes dépliables sur les titres, fils macro/marché).
L'onglet `/sentiment` du robot est inchangé — c'était la demande.

**Ce que la mesure a corrigé dans ma conception.** L'onglet existant moyenne à **poids
égal**. Sur un portefeuille dont on connaît les poids, ça décrit un portefeuille que
personne ne détient. Les deux humeurs sont donc affichées, et leur **écart** est publié :
il dit si le pessimisme est sur les grosses lignes ou sur les miettes.

**Le piège qui n'était pas dans la demande.** `/api/portfolio/*` promet « aucune
persistance » ; `history.record_and_delta` **écrit**. Un portefeuille de passage aurait
pollué `sentiment_history.json` avec des symboles que le robot ne détient pas, faussant le
Δ du lendemain **dans l'onglet du robot** — invisible depuis la page fautive.
`history.delta` (lecture seule) extrait ; deux gardes (source + comportement), vérifiées
par sabotage : les deux tombent quand on remet l'écriture.

**Trouvé en passant.** Le repli momentum 63 j était recopié **deux fois** en dur dans
`snapshot.py` : remplacé par un appel unique, avec un test qui interdit la recopie.
`PortfolioSynergies.tsx` portait un second `return` **inatteignable** (JSX dupliqué) :
supprimé. La barre d'humeur de `/sentiment` avait un fond `#1d212a` en dur, illisible en
thème clair — même défaut que les couleurs de benchmark de ce matin, passé en jeton.

**Mesuré.** Cas le pire (aucune base de prix, `QUANT_NEWS` absent) : `mood: null`,
`poids_non_mesure: 1.0`, libellé « non mesuré ». Rien n'est inventé, et la page le dit.
Suite : **2 472 passés, 7 ignorés** (+19). `make certification` vert, dette inchangée
(1 479 l.). Build Next OK, `tsc` sans erreur nouvelle.

**Suite.** P1 secteurs GICS (`make hf-pull`), P2 armer le disjoncteur, P2 `chmod 600
models/*.pkl`, P2 backlog `ruff` du dépôt (line-length 88 vs style réel ~100).

## Session 2026-09-09 (24ᵉ) — Le correctif était déjà écrit, ailleurs

**22/22 NOTES, ZÉRO PLANTAGE.** Le filtre crypto tient. Mais deux pages Yahoo complètes
inondaient encore le terminal — pour IBM et NKE, deux vraies sociétés : des 502 transitoires,
donc un autre défaut.

**LE PROBLÈME N'EST PAS L'ERREUR, C'EST SON VOLUME.** yfinance ne journalise pas un échec, il
DÉVERSE la page du serveur : cent lignes de « sad panda » au milieu de la liste des notes. Un
502 transitoire est sans conséquence ; ce qui coûte, c'est que les lignes utiles se perdent.

**ET LE CORRECTIF EXISTAIT.** `dump_static.py` silence `yfinance`/`urllib3`/`peewee` depuis
un moment, avec le commentaire « yfinance dumpe des pages HTML ». Connu, résolu dans un
script, absent de l'autre qui appelle les mêmes fournisseurs.

**LE TEST QUI COMPTE.** Pas celui du silence — celui qui exige que les DEUX scripts batch
portent la précaution. Une correction ponctuelle répare un cas ; une convention vérifiée
répare la classe.

**2453 tests passés, 2 ajoutés.** ADR-0127.

## Session 2026-09-09 (23ᵉ) — Le banc a tranché

**2 169 TRADES SUR DONNÉES RÉELLES.** −0,059 R par trade, 26,8 % de réussite, −127,9 R au
total, DSR **0,0001** pour un seuil de 0,95. **Le swing ICT ne se branche pas.**

**LA NUANCE QUI COMPTE.** Gain moyen 2,51 R → équilibre à 28,5 % de réussite ; on observe
26,8 %. **1,7 point**, soit ~37 trades sur 2 169. Et ma règle la plus conservatrice — stop
prioritaire quand stop et cible tombent dans la même barre — porte exactement sur ces cas.
C'est donc une BORNE INFÉRIEURE. Dire « la stratégie est nulle » irait plus loin que la
mesure ; dire « elle ne franchit pas la porte » est exact.

Les coûts ne sont pas modélisés — ils ne peuvent qu'enfoncer le résultat. Ce qui trancherait
définitivement : des barres intraday.

**DEUX BUGS DE `make reports` AU MÊME RUN.** ZEC/USDC, VET/USDC et LTC/USDC envoyés à Yahoo
pour une analyse FONDAMENTALE — trois 500/502 dont la page HTML entière a inondé le
terminal — puis plantage sur `note_ZEC/USDC.html`, un chemin vers un dossier inexistant.
22 notes sur 25. Corrigé : une paire cotée n'a pas de bilan donc pas de note, et le nom de
fichier est assaini en gardant le point lisible.

**2451 tests passés, 5 ajoutés.** ADR-0126.

## Session 2026-09-09 (22ᵉ) — Écrire la sortie avant l'entrée

**LIVRÉ.** Section « ce qui invaliderait cette thèse » dans les notes d'analyse — Markdown
(coffre) et HTML. Ce n'est PAS un bear case : ce sont des faits mesurables, chacun avec sa
valeur actuelle, son seuil et la distance relative. Un critère qui ne se calcule pas n'est
pas publié ; un critère déjà franchi invalide la note et le dit en `[!danger]`.

**AUCUNE DONNÉE NOUVELLE.** Stop et pire drawdown depuis `risk_block`, MM200 depuis le bloc
technique, ROCE/WACC depuis le DCF. Un critère qui exigerait une source de plus ne serait
pas vérifiable les jours où elle manque.

**LE PIÈGE ÉVITÉ.** `technical` publie l'ÉCART à la MM200, pas son niveau : on remonte au
niveau avant de comparer, sinon on confronte un prix à un pourcentage — et le résultat reste
un nombre, donc l'erreur passe.

**2446 tests passés, 12 ajoutés.** ADR-0125.

## Session 2026-09-09 (21ᵉ) — Mon banc réclamait un catalogue

**LE BANC NE DÉMARRAIT PAS SUR LE VPS.** `_db_full_universe` lit une table de MÉTADONNÉES
absente de `market.db` (base OHLCV). Le banc réclamait un CATALOGUE là où il lui faut des
symboles et des barres. Il lit désormais `config/mobile_universe.csv` — la watchlist,
versionnée — et imprime sa source.

**ET IL NOMMAIT LA MAUVAISE CAUSE.** Sans base de prix : « 0 mesurés · 6 écartés
(< 200 barres) », ce qui envoie chercher un problème d'historique là où il n'y a aucune
base. Détecté avant la boucle et nommé. La leçon de la journée, appliquée à mon propre outil.

**VÉRIFIÉ DE BOUT EN BOUT** sur une base de test (plomberie uniquement) : −0,500 R par
trade, DSR 0,0008, déployable NON — le comportement juste sur du bruit.

ADR-0124.

## Session 2026-09-09 (20ᵉ) — Le swing ICT ne se décide pas, il se mesure

**LA BONNE QUESTION POSÉE.** « Brancher le swing » veut dire quoi, et comment savoir si ça
vaut le coup ? On ne pouvait pas le savoir : aucun chiffre n'existait.

**ET UNE CONFUSION LEVÉE.** L'îlot swing n'est PAS le swing déjà backtesté du dépôt
(`strategies/swing` + `fast_swing`, repli en tendance SMA/RSI/ATR). `moteur_swing` est une
stratégie ICT / Smart Money entièrement différente — Hurst 1W, SFP, BOS, OTE, order blocks,
CHoCH sur trois horizons. Deux stratégies coexistent, une seule a été mesurée.

**LE BANC, ET SES TROIS RÈGLES.** Entrée en LIMITE (pas au marché, sinon chaque signal
devient un trade et la significativité gonfle) ; stop prioritaire sur la cible dans une même
barre (l'inverse choisit la version favorable d'une information qu'on n'a pas, et sur un
RR > 1 ça suffit à faire passer un banc du rouge au vert) ; résultat en R.

**L'ANTI-FUITE EST STRUCTURELLE.** `parcourir` tronque les barres à `i` : un détecteur qui
lirait l'avenir ne l'aurait pas. Deux tests, dont un détecteur TRICHEUR — sans lui, le
premier passerait au vert sur un banc qui n'appelle jamais le détecteur.

**AUSSI.** `make list-db` renvoyait un chemin de Mac (`$HOME/Desktop/YAHOO.db`), inapplicable
sur le VPS. Il imprime désormais l'ordre de recherche réel et l'état de chaque emplacement.

**2434 tests passés, 10 ajoutés.** Rien n'est branché. ADR-0123.

## Session 2026-09-09 (19ᵉ) — Une P0 que j'avais inventée

**J'AI OUVERT UNE P0 QUI N'EXISTAIT PAS.** « Le panneau montre un sous-ensemble favorable » :
j'avais lu la ligne de `diag_journal_compte` sans vérifier ce qu'elle avait déjà provoqué.
`/api/journal` publie les deux périmètres depuis `perimetre_affiche`, et `/journal` affiche
le bandeau « Périmètre affiché ≠ compte » avec les deux chiffres. Annulée.

**DEUX LIBELLÉS QUI MENTAIENT, EUX, SONT CORRIGÉS.** « Actions diverses » n'est pas un
secteur mais le dernier recours de `_sector_of` : le franchissement sort désormais sous le
type `secteur inconnu`, ce qui envoie chercher le champ `sector` à peupler et non une
allocation à corriger. Il RESTE signalé — un livre à moitié non classé est un vrai problème,
et une concentration non mesurable est plus inquiétante qu'une concentration mesurée.

Et `market_structure` affirmait « aucun appelant en production » alors que `make labs`
l'utilise : le lire comme du code mort aurait conduit à le supprimer et à casser les bancs.

**2424 tests passés, 4 ajoutés.** Dette de câblage 1 704 → 1 479. ADR-0122.

## Session 2026-09-09 (18ᵉ) — Deux courbes tracées, une seule lisible

**REMONTÉ À L'USAGE.** S&P 500 en `--warn` (#d97706) et Bitcoin en #f7931a : deux oranges.
Les deux lignes tracées, les deux boutons actifs, une seule visible — et rien ne le signale.

**CORRIGÉ, ET PLUS LARGEMENT.** Le S&P passe en ardoise désaturée : marché large = référence
neutre, et sa faible chroma le sépare des trois autres même pour un œil daltonien. Surtout,
Nasdaq et Bitcoin étaient des LITTÉRAUX dans le composant — même valeur en clair et en
sombre. Les trois deviennent des tokens de `globals.css`, définis pour les deux thèmes. Une
couleur de graphe qui ne suit pas le thème est un bug qui attend son utilisateur.

Build vert, `tsc` propre. ADR-0121.

## Session 2026-09-09 (17ᵉ) — La courbe du compte face aux indices

**LIVRÉ.** Onglet Positions : la courbe d'equity RÉELLE face au S&P 500, au Nasdaq 100 et au
Bitcoin, filtrables, avec période (1M/3M/6M/1A/Tout), zoom par glisser et détail au survol.
Route `/api/performance`, module `apps/api/performance.py`, composant
`PerformanceVsBenchmarks`.

**EN DOLLARS, PAS EN BASE 100.** Chaque référence part du capital de DÉPART du portefeuille :
l'écart entre deux courbes se lit comme un montant, pas comme un écart de pourcentages à
retraduire.

**LA RÈGLE QUI COMPTE.** Dernière clôture CONNUE à la date — jamais la suivante. Le compte
est valorisé le samedi, l'action ne cote pas : prendre le lundi serait un look-ahead
systématique qui flatterait la référence la plus volatile. Test avec un lundi à 999 qui ne
doit pas apparaître.

**PAS DE SYNTHÉTIQUE.** Une référence introuvable est NOMMÉE, jamais simulée. Un utilisateur
qui compare son compte à un indice ne peut pas deviner que l'indice a été inventé.

**UN TEST DU DÉPÔT M'A RATTRAPÉ.** `test_aucune_route_appelee_n_est_absente_du_build` : la
route marchait en local et aurait rendu 404 en ligne. Ajoutée à `dump_static`.

**AUSSI.** Une commande d'arrière-plan a terminé après moi et la route s'est retrouvée EN
DOUBLE dans `main.py` — la seconde était silencieusement ignorée par FastAPI. Retirée, et
un contrôle des noms de fonctions dupliqués confirme qu'il n'en reste aucun.

**2420 tests passés, 13 ajoutés.** Build Next.js vert. ADR-0120.

## Session 2026-09-09 (16ᵉ) — Mon propre garde-fou m'a refusé le passage

**DEUX BRANCHEMENTS.** `protocole_oos` → `gate.verdict_hors_echantillon` : le DSR est
désormais CALCULÉ avec un `n_essais` lu du ledger, et la signature n'offre aucun moyen de le
fournir. `disjoncteur` → `run_live` via `coupe_circuit`, DÉSARMÉ : il observe, publie, et
n'agit qu'avec `QUANT_DISJONCTEUR=1`.

**LE MOMENT DE LA JOURNÉE.** `make certification`, écrit deux heures plus tôt, a REFUSÉ mon
branchement : `disjoncteur` devenait atteignable depuis `run_live` tout en déclarant
« aucun appelant en production ». Le gate a fonctionné contre son auteur — c'est le seul
test qui compte pour un garde-fou.

**TROIS CHOIX QUI COMPTENT.** La perte du jour se lit sur l'EQUITY, pas sur le journal qui
ne réconcilie pas. L'état persiste sur disque, sinon le cron le remettrait à zéro à chaque
passage et le verrou ne verrouillerait jamais. Et il n'agit pas : son déclenchement ferme
les positions, on ne confie pas ça à un composant jamais éprouvé en réel.

**UNE P0 REQUALIFIÉE.** Le « chemin d'écriture qui dédouble » n'existe pas : le code qui a
produit les ids `LEG-` n'est plus dans l'arbre. C'est une contamination de données
historiques, pas un bug vivant. Passée en P1, remède au niveau données.

**PAS BRANCHÉ, ET DIT.** `frictions` exige un gain attendu par ordre que le rebalanceur ne
produit pas. L'îlot swing change ce que le robot TRADE — décision de produit.

**2407 tests passés, 10 ajoutés.** Dette de câblage 1 906 → 1 704. ADR-0119.

## Session 2026-09-09 (15ᵉ) — L'audit demandait ce qui existe déjà

**CE QUE L'INVENTAIRE DIT.** Audit institutionnel sur quatre axes. CPCV, triple barrière,
meta-labeling, PSR/DSR (formule Bailey–López de Prado complète), PBO, Benjamini-Hochberg,
survivorship, impact en racine carrée, Almgren-Chriss, EVT, débruitage RMT : **tout est
déjà là**. 375 modules, 373 fichiers de test. Une prémisse de l'audit était même fausse —
`cvar_historical` est NON PARAMÉTRIQUE, il n'y a pas de normalité à corriger.

**LE SEUL MANQUE RÉEL** : les barres non temporelles. Zéro implémentation.

**ET LE VRAI CONSTAT.** Dix modules se déclarent SHADOW : **1 906 lignes jamais exécutées**,
mesurées par atteignabilité transitive depuis `run_live`/`snapshot`/`main`. Le système ne
manque pas de machinerie, il manque de câblage. Ajouter CPCV ferait un onzième fantôme.

**CE QUI M'A LE PLUS FRAPPÉ.** Rien ne revérifiait ces déclarations. « Aucun appelant en
production » était vrai le jour de l'écriture ; un import ajouté plus tard le rend faux en
silence. `make certification` mesure désormais, et bloque. Sabotage vérifié.

**MA PREMIÈRE LECTURE ÉTAIT FAUSSE, ET JE L'AI CORRIGÉE AVANT D'AGIR.** J'ai d'abord classé
`disjoncteur` et `frictions` en « doublons à supprimer ». Lecture faite : `dd_kill_switch`
coupe sur le DRAWDOWN, le disjoncteur sur la perte du JOUR — mécanismes différents ; et
`frictions` DÉCOMPOSE les coûts au lieu de les renchérir. **Rien à supprimer.** Un premier
filtre trop large m'avait aussi fait compter 16 modules SHADOW au lieu de 10 : les six
autres portaient « UNCALIBRATED » comme statut de RETOUR, c'est-à-dire le mandat
données-réelles qui fonctionne.

**AUCUN BRANCHEMENT FAIT.** Chacun change le comportement d'exécution et mérite sa décision.

**2397 tests passés, 6 ajoutés.** ADR-0118.

## Session 2026-09-09 (14ᵉ) — Les correctifs marchent, la chaîne reste à geler

**LES DEUX CORRECTIFS ONT TENU.** Second passage : les lots reconstitués portent des prix
JUSTES (BTC 79 499 $ le 04/09, 81 132 $ le 03/09 — cohérents avec le marché) et le coût de
revient tombe de 83 804 $ à 16 538 $. Le garde-fou n'a rien eu à refuser : il n'y avait plus
rien d'incohérent à écrire.

**ET LE RÉSULTAT EST QUAND MÊME PIRE.** Réalisé +245,33 → **−1 203,05 $**, soit −1 448 $,
quand la chaîne n'annonce que −222 $ (+39,98 de fermetures, −262,38 de doublon). **−1 226 $
non expliqués.** Écart de réconciliation : +169 → **+1 694 $**.

**CE QUE J'AI COMPRIS TROP TARD.** Ajouter des ouvertures RÉ-APPARIE le FIFO : des
fermetures déjà enregistrées changent de contrepartie. La chaîne ne s'ajoute pas au
registre, elle le RECALCULE — sans le dire. Et la cause est en amont : NWL à 1,74× la
quantité achetée sur 7 identifiants `LEG-…`, MAS à 1,91× sur 6. Le diagnostic le disait
depuis le début — « le chemin d'ÉCRITURE crée deux identités ». Réparer en aval d'un writer
qui dédouble ne peut pas converger.

**DÉCISION. J'ARRÊTE.** Deux tentatives, deux dégradations. Journal restauré, laissé tel
quel. `make reparer-journal` reste au dépôt mais ne doit plus être lancé avant que le
dédoublement soit fermé. Aucun effet sur l'exécution : `run_live` lit le COURTIER.

**RAPPEL POSÉ** pour le 23/09 : mesurer la rotation réelle (`make turnover-audit`) après
deux semaines de cron.

ADR-0117.

## Session 2026-09-09 (13ᵉ) — Le garde-fou existait, il regardait trop tard

**RETOUR ARRIÈRE CONFIRMÉ.** Le journal du VPS est restauré : `réalisé +245,33 $`, au
centime près comme avant. L'écart affiche +596 $ au lieu de +169 $ uniquement parce que le
LATENT a bougé avec le marché (+576 → +56 $) — le journal, lui, est identique.

**CE QUE J'AI FERMÉ.** ADR-0115 corrigeait la cause des faux lots. Restait pourquoi rien ne
l'avait arrêtée. Le contrôle existait — `_base_de_cout` compare chaque prix d'entrée à la
clôture de son jour — mais APRÈS l'écriture. Il constatait au lieu d'empêcher.
`lots_incoherents` le fait désormais AVANT, et `completer_ouvertures` refuse d'écrire.

**FAIL-CLOSED SUR L'INCOHÉRENCE, PAS SUR LE SILENCE.** Un cours introuvable ne condamne pas
un lot : une base muette n'est pas un verdict. Deux tests tiennent les deux bords.

**UNE COMMANDE.** `make reparer-journal` enchaîne les six étapes dans l'ordre imposé par les
scripts. On ne demande plus de retenir un ordre dont l'inversion casse le registre.

**CE QUI RESTE VRAI ET QU'IL FAUT DIRE.** Le robot FONCTIONNE. `run_live` lit les positions
du COURTIER, jamais le journal : le rebalancement n'a jamais dépendu de cet état. Le journal
est un registre, pas une commande.

**2391 tests passés, 3 ajoutés.** ADR-0116.

## Session 2026-09-09 (12ᵉ) — La réparation a cassé ce qu'elle devait réparer

**CE QUE J'AI FAIT APPLIQUER, ET QUI ÉTAIT FAUX.** J'ai recommandé la chaîne de réparation
du journal. Appliquée sur le compte réel, elle a fait passer l'écart de réconciliation de
**+168,76 $ à +4 490,52 $** — 26 fois pire — et le réalisé de +245 $ à **−3 929 $**. Le
compte, lui, n'a bougé que de +28 $ en vingt minutes.

**LA PREUVE.** BTC reconstitué à 76 801 $ le 07-07 puis fermé à 61 731 $ le 07-08 : −19,6 %
en une nuit. ETH −29,1 %, LTC −13,1 %, la même nuit, −3 140 $ à eux trois — plus que la
totalité du lot. Cette nuit n'existe pas sur la courbe du compte.

**LA CAUSE.** `ouvertures_manquantes` fusionnait les fills non couverts en un lot au VWAP
des uns et à la DATE des autres. Le FIFO consomme les fills anciens, donc le reste est fait
des plus récents — les plus chers sur un actif qui monte — mais daté du plus ancien. Le
FIFO fermait ce lot en premier. Biais STRUCTUREL : sur un actif en hausse, la perte
fabriquée est systématique.

**CE QUI M'A LE PLUS APPRIS.** Le défaut était écrit dans un test qui PASSAIT :
`test_fill_coupe_en_deux…` exigeait un lot de 140 unités à 24,29 $ daté d'un jour où il n'y
en avait que 40, à 10 $. J'avais lu ce test comme une garantie ; c'était la spécification du
bug. Un test verrouille un comportement — il ne dit pas que ce comportement est juste.

**CORRIGÉ.** Un lot par fill, chacun à sa date et à son prix. Identifiant dérivé du CONTENU
— plusieurs lots par symbole désormais, une clé au seul symbole les aurait écrasés.
3 régressions, sabotage vérifié dans les deux sens.

**À FAIRE SUR LE VPS.** Restaurer `journal.avant-completion-20260909-091516.db` : l'état
d'avant (+168,76 $) était le bon. Puis rejouer la chaîne avec le code corrigé.

**2388 tests passés, 3 ajoutés.** ADR-0115.

## Session 2026-09-09 (11ᵉ) — Mon correctif déplaçait le défaut

**CE QUE LE VPS A MONTRÉ.** Le post-mortem du soir : `n_breaches` passé de 3 à 2, la ligne
« nom QQQ 50 % > 20 % » disparue — mon correctif du matin marchait. Et, à sa place,
« **secteur ETF 50 % > 40 %** ». Même actif, même poids, autre libellé. J'avais bouché l'axe
des noms et laissé celui des secteurs ouvert.

**CORRIGÉ AUX QUATRE SITES.** `index_sectors` applique `max_index` aux libellés de véhicule.
Le code savait déjà qu'« ETF » et « Indices » ne sont pas des secteurs — `_themes_section`
les exclut de la heatmap — mais cette connaissance n'était pas branchée sur les limites.

**GARDE-FOU CONTRE MON PROPRE CORRECTIF.** Un test NÉGATIF vérifie que Forex, Commodités et
Crypto gardent le plafond sectoriel à 40 %. Requalifier est utile ; requalifier trop
désarmerait la limite sans que rien ne le dise.

**LE JOURNAL, MESURÉ (simulation, rien écrit).** Le compte est bien plus sain que le
registre : écart de réconciliation **+168,76 $** sur +990,08 $, et le script explique que
c'est `latent(début)`, pas une anomalie. Restent, chiffrés : 21 lots ouverts sur des titres
que le courtier ne détient plus ; QQQ à **96,78 unités au journal contre 60,50 au courtier**
(+36,28 fantômes ≈ 26 000 $, ce qui recoupe l'estimation d'ADR-0109) ; 8 doublons de
fermeture pour **+915,37 $** de réalisé compté deux fois ; 18 achats sans prix de revient.

**LA DÉCOUVERTE LA PLUS GÊNANTE.** Le filtre `legacy` masque **234 lots et −2 414,96 $** de
réalisé. Le panneau affiche 58 % de réussite et +2 660 $ ; le compte a subi 52 % et
+245,33 $. Le journal ne ment pas — il montre un sous-ensemble FAVORABLE, ce qui produit le
même effet sur qui le lit. Non voulu, réel, et à trancher.

**AUSSI.** `safe_pickle` signale `models/ml_*.pkl` en mode 664 — inscriptible par d'autres
utilisateurs sur le VPS. Le garde-fou fait son travail ; la permission reste à resserrer.

**2386 tests passés, 3 ajoutés.** ADR-0114.

## Session 2026-09-09 (10ᵉ) — Je proposais un arbitrage ; le code avait déjà tranché

**CE QUE J'AI EU FAUX.** J'ai soumis à l'utilisateur un choix entre « reclasser les trackers
sous `max_index` » et « plafonner le cœur à 20 % ». Il n'y avait pas de choix : `limits.py`
porte `index_names` + `max_index=0.60` depuis le 06/07, la raison est écrite dans le
docstring (« un tracker n'est pas un risque d'émetteur unique »), et un test la vérifiait
déjà. J'ai présenté comme une décision à prendre une décision déjà prise et écrite.

**LA VRAIE CAUSE, TROUVÉE EN LISANT LES APPELANTS.** `index_names` est optionnel. Le rapport
du tableau de bord le passe ; celui du portefeuille preset non. Le post-mortem lit le
SECOND. Un cœur conforme était donc signalé en franchissement tous les jours d'un côté, et
silencieux de l'autre. Le signal à repérer n'était pas le chiffre : c'était que deux
rapports du même portefeuille, le même jour, ne disaient pas la même chose.

**CORRIGÉ + VERROUILLÉ.** Le site preset déclare ses trackers. Un test relit `snapshot.py`
et échoue si un appel omet `index_names` — sabotage vérifié dans les deux sens. Aucun poids
ne bouge : le franchissement disparaît parce qu'il n'existait pas.

**ET LE SECOND FRANCHISSEMENT EST D'UNE AUTRE NATURE.** « Actions diverses 47,5 % » n'est pas
un secteur : c'est le seau de DERNIER RECOURS de `_sector_of` pour une action sans secteur
GICS. Donc pas « la moitié du livre sur un secteur » mais « la moitié du livre non classée ».
La concentration sectorielle n'est pas franchie, elle est NON MESURABLE. Défaut de données.
Ouvert en P1 — à mesurer sur le VPS, pas ici : la base réelle est absente du conteneur.

**2383 tests passés, 2 ajoutés.** ADR-0113.

## Session 2026-09-09 (9ᵉ) — Douze décisions datées de demain

**CE QUE J'AI CASSÉ.** Les ADR-0100 à 0111, l'en-tête de séance et un enregistrement du
registre portaient **2026-09-10**. On était le 09. Quatorze horodatages faux en une journée,
dans les trois fichiers dont le seul travail est de dire QUAND. Aucun contrôle ne regardait
les dates : le lint du vault vérifiait les liens, les doublons d'ADR, les orphelins — pas
l'horodatage.

**CORRIGÉ, ET GARDÉ.** Les quatorze dates rectifiées, la séance renumérotée `(8ᵉ)` puisque
le jour en comptait déjà sept. Et un gate : `dates_futures` fait sortir `make vault-lint` en
erreur sur un en-tête d'ADR ou de séance postérieur à aujourd'hui. Sabotage : l'erreur exacte
remise en place → exit 1 ; retirée → exit 0.

**CE QUE JE N'AI PAS ÉLARGI.** Le contrôle ne lit que les EN-TÊTES. « à rejuger au
2026-12-01 » dans un corps d'ADR est un rendez-vous, pas une faute — le signaler ferait un
avertissement permanent, donc un avertissement ignoré. Un en-tête sans date passe aussi : les
ADR d'avant 0030 n'en portent pas.

**BLOQUÉ / À TRANCHER.** Rien de neuf ici, mais la P0 de la veille reste entière et le
rebalanceur automatique est ARMÉ : l'allocation courante franchit la politique de risque du
projet tous les jours — secteur « Actions diverses » 47,5 % contre 40 %, QQQ 50 % contre un
plafond de nom à 20 %, aux 05, 07, 08 et 09 septembre. Deux documents du projet se
contredisent ; lequel corriger est un arbitrage utilisateur.

**AUSSI, CONSTATÉ SANS AGIR.** `ruff check` hors de `packages/apps` remonte un arriéré
préexistant de plusieurs milliers de lignes (longueur de ligne, surtout dans `apps/api` et
`scripts`). Ce n'est pas de ce correctif — mes trois fichiers passent — mais le `ruff check .`
du rituel de clôture est rouge AVANT toute modification, donc il ne protège plus rien. À
traiter comme dette, pas comme urgence.

**2381 tests passés, 6 ajoutés.** ADR-0112.

## Session 2026-09-09 (8ᵉ) — HRP reste en production, et deux avaries de fond réparées

**LA PÉRIODE A TRANCHÉ.** Le script imprime enfin ce qu'il mesure :
**2024-05-15 → 2026-05-19**, 336 séances. Le krach obligataire de 2022 est HORS fenêtre.
Or l'allocation gagnante du Mean-CVaR fait **63 % d'ETF obligataires**, et sur le
RENDEMENT le duel contre HRP est indiscernable (7/16, p = 0,80). Son avantage porte donc
sur le seul risque de queue — et ce risque de queue EST une exposition de classe. On
mesure « ces ETF ont été calmes pendant deux ans », pas « cette méthode est meilleure ».
**HRP reste l'allocateur de production.** Le Mean-CVaR reste `en_test`, avec sa période
inscrite au registre : il sera rejugé quand l'historique couvrira un choc de taux.

**AVARIE 1 — un prix périmé comptait comme un prix réel.** Le chargement ne regardait que
le NOMBRE de barres. `HYPE/USDC`, arrêtée le 27 août 2024, figurait dans l'univers RÉEL
du 8 septembre 2026 : le screener pouvait la classer, le dimensionnement la dimensionner,
les graphiques l'afficher — sur un cours vieux de deux ans. Un prix périmé est pire qu'un
prix absent : il a l'air d'un prix. `_load_prices` écarte désormais toute série en retard
de plus de 60 jours sur la barre la plus fraîche de l'univers — pas sur la date du jour,
sinon un férié condamnerait tout le monde.

**AVARIE 2 — « 33 actifs à vérifier » n'est pas un rapport.** Personne n'ouvre une corvée
de trente-trois lignes. Le projet possédait déjà `corporate_actions`, qui ne conclut à un
split que si le ratio tombe sur une fraction usuelle ET que le volume change d'échelle en
sens inverse — et il n'était branché nulle part. La liste se sépare maintenant en
« SPLIT CONFIRMÉ », « volume non concordant » et « inexpliqué », seule catégorie qui
demande un œil.

**CE QUI RESTE.** Allonger l'historique commun (601 dates sur 802 jours de bourse), et la
P0 de réconciliation du journal, qui attend toujours la machine qui détient `journal.db`.

ADR-0100. Tests : 2326 passés, 7 ajoutés.

## Session 2026-09-09 (7ᵉ) — Le duel conclut, mon affichage mentait

**LE RÉSULTAT.** Seize fenêtres : le Mean-CVaR bat HRP **15 fois sur 16** (p = 0,001,
écart médian −0,39 % de CVaR), les deux variantes. min-variance 2/16, ERC et équipondéré
0/16. Le protocole peut enfin conclure — plancher de puissance à 3,05·10⁻⁵.

**DEUX DÉFAUTS DE MON AFFICHAGE.** Le « ✓ » marquait `concluant`, donc s'affichait aussi
sur l'équipondéré battu **0 fois sur 16** : le test des signes est bilatéral, il dit
qu'il y a un écart, jamais dans quel sens. Trois lignes sur cinq portaient une coche qui
se lisait comme une validation en décrivant une défaite. La colonne dit maintenant
« mieux » ou « pire ». Et le plancher de puissance, qui vaut 3,05·10⁻⁵, s'imprimait
« 0.0000 » — un zéro fabriqué par un format, dans un projet dont la discipline est de ne
jamais publier un chiffre qu'on n'a pas.

**LA VRAIE LIMITE A CHANGÉ DE NATURE.** Passer de `--pas 63` à `--pas 21` a monté les
fenêtres de 5 à 16 — et le recouvrement des périodes d'ajustement de 75 % à **92 %**.
Deux fenêtres consécutives ajustent sur presque la même histoire, donc produisent presque
les mêmes poids. Le test reste valide comme comparaison de deux PORTEFEUILLES sur seize
périodes disjointes ; il est faible comme comparaison de deux MÉTHODES. Avec 601 dates
communes, un test à fenêtres d'ajustement disjointes n'en donnerait qu'UNE. **On ne peut
pas acheter de l'indépendance qu'on n'a pas** : la contrainte est la longueur de
l'historique commun, pas le réglage.

**AJOUTÉ.** La période réellement mesurée s'imprime avec le tableau, avec un test
d'alignement à un jour près — un décalage d'un cran afficherait une période fausse sous
des chiffres justes, l'erreur la plus difficile à voir.

**LA RÉSERVE RESTE ENTIÈRE.** L'allocation gagnante est à 63 % en ETF obligataires. Un
duel sur le CVaR récompense mécaniquement qui détient la classe la moins volatile.

**RANGEMENT.** `valider_nouveautes.py` était monté à 629 lignes ; la comparaison
d'allocateurs part dans `scripts/comparaison_allocateurs.py`. `PLAFOND_LIGNE` n'a plus
qu'une définition.

**PROCHAIN.** Lire la période imprimée par le prochain run : contient-elle un épisode de
hausse des taux ? Et allonger l'historique commun (601 dates sur 802 jours de bourse,
parce que la grille exige que les 734 actifs cotent le même jour).

ADR-0099. Tests : 2319 passés.

## Session 2026-09-09 (6ᵉ) — Le seuil tient sa promesse, et un verdict s'inverse

**LE SEUIL CALIBRÉ TRANSFÈRE EXACTEMENT.** 45 actifs signalés sur 826, soit **5,4 %
contre 5,5 % prédits** sur le panneau de calibration. Zéro série cassée (contre cinq),
une seule figée (contre sept), 77 événements au lieu de 5632. La partie qualité de
données est réglée.

**ET LE REJET DU MEAN-CVaR TOMBE.** Hors échantillon, sur le panneau assaini :

| | CVaR 95 % | rendement |
|---|---|---|
| 08/09, données non réparées : HRP | 1,54 % | +12,3 % |
| 08/09 : Mean-CVaR | 2,91 % | −5,1 % |
| **09/09, assaini : Mean-CVaR plafonné** | **1,04 %** | +9,7 % |
| 09/09 : HRP | 1,51 % | +10,3 % |

Là où il était dernier et seul en perte, il est premier sur le risque de queue à
rendement quasi égal. HRP ne bouge presque pas. **Le rejet d'ADR-0087 est ANNULÉ, pas
infirmé** : sa mesure portait sur cinq séries crypto décrivant d'AUTRES jetons. Elle ne
prouvait pas ce qu'elle disait — et le nouveau chiffre ne prouve pas davantage le
contraire. Ligne datée au registre, l'hypothèse repasse en `en_test`.

**CAR LE NOUVEAU RÉSULTAT NE VALIDE RIEN NON PLUS, ET J'AURAIS DÛ LE SAVOIR AVANT.**
Cinq fenêtres hors échantillon : la plus petite p-valeur atteignable par un test des
signes vaut **2/2⁵ = 0,0625**. Même en gagnant les cinq, on ne descend pas sous 5 %. Le
protocole est sans puissance PAR CONSTRUCTION — un fait de forme, calculable avant de
regarder la moindre donnée, que j'aurais dû établir le 08/09 avant de prononcer un rejet
sur six fenêtres.

**LIVRÉ POUR TRANCHER.** `packages/portfolio/duel_hors_echantillon.py` : détail fenêtre
par fenêtre, duel apparié contre l'allocateur en place, test des signes — et deux
honnêtetés imprimées à l'écran, le plancher de puissance (rien sous 2/2ⁿ) et le
recouvrement (à 252/63 deux fenêtres partagent 75 % de leur ajustement, donc la p-valeur
est optimiste). Options `--fenetre` et `--pas` pour acheter de la puissance.

**AUSSI.** `/api/failures` affichait toutes les lignes `rejete` d'un ledger append-only :
une hypothèse rouverte y serait restée un échec pour toujours. L'endpoint retient
désormais le dernier mot par facteur, l'historique reste au fichier.

**PROCHAIN.** `make valider-nouveautes ARGS="--pas 21"` — seize fenêtres au lieu de cinq.
Lire le duel apparié, pas la moyenne. Et porter deux réserves : le Mean-CVaR sans plafond
met 63,7 % sur AGG, et l'allocation gagnante est à 66 % en ETF obligataires.

ADR-0098.

## Session 2026-09-09 (5ᵉ) — La prédiction tenait, et la source crypto est propre

**LA PRÉDICTION ÉCRITE D'AVANCE ÉTAIT JUSTE.** Hier je basculais six séries vers Binance
en écrivant ce qui devait se produire : *si l'arrondi vient de Yahoo, la part de clôtures
distinctes doit bondir ; s'il tient au pas de cotation du jeton, non*. Elle pouvait
échouer :

| base | clôtures distinctes | plus longue plage figée |
|---|---|---|
| SHIB | 3 % → **63 %** | 61 séances → **3** |
| BONK | 4 % → **84 %** | 130 → **2** |
| XEC | 10 % → **83 %** | 70 → **2** |
| FLOKI | 14 % → **95 %** | 25 → **2** |
| COMP | 17 % → **89 %** | 46 → **2** |
| GMX | 32 % → **84 %** | 256 → **2** |

**Et ça règle plus que ces six séries.** Les plages figées n'étaient pas des flux morts :
c'était la source qui décrochait. Le verdict « FLUX ARRÊTÉ » désignait un symptôme de la
source, jamais l'état du marché — et sans la mesure, le geste (retirer ces séries de
l'univers) aurait été le mauvais. `RPL` rejoint le lot sur la même signature, avec la
même prédiction à vérifier.

**ÉTAT FINAL DE LA SOURCE CRYPTO.** 102 bases sur 102 ingérées (PEPE incluse, que Yahoo
limitait à 119 barres), **21 sources forcées et vérifiées**, **92 séries CONFORMES**.
Restent 7 périmées (décision d'univers, elle t'appartient) et 3 non vérifiables — OKB,
LEO, KAS — que Binance ne cote pas : leur forme est saine, mais rien ne les confronte, et
on le DIT au lieu de les déclarer conformes par défaut.

**CE QUI COMPTE MAINTENANT, ET QUI N'EST PLUS DE LA PLOMBERIE.** Toutes les mesures
d'allocation antérieures à aujourd'hui — ADR-0087 compris, celui qui rejette le
Mean-CVaR — portaient sur 774 actifs dont 48 cryptos, avec cinq séries décrivant d'autres
jetons. Le panneau fait **823 actifs dont 97 cryptos**, tous confrontés à une référence.
Le rejet du Mean-CVaR ne devrait pas bouger — sa cause est le manque d'observations de
queue, que l'élargissement aggrave — **mais ce raisonnement n'est pas une mesure**.

**PROCHAIN.** `make valider-nouveautes` : refait la comparaison d'allocateurs sur
l'univers assaini ET applique pour la première fois le seuil calibré à 24.

ADR-0097. Tests : 2304 passés.

## Session 2026-09-09 (4ᵉ) — Le seuil est calibré, et il passe de 8 à 24

**TRANCHÉ.** Grille élargie, instrument réparé, 150 injections : **l'optimum est enfin
INTÉRIEUR dans les deux modes**, l'avertissement de bord ne se déclenche pas. Maximum
global à **24 avec normalisation** (score 0,905) devant 32 sans (0,889) — les deux
questions laissées ouvertes hier, quel mode et quel seuil, se répondaient bien ensemble.
`SEUIL_ECART = 24,0` appliqué : **45 actifs à lire au lieu de 489**, 93 % des splits et
99 % des ticks retrouvés sur 138 actifs. Le prix est inscrit dans le code : cinq points
de détection contre une lecture divisée par trois, et l'angle mort — un split ×4 ne vaut
que quinze unités pour une crypto d'échelle 5 %/jour — est **fixé par un test** qui
vérifie aussi qu'il ressort à seuil 12, pour distinguer un arbitrage d'une cécité.
Il aura fallu quatre passages : le mélange d'échelles, le calendrier de l'instrument, la
borne de la grille, puis la mesure. Aucun n'était évitable en raisonnant ; chacun a été
trouvé en regardant un chiffre impossible.

**LE DIAGNOSTIC S'EST CONTREDIT, ET IL AVAIT RAISON DEUX FOIS.** `OP` sortait CONFORME
(corr +1,00) puis COLLISION (−0,00) d'un passage à l'autre, sur la même base — seule la
fenêtre de référence avait changé. La série est **RECOLLÉE** : juste depuis la
réattribution du ticker, étrangère avant. Le diagnostic mesure désormais deux
corrélations, complète et récente, et nomme ce cas.

**UN ORDRE DESTRUCTEUR, CORRIGÉ AVANT QU'IL NE COÛTE QUELQUE CHOSE.** `_ingerer` effaçait
la série AVANT d'interroger la nouvelle source : source muette = base vide, sans
remplaçant. Le risque restait théorique à cinq entrées vérifiées ; il cesse de l'être à
vingt-et-une, dont onze non encore confirmées. On récupère d'abord, on efface ensuite.
Contrôle négatif vérifié par sabotage.

**RÉPARATIONS.** Le 2ᵉ lot (SUI, TIA, JUP, STRK, APE) ressort CONFORME à son tour :
**dix bases réparées et vérifiées sur dix**. Ajoutés pour le prochain passage : IMX, GRT,
GMX, GMT (collisions visibles seulement grâce à la référence paginée), OP (recollée), et
SHIB, BONK, XEC, FLOKI, COMP, PEPE (source inadéquate — avec une prédiction falsifiable
sur l'arrondi).

**RESTE À TRANCHER PAR TOI.** Sept séries périmées (HYPE, TON, MATIC, RNDR, FTM, GALA,
FXS), dont trois migrations réelles ; `RNDR` fait doublon avec `RENDER`, déjà présent et
conforme. Sortir un instrument change l'ensemble investissable : c'est ta décision, pas
un correctif de données.

ADR-0095, ADR-0096. Tests : 2304 passés, 5 ajoutés.

## Session 2026-09-09 (3ᵉ) — La réparation tient ; la calibration ne tient toujours pas

**CE QUI EST RÉPARÉ ET VÉRIFIÉ.** Les cinq bases routées vers Binance ressortent
**CONFORMES, corr +1,00**, et leur début de série change du tout au tout : `ARB` passe de
novembre 2017 — impossible, Arbitrum date de 2023 — à mars 2023 ; `APT` de 2021-11 à
2022-10 ; `UNI` de 2019-10 à 2020-09. La réparation est confirmée par une mesure
indépendante de celle qui l'avait motivée. L'univers réel passe de **774 à 823 actifs,
dont 97 cryptos au lieu de 48**.

**CE QUE LE PÉRIMÈTRE COMPLET A FAIT SORTIR.** Cinq NOUVELLES collisions (SUI, TIA, JUP,
STRK, APE — `JUP-USD` commence en 2017 pour un jeton de 2024), six séries à l'arrondi
destructeur (SHIB 3 % de clôtures distinctes, BONK 4 %, XEC 10 %, FLOKI 14 %, COMP 17 %,
GMX 32 %), et une avarie que personne ne cherchait : **une douzaine de séries mortes** —
MATIC s'arrête en mars 2025, IMX en juillet 2022 — qui sortaient « CONFORMES » et
peuplaient l'univers en se faisant passer pour vivantes. Nouveau verdict PÉRIMÉE.

**UN TROU DE LA MESURE, TOMBÉ SUR SES PROPRES CIBLES.** Dix séries sortaient « NON
VÉRIFIABLE » : la référence demandait les 1000 DERNIÈRES barres à Binance, donc toute
série s'arrêtant avant fin 2023 n'avait aucun recouvrement avec elle — c'est-à-dire
exactement les séries suspectes. Référence passée à l'historique paginé.

**LA CALIBRATION, EN REVANCHE, N'EST TOUJOURS PAS TRANCHÉE — et pour une bonne raison.**
L'instrument réparé donne enfin des sensibilités crédibles (100 % de détection des splits
à tous les seuils sans normalisation, contre 33-73 % erratiques avant : la correction du
calendrier était la bonne). Mais deux choses bloquent :

· La proposition (24) tombait sur le **plus grand seuil de la grille**, score encore
  croissant. Ce n'est pas un maximum, c'est le dernier point essayé. Grille élargie à 64,
  avertissement explicite sur les bords, `N_INJECTIONS` 40 → 150.
· **Le mode n'est pas tranché non plus.** À seuil 8, l'ANCIEN mode gagne sur les deux
  axes : coût 55,3 % contre 59,4 %, sensibilité 100 % contre 94 %. La normalisation ne
  l'emporte qu'à partir de 12, et par le seul coût. Mécanisme : diviser par l'échelle
  propre jette l'amplitude absolue, or un −75 % en une séance est une donnée cassée quelle
  que soit la volatilité habituelle du titre.

**Deux fois de suite la même erreur de méthode**, et je la note ici pour ne pas la
refaire : conclure sur un contrôle synthétique ce qui ne pouvait se trancher que sur le
panneau réel. Un panneau gaussien n'a ni queues épaisses, ni l'information d'amplitude
que la normalisation sacrifie.

**PROCHAIN (3ᵉ passage).** `make ingest-crypto && make diag-source-crypto` pour vérifier
les cinq nouvelles bascules, puis `make calibrer-seuil ARGS=--comparer-ancien` avec la
grille élargie — et trancher mode ET seuil ensemble.

ADR-0092, ADR-0093, ADR-0094. Tests : 2299 passés, 6 ajoutés.

## Session 2026-09-09 (suite) — Le premier passage réel dément deux de mes conclusions

Les deux instruments écrits ce matin ont tourné sur le VPS. Ils ont fait leur travail :
ils m'ont contredit.

**1. La normalisation par actif n'a PAS réduit le taux de signalement.** Au seuil 8 sur
le vrai panneau (1500 × 774) : **57,6 %** avec, contre 55,6 % sans (mesure du 08/09).
J'avais écrit ce matin que « queues épaisses » était une explication fausse. **C'est ma
correction qui était fausse.** Mon panneau de contrôle était gaussien : il n'a pas de
queues épaisses, donc il ne pouvait pas départager les deux hypothèses — et j'ai conclu
comme s'il le pouvait. Le mélange d'échelles était réel et est corrigé ; il n'était pas
le facteur dominant. La normalisation reste (la statistique dit enfin ce qu'elle prétend
dire), le seuil reste UNCALIBRATED. Par classe à 8 : crypto 94 %, actions 65 %, ETF 11 %.

**2. L'instrument de calibration mesurait le calendrier.** Il proposait `SEUIL_ECART = 24`
sur la foi d'un tableau contenant deux impossibilités : sensibilité de 33 % à seuil 4 mais
73 % à seuil 6 (une sensibilité ne peut pas baisser quand le seuil baisse), et 61 % de
détection pour un split de **−75 % en une séance**, qu'aucun détecteur ne peut manquer.
Cause : l'injection tirait sa date au hasard, et tombait une fois sur trois sur un jour
NON COTÉ — un défaut y produit zéro rendement, il n'y a rien à détecter, et l'échec était
compté contre le détecteur. Vérifié par sabotage sur calendrier 5/7 : 100 % → **40 %**, le
même ordre de grandeur que sur le vrai panneau. Le biais allait dans le sens qui désarme
le détecteur, le pire des deux. Proposition retirée, instrument corrigé.

**3. La source crypto, elle, a livré des causes nettes.** Cinq collisions de ticker
confirmées **deux fois chacune** — corrélation ≈ 0 contre Binance (TON −0,08, ARB +0,04,
STX +0,00, APT +0,11, UNI +0,25) ET date de début antérieure à l'existence du jeton (la
série Yahoo d'`ARB-USD` démarre en novembre 2017 ; Arbitrum date de mars 2023). Réparé en
routant ces cinq bases vers Binance, avec effacement annoncé des lignes de l'homonyme.
SHIB n'est pas un flux arrêté mais un **arrondi** : corr +0,80 (le bon jeton) et 3 % de
clôtures distinctes. Et le diagnostic a trouvé ce que personne ne cherchait : **52 bases
crypto sur 102 n'avaient jamais été ingérées**, frontière exactement au 50ᵉ symbole —
le défaut `--top 50` contre un univers de 102. La moitié de la poche crypto n'existait
pas, et rien ne le disait.

**PROCHAIN.** Sur le VPS : `make ingest-crypto` (102 bases, dont 5 reprises chez Binance),
puis `make diag-source-crypto` pour vérifier qu'elles sortent CONFORMES, puis
`make calibrer-seuil ARGS=--comparer-ancien` avec l'instrument réparé.

ADR-0090, ADR-0091 ; ADR-0088 et ADR-0089 amendés en tête par les mesures réelles.

## Session 2026-09-09 — Deux avaries de données : l'une mesurée, l'autre outillée

Suite des verdicts du 08/09. Deux chantiers ouverts, pris dans l'ordre où ils étaient
actionnables.

**FAIT — le détecteur d'anomalies accusait les cryptos d'être des cryptos (ADR-0088).**
430 actifs sur 774 signalés au premier passage réel. J'avais écrit au TODO « les queues
épaisses des marchés » : plausible, non mesuré, **faux**. Un panneau synthétique de 774
séries multi-classes SANS le moindre défaut injecté donne 100 % des cryptos signalées et
0 % du forex, 12 974 événements pour zéro anomalie. La coupe transversale mélangeait des
échelles sans rapport (0,5 % / 1,5 % / 5 % par jour). Correctif : chaque série est
divisée par sa propre échelle robuste avant comparaison. Même panneau : 75 actifs
signalés → **0**, et les 15 défauts injectés (splits ×4, ticks ×1,5 à ×10, dans les trois
classes) restent **tous** détectés. La gravité continue de se lire sur le rendement réel,
avec un test dont j'ai vérifié par sabotage qu'il sait échouer.

**OUTILLÉ — la source `/USDC` (ADR-0089).** Douze séries avariées sur un même format de
symbole : c'est la source, pas le marché. `scripts/ingest_crypto.py` faisait
`except Exception: continue` et ne renvoyait que le nombre de succès — **une base muette
ne laissait aucune trace**, et c'est ce silence qui a laissé pourrir douze séries.
L'ingestion liste désormais chaque échec avec sa cause. Et `make diag-source-crypto`
confronte chaque série à une référence indépendante (Binance klines) pour séparer les
quatre causes possibles, dont les gestes sont opposés : collision de ticker, flux arrêté,
précision, conforme.

**BLOQUÉ ICI, pas ailleurs.** Cette machine n'a ni `market.db`, ni `crypto.db`
(`journal.db` y est présent mais vide : 0 trade). Le proxy refuse les fournisseurs de
prix. Les deux mesures finales — quel ticker répond vraiment pour UNI/ARB/OP/STX/TON, et
si 8,0 reste le bon seuil une fois la coupe homogène — se font sur la machine qui détient
les bases : `make diag-source-crypto` puis `make calibrer-seuil`. Les deux ne font que
lire et imprimer ; `ALIAS_YAHOO` est volontairement **vide**, le remplir sans mesure
remplacerait une série fausse par une autre.

**PROCHAIN.** Lancer ces deux commandes sur le Mac mini / le VPS, puis la P0 de
réconciliation du journal, qui attend la même machine.

Tests : **2280 passés, 7 ignorés, 0 échec**. Seize ajoutés : 4 sur la normalisation par
actif (dont le contrôle négatif qui compare les deux modes et échoue si l'ancien ne crie
pas), 4 sur l'instrument de calibration, 8 sur le diagnostic crypto.

## Session 2026-09-07 (suite 32) — Réécriture des textes du site en langage clair

Retour de l'utilisateur : « trop technique ». Il avait raison, et le diagnostic est plus large qu'un
paragraphe — l'ensemble du site parlait le vocabulaire de celui qui l'a écrit.

**Règle appliquée : simplifier le VOCABULAIRE, jamais le CONTENU.** Une phrase plus courte qui
laisserait tomber « non validé hors échantillon » serait un recul déguisé en amélioration. Chaque
chiffre, chaque réserve et chaque avertissement sont conservés à l'identique ; seuls les mots
changent.

Exemples du registre visé, à contenu strictement égal :
- « Minimum variance robuste sur l'univers disponible » → « Le panier qui bouge le moins »
- « Equal Risk Contribution » → « Chaque ligne apporte la même dose de risque »
- « IC +0,0202 sur 83 fenêtres disjointes (t = 0,76) » → « lien classement / hausse réelle =
  +0,0202 (fiabilité 0,76 — il en faudrait 2) » — le seuil est DIT, il n'est plus à connaître
- « chemin de moindre effort · turnover cumulé » → « par quoi commencer · portefeuille remué »
- « série arrêtée, elle paraîtrait sans risque » → « un cours figé donne l'illusion d'un titre
  calme, donc sans risque : le calcul lui donnerait une place qu'il ne mérite pas »

Pages traitées : étape 4 (profils, panneaux, méthodologie), profil investisseur, journal, positions,
portefeuille, risque, thèmes, trades, sentiment, ML, notes. Le bloc « méthodologie » de l'étape 4,
le plus dense, est découpé en trois paragraphes titrés — ce que font les profils, ce qu'ils ne
cherchent pas, ce qui n'est pas compté.

Restent à traiter : accueil, dashboard, crypto, glossaire, fiche, events, screener, universe,
échecs, méthode, macro, data, live, investors, fundamentals. Le glossaire est volontairement
technique par nature.

## Session 2026-09-08 (nuit) — Trois ajouts pendant que l'utilisateur dort

Consigne : « fais tout le reste, on testera au réveil sur données réelles ». J'ai donc pris
ce qui était faisable SANS les bases réelles, et laissé le reste plutôt que de deviner.

**Le banc n'était pas déterministe — et c'était le plus urgent.** Ouvert en P2 la veille,
fermé ici. Cause ISOLÉE, pas supposée : `GradientBoostingClassifier` sans `random_state`
consomme le générateur aléatoire GLOBAL de numpy pour départager les égalités entre découpes
d'arbre. Vérifié en figeant ce générateur — la séquence devenait reproductible, ce qui
désignait la cause sans ambiguïté. La graine est posée sur l'ESTIMATEUR, jamais par
`np.random.seed()` : figer le générateur global depuis une bibliothèque contaminerait tout le
processus, y compris des tirages qui doivent rester indépendants. Trois exécutions de
`demo_ml.py` sont maintenant identiques au caractère près. Sans ça, la migration Mac → NVIDIA
n'aurait pas pu être validée : on n'aurait pas su distinguer un écart de matériel d'un écart
de logique.

**Explicabilité — le manque que comble `cuml.explainer`.** « Le modèle donne 68 % » n'explique
rien, c'est la chose même qu'il faudrait expliquer. Deux lectures distinctes : importance par
permutation (globale) et valeurs de Shapley (locale). Le garde-fou est l'EFFICIENCE — les
contributions somment exactement à `f(x) − moyenne(f(fond))`, un théorème. Sans ce test,
n'importe quel histogramme normalisé passerait pour une explication.

*Erreur commise et corrigée* : ma première version tirait la référence AU HASARD à chaque
permutation. La somme retombait alors sur la moyenne de l'échantillon TIRÉ, pas du fond —
l'efficience n'était plus exacte, à 1e-2 près. J'ai d'abord été tenté de relâcher la tolérance
du test ; c'eût été supprimer le seul garde-fou. Le parcours systématique de chaque référence
rétablit l'exactitude sans rien coûter.

**Anomalies croisées — l'angle utile de NV-Tesseract : surveiller, pas prédire.** Les contrôles
existants vérifient chaque série SÉPARÉMENT et attrapent l'impossible (prix négatif, OHLC
incohérent). Ils ne voient pas le POSSIBLE MAIS ABSURDE : un split non ajusté, un tick erroné,
un flux figé. On compare donc chaque actif à la COUPE du jour — médiane et MAD, jamais moyenne
et écart-type : un jour de krach, une poignée de valeurs extrêmes déplacerait la moyenne au
point de rendre tout le reste « normal ». Test dédié : un krach général à −12 % ne doit
déclencher AUCUNE alerte.

Le flux figé est le plus dangereux des trois, et il rejoint directement l'ADR du Mean-CVaR :
un cours immobile n'a ni dispersion ni queue, donc il paraît sans risque à TOUS les
optimiseurs, variance comme CVaR. Aucun contrôle de forme ne peut le voir.

**Ce que je n'ai PAS fait, et pourquoi.** Le P0 du journal (pas la vraie base ici), le sens de
fusion `_index_series` (le TODO exige de confirmer avant de corriger), le câblage d'Almgren
(change les tailles de position réelles), les séries macro (clé FRED absente), l'élargissement
des délistés (données absentes). Deviner sur l'un de ces points aurait coûté plus cher que de
ne rien faire.

Aucun des trois modules n'est branché en production — ni ceux-ci, ni le Mean-CVaR, ni le
générateur de signaux. C'est le rendez-vous du réveil.

## Session 2026-09-07 (suite 36) — Portabilité Mac ↔ NVIDIA : trois points de contact, pas cent

Demande : rendre le code « 100 % device-agnostic » avant migration du Mac (MPS) vers une
machine NVIDIA (CUDA), en remplaçant tous les `.to("mps")`, `.cuda()` et `.to("cpu")` codés
en dur.

**L'audit a d'abord contredit la prémisse, et c'était l'information utile.** Il n'existe
**aucun** appareil codé en dur dans le dépôt : zéro `.to("mps")`, zéro `.cuda()`. `torch`
n'apparaît que dans une docstring. `lightgbm` est déclaré en dépendance mais n'est importé
nulle part ; `catboost` n'existe pas dans le projet. Le seul appel à accélérer était UNE
instanciation `XGBClassifier`, plus le pipeline FinBERT qui choisissait son matériel seul.

Le dire valait mieux que produire un gros diff sur du code inexistant. La refonte porte donc
sur **trois points de contact** — et sur une infrastructure qui empêchera le problème de
naître quand torch entrera vraiment dans le projet.

**Ce qui a été construit** : `packages/common/device.py` — détection CUDA → MPS → CPU
(surchargeable par `QUANT_DEVICE`), `torch_device()`, `device_index()` pour HuggingFace,
`params_arbres(lib)` pour les trois bibliothèques d'arbres, `activer_cudf()`, bannière
« Exécution sur : … ». Rien n'est importé au niveau module : le cœur du dépôt ne déclare
aucune dépendance, et ni torch ni xgboost ne sont installés en CI.

**Deux pièges qui auraient coûté cher, et qu'il fallait traiter à contre-courant de la
demande.**

1. *`cudf.pandas` n'est pas un import de repli.* La consigne était « try: import cudf.pandas,
   sinon pandas ». Ça ne marche pas : `cudf.pandas` est un CROCHET D'IMPORTATION à poser avant
   que pandas n'entre en mémoire, pas un module ayant l'API de pandas. Posé trop tard, il ne
   fait rien **et ne lève rien** — on se croirait accéléré en tournant sur processeur. D'où
   l'appel en tête des points d'entrée et un message explicite quand c'est trop tard.

2. *La version d'XGBoost se LIT.* La 2.0 a remplacé `tree_method="gpu_hist"` par
   `tree_method="hist"` + `device="cuda"`. L'ancienne forme est ignorée en silence par la
   nouvelle : parier ferait tourner sur processeur une machine à 10 000 € sans un message.
   Corrigé au passage : `use_label_encoder=False`, retiré d'XGBoost 2.0, faisait lever
   l'instanciation sur toute installation récente — un bug latent, pas lié au matériel.

**Preuve de non-régression, et son revers.** J'ai comparé la sortie complète de
`scripts/demo_ml.py` avant/après : une ligne différait (accuracy sklearn). Avant d'accuser mon
changement, j'ai lancé deux fois la MÊME version : elles diffèrent aussi. **Le script est non
déterministe par lui-même** — `GradientBoostingClassifier` sans `random_state`. La différence
ne venait pas de moi, mais elle a révélé un vrai défaut : un banc de mesure dont deux
exécutions ne coïncident pas ne peut pas servir à comparer quoi que ce soit. Ouvert en P2.

La preuve retenue est donc structurelle : le diff de calcul se réduit à deux appels
(`params_arbres` et `device_index`), tout le reste est de la documentation et des points
d'entrée. 20 tests, contrôle négatif vérifié (ordre saboté → 7 rouges).

## Session 2026-09-07 (suite 35) — « fais tout ce qui reste » : ce qui est fait, ce qui est bloqué

Six chantiers livrés, un bloqué faute de données, deux volontairement non faits.

**Bloqué, et il faut le dire clairement.** Le P0 de réconciliation du journal ne peut PAS être
joué depuis cette session : `data/journal.db` y contient **0 trade**. C'est un fichier vide
d'amorçage, pas le journal réel (313 lignes, synchronisé Mac↔VPS le 05/09), et il n'est même pas
suivi par git. Lancer `--appliquer` dessus n'aurait rien réparé et aurait produit une archive
trompeuse. Les commandes sont dans le TODO, à jouer sur la machine qui détient la vraie base.

**Dates d'arrêté — la synergie qui manquait vraiment.** Trois dates coexistaient sans explication.
L'inventaire existait déjà (`coherence_site.dates_d_arrete`) mais ne sortait que dans les journaux
de fabrication. Il est maintenant publié dans `meta` et affiché sur chaque page, avec l'écart au
bloc le plus frais du site — et la raison possible, parce qu'une fenêtre de mesure close ne devient
pas fausse en vieillissant. Vérifié : l'alerte se déclenche sur `/data` (18/06) et `/universe`,
pas sur `/screener` (2 jours d'écart, sous le seuil).

**Le défaut trouvé en chemin est le plus intéressant** : `/api/universe` publiait `as_of: now()`.
La liste d'actifs se déclarait donc fraîche du jour même quand ses fichiers sources n'avaient pas
bougé depuis des mois — et l'inventaire CENSÉ SURVEILLER la fraîcheur la comptait parmi les blocs à
jour. Une fraîcheur affirmée sans être vraie est pire qu'une date ancienne assumée : elle empêche
de repérer la source qui a cessé d'être rafraîchie. `as_of` = date du fichier le plus récent ; la
date de fabrication garde sa place sous `genere_le`.

**Le tri conclut.** `/fiche` savait déjà aller jusqu'à « et donc, j'achète ou pas » ; le screener
s'arrêtait au classement. La jointure est extraite dans `lib/verdicts.ts` et partagée — **même
moteur `decide()`**, pas une version liste plus permissive. Deux verdicts divergents sur le même
titre selon la page ouverte serait pire que pas de verdict du tout.

**Fenêtre d'exclusion visible.** Le moteur écartait déjà les titres publiant sous 7 jours ; rien ne
le disait. Le calendrier l'affiche, avec LA constante importée du moteur — deux nombres auraient
dérivé au premier réglage.

**Seuil de promotion — la correction dont je suis le plus sûr.** Le gate promouvait à +0,05 quand
onze ans ne résolvent que ±0,118. Le labo imprimait déjà l'avertissement sans en tirer la
conséquence. Le remplacer par 0,12 aurait juste déplacé l'arbitraire : le seuil DEVIENT la
résolution mesurée de l'échantillon, plancher d'exécution à 0,05. Il donne 11 ans → +0,118,
20 ans → +0,087, 60 ans → +0,051 : **exactement les valeurs relevées le 31/08**, ce qui confirme
que l'implémentation reproduit la mesure au lieu de la réinventer. Nouveau verdict `🟡 INDISTINCT`
pour l'entre-deux — ni promu ni rejeté, parce que la donnée ne permet pas de trancher.

**Volontairement PAS fait, et pourquoi.**
- `_index_series` / sens de fusion des bases : le TODO exige de CONFIRMER par le bloc
  « comparaison des deux bases » avant de corriger. Sans `YAHOO.db` ni `market.db` ici, corriger
  serait deviner — sur la moitié du portefeuille de production.
- Câblage d'`almgren_chriss` au dimensionnement : ça change les tailles de position réelles. Ça se
  mesure avant, pas après.

**Piège récurrent, cinquième et sixième occurrence** : `pkill -f` a tué mon propre shell deux fois
(code 144), y compris avec la parade `[ ]`. Et un `next start` resté vivant m'a servi un ANCIEN
build pendant une vérification — j'ai lu « fonctionnalité absente » sur du code qui la contenait.
Réflexe à garder : tuer par PID relevé avec `ps`, jamais par motif.

**Contrôle négatif systématique.** Un audit qui affiche zéro sans avoir jamais rien détecté ne vaut
rien : chaque vérification a été rejouée sur l'état d'avant (365 éléments hors écran, test de seuil
sabotté → rouge). Une fois, mon propre contrôle était faux — le titre de colonne « ce qu'on en
conclut » ne matchait pas parce que le CSS le met en majuscules ; c'est la vérification qui était
cassée, pas la fonctionnalité.

## Session 2026-09-07 (suite 34) — 365 éléments hors écran, invisibles depuis toujours

Retour de l'utilisateur : « les textes et fonctions aux bords de l'écran sont parfois
inaccessibles ». Mesuré avant de toucher quoi que ce soit, Chromium à 390 px, sur les pages
réelles rendues avec des jeux de données de mise en page :

    ancien CSS  →  365 éléments hors écran ET sans parent défilable
    corrigé     →    0

Pire cas `/fundamentals` : le tableau dépassait de **492 px**, soit la moitié de ses quatorze
colonnes. « Solidité », « Risque de faillite », « Tendance du cours », « Note d'ensemble »,
« Avis » : hors d'atteinte, ni au doigt ni par script. Et **rien ne le signalait** — le tableau
semblait simplement s'arrêter à « Décote estimée ». C'est le pire genre de défaut : celui qui
n'a pas l'air d'un défaut.

**La cause n'est aucun tableau en particulier.** C'est la rencontre de deux règles chacune
raisonnable : `html, body { overflow-x:clip }`, posé comme garde-fou anti-débordement latéral,
et quatorze tableaux écrits hors de tout conteneur `overflow-x-auto`. `clip` coupe SANS créer
de zone défilable — contrairement à `hidden`, il n'y a aucun accès au contenu débordant. Le
garde-fou anti-débordement fabriquait le contenu inaccessible.

Envelopper les quatorze tableaux marchait ce jour-là ; le quinzième, écrit le mois prochain,
ramenait le bug. La correction est donc **structurelle** : sur mobile, tout `<table>` devient
son propre conteneur de défilement (`display:block; overflow-x:auto; width:max-content;
min-width:100%`). Vérifié à la mesure avant de l'appliquer, parce que je doutais que
`display:block` préserve la mise en colonnes : en-tête et corps restent alignés **au pixel**
(mêmes abscisses), et un tableau étroit continue de remplir sa carte sans défiler.

Deux autres débordements mesurés dans la foulée :
- **Bulles d'aide** : 240 px centrées sur une icône de 15 px. Dès que l'icône est à moins de
  120 px du bord — le cas ORDINAIRE en colonne de droite — 99 px de texte partaient hors écran
  et étaient coupés. Sur mobile la bulle quitte l'ancrage et se pose en bas de l'écran, pleine
  largeur : jamais coupée, quelle que soit la position de l'icône.
- **Marges de `main`** : 14 px fixes, donc SOUS l'encoche en paysage sur iPhone.
  `max(14px, env(safe-area-inset-*))` garde le plus grand des deux et ne coûte rien quand la
  marge de sécurité vaut zéro. Même correctif sur le tiroir de navigation, qui colle au bord droit.

**Le zéro ne prouve rien sans témoin.** J'ai rejoué le même audit avec l'ancien CSS remis en
place : 365. C'est cette comparaison qui vaut, pas le zéro seul — un audit aveugle affiche zéro
aussi. Même discipline sur le test de non-régression ajouté
(`tests/web/test_mobile_pas_de_hors_ecran.py`) : règle sabotée → rouge, restaurée → vert. Un
test incapable d'échouer ne garde rien.

Piège de la session, quatrième ou cinquième occurrence : `pkill -f "next start -p 3100"` a tué
mon propre shell (code 144), deux fois de suite, y compris avec la parade `[ ]` — le motif reste
dangereux dès qu'il décrit une commande que je viens de taper. Réflexe à garder : lancer en
`nohup … &` et vérifier avec `ps aux | grep "[n]ext start"` plutôt que tuer à l'aveugle.

## Session 2026-09-07 (suite 33) — Les quatorze pages restantes, même règle

Suite directe : « fais les quatorze autres pages ». Même règle qu'à la suite 32 — **simplifier le
VOCABULAIRE, jamais le CONTENU**. Aucun chiffre, aucun seuil, aucune réserve n'a été retiré.

**`accueil` : non réécrite, et c'est la bonne décision.** Sa prose était déjà en langage courant
(« Un outil qui trie les marchés à votre place, explique chacun de ses choix, et dit franchement ce
qu'il ne sait pas »). La réécrire pour pouvoir cocher quatorze au lieu de treize aurait été du
travail pour le compteur, pas pour le lecteur.

Pages traitées : `methode`, `echecs`, `screener`, `dashboard`, `data`, `live`, `universe`, `macro`,
`investors`, `fundamentals`, `fiche`, `events`, `crypto`. Le glossaire portait déjà sa traduction
« en clair » sous chaque terme et n'appelait rien.

Deux formes récurrentes, appliquées partout :
- **La question avant la réponse.** Chaque étage du gate de `/methode` s'ouvre désormais sur ce
  qu'il cherche (« combien d'idées a-t-il fallu essayer avant de tomber sur celle-là ? »), la
  formule SR* et la référence López de Prado restant intégralement en dessous. La rigueur n'a
  jamais exigé d'être illisible.
- **L'explication au survol plutôt qu'en note.** `Col.title` ajouté à `SortableTable` : un
  en-tête de colonne porte sa définition sans allonger la page. « PER » devient « Prix /
  bénéfices » avec, au survol, « combien d'années de bénéfices actuels il faut pour rembourser le
  prix de l'action ».

Exemples, à contenu strictement égal :
- « Le rendement hors-QQQ n'est PAS une preuve de compétence (DSR≈0) » → « La part qui ne vient pas
  de QQQ ne prouve PAS un savoir-faire : le plus souvent, c'est l'exposition à d'autres choses que
  QQQ, plus de la chance »
- « Biais du survivant » → « les actifs qui ont disparu de la cote sont remis dans les calculs :
  ne garder que les survivants ferait croire que tout finit par monter »
- « rendement pondéré dans le temps · un virement n'est ni un gain ni une perte » → « vos versements
  et retraits sont mis de côté dans le calcul : seule la façon dont l'argent a travaillé compte »
- « le screen capte peut-être UN thème, pas N opportunités indépendantes » → « c'est peut-être une
  seule et même idée répétée dix fois : dix titres qui montent et descendent ensemble ne protègent
  de rien »
- « Trading SPOT uniquement » → « on achète et on vend comptant : jamais d'argent emprunté, jamais
  de pari à la baisse »
- « funding positif = les longs paient les shorts (biais contrarian baissier) » → « les parieurs à
  la hausse paient — ils sont trop nombreux, ce qui annonce souvent une correction »

Vérifié : `npx tsc --noEmit` propre sur les fichiers touchés (seules subsistent les deux erreurs
`three` préexistantes de `components/landing/Scene.tsx`), `npm run build` vert sur les 26 pages.

## Session 2026-09-07 (suite 31) — 99 % sur une ligne : correct, et impossible à vérifier

Question : est-il normal que « Prudent » propose 99 % sur NEAR, « Dynamique » 99,8 %, et « Neutre »
une répartition de 1,7 % à 21,9 % ?

**Première hypothèse, FAUSSE.** J'ai supposé une instabilité d'estimation (T/N = 31, covariance
empirique non régularisée alors que la production applique Ledoit-Wolf). Mesuré sur un cas
reconstruit : δ* = 0,05, et le poids maximal passe de 87,0 % à 88,0 %. Le shrinkage ne change RIEN
ici. L'hypothèse était plausible et le chiffre l'a écartée.

**La vraie explication.** Reproduction sur neuf actifs à ~73 % de volatilité et un à 18 % :
min-variance 87 % sur le calme, HRP 77 %, ERC 25 % maximum. Les trois profils du site montrent
exactement ce profil. Ce n'est pas un défaut : minimiser la variance CONCENTRE sur l'actif de plus
faible variance, et l'ERC ne le fait pas parce qu'il égalise les contributions au risque par
construction. L'écart entre les profils n'est pas un bug — c'est leur définition.

**Ce qui manquait vraiment : de quoi le VÉRIFIER.** Sans les volatilités individuelles sous les
yeux, un poids de 99 % est indistinguable d'un bug — et, plus grave, d'une SÉRIE ARRÊTÉE, qui n'a
plus de variance récente et que l'optimiseur prend pour l'actif le plus sûr du panier. Le chemin
« Mon portefeuille » n'avait ni garde-fou de fraîcheur ni volatilité par ligne, alors que la
recommandation a les deux depuis ce matin.

`diagnostic_par_actif` publie désormais la volatilité annualisée et la dernière barre de chaque
ligne détenue, et signale les séries arrêtées. **Il ne retire rien** — contrairement à la
recommandation : ces lignes sont DÉTENUES, on ne les écarte pas du portefeuille de leur
propriétaire. On l'avertit, il décide. L'affichage nomme la plus calme, la plus agitée et leur
rapport, et rappelle que le champ « poids maximal » est le garde-fou prévu pour ça.

## Session 2026-09-07 (suite 30) — « 25,6 positions effectives » pour 14 actifs

Impossibilité mathématique, repérée dans la capture de l'utilisateur : 1/Σw² ne peut pas dépasser
le nombre de lignes. Cause : le budget de perte avait ramené l'exposition à 47,3 %, les poids ne
sommaient donc plus à 1, et la formule gonflait mécaniquement — quatorze lignes équipondérées à
47,3 % d'exposition donnent 62,6.

La mesure porte sur la RÉPARTITION des poids, pas sur leur somme : les liquidités ne sont pas une
quinzième position. Normalisation avant calcul, et trois tests, dont un qui balaie 3/14/40 lignes ×
trois niveaux d'exposition — la valeur doit être identique, seule la répartition compte.

À noter : le ratio de diversification, lui, est invariant d'échelle par construction —
(Σwᵢσᵢ)/σₚ, numérateur et dénominateur se multiplient par le même facteur. Il n'était pas touché.
C'est précisément pourquoi l'erreur était difficile à voir : trois métriques côte à côte, deux
justes, une fausse.

## Session 2026-09-07 (suite 29) — Chercher un edge sans se mentir, et des préférences qui ont un prix

**1. « Ajouter les actifs au meilleur set-up » — la seule réponse honnête est un protocole.**
Un IC de +0,0202 à t = 0,76 n'est pas « pas d'edge » : c'est « indiscernable de zéro À CET
HORIZON, SUR CET UNIVERS ». Reste à chercher ailleurs — mais chercher, c'est multiplier les
essais, et vingt essais à 5 % produisent un « significatif » par pur hasard.

`scripts/balayage_ic.py` (`make balayage-ic`) balaie horizons × classes d'actifs, calcule une
p-valeur par cellule et applique **Benjamini-Hochberg sur l'ensemble** : chaque cellule est jugée
en sachant combien d'autres ont été tentées. Toutes les cellules — surtout les rejetées — sont
consignées au registre, car le compteur d'essais déflate le Sharpe et un balayage non consigné le
fausserait à la hausse. Si une cellule survit ET tient hors échantillon, le profil « Conviction »
s'ouvre de lui-même. Sinon la sélection reste un classement, et on le sait.

**2. Préférences sectorielles — des CONTRAINTES, jamais des vues.** « Privilégier la santé » a deux
sens : une prévision (que rien ne valide ici) ou une contrainte personnelle (qui n'exige aucune
preuve). `packages/portfolio/preferences.py` n'implémente que la seconde : exclusions, planchers,
plafonds, appliqués dans cet ordre — une exclusion est absolue et prime sur un plancher.

**Deux défauts trouvés par mes propres tests avant livraison.** Un plancher RESSUSCITAIT un secteur
mis à zéro, y compris un secteur qu'on venait d'exclure : la répartition « à parts égales » quand le
groupe pèse zéro inventait des lignes que le modèle de risque avait refusées. Corrigé : un plancher
ne crée jamais une position à partir de rien, il est déclaré NON SATISFAIT avec sa raison.

**Le coût est publié.** Une contrainte détourne du poids d'une allocation qui minimisait le risque :
volatilité, ratio de diversification et positions effectives sont rendus avant/après. Le champ
s'appelle `ecart_vol` et non « surcoût » — exclure un actif très volatil FAIT BAISSER la
volatilité, et le nommer surcoût serait faux. Une préférence qu'on croit gratuite est une préférence
mal posée.

`recommendation.py` atteignait 465 lignes : contraintes extraites dans
`packages/portfolio/contraintes.py` (317 + 164). 2123 tests passés ; build vert.

## Session 2026-09-07 (suite 28) — LA CAUSE : PM2 ressuscitait le front derrière nous

Le diagnostic de filiation, ajouté au tour précédent, a livré la réponse en quatre lignes :

    860440  next-server     (parent 860439)
    860439  sh              (parent 860404)
    860404  npm run start   (parent 40536)
    40536   PM2 v7.0.4: God (parent 1)

**PM2 supervisait le front**, installé avant les services systemd. Son démon relance
l'application dans les secondes suivant chaque arrêt. Tuer le processus ne servait donc à RIEN :
il renaissait aussitôt, et le symptôme ressemblait à un orphelin tenace.

Tout ce qui a été écrit aujourd'hui contre les « orphelins » — nettoyage par port et par nom,
`KillMode=control-group`, exec du binaire local, garde de réservation — était juste, utile, et
**incapable d'atteindre la cause**. Deux superviseurs se disputaient le port 3000 depuis le matin.

**Un processus qui renaît n'est pas un orphelin : c'est quelqu'un qui le redémarre.** Cette
distinction manquait à toute mon analyse. Je cherchais un processus abandonné là où il y avait un
processus entretenu.

Deux détections ajoutées, aux deux moments utiles. `stop_services.sh` avertit que PM2 annulera son
propre travail et liste les applications supervisées. `verifier_service.sh` nomme PM2 dans le
verdict de filiation et donne la procédure — car « tuer le PID » est précisément le conseil qui ne
marche pas ici.

Rappel de méthode : c'est le diagnostic qui IMPRIME CE QU'IL A VU, ajouté après deux verdicts que
je ne savais pas justifier, qui a résolu la journée. L'assertion sans preuve avait tenu huit heures.

## Session 2026-09-07 (suite 27) — Mes commentaires s'exécutaient : l'installateur se relançait lui-même

    scripts/install_services.sh: line 42: mixed: command not found
    ✗ Refus d'installer les services sous root …   (deux fois)

Le heredoc qui écrit l'unité systemd n'est pas protégé — il DOIT interpoler `$UTILISATEUR`,
`$RACINE`, `$VERSION_UNITE`. Bash y traite donc les accents graves comme des substitutions de
commande, **y compris dans ce qui ressemble à un commentaire**. Mon commentaire « régénéré par
[make services] » a donc relancé l'installateur RÉCURSIVEMENT, sous root, qui a refusé — et les
unités ont été écrites au milieu de messages d'erreur.

**Troisième occurrence du même piège dans la journée** : `make stop` ce matin (pkill qui se tuait
lui-même), la garde de démarrage cet après-midi (accents graves autour de « make start »), et
maintenant l'installateur. Le repérer à l'œil ne suffit visiblement pas : `tests/scripts/
test_unite_systemd.py` interdit désormais tout accent grave et toute `$(...)` dans le gabarit,
vérifie que les variables attendues y sont bien interpolées, et que `KillMode=mixed` n'est pas
réintroduit.

**Verdict « PID étranger » : je ne sais toujours pas s'il est juste.** Il est tombé deux fois sur
des PID espacés de 35, donc probablement parent et enfant. Ma remontée de filiation a été testée et
fonctionne sur un couple réel — mais je ne peux pas exclure qu'elle manque un cas. Plutôt que de
trancher au jugé, le diagnostic imprime maintenant la filiation OBSERVÉE (PID, commande, parent, sur
six niveaux) et le cgroup du service, avec la question posée franchement : si le PID figure dans le
cgroup, c'est ma remontée qui échoue. Un diagnostic qui ne montre pas ce qu'il a vu oblige à le
redemander.

## Session 2026-09-07 (suite 26) — Ratios de structure, et un turnover que j'avais faussé

**Défaut introduit hier soir, trouvé dans la capture d'écran.** Le turnover affichait 100 % sur
les trois profils alors qu'ils investissent de 37,6 % à 81,1 %. Cause : la ligne « Liquidités »,
ajoutée pour rendre visible l'exposition réduite par le profil, était comptée comme un ACHAT dans
`Σ|Δ|/2`. Le cash est ce qui RESTE après les ventes, pas un instrument qu'on acquiert. Corrigé :
68,8 % au lieu de 100 %, coût 103 € au lieu de 150 € — une surestimation de 45 %.

**Ratios ajoutés — tous des constats, aucun n'est une prévision.** `packages/portfolio/indicateurs`.

*Par ligne* : plus haut / plus bas 52 semaines, position dans la bande, et distance au plus haut.
Ce dernier est le seul qui se lise sans contexte : −40 % exige +67 % pour revenir, asymétrie que
le pourcentage de baisse masque.

*Par allocation* : volatilité annualisée, **ratio de diversification** (Σwᵢσᵢ)/σₚ — vaut 1,0 quand
tout bouge ensemble, et dix lignes n'y valent alors pas mieux qu'une —, **positions effectives**
(1/Σw², qui corrige le nombre de lignes de leur concentration : quatorze dont une à 38 % n'en valent
que 5,7), corrélation moyenne des paires, et Sharpe RÉALISÉ.

**Ce qui a été refusé : l'objectif de cours.** Il faudrait le déduire d'un nom ou l'acheter à un
tiers, et sa valeur prédictive n'est mesurée nulle part ici. Le publier à côté d'une allocation
contredirait le résultat du jour même — IC +0,0202, t = 0,76. Le Sharpe réalisé est le cas limite :
c'est un constat, mais il se lit comme une promesse ; il voyage donc avec un avertissement dans la
charge utile elle-même, pas dans un commentaire, et son biais est nommé — l'allocation a été
choisie EN CONNAISSANT ces prix.

`PortfolioScenarios.tsx` atteignait 404 lignes : panneaux extraits dans `PortfolioPanneaux.tsx`
(207 + 220). 10 tests dédiés ; 2106 passés ; build vert.

## Session 2026-09-07 (suite 25) — Vérifier tôt : une garde tardive coûte tout ce qu'elle laisse faire

Trois messages d'échec, une seule cause : l'unité systemd n'avait pas été réinstallée. Le contrôle
de version d'unité, ajouté juste avant, faisait son travail — mais à la FIN de `make up`, après
deux minutes de recompilation inutile. Une vérification tardive ne coûte pas seulement du temps :
elle laisse le système faire tout le travail avant de refuser, ce qui décourage de la relancer.

Le contrôle d'unité s'exécute désormais en PREMIER (`verifier_service.sh --unite`), avant tout
arrêt, tout nettoyage et toute recompilation. Les deux autres contrôles — qui tient le port, quel
build est servi — restent à la fin, où ils ont un sens : ils portent sur un état qui n'existe
qu'après le démarrage.

Ordre général de la journée, retrouvé une fois de plus : ce qui peut être vérifié avant d'agir doit
l'être avant d'agir.

## Session 2026-09-07 (suite 24) — Une consigne orale n'est pas un mécanisme

`make up` a enfin dit la vérité : « Le port 3000 est tenu par le PID 818916, ÉTRANGER au service
quant-web (PID 818895) ». Vérification de la vérification : la logique de filiation a été rejouée
localement sur un vrai couple parent/enfant — elle remonte correctement. Le verdict était donc
juste, et le port tenu par un orphelin d'une tentative antérieure dont le parent est mort.

**Cause : `make services` n'a pas été relancé.** Le changement de `KillMode` vit dans le fichier
`/etc/systemd/system/quant-web.service`, pas dans le dépôt. Je l'avais signalé en prose ; ça n'a
pas suffi, et rien dans l'outillage ne l'imposait. Le service a donc continué à laisser des
orphelins pendant que `git log` montrait le correctif appliqué — la pire configuration : le
correctif EXISTE, il n'est pas ACTIF, et tout indique le contraire.

L'unité générée porte désormais `# quant-unit-version: N`, et `make up` compare cette valeur à
celle attendue par le dépôt. Une unité obsolète fait échouer la vérification en nommant la
commande de réinstallation. Toute modification future du gabarit devra incrémenter `VERSION_UNITE`,
sinon l'écart passera de nouveau inaperçu.

C'est la même leçon que le reste de la journée, appliquée à la configuration système : ce qui n'est
pas vérifié par une machine finit par diverger sans bruit.

## Session 2026-09-07 (suite 23) — Mon unité systemd FABRIQUAIT les orphelins qu'elle subissait

L'orphelin tué, un autre reprenait le port. Ce n'était donc pas un accident de session SSH : la
source était mon unité elle-même, par deux défauts qui se combinent.

**1. `exec npx next start`.** `exec` remplace bien bash par npx — mais npx SPAWNE ensuite Next
comme enfant. Le processus que systemd surveille (`MainPID`) n'est donc PAS celui qui tient le
port. À l'arrêt, systemd signale le principal, npx s'en va, et le serveur reste derrière lui.
Chaque redémarrage fabriquait un orphelin de plus. Corrigé en appelant le binaire local :
`exec ./node_modules/.bin/next start` — le processus surveillé EST celui qui écoute.

**2. `KillMode=mixed`.** Ce mode n'envoie le signal d'arrêt qu'au processus principal. Tout enfant
qui lui survit garde ses ressources — ici, le port 3000. Retour au défaut `control-group` : le
signal va à TOUS les processus du service. À lui seul, ce réglage aurait suffi à empêcher
l'accumulation, quelle que soit la forme de l'arbre de processus. Je l'avais changé sans nécessité.

Les deux correctifs sont indépendants et cumulés délibérément : le premier rend l'arbre correct, le
second garantit le nettoyage même si l'arbre ne l'est pas.

Vérifié : `./node_modules/.bin/next start` sert la page en HTTP 200.

**Le changement de `KillMode` impose de RÉÉCRIRE l'unité** — `make services` avant `make up`, dans
cet ordre, sinon systemd relit l'ancien fichier.

Note de méthode, troisième occurrence du jour : en nettoyant ce test j'ai lancé `pkill -f "3888"`,
qui a tué mon propre shell — le motif figurait dans sa ligne de commande. Exactement le défaut
corrigé le matin dans `make stop`. Un motif `pkill` doit toujours être écrit pour ne pas se
reconnaître lui-même.

## Session 2026-09-07 (suite 22) — L'orphelin identifié : `systemctl restart` ne tue que les siens

Diagnostic confirmé sur le VPS, sans ambiguïté :

    LISTEN *:3000  users:(("next-server (v1",pid=757591,fd=18))
    quant-web.service : activating (auto-restart) (Result: exit-code) status=1/FAILURE

Un `next-server` orphelin, né d'un `make start` d'une session SSH fermée, tenait le port 3000
depuis des heures. Le service systemd bouclait en échec toutes les cinq secondes, et le navigateur
parlait à l'orphelin — page fonctionnelle, code vieux de quinze commits, aucun signal.

**Le défaut de `make up` :** il faisait `systemctl restart`, qui ne tue QUE les processus du
service. L'orphelin, par définition, n'en fait pas partie : il survivait à toutes les relances.
`make services` appelait bien `stop_services.sh`, mais `make up` — la commande du quotidien — ne
l'appelait pas. Le nettoyage existait et n'était pas branché là où il servait tous les jours.

Ordre corrigé, et l'ordre est le fond du correctif : arrêter les services, PUIS nettoyer les
orphelins, PUIS démarrer. Nettoyer avant d'arrêter tuerait le service en cours sous les pieds de
systemd et déclencherait une tempête de redémarrages.

## Session 2026-09-07 (suite 21) — « ça répond » n'est pas « le bon processus sert le bon code »

Après vingt commits, la page affiche toujours l'ancien code : avertissement figé, trois profils,
paires USDC manquantes, et surtout « historique commun jusqu'au 2026-06-17 » — BK est encore là.
`make up` annonce pourtant « front prêt » à chaque fois.

Hypothèse principale : un `next dev` orphelin d'une session SSH morte tient le port 3000, le
service systemd ne peut pas s'y lier et boucle, et le navigateur parle à l'ancien processus. La
page FONCTIONNE, elle sert du code vieux de quinze commits, et rien ne le signale.

C'est la troisième fois de la journée qu'un outil dit « fait » sans que ce soit vrai — après
`make stop` qui annonçait « arrêté » sans rien arrêter, et la garde de port qui répondait « libre »
sur un port occupé. Le point commun : la vérification portait sur un SYMPTÔME (ça répond, ça rend
0) et non sur le FAIT (qui répond, avec quel code).

`scripts/verifier_service.sh`, appelé par `make up`, pose les deux vraies questions :
1. **Qui tient le port** — le PID doit remonter, par filiation, au MainPID du service. Un
   processus étranger est nommé, avec la commande pour le tuer.
2. **Quel build** — le tampon `apps/web/.quant-build-commit` doit valoir la tête courante.

`make up` échoue désormais bruyamment au lieu d'annoncer une réussite qu'il n'a pas vérifiée.

## Session 2026-09-07 (suite 20) — La recommandation allouait 57 % à des séries mortes

L'audit d'univers a révélé ce que dix heures de travail sur cette carte n'avaient pas vu. Les
6 périmés — **BK (18 juin), EA (10 août), EQR (21 août)**, CA (26 mai), AVB, LEG — comprennent
TROIS des six lignes recommandées, soit 57 % du portefeuille proposé.

**Cause racine : un prédicat pour deux questions.** `is_real_mode` refuse « mixte » à juste titre
— un seul titre en repli synthétique interdit de CERTIFIER l'univers réel. Mais le nettoyage des
titres périmés était gardé par ce même prédicat, alors qu'il ne pose pas cette question : il
demande seulement si les dernières barres sont des dates comparables. Le VPS tourne en « mixte » :
le nettoyage ne s'est donc JAMAIS exécuté en production. `contient_des_prix_reels` répond
désormais à la seconde question, et les deux prédicats sont testés comme DISTINCTS.

**Deux dégâts, le second plus vicieux que le premier.**
1. L'alignement par intersection ramenait la fenêtre commune à la dernière barre du plus mort :
   la carte affichait « historique commun jusqu'au **2026-06-17** » — la dernière barre de BK —
   et personne, moi compris, n'y a vu un avertissement. Trois mois de données perdus pour tous.
2. Une série figée n'a plus de variance récente. Un min-variance la prend pour l'actif le moins
   risqué de l'univers et la surpondère mécaniquement. **La donnée morte n'est pas seulement
   inutile : elle attire le capital.** C'est ce qui explique BK à 16,5 %, EA à 20 %, EQR à 20,9 %.

Défense en profondeur : `ecarter_perimes` retire les séries arrêtées AVANT tout calcul, seuil
relatif à la barre la plus fraîche des candidats, dates non ISO → on n'écarte personne plutôt que
d'écarter au hasard. Les exclusions sont publiées avec leur dernière date, en ambre.

Ce défaut n'a été trouvé ni par les tests ni par moi : par un audit demandé pour une autre raison
(les noms manquants), dont l'utilisateur a lu la sortie brute. 2096 tests passés.

## Session 2026-09-07 (suite 19) — 517 noms écrits, et un refus de signer la liste des 77

`make noms-univers` a écrit 517 noms sur 594. Les 77 restants sont classés « inconnu du
fournisseur » sur la foi de 404 explicites (« Quote not found for symbol: SEE »), ce qui est un
INDICE de délistage — pas une preuve. `BK` et `CMA` figurent dans cette liste, et rien ici ne
permet d'affirmer qu'ils sont morts. Un fournisseur peut ignorer un ticker parfaitement coté
(changement de place, suffixe, panne de son côté).

Le risque d'une purge sur cette seule base est ASYMÉTRIQUE : un titre retiré à tort ne se signale
jamais, il manque simplement — et rien ne le détecte ensuite. D'où `make audit-univers`, en lecture
seule, qui tranche sur les PRIX locaux : un titre délisté cesse d'avoir des barres.

Le seuil est RELATIF à la barre la plus fraîche de l'univers, jamais à l'horloge : un seuil absolu
déclarerait tout l'univers périmé un lundi férié ou après une semaine sans ingestion. C'est la règle
déjà appliquée par `build_snapshot`, reprise et non réinventée. Trois catégories, dont une pour
l'ignorance : vivants, périmés, et sans aucune barre locale — ne pas savoir n'est pas savoir à
moitié. 5 tests.

## Session 2026-09-07 (suite 18) — `ABC → Abell Coin USD` : le repli crypto contaminait les actions

Une ligne du dry-run réel a tout arrêté :

    ABC → Abell Coin USD

`ABC` est AmerisourceBergen, une action pharmaceutique américaine (délistée, renommée COR en 2023).
Mon script s'apprêtait à ÉCRIRE DANS LE DÉPÔT le nom d'une cryptomonnaie pour cette ligne. C'est
précisément le mode de défaillance que l'utilisateur redoutait — un nom plausible et faux — et
c'est mon propre code d'alias qui l'a produit.

**Le même mécanisme existait sur le chemin des PRIX**, et il est plus grave. `_load` essaie les
alias dans l'ordre : pour une action sans barres locales (parce que délistée, justement), il
passait à `{ticker}-USD` puis interrogeait `crypto.db`. Une action pouvait donc être valorisée par
la série d'un jeton, silencieusement, dans une analyse de portefeuille. Le repli avait été écrit le
06/09 pour retrouver `ETH-USD` depuis `ETH` ; personne n'avait envisagé qu'il s'appliquerait à un
symbole à trois lettres d'une action morte.

Corrigé : `_aliases(symbole, classe)` n'ajoute `-USD` que si la classe est CRYPTO ou INCONNUE. La
classe circule depuis les seeds jusqu'au chargement (`charger_series` → `_collecter` → `_load`), et
le script de noms la lit dans la colonne `asset_class` du CSV. Classe inconnue (portefeuille tapé à
la main) : le repli reste, car « ETH » en a besoin, mais l'ambiguïté résiduelle est rendue VISIBLE
par l'alias publié dans chaque ligne du tableau — ajouté le matin même, pour une autre raison.

Six tests verrouillent les deux sens : aucune action, ETF, commodité ou devise ne reçoit d'alias
crypto ; une crypto conserve le sien. 2084 tests passés.

## Session 2026-09-07 (suite 17) — Mon propre script confondait trois causes d'échec

Le dry-run sur le VPS a résolu la plupart des noms (Agilent, Alcoa, Apple, AbbVie…) et laissé une
liste d'échecs qui, relue, contenait TROIS familles distinctes que mon script fondait en un seul
« introuvable » — l'erreur exacte que je corrige depuis ce matin, commise dans mon propre outil :

1. **Délistés/renommés** : ATVI, CELG, ABC, CBS, DISCA, ETFC, FRC, COL, FLIR, CBG, HRS, COG… Ceux-là
   doivent sortir de l'univers ; c'est la même famille qu'EVHC et SCG repérés plus tôt.
2. **Vivants mais non mesurés** : BK, CMA, DFS, HES, HOLX, FL, GPS. Grandes capitalisations bien
   cotées — le fournisseur avait simplement limité le débit sous 8 requêtes parallèles.
3. **Format de paire non reconnu** : AAVE/USDC, BTC/USDC, ETH/USDC, HYPE/USDC. yfinance ignore ce
   format mais connaît `AAVE-USD`, et `_aliases` sait déjà faire la traduction.

Publier ces trois familles sous une seule étiquette aurait fait conclure que l'univers est plein de
titres morts, alors qu'une partie n'avait pas été interrogée correctement.

Corrigé : `_essayer` distingue « le fournisseur a répondu qu'il ne connaît pas » (INCONNU) de
« le fournisseur n'a pas répondu » (MUET) ; les MUET sont réessayés avec temporisation croissante,
les INCONNU jamais — insister n'apprend rien. Les alias viennent de `user_analysis._aliases`, la
MÊME fonction qui résout les prix : un instrument valorisé sous un alias doit être nommé sous le
même, sinon la colonne « nom » décrirait un autre instrument que la colonne « prix ». Parallélisme
ramené de 8 à 3 fils, réglable. Le rapport groupe par cause et dit quoi faire de chacune.

5 tests dédiés.

## Session 2026-09-07 (suite 16) — VERDICT : le score de screening ne prédit rien de démontrable

Première mesure sur données réelles (779 symboles réels, horizon 21 j, 83 fenêtres disjointes) :

| grandeur | valeur | lecture |
|---|---|---|
| IC moyen | **+0,0202** | erreur-type 0,0266 |
| t-stat | **+0,76** | p = 0,45 — indiscernable de zéro |
| IC à 95 % | **[−0,032 ; +0,072]** | zéro confortablement dedans |
| 1re → 2e moitié | +0,0322 → +0,0084 | **−74 %** |
| robuste | **NON** | |

Il faudrait un IC de 0,053 — **2,6 fois le mesuré** — pour atteindre t = 2 sur ce nombre de
fenêtres. Même en prenant l'IC pour argent comptant, la loi fondamentale donne un IR de 0,07 à
12 paris indépendants par an, 0,15 à 52. Ce n'est pas un edge : c'est du bruit avec un signe.

**Conséquences appliquées sans discussion.** Le profil « Conviction » reste FERMÉ — le verrou fait
exactement ce pour quoi il a été écrit. L'avertissement de la carte affiche la mesure au lieu d'une
formule. La sélection reste un CLASSEMENT, jamais une prévision, et c'est désormais établi plutôt
que supposé.

**Réserve de méthode.** Un seul horizon a été testé. L'absence de significativité à 21 jours ne
prouve pas l'absence à tout horizon — mais en tester plusieurs impose Benjamini-Hochberg avant de
publier le meilleur, sans quoi on aura simplement choisi le plus flatteur. Le champ
`horizons_testes` existe pour ça.

**Chaque mesure est désormais consignée au registre des hypothèses**, y compris — surtout — quand
elle échoue. Une hypothèse rejetée doit rester citable, sinon elle sera re-testée dans six mois par
quelqu'un qui aura oublié. Et chaque mesure est un ESSAI : elle incrémente le compteur qui déflate
le Sharpe. Ne consigner que les succès ferait mécaniquement grimper la significativité apparente de
ce qui reste — un registre qui ne garde que ce qui marche organise le p-hacking au lieu de s'en
prémunir.

## Session 2026-09-07 (suite 15) — Identifier l'instrument, et l'aveu de 594 noms manquants

Crainte exprimée : confondre deux tickers. **Elle est fondée, et ce n'est pas un cas limite.**
Mesuré : 594 symboles sur ~766 n'ont AUCUN nom dans `data/seed/*.csv`. Ni les fondamentaux ne le
comblent — la dataclass `Financials` n'a pas de champ `name`.

**Correction d'un correctif du matin.** J'avais fait retomber un nom vide sur le ticker « pour que
la colonne ne reste pas blanche ». C'était traiter un symptôme d'affichage au prix de la vérité :
« BK / BK » se lit comme une identification alors que rien n'a été identifié, et le lecteur croit
avoir vérifié. Un nom absent reste désormais absent, affiché « nom non renseigné ». Le test qui
verrouillait l'ancien comportement est retiré, avec sa raison conservée en commentaire.

**Ce qui existait déjà et n'était pas publié** : `venue` et `currency` sont dans les seeds depuis
toujours (BK → NASDAQ/NYSE · USD). S'y ajoute l'ALIAS — le symbole réellement coté, `ETH` valorisé
via `ETH-USD` — qui est le désambiguïsateur le plus utile puisqu'il dit quelle série a servi au
calcul.

**Lien : la fiche du FOURNISSEUR, pas le site relations investisseurs.** Déduire une URL d'IR à
partir d'un nom peut ouvrir la page d'UNE AUTRE société — exactement l'erreur à éviter. Le lien est
indexé par le symbole exactement utilisé : si notre identifiant est faux, la page est fausse de la
même façon, donc visiblement fausse. Un lien qui échoue de façon détectable vaut mieux qu'un lien
plausible et faux.

**`make noms-univers`** comble les noms manquants DEPUIS les fournisseurs, jamais de mémoire. Les
saisir à la main écrirait dans le dépôt des libellés sans source ni date : un nom faux est pire
qu'un nom absent — absent il alerte, faux il rassure. Le script n'écrit que ce qu'un fournisseur a
répondu, ne touche jamais un nom existant, et liste ce qu'il n'a pas résolu.

2074 tests passés ; build Next.js vert.

## Session 2026-09-07 (suite 14) — Les quatre synergies inter-onglets, câblées

Chacune partage la même discipline : le câblage est ACTIF, et son effet est proportionnel à la
preuve disponible. Trois des quatre ne font donc rien aujourd'hui — et le disent.

**1. Résultats imminents → filtre d'ENTRÉE.** `packages/strategies/earnings_blackout` portait
l'intention dans sa docstring (« à utiliser comme filtre d'entrée ») sans que rien ne l'appelle.
Une covariance historique mesure le risque ORDINAIRE, celui qui se diversifie ; une annonce de
résultats est datée, binaire, d'amplitude 20-30 %, et n'a aucune raison de compenser celle d'un
autre titre. Un min-variance ne la voit pas et entrerait trois jours avant. Les candidats
concernés sont écartés AVANT tout calcul de covariance. **Date inconnue ≠ pas de résultats** :
conservée mais publiée à part — l'exclure viderait la sélection, la taire laisserait croire que
le filtre l'a couverte. Appels parallélisés, budget de temps borné, gate `QUANT_EARNINGS` respecté.

**2. Régime macro → EXPOSITION seulement, et seulement vers le BAS.** Incliner les poids entre
titres suppose de savoir QUI profitera du régime : prévision transversale que rien ne valide.
Réduire l'exposition ne suppose que de savoir que le risque global est moins bien payé —
affirmation plus faible, donc plus soutenable. Asymétrie assumée : se tromper en étant prudent
coûte un rendement manqué, se tromper en étant agressif coûte la capacité à rester investi. Un
régime favorable n'autorise donc AUCUNE hausse. L'amplitude suit `force_preuve`, la règle déjà
écrite pour la page profil, bornée par `AMPLITUDE_MAX` = 5 pts. Sans t-stat publié pour le régime,
la force vaut 0 et la modération vaut exactement 1,0.

**3. Chemin de moindre effort.** « Voici la cible » n'est pas actionnable à 100 % de turnover : le
coût est certain et immédiat, le bénéfice diffus. Les mouvements sont ordonnés par variance évitée
PAR POINT DE TURNOVER (glouton assumé, chaque étape publiant la volatilité atteinte, vérifiable).
Mesuré sur un cas construit : le premier mouvement capture 97 % du risque évité pour 25 % du
turnover. La part du gain peut dépasser 100 % en cours de route — sortir du marché est
momentanément moins risqué que la cible, qui n'est pas le point de variance minimale.

**4. Score ML dans les vues de Conviction.** `somers_d(AUC) = 2·AUC − 1` rend comparable un
classifieur binaire et un score continu, et rend surtout visible ce que « edge détecté » masque :
**AUC 0,52 = IC 0,04**. Les deux signaux sont combinés en pondérant chacun par SON IC — un signal
nul disparaît de lui-même, sans branche particulière à maintenir. L'IC combiné est borné par la
somme simple : √(ΣIC²) suppose l'indépendance, deux signaux corrélés font moins.

`scenario_conviction` déménage dans `packages/portfolio/conviction.py` : la limite de 400 lignes,
mais surtout tout ce qui touche à un rendement ATTENDU doit se lire d'un seul tenant, garde-fous
compris, plutôt que dispersé au milieu de calculs qui ne prétendent rien prédire.

21 tests dédiés (9 filtre résultats + 12 synergies) ; 2072 passés ; build Next.js vert.

## Session 2026-09-07 (suite 13) — Le profil déclaré BORNE enfin la recommandation

La page « Mon profil » l'écrivait elle-même : « Elles ne contraignent aujourd'hui aucun autre
écran ». C'est levé pour la recommandation d'univers.

**Où poser la contrainte.** Le profil vit dans le navigateur (`localStorage: quant.profil`), la
covariance vit côté serveur. Le front transmet donc le profil à chaque appel — exactement ce que
fait déjà la page de profil avec `/api/profil` : l'API calcule et ne conserve rien, aucune session,
aucune écriture. La promesse « rien n'est envoyé ni conservé » vise un serveur distant, pas l'API
locale de l'utilisateur ; le modèle Pydantic le redit en commentaire.

**Deux contraintes, dans cet ORDRE, et l'ordre n'est pas arbitraire.** Le plafond de ligne est
RELATIF (aucune position au-dessus de x %) : projection sur le simplex, redistribution à somme
constante — un `min(w, cap)` suivi d'une renormalisation ferait ressortir au-dessus du plafond ce
qu'on venait d'y ramener. L'exposition est ABSOLUE (le portefeuille ne doit pas pouvoir baisser de
plus que le budget déclaré) et se lit sur la volatilité des poids DÉFINITIFS : mesurer la
volatilité d'une allocation qu'on ne détiendra pas donnerait une exposition fausse. Testé.

`maxDD ≈ 2,5 × vol` via `vol_target_from_drawdown` — la conversion du dimensionnement de
production, pas une seconde formule pour le même objet.

**Vérifié sur le profil réel de l'utilisateur** (horizon 10 ans, perte max 25 %, 50 % du
patrimoine) contre six actifs à 2,2 % de vol quotidienne : budget 23 %, volatilité cible 9 %,
exposition ramenée à 72,1 %, **27,9 % en liquidités**, et la volatilité finale atteint exactement
la cible. Les liquidités apparaissent comme une LIGNE du tableau : une somme de poids à 72 % sans
ligne dédiée se lirait comme une erreur d'arrondi plutôt que comme la contrainte demandée.

Monotonie testée : moins de perte acceptée ⇒ moins d'exposition, jamais l'inverse. Des actifs
calmes ne déclenchent aucune réduction — la contrainte ne prélève pas de cash sans objet.

2051 tests passés ; build Next.js vert.

## Session 2026-09-07 (suite 12) — Le piège que l'installation des services a créé

`EADDRINUSE 127.0.0.1:3000` : le service `quant-web` tient le port en permanence, et `make start`
essayait d'y lancer un second serveur. J'ai installé les services sans neutraliser la commande
qu'ils remplacent — deux processus se disputant le même port, à chaque fois. `start.sh` refuse
désormais tôt si `quant-web.service` est actif, nomme `make up` et rappelle comment revenir au
mode manuel. Vérifié avec un faux `systemctl` : refus, code retour 1.

**Erreur grave évitée de justesse dans ce correctif.** J'avais écrit le message d'erreur avec des
accents graves autour de « make start ». Entre guillemets doubles, bash y voit une SUBSTITUTION DE
COMMANDE : la garde aurait relancé `make start` récursivement, depuis le message censé l'interdire.
`bash -n` ne détecte pas ce cas — seule la relecture l'a vu. Guillemets typographiques désormais.

## Session 2026-09-07 (suite 11) — L'IC mesuré, et le seul profil que la mesure peut interdire

Demande : que la recommandation tienne compte de l'IC et sélectionne « les meilleurs set-ups pour
maximiser les gains ». La seconde moitié n'est pas livrable telle quelle — maximiser un gain exige
un rendement attendu, donc un signal dont le pouvoir prédictif est établi. Ce qui EST livrable, et
qui manquait, c'est la mesure de ce pouvoir. Elle décide ensuite du reste.

**`packages/research/screening_ic.py` — IC walk-forward.** Pour une grille d'instants `t`, on
demande au moteur son classement avec la seule information disponible à `t` (vérifié :
`FactorContext._closes` tronque à `bars[: t+1]`, aucun look-ahead), puis on corrèle par Spearman ce
classement au rendement réalisé `t → t+h`. Deux pièges évités explicitement : le **chevauchement**
(pas = horizon par défaut, sinon les IC s'autocorrèlent et le t-stat gonfle sans information
ajoutée) et le **choix a posteriori de l'horizon** (paramètre explicite, `horizons_testes` publié,
Benjamini-Hochberg requis pour en tester plusieurs). Coupe hors échantillon CHRONOLOGIQUE, jamais
aléatoire. 8 tests, dont les deux bornes : score prescient → IC = 1, bruit → IC ≈ 0, t-stat < 3.

**`scripts/mesurer_ic_screening.py` (`make ic-screening`)** réutilise `_seed_universe` et
`_load_prices` de la production — jamais une seconde définition de l'univers — et EXCLUT les prix
synthétiques. Résultat daté écrit dans `out/ic_screening.json` ; la mesure réexécute le moteur à
chaque date de la grille, ce n'est pas une opération de requête HTTP.

**Quatrième profil « Conviction », gouverné par la mesure.** Black-Litterman, prior = ERC, vues
issues des scores. L'amplitude des vues n'est pas un réglage : elle vaut IC × σ × z (Grinold). Un
IC de 0,005 produit donc un postérieur quasi identique au prior — c'est le mécanisme qui empêche
une conviction non mesurée de déplacer un euro (testé : la monotonie de l'écart au prior en
fonction de l'IC). Sans mesure, ou avec une mesure non robuste, le profil **n'existe pas** : pas de
repli silencieux vers HRP sous un nom prometteur, et la carte affiche la raison chiffrée (les deux
demi-périodes). L'avertissement général suit désormais l'état réel de la mesure au lieu d'une
formule figée.

578 tests passés (portefeuille + recherche + API) ; build Next.js vert.

## Session 2026-09-07 (suite 10) — Les paires en USDC amputaient la moitié de la recommandation

Écran réel : « 6/15 lignes retenues · 9 sans historique exploitable (EVHC, SCG, TRX/USDC,
LINK/USDC, INJ/USDC, BNB/USDC, BTC/USDC, SOL/USDC, ETH/USDC) ». Sept des neuf sont des paires
crypto cotées en USDC. Le correctif du 06/09 ne reconnaissait que le suffixe `USDT` : normalisée,
`TRX/USDC` devient `TRX-USDC`, contient un tiret, et la branche qui ajoute `-USD` était donc
sautée. La moitié de la sélection du jour tombait pour un suffixe.

`_base_crypto` reconnaît maintenant la devise de cotation quelle qu'elle soit (FDUSD, USDC, USDT,
BUSD, USD), avec ou sans séparateur, **triée par longueur décroissante** — tester « USD » avant
« USDC » amputerait `TRX-USDC` en `TRX-C`. Une classe d'action comme `BRK-B` n'est pas prise pour
une paire : aucune variante inventée. Trois tests ajoutés.

Restent EVHC et SCG, deux tickers délistés (2018 et 2019) que le screening remonte alors que
`load_bars` ne les trouve pas : le screener lit le `panel` en mémoire du snapshot, la
recommandation lit YAHOO.db/crypto.db. **Deux sources différentes pour le même univers** — à
traiter, noté au TODO. Ce n'est pas corrigé ici et la carte continue de les nommer.

232 tests portefeuille passés.

## Session 2026-09-07 (suite 9) — Services systemd : l'orphelin ne peut plus naître

**Défaut trouvé dans ma propre garde avant de livrer.** Après avoir tué l'orphelin nommé par le
diagnostic, `make start` repartait sur 3001 SANS que la garde signale quoi que ce soit : mon test
réussissait là où Node échoue. Cause : je testais un bind sur `0.0.0.0` (IPv4) alors que
`server.listen(port)` de Node se lie à `::` en double pile. Un détenteur lié à `::` en IPv6-only
laisse l'IPv4 libre — le test passait, Next échouait une seconde plus tard, et la garde restait
muette sur le cas exact qu'elle devait attraper. Le test réplique désormais Node (AF_INET6,
IPV6_V6ONLY=0), avec repli IPv4 là où AF_INET6 n'existe pas. Non reproduit ici : le conteneur de
développement n'a pas d'IPv6 ; c'est un raisonnement vérifié sur le mécanisme, pas une mesure.

**Services livrés.** `quant-api.service` et `quant-web.service`, installés par
`scripts/install_services.sh` (`make services`) qui GÉNÈRE les unités avec le vrai utilisateur et
le vrai chemin plutôt que de les coder en dur, refuse de tourner sous root, et arrête d'abord les
processus lancés à la main. `Restart=always`, démarrage au boot, arrêt propre.

**Trois décisions.** (1) Front en mode PRODUCTION (`build` + `next start`) et non `next dev` : c'est
l'enfant `next-server` du serveur de développement qui survivait à chaque déconnexion. Contrepartie
assumée : `sudo systemctl restart quant-web` après un `make sync`, d'où `TimeoutStartSec=900`.
(2) `QUANT_BIND_HOST=127.0.0.1` pour l'API ET le front : le dépôt est public, la page affiche des
positions réelles, l'API n'a aucune authentification — accès par tunnel SSH, jamais par un port
ouvert. (3) `STATIC_EXPORT`/`NEXT_PUBLIC_STATIC` explicitement neutralisés dans `svc_web.sh` :
systemd charge le `.env` du dépôt, et une de ces variables y traînant produirait un build exporté
que `next start` ne sait pas servir — panne sans rapport visible avec sa cause.

L'environnement (venv + variables QUANT_*) est extrait dans `scripts/env_quant.sh`, sourcé par
`start.sh` et par les deux services : une seule définition, aucune divergence possible.

Vérifié : `next start` sert `/analyse-portefeuille/` en HTTP 200 sur le build serveur.
272 tests passés (portefeuille + API).

## Session 2026-09-07 (suite 8) — Le coupable nommé : un `next-server` orphelin que `make stop` n'a jamais tué

Le diagnostic tardif a livré la ligne décisive :
`LISTEN *:3000 users:(("next-server (v1",pid=423655))`. Un `next-server` tenait le port depuis
des heures. `make stop` annonçait « arrêté » sans l'avoir touché — il ne cherchait les détenteurs
qu'avec `lsof`. Toute la matinée en découle : port pris → Next sur 3001 → origine hors CORS →
requêtes refusées avant émission → « TypeError: Load failed » qui accusait la donnée.

MÉCANISME de l'orphelin : `next dev` tourne au premier plan d'une session SSH. À la déconnexion,
le shell reçoit SIGHUP et `npm` meurt, mais l'enfant `next-server` survit, détaché, port toujours
lié. Chaque cycle connexion/déconnexion en fabriquait un de plus.

Corrigé dans `stop_services.sh` : les détenteurs sont cherchés par `ss` ET `lsof` (union), et un
filet par nom rattrape un `next-server` que ni l'un ni l'autre ne montrerait. Ce filet a d'abord
été écrit en `pkill -f` nu — il a tué mon propre shell de test, dont la ligne de commande
contenait le motif. Il exige désormais que `comm` soit réellement node/next : le motif désigne le
candidat, l'exécutable décide. Vérifié dans les deux sens (orphelin tué, voisin épargné).

## Session 2026-09-07 (suite 7) — « Nombre de lignes » demandé n'est pas obtenu, et il faut le dire là où on regarde

Quatre lignes demandées, trois obtenues ; dix demandées, trois aussi. La réponse était DÉJÀ dans la
charge utile (`selection.kept/asked`, `dropped` avec la date de début, `missing_history`), mais
affichée SOUS le tableau — trop loin pour être lue. Une information qu'on ne trouve pas est une
information qu'on n'a pas : on lisait « 3 lignes » sans savoir pourquoi. Le bilan est remonté
AU-DESSUS du tableau qu'il explique, en ambre tant que le compte n'y est pas, et il nomme la cause :
candidats sans historique dans la base locale, ou écartés parce que leur introduction récente
écraserait la fenêtre commune.

Défaut corrigé au passage : la colonne « Nom » restait blanche (BK, EA, NDX). `_lignes` faisait
`.get("name", s)` — or le screener publie parfois une chaîne VIDE au lieu d'omettre la clé, et le
repli par défaut ne se déclenche pas dans ce cas. `or s` remplace le défaut positionnel. Test ajouté.

Reste à mesurer côté VPS laquelle des deux causes domine : le bilan le dira au prochain affichage.
229 tests portefeuille passés ; build Next.js vert.

## Session 2026-09-07 (suite 6) — Le port est repris APRÈS la vérification, et 3001 cesse d'être fatal

Le test de réservation a livré la mesure décisive : « Port 3000 encore occupé, attente de sa
libération » s'est affiché, puis le script a CONTINUÉ — donc le bind a fini par réussir — et Next,
quelques secondes plus tard, a malgré tout basculé sur 3001. Le détenteur apparaît donc APRÈS la
garde, pendant le démarrage de l'API, la purge du cache ou `npm install`. Vérifier juste après
l'arrêt des process ne pouvait pas le voir. Un second contrôle est posé JUSTE AVANT `next dev`,
avec un diagnostic complet (sockets tous états + processus node/next vivants + rappel du `sudo`).

Deux décisions de fond. **La garde n'interrompt plus** : bloquer le démarrage coûtait plus que ça
ne protégeait. **`localhost:3001` et `127.0.0.1:3001` entrent dans les origines CORS par défaut** :
Next bascule tout seul sur 3001, et l'omettre transformait un simple décalage de port en panne
totale et muette — page affichée, requêtes refusées avant d'être émises, navigateur ne rapportant
qu'une panne réseau anonyme. On reste strictement en localhost : aucune surface réseau ajoutée.

Le commentaire qui annonçait encore « mieux vaut refuser de démarrer » a été corrigé en même temps
que le code : une étiquette qui survit à la décision qu'elle décrit est exactement le défaut
poursuivi toute la journée.

43 tests API passés ; typecheck front sans erreur nouvelle.

## Session 2026-09-07 (suite 5) — « y a-t-il un listener ? » n'est pas « puis-je réserver ce port ? »

Ma garde du port 3000 disait LIBRE, `sudo ss -ltnp 'sport = :3000'` disait LIBRE, et Next refusait
de s'y lier en basculant sur 3001. Trois affirmations incompatibles au même instant : la
vérification ne mesurait donc pas la bonne chose. `ss -l` ne liste que l'état LISTEN — il ne voit
ni les sockets résiduelles d'un processus tué, ni un détenteur qu'il n'a pas le droit d'afficher.
Poser la question à `ss` était structurellement incapable de prédire ce que ferait Next.

La garde tente désormais le bind lui-même, avec SO_REUSEADDR comme Node — exactement l'opération
que Next va tenter — et réessaie 30 s, l'occupation après un `kill -9` étant souvent transitoire.
Si le port reste inaccessible, elle imprime l'état COMPLET des sockets (`ss -tanp`, tous états) au
lieu de la seule vue LISTEN, et rappelle que `sudo` est nécessaire pour voir un autre compte : le
diagnostic est produit automatiquement au lieu d'être redemandé.

Vérifié dans les deux sens : port réellement lié → détecté occupé, code 1 ; port libéré → réservable
immédiatement, code 0. `ss` peut être absent (constaté en conteneur) : repli sur `lsof`.

## Session 2026-09-07 (suite 4) — Next bascule sur 3001, et le CORS le refuse en silence

`make start` affichait « ⚠ Port 3000 is in use, trying 3001 instead » et poursuivait. Or
`apps/api/main.py:39` n'autorise par défaut que `localhost:3000`, `127.0.0.1:3000` et
`localhost:8080` : un front servi sur 3001 voit TOUTES ses requêtes refusées par le CORS avant
qu'elles partent. Symptôme : la page s'affiche, aucune donnée ne se charge, et le navigateur ne
rapporte qu'une panne réseau anonyme — exactement le « TypeError: Load failed » de ce matin.
Le démarrage échoue désormais au lieu de dériver.

**Et la première version de cette garde était fausse.** Elle interrogeait `lsof -ti:3000`. Mesuré
sur le VPS : `lsof -i:3000 -sTCP:LISTEN` ne rend RIEN alors que Next refuse le port — sans
privilèges, `lsof` ne montre que les sockets de l'utilisateur courant, et le détenteur appartenait
à un autre compte. La garde serait passée à côté du cas même qui l'a motivée. Elle utilise `ss`,
qui liste les sockets d'écoute quel qu'en soit le propriétaire, avec repli sur `lsof`.

Le message de transport du front distingue maintenant trois cas au lieu de deux : origine
autorisée (API éteinte → `make start`), origine localhost mais hors liste (CORS → libérer 3000 ou
élargir `QUANT_CORS_ORIGINS`), origine distante (`NEXT_PUBLIC_API_URL`). La liste par défaut est
dupliquée côté front pour ce diagnostic ; le message dit « par défaut » et ne prétend donc rien
sur une configuration surchargée.

## Session 2026-09-07 (suite 3) — Recommandation d'univers : que détenir, pas seulement comment repondérer

Demande : une quatrième proposition où le robot dit QUELS actifs détenir, y compris des actifs
absents du portefeuille, avec un % par profil.

**Correction préalable d'une étiquette fausse.** `optimal_allocation` ressemblait à la réponse toute
faite. Elle ne l'est pas : `snapshot.py:1858` pose `corr_syms = held[:12]` — ce sont les douze
premières lignes DÉJÀ DÉTENUES. L'exposer comme « recommandation » aurait répondu « comment le robot
devrait repondérer ce qu'il a » sous le nom de « que devriez-vous détenir ». Aucun actif nouveau
n'aurait pu en sortir, et rien ne l'aurait signalé.

**Ce qui est livré.** `packages/portfolio/recommendation.py` : la sélection vient du screening du
jour (`/api/screen` — filtres durs YAML puis score composite z-score sur l'univers investable), les
poids des trois profils viennent des mêmes moteurs de risque que l'étape 4. Endpoint
`POST /api/portfolio/recommend` (read-only, garde localhost, comme `/analyze`). Côté front, un
sélecteur de source dans l'étape 4 : « Mon portefeuille » ou « Recommandation du robot », les trois
profils inchangés.

**Élagage T/N.** Une introduction récente parmi quinze candidats peut réduire la fenêtre commune à
quelques semaines : une covariance de 15 actifs sur 40 jours est du bruit (Marchenko-Pastur — la
bande de bruit s'élargit en (1+√(N/T))², et un min-variance nourri de cette matrice concentre sur les
actifs dont la variance est sous-estimée par accident). `elaguer()` retire l'actif dont l'historique
commence le plus tard — ce qui augmente T et diminue N — jusqu'à T ≥ 30·N, en départageant les débuts
identiques par le score le plus faible. Ce qui est retiré est PUBLIÉ avec sa date de début.

**Trois honnêtetés imposées par le mandat données-réelles.** (1) Les lignes détenues absentes de la
sélection apparaissent à 0 % : les omettre sous-estimerait le turnover et cacherait ce qu'il faut
vendre. (2) `caveat` est publié avec chaque résultat : les poids répartissent un risque mesuré, la
SÉLECTION repose sur un score dont le pouvoir prédictif n'est pas validé hors échantillon. (3) Aucun
rendement attendu n'entre nulle part : « idéal » veut dire « bien réparti », jamais « le plus
rentable » — la méthodologie le dit en toutes lettres.

12 tests dédiés ; 2028 passés sur la suite complète ; build Next.js vert.

## Session 2026-09-07 (suite 2) — `make stop` se tuait lui-même, et tuait les tunnels SSH

Deux défauts d'outillage, mesurés et reproduits, pas déduits.

**`make stop` se terminait sur « [Makefile:43: stop] Terminated ».** Cause : make exécute la
recette via `/bin/sh -c '…'`, dont la ligne de commande CONTIENT le motif `uvicorn apps.api.main`.
`pkill -f` tuait donc ce shell — et les deux nettoyages de ports qui suivaient sur la même ligne
n'étaient JAMAIS exécutés. Un arrêt qui échoue bruyamment tout en s'arrêtant à mi-course.
Reproduit sur un Makefile minimal : la ligne suivante n'est jamais atteinte. Corrigé par les
crochets (`uvicorn apps[.]api[.]main`), qui cassent l'auto-correspondance sans changer la cible ;
vérifié : `make stop` rend « arrêté » et le code retour 0.

**`kill -9 $(lsof -ti:PORT)` tuait les tunnels SSH.** L'utilisateur avait ouvert
`ssh -L 3000:… -L 8000:…` depuis le VPS lui-même ; `start.sh` a tué le processus qui tenait les
ports — c'est-à-dire le tunnel — et avec lui la session qui exécutait `make start`. Un tunnel n'est
pas un service à redémarrer. Le nettoyage inspecte désormais `ps -o comm=` et refuse de tuer un
`ssh`/`sshd` : il le nomme et dit quoi faire. Vérifié avec un processus réellement nommé `ssh`
tenant le port 3000 : survivant, message affiché.

Les deux chemins d'arrêt (`make stop` et `scripts/start.sh`) dupliquaient ces trois lignes. Ils
appellent maintenant `scripts/stop_services.sh` : une seule définition de ce qu'on tue.

## Session 2026-09-07 (suite) — « TypeError: Load failed » n'est pas une donnée manquante

Après le correctif des alias crypto, l'étape 4 restait vide, mais sous un motif NOUVEAU :
« Analyse historique indisponible : TypeError: Load failed. Couverture 0% ». Ce n'est pas une
mesure — c'est la chaîne que Safari rend pour TOUTE panne de transport (Chrome dit « Failed to
fetch »). Le corps de la requête n'était jamais parti : aucune base n'avait été ouverte, aucun
historique lu. Le front relayait cette chaîne sous une étiquette qui accuse la donnée. Les quatre
colonnes de preuves à 0/4 dans le même écran confirmaient la panne de transport, pas la donnée.

Trois causes possibles, et le message ne permettait de trancher aucune : API éteinte, mauvais port,
ou origine refusée par le CORS (page ouverte depuis une IP LAN — « localhost » y désigne l'appareil
qui affiche, pas celui qui héberge l'API). `analyzePortfolio` distingue désormais l'échec de
transport (try/catch autour du `fetch`) de la réponse HTTP en erreur, et nomme l'URL visée, la
commande de vérification (`curl <BASE>/health` — la route est `/health`, pas `/api/health`) et,
si l'origine n'est pas localhost, la variable à régler (`NEXT_PUBLIC_API_URL` + `QUANT_CORS_ORIGINS`).

L'étape 4 relaie maintenant le motif amont au lieu d'en réinventer un générique : « Aucune
allocation calculée : l'analyse de l'univers n'a rien renvoyé » paraphrasait une cause déjà connue
en la rendant inutilisable.

## Session 2026-09-07 — Step 4 : trois causes distinctes, aucune n'était « la donnée »

L'étape 4 affichait « — » sur les trois cartes avec le motif « Historique/covariance indisponible
pour cet univers exact ». Ce motif accusait la donnée. **Mesuré : la donnée était là.** Trois causes
indépendantes, chacune suffisante à elle seule.

**A — le ticker crypto nu ne trouvait jamais sa base.** `_aliases("ETH")` ne produisait que `ETH` ;
seuls les symboles finissant par `USDT` recevaient une variante `-USD`. Or `data/crypto.db` stocke le
format yfinance `{base}-USD`, et `load_bars` ne consulte QUE `YAHOO.db`/`market.db` : la base crypto
est hors de son chemin de recherche. Un univers AAPL/NVDA/AMD/ETH partait donc en
`missing=["ETH"]` → `available: False` → tout vide. Corrigé : `-USD` est tenté pour tout symbole
court sans suffixe connu (coût nul sur une action, l'alias nu répond en premier), et `_bars_crypto()`
lit `crypto.db` en réutilisant la convention de `apps/api/main.py::_company_closes`.

**B — les deux côtés ne parlaient pas la même clé.** Le front posait `hrp`, `buildScenario` lisait
`black_litterman` : le scénario dynamique ne pouvait JAMAIS être trouvé. Le back publie désormais
`prudent`/`neutre`/`dynamique`, lus tels quels. Et il s'appelle HRP, pas Black-Litterman — BL exige
des μ que rien ici ne calibre ; le verrou ML sur « dynamique » est retiré, le HRP n'a besoin
d'aucun rendement attendu.

**C — `analyze()` contenait du code mort.** Preuve par AST : un `return` de niveau 1 ligne 126 suivi
de 8 instructions inatteignables (lignes 134–184) et deux docstrings — séquelle de la fusion de
`fix/portfolio-analysis-build`. Réécrit en `_collecter()` + `_scenarios()` + `analyze()` de 33 lignes.

**Au passage :** `_align` annonçait « aucun remplissage » tout en faisant un forward-fill. Sur un
mixte actions + crypto, remplir l'action le week-end lui invente deux rendements NULS par semaine :
sa volatilité mesurée baisse d'environ 15 %, et l'optimiseur min-variance sur-pondère mécaniquement
les actions. L'intersection est rétablie, et la constante partagée `ALIGNEMENT` interdit que le
calcul et son étiquette divergent à nouveau. Le message unique d'indisponibilité est éclaté en trois
messages qui nomment la cause réelle.

Vérifié bout en bout sur AAPL/NVDA/AMD/ETH : `available: True`, alias `{'ETH': 'ETH-USD'}`, trois
scénarios sommant à 1,0000. 5 tests de non-régression ajoutés ; 2016 passés sur la suite complète.


## Session 2026-09-06 — Step 4 : le veto rendait tous les scénarios invisibles

Avec six actifs et un plafond de 20 %, min-var/ERC dépassaient souvent le plafond brut ; le front
refusait alors tout le scénario au lieu de résoudre l'optimisation contrainte. Le plafond est
maintenant projeté sur le simplex : les poids excédentaires sont plafonnés et le reliquat redistribué
proportionnellement, seulement si `N × plafond ≥ 100 %`. Sinon l'infaisabilité est expliquée. Le
compteur de plafonds activés et leur effet moyen sont visibles. La progression passe réellement à
l'étape 4, le bouton y fait défiler la page et un état de calcul remplace le faux avertissement
transitoire. Le dynamique demeure indisponible sans rendement attendu ML calibré OOS : pas de faux μ.

## Session 2026-09-05 (suite 5) — Build Mac : doublon de composant après fusion

Le fichier vu sur le Mac contenait deux déclarations `PortfolioAnalysisWorkspace` et avait perdu
l'accolade fermante de la première, état qui n'existait pas dans le commit source et indique une
fusion locale incomplète. Le composant est réécrit intégralement, avec une seule exportation, des
imports de types explicites et l'annulation logique des réponses asynchrones périmées. Le build
Next.js constitue le test de non-régression de syntaxe.

## Session 2026-09-05 (suite 4) — Les données existaient ; la page ne les chargeait jamais

Cause du « 1/6 marché » et des scénarios vides : la page lisait uniquement les lignes ayant survécu
aux filtres de `/api/screen`, puis exigeait que l'univers importé soit identique au portefeuille de
production précalculé. Elle ne demandait jamais les historiques de PLTR/CLSK/BMNR/SBET/ETHUSDT.
Correction : jointure avec le screener complet, normalisation des alias crypto, puis endpoint local
read-only qui charge d'abord les séries déjà présentes dans le snapshot, ensuite YAHOO.db/yfinance,
aligne l'intersection des dates sans forward-fill et recalcule risque + min-var/ERC/HRP. Cash est une
série constante explicite. Un historique manquant publie maintenant son symbole et la couverture.

## Session 2026-09-05 (suite 3) — Des scénarios honnêtes, ou aucun scénario

L'étape Améliorer affiche maintenant prudent (min-variance), neutre (ERC) et dynamique
(Black-Litterman), mais seulement si les poids existants ont été calculés sur exactement le même
univers que le snapshot importé. Le dynamique est en plus refusé sans gate ML positif. L'utilisateur
peut poser valeur, coûts en bps et poids maximal ; la page publie turnover, coût indicatif et nombre
de violations. Une violation bloque le scénario au lieu de clipper silencieusement. Les coûts restent
linéaires : spread dynamique, fiscalité et impact racine carrée sont explicitement non modélisés.

## Session 2026-09-05 (suite 2) — Le snapshot importé rejoint réellement les autres vues

Le portefeuille confirmé est maintenant croisé, dans le navigateur, avec les payloads existants
de screening, fondamentaux, ML, résultats et macro. La page publie la couverture par source, HHI,
nombre effectif de positions et plus grande ligne. Un score ML n'apparaît que si son gate d'edge
est positif. Les allocations existantes ne sont déclarées réutilisables que si leur univers est
exactement celui du snapshot ; sinon la page refuse de recycler les poids d'un autre portefeuille.
Restent le recalcul serveur sur historiques/FX réels, les coûts et les contraintes utilisateur.

## Session 2026-09-05 (suite) — Les synergies sont une cible, pas encore une fonctionnalité

Clarification après revue : l'import MVP ne tire pas encore les scores ML, la macro, les résultats,
les fondamentaux ou les historiques utilisés par les autres vues. Un panneau de statut le dit
maintenant dans l'interface et le contrat d'intégration décrit la jointure par identifiant, le bundle
de preuves daté, le fallback classique et la frontière stricte avec l'exécution. Les profils prudent,
neutre et dynamique seront des objectifs sous contraintes ; aucun label ne rendra artificiellement
prudent un univers risqué, et aucun score de classification ne deviendra directement un rendement.

## Session 2026-09-05 — Analyse de portefeuille, incrément 1 : une entrée contrôlée avant les maths

Ajout d'un parcours distinct « Analyser mon portefeuille » dans le front Next.js. Il accepte une
saisie pondérée ou un CSV, classe seulement quelques instruments explicitement connus, et laisse
les autres « à vérifier » au lieu de deviner à partir du ticker. Les crypto-actifs restent à
confirmer tant que paire et plateforme ne sont pas établies.

La confirmation bloque tant que poids, résolution et total ne sont pas cohérents. Normalisation
et exclusion sont explicites, les valeurs originales sont conservées, les doublons sont signalés
sans fusion automatique. Le snapshot versionné reste dans le navigateur : aucune donnée importée
n'atteint l'API, le LLM ou l'exécution. Le diagnostic affiche volontairement « indisponible » tant
que les historiques ajustés et les conversions FX réelles ne sont pas raccordés. C'est le premier
des quatre incréments demandés ; aucune allocation ou mesure de marché n'a été inventée.

## Session 2026-09-05 (clôture réelle) — L'IC mesuré, la pièce qui manquait à `breadth.py`

**Contexte inhabituel** : l'utilisateur a soumis un prompt généré par Gemini pour
« passer en Swing D/W », truffé de détails qui ne décrivaient PAS ce dépôt — un
cycle 1H qui n'existe pas (la prod tourne en DAILY, cron 14:40 UTC), des scores
(`Fed_Shock_Score`, `Whale_Consensus_Index`) et un levier x3 BitMart introuvables
dans le code ou le vault (Bitmart est SPOT, `live_roundtrip.py` le dit explicitement).
**Refusé d'auditer un fantasme** : signalé les écarts factuels avant tout code,
plutôt que d'exécuter un prompt éloquent construit sur un système qui n'existe pas.

**Confronté aux faits, Gemini a corrigé son propre prompt** — daily 14:40 UTC, spot
sans levier, `detention_min=0` validé par le balayage de ce soir (suite 13). Version
corrigée, Option B choisie par l'utilisateur : construire les fonctions pures
Grinold-Kahn (IC/TC/IR) pour évaluer la qualité d'un signal Swing.

**Découverte en creusant : `packages/research/breadth.py` (166 lignes, 8 tests déjà
verts) implémentait DÉJÀ la quasi-totalité de la demande** — souffle EFFECTIF
(corrige le piège du sur-comptage BR=N×T que le prompt Gemini ne mentionnait même
pas), `transfer_coefficient`, `expected_ir`, `ir_report` avec gate `UNCALIBRATED`,
et même `optimal_horizon` (durée de détention qui maximise l'IC à partir de la
demi-vie d'un signal — directement pertinent pour la question `detention_min` de
ce soir). Seule pièce manquante, vérifiée par recherche (`grep spearmanr` :
aucun résultat dans tout le dépôt) : rien ne MESURE l'IC depuis des prédictions
brutes — `breadth.py` le prend en entrée, déjà connu.

**Livré : `packages/research/information_coefficient.py`** (83 lignes).
`information_coefficient()` — Spearman, NaN-safe, `None` (pas 0.0) sous le seuil de
20 paires ou variance dégénérée — la distinction compte : un IC mesuré à 0,0 est
une information (« ce signal ne prédit rien »), `None` dit qu'on n'a rien pu mesurer.
`ic_in_sample_hors_echantillon()` + `ICInEchantillon.robuste` (ratio OOS/IS ≥ 0,5,
même seuil que ADR-0066, jamais robuste par défaut). 10 tests : corrélation
parfaite/inverse/nulle, seuil N, variance nulle, filtrage NaN, tailles différentes,
IS/OOS robuste et non-robuste. Vérifié en bout en bout avec `ir_report` existant —
aucune couture, zéro duplication.

**Portée délibérément limitée** : module d'ANALYSE pur, ne touche ni
`order_gate.py` ni l'exécution — exactement ce que la version corrigée du prompt
demandait, et ce que ce dépôt exige (séparation IA/capital).

## Session 2026-09-05 (clôture) — Bilan honnête : ce qui est fini, ce qui ne l'est pas

**Demande : « finalise TOUTES les corrections maintenant ».** Triage du TODO plutôt
qu'une clôture optimiste — quatre points ouverts, statuts réels :

1. **P0 lots orphelins sens inverse (8 symboles) — PAS un nouveau bug, une conséquence
   mécanique du nettoyage de ce soir.** `completer_ouvertures` avait tourné AVANT le
   retrait des 20 doublons ; en supprimant les fermetures en double,
   `achats_non_journalises` a augmenté (AVAX 274→605, LINK 66→228, LTC 1,5→61,6) —
   le trou n'est pas pire, il est enfin visible dans sa vraie taille. Le correctif
   existe déjà et a déjà servi cette session ; il suffit de le REJOUER dans l'ordre :
   `completer_ouvertures` → `reconcilier_journal` → `diag-journal`. Rien à construire.

2. **P2 OSCR isolé — RÉPONDU par les données déjà produites.** Le `diag-surfermeture`
   relancé après le retrait des doublons montre `invente = 0` sur les 27 AUTRES
   symboles. Pas besoin d'un nouvel outil : la mesure était déjà là, il fallait juste
   la relire avec la bonne question. Reste ouvert seulement la CAUSE de ce lot précis
   — creuser demande l'historique complet des ordres OSCR, hors de portée ici.

3. **P1 détention 0,1 jour — GENUINEMENT bloqué, pas esquivé.** Nécessite des
   snapshots RÉELS de production (`fast_swing`/`preset` en conditions réelles), que
   ce conteneur n'a jamais eus (aucune clé, aucun `data/market.db` réel ici). Rien à
   « finaliser » sans les données — le dire clairement vaut mieux qu'un faux vert.

4. **P1 trois dates d'arrêté — GENUINEMENT bloqué, même raison.** Le site n'est
   construit qu'avec des données réelles (`make site`), absentes de ce conteneur.

**Ce qui distingue les deux premiers des deux derniers** : (1) et (2) se résolvent par
la RELECTURE de ce qui existe déjà — outils construits, données déjà mesurées ce soir.
(3) et (4) demandent une MESURE NOUVELLE que seul l'environnement réel (Mac mini/VPS)
peut produire. Prétendre les finaliser sans données serait exactement le type de
déduction que ce dépôt interdit.

## Session 2026-09-05 (suite) — Appliqué sur le compte réel : 20 doublons, pas 6

**`make annuler-doublons ARGS=--appliquer` exécuté sur le VPS**, sur le vrai journal
(313 lignes). Résultat mesuré, pas supposé : **20 doublons retirés** (SOL ×3, LINK ×2,
BTC ×2, ETH ×2, LTC ×3, AVAX ×3, BCH ×3, STT, SLG) — bien au-delà des 8 vérifiés à la
main (AVAX+LINK+LTC). La règle générique (même symbole, même date+prix de sortie, un
nommé + un sans nom) a correctement généralisé sans sur-détection : 313 → 293 lignes,
+3 448,65 $ de « réalisé » en double retiré, sauvegarde + archive JSON créées.

**`diag-surfermeture` après coup : `INVENTÉ` +258,3302 → +85,2740.** Baisse de
173,06 unités — exactement la quantité des doublons retirés. Le résidu de 85,27 est
ENTIÈREMENT OSCR, et c'est attendu : OSCR n'est pas un doublon date+prix, c'est un lot
sans AUCUNE contrepartie réelle (ouvert/fermé le même jour, aucun ordre du courtier ne
l'explique) — mécanisme différent, hors du périmètre de cet outil.

**Effet de bord compris, pas un problème** : `achats_non_journalises` a augmenté sur
les symboles touchés (AVAX 274,41 → 605,34) — mécanique, puisque `ferme_journal` a
baissé et que l'identité `achats_nj = achete − (ferme+ouvert)` remonte en
conséquence. Une réalité déjà là (achats jamais journalisés), simplement démasquée.
Identité vérifiée (✓) sur chaque ligne après coup.

**Reste ouvert** : le mécanisme OSCR (lot orphelin sans ordre réel du tout, pas un
doublon) — à chercher s'il existe ailleurs avant de construire un second outil.

## Session 2026-09-05 (suite) — Outil de retrait des doublons, sur les 6 cas vérifiés

**Le même mécanisme, reproduit à l'identique sur AVAX et LTC.** Croisement ordre par
ordre (comme pour LINK) avec l'historique complet des ventes du courtier : AVAX
(3 doublons, 08-27/08-28/08-31) reconstruit à **+60,8196** contre +60,8195 imprimé ;
LTC (3 doublons, mêmes dates) à **+36,0020**, exact. Six doublons au total, tous avec
la même signature : un lot `-Xn` (motif `reconciliation paper (reduce/close)`, écrit
par l'ancien `close_sells` avant le correctif du jour) tombe sur la MÊME date et le
MÊME prix qu'une correction nommée (`reconciliation-journal:<uuid>`) postée plus tard
par `reconcilier_journal --appliquer`. Un résidu distinct, plus gros que les doublons :
l'ordre AVAX du 07-08 (306,46 unités) n'a que 41,91 unités captées — 264,55 unités de
vente réelle jamais journalisée, doublon ou pas.

**Outil construit** : `packages/research/doublons_correction.py::identifier()`. Règle
de détection dérivée directement de la vérification manuelle (pas devinée) : même
symbole canonique, même date de sortie, même prix de sortie — un enregistrement qui
cite un ordre réel, un qui n'en cite aucun. Deux négatifs encodés en tests, tous deux
des pièges déjà rencontrés cette semaine :
- deux enregistrements citant le MÊME uuid (LINK/LTC 07-08, AVAX 09-03) → fermeture
  multi-lots légitime, PAS un doublon (le piège du faux P0 LINK du 04/09, revisité) ;
- un lot sans nom SANS homologue nommé à la même date (les -X4/-X5 partout) → une
  vente réelle non journalisée, un trou différent, PAS une invention.

`scripts/annuler_doublons_correction.py` : même squelette que
`annuler_chronologie_impossible.py` (SIMULATION par défaut, sauvegarde + archive JSON
avant tout retrait, `--appliquer` explicite). Il ne retire QUE le lot sans nom — la
correction nommée, vérifiée contre l'ordre réel, reste intacte.

**10 tests, dont les 6 cas RÉELS en dur** (AVAX ×3, LINK ×2, LTC ×3, avec les vrais
identifiants et prix des relevés du 05/09) — une régression future ne peut pas passer
inaperçue sur ces montants précis. Vérifié aussi via `SqliteTradeJournal` réelle, pas
seulement en mémoire.

**Pas encore appliqué.** L'outil est en simulation ; `--appliquer` reste au choix de
l'utilisateur, sur sa vraie base (ni le Mac mini ni le VPS n'est accessible depuis ce
conteneur). Commande : `make annuler-doublons` puis `make annuler-doublons
ARGS=--appliquer`.

## Session 2026-09-05 (suite) — P0 : le bug d'invention est dans la PRODUCTION, pas l'historique

**Le journal réparé (313 lignes, sync Mac→VPS OK) montre une vraie invention.** Premier
run de `diag-surfermeture` sur des données authentiques : `SUR-FERMETURE totale :
+258,3302` unité(s), concentrées sur AVAX (+60,82), LINK (+74,05), OSCR (+85,27), LTC
(+36,00). Le bloc « ORDRE PAR ORDRE » montre 0 excès sur 195 ventes NOMMÉES
(`reconciliation-journal:<uuid>`) — l'invention n'est donc PAS dans ce qui se vérifie
individuellement contre un ordre réel.

**Dump brut d'OSCR (5 lignes) : la coupable identifiée par élimination arithmétique.**
4 des 5 lignes citent un UUID vérifié. La 5ᵉ, `P-20260831-Alpaca-OSCR` (99,177122
unités, ouverte ET fermée le même jour, motif `reconciliation paper (reduce/close)`),
n'en cite aucun. Calcul : vendu réel total (broker) 178,7987 − consommé par les 4
closures nommées (164,8956) = 13,9031 de vente réelle NON attribuée restante. Sur les
99,177122 unités de la 5ᵉ ligne, au PLUS 13,90 peuvent être réelles ; au MOINS **85,27
sont pure invention — exactement le total imprimé.** Coïncidence exclue.

**Root cause trouvée dans le code de PRODUCTION, pas un script de réparation.**
`scripts/run_live.py:282` (avant correctif) : `sold.append({..., "notional":
abs(delta)})` — le DELTA PLANIFIÉ par le rebalancement (`cible − détenu`), jamais le
fill réel. `close_sells` (`live_roundtrip.py`) calculait `remaining = notional / prix`
pour décider la quantité à fermer au journal. Si le fill réel est plus petit que ce qui
était visé (slippage, remplissage partiel, ordre encore `EN_COURS` — `compte_comme_envoye`
accepte cet état), le journal ferme quand même le montant PLANIFIÉ. **Ce code tourne
chaque jour ouvré ; sans correctif, il aurait continué à inventer du « réalisé »
lundi et tous les jours suivants.**

**Correctif : le fill réel, quand il est citable, prime STRICTEMENT.** Nouvelle fonction
`_fill_vente_jour` (`run_live.py`) isole la lecture du fill du jour (prix ET quantité,
pas seulement le prix comme le faisait `_exit_price`). `close_sells` accepte un champ
`qty_reelle` optionnel : fourni et positif, il remplace `notional/prix` ; absent, le
comportement d'avant est inchangé (aucune régression sur les ventes sans ordre citable,
ex. `close_position`). 6 tests ajoutés (3 sur `close_sells`, 3 sur `_fill_vente_jour` /
`_exit_price`), rejouant le cas OSCR (planifié 99, fait 14 → ferme 14, pas 99).

**Ce que ce correctif ne résout PAS** : les ~258 unités déjà inventées dans le journal
historique restent à corriger — ce n'est pas le rôle de ce patch, qui empêche seulement
la récidive. Et `AVAX/LINK/LTC` méritent le même dump brut qu'OSCR pour confirmer que
la même cause (lots `P-...` sans UUID) explique chacun avant toute correction.

## Session 2026-09-05 (suite) — La preuve : le journal.db du VPS date d'AVANT toute réparation

**Lancé `make diag-surfermeture` sur le VPS.** 95 enregistrements (contre 313 sur le Mac
mini). J'ai d'abord accusé mon propre outil : `diag_journal_compte.py --symbole PATH`
répondait « 0 ligne » alors que mon tableau montrait PATH à −300,2230. J'ai dit à
l'utilisateur de ne pas faire confiance au script — **à tort**.

**Vérifié à la main sur le relevé brut** (`SELECT id, instrument, qty, exit_ts FROM
trades`) : zéro ligne au journal pour PATH, c'est justement ce qui PRODUIT l'écart par
construction (`ferme_journal=0, ouvert=0` → `achats_non_journalises=+achete` et
`sur_fermeture=−vendu`). Recalculé à la main pour PATH et NWL, résultat identique au
tableau du script au dix-millième. **Aucun bug. Je me suis trompé en doutant de l'outil.**

**Le vrai défaut n'était pas dans le calcul, mais dans l'étiquette.** J'avais défini
`sur_fermeture > 0` = « invention ». Un signe négatif ne veut PAS dire l'inverse — il
signale un TROU DE SORTIES symétrique du trou d'entrées (une vente réelle qu'aucune
clôture ne référence), pas une absence de problème. Ma propre bannière « SUR-FERMETURE
totale : +0,0000 $ » était juste selon ma définition mais lisait comme rassurante alors
que PATH (aucune ligne du tout), NWL (1 ligne sur 1554,63 — 8 % capturé), SJM, R, T,
TRV, TYL, THC, VLO, TMO, TER, TSM, ASML, AAVE, ZION montraient tous ce trou massif.
Corrigé : `invente` et `vente_non_journalisee` sont deux propriétés séparées
(`max(0, ±sur_fermeture)`), jamais mélangées dans une colonne signée. 2 tests ajoutés
rejouant PATH/NWL avec les vraies valeurs (9 tests au total).

**La cause racine, confirmée par le relevé** : les 95 lignes du VPS commencent TOUTES
par `P-` — aucune ne porte le préfixe `C-` des écritures de correction. Ce `journal.db`
est la version D'AVANT `reconcilier_journal --appliquer` (Mac mini, aujourd'hui). Les
deux machines n'ont jamais partagé le même fichier — le P1 « trois copies divergentes »
signalé plusieurs fois cette session vient de produire un diagnostic concret, pas
seulement un risque théorique.

**Action recommandée, avant lundi 14:40 UTC** : `make journal-push` (Mac mini, source de
vérité) puis `make journal-pull` (VPS). Sûr maintenant : le timer VPS n'a rien écrit
depuis le 04/09 19:23, donc rien à perdre côté VPS.

## Session 2026-09-05 (suite) — L'écart courtier/journal est DÉCOMPOSÉ, plus seulement constaté

**Le problème.** `diag-journal` constate que le courtier détient ce que le journal ignore
(AVAX 335,50 contre 3,65 · LINK 219,80 contre 82,41 · OSCR 85,27 contre 0), sans dire de
quoi cet écart est fait. Deux causes possibles, remèdes opposés — et rien pour les séparer.

**L'identité qui les sépare, et qui se vérifie :**

    manque_ouvert = achats_non_journalises + sur_fermeture

    manque_ouvert          = (acheté − vendu) − ouvert(journal)
    achats_non_journalises = acheté − total(journal)      entrées jamais écrites — un TROU
    sur_fermeture          = fermé(journal) − vendu       sorties INVENTÉES

La démonstration tient en une ligne : (acheté − fermé − ouvert) + (fermé − vendu) =
acheté − vendu − ouvert. Les deux termes s'additionnent EXACTEMENT au manque. Le module
publie `identite_verifiee()` et le rapport l'imprime par ligne : **si l'identité ne se
referme pas, c'est le module qui a tort, pas la donnée.** Une mesure réfutable, pas une
opinion sur l'origine de l'écart.

**Sur les chiffres RÉELS d'AVAX du 05/09, la décomposition tombe juste** (test dédié) :
manque 331,847254 = achats non journalisés 274,407653 + **sur-fermeture 57,439601**. Donc
les deux causes coexistent, et ~57 unités d'AVAX ont été soldées au journal sans que le
courtier les ait vendues. C'est du « réalisé » sans contrepartie réelle — la cause qui
CONTAMINE les statistiques, par opposition au trou d'entrées qui les rend seulement
incomplètes.

**Imputation ordre par ordre.** Les sorties écrites `reconciliation-journal:<uuid>`
nomment le fill réel : on compare exactement. Celles écrites `reconciliation paper
(reduce/close)` ne nomment rien et ne sont imputées à AUCUN ordre — les imputer d'office
fabriquerait l'excédent qu'on cherche. Les deux blocs sont publiés séparément.

**Le piège LINK est encodé en test, pas seulement en commentaire.** Un ordre ferme
légitimement plusieurs lots (pool FIFO commun aux chaînes `P-` et `C-`). Un excédent
n'existe que si la SOMME dépasse la quantité réellement vendue. Le test rejoue les vrais
chiffres — 125,613741 + 147,511643 = 273,125384 pour un fill de 273,12538382 — et exige
« aucun excès ». La fausse alerte du 04/09 ne peut plus être reposée par inadvertance.

**Livré** : `packages/research/sur_fermeture.py` (161 l.), `scripts/diag_sur_fermeture.py`,
`make diag-surfermeture` (LECTURE SEULE, `ARGS=--symbole AVAX` pour un titre), 7 tests.
Courtier illisible → message `UNCALIBRATED` explicite, jamais une trace d'appel.

**Prochaine étape, côté utilisateur** : lancer `make diag-surfermeture` là où vit le vrai
journal. La décomposition dira si le mal dominant est le trou d'entrées ou l'invention de
sorties — et c'est elle qui décidera du correctif, pas une hypothèse.

## Session 2026-09-05 — `make live` ne montrait pas le compte : aperçu ≠ simulation

**Ce que l'aperçu affichait, et pourquoi c'était trompeur.** Sur le VPS, `make live`
sortait `détenu 0 $` sur CHAQUE ligne d'un compte qui porte ~99 700 $ de positions, et
un capital de 10 000 $. Deux causes, toutes deux volontaires dans le code :
`run_live.py` forçait `cur_alp, cur_bit = ({}, {})` en dry-run, et le Makefile passait
`--equity 10000` en dur. Conséquence : chaque cible sortait au DIXIÈME de sa taille
réelle, et l'aperçu annonçait l'achat du portefeuille entier PAR-DESSUS l'existant.

**C'est exactement le mode de défaillance que `live_guards` interdit au run LIVE** —
son principe 1 dit « inconnu ≠ zéro », né du jour où un `détenu=0 prudent` a fait
racheter tout le portefeuille. Le run réel en est protégé ; l'aperçu, lui, le mettait
à l'écran, et un aperçu qui n'annonce pas le run suivant ne sert à rien.

**Le piège de lecture que ça a failli produire.** Sept lignes crypto sortaient
« cible 188-262 $ sous le plancher de ligne (1000) — on n'ouvre pas ». J'ai d'abord lu
là une confirmation du plancher comme cause de la détention médiane de 0,1 jour. C'est
FAUX et c'est un artefact de `--equity 10000` : à l'équity réelle, ces mêmes cibles
valent ~2 000-2 600 $ et passent le plancher sans le toucher. L'hypothèse du plancher
reste donc OUVERTE et non mesurée — elle ne peut pas l'être avec un aperçu au 1/10ᵉ.

**Premier correctif INCOMPLET — et son symptôme était pire que le mal.** Rendre
`vet_brokers` capable de lire l'equity réelle en dry-run ne servait à rien : `_make_brokers`
renvoie `(None, None)` en dry-run, donc AUCUN broker n'existait pour être lu. L'aperçu est
passé de « détenu 0 $ » à « cible 0 $ ET détenu 0 $ » sur toutes les lignes — un tableau
entier de zéros, qui se lit comme « le système ne veut rien faire » alors qu'il n'a rien pu
lire. Une valeur par défaut retirée sans vérifier ce qui la remplaçait.

**Correctif complet.** `_make_brokers(dry, apercu=)` construit Alpaca EN LECTURE quand
l'aperçu le demande (place crypto laissée absente : `cron_live.sh` la neutralise, et les
paires crypto d'Alpaca sont déjà dans ses positions). Sûreté vérifiée avant d'y toucher :
`_reconcile` sort sur `if dry or broker is None` AVANT tout envoi (run_live.py:232), donc
construire un broker en dry-run ne peut pas envoyer d'ordre. Et `_apercu` replie désormais
un capital nul sur 10 000 $ SIMULÉS avec un avertissement explicite, y compris quand le
broker est absent : un aperçu qui ne décrit pas le compte doit le DIRE, pas le montrer sous
forme de zéros silencieux.

**Deux modes nommés, au lieu d'un seul qui mentait.**
- `make live` (aperçu) — equity ET positions RÉELLES, aucun ordre envoyé. C'est
  maintenant le seul moyen de voir ce que fera le prochain run réel.
- `make live-sim` (`EQUITY=…`) — portefeuille NEUF au capital imposé, détenu ignoré à
  dessein. L'ancien comportement, sous un nom qui dit ce qu'il fait.

`live_guards.simule(dry, cli_equity)` porte la distinction ; en aperçu, une equity
illisible se replie sur 10 000 $ SIMULÉS avec un avertissement, sans être fatale — un
aperçu n'envoie aucun ordre, le sanctionner comme un run live n'aurait pas de sens.
6 tests ajoutés (13 dans `test_live_guards`, 2 dans `test_run_live_seance`).

**Suite complète VERTE** : 1970 passés, 7 ignorés, 0 échec (8 min 10). Les appels
réseau que le proxy du conteneur refuse sont tous dans des tests qui les tolèrent —
lancée en tâche de fond plutôt qu'avec un délai court, la suite passe entière.
`tests/execution` + `tests/risk` (337) repassés après la mise en forme finale.

## Session 2026-09-04 (suite 13) — Le verrou de détention mesuré : hypothèse NON retenue

**L'hypothèse testée** (utilisateur, d'après son historique réel) : les round-trips tenus
moins de 10 jours perdent, donc imposer un plancher de détention laisserait au trade le
temps de « nettoyer » la volatilité d'entrée avant de viser la cible. Paramètre
`detention_min` ajouté à `fast_swing_backtest` (`9459f00`), balayé 0/5/10/15 séances dans
`sortie_lab`, 783 titres · 2 045 257 barres · dernière séance 04/09.

| réglage | trades | payoff | marge | jours | Sharpe | maxDD | DSR | net $ |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| aucune ◀ prod | 1342 | 2.65 | 3.9 % | 42 | 0.17 | −27.9 % | 7.1 % | 937 |
| min 5 j | 1293 | 2.42 | 8.4 % | 45 | 0.29 | −27.4 % | 16.2 % | 2 113 |
| min 10 j | 1141 | 2.32 | 0.8 % | 48 | 0.18 | −26.6 % | 7.7 % | 177 |
| min 15 j | 1030 | 2.22 | 2.7 % | 51 | 0.20 | −31.0 % | 9.2 % | 597 |

**Décision : `detention_min` reste à 0 en production.** Quatre raisons mesurées, aucune
d'opinion.

1. **Le 10 jours précisément demandé est le PIRE des trois verrous** : 177 $ net contre
   937 $ sans verrou. Si l'effet « <10 j perd » existait, c'est ce réglage qui devrait
   gagner. Il perd le plus.
2. **La suite des Sharpe n'a pas la forme d'un effet** : 0.17 → 0.29 → 0.18 → 0.20. Un
   mécanisme réel produit une courbe (croissante, décroissante, ou avec un optimum) ;
   un zigzag qui repasse deux fois par la même valeur est la signature du bruit.
3. **La seule colonne monotone va dans le sens du COÛT** : payoff 2.65 → 2.42 → 2.32 →
   2.22. Différer la cible et le suiveur fait sortir plus loin du sommet — c'est
   mécanique, et c'est la seule chose que le balayage établisse proprement.
4. **Aucun DSR n'approche 50 %** : après déflation du nombre d'essais (RR + suiveurs +
   détentions), aucun réglage n'est distinguable de zéro. Le meilleur (16.2 %) reste à
   un tiers du seuil.

**Pourquoi la statistique du journal ne contredit pas ce résultat : elle est confondue.**
Les longues détentions du journal réel sont presque toutes des tranches d'un même lot
crypto sur un seul rallye (cf. `turnover_audit`, suite 9). « Tenu longtemps = gagnant »
y décrit un rallye compté plusieurs fois, pas une durée de détention. La durée moyenne du
banc est déjà de 42 jours : il contient très peu de trades courts, donc un plancher de
5 ou 10 séances n'y touche qu'une minorité de positions (durée moyenne 42 → 45 → 48).

**Ce qui reste acquis** : le paramètre et ses 6 tests (`tests/backtest/test_detention_minimale.py`)
restent en place, défaut 0. La question redeviendra mesurable si l'exécution réelle produit
un jour assez de trades courts non confondus. Et ADR-0073 tient toujours : ce banc mesure
`fast_swing_backtest`, pas le moteur `preset risk-parity + DD-target` qui envoie réellement
les ordres — même un gain net ici ne serait pas transposable tel quel.

## Session 2026-09-04 (suite 12) — Le "bug" LINK n'en était pas un, et l'addition le prouve

**Fausse alerte, vérifiée avant correction — pas après.** Le P0 posé en clôture (« deux
chaînes d'identifiants fermées par la même vente ») ne tenait pas à l'addition. Vérifié
sur l'ordre réel `ee481ad2` (LINK, 07/08) via `AlpacaBroker().orders()` filtré : quantité
RÉELLE **273,12538382**. Or `C-LINK-R1` (125,613741) + le lot `P-` correspondant
(147,511643) = **273,125384** — exact au dix-millième. `_plan` regroupe déjà `P-` et `C-`
dans un seul pool FIFO par symbole ; une vente plus grosse que le premier lot en ferme
légitimement plusieurs à la suite. C'est voulu, pas un bug.

**Ce qui a évité de corriger un code qui n'était pas cassé** : l'utilisateur a insisté pour
vérifier plutôt que d'accepter le diagnostic tel quel, et la vérification demandée
(comparer la fermeture proposée à la quantité RÉELLE de l'ordre chez le courtier) était
déjà la bonne méthode — je l'ai juste appliquée après coup au lieu de l'avoir faite avant
d'écrire « P0 » dans le TODO. Le motif qui avait déclenché l'alerte (même date, même prix,
deux lots) ressemblait à un doublon mais ne l'était pas — une seule addition suffisait à le
savoir, et je ne l'avais pas faite.

**TODO corrigé, pas juste refermé** : l'entrée P0 est remplacée par ce qui a été vérifié et
pourquoi, pour qu'une session future ne reparte pas sur la même fausse piste.

## Session 2026-09-04 (suite 11, clôture) — Le journal réparé révèle un bug plus profond que la donnée qu'il corrigeait

**La chaîne de réparation, appliquée pour de vrai sur le compte réel.** `make completer-ouvertures`
puis `make reconcilier-journal`, dans cet ordre (imposé par le code : on ne peut fermer un lot
qui n'a pas d'ouverture). Résultat mesuré, pas supposé : écart de réconciliation −684,55 $ →
**−294,00 $**, lots orphelins 15 → 12, achats sans prix de revient 20 → 11. Progrès réel, la
moitié du trou refermée par les outils déjà construits plus tôt cette semaine.

**Ce qui reste n'a plus la même nature.** Les deux scripts demandaient déjà `limit=5000` à
Alpaca ; 463 ordres, c'est TOUT l'historique que l'API rend, pas une fenêtre tronquée. Les 12
lots orphelins et les 11 achats non couverts n'ont donc aucun ordre correspondant dans
l'historique complet du compte — relancer les mêmes scripts n'aurait rien changé.

**Le dump `--symbole LINK` a montré autre chose : un vrai bug de code, pas un trou de donnée.**
`live_journal.py:127` écrit les ouvertures normales en `P-{date}-{venue}-{symbole}` ;
`completer_ouvertures.py:91` écrit ses lots correcteurs en `C-{symbole}`. Les deux chaînes
existent en parallèle pour LINK, et se sont fait fermer par les MÊMES ventes réelles : la
sortie du 27/08 à 11,842 $ ferme à la fois `P-...-X1` (86,88 unités, entrée 8,03 $) et
`C-LINK-R3` (88,60 unités, entrée 11,53 $) — même date, même prix, deux lots distincts. Idem
le 28/08. Pas un doublon simple (quantités et prix d'entrée différents) : un lot correcteur créé
un jour sans vérifier que le manque qu'il comblait se refermerait de toute façon via la chaîne
normale. Ça touche `reconcilier_journal._plan`, pas une donnée à nettoyer.

**Pourquoi je n'ai pas codé le correctif ce soir.** Toucher la logique d'appariement du journal
qui pilote un compte réel (même en paper) sans y regarder à tête reposée serait exactement
l'erreur qu'on a corrigée chez quelqu'un d'autre toute la journée — deviner au lieu de mesurer.
Consigné dans le TODO en P0, avec le chemin de reproduction exact (`--symbole LINK`).

**Bilan de la journée, vu d'ici** : VPS provisionné et opérationnel (systemd, Python, base de
prix) ; deux bugs d'ingestion réels corrigés (`ingest_crypto.py` timezone, schéma `prices`
migré) ; outil de mesure du turnover construit puis corrigé deux fois sur ses propres pièges de
comptage (tranches, fermetures administratives) avant de donner un chiffre fiable ; découverte
que le banc de sortie ne mesure pas le moteur de production (ADR-0073) ; 6 chronologies
impossibles retirées ; la moitié du trou de réconciliation refermée ; un bug de fond découvert
en cherchant autre chose. Rien de tout ça n'aurait tenu sans mesurer à chaque étape plutôt que
supposer — et la dernière trouvaille du soir en est la preuve : le chiffre qui semblait clore le
sujet (l'écart réduit de moitié) cachait un bug qu'aucune mesure agrégée n'aurait montré, seul
un dump ligne à ligne l'a fait apparaître.

## Session 2026-09-04 (suite 10) — Le banc qu'on règle depuis des semaines ne mesure pas la production

**Trois mesures, trois faux résultats corrigés, une vraie réponse.** L'utilisateur
demandait si le rebalancement quotidien coupe les trades trop tôt. Chaque passage sur le
journal réel a d'abord produit un chiffre flatteur qu'il a fallu casser :

1. **+10,26 % par position, t = 5,50 « significatif »** — faux. `close_sells` scinde un
   lot soldé en tranches portant la même entrée ; huit lots crypto du 07/07 revenaient
   six fois chacun avec leur +25 à +47 %. Comme |t| croît en racine de n, la
   significativité était fabriquée par le découpage des ventes. Agrégation par lot.
2. **+5,14 %, t = 2,61** — encore faux. 31 des 37 positions avaient été fermées par le
   script de réparation du matin même : sorties réelles, mais dates et prix reconstruits
   a posteriori dans les fills courtier. 84 % de l'échantillon ne mesurait aucune
   décision. Rapport scindé en trois blocs.
3. **Décisions du système seules : 6 positions, t = +0,92, non significatif.** Rien à
   conclure sur la rentabilité — et c'est la réponse honnête.

**Mais le constat qui compte n'est pas statistique.** Détention médiane des décisions du
système : **0,1 jour**. Le banc `sortie_lab`, où l'on règle `rr` et le suiveur ATR depuis
des semaines, annonce des détentions de 42 à 48 jours. L'écart n'est pas un désaccord de
mesure : `sortie_lab` rejoue `fast_swing_backtest` (stop 4 ATR, cible R-multiple,
suiveur), tandis que la production applique des poids cibles `preset risk-parity +
DD-target`. **Deux moteurs différents.** La production n'a ni stop ATR, ni cible, ni
suiveur — donc aucune notion de TP ou de SL, et un seul motif de sortie possible. Régler
`rr 6 → rr 9` ne changerait pas un ordre. ADR-0073.

**Ce que les 6 décisions disent quand même.** Capture −22 % sur 5 d'entre elles : passées
en positif (+1,3 à +2,2 % de MFE) puis sorties en perte, après quelques heures. C'est
exactement le mécanisme que l'utilisateur décrivait. Six observations : cohérent avec son
intuition, ne prouve rien.

**Instabilité relevée au passage, désormais secondaire.** `sortie_lab` « sans suiveur »
donne Sharpe 0,50 sur les données au 04/09 et 0,03 au 20/06 — deux mois et demi
d'écart, avec un rallye crypto (BTC +21 %, ETH +33 %, LINK +38 %) dans l'intervalle. Le
banc avertit lui-même que deux runs ne se comparent qu'à empreinte identique. Même
robuste, ce réglage ne toucherait pas la production.

**À diagnostiquer, pas encore expliqué.** Pourquoi 0,1 jour de détention ? Hypothèse à
vérifier : le plancher de ligne (1 000 $) solderait une position ouverte la veille dès
que sa cible repasse dessous. Formulé comme piste, pas comme cause.

## Session 2026-09-04 (suite 9) — VPS OVH mis en service, et un outil de mesure au lieu d'une décision devinée

**VPS opérationnel.** Guidage pas à pas (accès SSH par clé, pare-feu, fail2ban, mises à jour
auto, Python 3.11, dépôt cloné sur la branche de dev, `.env` avec les clés Alpaca PAPER) jusqu'à
un service systemd qui rejoue le rebalancement quotidien (`cron_live.sh`) en redondance de
GitHub Actions — idempotent par construction, donc sans risque de double exécution. Le vrai
apport du VPS n'est pas « faire tourner le bot » (Alpaca tourne déjà dans le cloud depuis
`paper.yml`) mais une base de prix unique synchronisable entre Mac mini et MacBook Air, et le
terrain prêt pour Bitmart/Binance/Blofin en réel — jamais activé sans décision explicite,
puisque Bitmart n'a pas de paper et que le garde-fou du projet l'exige par courtier.

**Une confusion récurrente, bien réelle.** Cinq allers-retours avant que la séquence
scp → ssh → bash passe sans erreur : script lancé sur le Mac au lieu du VPS, fichier obsolète
resservi depuis `~/Downloads`, un `sed` de rattrapage qui aurait rendu un test toujours vrai
(repéré avant de l'envoyer). Le correctif qui a fini par marcher : plus de transfert de fichier,
un seul bloc `cat > fichier <<'EOF' ... EOF` collé directement dans le terminal déjà connecté,
avec `hostname` comme vérification imposée avant tout script sensible.

**Question stratégique de l'utilisateur, honnêtement instrumentée plutôt que devinée.**
« Pourquoi rebalancer chaque jour plutôt que tenir une position jusqu'à son TP/SL ? » Lecture du
code, pas supposition : le chemin live (`run_live.py`, poids `preset risk-parity + DD-target`)
n'a AUCUNE sortie déclenchée par un TP ou un SL aujourd'hui — une seule cause de clôture existe,
le rebalancement (`exit_reason` toujours identique, `"reconciliation paper (reduce/close)"`).
Le moteur avec stop ATR + reward:risk existe (`fast_swing_backtest`), mais étiqueté « legacy » :
ce n'est pas ce qui tourne en production.

**Ce qui a été construit : l'outil de mesure, pas la décision.** `make turnover-audit`
(`packages/research/turnover_audit.py`, 8 tests synthétiques) — coût (frais + slippage cumulés),
durée de détention médiane, taux de gain, et une « capture » (`pnl_pct / mfe`) qui dit si une
ligne sort loin de son meilleur point observé PENDANT sa détention. Limite dite explicitement
dans le module : ça ne dit rien de l'après-sortie (`mfe`/`mae` bornés à la fenêtre
[entrée, sortie]) — impossible de prouver qu'une position aurait continué à monter si on l'avait
gardée. **`data/journal.db` est vide dans cette session** (conteneur cloud fraîchement cloné) :
`UNCALIBRATED`, affiché tel quel plutôt qu'un chiffre inventé. La vraie histoire vit sur le Mac
mini et, désormais, le VPS. Prochain pas : lancer `make turnover-audit` là où le journal réel
existe, avant de choisir entre une bande de tolérance élargie sur le rebalancement existant (la
piste la plus probable) et un moteur TP/SL parallèle (qui entrerait en conflit d'arbitrage avec
le risk-parity — pas construit tant que ce n'est pas mesuré comme nécessaire).

## Session 2026-09-04 (suite 8) — « Contribution alpha 1072 % » : le bêta était faux, pas l'alpha

**La question était la bonne.** Devant le tableau de bord : « contribution alpha, est-ce correct ?
Il me semble élevé. » Oui — mais le chiffre à regarder n'était pas la contribution alpha, c'était
le **bêta de 0,037** juste à côté, avec une corrélation de 0,031. Un portefeuille long-only
d'actions américaines qui ne bouge pas avec le Nasdaq, cela n'existe pas. Et une contribution
alpha n'est qu'un résidu : `r − β·b`. Bêta écrasé ⇒ tout le rendement bascule en « alpha ».
Les 1 072 % n'étaient pas une performance, c'était le symptôme.

**Cinquième et sixième occurrences du même défaut.** Le matin même, ADR-0067 corrigeait
`compute_attribution`. Mais le panneau web ne passe pas par cette fonction : il lit
`/api/analytics` → `packages/reporting/analytics.py`, qui faisait `m = min(len(r), len(b))` puis
`r[-m:], b[-m:]`. Le correctif du matin ne touchait pas ce que l'utilisateur regarde. En cherchant,
une sixième : `_bench_series` posait le i-ème cours du S&P sur la i-ème date du portefeuille — la
courbe de comparaison tracée sous l'equity du tableau de bord, tous les jours.

**Mesuré, pas déduit.** Deux fois la même courbe sur 400 séances, cinq séances retirées du seul
calendrier du benchmark (1,25 %) : par date bêta 1,200 / corrélation 1,000 ; par position bêta
0,345 / corrélation 0,288. **1,25 % de calendrier détruit 71 % du bêta.** Sur un levier pur 1,2×,
dont l'alpha est nul par construction, la part « alpha » passe de 5,5 % à 47,6 %.

**Ce qui change à l'écran.** Le bêta et l'alpha sont calculés sur les séances COMMUNES aux deux
calendriers, et le panneau dit lesquelles (`n_observations`). Si le calendrier du benchmark
manque, l'appariement reste positionnel mais le tableau de bord l'affiche en orange :
« bêta et alpha non fiables ». Un chiffre publié porte désormais la manière dont il a été obtenu.

**Ce que je n'ai PAS fait, et pourquoi.** La chasse a sorti trois autres endroits du même moule :
l'indice équipondéré `eqw` (`zip(*norm)` empile la première barre de chaque titre — 2015 pour un
ancien, 2023 pour une IPO récente), l'horodatage de `fast_swing` (`n = max(len)`, dates prises du
premier symbole), et `_align` de `packages/portfolio/benchmark` qui tronque par le DÉBUT face à une
equity plus longue. Ce sont des lectures de code, pas des mesures : je n'ai pas les bases ici pour
chiffrer l'écart. Remplacer un chiffre publié par un autre sans l'avoir mesuré serait refaire
l'erreur de la veille dans l'autre sens. P1 au TODO, avec le mécanisme exact.

**Prochain pas.** `make sync` puis relancer un build : le tableau de bord doit afficher un bêta
plausible (0,5–0,9 pour ce portefeuille). Si le bêta reste sous 0,1 après appariement par date,
c'est que les deux calendriers ne se recouvrent presque pas — et c'est alors `n_observations` qui
le dira, au lieu du silence.

## Session 2026-09-04 (suite 7) — Deux fois la même erreur : j'ai deviné le payload au lieu de le lire

**Deuxième blocage, deuxième faute de ma part.** Le gate a de nouveau arrêté le déploiement, en
annonçant : `dashboard.json/equity : 2392 point(s) non exploitable(s)` sur une courbe de
2 392 points, plus les deux courbes de `live.json`. Toute la courbe, donc. J'ai vérifié avant de
conclure — et c'était un FAUX POSITIF.

**La forme, après les noms.** Le dépôt publie ses courbes principales en listes de POINTS
`{"t": date, "v": valeur}` — `_dash_equity`, `alpaca_perf.curve`, `crypto_perf.curve`. Ma règle
n'acceptait que des listes de nombres et comptait chaque point comme un trou. Hier j'avais deviné
les NOMS de clés (`qqq` désigne aussi un poids), aujourd'hui la FORME. Deux fois la même faute de
méthode : construire un contrôle contre l'idée que je me fais du payload, plutôt que contre le
payload.

**Le second défaut est bien pire que le premier, et il était invisible.** `coherence_site`
ignorait ces mêmes courbes SANS RIEN DIRE : sa règle « une courbe positive interdit une
statistique de −100 % », écrite exactement pour attraper le CAGR de −100 % de la veille, **ne se
serait jamais déclenchée sur le vrai tableau de bord**. Un faux positif fait échouer un build, on
le voit. Un contrôle silencieux laisse croire qu'on est protégé — et j'aurais annoncé une
protection qui n'existait pas.

**Ce qui est corrigé.** `valeurs_de_courbe` reconnaît les deux formes, une seule fois, et les deux
modules l'utilisent. Une liste de dicts n'est une courbe que si ses points portent une valeur —
sinon c'est un tableau (positions, trades) et on ne le juge pas. Une entrée textuelle au milieu de
nombres reste un trou : être indulgent là-dessus rendrait la règle silencieuse, ce qu'on vient
précisément de payer. Douze tests de plus, sur les formes RÉELLES.

**Ce que les deux échecs disent de bon.** À aucun moment le site en ligne n'a été modifié :
`deploy` a été SKIPPED deux fois. Le principe « un build rouge ne publie pas » a tenu, y compris
contre mes propres erreurs. C'est la seule chose qui a bien fonctionné aujourd'hui, et c'est celle
qui compte.

**Le blocage a aussi révélé quelque chose que je n'avais pas demandé.** L'inventaire des dates
d'arrêté imprime trois valeurs distinctes : `events`/`themes`/`universe` au 04/09, `screener` et
`dashboard.regime` au 02/09, et **`dashboard` racine + `data` au 18/06** — deux mois et demi de
retard. Je ne sais pas encore si c'est légitime (fenêtre de backtest close) ou si c'est un défaut.
C'est noté, pas conclu.

## Session 2026-09-04 (suite 6) — Mon gate a bloqué le déploiement, et il avait tort

**Ce qui s'est passé.** PR #369 mergée, CI verte, build Pages lancé — et le gate de publication a
échoué. Pas sur une incohérence : sur une `TypeError`. `'float' object is not iterable`.

**La cause, et c'est ma faute de méthode.** `trous_dans_courbe` faisait `if not courbe` puis
itérait. Appelée sur `index_core.spec = {"qqq": 0.5, "megacap": 0.3, "sector_mom": 0.2}` — où ces
noms désignent les **POIDS** du cœur et non ses courbes — elle a levé. **J'avais deviné les noms
de clés au lieu de les vérifier sur le payload réel.** Un nom peut toujours resservir ailleurs
avec un autre sens ; le type, lui, ne ment pas. Le filtre est désormais `isinstance(list)`.

**Ce que l'échec dit de bien, et ce qu'il dit de mal.** De bien : rien n'a été publié, le site en
ligne est resté intact, `deploy` a été SKIPPED. Le principe « un build rouge ne publie pas » a
tenu. De mal : un gate qui plante est aussi nuisible qu'un gate absent — devant un build rouge
inexpliqué, le premier réflexe est de désactiver le contrôle, pas de chercher la cause. Un
gate doit être increvable avant d'être sévère.

**`coherence_site` ne portait pas la faiblesse** : il filtrait par `isinstance(list)` dès
l'origine. Seul `gate_publication` guessait. Quatre tests de non-régression, dont un qui balaie
tous les types d'entrée et exige qu'aucun ne lève.

**La leçon, et c'est la même que celle du cache `.next` et de la branche écrasée.** J'ai vérifié
mon gate sur des fixtures que j'avais écrites moi-même, donc conformes à l'idée que je me faisais
du payload. Je l'ai ensuite exercé sur une structure calquée sur le VRAI dashboard — poids,
courbes, métriques, régime, positions — et c'est seulement là qu'il devient crédible. Tester son
code contre sa propre représentation du monde ne teste que la représentation.

## Session 2026-09-04 (suite 5) — « Plus aucune incohérence » : ce qu'on peut réellement garantir

**La demande, et ce que j'en fais.** « Assure-toi que TOUTES les données publiées — local, en
ligne, ordinateur, téléphone, entre onglets — soient cohérentes et correctes. » Je ne peux pas
promettre l'absence d'erreur : ce serait une promesse que le code ne tient pas, et ce carnet est
plein d'affirmations de ce genre qu'il a fallu retirer. Ce que je peux faire, et qui vaut mieux :
transformer l'exigence en **contrat vérifié par la machine, qui casse le build**.

**Le fait qui rend les invariants durs.** Les 24 payloads dérivent d'UN SEUL snapshot
(`dump_static` appelle `M._snap()` une fois). Deux pages ne peuvent donc pas diverger à cause des
données : si elles divergent, le même nombre est calculé à deux endroits et l'un des deux est
faux. C'est exactement l'historique du dépôt — PSR à 0,0 % et 100 % sur la même page, trois
conventions de Sortino, un bêta de 0,006, un CAGR de −100 % avec Sharpe positif.

**Le principe de conception : AUCUN faux positif.** Un gate qui crie au loup finit désactivé, et
ce dépôt l'a déjà vécu — le détecteur de fraîcheur macro se trompait 4 fois sur 5 et « apprenait
à être ignoré ». Chaque règle est donc une IMPOSSIBILITÉ, pas un seuil :

  · une courbe strictement positive interdit toute statistique d'anéantissement — aucun argument
    de flux, de frais ou de fenêtre ne franchit cette borne ;
  · une courbe et ses dates ont la MÊME longueur — signature de l'empilement positionnel, quatre
    occurrences ici ;
  · un capital anéanti avec un ratio positif, ou un `null` dans une courbe publiée (ADR-0070).

Les tests « doit PASSER » comptent autant que les autres : une vraie ruine passe, une perte de
−62 % passe, un anéantissement avec Sharpe négatif passe. Ce sont eux qui gardent le gate
crédible.

**Local ≠ en ligne : le piège structurel, désormais testé.** Le front a deux modes —
`data/<nom>.json` en statique (téléphone, ordinateur en ligne) et `localhost:8000/api/…` en local.
Une page qui appelle une route que `dump_static` n'écrit pas fonctionne parfaitement en local et
rend **404 en ligne** ; le développeur ne le voit jamais, il travaille sur le mode qui marche.
Comparaison faite : 25 routes appelées, 26 fichiers publiés, **aucune manquante**, un seul
orphelin (`overlays`, neutralisé exprès). Rien à corriger aujourd'hui — et c'est justement le
moment d'écrire le test, pendant que c'est vert : un test ajouté après la panne ne protège que du
passé.

**Ce qui est inventorié plutôt que bloqué.** Les dates d'arrêté diffèrent LÉGITIMEMENT entre
domaines : la crypto cote le week-end, les actions non. En faire une règle produirait un faux
positif chaque samedi. Le build les RECENSE dans son log — mesurer sans juger vaut mieux qu'une
règle fausse.

**Ce que ce dispositif ne couvre pas, et il faut le dire.** Il vérifie la cohérence *interne* des
chiffres publiés et la parité des routes. Il ne vérifie pas qu'un chiffre est JUSTE au sens
économique — aucun automate ne le peut. Le journal réel reste local-only par construction (le
build CI n'a pas les clés courtier), donc les chiffres de compte du site public ne sont pas ceux
du Mac : ce n'est pas une incohérence, c'est un périmètre, et il est désormais affiché.

## Session 2026-09-04 (suite 4) — `0 × NaN = NaN` : une panne visible en production

**Le signalement.** Le téléphone affichait gain total **−100 %**, CAGR **−100 %**, pire baisse
**−100 %** — et, dans les mêmes cartes, Sharpe **0,25** et Sortino **0,18**, tous deux POSITIFS.
Cette combinaison est arithmétiquement impossible : un capital réduit à zéro ne donne pas un
Sharpe positif. C'est elle qui a permis de remonter à la cause, parce que les deux familles ne
sont pas calculées au même endroit — les ratios sur les rendements, le CAGR sur les extrémités
de la courbe nettoyée.

**La cause, en une ligne.** `preset_curves` calculait
`(w * (A[:, t+1] / A[:, t] - 1)).sum()`. Or **`0 * nan` vaut `nan` en numpy** : un titre au poids
ZÉRO, qu'on ne détient même pas, suffisait à rendre le rendement du jour NaN dès qu'il lui
manquait un cours. L'equity devenait NaN, puis toute la fin de la courbe.
`dump_static._clean` convertit ensuite NaN en `null` — le bon geste, sans quoi le JSON serait
invalide et la page bloquée — et le front lit ce trou comme un zéro.

**Le NaN n'est pas une anomalie ici.** Depuis l'alignement par date, la matrice en contient
légitimement : un titre ne cote pas toutes les dates du panel. Ce n'est donc pas une donnée à
traquer en amont, c'est un état normal que ce calcul devait savoir traverser. `megacap` avait le
même défaut, sans même la garde de poids ; `sector_momentum` portait déjà la sienne. Les deux
renormalisent désormais sur les lignes cotées — les ignorer sans renormaliser supposerait que la
part manquante fait 0 % ce jour-là, ce qui est un rendement inventé, pas une absence.

**Ce qui est plus grave que le bug : le gate ne regardait pas les nombres.** `check_build`
vérifiait la présence des fichiers, leur taille et leur fraîcheur. Un dump complet, volumineux et
daté du jour annonçait la ruine, et passait au VERT. C'est l'utilisateur qui l'a vu.

`gate_publication` ajoute deux règles, et ce sont des **contradictions**, pas des seuils :

  1. capital anéanti (≤ −99,9 %) avec un ratio positif → impossible ;
  2. `null` dans une courbe d'équity publiée → une courbe percée n'est pas une courbe.

La seconde vaut mieux que la première : elle attrape la CAUSE, pas le symptôme. Et le choix des
contradictions plutôt que des seuils est délibéré — « CAGR < −50 % » serait un jugement, une
stratégie a le droit de perdre, et un gate qui refuse les mauvaises nouvelles finit par cacher
les vraies. Vérifié de bout en bout : perte sévère cohérente → PUBLIÉ ; anéantissement avec
Sharpe négatif → PUBLIÉ ; le cas exact du 04/09 → REFUSÉ ; courbe percée → REFUSÉ.

## Session 2026-09-04 (suite 3) — Audit de fuite du momentum sectoriel : la cause est l'univers

**Le verdict.** CAGR 55,5 % sur 9,4 ans avec DSR 100 % n'était pas un résultat. Trois causes
possibles, séparées par la MESURE plutôt que par l'opinion :

  · **coûts de transaction absents** — réel, et MINEUR. Le module rotait mensuellement sur deux
    secteurs entiers sans jamais rien payer, tout en étant comparé à QQQ, un buy-and-hold de
    turnover nul. Mesuré sur panneau synthétique (24 titres, 4 secteurs) : **0,64 point de
    CAGR**. Corrigé (5 bps, même convention que `coeur_multi_actifs`), frais publiés avec le
    résultat. Ce n'est pas l'explication.
  · **look-ahead dormant dans la MM50** — `_sma` remplissait ses `w-1` premières cases avec
    `out[0]`, la moyenne des jours 0..w-1 : lue à t=10, elle contient l'avenir. Jamais lue
    aujourd'hui (la boucle démarre à `max(lookback, 50)` = 126), mais un `lookback` plus court
    la réveillerait **en silence**. Remplacé par NaN — une comparaison avec NaN vaut False, donc
    le titre est écarté du filtre au lieu d'être admis sur une valeur inconnaissable.
  · **univers de SURVIVANTS** — et c'est la cause principale.

**Le mécanisme, à la ligne près.** `build_snapshot` nettoie l'univers : tout titre dont la
dernière barre a plus de dix jours est retiré de `data`. C'est-à-dire **tous les délistés, avant
que le moindre backtest ne tourne**. Ce cœur classe ensuite des secteurs sur 9,4 ans en ne voyant
que les sociétés qui existent ENCORE. Les faillites et radiations qui auraient vidé les paniers
sectoriels ont été écartées par construction. C'est exactement la configuration qui fabrique un
CAGR spectaculaire.

**L'audit existait déjà et répondait à côté.** `survivorship_audit` rapporte le nombre de
délistés CONNUS au nombre d'actifs : sur 3 titres vivants et 43 délistés au catalogue, il annonce
« corrigé (partiel) » et 93,5 % de couverture. Il répond à « en connaît-on ? », pas à « sont-ils
DANS le panneau ? ». Un délisté absent ne corrige rien. `_biais_survivant` compte donc les
délistés RÉELLEMENT présents dans l'univers du backtest — zéro présent, biais ÉLEVÉ, quel que
soit le catalogue.

**Et surtout : le chiffre ne voyage plus seul.** Le statut du biais est attaché au résultat, pas
posé à côté. Un CAGR séparé de son biais se lit comme un résultat — c'est précisément ce qui
s'est produit jusqu'ici, l'audit étant disponible mais jamais joint.

**Ce que je n'ai PAS fait.** Corriger le biais. Cela demande l'historique de prix des délistés,
que le dépôt sait sous-échantillonné. Tant qu'il manque, ce cœur reste INDICATIF — et il le dit
désormais dans son propre résultat.

## Session 2026-09-04 (suite 2) — Un bêta de 0,006, et trois Sortino pour un portefeuille

**Le bêta absurde avait une cause lisible.** `compute_attribution` comparait la courbe du preset
(calendrier de l'univers négociable) à celle de QQQ (calendrier des indices) **par position** —
`n = min(len(...))` puis `[-n:]`. Publié : **bêta 0,006 et corrélation 0,008** pour un
portefeuille long-only d'actions américaines. Un chiffre que personne ne peut croire, affiché
sans que rien ne le signale.

**La racine était une ligne en amont.** `_index_closes` faisait `closes, _dates, real =
_index_series(...)` puis `return closes, real` : les dates existaient et étaient jetées juste
avant qu'on en ait besoin. `_index_closes_dates` les conserve, le snapshot publie `qqq_dates`, et
l'attribution apparie par date. Sans les deux calendriers, elle **refuse** désormais de conclure
avec un motif — un résultat absent se voit, un résultat faux se lit.

**Ma première contre-épreuve ne prouvait rien, et je l'ai vu à temps.** J'avais écrit un test où
QQQ démarre cinq séances plus tard : l'appariement positionnel y donnait corrélation 1,000, tout
comme le corrigé. Normal — les deux séries **finissent le même jour**, donc compter depuis la fin
tombe juste. Le vrai mécanisme est ailleurs : des trous INTÉRIEURS de calendrier (jours fériés
d'indice absents de l'univers négociable). Reproduit : même actif, douze fériés intérieurs,
**corrélation 0,29 en positionnel contre 1,00 par date**. Le test dit maintenant cela, et le
dit dans son docstring — un test qui passe pour la mauvaise raison est pire que pas de test.

**Quatrième occurrence de l'empilement positionnel.** `apparier_deux_series` rejoint
`aligner_par_date` dans `panel.py` : une seule règle d'alignement, deux points d'entrée selon la
forme des données.

**Trois conventions de Sortino, et le backlog sous-estimait l'écart.** `index_core` et
`company_report` appliquaient la définition (RMS de min(r,0) sur N total) ; `metrics.sortino` et
`perf_summary` prenaient l'écart-type des NÉGATIFS seuls ; `analytics` l'écart-type de min(r,0).
La note annonçait 1,04× d'écart. Mesuré sur 2 520 rendements (46,6 % de séances négatives) :

    définition (RMS sur N)         0,008314    Sortino ×1,000
    écart-type des NÉGATIFS        0,007369    Sortino ×1,128
    écart-type de min(r,0) sur N   0,006979    Sortino ×1,191

**Douze à dix-neuf pour cent**, et les deux erreurs vont dans le même sens : elles flattent.
Diviser par le nombre de négatifs est la plus grave — le ratio cesse alors de dépendre de la
FRÉQUENCE des pertes, ce que Sortino existe précisément pour mesurer. Une définition unique en
Python pur (`portfolio.deviation`, sans numpy puisque `analytics` et `company_report` s'en passent
délibérément), quatre appelants branchés dessus.

## Session 2026-09-04 (suite) — Une politique de fusion au lieu de deux, et un scan qui se compte

**Le contexte : deux questions produit.** L'utilisateur demande s'il faut ajouter un onglet
« l'IA pilote TradingView » (sur la foi d'un post viral) et un onglet « entrepôt de données ».
Réponse aux deux : non, parce que le dépôt possède déjà l'essentiel des deux — `mcp_tradingview`
expose neuf outils (dont `generate_pine`, `compare_pine_python`, `query_market_db`), `pine.py`
traduit le preset en Pine v5, le copilote `/api/ai/chat` existe avec ses scopes ; et côté données
l'architecture médaillon bronze/silver/gold, le dépôt DuckDB avec export Parquet, le feature store
GOLD, `make audit` et `make contracts` sont là, page `/data` comprise. Ce qui manquait n'était pas
des onglets.

**Chantier 1 — une seule politique de fusion, et le lignage.** Le défaut est mesuré depuis des
jours et restait ouvert : `_load_prices` fusionnait en « premier gagne », `merge_bars` en
« dernier gagne », **sur les mêmes bases**. Mêmes dates, deux historiques selon la fonction qui
demande — 0,71 %/an d'écart sur le cœur QQQ. La règle retenue est celle qui avait une raison
écrite : la base longue est AJUSTÉE, la couche de maj est brute, la laisser écraser insérerait
une discontinuité raw/ajusté au milieu de l'historique. La fraîcheur n'en souffre pas, les dates
récentes étant justement celles qui manquent à la base longue. Une seule implémentation
(`fusion_sources`), deux appelants, et un LIGNAGE qui enregistre quelle source a fourni chaque
jour — la question « d'où vient cette barre ? » devient une lecture au lieu d'une enquête.

**Et la mesure qui manquait.** `make diag-fusion` chiffre, symbole par symbole, sur combien de
jours les bases se recouvrent et sur combien elles DIVERGENT. Tant qu'on ne l'avait pas,
« les bases sont d'accord » était une hypothèse. Un désaccord ne dit pas laquelle a raison : il
dit que la priorité change le résultat, donc qu'elle doit être motivée plutôt que subie.

**Chantier 2 — un scan est un essai.** Un scanner en langage naturel balaie 200 titres en une
minute ; c'est sa qualité, et c'est ce qui en fait une machine à tests multiples. « RSI < 30 »,
puis « et si c'était 25 ? », puis « et en 4 h ? » : trois essais, trois questions légitimes, zéro
trace. `scan_registre` valide des critères STRUCTURÉS (aucun parseur de langage naturel enfoui
dans la couche de recherche — c'est le travail du modèle appelant), exécute purement, et produit
un enregistrement pour le `ledger`.

**Le retournement, et c'est la raison d'être du module.** Le compte d'essais est aujourd'hui
SOUS-estimé : les idées essayées à la main ne sont journalisées nulle part, donc le `N` du DSR ne
voit qu'une fraction de la recherche et déflate trop peu. Un scanner qui enregistre rend ce compte
honnête pour la première fois. Idempotence obligatoire dans les deux sens : rejouer le même scan
n'est pas un nouvel essai (sur-déflater est l'erreur symétrique, tout aussi fausse), mais deux
seuils différents SONT deux essais.

**Chantier 3 — DuckDB : ce que j'ai trouvé, et ce que je refuse de conclure.**
`make_bars_repository` choisit entre sqlite et duckdb… et **n'est appelé nulle part**. Le dépôt
DuckDB existe, son docstring dit « écrit pour la prod, non exécuté hors-ligne », et rien ne
l'exécute. Je ne peux pas le mesurer d'ici (`duckdb` absent de cet environnement), donc je
n'affirme aucun gain : `make bench-backend` le mesurera sur la vraie base, **avec sa règle de
décision écrite avant le run** — gain médian < 1,5× on reste sur SQLite, ≥ 1,5× le basculement se
justifie mais reste conditionné à l'unification de `DBPriceProvider` et `BarsRepository`. Ces deux
abstractions sur la même donnée sont d'ailleurs la vraie raison pour laquelle la fabrique n'a
jamais eu d'appelant.

## Session 2026-09-04 — `make start` écrasait ce que `make sync` venait de récupérer

**Ma explication d'hier était fausse.** J'avais mis les deux correctifs invisibles (`/sentiment`
dans la barre, étiquette Bund) sur le compte du cache `.next`. Le terminal de l'utilisateur le
montre autrement, en une ligne :

    make sync   → b40ee72   (branche de dev, mes commits)
    make start  → 43b15a9   (origin/main)

`start.sh` faisait `git reset --hard origin/main`. `make sync` alignait la branche de dev, puis
`make start` la réécrasait deux secondes plus tard sur `main`, où rien n'est mergé. **Les
correctifs n'ont jamais tourné.** Et comme le Makefile de `main` est plus ancien, `make sync`
disparaissait ensuite — l'utilisateur perdait jusqu'à la commande qui sert à sortir de là.

**Le forçage visait un vrai danger** — une branche de travail restée en arrière, et `make start`
ramenant du code vieux de quatre PR sans rien dire. Mais il en créait un pire : il détruisait
l'état que l'utilisateur venait délibérément de demander. Un garde-fou qui écrase le geste qu'il
est censé protéger n'est plus un garde-fou.

**Ce qui remplace.** `start.sh` suit la branche COURANTE, et le danger d'origine est traité par
un AVERTISSEMENT chiffré : « en retard de N commits sur main », avec la commande pour se
réaligner. Informer laisse le choix ; écraser le retire. Vérifié sur dépôt jouet : sur `dev`,
le contenu reste celui de `dev` ; HEAD détaché retombe sur `main`.

**La leçon de méthode, et c'est la deuxième fois cette semaine.** J'ai expliqué un symptôme par
une cause plausible — le cache — sans mesurer laquelle des deux agissait. La sortie du terminal
contenait la réponse depuis le début. Chercher la cause dans le code qu'on croit exécuté, sans
vérifier QUEL code est exécuté, c'est la même erreur que déduire un latent au lieu de le lire.

## Session 2026-09-03 (suite 6) — Le correctif était juste ; c'est le build qui mentait

**Deux correctifs poussés, deux « ça n'a pas marché ».** Le menu « Marché » affichait toujours ses
cinq anciennes entrées sans `/sentiment`, et la tuile Bund portait encore « série arrêtée ». Le code
poussé contenait pourtant les deux corrections, vérifiées dans le fichier.

**La cause est le cache `.next`.** `make start` lance `npm run dev`, qui resert le rendu mis en cache.
Après un `make sync` qui change les sources, le navigateur montre l'état d'AVANT — et rien ne le
signale. C'est le pire mode de défaillance possible : on croit lire le résultat de son correctif,
on lit celui d'avant, et l'on va chercher un bug déjà corrigé.

**Le garde-fou.** `start.sh` tamponne le commit ayant produit le build dans
`apps/web/.quant-build-commit` — HORS de `.next`, que Next régénère — et purge le cache si la tête
courante en diffère. Trente secondes de rebuild contre une heure de fausse piste. Vérifié sur les
trois cas : premier lancement (purge), relance au même commit (cache conservé), nouveau commit
(purge). Ajouté aux pièges connus de `CLAUDE.md` : **avant de conclure qu'un correctif front ne
marche pas, vérifier qu'il est BUILT.**

## Session 2026-09-03 (suite 5) — Trois signalements de l'utilisateur, trois affirmations fausses du site

**Le nettoyage a tenu.** 33 lots retirés : 343 enregistrements → 310, lots ouverts `legacy`
45 → 12, lots fantômes 43 → 10, symboles à 2× **29 → 3**, excédent 3 308 → 1 317 unités, et
« lots ouverts appariés à une vente » **33/52 → 0/19** — il n'en reste aucun que la preuve
désigne. Le reliquat (NWL 1,74×, MAS 1,91×, QQQ 1,56×) tient à des ventes exécutées en
PLUSIEURS fills, que le critère strict refuse d'apparier : c'est le plancher assumé.

**Six sorties antérieures à leur entrée, −142,33 $.** SJM, STT, PATH, DUOL, TYL, T. La garde
`_anterieur` empêche d'en créer ; elle ne rétroagit pas. Leur reprise reste ouverte.

**« Mon profil » ne contraignait rien.** L'utilisateur demande : « une fois réglé, est-ce pris en
considération ? » Mesuré : `quant.profil` n'est lu que par la page qui l'écrit, et `/api/profil`
n'est appelée que par elle. Aucun autre écran, ni la chaîne d'exécution, ne les consulte. Or la
page et l'API affirmaient toutes deux « ces chiffres CONTRAIGNENT votre outil ». C'est faux, et
c'est la troisième affirmation de ce type corrigée aujourd'hui. Les deux textes disent désormais
ce que le code fait : un calcul de RÉFÉRENCE.

**Et le réglage se perdait — vraie course, vrai correctif.** L'effet d'écriture partait au
MONTAGE, donc avec les valeurs par DÉFAUT (l'état restauré n'étant pas encore appliqué), et
écrasait le stockage avant que la restauration ne s'y réécrive. Quitter la page entre ces deux
instants suffisait à perdre le réglage. Un drapeau `lu` interdit d'écrire avant d'avoir lu, et
la persistance est séparée de l'appel API — deux préoccupations, deux effets.

**Une page invisible n'existe pas.** « Je ne retrouve plus l'onglet des news. » Elle n'avait pas
été supprimée : la réduction à 3 groupes l'avait laissée hors de tout menu, joignable seulement
par URL directe ou ⌘K. `/sentiment` et `/events` reviennent dans « Marché ». Onze autres pages
restent hors de la barre (`/fiche`, `/live`, `/trades`, `/portfolio`, `/ml`, `/conviction`,
`/notes`, `/investors`, `/fundamentals`, `/data`, `/accueil`) — c'est le résultat de l'audit
« simplicité radicale », pas un accident, donc je ne le défais pas sans décision.

**Le Bund n'était pas mort, il était en retard — et le détecteur ne savait pas dire la
différence.** Dernière observation au 01/06, 94 jours, seuil 93 : dépassement d'UN jour, soit
3,03× la cadence. Le cas qui a motivé la règle — chômage zone euro — valait 43×. Le même mot
pour les deux le rend inutilisable, et la série OCDE des taux longs, publiée avec deux mois de
décalage structurel, rebasculerait en « arrêtée » à chaque trimestre : une alerte qui clignote
au rythme du calendrier de publication apprend à être ignorée. Deux seuils désormais — au-delà
de 3× la publication est EN RETARD, au-delà de 12× (un an de silence sur du mensuel) la série
est ARRÊTÉE. `perimee` reste vrai dès le retard pour ne casser aucun appelant ; `statut` porte
la nuance.

## Session 2026-09-03 (suite 4) — La lecture tient à l'échelle, et une sortie précédait son entrée

**Confirmé sur 87 symboles, plus seulement deux.** 79 sur 87 ont des FERMETURES égales à la
quantité achetée à 0,01 % près ; les 8 autres (PATH, T, QQQ, DUOL, TRV, TYL…) ferment MOINS
qu'elles n'achètent — ce sont exactement les titres dont le journal et le courtier s'accordent
dans le tableau des positions, c'est-à-dire ceux encore détenus. L'appariement des sorties est
donc sain partout. **33 des 52 lots ouverts portent la signature exacte d'une vente exécutée**,
et le critère étant strict (un fill unique de même quantité et même prix), 33 est un PLANCHER.

**L'identité comptable est refermée : écart +3,93 $ sur +868,83 $.** De −4 198 $ ce matin.

**Le bug que la question de l'utilisateur a trouvé.** « Une entrée DUOL le 03/09 et une sortie
le 01/09, ce n'est pas logique. » Non, et c'était un défaut de `reconcilier_journal._plan` :
l'appariement prenait le plus ancien lot du symbole **sans jamais regarder sa date d'entrée**.
Une vente pouvait donc fermer un lot qui n'existait pas encore, et le P&L du round-trip fabriqué
était calculé sur un prix de revient POSTÉRIEUR à la sortie. `_anterieur` compare désormais les
deux dates AU JOUR — pas à la seconde : le lot porte l'instant où le run l'a écrit, le fill celui
de l'exécution, et trancher à la seconde refuserait des aller-retours réels. Le FIFO saute le lot
trop récent au lieu de s'arrêter. 4 tests.

**Ce qui est livré pour le nettoyage, et sous quelles conditions.** `make annuler-ventes` retire
les lots ouverts dont la signature est celle d'un fill de VENTE. Ni écriture de correction, ni
fermeture au prix d'entrée : fermer produirait un aller-retour à 0,00 $ qui n'a jamais eu lieu et
gonflerait le compte de trades — on remplacerait une fausse position par un faux trade. Une
opération qui n'a pas eu lieu se retire. Survivent au retrait : une sauvegarde horodatée de la
base ET un JSON qui garde chaque ligne avec le fill qui l'a désignée — un retrait sans sa preuve
n'est pas rejugeable. Ce JSON porte des fills réels : ajouté au `.gitignore` (dépôt public).

**Ce que l'outil refuse.** Courtier injoignable → aucune preuve → aucun retrait. Vente exécutée
en plusieurs fills → pas d'appariement → le lot reste ouvert et reste signalé. On préfère un
registre encore imparfait à un registre nettoyé sur une présomption.

## Session 2026-09-03 (suite 3) — Le registre est exact là où il ferme ; il invente là où il ouvre

**Le dump a répondu, et la réponse est plus simple que mes deux hypothèses.** Sur les deux titres
ventilés, la partie FERMÉE du journal égale la quantité achetée **au dix-millième** :

    ICLN — fermés 301,600106 · acheté 301,6001 · écart +0,0000 · OUVERT 301,600106
    NWL  — fermés 1 554,626507 · acheté 1 554,6265 · écart +0,0000 · OUVERTS 1 306,379607

L'appariement des sorties est donc juste. **Tout l'excédent est dans les lots OUVERTS**, et le
chiffre des lots ouverts NWL — 1 306,379607 — est exactement celui que le tableau
« journal vs positions réelles » signalait déjà comme fantôme.

**Ce que ces lots ouverts sont.** Ils portent la date et le prix de VENTES :

  · ICLN, lot ouvert de 301,600106 entré le 23/06 à 20,8300 — jour et prix EXACTS de la vente
    qui a soldé les deux lots précédents ;
  · NWL, lot ouvert de 155,375433 entré le 25/06 à 5,7800 — quantité identique au millionième,
    même jour et même prix que la SORTIE `-R1`.

Une vente a été enregistrée comme une ouverture. C'est la cause du « 2× » : le journal porte
`acheté + vendu` là où un aller-retour complet est bouclé, d'où le rapport exactement 2,0000 sur
les titres soldés, et 1,84 sur NWL qui ne l'est pas entièrement.

**Ce qui est livré, et ce qui ne l'est pas.** `_excedent_dans_les_ouverts` teste cette lecture
sur TOUS les symboles et sur chaque lot ouvert : existe-t-il chez le courtier une vente de même
symbole, même quantité, même prix ? L'appariement est volontairement strict — une vente exécutée
en plusieurs fills ne sera pas appariée — donc le compte renvoyé est un **plancher** : il
sous-estime, il ne peut pas surestimer. C'est le sens qu'on veut pour un chiffre qui servira à
décider d'un retrait de lignes. **Aucune ligne n'est retirée avant de l'avoir lu.**

**Troisième hypothèse, première confirmée — et c'est la mesure qui l'a produite, pas une lecture
de code.** Les deux précédentes (recouvrement import/live, puis deux identités par le chemin
d'écriture) restent écrites avec ce qui les a démenties.

## Session 2026-09-03 (suite 2) — Ma deuxième hypothèse sur le doublon est fausse aussi

**Ce que la ventilation a répondu.** J'avais écrit deux lectures possibles : deux préfixes à ~1×
chacun (import historique + live), ou un seul préfixe à 2× (le chemin d'écriture crée deux
identités). C'est la seconde, et sous une forme que je n'avais pas prévue : **tout est `legacy=1`,
tout porte le préfixe `LEG`, et la quantité se répartit sur PLUSIEURS identifiants** — ICLN
603,2002 sur 3 ids pour 301,6001 acheté, NWL 2 861,0061 sur 8 ids pour 1 554,6265 acheté, RIOT
248,4954 sur 2 ids pour 124,2477. Le recouvrement import/live est écarté : `legacy=0` vaut
0,0000 sur les huit symboles ventilés.

**Pourquoi je ne peux pas lire la cause dans le code.** `grep` sur tout le dépôt ne trouve AUCUN
script qui écrive un identifiant `LEG-`. L'import qui les a produits n'est plus dans l'arbre.
On ne peut donc pas lire son mécanisme — seulement ses traces. `--symbole` imprime tous les
enregistrements d'un titre à plat (identifiant, quantité, entrée, sortie, motif), sans
interprétation. Ce sont ces lignes qui diront si le même achat a été importé plusieurs fois sous
des identités différentes, ou si un lot a été scindé sans que le reste soit réduit.

**Deuxième hypothèse à moi, deuxième réfutation en deux mesures.** Je les laisse écrites toutes
les deux dans le code, avec ce qui les a démenties : c'est le seul moyen qu'une troisième
génération de lecteur ne les repose pas.

**Un chiffre a bougé entre les deux diagnostics, et c'est normal.** Latent +439,93 $ puis
+541,36 $, écart −104,74 $ puis −220,43 $ : les cours ont changé entre 20 h 02 et 20 h 23. Le
latent est une mesure de marché, pas une constante du registre.

## Session 2026-09-03 (suite) — La réparation a tenu ; ce qu'elle a mis au jour ne l'était pas

**Ce que la réparation a donné, mesuré.** `completer-ouvertures` a reconstitué 30 ouvertures
(99 847 $ de coût de revient), `reconcilier-journal` a posté 67 fermetures avec les fills réels
(−3 860 $), et la couverture est passée de **57/87 à 87/87 — 0 incomplet**. L'identité comptable
se referme : réalisé +569,31 $, latent +439,93 $, attendu +1 009,24 $, constaté +904,50 $,
**écart −104,74 $** — contre −4 198 $ avant. Le résidu résiduel vaut le latent au premier point
de la courbe et les frais hors P&L, ce que le script disait devoir rester.

**Ce que la complétion a refusé de toucher, et c'était le bon geste.** 40 symboles où le journal
en sait PLUS que le courtier, signalés sans être corrigés. J'ai calculé le rapport sur les dix
premiers : **2,000000 ×** dix fois de suite (AAPL 47,2824 contre 23,6412 ; BXP 212,6200 contre
106,3100 ; FOX 317,8576 contre 158,9288). Ce n'est pas un arrondi. Le même achat est enregistré
deux fois.

**Pourquoi `_doublons` avait répondu « aucun doublon ».** Il ne compare que des lots OUVERTS de
mêmes titre, quantité, prix et jour. Les deux copies ont des identifiants différents, l'une peut
être fermée et l'autre non, et elles ne portent pas forcément le même drapeau `legacy`. Un test
trop étroit avait donc répondu par la négative à une question qu'il ne posait pas — c'est la
troisième fois de la semaine qu'une mesure trop spécifique passe pour une réfutation.

**Ce qui est livré, et ce qui ne l'est pas.** `_origine_du_double` VENTILE la quantité par drapeau
et par préfixe d'identifiant, sans rien supprimer. Deux préfixes portant chacun ~1× l'achat =
recouvrement entre l'import historique et la journalisation live. Un seul préfixe portant 2× = le
chemin d'écriture crée deux identités. Le chiffre tranchera au prochain `make diag-journal` ; je
ne tranche pas ici, et aucune ligne n'est retirée avant de savoir laquelle.

**Le panneau du site montrait un sous-ensemble favorable, et ne le disait pas.** `legacy=0`
affiche +6 260,82 $ et 70 % de réussite ; le compte a subi +569,31 $ et 56 %, le filtre masquant
266 lots et −5 691,51 $. Aucun des deux chiffres n'est faux : c'est de n'en publier qu'un qui
l'était. `perimetre_affiche` publie désormais les deux côte à côte, chiffrés. On ne verse PAS les
lots `legacy` dans la statistique affichée — ce sont des fills sans features de décision, et les y
mêler rendrait inutilisable le chiffre qui sert la calibration ML.

## Session 2026-09-03 — Le journal n'était pas faux, il était incomplet : la cause était à l'ENTRÉE

**La question posée.** « Trouve la solution pour que le journal soit FIABLE, puis fais-la. »
Deux jours de réparations portaient sur les SORTIES (lots orphelins, fermetures à +0,00 $,
résidu inexpliqué). Elles étaient justes et insuffisantes : on refermait un registre dont la
moitié des entrées n'avait jamais été écrite.

**La mesure qui a tranché.** `make diag-journal` compare, symbole par symbole, la quantité
ACHETÉE chez le courtier à celle que le journal connaît : **87 symboles achetés, 57 couverts,
30 INCOMPLETS** — AVAX 626 unités au journal contre 1 239 achetées, PATH 9 contre 139. Un achat
sans lot n'a pas de prix de revient : quand la position est vendue, le compte encaisse le
résultat et le registre n'a rien à lui opposer. Aucune réparation des sorties ne peut refermer
cet écart, parce qu'il ne naît pas là.

**La cause, à la ligne près.** `run_live._journal_opens` prenait le prix et la quantité d'entrée
dans la **position du courtier**, lue juste après l'envoi de l'ordre. Deux défauts dans un seul
geste : si la position n'était pas encore rafraîchie (ordre non rempli à l'instant du run,
marché fermé, latence), le fill était introuvable et l'achat n'était journalisé nulle part — le
message disait « capturé au prochain run », mais **rien ne le capture** ; et quand la position
était lisible, elle portait la quantité TOTALE et le prix de revient MOYEN, pas l'achat du jour.
Le lot ne décrivait donc pas l'opération qu'il prétendait décrire.

**Ce qui est branché.** Le fill vient désormais des **achats réellement exécutés du jour**
(`agreger_achats` : quantité et VWAP, par symbole canonique, `AVAX/USDC` et `AVAXUSD` confondus),
la position ne servant que de repli. Les fills existent après coup — un run tardif les retrouve,
une position non rafraîchie non.

**Le rattrapage de l'historique, et le point de méthode.** `make completer-ouvertures` reconstitue
les achats manquants depuis les fills. Le prix retenu n'est **pas** le VWAP de tous les achats du
symbole : ce serait mélanger les fills déjà couverts avec ceux qui manquent. On consomme les fills
en FIFO à hauteur de ce que le journal couvre déjà, et on retient le VWAP de **ceux qui restent** —
c'est-à-dire précisément ceux que le registre ignore. Ces lots sont écrits en `legacy=1` : leurs
features de décision n'ont jamais été capturées et ne peuvent plus l'être, c'est la définition du
drapeau. Les mettre en `legacy=0` gonflerait de trades aveugles la statistique qu'on cherche à
rendre fiable.

**Le piège que la complétion a révélé.** L'idempotence du réconciliateur écartait un fill de vente
dès qu'il avait servi UNE fois. Une vente de 500 unités qui n'avait trouvé que 200 unités de lots
était marquée consommée en entier : ses 300 unités restantes ne pourraient plus jamais fermer les
lots reconstitués, condamnés à rester ouverts pour toujours. On compte désormais la **quantité**
consommée par fill, pas son identifiant — le reste est rejoué, ni plus (pas de réalisé fabriqué),
ni moins.

**Ce que l'outil refuse de faire.** Rien pour un courtier muet : un silence n'est pas une mesure.
Et là où le journal en sait PLUS que le courtier, l'écart est **signalé, jamais corrigé** — il dit
autre chose (historique tronqué, lots fantômes), et un outil qui supprime des lots pour faire
coller les chiffres ne répare rien.

**Le panneau disait une chose fausse.** « C'est la matière première du verdict GO/NO-GO » : non —
`rdv_paper` lit la courbe d'équité. Le texte dit maintenant ce que le registre est (les trades) et
ce qu'il n'est pas (la performance du compte), et que son taux de réussite est **biaisé à la
hausse par construction** — le rebalancement solde les gagnants et garde les perdants ouverts, ce
qui explique 87 % au journal contre 28 % au backtest sans qu'aucun des deux soit faux.

**Ordre d'exécution, et il n'est pas commutatif :**
`make completer-ouvertures ARGS=--appliquer` → `make reconcilier-journal ARGS=--appliquer` →
`make diag-journal`. Le réconciliateur ne peut fermer que des lots qui existent.

## Session 2026-09-02 — Le suiveur coupait les gagnants, et deux runs identiques ne l'étaient pas

**Le résultat.** Retirer le stop suiveur bat le réglage de production sur payoff, marge, Sharpe,
DSR, espérance et net — et le **maxDD s'améliore** (−27,8 % contre −29,1 %). Le mécanisme était
annoncé depuis la veille : l'avantage vit dans la queue droite, et le suiveur à 5 ATR mordait
avant la cible à +24 ATR. Le 6:1 nominal n'existait pas. `trail_atr = 0.0` en production
(ADR-0052) ; le risque par trade est inchangé, le stop initial à 4 ATR tient.

**La règle avait été écrite AVANT de voir le chiffre** — « maxDD dégradé de moins de 3 points →
on bascule ; de plus de 6 → on garde malgré le Sharpe ». C'est le point de méthode de la journée :
sans règle préalable, tout résultat se justifie après coup.

**Ce qu'on refuse de toucher.** Le classement des cibles s'est INVERSÉ entre les deux jeux de
données : rr 6 meilleur le 01/09, rr 9 meilleur le 02/09. Un optimum qui bouge d'un jour à
l'autre est du bruit. `rr` reste à 6, et l'interaction n'est pas explorée : chaque essai relève
le seuil du DSR sur tout le reste.

**Le défaut que ce flip a révélé, et il est plus grave que le réglage.** Sur un appel au backtest
identique au caractère près (vérifié par diff), la même configuration a donné Sharpe 0,65 puis
0,38 à un jour d'écart. **Rien ne le disait.** Les trois bancs affichent désormais une EMPREINTE
— titres, barres, dernière date, provenance du VIX. Cette dernière parce que `_index_closes`
interroge le réseau quand la base est périmée : un banc de décision pouvait comparer en silence
un VIX réel à un VIX synthétique, et le multiplicateur d'exposition (×1,0 / ×0,7 / ×0,4) suffit à
tout déplacer. J'ai émis cette hypothèse puis elle n'a PAS été confirmée — le run du 02/09
affiche « VIX RÉEL ». Reste le jour de données ajouté, à confirmer.

**Troisième occurrence de l'empilement positionnel, et cette fois elle est de moi.** Le harnais
des candidats prenait `min(len(série))` comme axe : un titre de 265 barres réduisait la mesure à
14 jours pour les 785 autres, et les quatre candidats sortaient « trop peu de jours ». Écrit le
jour même où je corrigeais la deuxième occurrence dans `sector_momentum`. L'axe est désormais
l'union triée des DATES, chaque titre lu à sa propre position. Non-régression vérifiée dans les
deux sens : 14 jours sur l'ancien code, 149 sur le nouveau.

**Aussi livré** : ciblage de volatilité (Moreira-Muir) branché en opt-in — sa grille absolue
était INERTE, les cibles sont désormais des fractions de la vol réalisée ; `make sync` pour ne
plus jamais faire `git pull` sur une branche réécrite ; `signal_lab` et `candidats_lab` sous
protocole unique.

**Fait** : ADR-0051, ADR-0052, PSR/DSR réparés (#367), suiveur retiré. **Bloqué** : rien.
**Suite** : relancer `candidats_lab` avec le harnais réparé — le PEAD reste le seul candidat
structurellement orthogonal à la tendance.

## Session 2026-09-01 (2) — Cinq trades sur 477 séparaient le gagnant du perdant

**Le fait, sur les chiffres réels.** Profit factor 1,19, marge de payoff +19,5 % — tout paraissait
correct. Le profit factor privé des CINQ meilleurs trades valait **0,89** : sans 1,05 % des
trades, le système était perdant. Le panneau ne le montrait pas parce qu'il mesurait la part du
gain BRUT ; avec un profit factor proche de 1, cette part paraît modeste alors que le rapport au
NET bascule — et il n'était calculé nulle part.

**La question préalable, qui manquait aussi.** L'espérance est-elle distinguable de zéro ?
`t = 0,94`, IC 95 % de **[−21 ; +62] $** par trade — à cheval sur zéro. Il faudrait 2 184 trades,
soit 40 ans au rythme actuel. Attendre n'était pas un plan.

**Ce qui a tranché : la mesure en R.** Dimensionner à risque égal rend le P&L proportionnel au R,
donc le t sur les R est celui qu'on aurait obtenu à signaux identiques. 0,94 en dollars contre
**2,00 en R** ; PF-5 de 0,89 contre **1,21**. La concentration n'était pas dans le signal, elle
était dans la TAILLE des positions. Cause : `room` tronquait les lignes, donc la taille d'un trade
dépendait de combien le carnet était plein ce jour-là.

**Puis le re-run a contredit la contrefactuelle, et c'est le point de méthode de la journée.**
La mesure en R annonçait +114 % sur le t. Le backtest complet donne un Sharpe **indiscernable**
(p = 0,59) et un net **−29 %**. Une contrefactuelle n'est pas une expérience : redimensionner
change le capital disponible, donc les trades qu'on peut prendre. Adopté quand même à 0,5 %, sur
le seul fait établi (PF-5 0,89 → 1,15), explicitement PAS sur la performance → ADR-0051.

**Quatre erreurs à moi, toutes attrapées par un test ou par le re-run, aucune visible dans le
résultat publié :**
1. `x or []` teste la vérité de l'objet — le garde d'intégrité refusait le ndarray qu'il devait
   garder (9 tests rouges, et la CI de 7 à 38 min car `lru_cache` ne mémorise pas une exception) ;
2. le t en R publié en i.i.d. — la mesure censée corriger l'optimisme le reproduisait ;
3. un « biais de 19 % du bootstrap par blocs » annoncé puis démenti : **artefact d'arrondi** des
   IC à deux décimales ;
4. le banc de comparaison tournait **sans VIX**, donc à exposition maximale en permanence — il
   sous-représentait les troncatures qu'il était censé mesurer. Corrigé, sa ligne de référence
   reproduit la production au chiffre près (477 / 0,89 / 0,94 / 427), ce qui la valide.

**Aussi corrigé.** `$VIX: possibly delisted` à chaque build : `VIX` est notre nom de base, pas un
ticker Yahoo (un indice y porte toujours un `^`). Le vrai risque n'était pas le bruit mais la
COLLISION — le jour où un titre coté s'appelle `DJI`, on télécharge un small-cap et on le lit
comme le Dow, en silence.

**Fait** : #364 et #365 mergés ; `packages/portfolio/fragilite` (22 tests), `_taille` à risque
constant (8 tests), `scripts/sizing_lab.py`, risque 0,5 % en production. Suite complète **1 669
verts** sur la machine de Thierry.
**Bloqué** : rien. **Suite** : mesurer les 5 modules SHADOW avant tout câblage ; le seuil de
promotion à +0,05 reste inatteignable avec 11 ans (plancher ~±0,12).

## Session 2026-09-01 — Un NaN est un incident de données, et le garde tombait sur le type qu'il protégeait

**Le fait.** La CI est passée du vert au rouge sur un code **identique** :
`assert nan <= nan`, `assert nan > 0`. Le re-run est repassé vert sans changer une ligne —
c'est la définition d'un défaut latent, pas d'un test fragile.

**L'amplification, et c'est elle qui rend le défaut sérieux.** `stress.mc_projection` tire les
rendements futurs **avec remise** dans le vivier observé. Un seul point non fini parmi 2760
apparaît donc dans la quasi-totalité des 1000 trajectoires, et `cumprod` le propage jusqu'au
bout : les cinq percentiles sortaient tous à `nan`. **Un point sur 2760 suffisait.**

**Pourquoi ce n'était pas qu'un test cassé.** Aujourd'hui ça casse un test, donc on le voit.
Demain ça publie un `sharpe: nan` que le front affiche « — » sans que personne ne sache qu'une
donnée manquait. **Une métrique absente est un problème visible ; une métrique fausse ne l'est
pas.**

**La règle posée** (`packages/portfolio/integrite`) : on ne remplace jamais un NaN par une
valeur inventée — ni 0, ni la moyenne, ni le dernier cours. On le **compte**, on le **dit**, on
calcule sur ce qui existe. Deux traitements, et la distinction est de fond : une **courbe
d'equity** se tronque au premier trou (après un trou la capitalisation est rompue ; recoller
fabriquerait un rendement qui n'a jamais existé, celui qui enjambe le trou) ; un **vivier de
rendements** se filtre (un rendement inobservable n'appartient simplement pas à l'échantillon
dans lequel on tire). Une courbe est une *séquence*, un vivier est un *ensemble*.

**Puis le garde est tombé sur exactement ce qu'il protégeait.** Première version : 9 tests
rouges. `serie or []` teste la **vérité de l'objet** ; sur un `np.ndarray` de plus d'un élément
Python lève « truth value ambiguous » *avant* toute analyse. Or `returns_from_equity` renvoie un
ndarray que `snapshot.py` passe directement à `mc_projection`. J'avais écrit un garde d'intégrité
qui refusait le type réel de la donnée qu'il devait garder.

**Le second coût, plus instructif que le premier.** La suite est passée de 7 à **38 minutes**.
`_snap()` est mémoïsé par `lru_cache`, mais **`lru_cache` ne mémorise pas une exception** :
chaque test reconstruisait le snapshot entier. Une exception dans une fonction cachée ne coûte
pas un test, elle coûte N constructions. Vérifié dans les deux sens : 9 rouges en 38m32, puis
9 verts en 4m19 en local et 7m34 en CI.

**Règle de méthode retenue.** Sur une séquence, le seul test permis est `is None`. Toute autre
forme de vérité (`if not x`, `x or []`) est un piège dès qu'un ndarray peut arriver — et dans ce
dépôt il arrive presque toujours. Les 5 modules SHADOW ont été relus pour le même motif : seul
`ddm.py` teste une vérité de séquence, sur un `tuple` par contrat. Rien à corriger.

**Fait** : #364 mergé (24 tests sur `integrite`, dont 5 vérifiés **rouges sur le code d'avant**
en remettant l'ancien fichier en place plutôt qu'en le supposant). CI verte.
**Bloqué** : rien. **Suite** : mesurer chacun des 5 modules SHADOW avant tout câblage
production ; le seuil de promotion à +0,05 reste inatteignable avec 11 ans (plancher ~±0,12).

## Session 2026-08-31 (22) — 53,6 % de CAGR : la troisième occurrence du même défaut

**Le chiffre qui a déclenché l'enquête.** `make index-core` affichait, pour le cœur momentum
sectoriel : **CAGR 53,6 %, rendement total 8908 %, Sharpe 1,29**. Un résultat qui, s'il était
réel, rendrait inutile tout le reste du système — donc le signe qu'on attaque, pas qu'on célèbre.

**Cause trouvée en lisant trente lignes.** `sector_momentum.py` importait `fenetre_commune` :

```python
syms, L, panel_diag = fenetre_commune(data, syms)      # empilement POSITIONNEL
closes = {s: np.asarray([b.close for b in data[s]][-L:], float) for s in syms}
ref = max(syms, key=lambda s: len(data[s]))
dts  = [b.ts.isoformat() for b in data[ref]][-L:]      # calendrier d'UNE SEULE série
```

Les L dernières barres de chaque titre, superposées, avec un calendrier pris sur la série la
plus longue. **Un titre radié en 2018 verse ses cours de 2018 dans des colonnes étiquetées
2026.** Le classement `closes[s][t] / closes[s][t - lookback] - 1` comparait donc des rendements
calculés sur des **périodes calendaires différentes** au sein d'un même secteur.

Le preset avait été migré en #341, la production en #347. **Ce cœur ne l'avait jamais été.**
Troisième occurrence, troisième module, même défaut.

**Deux pièges que la migration seule aurait ouverts**, et c'est le vrai enseignement :

1. `aligner_par_date` initialise sa matrice à `np.nan` — les trous sont légitimes. Or `_sma`
   utilisait `np.cumsum`, qui **propage un NaN à l'infini** : un seul jour manquant rendait la
   MM50 NaN pour tout le reste, le filtre `cours > MM50` devenait faux à jamais, et le titre
   était exclu **en silence**. `_sma` somme désormais les points valides et divise par LEUR
   NOMBRE.
2. La moyenne des rendements du jour rendait NaN dès qu'une ligne détenue était radiée, et
   l'equity restait NaN jusqu'au bout. **Attrapé par mon propre test**, pas par relecture.

**Biais résiduel, écrit plutôt que masqué.** Retirer la ligne radiée de la moyenne revient à
répartir son poids sur les survivantes le jour même, donc à ÉCHAPPER à la perte de radiation.
C'est optimiste. Le traitement exact demande les rendements de radiation
(`data/delisted.csv`) et n'est pas fait : le module reste INDICATIF.

**Le sweep QQQ, lui, a rendu son verdict** (garde-fou livré en #362) :

```
Référence = 50% · seuil détectable ±0.27
    0% : ΔSharpe -0.24 (p=0.159)    75% : +0.02 (p=0.765)
   25% : ΔSharpe -0.07 (p=0.344)   100% : +0.01 (p=0.918)
→ AUCUN ratio n'est distinguable. Le « meilleur Sharpe » (75%) est du bruit de sélection.
```

La question « faut-il plus ou moins de QQQ ? » est donc **close** : on garde 50 %. Ce qui bouge
vraiment n'est pas le Sharpe (plat) mais le couple CAGR 8,5→21,1 % / maxDD −24,4→−35,1 %. C'est
une préférence, pas une statistique.

**Tests.** 6 neufs (1505 verts). Ruff sur le module : 20 → 11.

---

## Session 2026-08-30 — S&P/Nasdaq plats : la série la plus longue était périmée

**Observation réelle.** Sur le dashboard comptes vs indices (17/06→29/08), S&P et Nasdaq bougeaient
quelques jours puis devenaient parfaitement horizontaux, alors que le tableau annonçait des données
100 % réelles. Ce n'était pas le marché : `_index_closes` choisissait la série la plus longue sans
regarder sa dernière date. Une longue base arrêtée fin juin gagnait contre une base plus courte mais
fraîche, puis `_account_compare` forward-fillait sa dernière valeur jusqu'à fin août.

**Correctif.** `packages/data/index_history.py` fusionne le même alias entre bases par date, refuse de
mélanger indice et ETF (échelles différentes), exige 250 barres et privilégie un alias frais (≤7 j).
Si toutes les bases sont périmées, yfinance tente de compléter ; si cela échoue, l'indice est exclu
de la comparaison réelle au lieu d'être aplati. `_account_compare` reçoit désormais les dates propres
de chaque indice, et non le calendrier positionnel du plus long actif de l'univers.

**Compteurs/preuves.** Tests dédiés : fraîcheur > longueur, fusion sans plateau, stale explicite et
alignement exact des fluctuations S&P/Nasdaq. Le texte UI dit désormais « indice ou ETF proxy frais »
et documente l'exclusion d'un benchmark périmé.

## Session 2026-08-29 (4) — Gemini connecté mais génération 404 : transport réellement testé

**Bug réel.** `/models` répondait, donc le voyant passait au vert, mais la couche OpenAI-compatible
de Gemini renvoyait 404 sur `/chat/completions`. Le diagnostic testait le catalogue, pas le transport
de génération. Le chat affichait en plus « UNCALIBRATED / rejeté » pour une panne réseau, confondant
qualité de données et connectivité.

**Correctif.** Le client tente toujours le protocole compatible, puis, uniquement pour Google et un
404, bascule sur `models/{model}:generateContent` avec `x-goog-api-key`. Le corps d'erreur fournisseur
est désormais remonté au lieu du seul statut HTTP. Le front distingue `CONNEXION ÉCHOUÉE` d'une
réponse non grounded. Tests : deux transports simulés, clé jamais placée dans l'URL.

**Utilité quant.** Les scopes overview/portfolio publient maintenant une comparaison déterministe des
rendements de bout en bout du portefeuille et des benchmarks, ainsi que les KPIs des comptes réels
sur leur fenêtre commune lorsqu'ils existent. Une question « pourquoi moins que le Nasdaq ? » reçoit
donc enfin les faits nécessaires ; sinon la réponse doit rester `UNCALIBRATED`.

## Session 2026-08-29 (3) — L'IA connectée devient un copilote read-only réellement utile

**Avant.** Le voyant vert ne débloquait qu'un commentaire one-shot à prompt fixe. Aucun champ de
question, aucune consultation du vault ou des sections du terminal, et la route ne passait pas sa
sortie dans le garde numérique pourtant déjà disponible.

**Livré.** Drawer global « Interroger » sur toutes les pages, suggestions et scope contextuels,
conversation éphémère, réglages fournisseur accessibles dans le chat et opt-in séparé avant d'envoyer
les positions détaillées. `POST /api/ai/chat` ne donne accès qu'à six builders read-only bornés
(overview/portfolio/risk/screener/research/vault), avec citations `as_of`; le vault réutilise le RAG
extractif existant. Les nombres non présents dans le contexte font rejeter toute la réponse.

**Sécurité et observabilité.** Aucun outil SQL/shell/fichier arbitraire, aucun import execution/risk,
aucune action broker. `GET /api/ai/metrics` publie demandes, rejets et taux effectif. Le texte de
confidentialité distingue désormais modèle local et cloud : un fournisseur cloud reçoit forcément
la clé et le contexte sélectionné par HTTPS, même si Quant Terminal ne les persiste pas.

## Session 2026-08-29 (2) — Fondations causales plutôt qu'un big-bang invérifiable

**Livré.** Kalman strictement avant avec calibration MLE limitée au train ; embargo de CV désormais
borné inférieurement par l'horizon triple-barrière ; sélection FFD fold par fold ; sizing conforme
qui ne peut que réduire et tombe à zéro au-delà de l'incertitude admise ; projection ERC/Min-Var/HRP
sous bornes du mandat, avec veto explicite si le problème est infaisable.

**Preuves.** Les tests modifient tout le futur après la coupure d'apprentissage et vérifient que la
calibration et les états du préfixe sont invariants. Les trois optimiseurs sont testés contre les
mêmes hard constraints. Le dimensionnement conforme est monotone en risque.

**Périmètre honnête.** Ces briques ferment des contrats mathématiques, mais ne sont pas présentées
comme un câblage des six chantiers. Le remplacement de DualMarket, le benchmark `mkt` exogène, les
corporate actions FIFO, Gold/ADV, PIT DuckDB, snapshot async et états UI restent ouverts. Les brancher
sans schéma de données réel ni benchmark aurait créé des fallbacks ou calibrations inventés, interdits
par le mandat du dépôt.

## Session 2026-08-29 — Cartographie complète pour passation à un agent IA

**Demande.** Produire une explication transmissible du fonctionnement et du contenu du dépôt afin
qu'un agent externe puisse identifier des améliorations sans réinventer l'architecture ni confondre
présence d'un module, câblage production et preuve d'alpha.

**Livré.** `docs/AI_CODEBASE_MAP.md` cartographie les frontières, les packages, les trois flux
recherche/terminal/paper, les commandes, l'état honnête et la dette connue. Le document impose aussi
un format d'audit en dix points : preuve dans le dépôt, causalité/PIT, protocole anti-overfit,
frictions/capacité, observabilité des garde-fous et red-team CRO.

**Décision.** Aucun nouvel ADR : il s'agit d'une synthèse des contrats et décisions existants, pas
d'un changement d'architecture. `vault/03_TODO.md` reste la roadmap unique.

## Session 2026-08-27 (21) — `régime = 0` élucidé : la porte lisait sa propre sélection

**Le run de production a tranché**, et la ligne de diagnostic ajoutée le matin a suffi :

```
    score qualité      ⚠️  0 scoré(s) → repli MOMENTUM (prix seuls, aligné par date)
    panel aligné       12 noms × 1329 dates communes
    régime (détail)    DD -23.8% (pic il y a 45 barres) · niveau 316.45 vs MM200 208.75
                       · pente 20j +15.5%
    exposition brute   DD-target 0.143 × régime 0.000 × ampleur 1.000  =  0.0000
```

**La contradiction est désormais LISIBLE, et elle désigne la cause.** L'indice est 52 %
AU-DESSUS de sa MM200 (316,45 vs 208,75) et monte de +15,5 % sur 20 jours — et il affiche
simultanément un drawdown de −23,8 %. Les deux sont vrais **de ce panier-là**, et c'est
précisément le problème : `mkt = A.mean(axis=0)` est la moyenne des 12 titres SÉLECTIONNÉS,
pas un indice de marché. Sans score qualité, le repli prend le top-12 du momentum à 12 mois,
c'est-à-dire **par construction les douze titres les plus extrêmes de l'univers**. Un tel
panier est presque toujours à plus de 15 % sous son pic tout en étant loin au-dessus de sa
MM200. La porte de régime s'annulait donc en lisant sa propre sélection.

**Le correctif expérimental, décisif.** Même capital, même minute, `QUANT_LIVE_LITE=0` :

| | mode léger | mode complet |
|---|---|---|
| score qualité | 0 scoré → repli momentum | scoré |
| univers | 12 noms extrêmes | THC, UNP, PATH, TGT, STT, TMO, T… |
| satellite actions | **VIDE** (régime 0,000) | **75 720 $ alloués** |
| durée | ~30 s | 5 min 38 |

**Décision.** `fundamentals` sort de `_LITE_SKIP`. Ce n'était pas une section « non
essentielle » : elle **décide de l'univers**. Coût assumé (snapshot plus long, mais le cron
tourne sans personne devant l'écran) et surtout **dégradation gracieuse** : `safe_section`
isole toute panne, un échec de `fundamentals` fait retomber sur le momentum — le
comportement d'avant. Le pire cas du correctif est l'état antérieur. Échappatoire :
`QUANT_LIVE_LITE_SKIP_FUNDAMENTALS=1`.

**Un second bug, trouvé dans la même sortie et sans rapport.**

```
AAVEUSD  Alpaca  cible 0$  détenu 2541$  Δ -2541$   ⏸ REPORTÉ — hors séance
```

Une liquidation de CRYPTO bloquée par le calendrier des ACTIONS. Chaîne : les cibles portent
« AAVE/USD », les positions rendues par Alpaca portent « AAVEUSD » sans séparateur ; une
position à solder n'a pas de ligne cible, donc `_broker_targets` la crée avec `{"o": None}` ;
le code lisait `(o or {}).get("asset_class") or "equity"`. **Toute liquidation hors-univers
était donc classée « action ».** Et `routing._is_crypto` ne reconnaissait pas non plus le
format sans slash. Gravité : c'est un DÉSENGAGEMENT — le portail de risque ne bloque jamais
une réduction d'exposition, le calendrier ne doit pas le faire par méprise ; et rien ne met
les reports en file d'attente, donc il se serait reproduit chaque nuit. Corrigé par
`routing.classe_actif`, qui infère la classe du format position, base contrainte à la
whitelist Alpaca pour éviter qu'une action au ticker en « USD » devienne crypto.

**Exécution réelle.** `make live-go` a envoyé 7 ordres (allègements crypto vers les cibles).
Equity Alpaca 101 735 $.

**Ce que je n'ai PAS corrigé, délibérément.** `mkt` reste (a) la moyenne du panier
sélectionné et non un indice de marché, (b) une moyenne de PRIX BRUTS — un titre à 500 $
y pèse 25 fois un titre à 20 $. Les deux sont des défauts réels. Les corriger change ce que
la porte de régime MESURE, donc les résultats de backtest : cela demande une mesure au labo,
pas un correctif à l'aveugle. Après trois bugs livrés en deux jours faute de mesure, la leçon
est prise. Ouvert en P1.

**Tests.** 17 neufs (1456 verts). Ruff : `safe_section` 3→0, `routing` 16→11, aucun ajout.

---

## Note 2026-08-27 (20) — Le rebalancement automatique sera crypto, et c'est dit

**Contrainte matérielle.** La machine n'est allumée que vers 22h. Or la clôture NYSE tombe
à **22h00 pile** heure de Paris — vérifié en exécutant `market_calendar.is_open` plutôt qu'en
le supposant : à 21h55 les actions sont ouvertes, à 22h00 elles sont fermées. Un cron à 22h05
ne peut donc jamais remplir un ordre actions.

**Décision.** Cron à 22h05 quand même : 8 des 9 positions sont du crypto, qui tourne 24/7.
L'automatisation garde l'essentiel, les actions restent manuelles. L'heure du script était codée
en dur à 16h05 ; elle est désormais configurable (`QUANT_LIVE_HOUR` / `QUANT_LIVE_MIN`).

**Le défaut trouvé en écrivant ce correctif.** Le récapitulatif des ordres reportés affirmait
« Pas une erreur : ils partiront à la prochaine séance. » C'est **faux** dès que le planning est
hors séance : la prochaine exécution sera elle aussi hors séance, et rien ne met les ordres en
file d'attente. Un message rassurant et faux est pire que pas de message — il aurait laissé
croire à un rattrapage qui n'arrive jamais. Le récapitulatif ventile maintenant par classe
d'actifs et donne les deux issues actionnables.

**Deux bugs de forme au passage.** `.replace(",", " ")` s'appliquait à toute la chaîne
concaténée, donc mangeait aussi la virgule de ponctuation (`)  2 450$` au lieu de `), 2 450$`).
Présent aussi dans le bloc des ordres REFUSÉS — corrigé aux deux endroits. Et un zéro codé en
dur dans `${HOUR}h0${MIN}` rendait « 20h030 » pour MIN=30.

**Piège de calendrier documenté.** Entre le changement d'heure européen (dernier dimanche
d'octobre) et américain (premier dimanche de novembre), l'écart Paris↔New York passe à 5 h
pendant une semaine : la clôture tombe alors à 21h00 heure de Paris. D'où le conseil d'éviter
21h30-22h00 si le cron devait être avancé.

**Tests.** 4 nouveaux (1435 verts). Le plus utile vérifie que le message ne promet PAS un envoi
automatique — c'est-à-dire qu'il teste l'absence de l'ancienne affirmation.

---

## Session 2026-08-27 (19) — La stratégie devient une donnée, et le moteur cesse d'être influençable

**Point de départ.** L'utilisateur propose une architecture : le LLM produit une *définition de
stratégie*, pas des ordres ; un cœur déterministe traduit cette définition en signaux ; le moteur
est indépendant du LLM « pour la fiabilité et l'audit » ; et un data layer couvre tout, jusqu'aux
données alternatives.

**Ce qui est juste, et validé par nos propres bugs.** La séparation moteur/LLM est le point le
plus important, et les trois divergences production/backtest corrigées en 24 h (#347, #352, #353)
ont TOUTES la même cause racine — qui n'est aucune des trois : aucun artefact ne disait « voici la
stratégie ». Elle vivait dans des valeurs par défaut, des variables d'environnement et des effets
de bord. La proposition les aurait rendues **impossibles**, pas seulement détectables.

**Ce que j'ai contesté.** « Demande un Sharpe à 2,3 » est une spécification par le résultat. Le
dépôt possède le chiffre qui la réfute : 126 pas ne résolvent que ~+0,14 de Sharpe (ADR-0039), donc
le système ne distingue même pas 1,35 de 1,49. Et une boucle qui garde les candidats atteignant la
cible fait du p-hacking à l'échelle — le maximum de N tirages bruités croît en √(2 ln N). Le refus
est désormais STRUCTUREL : le schéma de mandat rejette les cibles de résultat en entrée.
Démonstration mesurée : le meilleur de 200 mandats tirés d'un **bruit pur** affiche un Sharpe de
0,157 contre 0,168 atteignable par pur hasard — correctement rejeté.

**Livré.** `packages/mandate` (canonical / spec / purete, 448 l.), `packages/research/fdr.py`,
`config/mandats/preset_multi_actifs.json`, 50 tests. ADR-0048/0049/0050, diagramme mis à jour.

**Mon erreur de la session, et elle est structurelle.** J'ai écrit un `hypothesis_ledger` complet —
PSR, DSR, registre d'essais — avant de découvrir que `portfolio/psr.py` et `research/ledger.py`
faisaient déjà tout cela, **et mieux** : l'existant gère le piège de périodicité annualisé
vs par-période (audit du 20/08) que je n'avais même pas identifié. J'ai supprimé mon doublon et ne
gardé que Benjamini-Hochberg, seule brique réellement absente (vérifiée par recherche, et P0 ouvert
du TODO). J'ai conçu avant de lire, dans un dépôt de 28 paquets. La règle en tire une ligne dans
l'ADR-0050.

**Deuxième erreur, attrapée par un test.** Mon test sur la croissance du seuil de hasard affirmait
« +40 % de 100 à 10 000 essais » d'après l'asymptotique √(2 ln n). La formule exacte donne +53 % —
l'asymptotique n'est pas serrée pour n ≲ 10⁵. Corrigé avec la vraie valeur, pas en élargissant la
borne.

**Non livré, délibérément.** Le harnais de pureté n'est PAS branché sur le preset. C'est une
migration qui touche du code de production stabilisé il y a quelques heures ; elle mérite sa propre
PR et son propre contrôle d'équivalence.

**Sur le data layer.** Bonne intuition, mais deux avertissements écrits au TODO : futures et options
ne sont pas « plus de lignes » (expiration, roll, structure par terme — autre modèle de données), et
les données alternatives sont précisément là où la règle point-in-time se fait violer. Le dépôt a
déjà la bonne règle formalisée dans `config/macro_publication_lags.yaml` : *feature at t may only
use vintages with release_date <= t*.

---

## Incident 2026-08-27 — Le passage du dépôt en PRIVÉ a cassé deux workflows en silence

**Symptôme.** `gitleaks` rouge sur toutes les PR. J'allais le classer « rouge pré-existant,
pas mon diff » et passer à autre chose — la question de l'utilisateur (« est-ce parce que
j'ai rendu le dépôt privé ? ») a ouvert la vraie piste.

**Le motif qui tranche.** Sur `gitleaks`, l'événement `push` sur `main` est resté VERT tout
du long, seul `pull_request` échoue — 7 fois d'affilée depuis le 26/08 au matin. Sur un push,
gitleaks scanne en local sans toucher à l'API ; sur une PR, il appelle
`GET /pulls/{n}/commits`. Le workflow ne déclarait que `contents: read` : sur un dépôt PUBLIC
cet endpoint sert de la donnée publique et un jeton sans le scope peut la lire, en PRIVÉ il
l'exige. D'où `403 Resource not accessible by integration`. Correctif : `pull-requests: read`.

**La conséquence qu'on n'avait pas vue, et qui compte davantage.** `pages.yml` échoue depuis
exactement la même fenêtre (dernier succès 05:57, contre 05:32 pour gitleaks). Le job `build`
réussit, c'est `deploy` qui rend `404 — Ensure GitHub Pages has been enabled` : GitHub
DÉSACTIVE Pages quand un dépôt privé est sur un plan Free. **La PWA publique était figée
depuis 24 h et rien ne le disait.** Décision de l'utilisateur : repasser le dépôt en public.

**Contrôle avant re-publication.** Aucun fichier sensible suivi, aucun motif de secret dans le
diff de la fenêtre privée, `.env.example` sans valeur sensible. Surtout : gitleaks scanne
l'historique COMPLET (`fetch-depth: 0`) à chaque push sur `main` et tous ces runs sont verts,
le dernier le 26/08 à 19:11 — `main` n'a jamais cessé d'être couvert.

**Leçon.** Un changement de VISIBILITÉ est un changement d'INFRASTRUCTURE. Il modifie
silencieusement les permissions implicites du jeton d'Actions et les droits Pages, sans
toucher une ligne de code ni produire d'alerte. Deux workflows sont morts au même moment sans
que rien ne le signale. Corollaire : « rouge avant mon diff » n'est pas une conclusion, c'est
le début d'une question.

---

## Session 2026-08-27 (18) — L'univers de production était classé sur le momentum de 2015

**Le fait mesuré.** Après le repli momentum de la session 17, le run de production a rendu :

```
    exposition brute   DD-target 0.515 × régime 0.000 × ampleur 1.000  =  0.0000
    ⛔ ARRÊT : exposition brute NULLE — porte(s) à zéro : régime
```

**Une contradiction, donc un défaut.** `ampleur = 1,000` dit que 100 % de l'univers est
au-dessus de sa MM200. `régime = 0,000` ne peut venir que du drawdown DUR (> 15 %) du même
indice `mkt`. Les deux portes lisent le MÊME panier : elles ne peuvent pas décrire deux
marchés opposés. Une contradiction interne est un fait, pas une opinion — contrairement aux
trois hypothèses de la veille, celle-ci n'avait pas besoin d'être devinée.

**La cause.** `_price_universe` mesure le momentum au DÉBUT de la fenêtre commune,
`s0 = max(lookback, 50) = 120`. Sur 2762 barres, c'est le momentum de **début 2015**, puis
figé. Ce point est CORRECT en backtest — le mesurer à la fin reviendrait à choisir l'univers
en connaissant l'avenir, le biais #2 que le dépôt a fermé — et indéfendable en production, où
« aujourd'hui » EST le dernier point connu. Des titres forts en 2015 et effondrés depuis
restaient sélectionnés ; l'indice de leur panier affichait un drawdown > 15 % ; la porte de
régime mettait l'exposition à zéro.

**Correctif.** `_price_universe(..., au_dernier_point=True)` pour le seul chemin de
production. Le défaut du backtest ne bouge pas, et un test le verrouille explicitement.

**Un second défaut, dans le correctif lui-même.** `momentum_rank` gardait
`if len(M[s]) > s0`. On lit l'indice `s0 - 1` : une série de LONGUEUR `s0` est parfaitement
lisible. Sans conséquence tant que `s0` valait 120, mais au dernier point `s0 == len(série)`
et le garde excluait **tous** les titres → `sel` vide → `len(sel) < 5` → retour de
`list(syms)[:top_k]`, c'est-à-dire **l'ordre du dictionnaire**. Le repli momentum se serait
donc dégradé en silence exactement en ce qu'il devait remplacer. Garde passé à `>= s0`.

**Ma vérification de la veille lisait ce repli en croyant lire un succès.** Le script
synthétique renvoyait `ACTUEL00, ACTUEL01, ACTUEL02…` — l'ordre d'insertion, pas un
classement. Je l'ai pris pour une preuve. Le tri par ordre alphabétique d'`aligner_par_date`
a ensuite rendu VERT un premier test qui ne mesurait rien : « ACTUEL » précède « VIEUX »,
donc le repli arbitraire tombait juste par hasard. Les familles sont désormais nommées pour
que l'ordre du dictionnaire ET l'ordre alphabétique favorisent tous deux les titres périmés :
seul un vrai classement momentum peut passer.

**Le diagnostic chiffre maintenant la porte de régime** (`regime_detail`) : drawdown, recul du
pic, niveau vs MM200, pente 20 j. Trois hypothèses fausses ont été émises faute de cette
ligne ; elle n'entre dans aucun calcul.

**Tests & CI.** 1381 verts. Cinq nouveaux tests, vérifiés rouges sans chacun des deux
correctifs pris séparément. Aucune nouvelle alerte ruff dans `packages/` et `apps/`.

**Ce que ce correctif ne prouve PAS.** Il ferme un défaut sans ambiguïté sur ses propres
termes. Que `régime = 0` disparaisse réellement en production doit venir du prochain run de
l'utilisateur, pas de ma prédiction : je me suis trompé trois fois sur cette question et j'ai
livré deux bogues dans mon propre outil de diagnostic.

---

## Session 2026-08-26 (17) — La cause, enfin : les portes mesuraient un panier tiré au hasard

**Le diagnostic a parlé.** Après deux correctifs de l'outil lui-même (garde-fou bogué, puis
mauvais chemin de lecture), le run de production a donné le fait :

```
    éligibles          633 titres (> 200 barres)
    score qualité      ⚠️  0 titre(s) scoré(s) → REPLI sur les 12 premiers, ordre ARBITRAIRE
    panel aligné       12 noms × 1907 dates communes
    exposition brute   DD-target 0.255 × régime 0.000 × ampleur 0.000  =  0.0000
    ⛔ ARRÊT : exposition brute NULLE — porte(s) à zéro : régime, ampleur
```

**La chaîne causale, complète.** `make live` tourne en mode LÉGER, qui coupe la section
`fundamentals` : `quality` est donc **toujours vide à l'exécution**. Le repli prenait alors
les 12 premiers symboles du dictionnaire. Et `mkt = A.mean(axis=0)` — l'indice de marché que
lisent les portes de régime et d'ampleur — était la moyenne de **ces 12 noms arbitraires**.

Les portes concluaient « marché en chute de plus de 15 %, aucun titre au-dessus de sa MM200 »
et mettaient l'exposition brute à zéro. **Le satellite actions n'était pas vide par décision
de risque : il était vide parce qu'on mesurait le risque d'un panier tiré au hasard.**

Toutes les exécutions de production passaient par ce repli, depuis toujours.

**Correctif.** Le repli utilise désormais `_price_universe` — le MÊME classement momentum que
le backtest, aligné par date, sans fondamentaux. Il fonctionne quelle que soit la raison de
l'absence de scores (mode léger, réseau coupé, quota d'API) au lieu de dépendre d'un ordre de
dictionnaire. Vérifié sur un panier où les 12 premiers du dict sont les PIRES titres : l'ancien
repli les retenait et fermait les portes (gross 0,00) ; le nouveau retient les meilleurs et
l'exposition remonte à 1,00.

**Mon hypothèse n°3 était juste, et je l'avais déclarée réfutée à tort.** « Le mode léger coupe
`fundamentals` » était exact. Je l'ai abandonnée parce que la mesure censée la tester lisait
`snap["preset_allocation"]` à la racine, où cette clé n'existe pas — elle est sous `dashboard`.
La réfutation était fausse, pas l'hypothèse. C'est la leçon la plus coûteuse de la journée :
**j'ai écarté une bonne piste sur la foi d'une mesure que je n'avais pas validée.**

**Bilan de l'enquête** : trois hypothèses annoncées (une juste, écartée à tort), deux défauts
dans mon propre outil de diagnostic, un défaut de fond trouvé. Toutes les corrections sont
venues de la mesure de l'utilisateur, aucune de ma lecture du code.

**Tests & CI.** 1376 verts. Deux tests reproduisent le défaut de production : rouges sans le
correctif, verts avec.

**Reste à décider.** Faut-il aussi retirer `fundamentals` de `_LITE_SKIP` ? Le repli momentum
rend la production correcte sans cela, mais l'univers de production reste sélectionné par
momentum plutôt que par qualité — ce n'est pas ce que le design prévoyait. Arbitrage entre
justesse du signal et durée du snapshot, à trancher explicitement.

---

## Session 2026-08-26 (16) — Trois hypothèses fausses : arrêter de deviner, instrumenter

**Le fait.** Compte paper : cœur QQQ, huit lignes crypto, **zéro action du satellite**. Sur ce
seul symptôme, j'ai proposé successivement trois causes, et **les trois étaient fausses** :

1. **Plancher de ligne à 1000 $** — réfuté par le capital réel (100 302 $, très au-dessus du
   seuil de 18 519 $ que j'avais calculé).
2. **Horaires de marché** (actions en `TimeInForce.DAY` hors séance) — plausible et vérifié dans
   le code, mais `crontab -l` a montré qu'il n'y a **aucun cron** : rien ne tourne
   automatiquement. Le garde-fou livré reste juste ; il ne répondait pas à la question.
3. **Mode léger coupant `fundamentals`** — réfuté par la mesure : le mode COMPLET donne
   **0 cible**, le mode léger en donne 8. L'inverse de ma prédiction.

**Le vrai enseignement n'est aucune de ces trois causes.** C'est qu'aucune trace ne disait où la
chaîne s'arrêtait. `preset_latest_weights` renvoie `{}` pour **au moins six raisons** et n'en
distingue aucune : trop peu d'éligibles, aucun score qualité (repli silencieux sur un univers
ARBITRAIRE), panel trop court après intersection, fenêtre de covariance insuffisante, exposition
brute annulée par une porte, ou concentration qui balaie tout. Trois allers-retours avec
l'utilisateur pour un diagnostic qu'une ligne de journal aurait donné immédiatement.

**Livré : `packages/backtest/preset_diag.py`.** Journal des étages, publié dans le snapshot
(`preset_diagnostic`) et affiché par `run_live` **quand le satellite actions est vide**. Chaque
porte publie son multiplicateur, et le PREMIER étage bloquant est nommé comme la cause.

Le repli le plus dangereux est désormais tracé : `len(q) >= 5` bascule sur `syms[:top_k]` — un
univers dans l'ordre arbitraire du dictionnaire — **sans un mot**. C'est un incident, pas un
défaut acceptable, et il le dit maintenant.

**Aucun chiffre ne change.** Vérifié explicitement : `preset_latest_weights` délègue à
`preset_latest_weights_explique` et renvoie les mêmes poids, testé sur 5 tirages.

**Ce qui reste ouvert, et c'est le point.** Je ne sais toujours PAS pourquoi ton satellite est
vide. La différence entre tes deux mesures porte sur DEUX variables à la fois (mode léger vs
complet, et clé `preset_allocation` vs `live.target_orders`) : aucune conclusion n'est possible.
Le diagnostic livré donnera la réponse au prochain run, sans nouvelle hypothèse.

**Tests & CI.** 1368 verts (+12), dont 10 pour le diagnostic. ruff propre sur le neuf ;
`preset_weights` passe de 22 à 14 E501.

---

## Session 2026-08-26 (15) — Fermer le chemin d'exécution : l'issue de l'ordre, et l'écran qui ment

Suite directe de (14). Deux trous du même chemin, tous deux du genre « le système affirme
quelque chose qui n'arrivera pas ».

**L'ordre envoyé n'était pas l'ordre exécuté.** `run_live` faisait `sent += 1` dès que l'appel
courtier ne levait pas d'exception, sans jamais lire la RÉPONSE. Or Alpaca accepte un ordre puis
peut le rejeter : le compteur annonçait « 12 ordres envoyés » là où douze avaient été refusés.

`packages/execution/order_outcome.py` classe en **quatre** issues, pas deux. « Envoyé/échoué »
est trop grossier pour un ordre au marché : `REJETE` (ne se remplira jamais — c'était l'angle
mort), `REMPLI`, `EN_COURS` (accepté, remplissage non confirmé — le cas NORMAL à la soumission,
exiger « rempli » ici crierait au loup à chaque ordre), `INCONNU`. Un rejet ne compte plus comme
envoyé et n'est plus journalisé comme une ouverture.

**Deux régressions que j'allais introduire, attrapées avant.** Bitmart et Binance renvoient
`OrderStatus.SUBMITTED` (vocabulaire interne) : l'oublier aurait classé INCONNU tous les ordres
crypto, donc cessé de les compter. Et `AlpacaBroker.close_position` renvoie un **booléen**, pas
un ordre : sans ce cas, toute liquidation devenait INCONNUE. Le correctif aurait créé le défaut
inverse de celui qu'il corrige. Vérifié contre les quatre courtiers du dépôt avant d'activer.

**Un test a démenti ma propre docstring.** `classer()` affirmait « ne lève JAMAIS » ; un objet
exposant `status` en propriété qui lève traversait. La garantie est maintenant tenue par un
`try`, pas par la prudence supposée du code en amont.

**Et un bug de câblage qui s'est déguisé en panne courtier.** Mon import d'`order_outcome`
n'avait pas atterri (le `replace` ne correspondait plus après une édition antérieure, et je
n'avais pas mis d'`assert` dessus). Le `NameError` est tombé dans le `except` de l'envoi et
s'est affiché « ÉCHEC après retries » — exactement le masquage qu'on cherche à supprimer.

**L'écran de positions promettait des achats impossibles.** La page badgeait « à acheter » toute
cible non détenue sans jamais consulter le plancher de ligne que `decider()` applique. Même
famille que le satellite vide : l'écran affirme une action qui n'aura pas lieu. Désormais
« bloqué · sous le plancher » avec le montant manquant, et un bandeau quand AUCUNE cible ne peut
partir — le cas qui a mené au diagnostic. Le plancher vient de l'API, jamais recodé côté front.

**Tests & CI.** 1356 verts (+26). ruff propre sur tout le neuf ; `run_live` descend de 75 à 72
E501. TypeScript : 2 erreurs, les mêmes qu'avant (three.js, sans rapport).

**Reste ouvert.** Le rolling universe (aucune preuve qu'il aide), le câblage d'`impact.py`
(données ADV manquantes), le biais du survivant (liste de délistés à élargir) et surtout la
**fenêtre du labo** — tant qu'elle ne résout que ±0,14, aucun levier ne peut être départagé.

---

## Session 2026-08-26 (14) — Le satellite actions était vide, et personne ne le disait

**Le symptôme.** Compte paper : cœur QQQ 50 602 $ (50,4 %), huit lignes crypto 21 673 $
(21,6 %), cash 28 027 $ (27,9 %) — et **zéro action du satellite**. Les 28 % de cash étaient
exactement à la place de la part actions manquante.

**La cause, vérifiée.** `alpaca_broker.py:62` envoie les actions en `TimeInForce.DAY` sans
`extended_hours`, la crypto en `GTC` (24/7). Hors séance, une action ne PEUT pas se remplir.
Or **aucun contrôle d'horaires n'existait** — vérifié : zéro occurrence de `is_open`, `clock`
ou `market_open` dans `run_live`, `alpaca_broker` et `live_guards`. Un rebalancement lancé
depuis l'Europe tombe à 03 h à New York : la crypto passe, les actions jamais.

**Ce qui a rendu le défaut invisible est plus grave que le défaut.** L'erreur était tronquée à
40 caractères (`str(e)[:40]`) : un rejet de courtier devenait illisible. Et le code ne vérifie
jamais le statut de l'ordre après envoi — un ordre accepté puis rejeté est compté comme réussi.
Le satellite pouvait donc rester vide des semaines sans une ligne dans le journal.

**Livré.**
- `packages/execution/market_calendar.py` — F11 partiel, le strict nécessaire pour répondre
  « peut-on envoyer cet ordre maintenant ? » : XNYS 09:30-16:00 ET, week-ends, fériés, 24/7
  crypto. stdlib pure, sans réseau (un garde-fou ne doit pas dépendre d'un appel faillible).
  Table des fériés EXPLICITE, avec un test qui casse quand elle se périme — un garde-fou qui
  se périme en silence rassure sans protéger.
- `run_live` REPORTE les ordres hors séance au lieu de les envoyer dans le vide, avec un
  récapitulatif chiffré et le conseil de décaler le cron (séance = 15:30-22:00 CEST).
  Échappatoire explicite `QUANT_IGNORE_SESSION=1`.
- Erreur de courtier COMPLÈTE à l'écran (200 car.) et dans le journal structuré.

**Troisième défaut trouvé en chemin.** `preset_latest_weights` — la fonction qui pilote
`make live` — empilait les séries POSITIONNELLEMENT (`fenetre_commune`) alors que le backtest
était passé à l'alignement par date en #341. **Production et backtest ne mesuraient pas la
même chose.** Migré sur `aligner_sans_trous` (aligné par date ET sans NaN, comme le ledger).
Mesuré sur deux familles aux économies identiques ne différant que par leur calendrier :
rapport de poids par ligne **0,88 → 0,97** (neutre = 1,00), dispersion [0,63 ; 1,31] → [0,77 ; 1,16].

**Deux hypothèses à moi, réfutées en route**, et c'est le bon ordre des choses : le plancher de
1000 $ par ligne (faux — 100 302 $ d'equity, très au-dessus du seuil de 18 519 $ que j'avais
calculé), et le désalignement de calendrier comme cause du portefeuille (réel, mais l'effet
mesuré est trop faible et sans direction nette pour l'expliquer). Un premier test que j'avais
écrit était lui-même biaisé — qualité uniforme à 1,0, donc tri par ordre d'insertion : il
mesurait mon générateur, pas le système.

**Tests & CI.** 1330 verts (+18). Deux tests existants du portail de risque ont viré au rouge
sous le nouveau garde-fou — exactement leur rôle. Isolés par une fixture explicite ; le
calendrier a ses propres tests. ruff : aucune dette ajoutée (`run_live` passe même de 75 à 73).

**Reste ouvert.** Le statut de l'ordre n'est toujours pas relu après envoi : un ordre accepté
puis rejeté par le courtier reste compté comme réussi. C'est le prochain trou de ce chemin.

---

## Session 2026-08-26 (13) — Le labo promeut sous son propre plancher de détection

**Deux défauts que seule la vraie base pouvait montrer.** Le run du Mac a fait tomber deux
choses invisibles en CI et dans le conteneur distant (qui n'a aucune donnée de marché).

`fx.rate("TWD", "")` renvoyait **0,0314 au lieu de `None`** : `quote or "USD"` réécrit une chaîne
vide en « USD » (une chaîne vide est falsy), donc le garde-fou juste en dessous ne voyait jamais
le cas. L'appelant convertit des états financiers avec ce taux — un P/E et un DCF crédibles et
faux, sans alerte. **Le test était vert pour la MAUVAISE raison** : sans réseau, l'appel tombait
dans l'`except` et renvoyait `None` sans jamais exercer le défaut. Rendu hermétique (cache
pré-rempli), il est maintenant rouge partout sans le correctif.

`Équipondéré (même univers) −100,0 % / nan%` : la stratégie traite les radiations depuis #341
(`dernier_connu`), la ligne de **comparaison** n'avait jamais été migrée. Un seul titre radié
mettait toute la courbe à NaN. **Le preset se comparait donc à RIEN sans le dire** — pire qu'une
comparaison absente, parce qu'elle a l'air d'exister. Corrigé, et vérifié bit-à-bit identique sur
panel complet : le correctif ne mord que sur le cas cassé.

**Le vrai sujet : le labo promeut sous son plancher de détection.** Neuf leviers « rejetés » avec
des ΔSharpe de −0,01 à −0,12, présentés comme neuf verdicts distincts. Mais avec quelle précision ?
Personne ne le demandait — le gate compare des estimations ponctuelles à un seuil fixe.

Jobson-Korkie/Memmel sur Sharpe **appariés** (deux variantes tournent sur les mêmes dates,
ρ > 0,95 : les traiter comme indépendantes surestimerait massivement l'incertitude). Puissance
sur 126 pas :

| ΔSharpe **vrai** | détecté |
|---|---|
| +0,05 ← *seuil du gate* | **7,3 %** |
| +0,15 | 30,2 % |
| +0,32 | 85,1 % |

**Le seuil de +0,05 est trois fois sous ce que 126 pas résolvent (~+0,14, même à ρ = 0,99).** À ce
niveau, le taux de détection (7,3 %) dépasse à peine le taux de faux positifs (5 %) : promouvoir
ou rejeter est un tirage au sort.

Ça ne change aucun chiffre publié. Ça change ce qu'on a le droit de **conclure** : « aucun levier
ne bat la base » reste vrai, mais se lit « rien de distinguable sur cet échantillon », pas « ces
leviers sont mauvais ». La nuance décide s'il faut les abandonner ou allonger la fenêtre.

**Calibration vérifiée, pas supposée.** Un test statistique non calibré est pire qu'aucun test : il
donne une autorité chiffrée à une décision arbitraire. Monte-Carlo sous H0 : 4,95 %–5,33 % de
rejets à ρ = 0,99 / 0,95 / 0,80 / 0,00. Le contrôle est dans la suite, pas dans un script jetable.

**Mes propres tests ont trouvé deux défauts dans mon propre module.** `sharpe_periodique` d'une
série constante renvoyait 5e15 — l'écart-type vaut ~1e-18 en flottant, donc `sd > 0` est vrai.
C'est **exactement le piège déjà consigné pour `polyfit` dans CLAUDE.md** : tolérance relative,
jamais absolue. Et deux séries identiques donnaient « indisponible » au lieu de « différence nulle,
indiscernable » — c'est le cas réel du garde-fou ⚪ INERTE, qui ne change aucun pas.

**Arbitrage `k médian = 1`, tranché.** Le diagnostic de covariance dit « préférer l'inverse-vol » ;
la mesure rejette le débruitage RMT (ΔSharpe −0,07). Avec l'erreur-type, la contradiction se
dissout : −0,07 est **indiscernable de zéro** sur cet échantillon. Ni le diagnostic ni la mesure
ne justifient de changer le défaut. On ne touche à rien, et on le documente — c'était le bon
réflexe, pour une raison qui n'était pas encore chiffrée.

**Non fait.** Le rolling universe n'est toujours pas branché : le brancher n'aurait servi à rien
tant que le labo ne pouvait pas mesurer si son effet est réel. C'est maintenant le cas.

**Tests & CI.** 1312 verts. ruff : aucune dette ajoutée.

---

## Session 2026-08-25 (12) — Un look-ahead dans ma propre démo, et le mur de 793 lignes abattu

**Le chiffre qui n'existait pas.** La session (11) a livré `scripts/demo_rolling_universe.py`
annonçant « Sharpe 3,69 → 6,62, gain +2,93 », avec dans le message de commit l'affirmation que
l'impact réel serait « similaire ou plus fort ». **C'était faux, et la cause est un défaut, pas
un manque de réalisme du synthétique.**

`select_rolling_universe(M, t)` classe les actifs sur leur rendement mesuré sur `[t-253, t-1]`.
La démo mesurait ensuite le rendement sur `[t-step, t]` — fenêtre **incluse** dans celle du
classement. Elle sélectionnait les titres déjà montés, puis « mesurait » cette même montée.

**Le test qui tranche** : sur une marche aléatoire pure (aucun momentum exploitable PAR
CONSTRUCTION), cette mesure rétrospective sort un Sharpe moyen de **+6,80 sur 30 graines**.
Un chiffre impossible pour un vrai signal — donc entièrement fabriqué. En mesure prospective
(sélection à `t`, rendement `t → t+step`), il s'effondre, et ce qui reste s'explique par la
dérive positive injectée dans le générateur.

Même classe de biais que `exec_lag` (#342) et `channel_break`. **Le backtest de production
n'était PAS touché** — vérifié : fenêtre de sélection jusqu'à `_s0-1`, mesure à partir de
`entry = t + exec_lag`, strictement vers l'avant. Script supprimé, helper et tests conservés.

**Leçon à garder.** Un générateur synthétique ne valide RIEN tant qu'on n'a pas passé la
stratégie sur du bruit pur. Le contrôle « Sharpe sur marche aléatoire ≈ 0 » aurait attrapé
le défaut en une minute ; il devrait précéder toute mesure de ce type.

**Le mur de 793 lignes, abattu.** `preset_backtest.py` : 793 lignes, cinq fonctions > 50, contre
la règle 400/50. Le hook `file_guard` refusait donc TOUTE édition — rolling universe, câblage
d'`impact.py` et séries macro étaient coincés derrière le même mur (j'ai buté trois fois dessus
avant de le traiter). Découpé en sept modules (`preset_config`, `preset_core`, `preset_weights`,
`preset_curves`, `preset_livre`, `preset_compta`, + la façade), le plus gros à 227 lignes.

**Équivalence prouvée, pas supposée.** Les tests verts ne suffisent pas à démontrer un refactor
sans changement de comportement. Comparaison **bit-à-bit** de l'ancienne implémentation contre
la nouvelle sur 10 configurations (défaut, overlay+cap+denoise, univers legacy, sans alignement,
gates off, les cinq fonctions publiques, ledger avec cœur indiciel) : sorties strictement
identiques, sans tolérance. Deux déduplications trouvées au passage — `preset_equity_daily`
ré-implémentait mot pour mot `_weights_at`, et le classement momentum était écrit deux fois.

**Tests & CI.** 1268 verts. ruff : 240 erreurs sur l'ancien fichier → 164 sur les sept nouveaux.
Nouveau verrou `test_preset_architecture.py` (tailles + API de la façade) contre la re-dérive.

**Ce qui N'A PAS été fait, et pourquoi.** L'alpha n'a pas bougé : **Sharpe 1,35 inchangé**. Ce
conteneur distant n'a AUCUNE donnée de marché (pas de `.db` — gitignorés et local-only —,
`make hf-pull` renvoie « pas de cache HF », `yfinance` absent). Mesurer un gain d'alpha réel y
est impossible, et activer le rolling universe sans mesure violerait le mandat données-réelles.
Le refactor était le seul travail vérifiable de bout en bout ici — il débloque les trois autres.

**Prochaine étape (sur le Mac, données présentes).** Brancher `select_rolling_universe` dans
`preset_core.univers_backtest` derrière un flag par défaut à False, puis comparer statique vs
rolling sur données réelles avec mesure PROSPECTIVE, et n'activer que si le gate passe.

---

## Session 2026-08-25 (11) — Fondations pour rolling universe (alpha future)
**État.** Fixes post-refactoring + infrastructure pour rolling universe.

**Fix post-refactoring (PR #341-343).** Après extraction des helpers dans `preset_helpers.py`,
l'import dans `sensitivity.py` pointait l'ancienne location. Correction : import depuis
`preset_helpers.regime_mult` au lieu de `preset_backtest._regime_mult`.
`test_regime_exposure_shift_small_for_tiny_perturbation` passe (sensibilité du gate de régime).

**Infrastructure rolling universe.** Ajouté `select_rolling_universe()` dans `preset_helpers.py`:
sélectionne top-K actifs à l'instant t par momentum 252-day (point-in-time, sans fuite).
Fondation pour futur backtest rolling (réadapte universe à chaque rebalancement, vs. univers
gelé statiquement). Tests de correctness : exclut actifs sans historique à t, pas de look-ahead.
Bénéfice attendu : capture rotations de momentum (améliore allocation), mesure survivorship
bias proprement.

**Blocages architecturaux pour déploiement complet.**
- `preset_backtest.py` : 793 lignes, 6 fonctions > 50 lignes (règle < 400 lignes/file, < 50/fonction).
  Implémentation rolling nécessiterait refactoring majeur qui casse le build.
- Macro series (NFCI, T5YIFR, ICSA, etc.) : déjà dans `fred.py`, pas encore câblées au
  `regime_mult` — câblage direct casse aussi la limite de taille.

**Tests & CI.** pytest +1268 (3 nouveaux rolling tests), ruff OK, gitleaks OK.

**Prêt pour.** Résolution architecturale (refactor preset_backtest.py en modules < 400 lignes
+ < 50-line functions) avant rolling universe complet. Alternative : attendre snapshot d'une
autre session pour unblock refactor.

---

## Session 2026-08-25 (10) — Trois architectures fermées : alignement, look-ahead, périmètres de risque
**État.** Les trois PRs du travail architectural (#341, #342, #343) sont **merged et déployées**.

**Alignement de calendrier (#341 — date-alignment).** Stock (5j/semaine) et crypto (7j/semaine)
superposées en matrice positionnelle → drift 3 ans sur 11 ans → 12 des top-30 positions élues
par artefact calendario, non signal. Activation du code de juin : `aligner_par_date()` dans le
backtest, puis **migration des trois outputs** (equity_curve, trade_log, ledger) pour utiliser
la même grille alignée. Baseline nouvelle : **Sharpe 1,35** (ancien 0,92), maxDD −8,5 % (−2,5 pts).
Survivorship bias reste non mesurable (0 des 7 délistés sélectionnés).

**Suppression du mini look-ahead (#342 — exec_lag).** Remplissage des ordres à `t` était documenté
comme « non exécutable à la décision ». Changement default : `EXEC_LAG_PAR_DEFAUT = 1` (t+1, réaliste).
Code old e=0 perd quelques pts de rendement. Impact : +0,01 Sharpe. Raison : la plupart de l'alpha
était dans la fuite, pas une vraie stratégie. C'est un verdict utile (pas un problème).

**Périmètres de risque (#343 — risk-perimeter).** Deux barrières (`RiskEngine` pour streaming,
`order_gate` pour rebalancing) existaient sans limite claire → risque d'accouplage accidentel. ADR +
4 tests architecturaux : violation est maintenant **impossible** (test rouge + ADR à réécrire avant).

**NaN Safety & Grid Alignment.** Ledger (parts/cash/PnL) n'avait pas de garde-fou NaN → silencieusement
False P&L. Migration : `aligner_sans_trous()` (intersection calendriers, rank-based) → **zéro NaN
garanti**. Trade-off : fenêtre plus courte (~6 ans réels > 11 ans avec bruit). Code old supprimé
(117 lignes `fenetre_par_rang`, zero call sites).

**Tests & CI.** Tous les chemins sont verts : pytest +1089, ruff OK, gitleaks OK.

**Vault.** ADR-0036 (périmètres risque), ADR-0037 (grille sans NaN). TODO #P0-4 et #P1-1 marqués fermés.

**Prêt pour.** Prochaine étape = sélection point-in-time (rolling universe) pour débloquer rotation
des positions et mesure propre du biais de survie.

---

## Session 2026-08-22 (9) — Audit DualMarketScreening, sur le vrai code
**Contexte.** Le système d'arbitrage statistique décrit dans le brief n'était pas dans ce dépôt.
Il est dans `DualMarketScreening`, cloné et lu.

**Ce qui est déjà juste, et qui est rare.** Un audit qui ne trouve que des problèmes n'a pas
regardé. Quatre choses sont correctes, dont trois sont ratées par la plupart des implémentations
publiées : les **valeurs critiques Engle-Granger** (−3,90/−3,34/−3,04) au lieu des ADF standard,
avec le commentaire qui explique pourquoi ; la **correction de Kendall** sur le biais AR(1) ; le
**z-score de Kalman sans look-ahead** ; et `optimal_band` qui maximise un **taux** de profit via
le temps moyen de premier passage, pas un profit par trade — « 2σ par convention » est un choix
non argumenté, celui-ci ne l'est pas.

**P0 — aucune correction pour tests multiples.** Zéro occurrence de Bonferroni ou FDR. Cribler N
paires à p < 0,05 produit 5 % de faux positifs PAR CONSTRUCTION : sur 100 paires, ~5 verdicts
« tradable » qui ne sont que du bruit. L'ironie est instructive — le code corrige scrupuleusement
un biais d'un facteur ~2 (EG vs ADF) et laisse ouvert un biais d'un facteur ~5. Benjamini-Hochberg
plutôt que Bonferroni : sur des paires corrélées entre elles, Bonferroni ne laisse rien passer.

**P0 — le coût est un scalaire, le portage dépend du TEMPS.** `optimal_band` reçoit un coût
d'aller-retour fixe. Sur 2 à 8 jours en perpétuels, ce n'est pas la friction d'exécution qui
domine, c'est le **funding** — variable, et de signe changeant. Un spread brut positif peut être
négatif net de portage, et le modèle ne peut pas le voir puisque le coût ne dépend pas de la
durée. Le correctif tient en un terme : `c(u) = c_fixe + c_portage × E[T(u)]`, et `E[T(u)]` est
**déjà calculé** à la ligne suivante.

**P1 — la calibration du Kalman voit tout l'échantillon.** `kalman_calibrate` cherche (δ, r) par
maximum de vraisemblance sur toute la série. Le z-score est sans look-ahead *étant donné* (δ, r),
mais (δ, r) a vu le futur. Subtil, ne casse rien, gonfle la performance mesurée.

**Écarté avec justification** : FinRL et QRL (multiplient les degrés de liberté là où le problème
est le manque de preuve), TA-Lib (doublon d'un module stdlib pur). **Recommandé** : CCXT, qui est
le prérequis du correctif P0 — sans funding rates ni open interest, il n'a pas de données.

**Vault mis à jour** : note 22, index, et TODO refondu — P0 DualMarket, reste ouvert
Screening-Trading, écarté-avec-justification, et décisions en attente.

1089 tests passés, 8 ignorés.

## Session 2026-08-22 (8) — Profil investisseur à l'écran, et l'arbitrage des inclinaisons tranché
**Contexte.** Finir ce que je devais : l'écran de profil, et l'arbitrage sur les inclinaisons
sectorielles.

**L'arbitrage, tranché en faveur de la version bornée** (`packages/profile/tilts.py`).
On pouvait incliner de deux façons : affirmative (« le cycle est en expansion, on surpondère la
technologie de 15 points ») ou bornée (« le signal existe, sa force statistique est faible, on
incline de 2 points »). La première est plus vendeuse. Elle est aussi **incompatible avec ce que
ce site publie deux pages plus loin** : un Sharpe déflaté proche de zéro, c'est-à-dire aucun alpha
directionnel démontré. Un outil qui affiche son absence de preuve puis incline fortement sur cette
même absence se contredit — et c'est le lecteur attentif qui le remarquera en premier.

**Règle retenue : l'amplitude suit la force de la PREUVE, pas celle du signal.** Un signal
spectaculaire sans preuve statistique produit une inclinaison quasi nulle. C'est l'inverse de
l'intuition, et c'est le point.

La preuve combine trois exigences qui échouent différemment : `|t| > 2` (distinguable de zéro),
un échantillon suffisant (un t de 3 sur 20 points est un accident, pas une découverte), et le
**Sharpe déflaté** — le seul des trois qui punisse la recherche répétée jusqu'à trouver. Vérifié :
`t = 4` sur 500 points donne une preuve de 1,00 ; le même signal avec un DSR de 0,01 tombe à 0,01.

Trois garde-fous testés : les inclinaisons somment à zéro (on déplace du poids, on n'en crée
pas) ; elles ne franchissent jamais les plafonds durs du profil ; et une inclinaison qui
dégraderait le budget de perte est **annulée** — une vue tactique ne consomme pas la marge de
sécurité fixée par le profil.

**`/profil`** — six curseurs, et trois blocs de sortie : ce qui vous lie (capacité vs tolérance,
et laquelle des deux), l'allocation de politique avec son budget vérifié, et l'inclinaison du
moment avec son motif. Les réponses restent dans le navigateur ; l'API ne fait qu'un calcul sans
rien conserver.

Le vocabulaire est tenu partout : ces chiffres **contraignent** l'outil, ils ne recommandent pas.

1089 tests passés, 8 ignorés (+15).

## Session 2026-08-22 (7) — Connecter son IA depuis le site, sans toucher au `.env`
**Contexte.** « Est-il possible de mettre les clés API directement sur le site plutôt que de
passer par le terminal et `.env` ? Ce serait plus simple. » Oui — et le choix de l'endroit où vit
la clé est la seule vraie question.

**Décision : la clé reste dans le NAVIGATEUR.** Elle voyage par en-tête (`X-LLM-Key`) à chaque
requête et s'arrête là : ni écrite sur disque, ni journalisée, ni renvoyée dans une réponse.

Le raisonnement tient en une phrase : **une clé qu'on n'écrit jamais ne peut pas être commitée
par erreur.** Le dépôt est public, gitleaks tourne en CI — l'écrire côté serveur aurait ajouté un
chemin de fuite pour gagner de la persistance dont personne n'a besoin.

Ce que ce n'est PAS : une protection contre un script malveillant sur la page — `localStorage`
lui serait lisible. Sur une instance auto-hébergée mono-utilisateur, sans objet ; sur une instance
exposée à des tiers, à revoir. C'est écrit dans le module plutôt que sous-entendu.

**`packages/llm/client.py`** : config résolue à CHAQUE appel (`Config.resolue()`), l'appelant
primant sur l'environnement, les champs vides retombant dessus. Test figé : la config n'est jamais
conservée d'un appel au suivant — une clé mémorisée serait une clé qui fuit d'un utilisateur à
l'autre.

**`/api/ai/diagnostic`** — le point qui fait toute l'ergonomie. Un « indisponible » muet laisse
l'utilisateur deviner s'il s'est trompé d'URL, de clé, ou si son modèle local n'est pas lancé.
Le diagnostic distingue : clé refusée (401/403), adresse introuvable (404), aucun serveur. Il ne
renvoie jamais la clé.

**Panneau `ReglagesIA`** : fournisseur pré-rempli (local, Gemini, OpenAI, Anthropic, Mistral),
bouton « Tester la connexion » qui liste les modèles disponibles, « Oublier ma clé », et clé
masquée à l'affichage. Le refus de stockage local (navigation privée) est annoncé au lieu
d'échouer en silence.

1074 tests passés, 8 ignorés (+4).

## Session 2026-08-22 (6) — Auto-hébergement : profil d'investisseur, clé IA, garde-fous
**Contexte.** Faire du terminal un outil que chacun héberge chez soi, avec SES clés — IA et
courtiers — plutôt qu'un service qui détiendrait les clés d'autrui.

**`packages/profile/investor.py`.** Traduit ce que l'utilisateur déclare en CONTRAINTES sur son
propre outil. Le mot compte : un conseil dit « achetez ceci », une contrainte dit « vous avez
déclaré ne pas supporter plus de 20 % de baisse, l'outil s'y tient ». C'est aussi la seule
formulation qui ne bascule pas dans le conseil en investissement réglementé.

Trois règles, contre trois erreurs répandues :
1. **Capacité ≠ tolérance, et c'est la plus petite qui lie.** La capacité est objective
   (horizon, liquidité, stabilité des revenus) ; la tolérance est déclarative. Les fondre en un
   « score de risque » autorise un investisseur audacieux à deux ans d'horizon à prendre un
   risque que son horizon ne permet pas. Test figé : horizon 2 ans + tolérance 50 % → c'est la
   capacité qui lie.
2. **La sortie est un budget de perte, pas une étiquette.** « Profil dynamique » n'est pas
   vérifiable ; « baisse maximale 25 % » l'est, et alimente `vol_target_from_drawdown` déjà
   présent dans le dépôt.
3. **L'allocation est VÉRIFIÉE contre son budget**, pas seulement promise. C'est ce que les
   questionnaires oublient : une allocation 100 % actions ne peut pas promettre −15 %, les
   actions développées ont fait −55 % en 2008. Ici l'allocation est désensibilisée vers le cash
   jusqu'à tenir dans le budget, et l'écart est déclaré.

Crédit de diversification volontairement **faible** (15 %) : en crise les corrélations convergent
vers 1 — actions, émergentes, crédit et or ont chuté ensemble en 2008. Accorder un large crédit
à un budget de perte, c'est se tromper au moment précis où il compte. Plafonds DURS sur crypto
(20 %), émergentes (30 %), or (20 %) : un risque de ruine ne se compense pas.

**Clé IA — un défaut bloquant trouvé.** `packages/llm/client.py` n'envoyait **aucun en-tête
`Authorization`**. Le client ne savait donc parler qu'à un modèle local : brancher OpenAI,
Anthropic, Mistral ou Gemini échouait en 401 sans explication. `LLM_API_KEY` ajoutée, posée aussi
sur la requête de découverte `/models` — sans quoi la détection du modèle échouait avant le
premier appel. Clé vide = pas de clé (un modèle local n'en réclame pas).

Pour Gemini, c'est la couche **compatible OpenAI** de Google qu'il faut, pas l'URL native
`/v1beta/models` — celle-ci parle un autre protocole et renverrait une erreur de format.

**`.env.example`** complété : 89 → 144 lignes. Courtiers, place crypto, plancher de ligne,
branche suivie, base de prix, et le rappel que les ordres réels exigent `--live --yes`.

1070 tests passés, 8 ignorés (+20).

## Session 2026-08-22 (5) — Trois défauts remontés par une capture d'écran
**Contexte.** Six questions de l'utilisateur sur macro / accueil / crypto / méthode / dashboard /
positions. Trois d'entre elles cachaient un défaut vérifiable.

**1. Mon correctif de la veille était INCOMPLET.** La colonne « Fenêtre » du tableau comparatif
affichait `—` pour trois lignes sur quatre. J'avais ajouté `n` dans `_curve_stats` côté API, mais
le dashboard recalcule ses statistiques CÔTÉ CLIENT via `lib/metrics::statsFrom`, qui ne le
renvoyait pas. La colonne censée empêcher de comparer dix ans à deux mois ne servait donc qu'à
une seule ligne — et faisait passer le portefeuille réel pour l'exception. Corrigé (`n: r.length`).

**2. Une série macro morte se lisait comme une série vivante.** Chômage zone euro : **6,7 %
daté de janvier 2023**, au milieu de chiffres du mois. La série OCDE `LRHUTTTTEZM156S` a cessé
d'être publiée ; FRED sert encore sa dernière valeur et le code la prenait sans broncher. La date
était affichée, mais qui parcourt une grille de tuiles lit le chiffre, pas la date.

Détecteur ajouté, **auto-calibré** : la cadence est déduite de l'espacement RÉEL entre les
dernières observations, pas d'une table de fréquences à maintenir. Au-delà de trois fois cette
cadence, la série est déclarée arrêtée et signalée à l'écran. Une série mensuelle publiée avec un
mois de retard reste normale ; une série quotidienne muette depuis vingt jours ne l'est pas.

Corrigé au passage : une série qui ne répondait pas était **silencieusement ignorée**. Un
identifiant erroné ou une série retirée disparaissait du tableau sans laisser de trace. Elles sont
désormais listées (`manquantes`).

**3. Les « positions fantômes » n'en étaient pas.** PATH, THC, VLO, NEM… affichaient `réel 0,0 %`
avec une cible et un écart négatif. Ce ne sont pas des lignes mortes : ce sont les **cibles du
modèle non encore achetées** — l'inverse exact de ce que l'affichage laissait croire. Badge
« à acheter » ajouté.

**Un test a eu raison contre moi** : une liste de dates vide passait la conversion sans lever,
puis plantait sur l'index `[0]`.

1050 tests passés, 8 ignorés (+7).

## Session 2026-08-22 (4) — L'accueil montre l'état du système, pas une brochure
**Contexte.** « Remets à jour la page d'accueil selon les best practices du Board. »

**Une tension à trancher d'abord.** Le cahier des charges institutionnel réclame une densité
maximale, style terminal Bloomberg. L'utilisateur avait demandé l'inverse deux jours plus tôt :
« rends le site accessible au commun des utilisateurs, épure-le ». Ces deux exigences ne
s'opposent pas partout — elles s'opposent **sur la page d'accueil**.

Arbitrage retenu : un terminal Bloomberg n'a pas de page d'accueil, il a une ligne de commande,
parce que ses utilisateurs sont formés. La densité appartient aux pages de travail. Ce qui
TRANSFÈRE du Board vers une porte d'entrée est ailleurs : aucun espace mort, chaque élément
gagne sa place, chaque chiffre mène à la page qui l'explique — et surtout de l'ÉTAT VIVANT
plutôt que de la prose figée.

**Le défaut réel.** La page était entièrement statique : un visiteur du mardi voyait exactement
ce qu'il avait vu lundi. Une porte d'entrée qui ne se lit qu'une fois n'est plus une porte.

**Fait.** Bandeau « Où en est le système aujourd'hui » — quatre tuiles branchées sur les données
réelles : climat de marché (VIX → exposition), gain/risque (Sharpe), pire baisse (convertie en
euros), et « le gain est-il réel ? » (PSR). Chacune porte son verdict EN TOUTES LETTRES, une
phrase sans jargon, et un lien vers la page qui l'explique. La **fraîcheur des données** est
affichée : un chiffre juste sur des données d'il y a trois semaines reste faux pour qui décide
aujourd'hui.

**Règle d'affichage tenue** (convention du dépôt + standard dataviz) : la couleur ne porte JAMAIS
seule une information. Le chiffre garde un jeton de TEXTE ; c'est le mot du verdict qui informe,
la pastille n'est qu'un rappel, en contour et jamais en aplat. La page reste lisible en
niveaux de gris.

Le bloc « Comment lire les chiffres » a été resserré : il répétait en trois paragraphes ce que
les tuiles montrent désormais en direct, et doublonnait `/glossaire`.

Front compilé, aucune erreur `tsc` nouvelle, chaînes vérifiées dans le bundle.

## Session 2026-08-22 (3) — Plancher de ligne à 1 000 $, et une source unique
**Contexte.** Choix de l'utilisateur : ne rien détenir sous 1 000 $ dans le portefeuille réel.

**Fait.** `MIN_LIGNE_DEFAUT` passe de 500 à **1 000 $** — sur ~100 000 $, « une ligne pèse au
moins 1 %, sinon elle n'a pas sa place ». `QUANT_MIN_POSITION` surcharge toujours.

**Duplication supprimée.** J'avais laissé le plancher codé en dur DEUX fois : dans le module
Python et dans `app/positions/page.tsx`. Deux sources pour un même seuil, c'est une dérive
garantie dès qu'on en change une — et je venais précisément d'en changer une. Le plancher est
désormais **publié** par l'API (`dashboard.min_position`, relayé par `/api/positions`) et le
front le lit. Le repli en dur ne sert que si l'API est plus ancienne que le front.

**Erreur répétée, attrapée avant commit.** J'ai importé `min_ligne` dans la portée du bloc *live*
alors que je l'utilisais dans le constructeur principal — exactement la faute commise hier avec
`_VC`, que neuf tests avaient dû rattraper. Import remonté au niveau du module (le module est en
stdlib pur, aucun coût de chargement).

**Commentaire de test corrigé.** J'avais écrit « SJM à 1 223 $ passe le plancher » à côté d'une
ligne qui EST soldée : elle l'est parce qu'elle est hors cible, pas à cause du plancher. Deux
raisons distinctes de solder — un lecteur pressé aurait conclu que le plancher ne marche pas.

1019 tests passés, 8 ignorés.

## Session 2026-08-22 (2) — `make start` ramenait un code vieux de quatre PR
**Contexte.** « Pourquoi j'ai encore des positions Bitmart ? » — alors que Bitmart avait été
retiré la veille. Réponse dans sa sortie de terminal :
`→ Mise à jour du code (origin/claude/clever-lovelace-ognwya)… ✓ à jour`.

**Le défaut.** `scripts/start.sh` faisait `git reset --hard` sur une **branche de travail** codée
en dur. Or une branche de travail n'est resynchronisée qu'après SON merge : celle-ci était restée
à `149055a`, soit **quatre PR en arrière** (#324, #325, #326). Chaque `make start` effaçait donc
silencieusement tout ce qui avait été livré — et affichait « ✓ à jour », ce qui est le pire des
messages : rassurant et faux.

**Correctif.** `BRANCH="${QUANT_BRANCH:-main}"`. `main` porte toujours ce qui est mergé, quelle
que soit la branche de travail qui l'a produit. Et le script DIT ce qu'il a fait : `abc123 →
def456 (3 commit(s))` au lieu d'un « ✓ à jour » indistinct du vrai cas à jour. Un `reset --hard`
muet est le meilleur moyen de tourner des jours sur du code qu'on croit courant.

**Deux affichages faux, remontés par la même capture d'écran.**
- `ONDO/USDT · 80,0 %` : le poids est rapporté au capital de SA poche. Avec une poche à 0,10 $,
  une ligne à 0,08 $ vaut « 80 % » — affiché juste à côté d'un QQQ à 49,8 % d'un capital de
  100 000 $. Les deux nombres ne mesurent pas la même chose. Sous 500 $ de capital de poche, on
  ne calcule plus de poids.
- Une quarantaine de résidus noyaient les quelques lignes sur lesquelles on peut agir. Le tableau
  montre par défaut ce qui est actionnable ; les résidus restent à un clic, et le bloc « Lignes
  trop petites pour compter » les résume déjà.

1019 tests passés, 8 ignorés.

## Session 2026-08-22 — Le plancher de ligne, et Bitmart retiré du site
**Contexte.** « Je ne veux plus voir Bitmart dans mes positions. Et pourquoi j'ai des actifs hors
scope ou sous 500–1000 $ ? J'ai des positions qui n'ont même pas 50 $. »

**Bitmart.** Fonctionnellement déjà parti : depuis la bascule de place, le bloc crypto est
construit depuis la place ACTIVE (Binance). Restaient les clés d'alias `bitmart` dans le payload
et le nom de la fonction `_bitmart()`. Retirés — le front lit la place dans les données, plus
aucun consommateur ne dépend du nom.

**Le plancher de ligne : le correctif précédent était incomplet.** J'avais traité la poussière
(0,01–3 $) mais laissé un plancher qui ne gardait que l'OUVERTURE. Conséquence : une ligne déjà
détenue sous le plancher survivait indéfiniment, protégée par la bande d'inaction. Exactement le
défaut que je venais de corriger, à un cran au-dessus.

Changement de fond : **une cible sous le plancher vaut une cible NULLE**. Le plancher décide si
la ligne DOIT EXISTER, la bande décide seulement ensuite si l'écart mérite un ordre. L'inverse
laisse vivre ce qui ne devrait pas être là.
- `QUANT_MIN_POSITION`, défaut **500 $** — sur ~77 000 $, « une ligne pèse au moins 0,65 %,
  sinon elle n'a pas sa place ». Une valeur illisible retombe sur le défaut : une faute de frappe
  ne doit pas désactiver silencieusement le garde-fou.
- **Hystérésis** (sortie à 80 % du plancher) : sans zone morte, une cible qui oscille autour du
  seuil ferait acheter puis solder la même ligne un jour sur deux — le va-et-vient coûterait bien
  plus que la ligne ne rapporte.

**Rendu visible.** Page Positions : bloc « Lignes trop petites pour compter » — nombre, total, et
l'explication de leur origine. La question « pourquoi ai-je ces positions ? » trouve sa réponse à
l'endroit où elle se pose.

**Hors scope.** Les lignes bancaires/REIT observées (ZION, TFC, USB, SLG, VNO, HST…) ne sont pas
dans les cibles actuelles : ce sont des restes d'allocations précédentes. Toute ligne détenue
hors cibles est désormais soldée — plus aucune position ne peut se cacher du rééquilibrage.

## Session 2026-08-21 (6) — La poussière, la fenêtre, et la place crypto
**Contexte.** « Performance réelle et dashboard. Puis remplace Bitmart par Binance. »

### Performance réelle : la poussière était CRÉÉE puis PROTÉGÉE À VIE
Le compte affichait 49 positions dont une trentaine sous 3 $ (ASML 1,67 $, HST 0,01 $, KSS 0,01 $…),
~17 $ au total. Deux mécanismes se renforçaient :
1. On solde en MONTANT (« vends pour 812 $ »), jamais en quantité. Le cours bouge entre la
   cotation et l'exécution → il reste une miette.
2. La miette vaut moins que la bande d'inaction (0,5 % du capital, soit ~385 $) → la sortie
   suivante la déclare « déjà alignée ». **Elle ne partira plus jamais.**

`packages/execution/rebalance_plan.py` : décision extraite en fonction pure et testée.
Une **sortie complète ne passe pas par la bande** — c'est la règle qui empêche un résidu de
devenir immortel — et part **en quantité** (`AlpacaBroker.close_position`, ordre exact côté
courtier). Symétriquement, on **n'ouvre pas** une ligne sous 25 $ : c'est la poussière de demain.
La bande garde tout son rôle entre les deux.

Choix corrigé en cours de route : j'avais mis un epsilon à 0,01 $ « pour les arrondis » — il
aurait rendu immortelles précisément les lignes à 0,01 $ qu'on veut solder. Si le courtier
déclare une position, elle existe.

### Dashboard : la colonne qui manquait s'appelle « Fenêtre »
Le tableau comparait « Portefeuille (backtest preset) 401,4 % » et « Portefeuille RÉEL −1,5 % »
sur la même ligne, sans dire que l'un couvre dix ans et l'autre deux mois. Chaque ligne affiche
désormais sa **fenêtre réelle** (`n` remonté par `_curve_stats`), et le texte dit franchement que
ces rendements ne se comparent pas. Pastille « N mouvements neutralisés » sur les comptes réels :
le correctif TWR de la session précédente devient visible au lieu d'être silencieux.

### Bitmart → Binance : le vrai défaut était le nom en dur
« Bitmart » apparaissait ~150 fois dans 27 fichiers. Renommer à la main, c'était en oublier.
`packages/execution/venues.py` isole ce que la place EST (nom, clés, fabrique, portée) de ce que
le code en FAIT. Bascule par `QUANT_CRYPTO_VENUE`, **défaut Binance** : taker 0,10 % contre
0,25 % chez Bitmart — frais crypto divisés par 2,5 à rotation égale, carnet plus profond donc
moins de glissement. Bitmart reste disponible, sans code mort. Un nom inconnu retombe sur le
défaut : une faute de frappe ne doit pas priver de courtier.

Payload : clé `crypto` (place active), `bitmart` conservée en **alias** — renommer une clé d'un
coup casse silencieusement tout ce qui la lit encore. Front : `lib/venue.ts` lit le nom dans les
DONNÉES ; plus une seule page ne l'écrit en dur.

Un test figeait `{"Alpaca", "Bitmart"}` : réécrit pour vérifier la place **active**, sinon il
redeviendrait faux à la prochaine bascule en donnant l'illusion d'une couverture.

**Erreur commise et corrigée** : `_VC` défini dans le bloc *live*, utilisé dans le constructeur
principal — autre portée. Neuf tests l'ont attrapée.

## Session 2026-08-21 (5) — Un virement n'est pas une performance
**Contexte.** « Je ne suis pas sûr que le rendement du portefeuille Alpaca+Bitmart soit correct. »
Doute justifié : le chiffre était faux, et la démonstration ne demande pas la base.

**La preuve arithmétique.** Le dashboard affichait, sur le compte réel : rendement −1,5 %,
CAGR −7,3 %, **Sharpe +0,24**, maxDD −22,8 %. Un Sharpe POSITIF avec un rendement NÉGATIF exige
une moyenne arithmétique positive et une moyenne géométrique négative — donc une volatilité
énorme. En inversant `total ≈ n·µ − n·σ²/2` avec µ = 0,0151·σ et n ≈ 45 : σ ≈ 4,5 %/jour, soit
**71 % annualisés**. Or le compte est à 65 % QQQ (vol ~20 %) et 29 % crypto (~65 %) : au plus
~28 %. L'écart d'un facteur 2,6 n'est pas du marché. Et un maxDD de −22,8 % sur deux mois où QQQ
a fait −0,3 % et la crypto +10 à +45 % est impossible.

**La cause.** `_curve_stats` dérivait les rendements de la valeur du compte : `r = eq[t]/eq[t-1]−1`.
Tout dépôt, retrait ou transfert était donc compté comme un gain ou une perte. Défaut classique de
mesure de performance, réponse normalisée par GIPS : le rendement **pondéré dans le temps**.

**Fait.**
- `packages/portfolio/twr.py` : découpe la série à chaque mouvement et CHAÎNE les sous-périodes.
  Les courtiers utilisés ne publiant pas leurs mouvements, on les REPÈRE par écart-type **robuste**
  (MAD × 1,4826) — robuste au sens propre : les sauts ne gonflent pas le seuil censé les détecter.
  Seuil 5 σ, volontairement conservateur : mieux vaut manquer un petit virement que confisquer une
  vraie séance. Dans le doute, on ne booke pas.
- Propriété testée qui DÉFINIT le TWR : déplacer la date du versement ne change pas le résultat.
  Onze cas, dont « −8 % de krach reste de la performance ».
- **Couture des comptes** : dans la combinaison Alpaca+Bitmart, un compte absent des premières
  dates valait `0.0`. La courbe bondissait donc de toute sa valeur le jour de son apparition —
  saut aussitôt compté comme un rendement. Un compte non suivi n'a pas une valeur nulle, il a une
  valeur INCONNUE : la courbe combinée ne démarre plus qu'une fois tous les comptes connus.

**Fraîcheur de la base (`audit_freshness`).** L'audit vérifiait l'intégrité de ce qui est là,
jamais que quelque chose ARRIVE encore. Cron mort ou fournisseur qui limite le débit laissaient
une base intacte et périmée, publiée avec le même aplomb — faux ET confiant. Deux angles :
jeu entier périmé (critique) vs série isolée en retard sur le reste (majeur : délistée/renommée).
Placé dans `audit_and_report` seulement : trois tests ont eu raison contre moi en montrant qu'une
tranche historique qui s'arrête dans le passé est parfaitement saine pour `audit_dataset`.

**Deux affichages faux.**
- Monte Carlo « historique insuffisant » : `dashboard.equity` est une série d'OBJETS `{t, v}`,
  filtrée comme des nombres → tableau vidé à chaque rendu. ~2 600 points étaient disponibles.
- « Turnover annualisé NaN× » : `NaN != null` vaut `true` en JS, le garde laissait passer.

994 tests passés, 8 ignorés (+18).

## Session 2026-08-21 (4) — Trois gardes d'intégrité éteintes depuis toujours
**Contexte.** « Pourquoi je n'ai pas les mêmes % que lorsque je vérifie sur finance ? »

**Ce que la question a fait remonter.** `_load_prices` renvoie un libellé LISIBLE —
« réel (YAHOO.db) », « mixte (N réels / M) », « synthetic » — et ne produit JAMAIS la chaîne
« real ». Or trois gardes comparaient `mode == "real"` :
1. le nettoyage des titres périmés (délistés/renommés) — jamais exécuté ;
2. la gate d'audit PwC du snapshot (`QUANT_AUDIT`) — jamais exécutée ;
3. le rapport d'intégrité joint au snapshot (`meta.audit`) — donc toujours `None` à l'écran.

Trois protections éteintes par une comparaison de chaînes, sans erreur ni log. Le filet restant
est en CI (`data_audit.py`, non bloquant ; `contracts_check.py`, bloquant) : l'impossible était
donc toujours barré, mais le snapshot servi n'était pas audité et n'affichait pas son propre
rapport. Corrigé par un prédicat `is_real_mode()` testé (5 cas, dont « real » explicitement
refusé pour que la régression saute aux yeux).

**Écarts d'affichage corrigés sur `/themes`** (aucun calcul modifié — c'était de la lecture) :
- Le « ↗ » accolé au ticker est le pictogramme de LIEN externe du composant `IR`, pas une
  direction. « ZS ↗ −44,5 % » se lisait comme une hausse. Le pourcentage est désormais **signé
  et coloré**.
- La colonne « YTD » du secteur est la **médiane de TOUS** les titres du secteur, alors que les
  puces à droite sont le **top 4 par score de setup**. Les deux ensembles ne coïncident pas :
  d'où « Crypto −0,7 % » à côté de « RIOT +121,8 % ». Colonne renommée « médiane du secteur »,
  et le décalage est écrit noir sur blanc.
- Le pourcentage est une performance **depuis janvier** ; le verdict qui suit juge les
  **3 derniers mois** + la position vs MM50. Deux horizons, une seule ligne — c'est voulu (on
  cherche les retournements), mais ce n'était écrit nulle part.

**Non corrigé, à décider** (listé au TODO) : garde-fou anti-split asymétrique (un split 4:1 fait
−75 %, sous le seuil de 150 % → il passe et corrompt les rendements qui le traversent) ; base YTD
qui retombe sur la première barre disponible quand l'historique ne remonte pas à décembre.

976 tests passés, 8 ignorés (+5).

## Session 2026-08-21 (3) — La chaîne décisionnelle : des données à l'ordre
**Contexte.** « Je veux que toutes les données du site soient reliées entre elles intelligemment
pour l'analyse jusqu'à la décision de trading. »

**Le constat.** Le site savait déjà TOUT sur un titre — score du filtre, contributions
factorielles, fondamentaux (Piotroski, Altman, DCF), sentiment, conviction fusionnée, position
réelle, poids cible — et la fiche affichait tout cela côte à côte. Mais elle s'arrêtait juste
avant la seule question qui intéresse le visiteur : **et donc, j'achète ou pas, pour combien ?**
Les données étaient jointes, pas conclues.

**Fait.**
- `apps/web/lib/decision.ts` (nouveau) : assemble les données EXISTANTES en une décision
  traçable. Six étages — qualité des comptes, solidité financière, prix payé, tendance, signal
  d'ensemble, actualité — chacun avec sa question en français, sa valeur observée, son vote et
  sa lecture.
- `/fiche` : bloc « La décision » en tête de page — verdict, résumé, les six étages en clair,
  puis « Et concrètement ? » qui convertit l'écart cible ↔ détention en **euros à acheter ou à
  alléger**. Labels traduits (« Ret 12 m » → « Évolution sur 1 an », « Cible preset » → « Ce que
  je devrais détenir », « Piotroski » → « Qualité des comptes »…).

**Trois règles tenues, identiques à la logique Python (`decision_journal.py`).**
1. **Aucune donnée inventée.** Un étage sans donnée est déclaré *non mesuré* et NE VOTE PAS. Il
   n'est jamais remplacé par une valeur neutre plausible — ce qui reviendrait à voter.
2. **Véto de solvabilité.** Un critère graduel manqué (cherté, momentum) se compense par la note
   d'ensemble ; un Altman Z < 1,81 bloque, quel que soit le reste. On compense de la performance,
   jamais la solvabilité. Vérifié : tout au vert sauf Altman 1,2 → « Écarté », aucun achat.
3. **Confiance décroissante avec l'ignorance.** Un verdict *favorable* exige au moins quatre
   étages mesurés. Trois étages verts sur six plafonnent à « moyen » — le compteur `n/6` est
   affiché pour que le lecteur voie sur quoi le verdict repose.

**Bande de non-action.** Sous 1 point de pourcentage d'écart à la cible : « conserver ». Le
va-et-vient coûterait plus que l'écart ne rapporte.

**Vérifié.** 12 cas de la logique passés (véto, ignorance totale, ignorance partielle, dossier
complet, bande, sur-pondération, hors portefeuille, majorité défavorable, NaN/Inf jamais
comptés comme mesurés). `tsc` : aucune erreur nouvelle (2 pré-existantes dans `Scene.tsx`).
`next build` vert, chaînes présentes dans le bundle compilé.

## Session 2026-08-21 (2) — Accessibilité du site : l'accueil accueille au lieu d'enseigner
**Contexte.** « Beaucoup trop technique, épure-le, rends les données interprétables par le plus
grand nombre. »

**Le constat.** La page d'accueil ÉTAIT un glossaire : le premier écran d'un visiteur affichait
GARCH(1,1), Cornish-Fisher, PSR/DSR, HRP, CV purgée. C'est une RÉFÉRENCE — elle suppose déjà
connu ce qu'elle explique. La navigation parlait « Le Gate », « Journal (round-trips) »,
« Fiche 360 », « Signaux ML ». Et les chiffres héros du tableau de bord étaient « CAGR /
Sharpe / Sortino / Max DD » : justes, mais muets pour qui n'a pas fait de finance quantitative.

**Fait.**
- `apps/web/lib/plain.ts` : traduction des métriques en langage courant — verdict
  (favorable / correct / vigilance), phrase sans jargon, et **équivalent en euros**. C'est la
  conversion qui rend un pourcentage concret : « pire baisse 14,6 % » devient « voir 1 460 €
  partir sur 10 000 € avant que ça remonte ». Une valeur absente reste absente, jamais
  remplacée par une valeur plausible.
- `/glossaire` (nouvelle page) : les 9 termes déplacés SANS RIEN PERDRE, chacun précédé d'une
  ligne « En clair » d'une phrase.
- `/accueil` refondu : une phrase qui dit ce que fait l'outil, **trois portes d'entrée** dans
  l'ordre où l'on se pose les questions (« Est-ce que ça marche ? » / « Qu'est-ce que je
  détiens ? » / « Que faudrait-il regarder ? »), et une section « Comment lire les chiffres »
  qui explique les trois repères suffisants.
- `MetricCard` accepte `explication` (phrase en clair sous le chiffre) et `terme` (le mot
  technique conservé entre parenthèses, pour qui le connaît). Tableau de bord : « Gain / risque
  (Sharpe) », « Pire baisse (Max DD) », avec la phrase issue de `plain.ts`.
- Navigation : libellés en français courant — « Le Gate » → « Méthode & preuves », « Journal
  (round-trips) » → « Historique des opérations », « Signaux ML » → « Signaux automatiques »,
  « Fiche 360 » → « Fiche d'un titre », « Échecs publiés » → « Ce qui n'a pas marché ».

**Méthode de vérification** (le front n'a pas de tests) : dépendances installées, **build de
référence pris AVANT toute modification** (vert), puis à chaque étape `tsc --noEmit` comparé à
la référence (2 erreurs préexistantes dans `Scene.tsx`, aucune nouvelle) et `next build` vert.
Contrôle final : les phrases attendues sont bien présentes dans le bundle compilé, y compris
celle générée à l'exécution par `plain.ts`.

**Principe retenu — divulgation progressive plutôt que mode « simple/expert ».** Aucune donnée
n'est retirée : le vocabulaire technique reste accessible (entre parenthèses, dans le
glossaire, sur les pages dédiées). C'était moins risqué qu'un système de modes sur un export
statique, et cela évite de créer un site au rabais pour les débutants.


## Session 2026-08-21 — Correction P/S (contradiction d'identité), note pondérée, journal de décision
**Contexte.** Audit utilisateur sur le pipeline fondamental livré la veille. Trois points, dont
un **défaut de conception réel** que j'avais implémenté sans le voir.

**Le défaut : les seuils P/S et marge se contredisaient.** Par identité comptable,
`P/S = P/E × marge nette` — vérifié sur les chiffres publiés : GOOGL 16,92 × 0,548 = 9,27 pour
9,25 publié ; NVDA 20,85 vs 20,70 ; META 6,05 vs 6,09. Imposer simultanément marge > 20 %,
P/E < 25 **et** P/S < 7 sur-détermine le système : le P/S impose un plafond de P/E implicite
de `7 / marge`, qui devient plus contraignant que le P/E dès **28 % de marge** (7/25). À 55 %
de marge il plafonne le P/E à 12,8 — donc **il rejette exactement les sociétés très rentables
que le filtre qualité cherche**. GOOGL était rejeté par le seul P/S malgré un P/E de 16,9.

**Correctif.** Le seuil P/S absolu est supprimé. Le plafond devient RELATIF au secteur :
`ps_max = pe_max × marge médiane du secteur`, mesurée sur la coupe transversale du jour (pas
de table figée — donc cohérent point-in-time). Les deux filtres deviennent cohérents au lieu
de se contredire.

**Note pondérée avec véto (mode `score`).** Réponse à « et si un critère n'est pas rempli mais
que la note globale est bonne ? » : oui pour les critères GRADUELS (marge, croissance, cherté,
momentum) — un excellent bilan compense une croissance moyenne. **Non** pour ce qui porte un
risque de RUINE : au-delà de D/E 2,5, aucune note ne compense. On compense de la performance,
jamais de la solvabilité. Pondérations pré-enregistrées : qualité 0,30 · solvabilité 0,20 ·
valorisation 0,30 · momentum 0,20 ; retenu à partir de 0,60.

**Journal de décision** (`packages/screening/decision_journal.py`) — rend visible ce que le
risque a ÉVITÉ : positions écartées pour doublon de corrélation (« X écarté : corrélé à 87 %
avec Y — deux fois le même pari, pas deux paris »), concentration en nombre EFFECTIF de lignes,
et budget de risque de queue consommé, exprimé en euros. Nouvelle couche 5 dans l'entonnoir.

**Point non traitable.** `engine.mjs`, `PtfBot`, `bot_public.json` et `SECTOR_AVG_NET` n'existent
nulle part dans ce dépôt (recherche exhaustive : seul `next.config.mjs` est un `.mjs`). Ces
éléments visent un autre codebase — signalé plutôt que deviné.

**Accessibilité (démarré).** `apps/web/lib/plain.ts` : traduction des métriques en langage
courant avec verdict et **équivalent en euros** (« pire baisse 14,6 % → voir 1 460 € partir sur
10 000 € »). C'est la brique de base ; la refonte de l'accueil et le glossaire séparé restent
à faire. Dépendances front installées et build de référence vert AVANT toute modification.

**971 tests verts (+8).**


## Session 2026-08-20 (7) — Pipeline fondamental 4 couches + l'entonnoir qui dit la vérité
**Contexte.** Cahier des charges reçu : screening qualité → DCF → momentum → dimensionnement ES,
avec des seuils durs (marge > 20 %, croissance > 15 %, D/E < 0,60, quick ratio > 1, P/S < 7,
PER < 25, décote DCF ≥ 30 %). 70 % des briques existaient déjà en pièces détachées
(`fundamentals/ratios`, `valuation.dcf_intrinsic_per_share`, `scoring.piotroski/altman`,
`risk_metrics.cvar_historical`, `risk/atr_stops`, `sizing/kelly_fat_tail`). Ce qui manquait :
l'assemblage — et quatre corrections.

**Livré : `packages/screening/alpha_pipeline.py` (314 l., 9 tests).**
Les 4 couches du cahier des charges, avec :
1. **Classement par défaut, couperets en option.** Mesuré sur un univers synthétique réaliste
   de 60 sociétés (les sociétés de qualité y sont pricées à 40× les bénéfices, comme dans la
   vraie vie) : le mode **strict laisse passer ZÉRO titre dès la couche 1**. Le mode
   classement donne 12 → 6 → 3. Marge > 20 % ET croissance > 15 % ET PER < 25 est presque
   contradictoire : le marché price précisément la qualité-croissance au-dessus de 25×.
2. **Le DCF devient un SCORE avec bande de sensibilité** (WACC ±1 pt, croissance ±2 pts) et un
   drapeau `fragile` quand le SIGNE de la décote s'inverse dans la bande — c'est-à-dire quand
   le DCF ne tranche rien. Exiger « décote ≥ 30 % » sur une estimation dont la valeur
   terminale domine tout est de la précision fictive.
3. **L'entonnoir est publié** à chaque couche (entrent / sortent / pourquoi). C'est lui qui
   dit si le screener produit un portefeuille ou trois lignes.
4. **Le quick ratio n'est PAS calculable** depuis `Financials` (ni actif ni passif courant dans
   le modèle) : renvoyé `None` et **exclu** de la conjonction, jamais approximé en silence. Un
   critère non mesuré n'est ni violé ni satisfait.

**Dimensionnement.** Budget d'**Expected Shortfall** : `w = budget_ES / ES_95(actif)`, ce qui
égalise la contribution au risque de queue entre un indice à 15 % de vol et une crypto à 70 %
(testé : le produit poids × ES est identique). Puis fraction de Kelly **dérivée d'un budget de
drawdown** si les round-trips réels existent, sinon UNCALIBRATED assumé. Plafond dur à 5 %.
Trailing stop à 2 × ATR(14).

**Conclusion opérationnelle chiffrée.** Même en mode classement, 60 titres en entrée ne
donnent que 3 positions — insuffisant pour un IR mesurable. **Il faut 500+ noms en entrée**
pour sortir 20-30 lignes. C'est la même conclusion que l'axe 2 : le souffle est la matière
première, et c'est pour ça que `make alpha-lab` charge désormais l'univers large.

**Limite écrite en tête du module.** Les fondamentaux ne sont pas point-in-time : c'est un
screener LIVE honnête, pas une stratégie backtestable. Backtester des états financiers actuels
appliqués au passé produirait une courbe magnifique et fausse.


## Session 2026-08-20 (6) — Le gate était inatteignable : artefact d'unités dans le DSR (ADR-0035)
**Contexte.** Question posée : « peut-on produire de l'alpha plutôt que de seulement démontrer ce
qui échoue ? » En cherchant POURQUOI rien ne passe jamais, j'ai trouvé la réponse dans le code,
pas dans les marchés.

**Le défaut, mesuré.** `deflation_params` calcule `sr_std` sur les Sharpe **annualisés** stockés au
ledger, et le DSR le compare à un Sharpe **par période**. Sur le ledger réel : `sr_std = 0,972`
⇒ `sr_star = 1,721` par barre ⇒ il fallait un Sharpe **annualisé de 27** (quotidien) pour franchir
le gate. Aucun candidat ne pouvait passer. Latent jusqu'à ce que le ledger contienne 2 Sharpe —
le correctif de juillet avait réparé le repli, pas le chemin nominal.

**Correctif (ADR-0035).** Seuls les essais à périodicité CONNUE entrent dans `sr_std` ; les autres
sont exclus, jamais devinés. Moins de deux ⇒ repli `√(1/n)` (H0 de Bailey-LdP). `preset_lab` et
`alpha_lab` enregistrent `periods_per_year` ; `alpha_lab` passe désormais un Sharpe par période au
DSR. `deflation_diagnostic()` rend la déflation auditable. 6 tests de non-régression.

**Effet.** Le seuil passe à ~0,65 de Sharpe annualisé sur 7 ans mensuels. Sharpe 1,5 : DSR 0,00 la
veille, 0,98 aujourd'hui. Sharpe 0,30 : toujours rejeté. Le gate redevient falsifiable — ni
complaisant, ni impossible.

**Conséquence de méthode.** Tous les verdicts DSR antérieurs sont invalides sur cette composante.
Un rejet qui tenait par le placebo, le PBO ou le sabotage reste un rejet ; les autres sont à
ré-établir. C'est exactement ce que `make alpha-lab` et `make preset-lab` produiront au prochain
run sur données réelles.


## Session 2026-08-20 (5) — `make alpha-lab` : 5 hypothèses pré-enregistrées, passées au gate
**Contexte.** « je veux de l'alpha ». Constat honnête d'abord : la seule source de données
réelles dans le conteneur est l'outil MCP FMP, dont chaque réponse transite par le contexte —
impossible d'y construire un panel crédible. Les autres hôtes (stooq, yahoo, binance, nasdaq)
sont refusés par la politique du proxy. Donc : livrer un LABO que le Mac exécute en une
commande, plutôt que fabriquer un résultat.

**Livré.**
- `packages/research/alpha_hypotheses.py` : 5 hypothèses **pré-enregistrées** (paramètres figés
  a priori, aucune grille) — H1 momentum 12-1 (contrôle), H2 momentum RÉSIDUEL
  (Blitz-Huij-Martens), H3 basse vol idiosyncratique (Ang), H4 reversal 5 j, H5 proximité au
  plus-haut 52 semaines (George-Hwang) — plus un moteur transversal commun : quintiles,
  z robuste, dollar-neutre ou long-only, `exec_lag=1`, coût sur |Δposition|.
- `scripts/alpha_lab.py` + `make alpha-lab` : chaque hypothèse × {long/short, long-only} passe
  les 4 étages (placebo par **permutation du classement en coupe** → DSR déflaté par le ledger
  → PBO/CSCV sur les 10 configurations → sabotage), verdict compact, essais logués.

**Un vrai bug trouvé et corrigé en cours de route.** La première version résidualisait H2 et H3
sur la fenêtre où le signal est ensuite MESURÉ. Retirer des composantes ajustées sur les mêmes
points rend le résidu cumulé anti-persistant **par construction** : le signal devient contrarian
sans qu'aucune information de marché n'intervienne. Mesuré : Sharpe brut **−0,68 sur un panel
sans alpha** avant correction, ≈ 0 après. Correctif : loadings estimés sur une fenêtre
**antérieure** puis appliqués hors échantillon. C'est la même faute que résidualiser un alpha
sur des facteurs plein-échantillon, à une échelle plus discrète — et elle est désormais figée
en test.

**Validation du banc (synthétique, aucune mesure d'alpha).**
- *Calibration* : sans signal implanté, les Sharpes bruts des 5 hypothèses restent autour de 0
  sur 3 tirages.
- *Puissance* : avec une dérive idiosyncratique implantée, H1 passe de +0,19 à +0,44 — si le
  banc ne voyait pas un effet PRÉSENT, ses négatifs ne vaudraient rien.
- *Démonstration du gate* : sur un panel quasi-bruit, H1 long-only affiche **Sharpe 1,44 et
  CAGR 28,8 %** — et le gate le **rejette** (DSR 3 %). C'est exactement ce que le labo doit
  faire, et l'illustration la plus utile de pourquoi les backtests flatteurs abondent.

**Ce que ce labo NE corrige PAS, et qui est écrit en tête du script** : univers d'aujourd'hui
(biais du survivant, F9) et prix rétro-ajustés (F1). Un positif ici est un CANDIDAT à re-tester
après la vague 1, jamais une conclusion.


## Session 2026-08-20 (4) — Audit board 4 piliers : Hurst, HMM causal, netting Core/Satellite
**Contexte.** « fais-le toi » + audit de `main` selon les 4 piliers (quant, architecture,
cockpit, business). PR **#324** ouverte pour les travaux précédents.

**Fait (+22 tests).**
- `packages/regime/hurst.py` : R/S avec correction **Anis-Lloyd** et bande nulle par
  permutation. Piège figé en test : le R/S BRUT renvoie H = 0,566 sur du bruit pur (on
  conclurait « tendance » sur une marche aléatoire) ; corrigé, 0,507. Verdict opérationnel :
  persistant → momentum, anti-persistant → arbitrage statistique, dans la bande → **aucune
  allocation**.
- `packages/regime/hmm_causal.py` : Baum-Welch complet, fenêtre expansive, probabilité
  **filtrée** (jamais lissée ni Viterbi), réordonnancement des états par volatilité,
  hystérésis. **Correctif du finding F3.** Vérifié sur 2 régimes connus : σ [0,50 ; 2,51] pour
  [0,5 ; 2,5], diagonale 0,97 pour 0,97. Sentinelle de non-fuite : troncature ⇒ chemin
  identique. Écart chiffré du lissage : Viterbi 96,9 % contre 94,5 % pour le filtre causal —
  c'est le prix de l'honnêteté, et il est petit.
- `packages/portfolio/netting.py` : net / brut / exécuté, coût du conflit en bps, politiques
  `net` · `core_priority` · `block`, livres virtuels. **Correctif du finding F13.**
- [[19_AUDIT_BOARD_4_PILIERS]] : note d'audit des 4 piliers.

**Trois findings nouveaux.**
- **F11** — aucun calendrier de marché dans le dépôt (grep vide). Crypto 24/7 et séances
  régulées partagent la même boucle : l'agrégation 1 h → 4 h → Weekly est une **fuite
  structurelle** (barre Weekly étiquetée lundi mais close vendredi).
- **F12** — le moteur d'exécution est **synchrone et piloté par cron** ; `asyncio` n'existe que
  dans `apps/api` et le serveur MCP. Une poche crypto 24/7 ne peut pas réagir à une cascade.
- **F14** — pas de machine à états d'ordre ni de log d'événements immuable (le journal
  enregistre des trades, pas des transitions).

**Décidé.**
- **Moteur C++20 lock-free écarté** : à l'horizon 1 h, le budget de latence est de plusieurs
  secondes ; la contrainte est la donnée et le coût, pas le jitter. Ce serait optimiser le seul
  poste non limitant en ajoutant une frontière de langage à un projet d'une personne.
- **Business** : l'actif défendable n'est pas l'alpha (DSR ≈ 0 assumé) mais l'infrastructure
  d'intégrité de recherche. Le produit correspondant est « prouvez que votre backtest n'est pas
  surajusté », pas la vente de signaux — laquelle est en outre une activité réglementée. Les
  multiples d'ARR sont une conséquence, pas un objectif.
- F11 et F12 spécifiés mais **non implémentés** : le calendrier exige une source de jours fériés
  (décision de périmètre), la boucle asynchrone est une refonte du chemin de prod à ne pas mener
  sans un vrai flux pour la valider.


## Session 2026-08-20 (3) — M1 branché au preset : diagnostic d'abord, levier ensuite
**Contexte.** Suite « best practice » : premier branchement d'un des 7 modules, choisi pour son
rapport valeur/risque — la covariance décide de tout ce qui est en aval.

**Fait (910 tests verts, +9).**
- **Nouveau module `packages/backtest/cov_risk.py`** (95 l.) : extraction de `_cov_annual` hors de
  `preset_backtest.py` (661 l., au-dessus du plafond de 400 — on ne l'aggrave pas), plus
  `cov_diagnostic`, `cov_diag_annual` et la **porte d'entrée unique `cov_for_step`** partagée par
  le rail backtest ET le rail production, pour qu'ils ne puissent plus diverger.
- **Le diagnostic est TOUJOURS calculé, le débruitage JAMAIS par défaut.** Décision structurante :
  on veut savoir si le preset optimise du signal ou du bruit **sans toucher aux chiffres publiés**.
  `cov_diag` (k médian, q, % de pas dégradés, verdict) apparaît dans la sortie de `preset_backtest` ;
  `cov_denoise=True` est le seul chemin qui modifie la covariance.
- **Dégradation honnête** : moins de 2 directions distinguables du bruit ⇒ covariance DIAGONALE,
  donc ERC = inverse-vol. C'est ce que la matrice permet d'affirmer, ni plus ni moins.
- **`make preset-lab`** : config `+covariance débruitée RMT` + section « COVARIANCE —
  EXPLOITABILITÉ » imprimée même sans activer le levier.

**Deux défauts trouvés par mes propres tests, corrigés.**
1. `cov_for_step` appelait le diagnostic sans garde : un diagnostic KO tuait le backtest. Un calcul
   purement observationnel ne doit JAMAIS pouvoir casser un run → try/except + test dédié.
2. Le Sharpe publié est arrondi à 0,1 : il ne discrimine pas deux configurations proches. Les tests
   de non-régression comparent désormais les COURBES, pas les métriques arrondies.

**Observation (synthétique, donc UNCALIBRATED).** Sur 8 marches aléatoires indépendantes,
`k_signal` médian = 0 et le débruitage replie sur l'inverse-vol à 100 % des pas — comportement
attendu et correct : sans structure commune, il n'y a rien à optimiser transversalement.
Le chiffre qui compte est celui des **données réelles**, à produire sur le Mac (TODO M1).

**Décidé.** Aucune activation en production : le flag reste à False des deux côtés. L'activation
passera par une PR portant les chiffres de `make preset-lab` sur données réelles, comme pour tout
levier (garde-fou CLAUDE.md : jamais d'activation silencieuse).

## Session 2026-08-20 (2) — 7 modules avancés : RMT, CPCV, Almgren-Chriss, portage, alt-data
**Contexte.** Suite de l'audit 5 axes : demande de spécifications exécutables sur 7 modules
(matrices aléatoires, labellisation/CV combinatoire, décroissance d'alpha, exécution optimale,
queues + financement, quantamental NLP, pipeline alt-data + overlays).

**Livré — code (901 tests verts, +50 nouveaux, aucun câblage prod).**
- `packages/portfolio/rmt_denoise.py` : bornes de Marčenko-Pastur, nombre de facteurs par
  point fixe **et** écart spectral, débruitage à valeur propre résiduelle constante (trace
  préservée), détonage, rang effectif, chaîne MP → Ledoit-Wolf, **verdict** d'exploitabilité.
- `packages/ml/cpcv.py` : CV combinatoire purgée + embargo, `phi = C(n,k)·k/n` chemins,
  refus explicite d'échantillons non triés (la purge serait illusoire).
- `packages/ml/uniqueness.py` : concurrence, unicité moyenne, poids par attribution de
  rendement, décroissance temporelle, **taille d'échantillon effective**.
- `packages/execution/almgren_chriss.py` : `kappa` par résolution de cosh, trajectoire sinh,
  coût espéré/variance, frontière efficiente d'exécution, plafond de participation.
- `packages/execution/funding_costs.py` : marge, rebate de prêt de titres, dividendes short,
  coût du capital bloqué, **frais d'emprunt maximal supportable**.
- `packages/ranking/orthogonalize.py` : z robuste médiane/MAD, z intra-groupe avec taille
  minimale, QR séquentiel centré, projection de neutralisation, combinaison `Omega⁻¹·ic`.
- `packages/research/causality.py` : bêta incomplète + p-value de Fisher **sans scipy**,
  Granger bidirectionnel, information mutuelle Miller-Madow + permutation, `pit_align`, Šidák.

**Livré — guide.** [[18_MODULES_AVANCES]] (index, blueprint d'assemblage, correspondance avec
le framework de screening en 5 modules) + `vault/18_UPGRADE/` : M1 RMT, M2 labellisation/CPCV,
M3+M4 décroissance et exécution, M5 queues et financement, M6 quantamental, M7 alt-data.

**Trois résultats non triviaux.**
1. **Le seuil MP seul sur-détecte** quand quelques facteurs absorbent la trace (5 facteurs
   vrais → `k_mp = 15`, mesuré). L'écart spectral retrouve k exactement sur 1, 3 et 5 facteurs :
   le module renvoie les deux, et `k_mp` est documenté comme borne supérieure.
2. **200 labels de 10 barres décalés de 1 valent moins de 30 observations** (`n_eff` mesuré).
   Tout test de significativité utilisant 200 se trompe d'un facteur 2,6 sur les écarts-types.
3. **Le temps caractéristique d'exécution `1/kappa` ne dépend pas de la taille de l'ordre**
   (testé) : la taille change le coût, jamais le rythme. `lambda` est une décision de
   politique de risque, pas un paramètre à optimiser sur l'historique.

**Deux trous assumés, non comblés.** Surface de volatilité et couverture optionnelle (aucune
chaîne d'options ingérée — c'est une décision de périmètre, pas une tâche) ; optimisation CVaR
par programmation linéaire (Rockafellar-Uryasev spécifiée en M5 § 3, non codée car non
testable dans ce conteneur — `scipy` est déclaré dans le groupe `quant`).

**Décidé.** Priorité inchangée malgré l'attrait des 7 modules : tant que l'historique de prix
mute (F1) et que le coût est un forfait linéaire (F2), ajouter des sources exogènes ajoute des
occasions de se tromper avec plus de conviction. L'alt-data est le **dernier** chantier.


## Session 2026-08-20 — Audit institutionnel 5 axes + 4 modules de référence
**Contexte.** Demande d'audit « MD quant » sur le corpus Grinold-Kahn / Isichenko / Paleologo /
Chan / Taleb / Mandelbrot / Wilmott, traduit en spécifications pour la plateforme et les robots
multi-timeframes (1 h → Monthly).

**Livré — guide (vault).** [[17_AUDIT_INSTITUTIONNEL]] (scorecard, 10 findings de code datés
avec chemin/ligne, séquence de travail) + `vault/17_UPGRADE/` : [[AXE1_DATA_PIT]] (schéma
bitemporel, algorithme d'ajustement corporate actions, security master, conventions intraday),
[[AXE2_ALPHA_LOI_FONDAMENTALE]] (alpha = vol·IC·z, souffle effectif, chevauchement/Newey-West,
orthogonalisation par projection + Marchenko-Pastur), [[AXE3_QUEUES_REGIMES]] (Hill, GPD par
PWM, CVaR, HMM causal, cointégration), [[AXE4_SIZING_FRICTIONS]] (Kelly à queues épaisses,
impact racine carrée, admission), [[AXE5_EXECUTION]] (fill L1/L2, machine à états, dead-man).

**Livré — code (851 tests verts, +32 nouveaux, aucun câblage prod).**
- `packages/research/breadth.py` : N_eff/T_eff, coefficient de TRANSFERT, IR = IC·√BR·TC,
  `ic_required`, `optimal_horizon` (h* ≈ 1,81 × demi-vie, dérivé et vérifié numériquement).
- `packages/execution/impact.py` : impact en racine carrée avec vol ET volume **de la fenêtre**
  d'exécution, taille max sous budget, plafond POV, test d'admission alpha vs coût.
- `packages/research/cointegration.py` : ADF avec valeurs critiques **Engle-Granger**, ratio de
  couverture, demi-vie OU, correction multi-tests, verdict bidirectionnel.
- `packages/portfolio/sizing/kelly_fat_tail.py` : Kelly sur distribution empirique + queue GPD,
  borne de ruine, fraction dérivée d'un budget de drawdown (λ = 2/(1 + ln ε / ln b)).

**Trois findings qui changent des décisions.**
1. **F1** — `auto_adjust=True` + `_split_drift` : l'historique de prix MUTE après chaque split
   ou dividende. Deux backtests lancés à deux dates ne sont pas comparables — or DSR et PBO
   comparent exactement cela. Correctif : prix bruts immuables + table `corporate_action`,
   facteur calculé à la lecture avec `as_of`.
2. **F2 / axe 4 § 4.5** — avec les barèmes RÉELS déjà encodés dans `costs.py`, l'horizon minimal
   viable est ≈ 34 h (actions/Alpaca), ≈ 64 h (Binance), ≈ 219 h (**BitMart**). Aucun robot
   1 h / 4 h ne passe le test d'admission avec les courtiers configurés : le levier n'est pas le
   signal, c'est le coût (venue moins chère + exécution maker).
3. **F10** — `fraction=0.25` du Kelly correspond à un budget de drawdown de 50 %, pas au
   `QUANT_DD_TARGET=0.25` affiché ailleurs (qui impose λ ≈ 0,175). Deux appétits pour le risque
   contradictoires dans le même dépôt.

**Décidé.** Aucun des 4 modules n'est câblé : ils entrent en production par le gate
(`15_CERTIFICATION.md`) comme n'importe quel candidat. Tous les paramètres (Y de l'impact, κ de
la bande, seuils de demi-vie, IC supposés du tableau d'admission) sont **UNCALIBRATED** — les
ordres de grandeur suffisent à trancher la question du 1 h, pas à dimensionner une position.


## Session 2026-07-17 (2) — Research-integrity : fill t+1, sabotage Δposition, delta survivorship
**Contexte.** « fait tout selon best practices » sur la roadmap XL/L/M. Décision honnête : NE PAS
big-bang le god-object (2500 l., non vérifiable depuis le cloud) ni raser des pages front riches
sans app runnable. Fait le lot **backend research-integrity**, 100 % testable ici — c'est le wedge.

**Fait (828 tests verts, +11 nouveaux).**
- **M-1 · Fill t+1** : param `exec_lag` dans `preset_backtest` (défaut 0 = comportement historique
  EXACT, non-régression testée). exec_lag=1 → exécution au close t+1 (le close du jour de signal
  n'est pas exécutable = mini look-ahead). Config « fill t+1 » ajoutée à `make preset-lab` (chiffre
  l'écart : ~‑0,05 Sharpe sur synthétique).
- **M-2 · Sabotage sur Δposition** : `stress_returns`/`sabotage_verdict` acceptent `turnover`
  (scalaire ou tableau) → coût ∝ |Δposition|, plus « à chaque barre » (qui surfacturait un faible
  turnover comme un B&H). Rétro-compatible (None = worst-case documenté).
- **XL-1 · Delta de survivorship** : nouveau module `survivorship_delta.py` (séparé — ne grossit
  pas le god-object) : relance le preset survivants-seuls vs +délistés, publie Δ Sharpe/CAGR/maxDD.
  Câblé dans `make preset-lab`. Dépendance dure : prix des délistés en base (`make ingest-delisted`) ;
  sinon message honnête, jamais de chiffre inventé.

**Stagé explicitement (raisons).** XL-2 refactor snapshot/main (risque de casse silencieuse sans
app runnable → par tranches) ; L-3 fusion pages front (contenu riche, exige vérif visuelle) ;
L-4 ML CV calendaire (touche la section ML de snapshot, à vérifier sur données réelles).

## Session 2026-07-17 — Dashboard qualité des trades + simulateur Monte Carlo navigateur
**Contexte.** Demande : tuiles KPI façon terminal (trades, win rate, profit factor, gains/pertes)
+ simulation Monte Carlo interactive, inspirées de captures d'un autre outil.

**Fait (tsc + next build verts).**
- `components/DashboardStrips.tsx` : `TradeStatsRow` (count, win rate, profit factor, gain/perte
  moyens, meilleur/pire — depuis `trade_stats` déjà calculé, étiqueté « backtest ») + `HonestyStrip`
  extrait (page dashboard repassée sous 400 l.).
- `components/McFan.tsx` : fan chart réutilisable (bandes p5–p95/p25–p75 en UNE teinte accent,
  médiane 2 px, labels directs des finals, crosshair+tooltip, ligne capital de départ).
- `components/Simulator.tsx` sur `/risk` : Monte Carlo **100 % navigateur** (marche sur le site
  statique, zéro endpoint) — bootstrap par BLOCS 10 j (préserve le clustering de vol ; mode iid
  affiché comme « naïf ») des rendements passés (backtest preset, ou courbe réelle si ≥60 j),
  contrôles horizon/itérations/capital/frais/seed, sorties médiane/p5/p95, proba de perte, proba
  de ruine (−50 %), DD médian/p95. Note d'honnêteté : distribution conditionnelle au passé, PAS
  une prédiction.

**Décidé.** Pas de simulateur côté API : le client-side est la seule voie compatible GitHub Pages
0 € — et le backend `mc_projection` existant reste la référence reproductible (seed fixe).

## Session 2026-07-15 — Remédiation audit comité (4 critiques + P0) · ménage sections · labo Sharpe
**Contexte.** Audit hedge-fund 5 sièges rendu (moyenne 69/100) : DSR non falsifiable, fail-safe
d'exécution inversé, kill-switch manuel, prod pouvant mourir en vert. Demande : « corrige tout,
supprime prediction markets + crypto onchain, améliore Sharpe/Sortino/alpha ».

**Fait (tout testé, 818 tests verts).**
- **DSR réparé (CRITIQUE #1)** : `psr.py` — `sr_std` par défaut passe de 1.0 (seuil ≈ Sharpe 7
  annualisé, « DSR≈0 » vrai par construction) à **√(1/n)** (hypothèse H0 Bailey-LdP). Vérifié :
  Sharpe 1,6 ann. → DSR 0.999 ; Sharpe 0 → 0.03. `ledger.deflation_params` replie sur None ;
  snapshot déflate avec le N réel du ledger. **⚠️ re-runner les 8 hypothèses rejetées (TODO C).**
- **Fail-safe d'exécution corrigé (CRITIQUE #2)** : `packages/execution/live_guards.py` —
  positions/equity illisibles ⇒ broker ÉCARTÉ (inconnu ≠ zéro ; l'ancien « détenu=0 » rachetait
  tout le portefeuille). + suppression du repli 10 000 $ en live (broker à clé morte ne trade plus).
- **Kill-switch DD RÉEL (CRITIQUE #3)** : `dd_kill_switch` branché dans `run_live` — drawdown du
  compte depuis le pic (equity_history) ≤ `QUANT_INTRADAY_DD` (−15 %) ⇒ exposition 0 + CRITICAL.
- **Fail-loud (P0)** : run_live exit 3/4 si broker mort/positions KO ; cron_live.sh propage le code ;
  paper.yml step Telegram `if: failure()` + secrets TELEGRAM_* ; **keepalive.yml** mensuel (crons
  GitHub auto-désactivés après 60 j sans commit — condition n°1 du « NON » CTO).
- **Courbe du RDV 06/08 sauvée (P0)** : `hf_journal.py` pousse/tire aussi `equity_history.json`.
- **Badge « MODÉLISÉ » (P0 produit)** : nature des KPIs héros du dashboard affichée AVANT les chiffres.
- **Mismatch T10Y2Y/T10Y3M (1 mot ×4)** : classifieur/real_macro/synthetic alignés sur T10Y3M ingéré.
- **Ménage (réduction 50 %)** : prediction_markets + crypto_onchain supprimés PARTOUT (12 fichiers
  supprimés dont growthepie/crypto_report orphelins ; snapshot/main/dump_static/api.ts/macro page/
  Makefile/pages.yml nettoyés).
- **Sharpe/Sortino/alpha (gaté, pas d'overfit)** : `_cap_weights` (déduplique 3 copies) +
  `_adaptive_cap` corr-aware **branché sur le rail prod** (`preset_latest_weights` : cap 10 %→5 %
  si corr moyenne > 0,60) ; params `max_weight`/`corr_tighten` dans `preset_backtest` ;
  **`make preset-lab`** : 4 configs a priori (base/+cap/+overlay DD-vol/+les deux) mesurées puis
  GATÉES (mieux sur Sharpe ET maxDD), essais logués au ledger. Données réelles absentes du
  conteneur → **UNCALIBRATED ici, à runner sur le Mac (TODO A)**.

**Décidé.** Aucun levier de rendement activé sans mesure : le cap adaptatif est un CONTRÔLE DE
RISQUE (défensif, prod-only), les leviers de Sharpe attendent le verdict `preset-lab` sur données
réelles. L'amélioration honnête du Sharpe commence par un thermomètre réparé.

## Session 2026-07-05 — Clôture P0-1/P0-2 : verrou anti-fuite + alpha réel post-fix mesuré
**Contexte.** Reprise après limites d'usage. Demande initiale « écran suivant UI » ré-arbitrée par
l'utilisateur en « d'abord corrige la fuite de données » (P0-1, marqué « avant toute feature »).

**Constat d'audit (vérifié, pas supposé).** Le correctif *code* de P0-1 était **déjà dans `main`**
(`f78e18f`, 02/07) : `preset_equity_daily`/`preset_trade_log`/`preset_ledger` + `preset_backtest`
sélectionnent l'univers par momentum prix-only (`_price_universe`) ; aucun appelant ne passe
`legacy_quality_universe=True` ; le manifeste était déjà dé-chiffré. Le TODO n'avait juste pas été coché.
**Trou réel identifié : aucun test ne verrouillait la non-régression** (la fuite pouvait revenir en silence).

**Fait.**
- `1f51dde` test(backtest) : **`tests/backtest/test_dashboard_no_leak.py`** — 2 dicts `quality`
  OPPOSÉS ⇒ sortie strictement identique pour les 3 fonctions dashboard + `preset_backtest` (défaut) ;
  et le mode `legacy_quality_universe=True` **diverge** bien (le test a du mordant, pas un faux positif).
  4 tests verts ; suite backtest 47/47.
- **Mac** : `make vault-sync` → `Preset_Performance.md` régénéré post-fix :
  **`alpha_annual` 0.0755 → 0.0445** (la fuite gonflait l'alpha d'~3 pts — preuve empirique de P0-1).
  Beta QQQ 0.37, R² 0.63, maj 2026-07-05.
- Matin : #289 squash-mergée + branche resynchronisée (mobile tap-to-load des lives crypto,
  `QUANT_NEWS=1` en ligne, YTD secteurs en médiane, univers sans délistés, registre cliquable).

**Décidé (lecture honnête).** Le 4,45 % restant est un **alpha d'attribution** (régression vs QQQ),
**pas un alpha gaté** (placebo/DSR/PBO/sabotage jamais passés dessus). Claim public inchangé :
**DSR≈0, edge prouvé = réduction du drawdown**, pas la direction. P0-1/P0-2/P0-3 fermés au TODO.

**Prochaine étape.** Écran suivant UI (BLOC 5, plan avant code) sur `feat/ui-analytics` — PR #294
(dashboard) toujours ouverte à merger d'abord. P0-4 Phase 2 (round-trip journal) en file.

## Session 2026-07-05 (suite) — #294/#295 mergées · écran /positions · P0-4 Phase 2 (round-trip)
**Fait.**
- **Merges** : #294 (dashboard) + #295 (verrou anti-fuite + vault) squash-mergées, branche resynchronisée
  → rebuild Pages déclenché (dernière version en ligne).
- **Écran 2 BLOC 5 — `/positions` « réel vs cible »** (PR #296) : fusion positions réelles × cible preset
  par poche de capital, barre d'écart divergente + bande de non-trading 3 %, HHI/N effectif/top 3, badge
  earnings, SortableTable (tri/filtre/CSV) ; route `/api/positions` expose `preset_allocation` +
  `earnings_risk`. `tsc` + build statique 25 pages + 27 tests API verts.
- **Audit avant code (anti-doublon)** : BLOC 1a/1b/1c et P0-SI-LIVE #4/#5 étaient DÉJÀ livrés dans `main`
  via **#293** (idempotence + clientOrderId, fills partiels + alerte CRITICAL, wiring alertes). TODO et
  CLAUDE.md mis à jour (plus aucun P0-SI-LIVE ouvert ; live toujours conditionné au RDV 2026-08-06).
- **P0-4 Phase 2 — round-trip du journal** : `packages/execution/live_roundtrip.py` (FIFO, scission de
  lot `-Xn` déterministe, UPSERT idempotent, MFE/MAE depuis la série OHLC du snapshot) + `run_live.py`
  capture les VENTES et ferme les lots. Prix de sortie = FAIT broker (fill du jour → ticker → position ;
  sinon lot laissé ouvert). Refactor `_reconcile` (extraction `_broker_targets`, règle 50 l).
  6 tests round-trip ; **suite complète 811 verts**. Fix annexe : `test_alpaca_crypto` importorskip
  (env sans SDK alpaca).

**Décidé.** Round-trip côté chemin de PROD uniquement (`run_live`) — cohérent avec la décision (b) du
2026-07-04 (journal direct, pas de 2e chemin via LiveEngine). Reste une DÉCISION ouverte : sort de
`LiveEngine` (supprimer ou rétrograder) — pas de code tant que non tranché.

**Prochaine étape.** Merge #296 (pilote CI armé) → expectancy/Kelly calibrables dès que des round-trips
réels s'accumulent (RDV 2026-08-06). Écran 3 UI à planifier (`/screener` ou analyse portefeuille).

## Session 2026-07-04 — BLOC 5 : dashboard institutionnel (equity+underwater synchronisés) [PR #294]
**Contexte.** Branche isolée `feat/ui-analytics` (BLOC 5, jamais mélangée aux brokers). Reprise d'un travail en
cours non commité : refonte du **Dashboard principal** en écran d'analyse institutionnel, 100 % données réelles
via l'API existante (`useDashboard`/`usePositions`/`useAnalytics`). Aucun `packages/` ni `--live` touché.

**Fait (1 commit `d2d11c1`, 8 fichiers `apps/web`).**
- **`PerformancePanel`** (nouveau) : `EquityChart` au-dessus du `DrawdownChart` underwater, fenêtre de zoom
  `win` partagée → axes X synchronisés + `syncId` recharts (crosshair commun).
- **`EquityChart`** refondu : downsampling **LTTB** (~600 pts, 60 fps sur 2644 pts), zoom par glisser-sélection
  (`ReferenceArea`), `memo`. Rétrocompatible (sans `onWin` → zoom off).
- **`DrawdownChart`** (nouveau) : underwater dérivé client (`v/running_max−1`).
- **`PositionsAlertsTable`** (nouveau) : positions réelles triées par exposition (P&L plein), alertes
  `earnings_risk`, liens `/positions` et `/trades`.
- **`MetricCard`** : delta discret vs N−1. **`RegimeBanner`** : tokens régime outline + `pulse-dot`, zéro hex.
  **`globals.css`** : route `.plain` (dashboard sobre, coupe le décor animé global).

**Bug trouvé & corrigé (à la reprise).** `DrawdownChart` échantillonnait LTTB sur des objets renommés `{t, dd}`
alors que `lttb` clé sur `.v` (masqué par `as any`) → aires `NaN` → LTTB dégénérait en « 1er point par bucket »,
**creux perdus, pire DD sous-estimé**. Fix : downsampler sur `underwater()` (porte `.v`) puis référencer `v`.

**Vérifié.** `tsc --noEmit` : 0 erreur sur les fichiers du dashboard (seules erreurs pré-existantes hors périmètre :
`landing/Scene.tsx`, three.js). Contrôle **visuel headless** (Chrome) du dashboard rendu avec données réelles
(2644 pts equity, 2 benchmarks, 39 positions, régime expansion/risk-on) : les 6 composants s'affichent, underwater
synchronisé, et **« pire : −25,4 % » = KPI Max DD** (`metrics.max_drawdown = −0.254`) → preuve que le fix LTTB
préserve le creux.

**Décidé.** **ADR-0030** : underwater dérivé client + downsampling LTTB partagé (invariant « clé sur `.v`,
jamais après renommage »).

**Prochaine étape.** PR #294 ouverte (vers `main`). Écran suivant de BLOC 5 (candidats : `/positions`, `/screener`,
analyse portefeuille dédiée) — plan avant code. Reste hors branche : P0-SI-LIVE #4/#5 brokers, P0 full-review preset.

## Session 2026-07-02 (soir) — Audit adverse institutionnel (6 axes, scoring double, preuves exécutées)
**Contexte.** Audit technique ultra-sévère demandé (6 axes : Data / ML / Exécution / Portefeuille / Risque-Backtest /
MLOps). Barème **recalibré sur le scope assumé** (daily/EOD, paper, 0 € infra, DSR≈0 = constat honnête) : HFT/tick-data/
ML-lourd/infra-orchestrée = **(B) hors-scope, exclus du calcul** ; sévérité max sur l'in-scope (PIT, look-ahead, coûts,
gates, qualité data, repro, secrets, honnêteté chiffres). Méthode : **preuve exécutée `fichier:ligne` obligatoire**, un
finding non prouvé = retiré. Purge P0-2 en amont : manifeste dé-chiffré (commit `67df65d`), dashboard + `Preset_Performance.md`
régénérés par le pipeline anti-fuite.

**Fait.**
- **Cartographie** des 6 axes par 6 agents d'inventaire read-only (`fichier:ligne`, y compris absences).
- **6 findings capital/vérité prouvés ou retirés** : **#4 idempotence Bitmart** (`bitmart_broker.py:99`, retry redouble
  l'ordre) → **CONFIRMÉ capital** (gaté `dry_run`/`QUANT_NO_CRYPTO_LIVE=1`) ; **#5 fills partiels** (`live_engine.py:111`,
  `"filled"` strict → position non trackée) → **CONFIRMÉ** ; **#1 fuite Platt** (`snapshot.py:670-675`) → confirmé mais
  **RÉTROGRADÉ LOW** (métrique in-sample, `cal`/`p_cal` n'atteignent ni probas servies ni sizing → prémisse « contamine
  le sizing » réfutée) ; **#3 doublons DSR×3/PBO×2** → **reclassé dette** (2 impl. mortes, chaque call-site bien lié) ;
  **#2 `calibrate.py:34`** → **RETIRÉ** (exécuté, bon `import` psr, pas de crash) ; **#6 `.env`** → **RETIRÉ PASS**
  (gitignoré + jamais dans l'historique `git log --all`).
- **Scoring /20** : Data 15 · Risque 15 · Portefeuille 15 · ML 13 · Prod 11 · Exécution 10. **Double moyenne : égal-pondéré
  13,2 / pondéré-risque 13,7.** Écrit dans `vault/14_FULL_REVIEW.md` (section « Audit adverse 02/07 »).

**Décidé.** **ADR-0029** : long-only = scope v1 assumé (pas une régression, `sim_broker.py:43`). Findings capital #4/#5
classés **P0-SI-LIVE** (bloquants avant activation broker réel) ; #1/#3 en **P2**. Garde-fou ajouté à `CLAUDE.md` :
« ne jamais passer un broker en live sans avoir fermé ses P0-SI-LIVE ».

**Prochaine étape.** Corriger #4 (clientOrderId ccxt + court-circuit idempotent) et #5 (gérer `PARTIALLY_FILLED` +
brancher l'alerte de réconciliation) — **demain, pas ce soir** (aucun code ce soir). Filet opérationnel : brancher
l'alerting (Telegram/Discord codé mais non câblé) reste le plus gros trou prod (axe 6). P0 full-review (fuite univers
preset) toujours en attente du re-run Mac complet.

## Session 2026-07-02 (suite) — Persistance du journal de trades + capture features (P1-1 clos)
**Contexte.** Suite directe du full-review : le finding P1-1 (journal en mémoire, 0/100
`features_snapshot`, calibrations UNCALIBRATED N=0). Branche `feat/journal-features-snapshot`.

**Fait (5 commits atomiques).**
- `834338a` feat(storage) : **`SqliteTradeJournal`** — DB dédiée `data/journal.db` (séparée du cache
  prix régénérable), interface drop-in de `TradeJournal` (append/all/pnls/to_csv), `features_snapshot`
  en **JSON TEXT**, **UPSERT idempotent** sur `id`, migration auto du schéma, **colonne `legacy`
  indexée & requêtable** (`WHERE legacy=0` pour la calibration), warning si trade live sans features.
- `c2c4d36` feat(execution) : `LiveTradingEngine` persiste par défaut ; backtest garde l'in-memory.
  Le `features_snapshot` transite **inchangé** depuis la couche décision (`Signal.features` → `_Open`
  → `TradeRecord`), **jamais recalculé au fill** (anti look-ahead). Sites synthétiques (démo + tests)
  isolés en `:memory:` pour ne pas polluer le journal réel.
- `f64f5f6` feat(scripts) : `import_legacy_fills.py` — fills Alpaca existants → `features={}` + `legacy=1`,
  id déterministe (idempotent), dry-run par défaut. **Aucune reconstruction a posteriori** (= anti-fuite).
- `8dfe308` test(storage) : 8 tests — round-trip, idempotence, JSON round-trip, colonne legacy, warning
  live vs silence legacy, + **contrat anti-fuite de bout en bout** (snapshot journalisé = dict de décision
  + `ref_price` = prix d'entrée, jamais un prix futur).
- `3c1c771` fix(research) : **corrige le test breakout rouge pré-existant** — verdict : le **code** était
  bugué (canal plat → dérive flottante de la bande → fausse cassure à chaque barre → capture du rendement
  de la barre de cassure = mini look-ahead). Tolérance relative sur la condition. Hygiène uniquement :
  **la stratégie reste REJETÉE** (DSR 0 / PBO 0,88).

**Décidé.** **ADR-0028** : `SqliteTradeJournal` (SQLite stdlib, DB séparée, UPSERT idempotent, flag
`legacy` porté par la **couche storage** — pas par `TradeRecord` qui reste pur).

**Fait (données réelles).** `import_legacy_fills.py --commit` → **137 fills** importés dans
`data/journal.db` (`legacy=1`, features vides), réimport idempotent vérifié (reste 137), `data/journal.db`
bien gitignoré. `make test` : **773 passed, 2 skipped, 0 failed** (suite entièrement verte).

**Prochaine étape.** Laisser le paper live peupler `legacy=0` avec features réelles (RDV 2026-08-06 :
la calibration MFE/MAE/expectancy/Kelly deviendra possible dès N>0 sur `legacy=0`). P0 full-review
(fuite univers preset) toujours en attente du re-run Mac. Reste P1-2→P1-7.

## Session 2026-07-02 — FULL-REVIEW (revue complète multi-agents) + correctifs P0
**Contexte.** Skill `/full-review` sur la branche `ops-integration` (commit `627a0e2` : ops-kit +
top1pct-pack + certification-kit). 3 sub-agents lancés en parallèle (leakage-hunter, db-auditor,
vault-architect) + quant-critic. Rapport complet → `vault/14_FULL_REVIEW.md`.

**Fait (analyse).** Scores santé : Architecture 6/10 · Données 3/10 · Discipline quant 4/10 · Sync vault 3/10.
- **P0 confirmé (leakage-hunter + quant-critic)** : `preset_equity_daily`/`preset_trade_log`/`preset_ledger`
  sélectionnaient l'univers via la **qualité du jour** sur tout 2015+ (look-ahead + survivorship). `preset_ledger`
  alimente le **dashboard** (`snapshot.py:2081`). Le correctif `legacy_quality_universe=False` n'existait que
  dans `preset_backtest()`. Le claim « alpha 6,9 % corrigé » du manifeste était donc **faux** pour le chemin livré.
- **Mandat données-réelles** : journal = 100 fills Alpaca bruts, **0/100** features/stratégie/PnL, **en mémoire
  uniquement** → MFE/MAE, expectancy, Kelly = **UNCALIBRATED (N=0)**. MacroStore aussi `:memory:`. `adj_close` 99,7 % NULL.
- **top1pct-pack** : 11 modules, **9 orphelins** ; `pbo` dupliqué ; `vol_target` non enregistré.
- **Régression découverte** : `627a0e2` avait écrasé le Sizer `VolTarget` → branche livrée **avec 4 tests rouges**.

**Fait (correctifs P0, 3 commits atomiques).**
- `f78e18f` fix(backtest) : `_price_universe()` partagé (momentum prix-only, PIT) appliqué aux 3 fonctions +
  coûts de turnover nettés dans `preset_equity_daily` (P0-1, P0-3).
- `10d25ff` fix(sizing) : restaure la classe `VolTarget` enregistrée **en conservant** les helpers top1pct
  (suite 761→764 verts).
- `8b5b654` docs(vault) : `14_FULL_REVIEW.md` + `03_TODO.md` + rectificatif `12_MANIFESTE_HONNETETE.md` (P0-2).
- Clôture : ADR-0026 (ops-kit rétro-doc) + ADR-0027 (invariant anti-fuite + honnêteté « artefact »).

**Bloqué / à faire (Mac, données réelles requises).**
- **P0-2 résiduel** : régénérer le dashboard + `Preset_Performance.md` via `make` (les chiffres affichés
  restent des **artefacts** de l'ancien chemin fuité jusqu'au re-run). **Pas de capital réel avant.**
- 1 test rouge **pré-existant** non lié : `test_breakout.py` (off-by-one, code recherche = signal rejeté) → P1.

**Prochaine étape.** P1 : persistance journal + features_snapshot (débloque calibrations) · providers
fondamentaux PIT (`fmp`/`sec` ignorent `as_of`) · dédup `pbo` · câbler modules top1pct · dérive Mermaid/table état.

## Session 2026-06-30 — Multi-timeframe + mobile + rigueur DSR (rétro-documenté le 07-05)
> Entrée écrite a posteriori (trou détecté par l'audit vault du 2026-07-05) — faits tirés des commits.

**Fait.**
- `e38fe3d` (#288) : POC **microstructure** (OFI Cont-Kukanov-Stoikov, vPIN + variante ECDF),
  **sonar** carnet d'ordres (/crypto), alpha-decay/roll-spread/sabotage-sweep, correctifs d'audit
  5 personas (DSR déflaté sur essais DISTINCTS, leak-sentinel `pit_guard`, resolve 3-tiers),
  page « Échecs publiés » (/echecs).
- `a0f7c55` (#289) : graphe live **multi-timeframe** (1h/4h/1j/1sem/1mois, Binance klines + WS),
  sélecteur d'actif, sonar précisé « instantané », `deflation_params` compte les hypothèses
  distinctes par `facteur` (relances ≠ essais), mobile tap-to-load (préparation), QUANT_NEWS=1.

**Décidé.** Rien de câblé au ML : microstructure/peg/breakout restent en RECHERCHE (gate d'abord).

## Session 2026-06-29 (suite 2) — Cockpit crypto LIVE + gate breakout + RAG + croissance
**Fait (gros lot, ~12 PR-commits sur `claude/clever-lovelace-ognwya`, #285→#287).**

**Cockpit crypto enrichi.** Robustesse `_get_json` (retries+backoff → repli **cache disque**
`.cache/crypto`, persistant en CI via `actions/cache` → jamais de `n/d` silencieux) + badge de
fraîcheur. Correctif **peg** (USYC/BUIDL = tokens à *rendement*, plus flaggés « décrochés »).
Sections **Halving** (hauteur de bloc réelle), **Altseason** (dérivé des sparklines), **Dérivés**
(funding multi-CEX normalisé Bybit/OKX/Binance, pattern Coinglass/Velodata en build-time),
**Score d'Accumulation Institutionnelle 0-100** (contrarian déterministe). **Mini-fiche** in-page
(clic → prix/24h/7j + graphe 7j) + items **cliquables** vers CoinGecko + **glossaire** (InfoTip).

**ML honnête — 2 nouveaux négatifs (6e + 7e).** `regime_study` (F&G contrarian BTC) → **BRUIT**
(p=0,905). `breakout` (cassure de canal) → placebo ✅ p=0,039 **mais gate complet** (DSR/PBO/
sabotage via psr/pbo/adversarial) → **REJETÉ** (DSR 0 · PBO 0,88 · sabotage −11,7). **Cas d'école**
du faux positif que le placebo seul aurait laissé passer. Bug corrigé : BTC history via **Binance
klines** (CoinGecko gratuit renvoyait 0). `make regime-study` / `breakout-study`.

**RAG ancré + text-to-filter (Fiscal.ai, mais déterministe).** `vault_rag` → réponse **extractive
citée** [n]→fichier (0 hallucination), `make vault-ask`. `crypto_query` → NL→params→**le code
filtre**, `make crypto-screen`.

**Trio LIVE client-direct** (décision d'archi : proxy serveur **impossible** sur statique → WS
navigateur + REST CORS, `n/d` sinon ; cf. ADR-0025) : **jauge de sentiment** (low-pass 0,25 :
F&G+momentum WS+funding+ΔOI), **graphe** Lightweight Charts (UMD CDN, Coinbase WS, v4 pin),
**analyse experte « Œil de Hasheur »** (CoinGecko+F&G+DefiLlama RWA+Bybit/OKX, sentiment composite
transparent, auto-refresh 90s visible-only).

**Croissance (M5) + landing (M6).** Boucle **partage/embed** (X/Farcaster + iframe `?embed=1`
read-only) — seule loop compatible 0 €/statique/marque ; **profils audités + parrainage refusés**
(backend obligatoire + anti-brand). Landing hero **froid/mathématique** (4 portes dans le hero),
compteur **7 échecs publiés**.

**Auto.** `make live-cron-install` (launchd) → rebalancement **paper** quotidien lun-ven (Alpaca
forcé paper, crypto réel neutralisé).

**Décidé.** Le gate à 4 étages reste **la valeur** : 7/7 hypothèses rejetées, 0 cachée, ML pur. Le
live crypto est du **contexte** (pas un signal). On optimise la variance, pas l'espérance.

**Prochaine étape.** Revue courbe paper **2026-08-06** (inchangée). Optionnel : RAG en outil MCP ;
KDE/K-Means zones de liquidité (→ gate). 

## Session 2026-06-29 (suite) — Cockpit crypto (vue marché, contexte gratuit)
**Fait.** Page `/crypto` + section snapshot `crypto_cockpit` (gatée `QUANT_CRYPTO=1`, best-effort,
build-time → JSON statique). Sources **gratuites, sans clé côté client** : CoinGecko
(global/markets/categories/trending), DefiLlama (chains TVL, stablecoins), alternative.me (Fear &
Greed). Parsers **purs et testés hors-ligne** (`packages/data/crypto_market.py`, 9 tests).
- 6 sections pédagogiques (chacune : donnée + source + explication + `n/d` si la source tombe,
  skeleton, reveal IntersectionObserver respectant `prefers-reduced-motion`) : Aperçu (humeur
  marché **déterministe** = moyenne F&G + cap 24 h + breadth), Pouls (cap/dominance/F&G/TVL),
  Narratifs (catégories), Gagnants/Perdants 24 h, Tendances retail, Stablecoins (taille + écart peg).
- `make crypto-cockpit` (CLI) + route `/api/crypto_cockpit` + lien Nav (groupe Marché).
- Garde-fou maison : **jamais de chiffre inventé** — sentiment et score dérivés des seules données
  réelles présentes ; tout absent → `n/d`. Contexte de marché, **pas un signal d'alpha**.

**Complément ML + Obsidian (même session).** Question : ces données crypto peuvent-elles servir au
ML et à Obsidian ? Réponse honnête, livrée :
- **Obsidian** = oui (contexte, pas de gate) → `crypto_brief.py` (note Markdown **déterministe** depuis
  le cockpit, front-matter, `n/d` si source absente) + `make crypto-brief` → `vault/11_Crypto/`.
- **ML** = faisable mais sous gate. La plomberie existe (`FeatureBuilder` + `MacroStore.as_of`,
  point-in-time). Seuls **F&G** (alternative.me, depuis 2018) et **TVL** (DefiLlama historique) ont
  un vrai historique gratuit ; le reste du cockpit est snapshot-only → non ML-able. Construit :
  `crypto_history.py` (parsers purs historiques) + `regime_study.py` qui **réutilise
  `funding_study.significance`** pour tester le **F&G contrarian sur BTC** (fade |z|>1.5 + placebo).
  `make regime-study`. **Rien câblé au ML/décision** tant que le gate n'est pas franchi (discipline).
- **Contrainte réseau** : l'egress de l'agent **bloque** CoinGecko/DefiLlama/alternative.me (403
  policy) → le verdict du gate se lance **sur le Mac**. Tout est pur + testé hors-ligne (19 tests).

**Prochaine étape.** Lancer `make regime-study` sur le Mac → verdict F&G. Si BRUIT (prior bas, 5/5
négatifs) : 6ᵉ négatif au manifeste. Si SIGNIFICATIF : DSR/PBO puis feature régime `FNG`. Puis
phases suivantes du cockpit (dérivés/funding/OI, altseason, RWA, corrélations, unlocks, ETF, halving)
+ hybride client-live. Revue paper toujours au **2026-08-06**.

## Session 2026-06-29 — Loop Engineering, sabotage, UI cinématique & on-chain crypto (contexte, pas alpha)
**Fait.** ~15 PR (#266→#280), CI verte → merge → resync, 0 €. Réponses *adaptées* à des prompts
externes (Loop Engineering, validation paranoïaque, second-brain, UI Pro Max, Blockchain.com) —
fil conducteur : **voler l'idée utile, refuser le framework redondant**.
- **Loop Engineering** → un seul vrai gap : `packages/research/gate.py` (Checker unique de
  promotion, #266) + `paper-watch` (watchdog dérive paper vs backtest, #267).
- **Validation paranoïaque** → `adversarial.py` : **test de sabotage** (coût×3 + bruit + latence,
  #268) ; le gate de promotion est désormais à 4 étages (placebo→DSR→PBO→sabotage).
- **Second-brain Obsidian** → volé une idée : `vault-lint` (liens morts/orphelins/ADR doublons, #270).
- **UI Pro Max** → landing cinématique R3F/Lenis isolée + 3D code-split (#271) + polish dashboard
  CSS (#272). 3D refusée sur les pages data.
- **Blockchain.com → multi-sources on-chain** : `crypto_onchain.py` (CoinGecko + DefiLlama, sans
  clé, #274) + widget (#276) + **rapport dynamique déterministe** (sentiment 🔴/🟢/🟡 + 3 sections
  style Hasheur) + Growthepie ETH (#279). Paiements/wallet **refusés** (pas de business model,
  dangereux sur site statique).
- **On-chain comme alpha → testé au gate** : `onchain-study` (#275/#277). `tvl_mcap` ❌ (p≈0,18,
  4 actifs) ; `fees_mcap` **non testable** (data DefiLlama non récupérée en gratuit). → **5e négatif**.
- Correctifs : ledger honnête (`non_teste` ≠ `rejete`, #278) ; `make site` (ré)installe les deps
  périmées (#280).

**Décidé.** **Aucun facteur on-chain ne passe le gate → rien câblé au ML/décision** (anti-fuite,
fidèle au manifeste). Le on-chain reste un **contexte analytique** (table + rapport `/macro`), pas
un signal. Méta : l'alt-data crypto échoue systématiquement au gate, comme les 4 négatifs actions.

**Prochaine étape.** Inchangée : **revue courbe paper le 2026-08-06** (paper-watch surveille). Le
on-chain est **clos comme piste d'alpha** ; il vit comme contexte. ML pur.

## Session 2026-06-25 — Recherche alt-data (4 négatifs) + couche risque + audit 3× → capital réel limité
**Fait.** ~15 PR successives (CI verte → merge → resync), tout 0 €.
- **Pipeline recherche alt-data** : event-study panier + benchmark + dé-chevauchement (#251-255),
  insider Form 4 par CIK + achats nets XML (#250-256), backtest PEAD net de coûts + **PBO/CSCV**
  réel (#254), funding crypto (#257), prediction-markets dé-biaisés favori-outsider (#253).
- **4 hypothèses directionnelles testées → 4 NÉGATIFS propres** (placebo/DSR/PBO) : PEAD large
  (p=0,21), PEAD small/mid (event-study ✅ p=0,019 **mais** backtest Sharpe 0,20 · PBO 0,76),
  insider (t=8 brut = autocorrélation → p≥0,55 corrigé), funding crypto (t=-3,4 trompeur, p=0,16).
  Documentés au manifeste — un négatif propre est un livrable.
- **Couche risque** : overlay d'exposition (drawdown taper × vol prévue EWMA, #258), **câblé dans
  le preset** opt-in (#263), concentration **corrélation-aware** (#264), `make risk-check`.
- **Audit contradictoire 5 voix, 3 rounds (66 → 77 → 83/100)** : source unique de vérité métriques
  (#259), audit data `warn` par défaut + survivorship honnête (#260), `_curve_stats` unifié +
  dé-redondance screening (#261), harnais de sensibilité Jaccard+régime (#262), seed curée de
  délistés incl. faillites bancaires SIVB/FRC/SBNY (#265).
- **Runs réels Mac** : sensibilité tout-vert (Jaccard 0,94 → seuils NON sur-optimisés) ; A/B overlay
  identique (preset MaxDD -4,8 % déjà géré → overlay = assurance tail) ; survivorship `undersampled:
  False` après seed.

**Décidé.** Pivot acté (ADR-0024) : on **arrête de chasser l'alpha directionnel** (DSR≈0 confirmé 4×)
et on **durcit la gestion du risque** (l'edge prouvé). Overlay risque **défaut OFF** (opt-in
`QUANT_RISK_OVERLAY=1`) car inerte sur un preset déjà peu drawdown. Survivorship corrigé
partiellement (résidu = vintages point-in-time, non gratuits, assumé).

**Verdict.** **PRÊT POUR CAPITAL RÉEL LIMITÉ** sous 3 conditions (sizing défensif `QUANT_DD_TARGET=0.15`,
track record paper d'abord, caveat survivorship). Aucun blocage logiciel restant.

**Prochaine étape.** Paper défensif lancé 2026-06-25 → **revue courbe paper vs backtest le 2026-08-06**
(`make analytics` + `make ledger-sweep`) → décision premier euro réel limité OU re-calibrage.

## Session 2026-06-24 — Audit « 5 entités » + comité hedge fund → feuille de route 5 lots (0 €)
**Fait.** Les 5 lots de la feuille de route d'audit, en PR successives → CI verte → merge. **567 tests.**
- **Lot 1** [#242] : screener INVESTABLE only (exclut indices `^…`/class index — fin des candidats
  fantômes type `^KS11`) + `packages/common/retry.py` (backoff exponentiel) câblé dans `run_live`.
- **Lot 2** [#243] : `adf_stat()` (Augmented Dickey-Fuller, numpy) + `min_ffd()` (López de Prado) →
  stationnarité **testée**, plus supposée (fin du `d=0.4` arbitraire).
- **Lot 3** : `monte_carlo_trades()` (shuffle/bootstrap des P&L par trade) → drawdown **path-dependent**
  réaliste vs le bootstrap iid optimiste.
- **Lot 4** : `audit.py` conscient de la classe (crypto = 365 j via `_calendar_days`/`_is_crypto`) →
  détecte les week-ends manquants d'une série crypto mal alignée.
- **Lot 5** : `conditional_correlation()` (stress vs calme → démasque la **fausse diversification**) +
  `drawdown_breach()` + `scripts/kill_switch_check.py` (`make kill-check`, cron, ferme le gap 24/7).
**Décidé.** Tout **additif** (0 régression) : on AJOUTE l'outillage de validation sans toucher au
pipeline de prod (ex. `frac_diff` d=0.4 n'avait aucun appelant). Aplatissement réel du kill-switch
intraday délégué au kill-switch existant de `run_live --live` (aucun ordre dans le check).
**Comité hedge fund (diagnostic).** Plus gros gisement d'alpha restant = **Obsidian comme système de
gestion d'hypothèses** (notes atomiques d'alpha + ledger d'essais + dashboard Dataview) → boucle
« idée ↔ DSR ↔ mémoire » à fermer. Proposé, non implémenté (en attente de feu vert).


## Session 2026-06-23 — Attribution honnête + nettoyage repo + docs
**Fait.**
- **Verdict d'attribution gaté sur la significativité** [PR #240] : `analytics.attribution()` calcule le
  **t-stat de l'alpha** (résidu r−β·b) + flags `alpha_significant`/`underperforms_benchmark`. Verdict
  « compétence » SEULEMENT si |t|≥2 ET ne sous-performe pas QQQ ; sinon « hors-QQQ — NON prouvé (DSR≈0) ».
  Front : label « Alpha (compétence) » → « Hors-QQQ » + caveat. Corrige l'incohérence relevée par
  l'utilisateur (β≈0,08 attribuait mécaniquement ~tout à l'alpha ; le preset sous-performe QQQ 160 % vs 557 %).
- **Nettoyage repo** [PR #239] : retrait du **gitlink fantôme** `Screening-Trading` (mode 160000, sans
  `.gitmodules`) + `.gitignore /Screening-Trading/`. Côté utilisateur : sortie de Vim (`core.editor true`),
  suppression du clone imbriqué récursif, réalignement `reset --hard origin/main`.
- **Docs** : README (table commandes + bloc Gouvernance/Honnêteté), TODO (opérationnel mesuré, chantiers
  restants), index. Rappels UX : `qt` (alias projet), `rm -rf apps/web/.next` avant `npm run dev` après
  un `make site`, site en ligne ≠ local = **données différentes** (univers CI borné vs `YAHOO.db`), pas version.

## Session 2026-06-23 — #8 Garde anti-hallucination LLM (alignement)
**Fait.** `packages/llm/guard.py` : `guard_numbers()` — tout nombre significatif (%/décimal/≥10) du
memo IA absent des `facts` fournis est neutralisé (`[n.d.]`) ou rejeté. Branché dans `_enrich_ai_memo`
(`main.py`) : >2 chiffres fabriqués → on garde le mémo à base de règles ; sinon mémo nettoyé +
mention « chiffres contrôlés ». L'IA narre, ne calcule jamais. 6 tests. **543 verts.**

**Validation données réelles (run utilisateur, 2026-06-23) :** `make backtest-preset` Preset CAGR 80,5 %
Sharpe 2,44 **maxDD -9,0 %** vs équipondéré CAGR 180 % Sharpe 2,16 **maxDD -23,3 %** → DD divisé par
~2,6 pour un meilleur Sharpe. `make calibrate-preset` : 27 combos, **Sharpe déflaté ≤ 1 %** partout
→ **DSR≈0 CONFIRMÉ en réel** : aucun alpha directionnel robuste. Best défensif : DD15/top20/bande3.
Le manifeste d'honnêteté est empiriquement validé : la valeur = gestion du risque, pas l'alpha.

## Session 2026-06-23 — #5 SPC / Six Sigma (qualité data) + UI
**Fait.** `packages/data/spc.py` (stdlib) : `p_chart` (carte p ±3σ), `cusum` (détection de dérive),
`dpmo` + `sigma_level` (décalage 1,5σ). Wiring dans la section `data` : taux de défaut OHLCV sur tout
le panel (high<low / prix≤0 / volume<0 / NaN) → DPMO + niveau sigma (`data.spc`). Section
« Maîtrise statistique (Six Sigma) » sur la page Données (niveau σ coloré, DPMO, cible 3,4, p̂).
8 tests. Smoke réel : 3,7 M barres, 0 défaut → 6σ (le gate contrats garde la base propre). **537 verts.**

## Session 2026-06-23 — #2 isolation des fautes + #3 PSR/honnêteté en UI
**Fait.**
- **#2 (phase 1)** `packages/common/safe_section.py` : chaque section feuille du snapshot (themes, ml,
  screen, sentiment, fundamentals, investors, conviction, universe, data) est isolée → une panne
  renvoie `{available:False}` au lieu de tuer tout le snapshot (anti bug historique IndexError).
  Chemin heureux inchangé. [PR #235]
- **#3 PSR en UI** : `_psr_block()` calcule le **PSR = P(Sharpe vrai > 0)** (corrigé skew/kurtosis,
  `packages/portfolio/psr.py`) sur la courbe affichée → `dashboard.honesty`. Bandeau « Honnêteté »
  sur le dashboard (PSR %, Sharpe ann., n, note expliquant que le DSR multi-essais ≈ 0). Passe par le
  payload `dashboard` existant (0 endpoint, dump statique automatique). `_SNAP_VERSION` auto-hash →
  cache invalidé sans bump manuel.
**Décidé.** On affiche le PSR (honnête, mono-courbe) ET on rappelle le DSR≈0 : transparence = wedge.
Reportés : #5 SPC, #8 validateur LLM, #6 prediction-markets, #9 GARCH, suite du #2 (modules sections).

## Session 2026-06-23 — Sprint-0 Gouvernance (audit « Conseil Suprême ») — tout 0 €
**Fait.** Items à plus haut ratio impact/effort de la matrice d'audit, tous gratuits & CI-vérifiés.
- **#1 Gate de publication (andon)** : `scripts/check_build.py` → **échec ROUGE** du workflow Pages si
  le site est vide/tronqué/**périmé** (`meta.generated_at` ≠ aujourd'hui). Branché dans `pages.yml`
  après le build. Tue le défaut « vert mais muet ».
- **#7 Reproductibilité** : `_SNAP_VERSION` = **hash auto** du code (`snapshot.py`+`payloads.py`) → fin du
  bump manuel (risque humain éliminé). `make repro` → `out/repro.json` (git sha + config hash + version
  + seed + env). Auditabilité « niveau papier ».
- **#4 Lignage & réconciliation** : `packages/data/lineage.py` — `fingerprint()` (provenance SHA-256
  déterministe) + `reconcile()` (divergence inter-sources yf/FMP/HF, brèches > tolérance). 5 tests.
- **#13 Tests de propriété** (`hypothesis`, OSS) : invariants des noyaux maths (`_zscore` standardisé,
  ordre préservé, série constante → 0 ; `above_sma200` booléen). A **déjà débusqué** une pathologie
  d'annulation flottante (corrigée par `assume`).
- **#11 `pip-audit`** (vulns deps) ajouté au job lint CI, non-bloquant. `hypothesis`/`pip-audit` en dev.
- **#14 Manifeste d'honnêteté** : `vault/12_MANIFESTE_HONNETETE.md` (DSR≈0 assumé = le wedge).
- **526 tests verts**, ruff propre sur tout le code neuf.
**Décidé.** Reportés en sprints dédiés (risque/scope, à faire avec vérif renforcée) : **#2** démontage
du god-object `snapshot.py` (registre de sections + isolation des fautes), **#9** GARCH au sizing,
**#3** DSR en UI, **#5** SPC/CUSUM, **#8** validateur anti-hallucination LLM, **#6** facteur
prediction-markets (Kalshi/Polymarket). Le burn-down ruff/mypy (~3800) précède le passage des gates en bloquant.

## Session 2026-06-23 — Screening branché (API + page front) + mypy CI + `make screen`
**Fait.** Le moteur de screening est désormais **exposé de bout en bout**.
- **Snapshot** : `_screen_section()` (`apps/api/snapshot.py`) lance `ScreeningEngine` sur le panel de
  l'univers → section `screen` (count, universe_size, filtres, poids, rows top-50 enrichis nom/secteur/
  classe + score/reason/ret_12m/drawdown/dollar_volume). Best-effort (jamais bloquant). Smoke réel :
  **25 candidats / 929**. Bump `_SNAP_VERSION` (invalide le cache).
- **API** : `GET /api/screen` (`apps/api/main.py`) ; **dump statique** (`dump_static.py`) → `data/screen.json`
  pour la PWA ; hook `useScreen` (`lib/api.ts`).
- **Front** : page `/screener` (`apps/web/app/screener/page.tsx`) — KPIs (candidats/univers/sélectivité),
  critères appliqués, table triée par score (recherche + export CSV, EmptyState si 0). Lien nav ajouté
  (groupe Marché). Build static OK : **20 routes**.
- **CI** : `mypy packages` ajouté au job lint en **non-bloquant** (strict trop bruyant sur le legacy).
- **CLI** : `make screen` (`scripts/run_screen.py`) imprime les candidats (source de vérité = snapshot).
- **Tests** : `test_snapshot` (clé `screen` + structure) + `test_engine` (payload `_screen_section`).
  **517 verts**.

## Session 2026-06-23 — Moteur de screening (filtres YAML + scoring z-score) [P1]
**Fait.** `packages/screening/` (le stub était vide) — comble le trou P1 « screening → trading ».
- **`engine.py`** : `ScreeningEngine` = filtres durs `{metric, op, value}` (op : `> >= < <= == != between`,
  `on_missing: fail|pass`) → survivants notés par **composite z-score** (réutilise `_zscore` du ranking,
  global ou sector-neutral, facteur sans donnée ignoré). `ScreenResult` porte `passed/score/failed/
  metrics/contributions` + `reason` lisible. `from_yaml()` + `top_n` + `include_rejected`.
- **`metrics.py`** : vocabulaire unifié filtres↔scoring. Réutilise le **registre de facteurs**
  (`momentum/trend/low_vol`, et `value/quality` si fondamental chargé) + **métriques prix** internes
  (`dollar_volume`, `ret_1m/3m/6m/12m`, `dist_sma50/200`, `above_sma50/200`, `drawdown_from_high`,
  `vol_63`, `last_close`). Point-in-time (barres ≤ t). Métrique inconnue → `ValueError` franc.
- **`config/screening.yaml`** : preset (liquidité ≥5 M$, au-dessus MM200, DD > -30 %, momentum sain) +
  scoring momentum/trend/low_vol, top 25.
- **Tests** : `tests/screening/test_engine.py` (11) — filtres, between, on_missing, liquidité, ordre du
  score, top_n, métrique/op inconnus, chargement YAML. **516 passés** au total, ruff propre sur le neuf.
**Décidé.** DRY : on réutilise `_zscore`/`FactorContext`/le registre de facteurs au lieu de dupliquer.
Le screening (filtre booléen + tri) est complémentaire du ranking (tri pur pondéré régime×classe).

## Session 2026-06-23 — CI gate (pytest bloquant + ruff informatif)
**Fait.** `.github/workflows/ci.yml` : 2 jobs sur push `main` / PR / dispatch.
- **`tests`** : setup-python 3.11 + cache pip, install **lean** `.[common,data,quant,api]` + reportlab +
  scikit-learn (les tests gardent torch/vectorbt/xgboost… via `importorskip` → skip propre si absent ;
  aucun import lourd au top-level des packages), puis `pytest -q` **bloquant**. Local : **505 passés,
  4 skips, 77 s**.
- **`lint`** : `ruff check packages apps scripts` en **`continue-on-error`** (informatif). Le legacy a
  ~3857 occurrences ruff → on ratchet sans bloquer le flux ; passera bloquant après burn-down.
- `concurrency` (annule les runs superséd és) + `permissions: contents read`.
**Décidé.** mypy **différé** (strict = trop bruyant sur le legacy, gate inutilisable d'emblée). weasyprint
exclu de l'install CI (libs système cairo/pango) — seul reportlab est testé, installé directement.

## Session 2026-06-23 — Design « radical » (robuste, 0 dépendance) [PR #229]
**Fait.** (CSS-only / contenu à `Nav.tsx` → aucune régression fonctionnelle possible, build static 21/21 vert)
- **Aurora background** : ruban conique flou (`body::after`, `globals.css`), mélangé en OKLCH aux accents,
  atténué en thème clair, **coupé sous `prefers-reduced-motion`**. Rendu CSS pur → 0 WebGL, 0 dépendance,
  0 coût batterie d'un canvas (objectif « borealis » premium sans le risque).
- **Accents OKLCH** : `--accent/--accent2/--pos/--neg/--warn` en OKLCH derrière `@supports`, déclarés
  **après** les hex → fallback automatique, aucune régression possible (plus vifs sur écrans P3).
- **Typographie display** : `font-optical-sizing`, ligatures `ss01/cv01`, `text-wrap:balance`, tracking
  resserré sur les titres.
- **Nav desktop condensée** : 18 liens qui passaient à la ligne → **Accueil + 3 menus groupés**
  (Marché / Analyse / Portefeuille), pur CSS `group-hover`/`focus-within` (pas d'état JS fragile,
  accessible clavier).

**Décidé (best practice — robustesse > produit).** Les 3 items « radicaux » restants sont **écartés** car
chacun ajoute une dépendance ou un appel réseau au **build CI** → risque sur la reconstruction quotidienne
du site : WebGL aurora (OGL), View Transitions à élément partagé (`next-view-transitions` — la VT native
ne se déclenche pas sur la navigation SPA de Next), police variable (`next/font` échoue si pas de réseau au
build). L'aurora CSS couvre l'objectif visuel sans ce risque ; `pageIn` couvre déjà les transitions de page.

## Session 2026-06-23 — « Mastermind 100 » : optimisations gratuites (FinOps/perf/data/auto)
**Fait.** (toutes open-source, testées, mergées)
- **FinOps IA** : `packages/llm/local.py` (`cheap_llm` Ollama + `smart_text` routeur) → tâches simples
  sur LLM local gratuit (`QUANT_LOCAL_LLM`, ex. gemma3n:e4b/qwen2.5:3b), Claude réservé au complexe.
  Corrigé un bug : `complete()` renvoie un dict → le mémo IA n'était jamais posé.
- **RAG** : `scripts/vault_search.py` — embeddings denses Ollama (`QUANT_EMBED=ollama`,
  `nomic-embed-text`) + indexation du **code** (`--code`). Texte tronqué 4000 car. (anti-overflow 2048).
- **Perf** : hot-path prix **vectorisé** (preload 1 scan, `db_provider`), snapshot **incrémental**
  (`packages/common/memo.py`, mémoïse multi_strategy + monte_carlo), brokers Alpaca∥Bitmart en
  parallèle (ThreadPoolExecutor), analytics **DuckDB** sur Parquet (`hf_cache.momentum_ranking`),
  push HF en **Polars**.
- **Data souveraine** : cache OHLCV **Hugging Face** (`scripts/hf_cache.py`, push/pull) → CI lit le
  cache avant yfinance (fini le rate-limit). Gate **contrats** OHLCV bloquant (`contracts_check.py`,
  CI) — ne bloque que l'impossible (close≤0, high<low, vol<0), tolère trous & prix ajustés.
- **Automatisation** : miroir **Notion** (`notion_sync.py`), KPIs **Supabase** (`kpi_to_supabase.py`),
  workflow **n8n** TradingView→`/api/tv/webhook` (`integrations/n8n/`). Tous branchés au cron (best-effort).
- **Agent** : `CLAUDE.md` enrichi (nouvelles commandes), skill `/brief`, RAG code.
- **Robustesse tests** : `test_snapshot`/`test_local` rendus indépendants de l'environnement
  (clés courtier présentes, LLM local actif, univers crypto réel `-USD`).

**Décidé.** Tout est **best-effort** : chaque intégration (Ollama, HF, Notion, Supabase, n8n) se
désactive proprement si la clé/le service est absent → jamais bloquant. n8n n'a de valeur qu'avec un
tunnel public (TradingView cloud) → le webhook reste testable en local via `curl`.

## Session 2026-06-21 — Mise en ligne GRATUITE (PWA mobile) + durcissement
**Fait.**
- **Déploiement GitHub Pages + Actions** (`.github/workflows/pages.yml`) : vrai front Next.js statique
  (parité `make start`) reconstruit chaque jour ouvré + à chaque push `main`, **données réelles** dans le
  cloud (yfinance/SEC). URL : `https://7noctis7.github.io/Screening-Trading/`. Mac éteint, 0 €.
- **Pipeline statique** : `scripts/dump_static.py` (fige `/api/*` en JSON + notes HTML) →
  `scripts/build_static_site.py` (export Next.js `output:export` → `site/`). Commandes `make site` /
  `site-lite` / `watchlist`. Univers borné `config/mobile_universe.csv` (watchlist fixe + top 200).
- **Bugs CI corrigés** (verts en local, cassés en ligne) :
  - lockfile `apps/web/package-lock.json` dé-ignoré et versionné (cache npm + `npm ci`).
  - `real_macro_store` : alignement défensif valeurs↔dates (l'indice réel est plus long que le calendrier
    univers en CI) → fin de l'`IndexError` qui plantait tout le snapshot (site déployé sans données).
  - `dump_static` : `_clean()` NaN/Inf → `null` (sinon JSON invalide → pages bloquées en chargement, ex.
    Fondamentaux). `build_static_site` aborte si le dump échoue (plus de déploiement « vert mais vide »).
  - `ingest_crypto` : base normalisée `BTC-USD → BTC` (fin du `BTC-USD-USD` 404).
  - Historique CI **depuis 2015** (`--since 2015-01-01`, `QUANT_HISTORY_DAYS=4015`) au lieu de 18 mois.
- **UI/UX mobile (Apple)** : nav en **tiroir** rendu par portail (échappe au `backdrop-filter` qui
  l'écrasait), safe-area iPhone, anti-débordement horizontal, thème clair plus lisible (décor atténué),
  heatmap de corrélation scrollable. Liens notes corrigés en statique.
- **Sécurité (repo public)** : audit OK — aucun secret/clé/`.env`/`.db` traqué, historique propre, tout
  gitignoré. Username macOS neutralisé dans les chemins d'exemple.

**Décidé.** Le site **public** ne reçoit jamais les clés courtier → positions réelles **local-only**
(confidentialité). Renommage compte GitHub → l'URL Pages suit (pas de hardcode), mais ne pas renommer
pendant un run (jeton OIDC invalidé).

## Session 2026-06-20 — Notes d'analyse institutionnelles (PwC / Citadel / Apple)
**Fait.**
- **Note d'analyse par société** (HTML + PDF reportlab/weasyprint, thème clair/sombre, design Apple) :
  `packages/reporting/company_report.py` + `company_report_render.py` ; endpoint `/api/company_report`,
  page `/notes`, icône 📄 (Fondamentaux/Conviction), pré-génération nocturne `make reports`.
- **Contenu** : Portfolio Snowflake (radar 5 axes), Vernimmen (ROCE/WACC/EVA/DuPont/gearing),
  Damodaran (DCF scénarios + inversé, multiples vs secteur), 3 scores (fond/tech/ML), risk management
  (vol/VaR/CVaR/Sharpe/Sortino/stop), historique annuel + trimestriel (yfinance → SEC EDGAR 10-Q),
  actionnariat (institutionnels/insiders en %), graphes SVG (cours+MM, drawdown, CA/RN), dividende réel.
- **Gouvernance (PwC)** : audit d'intégrité + **réconciliation GAAP vs Non-GAAP** en devise de dépôt,
  **blocking alert** (>10 % CA/RN), **pénalité de surévaluation** (DCF MoS < −30 % → pilier 0 + ≤ −40 %).
- **Fiabilité** : conversion devise ADR (yfinance financialCurrency + FX gratuit), réconciliation
  alignée TTM (faux écarts dûs au change/période supprimés), EBITDA ≥ EBIT, NaN → « — ».
- Cause racine corrigée : cache yfinance v3 (nom société/devise/dividende), réordonnancement thématique.

**Décidé.** Réconciliation en devise de dépôt (intégrité) ≠ valorisation en devise du cours (marché).

## Session 0 — Fondation
**Fait.**
- Posé le monorepo (section 3 du prompt maître) : `apps/`, `packages/`, `config/`, `tests/`, `vault/`.
- `packages/core` (domaine pur, zéro dépendance) : `models.py` (Instrument, Bar, Signal, Order,
  Position, RegimeState, FactorScore, TradeRecord + enums), `interfaces.py` (DataProvider, Indicator,
  Factor, Strategy, Sizer, RiskRule, Broker, RiskDecision), `registry.py` (plugins auto-enregistrés).
- `packages/common` : `config.py` (YAML), `logging.py` (JSON structuré), `event_bus.py` (pub/sub + topics).
- Configs YAML d'exemple : `universe`, `risk`, `factors`, `strategies/ma_crossover`.
- Tests : `test_registry` (validation archi plugin), `test_models`, `test_event_bus`.
- `pyproject.toml` (uv/ruff/mypy/pytest, deps par groupe), `.gitignore`, `.env.example`, `README`.
- Vault initialisé : INDEX, ARCHITECTURE (schéma vivant + 2 diagrammes Mermaid), DECISIONS (ADR-0001),
  TODO (roadmap P0/P1/P2), + stubs 05→12.

**Décidé.** ADR-0001 (stack & archi de fondation).

**Prochaine priorité.** P0 : CI (ruff/mypy/pytest) → Storage (bronze/silver/gold + Alembic) →
premier `DataProvider` (yfinance) avec normalisation OHLCV UTC + cache.

**Note.** Aucune logique de trading réelle écrite (garde-fou respecté). Attente du feu vert
pour entamer l'implémentation des modules métier.

## Session 1 — Tranche verticale runnable (data → backtest → métriques)
**Fait.**
- **Data** : `DataProvider` synthétique (GBM seedé, offline, reproductible) + yfinance (réel), auto-enregistrés.
- **Indicateurs** (numpy, anti-look-ahead testé) : SMA, EMA, MACD, **régression log-linéaire z-score**, RSI, ROC, ATR, largeur Bollinger.
- **Régime** : classifieur rule-based v1 (tendance vs SMA + pente, vol réalisée → cycle + risk-on/off), `extras` prêt pour FRED/surprises.
- **Stratégies** plugins : `ma_crossover` (trend), `rsi_reversion` (mean-reversion), stop/target ATR-based.
- **Sizing** : `fixed_fractional`, `vol_target` (Kelly-cap). **Risk engine** : règles veto (R:R, max positions, expo/actif) + **kill-switch drawdown quotidien**.
- **Exécution** : `CostModel` (frais+slippage) + `SimBroker` paper (sert backtest ET live → parité).
- **Backtest** : moteur event-driven multi-instruments, broker partagé, gestion stop/target, **journal avec snapshot features + R-multiple + MFE/MAE**.
- **Métriques** : Sharpe/Sortino/Calmar/MaxDD/profit factor/win rate/expectancy.
- **Démo** `scripts/demo_backtest.py` : tourne offline → résultat **honnête -1,1%** (trend sur quasi-random après coûts = attendu, pas d'alpha fabriqué). R-multiple -1.0 sur stops / +2.49 sur targets : accounting validé.
- **21 tests** verts (indicateurs/sizing/risque/moteur + archi).

**Décidé.** ADR-0002 (indicateurs groupés par famille) · ADR-0003 (broker simulé partagé backtest/live pour la parité) · ADR-0004 (sizer plafonné à la limite d'expo, risk engine = backstop dur).

**Découverte utile.** Sizer vol-target (20% capital) vs cap expo/actif (10%) → veto systématique : preuve que le risque a bien le dernier mot. Corrigé en calant le plafond du sizer sur la limite.

**Correctif clé (S1).** Déterminisme : remplacé `hash()` builtin (randomisé/process) par `hashlib` dans le provider synthétique → backtests reproductibles (ADR-0005, test dédié).

**Prochaine priorité.** P0 : Storage bronze/silver/gold (DuckDB+Parquet) + repository de persistance du journal + contrats pandera. Puis P1 : screening/ranking multi-facteur réel + walk-forward + deflated Sharpe.

## Session 2 — Storage (medallion) + univers + qualité + réponses design
**Fait.**
- **Univers** : loader `config/universe.yaml` → `Instrument`, séparation **tradables (4)** / **benchmarks (3)**.
- **Storage** : `SqliteBarsRepository` (stdlib) — bronze/silver, clé `(symbol,timeframe,ts)`, **UPSERT idempotent**, `last_ts()` pour l'incrémental, multi-timeframe natif.
- **Qualité** : `validate_ohlcv` (prix>0, cohérence OHLC, ts uniques/croissants, trous, fraîcheur) → `enforce` **bloque** le pipeline si KO. Pandas pur (pandera brranchable plus tard).
- **Démo** recâblée sur l'**univers réel** via pipeline medallion (provider→bronze→validation→silver→backtest). Corrigé l'incohérence : la démo codait 5 symboles ≠ univers (7 déclarés).
- **+10 tests** (33 verts). Reproductible (+0.2% stable).

**Décidé.** ADR-0006 (SQLite now / DuckDB cible + timeframe daily canonique) · ADR-0007 (pas de LLM dans le chemin chaud).

**Réponses design consignées** (questions utilisateur) : voir 08_DATA_MODEL (politique timeframe/cadence) et ADR-0007 (agents IA).

**Prochaine priorité.** Gold layer + feature store (indicateurs/facteurs stockés) → screening/ranking multi-facteur réel → walk-forward + deflated Sharpe. Brancher DuckDB+Parquet (même interface) quand volumes réels.

## Session 3 — Univers multi-marchés (source-driven) + ranking multi-facteur
**Fait.**
- **Moteur d'univers** : `UniverseBuilder` + sources plugins — `static` (seeds offline), `wikipedia`, `nasdaq_trader` (listings US complets), `coingecko`. Dédoublonnage + **snapshot daté** (point-in-time, anti-survivorship). `UniverseRepository` (SQLite).
- **Seeds exacts** : forex(20), commodities(20), indices(20), ETF(101 par secteur/industrie/géo), crypto(100), CAC40(40), AEX(24). Sources réseau pour SP500/Nasdaq100/SBF120/FTSE100/FTSE MIB/Nikkei/KOSPI/CSI300 + NYSE/Nasdaq complets.
- **Offline = 325 instruments** ; en ligne = milliers. Démo recâblée sur le builder (échantillon de 12 pour la vitesse) ; corrigé l'incohérence univers↔démo.
- **Ranking multi-facteur** (Module 4) : facteurs momentum/trend/low-vol (cross-sectional z-score), pondérations **régime × classe**, applicabilité (forex/crypto sans value/quality), **top N explicable** (contribution par facteur + raison).
- `scripts/build_universe.py` (--network), +11 tests (44 verts).

**Décidé.** ADR-0008 (univers source-driven + snapshots datés, jamais de tickers en dur).

**Réponse à la demande univers** : les ~milliers de titres viennent des sources réseau à l'exécution chez l'utilisateur — pas codés à la main (anti-hallucination/péremption).

**Prochaine priorité.** Fondamental & valorisation (Module 6 : ratios Vernimmen + DCF/multiples Damodaran → facteurs value/quality) → couche gold/feature store (stocker indicateurs+facteurs) → walk-forward + deflated Sharpe. Puis brancher yfinance/FMP réel + DuckDB.

## Session 4 — Univers mensuel + Russell + dédoublonnage + fondamental
**Fait.**
- **Mensuel** : `rebuild_cadence_days: 30`, `build_universe.py` cadence-aware (`--force`), `scripts/scheduler.py` (APScheduler, cron 1er du mois) + helper `due_for_rebuild` testé. → réponse : OUI, l'univers s'update une fois/mois (avant : non, manuel).
- **Russell 1000/3000** : source `ishares_holdings` (IWB/IWV), parser préambule CSV + filtre Equity + dot_to_dash.
- **Dédoublonnage par symbole** (priorité = ordre des sources) → tous les doublons inter-sources retirés ; `duplicates_removed` rapporté. Vérifié (seed ETF ×2 → 101 retirés).
- **Module fondamental** (Module 6) : ratios Vernimmen (ROE/ROIC/marges/net debt-EBITDA/FCF), valorisation Damodaran (PER/EV-EBITDA/P-B + **DCF FCFF + marge de sécurité**), provider synthétique déterministe (réel FMP/yfinance via même interface).
- **Facteurs value/quality** branchés dans le ranking (refactor à **contexte** : technique + fondamental cohabitent ; z-score **sector-neutral** pour value/quality ; facteur sans donnée = retiré proprement).
- +13 tests (57 verts).

**Décidé.** ADR-0009 (cadence mensuelle) · ADR-0010 (dedup par symbole) · ADR-0011 (Russell via iShares).

**Prochaine priorité.** Couche **gold/feature store** (stocker indicateurs+facteurs+fondamentaux datés) → **walk-forward + deflated Sharpe** → brancher providers réels (yfinance/FMP) + DuckDB. Puis screening top-down macro (FRED/ALFRED point-in-time).

## Session 5 — Couche gold (feature store) + walk-forward + deflated Sharpe
**Fait.**
- **Feature store (GOLD)** : `FeatureStore` SQLite + `materialize_indicators` (config `features.yaml`) → indicateurs point-in-time matérialisés depuis silver. **Anti training/serving skew** (test : store == recalcul). NaN de warm-up non stockés.
- **Statistiques de robustesse** : PSR + **Deflated Sharpe** (Bailey/López de Prado), stdlib (`NormalDist`). Corrige taille d'échantillon, non-normalité ET multiple testing.
- **Walk-forward** : `WalkForwardRunner` (fenêtres roulantes train→test, warm-up, sélection in-sample, éval OOS), DSR sur nb total d'essais. `scripts/demo_walkforward.py`.
- Démo : OOS +7.8% / Sharpe 0.46 / PSR 0.90 mais **DSR=0.00** sur 64 essais → "NON significatif" (garde-fou anti-surapprentissage qui marche).
- +10 tests (67 verts).

**Décidé.** ADR-0012 (feature store anti-skew) · ADR-0013 (walk-forward + deflated Sharpe).

**Prochaine priorité.** Brancher providers RÉELS (yfinance/FMP) + DuckDB+Parquet (même interfaces) pour quitter le synthétique → premiers backtests sur vraies données + walk-forward. Puis macro/régime point-in-time (FRED/ALFRED) et exécution paper Alpaca.

## Session 6 — Providers réels (yfinance/FMP) + DuckDB (drop-in)
**Fait.**
- **Wrappers** composables (testés) : `FallbackProvider`, `CachingProvider` (+persistance silver), `RateLimiter`/`RateLimitedProvider` (horloge injectable).
- **yfinance** : normalisation `df_to_bars` pure/testée (UTC, multi-index aplati) ; fetch réseau isolé.
- **FMP** : `FMPFundamentalsProvider` + `build_financials` (mapping JSON→Financials, testé fixture). Branche les vrais fondamentaux dans value/quality.
- **DuckDB** : `DuckDBBarsRepository` drop-in (même interface) + `export_parquet` ; `make_bars_repository(backend)` (sqlite|duckdb). Test DuckDB skippé proprement hors-ligne.
- `config/data_sources.yaml` (ordre fallback, quotas, provider fondamental). `scripts/verify_real_data.py` (smoke test en ligne).
- +11 tests (78 verts).

**Décidé.** ADR-0014 (providers réels via wrappers + backend pluggable).

**Note offline.** duckdb/yfinance/pyarrow absents ici → code écrit pour ton env ; logique 100% testée via fixtures/mocks. Lance `scripts/verify_real_data.py` avec réseau.

**Prochaine priorité (étape 2).** Macro & régime **point-in-time** : ingestion FRED/ALFRED (vintages), surprises éco (réalisé vs consensus), cartographie macro→actifs, classification du cycle → `RegimeState` quotidien enrichi. Puis (étape 3) exécution paper Alpaca.

## Session 7 — Macro & régime point-in-time (FRED/ALFRED, surprises, cartographie)
**Fait.**
- **MacroStore** (vintages) + `as_of` point-in-time : respecte délai de publication ET révisions (logique ALFRED). Testé sur scénario CPI publié+révisé.
- **FredProvider** (réel) + parser `parse_observations` (testé fixture) ; **synthetic_macro** (offline, lag de publication).
- **Surprises éco** (`surprise_index`) : réalisé vs consensus, par thème (inflation/croissance/emploi), point-in-time.
- **Cartographie macro→actifs** (`config/macro_impact.yaml` + `MacroImpactMap`) : multiplicateur d'exposition (risk_mode × cycle), inclinaisons de facteurs et de classes selon surprises.
- **MacroRegimeClassifier** (nowcasting) : courbe 2s10s + ISM/PMI + chômage + VIX → cycle + risk-on/off, point-in-time.
- Modèles domaine : `MacroObservation`, `EconomicRelease`. `config/macro.yaml`. `scripts/demo_macro_regime.py`.
- +14 tests (92 verts).

**Décidé.** ADR-0015 (macro point-in-time + cartographie).

**Prochaine priorité (étape 3).** Exécution **paper Alpaca** : `AlpacaBroker` (implémente l'interface Broker, paper natif), réconciliation broker↔DB, retries idempotents — puis boucle live paper (kill-switch visible). Toujours zéro réel sans feu vert.

## Session 8 — Exécution paper Alpaca + moteur live (parité backtest↔live)
**Fait.**
- **AlpacaBroker** (interface Broker, paper natif) + mappers purs testés ; réseau isolé.
- **LiveTradingEngine** : réutilise Strategy/Sizer/RiskEngine/Broker/Journal du backtest, en streaming (step par barre) → **parité**. Kill-switch visible à chaque pas.
- **Retries idempotents** (`submit_with_retries` + client_id ; SimBroker rendu idempotent → 2 submits même id = 1 fill). Backoff exponentiel, sleep injectable.
- **Réconciliation** broker↔interne (`reconcile`) + alerte event-bus sur divergence.
- `config/execution.yaml`. Démos : `demo_paper_loop.py` (offline SimBroker), `verify_alpaca.py` (ton env, paper).
- +13 tests (104 verts).

**Décidé.** ADR-0016 (paper Alpaca + parité + idempotence/réconciliation).

**Note offline.** alpaca-py absent ici → AlpacaBroker écrit pour ton env (mappers testés) ; toute la logique (live engine, idempotence, retries, réconciliation) testée via SimBroker. Lance `verify_alpaca.py` avec clés paper.

**Séquence des 3 étapes proposées TERMINÉE** (providers réels → macro/régime → paper). Reste roadmap : ML (triple-barrier, purged CV, MLflow), alertes multi-canal, excellence op (observabilité/CI-CD/tear sheets PDF), **front-end** Next.js, et live réel (sur feu vert).

## Session 9 — Module ML (triple-barrier, CV purgée, gouvernance)
**Fait.**
- **Labeling** : triple-barrière (profit/stop/temps) + meta-labeling + vol EWM (`packages/ml/labeling.py`).
- **CV PURGÉE & embargo** (`PurgedKFold`) : retire les labels chevauchant le test → OOS honnête.
- **Features** : différenciation fractionnaire + `FeatureBuilder` point-in-time (technique gold + macro `as_of`).
- **Modèles** : `LogitModel` (numpy pur, baseline testable) + `SklearnModel`/xgboost ; `make_model`.
- **Évaluation** : accuracy/précision/rappel + `purged_cv_score`.
- **Gouvernance** : `champion_challenger` (marge + barrière de risque) + `ModelRegistry`.
- Démo offline : OOS ~50% sur synthétique (anti-surapprentissage confirmé). +16 tests (120 verts).

**Décidé.** ADR-0017 (ML López de Prado).

**Reste roadmap.** Alertes multi-canal (Telegram/Discord) · excellence op (observabilité, drift, audit, CI/CD, tear sheets PDF) · **front-end Next.js** (dashboard/screener/portefeuille/positions) · live réel (sur feu vert).

## Session 10 — API FastAPI (contrat testé) + front Next.js + aperçu HTML
**Fait.**
- **Builders de payloads** purs et testés (`apps/api/payloads.py`) : régime, equity, screener, composition (totaux/P&L/exposition brute-nette), métriques, comparaison benchmarks rebasés, sérialisation trades JSON-safe.
- **snapshot.py** : état complet (dashboard/screener/portfolio/trades) depuis un run offline — **100% JSON-sérialisable** (vérifié).
- **FastAPI** (`apps/api/main.py`) : routes /health, /api/{dashboard,screener,portfolio,positions,trades} + CORS (ton env).
- **Front Next.js** : tokens (`lib/tokens.ts`) + tailwind + client TanStack Query (`lib/api.ts`) + Dashboard (page + MetricCard + RegimeBanner) + README.
- **Aperçu HTML statique** (`apps/web/preview/dashboard.html`) rendu depuis les vraies données (dark, SVG equity vs S&P 500, screener, P&L) — ouvrable sans build.
- `11_DESIGN_SYSTEM.md` rempli (tokens concrets). +7 tests (127 verts).

**Décidé.** ADR-0018 (API contrat testé + front consommateur).

**Note offline.** fastapi/uvicorn absents + pas de `npm install` (réseau) → app FastAPI et front écrits pour ton env ; toute la logique d'assemblage (payloads, snapshot) testée. Lance `uvicorn apps.api.main:app` puis `npm run dev`.

**Reste roadmap.** Alertes multi-canal · excellence op (observabilité/drift/audit/CI-CD/tear sheets PDF) · écrans front restants (portefeuille/analyse, positions, backtest) · live réel (feu vert).

## Session 11 — Analyse de portefeuille (relatif, risque, corrélation, revue) + écrans
**Fait.**
- **Mesures relatives** (`benchmark.py`) : beta, alpha Jensen, tracking error, information ratio, R², up/down capture.
- **VaR/CVaR** (`risk_metrics.py`) historique + paramétrique (Jorion).
- **Corrélation + clustering** (`correlation.py`) single-linkage → anti fausse-diversification.
- **Attribution** du P&L (`attribution.py`) par stratégie/actif/classe.
- **Stress test + Monte Carlo** (`stress.py`) : choc via beta, proba de ruine, worst DD, VaR de trajectoire.
- **Revue experte** (`review.py`) CFA/FRM/CPA/CAIA : ancrée sur les métriques (zéro chiffre inventé) + score de santé + recommandations priorisées.
- Exposé dans l'API (`/api/portfolio` → `analysis`) et le snapshot (JSON-sérialisable).
- **Front** : pages `portfolio` + `positions` (Next.js) + composants ExpertReview / CorrelationHeatmap. **Aperçus HTML** dashboard + **portfolio** (heatmap, revue, risque) rendus depuis les vraies données.
- +10 tests (137 verts).

**Décidé.** ADR-0019 (moteur analytique portefeuille).

**Reste roadmap.** Écran backtest/tear sheets · WebSocket live · alertes multi-canal · excellence op (observabilité/drift/audit/CI-CD/tear sheets PDF) · live réel (feu vert).

## Session 12 — Alertes & notifications multi-canal
**Fait.**
- **Moteur** (`AlertEngine`) : routage par sévérité (INFO/WARNING/CRITICAL), historique pour audit, tolérant aux canaux en échec.
- **Sinks** : InMemory/Console (testables) + Telegram/Discord (réseau, `format_message` pur/testé).
- **Throttle** anti-spam (TTL + dedup_key, horloge injectable).
- **Handlers** (1/type) abonnés à l'event bus : régime, kill-switch, rejet risque, qualité données, fill, divergence broker↔DB (`register_on_bus`).
- `config/alerts.yaml`, `scripts/demo_alerts.py`. +9 tests (146 verts).

**Décidé.** ADR-0020 (alertes multi-canal).

**Reste roadmap.** Excellence op (observabilité/drift/audit/CI-CD/tear sheets PDF) · écran backtest + WebSocket live · live réel (feu vert).

## Session 13 — Excellence opérationnelle
**Fait.**
- **Drift ML** (`ml/drift.py`) : PSI par feature + statut + drapeau, branché aux alertes (drift → réentraînement).
- **Audit trail** (`common/audit.py`) : append-only, rejouable, contexte JSON (features/régime/modèle).
- **Télémétrie** (`common/telemetry.py`) : compteurs/gauges/timers → snapshot santé.
- **Backup/restore** SQLite (`storage/backup.py`), testés (données préservées).
- **Tear sheets** (`reporting/tearsheet.py`) : HTML autonome + **PDF reportlab**.
- `scripts/demo_ops.py`. +8 tests (154 verts).

**Décidé.** ADR-0021 (excellence opérationnelle).

**Reste roadmap.** Écran backtest + WebSocket live · live réel (feu vert) · allocation PyPortfolioOpt · international macro (FMI/OCDE).

## Session 14 — Front interactif (hover/tooltips) + procédure de test
**Fait.**
- **Aperçu interactif autonome** (`apps/web/preview/build_interactive.py` → `interactive.html`) : onglets, courbe d'equity avec crosshair+tooltip au survol, compteurs animés, screener cliquable (barres de facteurs), heatmap de corrélation au survol. Un seul fichier, aucune install.
- **EquityChart** Recharts (tooltip/crosshair) branché au dashboard Next.js → vrai site interactif.
- `scripts/check_all.sh` (tests+démos+aperçus) et `TESTING.md` (procédure de test pas-à-pas).

**Note.** Les aperçus *statiques* (dashboard/portfolio.html) restent non interactifs (SVG serveur) ; `interactive.html` et le front Next.js portent l'interactivité.

## Session 15 — Correctifs (2026-06-16) : onglets interactifs, lxml, hygiène repo
**Fait.**
- **Bug onglets interactifs corrigé** (`build_interactive.py`). Cause racine : le helper `$()` faisait `div.innerHTML='<tr>…'` ; le navigateur **supprime les `<tr>/<td>` posés hors d'un `<table>`**, donc le rendu levait une exception après le Dashboard → onglets **Portefeuille** et **Positions vides**. Fix : chaque table construite en **UNE chaîne HTML complète** (`<table><thead>…<tbody>…</tbody></table>`) injectée d'un coup ; clics du screener **câblés après injection** via `querySelectorAll` + `data-i` (au lieu d'`onclick` sur des nœuds détachés) ; **chaque onglet enveloppé dans un `try/catch`** → une erreur ne peut plus vider les autres. Au passage : corrigé un attribut `class` **dupliqué** dans le bloc Positions (coloration P&L pos/neg cassée). `interactive.html` régénéré + ouvert : les 3 onglets s'affichent.
- **Dépendance manquante** : `lxml` ajouté à l'extra `data` de `pyproject.toml` (requis par `pd.read_html` dans `wikipedia_source.py`). Tests `test_wikipedia_parser.py` rendus robustes : `pytest.importorskip("pandas"/"lxml")` → **skip propre** si absent au lieu d'échouer.
- **Hygiène repo** : `.gitignore` (re)créé (absent du dépôt malgré la note S0 — perdu aux uploads) couvrant `__pycache__`, `.env`, artefacts data, `.DS_Store` ; `.DS_Store` déjà suivis retirés (`git rm --cached apps/.DS_Store apps/web/.DS_Store`).
- **154 tests verts** (aucune régression).

**Décidé.** ADR-0022 (DOM : tables injectées en une chaîne complète + rendu d'onglet isolé par try/catch).

## 2026-08-30 — Rotation automatique d'un modèle IA retiré

- **Incident réel** : la connexion au catalogue fournisseur était verte, puis la génération
  échouait parce que le modèle mémorisé n'était plus ouvert aux nouveaux utilisateurs.
- **Cause** : le preset Web figeait un identifiant fournisseur périssable et le repli natif
  réessayait exactement ce même identifiant.
- **Correction** : le preset laisse désormais le modèle vide. Si un ancien réglage explicite est
  refusé en génération, le backend consulte le catalogue, exclut ce modèle et sélectionne un
  modèle texte disponible, sans inscrire un nouvel identifiant fournisseur dans le dépôt.
- **Preuve** : test de régression en quatre appels simulés (compatibilité absente, modèle natif
  retiré, découverte du catalogue, génération native réussie). Aucun accès à l'exécution.

## 2026-08-30 — Formalisation falsifiable du cahier des charges price-action

- Ajout d'un plugin de recherche causal : pivots confirmés sans back-painting, BOS sur barres HTF
  terminées, zones FVG/order-block, midpoint, first-time-back, SFP et proxy LVN optionnel.
- Les paramètres subjectifs (span, HTF, déplacement, buffer, profil volume) restent obligatoires
  et train-only : aucune calibration n'a été inventée. Statut **UNCALIBRATED**.
- Le backtest exécute au prochain open, applique coûts/slippage, dimensionne le stop à 1 % maximum,
  traite l'ambiguïté intrabar pessimiste, sort la moitié au TP1 et le solde à 3R ou plus.
- L'espérance en R, le win rate et les moyennes gain/perte sont publiés ; moins de 30 trades reste
  `UNCALIBRATED`. Chaque veto publie son compteur et son effet moyen lorsqu'il s'est déclenché.
- Aucun import vers le chemin d'exécution, aucune activation live/paper, aucune limite relevée.

## 2026-08-30 — Le cron « paper » neutralise réellement toutes les places crypto

- Le cron historique retirait seulement les clés Bitmart avec `unset`. Depuis le passage de la
  place par défaut à Binance, ce garde-fou était incomplet ; de plus, `unset` autorisait le
  chargeur `.env` à réinjecter une clé plus tard dans le processus.
- Le cron définit désormais vides les clés Binance et Bitmart et force le sandbox Binance. Le
  chemin actions reste Alpaca paper. Un test vérifie toutes les variables avant `run_live.py`.
- Les ordres actions non remplis observés le week-end/hors séance ne sont pas forcés : le runner
  les reporte explicitement et doit être lancé pendant la séance NYSE.

## 2026-09-02 — Cœur multi-actifs : changer la corrélation, pas la concentration

- **Question posée** : concentrer le cœur (top-7 au lieu du top-10) améliorerait-il la
  performance ? **Non, et c'était déjà mesuré** : preset 0,82 → 50/50 QQQ 0,99 → QQQ pur
  0,98 → momentum sectoriel 0,86, pendant que le maxDD passe de −19,5 % à −73,6 %. La
  concentration achète du drawdown, pas du Sharpe.
- Le levier resté ouvert est la **corrélation**. Le compte réel affiche **N effectif 1,5**
  (HHI 0,665, top-3 = 87 %) : il se comporte comme une position et demie.
- **Livré** : `packages/backtest/coeur_multi_actifs.py` + `scripts/coeur_multi_actifs_lab.py`
  (`make coeur-multi`). Taille de cœur inchangée à 50 % — SEULE la composition change.
  Quatre variantes figées dans le code (60/25/15, 50/30/20, 40/35/25, inverse-vol),
  comptées dans la déflation. **Règle d'acceptation écrite avant le run** : ΔSharpe > 0
  avec p < 0,05 au test apparié, maxDD non dégradé, DSR ≥ 50 %.
- Le cœur paie 5 bps de rééquilibrage mensuel là où le cœur QQQ n'en paie aucun : la
  comparaison est **défavorable au nouveau venu**, sens d'erreur assumé.
- **Non encore exécuté** : le banc n'a pas tourné (pas de base de prix dans l'environnement
  distant). Aucun chiffre n'est donc avancé — la construction seule est livrée.

## 2026-09-02 — Cahier des charges swing institutionnel : câblé sur l'existant

- Quatre modules neufs, tous **SHADOW**, tous testés (32 tests verts) :
  `indicators/liquidite_ict` (SFP, BOS, CHoCH, OTE, order block, point-in-time),
  `portfolio/metriques_survie` (Ulcer, temps sous l'eau, R² log, ES de Cornish-Fisher),
  `risk/garde_swing` (MM200 marché, plafond de corrélation 30 j),
  `ml/caracteristiques_swing` (z-score EMA, RSI multi, moments glissants, squeeze),
  `strategies/moteur_swing` (`MarketStructureEngine`, `RiskManager`),
  `strategies/moteur_sortie` (`ExitEngine` : temps 15 j, liquidité opposée, partielle CVD).
- **Rien n'a été redupliqué** : DDM (−4R), stops ATR, CPCV, IC de Spearman, promotion ML
  existaient déjà. Les classes ORCHESTRENT, elles ne recodent pas.
- **Trois défauts trouvés par les tests, corrigés dans le code, pas dans le test** :
  1. ES modifié : la première version n'appliquait pas le crochet de Boudt-Peterson-Croux
     → l'ES ressortait **plus clément** que le gaussien alors que la VaR, elle, était bien
     aggravée. Formule complète + garde de domaine (croissance de l'expansion, aggravation,
     plausibilité vs pire observation) ; hors domaine → repli historique explicite.
  2. Pivots : la comparaison large (`>=`) faisait de CHAQUE barre un pivot sur une série
     plate → cassure de structure trivialement vraie sur un titre peu liquide. Extremum
     **strict sur les voisins**.
  3. Features : `sd <= 0` laissait passer un skew de 0,02 sur une série strictement
     géométrique — du bruit d'arrondi standardisé. Plancher **relatif** de dispersion.
- **Recouvrement assumé et documenté** avec `strategies/institutional_price_action` (30/08) :
  SFP, order block et BOS existent désormais en deux exemplaires. Dette P2 déclarée.
- **Dit plutôt que caché** : la jambe 1H/4H de la spec est câblée mais **non mesurable** —
  la base est quotidienne. `raffiner_entree` renvoie « indécidable », jamais « prêt ».

## 2026-09-02 — ExitEngine : la spec de sortie rejoint la mesure du 02/09

- Bloc 5 de la spec swing : sortie de temps à 15 séances, cible = liquidité opposée OU
  plancher 3R (le plus EXIGEANT des deux), partielle 50 % à 2R sur divergence de flux,
  **interdiction du breakeven arbitraire**.
- **Convergence à noter** : cette dernière règle est exactement ce que `sortie_lab` a
  mesuré le 02/09 (ADR-0052). Sans suiveur, payoff 3,21 · Sharpe 0,53 · maxDD −27,8 % ;
  avec suiveur 5 ATR, payoff 2,82 · Sharpe 0,38 · maxDD −29,1 %. L'avantage vit dans la
  queue droite ; tout ce qui la tronque le détruit. La spec et la mesure disent la même
  chose par deux chemins indépendants.
- **Invariant du module** : le stop ne recule jamais et ne bouge que sur un invalidant
  STRUCTUREL (creux confirmé plus haut, validé par un sommet postérieur). Le garde-fou
  est doublé — dans la détection ET dans `appliquer` — parce qu'une règle de sécurité
  présente à un seul endroit finit contournée par un appelant qui écrit le champ.
- **Ordre d'évaluation pessimiste** : stop, puis cible, puis temps, puis partielle. Quand
  une barre touche stop ET cible, des barres quotidiennes ne disent pas l'ordre intrabar :
  retenir la cible fabriquerait de la performance à partir d'une ambiguïté.
- **Approximation nommée** : le CVD exige des transactions signées. Le module utilise le
  proxy « close location value × volume » et s'appelle `cvd_proxy` pour que personne ne
  l'oublie en aval. Une divergence détectée ici est un fait de prix et de volume, pas une
  preuve de flux institutionnel.
- **La borne basse « 2 jours » n'est PAS un verrou** : elle est reportée
  (`hors_fenetre_nominale`) et ne bloque jamais une sortie. En verrou, elle coûterait un
  gain offert au jour 1 — un coût, pas une protection.
- Deux tests écrits d'abord conditionnels (`if partielles:`) ont été **refaits** : un test
  qui passe quand rien ne se produit ne teste rien. Série construite exprès pour que le
  prix fasse 113 → 117 pendant que le CVD approché passe de 6 300 à −2 100, plus le cas
  symétrique où le flux confirme et où la règle ne doit PAS mordre.

## 2026-09-03 — Le cœur multi-actifs est REJETÉ, et la prémisse tenait pourtant

- Banc exécuté sur la vraie base (2 580 séances, 2016-05-31 → 2026-09-02, 24 essais).
  **Aucune variante ne passe la règle d'ADR-0053.** Le cœur QQQ reste en production.
- **Ce qui a marché** : les corrélations. GLD/QQQ +0,11, QQQ/TLT −0,09. Les diversifiants
  sont réellement décorrélés — la construction reposait sur une prémisse VRAIE.
- **Ce qui n'a pas marché** : la décorrélation réduit le drawdown d'un tiers (−25,3 % →
  −17,1 %) mais ne produit AUCUN gain de Sharpe (0,96 → 0,90-0,92, p entre 0,65 et 0,75).
  TLT et GLD n'ont pas de rendement propre sur cette fenêtre ; on achète de la stabilité
  avec du rendement, à un taux défavorable.
- **Le test décisif est le Calmar**, pas le maxDD seul : production 0,605, meilleur cœur
  diversifié 0,532. Le drawdown baisse de 8,2 points, le CAGR de 6,2 — proportionnellement
  plus. Et le levier ne rattrape rien, puisque le Sharpe (invariant au levier) ne bouge pas.
- **L'issue secondaire déclarée d'avance s'est produite** et a été traitée comme prévu :
  remontée pour décision humaine, pas conversion en feu vert.
- **Limite assumée sans en faire un prétexte** : la fenêtre contient 2022 (TLT ≈ −31 %).
  Rejouer sur une autre période après avoir vu le résultat serait exactement ce que la
  déflation punit. Le chiffre reste tel quel.
- **P1 ouvert par la ligne de contrôle** : le QQQ ETF sur l'axe du preset rend −0,4 %/an de
  moins que le cœur de production, t(α) = −6,15, p = 0,000. Minuscule mais pas du bruit, sur
  une ligne censée mesurer le même actif. Soit la production mesure ^NDX (indice non
  achetable, donc dashboard optimiste de façon permanente), soit `blend_equity` désaligne
  positionnellement — quatrième occurrence. `make diag-coeur-qqq` tranche.
- **Le rejet ne dépend pas de cette anomalie** : les variantes perdent aussi contre la ligne
  de contrôle, elle correctement alignée par date.

## 2026-09-03 — Deux hypothèses falsifiées, et la vraie cause était dans le sens de fusion

- `make diag-coeur-qqq` exécuté. **Mes deux hypothèses sont FAUSSES**, et elles restent
  écrites : une hypothèse abandonnée en silence se re-teste six mois plus tard.
  · A « la production mesure ^NDX, indice non achetable » → **SOURCE RETENUE : QQQ (frais)**,
    2 763 barres. C'est bien l'ETF.
  · B « les calendriers diffèrent, `blend_equity` recolle par position » → **zéro séance
    d'écart** dans les deux sens. L'alignement positionnel tombe juste ici, par coïncidence
    des calendriers — pas par construction, ce qui reste un risque latent.
- **Mesuré** : corrélation quotidienne source/ETF **+0,9999**, écart annualisé **−0,71 %/an**
  (et non −0,4 % : le banc mesurait l'écart au niveau du MÉLANGE à 50 %, donc moitié moins).
- **La vraie cause, établie par lecture du code** : les deux chemins fusionnent YAHOO.db et
  market.db **dans des sens opposés**, sur le même symbole.
  · `_load_prices` : `merged.setdefault(jour, barre)` → le PREMIER gagne. YAHOO.db garde la
    priorité, market.db ne comble que les dates manquantes. Le commentaire dit pourquoi :
    « pas de discontinuité d'ajustement (raw vs adjusted) au milieu de l'historique ».
  · `_index_series` : `merge_bars` fait `target[jour] = close` → le DERNIER gagne. market.db
    ÉCRASE YAHOO.db sur toutes les dates communes.
  Si les deux bases n'ont pas le même niveau d'ajustement, la courbe de production est un
  RECOLLAGE entre deux référentiels, avec un saut artificiel au raccord. Étalé sur onze ans,
  ce saut se lit comme une dérive régulière — ce qu'on observe.
- **Ce qui n'est PAS encore établi** : que les deux bases divergent effectivement sur les
  dates communes. Le diagnostic mesure désormais ce point (bloc « COMPARAISON DES DEUX
  BASES ») au lieu de le supposer. Tant qu'il n'a pas tourné, la cause reste un CANDIDAT.
- **Défaut de mon propre diagnostic, corrigé** : sa lecture imprimait « la production mesure
  un actif différent de celui qu'on achèterait » juste après avoir imprimé « SOURCE RETENUE :
  QQQ ». Il se contredisait dans la même sortie. Le texte affirmait la conclusion écrite
  d'avance au lieu de lire ce que le run venait de produire.

## 2026-09-03 — Un ancien tableau de bord bien meilleur : ce qui est vrai, ce qui ne l'est pas

Comparaison demandée entre un ancien dashboard (469,8 % · CAGR 20,1 % · Sharpe 1,34 ·
610 trades · PF 1,48 · n=2391) et l'actuel (330,1 % · 14,9 % · 0,95 · 1 299 trades · PF 1,08).

**Ce qui n'est PAS crédible dans l'ancien.** Le bloc d'attribution affichait
**bêta 0,006 et corrélation 0,008 vs QQQ** pour un portefeuille long-only d'actions
américaines sur 9,5 ans. Aucun livre long d'actions US ne corrèle à 0,008 avec le Nasdaq —
l'ordre de grandeur est 0,6 à 0,9. Ce chiffre-là ne décrit rien de réel, et c'est
précisément lui qui portait « Alpha annualisé 17,8 % » et « Contrib. Alpha 365,1 % », les
deux nombres les plus flatteurs de la page. `obsidian.attribution` aligne par `min(len)` +
`[-n:]` — POSITIONNEL, la classe de bug déjà corrigée trois fois ailleurs. L'ancienne page
imprimait d'ailleurs sa propre mise en garde : « DSR≈0 → pas d'alpha directionnel prouvé »
et « ⚠ Sous-performe QQQ en absolu (368 % vs 481 %) ».

**Un défaut réel trouvé et CORRIGÉ au passage.** La même page affichait deux Sortino,
**1,29** en tête et **1,82** dans la table du cœur, sur des courbes dont les Sharpe
différaient de 0,01. Trois conventions coexistaient. Mesuré sur 2 400 points :
  · `perf_summary` — écart-type des négatifs → 1,04× la valeur correcte (acceptable) ;
  · `index_core._stats` — RMS des négatifs divisé par le COMPTE DES PERTES → **0,70×**,
    soit 30 % trop bas, au point de passer sous le Sharpe ;
  · définition : racine de la moyenne des `min(r,0)²` sur le nombre TOTAL d'observations.
`index_core._stats` est corrigé, avec quatre tests dont un qui CHIFFRE l'ancien écart.
Le symptôme à retenir : **un Sortino inférieur au Sharpe** signale un dénominateur mal
normalisé. Mon propre banc `coeur-multi` en souffrait — ses Sortino publiés le 03/09 sont
donc 30 % trop bas ; les VERDICTS ne bougent pas, la règle porte sur Sharpe/maxDD/DSR.

**Ce qui interdit la comparaison, indépendamment de tout ça.** Les deux mesures ne portent
pas sur la même fenêtre : n=2391 depuis 2017-04-25 contre 2 580 séances depuis 2016-03-01.
Le backtest actuel inclut **13 mois de plus au début**. Le texte de la page le dit
lui-même : « Lis d'abord la colonne Fenêtre ». Et le P1 du 02/09 reste ouvert — Sharpe 0,65
puis 0,38 sur un code identique au caractère près, à un jour d'écart. **Tant qu'il n'est pas
expliqué, aucune comparaison entre deux dates n'est valide, celle-ci comprise.**

**Ce que je ne sais PAS expliquer** : 610 → 1 299 trades, plus du double, alors que la
fenêtre ne grandit que de 8 % et que l'univers-graine est inchangé (1 047 lignes sur tous
les commits vérifiés). C'est un changement de règle ou d'ensemble éligible, pas de durée.

**L'expérience qui tranche**, à lancer avant toute autre conclusion :
`QUANT_HISTORY_DAYS=3600 make index-core` — le code ACTUEL sur la fenêtre ANCIENNE.
Sharpe qui remonte vers 1,34 → c'est la fenêtre. Sharpe qui reste vers 0,95 → c'est le code.

## 2026-09-03 — C'était la FENÊTRE, pas le code. Et le code s'est amélioré.

`QUANT_HISTORY_DAYS=3600 make index-core` — code ACTUEL sur la fenêtre ANCIENNE.

| | ancien dashboard | reproduction (3 600 j) | plein historique |
|---|---|---|---|
| Sharpe, blend 50 % | 1,33 | **1,33** | 0,96 |
| CAGR | 20,3 % | 18,5 % | 15,3 % |
| maxDD | −28,7 % | −22,4 % | −25,3 % |

**Le Sharpe retombe EXACTEMENT sur l'ancienne valeur.** L'écart 0,96 → 1,33 est imputable
à la fenêtre, pas au code : le backtest actuel démarre treize mois plus tôt (2016-03 au
lieu de 2017-04) et inclut une période plus difficile. Rien n'a régressé.

**Le code a même AMÉLIORÉ le portefeuille, à fenêtre égale.** Sur le preset pur :

| | ancien | actuel (même fenêtre) |
|---|---|---|
| CAGR | 17,7 % | 14,7 % |
| Sharpe | 0,99 | **1,12** |
| maxDD | −31,7 % | **−25,4 %** |

Trois points de CAGR en moins, mais **+0,13 de Sharpe et 6,3 points de drawdown en moins**.
Les correctifs d'alignement n'ont pas coûté de la performance : ils ont retiré du rendement
qui venait avec un risque disproportionné. C'est le sens attendu quand on corrige une fuite.

**Contrôle interne qui passe** : t(α) = 3,35 identique sur les lignes 0 %, 25 %, 50 %, 75 %,
et −0,03 à 100 %. Ce n'est pas un bug — pour un mélange `c·cœur + (1−c)·preset`, l'alpha ET
son erreur-type sont tous deux proportionnels à (1−c), donc le t est INVARIANT en c. À
100 % de cœur la variante EST la référence, donc t = 0. La fonction fait ce qu'elle annonce.

**Le Sortino corrigé se comporte comme prévu** : il est désormais SUPÉRIEUR au Sharpe sur
toutes les lignes (1,96 contre 1,33 à 50 %), là où il passait dessous avant le correctif.

**PIÈGE À NE PAS PRENDRE — la ligne 25 %.** Sharpe 1,42 contre 1,33, maxDD −18,2 % contre
−22,4 % : meilleure sur les deux axes. Mais **ΔSharpe +0,09, IC95 [−0,25 ; +0,42],
p = 0,612**, pour un seuil détectable de ±0,29. C'est du bruit de sélection sur cinq ratios
essayés. **On ne bouge pas.** Ce qui EST discernable ne va que dans un sens : 75 % (p=0,027)
et 100 % (p=0,011) sont significativement PIRES que 50 %.

**À AUDITER AVANT TOUTE CHOSE — le momentum sectoriel.** CAGR 55,5 % à 100 % de cœur,
26,8 % à 25 %, DSR 100 %. Un CAGR de 55 % sur 9,4 ans n'est pas un résultat, c'est une
alerte : biais du survivant ou fuite. Le script prévient pour le top-10 méga-caps, pas pour
celui-ci. À passer au `leakage-hunter` avant d'en dire un mot de plus.

**NARROWING DU P1 (instabilité entre runs).** Les deux runs consécutifs de ce soir sont
**identiques au caractère près**. Le code est donc DÉTERMINISTE ; l'instabilité 0,65 → 0,38
observée le 02/09 s'était produite à un JOUR d'écart, donc après un rafraîchissement de
données. **Hypothèse à tester** : elle vient du même défaut que l'anomalie du cœur QQQ —
`_index_series` laisse `market.db` écraser `YAHOO.db`, si bien que chaque `make daily` peut
déplacer le niveau d'ajustement de TOUT l'historique. Deux P1 qui n'en feraient qu'un.

## 2026-09-03 — 87 % de réussite sur le compte réel : une déduction fausse, corrigée

**J'ai avancé un chiffre déduit au lieu de mesuré, et il était faux.** J'avais conclu que
les 26 lots ouverts portaient « environ −5 600 $ de latent », par rapprochement entre
l'espérance affichée (39 × 149,27 $ = 5 821 $ réalisés) et le rendement du compte (+0,2 %).
Les positions réelles disent **P&L latent +614,53 $**, donc POSITIF. Le biais de sélection
que je décrivais ne s'est PAS matérialisé sur ce compte.

**Le mécanisme reste réel et générique** : un système qui rééquilibre allège ce qui a monté
et conserve ce qui a baissé, donc le sous-ensemble fermé est sélectionné. Mais il fallait le
MESURER avant de l'affirmer, et c'est exactement ce que je n'ai pas fait.

**Livré quand même, parce que le garde-fou vaut indépendamment** :
`packages/research/biais_fermeture.py` + branchement sur `/api/journal`. Le panneau publie
désormais À CÔTÉ des chiffres existants (jamais à leur place) : latent des lots ouverts, P&L
total, **espérance sur TOUTES les positions**, et un avertissement chiffré qui ne sort QUE
si part ouverte ≥ 20 % ET latent négatif — donc PAS aujourd'hui. Un lot sans prix est EXCLU,
jamais valorisé à son entrée : le compter à zéro de latent fabriquerait un gagnant neutre à
partir d'un trou de données. Cinq tests, présentés comme un scénario CONSTRUIT et non comme
l'état du compte.

**CE QUI RESTE OUVERT — ET QUI SE MESURE, MAINTENANT.** 5 821 $ de réalisé + 614 $ de
latent = 6 435 $ sur ~100 000 $, soit ~6,4 %, alors que le tableau de bord affiche le
portefeuille RÉEL à **+0,2 % sur deux mois**. Ces deux chiffres ne se réconcilient pas.
Plutôt que d'énoncer une nouvelle hypothèse — la première était fausse — j'ai écrit
`scripts/diag_journal_compte.py` (`make diag-journal`), qui MESURE les trois causes
possibles et imprime le résidu inexpliqué :
  1. le filtre `legacy` : combien de lots et combien de dollars réalisés le panneau
     masque-t-il, et dans quel SENS ;
  2. la fenêtre : les sorties du journal tombent-elles dans la période couverte par
     `equity_history`, ou déborde-t-on ;
  3. le latent RÉEL, lu chez le courtier — jamais reconstruit depuis un prix d'entrée.
Le script ne conclut pas quand les chiffres ne tranchent pas : le résidu est imprimé
comme résidu.

**CE QUI N'EST PAS CONTAMINÉ, vérifié dans le code avant de le dire.** Le verdict GO/NO-GO
du 2026-08-06 (`research/rdv_paper.compare`) lit la COURBE D'EQUITY, qui intègre le latent
par construction — pas le win rate. Le verdict est sain. En revanche le TEXTE du panneau
annonce que le journal est « la matière première du verdict » : c'est faux et ça invite à la
mauvaise lecture. P2.

**Autre lecture du même tableau, à ne pas perdre de vue.** Sur dix ans : portefeuille
330,8 % / CAGR 14,9 % / Sharpe 0,95 / maxDD −25,5 % contre Nasdaq 100 572,5 % / 19,9 % /
0,92 / −35,6 %. La stratégie **sous-performe le QQQ en absolu** avec un Sharpe à peine
meilleur et **10 points de drawdown en moins**. Un Nasdaq à risque réduit, pas une machine
à alpha — ce que dit aussi le DSR.

## 2026-09-03 — Mesuré : 5 557 $ manquent entre le journal et le compte

`make diag-journal` a tourné. Ce qui est désormais ÉTABLI, et ce qui ne l'est pas.

**Le filtre `legacy` n'explique rien.** Il masque 137 lots, mais **0 fermé et 0,00 $ de
réalisé**. Ma première piste tombe : le panneau ne cache aucune perte réalisée.

**La fenêtre est bonne côté Alpaca.** Courbe du 2026-06-22 au 2026-09-03, sorties du
journal du 2026-08-27 au 2026-09-02 : DANS la fenêtre. (Bitmart déborde, mais ce compte
vaut 0,10 $ — non matériel.)

**Le résidu, lui, est massif.**

    réalisé (tous lots)            +5 821,43 $
    latent des positions ouvertes    +611,14 $
    attendu sur le compte          +6 432,57 $
    variation constatée              +875,95 $
    RÉSIDU INEXPLIQUÉ              -5 556,62 $

**Le fait le plus frappant, et il n'était pas dans mes hypothèses : 39 aller-retours en
CINQ séances** (27/08 → 02/09), 5 821 $ de gains réalisés, sur un compte qui n'a bougé que
de 876 $ **en deux mois et demi**. Un rythme et un montant qui, à eux seuls, demandent une
explication.

**Défaut de mon propre script, trouvé par sa sortie et corrigé.** Le total affichait
+875,95 $ quand la somme des lignes donnait +879,34 $. Cause : la courbe était relue APRÈS
`build_snapshot()`, qui ENREGISTRE le point du jour — deux lectures, deux séries. Elle est
maintenant lue une seule fois, en amont. Une mesure qui ne se recoupe pas avec elle-même ne
vaut rien, si petit que soit l'écart.

**Deux causes restent, et le script les mesure désormais toutes les deux :**
  1. **VERSEMENTS/RETRAITS** — `_mouvements` détecte les sauts journaliers hors norme
     (seuil relatif : 6 × l'écart absolu médian de la série, pas un montant arbitraire).
     Un retrait de ~5 500 $ apparaîtrait comme un saut isolé.
  2. **LOTS FANTÔMES** — `_lots_vs_courtier` compare, symbole par symbole, les quantités
     des lots OUVERTS du journal aux quantités RÉELLEMENT détenues. Le réalisé s'obtient
     en appariant les ventes à des lots ouverts : si le journal porte des lots que le
     courtier ne confirme pas, ces appariements fabriquent des gains sans contrepartie.

**Rien n'est conclu tant que ce run n'a pas eu lieu.**

**Cause du `make sync` introuvable, confirmée par la sortie** : le HEAD local était sur
`43b15a9 (origin/main, main)`. Un déploiement avait remis la branche sur `main`, où la
cible `sync` n'existe pas encore. Le piège d'amorçage se reproduira à chaque déploiement
tant que la branche n'est pas fusionnée.

## 2026-09-03 — Le journal ne décrit pas le compte. Les 5 602 $ sont expliqués.

`make diag-journal` a éliminé les deux causes candidates et en a établi une troisième,
que je n'avais pas envisagée.

**ÉLIMINÉ — les versements/retraits.** Aucun saut hors norme sur Alpaca (seuil 3 984 $/jour,
zéro dépassement). Le résidu n'est pas de l'argent sorti du compte.

**ÉLIMINÉ — le filtre `legacy`.** 137 lots masqués, mais **0 fermé et 0,00 $ de réalisé**.

**ÉTABLI — le journal porte des positions que le compte n'a plus.** La réconciliation
quantité par quantité, symbole par symbole :

  · **~80 actions** (AAPL, BBY, CNC, ICLN, NWL 2 861 titres, ZION…) : journal > 0,
    **courtier = 0**. Le compte ne détient plus rien de tout cela.
  · **QQQ : 137,105 au journal contre 70,452 chez le courtier** — presque le DOUBLE.
  · **La poche crypto est comptée deux fois sous deux conventions** : `AVAX/USDC` au
    journal (41,9) et `AVAXUSD` chez le courtier (214,6), `LTC/USDC` 7,2 contre `LTCUSD`
    37,1, et ainsi de suite. Même actif, deux noms, jamais appariés — le dépôt connaissait
    déjà ce piège (`execution/routing`, incident du 27/08 : une liquidation crypto bloquée
    par le calendrier NYSE parce qu'`AAVEUSD` n'était pas reconnu comme crypto).

**LA CONSÉQUENCE, ET ELLE EST MÉCANIQUE.** Le P&L réalisé s'obtient en appariant les ventes
aux lots ouverts en FIFO. Les ventes RÉCENTES (27/08 → 02/09) se sont donc appariées à des
lots d'un portefeuille que le compte ne détient plus, au prix de revient de CE
portefeuille-là. Les 5 821 $ « réalisés » sont le produit de cet appariement, pas de
l'argent gagné. Les 87 % de réussite et les 149,27 $ d'espérance portent sur des
aller-retours qui n'ont pas eu lieu tels que le journal les décrit.

**Ce que ça ne remet PAS en cause** : le verdict GO/NO-GO lit la courbe d'equity du compte
(vérifié dans le code le 03/09), pas ces statistiques. La décision de passage au réel n'est
pas contaminée.

**Livré** : `biais_fermeture.reconcilier` + `symbole_canonique` (les trois conventions de
nommage ramenées au même actif, sinon toute la poche crypto ressortirait en faux écart),
branchés sur `/api/journal`. Quand la réconciliation échoue, la charge utile porte
`fiable: false` et le motif. **Le chiffre n'est pas retiré — il est MARQUÉ** : le retirer
ferait disparaître le problème de la vue au lieu de le montrer. Dix tests.

**Reste à décider (P0 avant tout usage du journal)** : que faire des ~163 lots orphelins.
Les solder à leur date de sortie réelle demande un historique de fills que nous n'avons
peut-être plus ; les archiver en `legacy` les sort du calcul sans mentir sur le passé.
C'est une décision, pas une correction automatique.

## 2026-09-03 — Réparer le journal : la cause d'abord, le passé avec la vérité du courtier

**LA CAUSE, CORRIGÉE.** `live_roundtrip.open_lots` appariait les ventes aux lots par
`t.instrument == instrument`, **exact au caractère près**. Les lots crypto sont écrits
« AVAX/USDC » et les ventes reviennent d'Alpaca en « AVAXUSD » : **aucune vente crypto ne
pouvait fermer son lot**, depuis l'origine, sans qu'aucune erreur ne soit levée. La poche
crypto s'accumulait donc en orphelins. L'appariement se fait désormais par symbole
CANONIQUE. Les 17 tests d'aller-retour existants passent inchangés.

**LE PASSÉ, RÉPARABLE — et par la meilleure source.** `AlpacaBroker.orders()` rend les
ordres exécutés avec symbole, sens, quantité, prix et DATE. La vérité est donc récupérable :
pas besoin d'estimer quoi que ce soit.

**POURQUOI PAS `legacy=1`, qui aurait été le geste rapide.** Ce drapeau signifie « fill
importé sans features de décision ». Ces lots ne sont pas ça : ce sont des lots dont la
SORTIE n'a jamais été enregistrée. Réutiliser un drapeau pour un second sens le rend
illisible — dans six mois personne ne saurait pourquoi ils sont legacy ni ce qu'on croyait
en les marquant.

**CE QU'ON FAIT À LA PLACE — la pratique comptable ordinaire.** On ne supprime ni ne
réécrit un enregistrement : on POSTE UNE ÉCRITURE DE CORRECTION, datée, avec son motif
(`exit_reason = "reconciliation-journal"`) et sa source. Chaque fermeture porte le prix et
la **date du fill réel**, pas ceux du jour de la réparation.

**CE QU'ON REFUSE DE FAIRE.** Un lot dont aucune vente du courtier ne rend compte reste
OUVERT et est signalé. Le fermer « au dernier prix connu » fabriquerait un P&L qui n'a
jamais existé — exactement l'erreur qu'on répare.

**Livré** : `scripts/reconcilier_journal.py` (`make reconcilier-journal`). **Simulation par
défaut** : il imprime le plan — fermetures appariées, P&L correspondant, lots restés
orphelins avec leurs dates — et n'écrit rien. `--appliquer` écrit, après **sauvegarde
horodatée de `journal.db`**. Six tests couvrent le plan seul, sans base ni courtier : les
deux conventions de nommage, le FIFO, la vente partielle, la vente excédentaire (ignorée,
jamais inventée), et l'ordre chronologique des ventes.

Suites `tests/execution` + `tests/research` : **447 verts**.

## 2026-09-03 — L'outil de réparation avait trois défauts, découverts APRÈS son passage

Le run réel a posté 185 écritures (P&L des fermetures **−1 391,77 $** : la liquidation de
juin, jamais enregistrée — le journal masquait donc des PERTES). 39 lots restent ouverts,
sans vente correspondante, et c'est le comportement voulu.

Mais la sortie contenait 185 avertissements « TradeRecord LEG-… enregistré SANS
features_snapshot ». **Ce n'était pas du bruit : c'était le journal qui signalait ma faute.**

**Défaut 1 — le drapeau `legacy` n'était pas conservé.** J'écrivais toutes les fermetures
en `legacy=False`, y compris celles de fills IMPORTÉS. Résultat : ces fermetures entraient
dans le périmètre AFFICHÉ, sans features de décision. J'assainissais le registre en
polluant exactement le chiffre que je cherchais à assainir. Le drapeau voyage désormais
avec le lot.

**Défaut 2 — collision d'identifiants sur les ventes partielles.** Un lot soldé en
plusieurs ventes produisait plusieurs enregistrements au même id `-R1` ; l'UPSERT n'en
gardait qu'un et les fermetures intermédiaires disparaissaient **sans bruit**. Visible dans
la sortie : `LEG-ad4ac9fa7f59-R1 (QQQ)` revient une dizaine de fois. Suffixe numéroté.

**Défaut 3 — trouvé par le test, jamais atteint en production.** Une date de fill sans
fuseau lève une `TypeError` en pleine boucle d'écriture, donc **après** des enregistrements
déjà commités. Une réparation de registre qui s'arrête à mi-chemin est pire que pas de
réparation. `_horodatage` normalise en UTC aware ou refuse la ligne.

**Ce que ça dit de ma méthode.** J'ai livré un outil qui écrit dans un registre avec six
tests portant uniquement sur le PLAN, aucun sur l'ÉCRITURE. Les trois défauts sont tous du
côté non testé. Le mode simulation par défaut et la sauvegarde horodatée ont limité les
dégâts — c'est précisément à ça qu'ils servent — mais ils ne remplacent pas des tests sur
le chemin qui écrit. Trois tests d'écriture ajoutés (drapeau conservé dans les deux sens,
absence de collision d'ids).

**À FAIRE — restaurer et rejouer.** La sauvegarde
`journal.avant-reconciliation-20260903-195231.db` contient l'état d'avant. La restaurer
puis relancer avec la version corrigée est la seule façon d'obtenir un registre propre :
les 185 écritures actuelles portent le mauvais périmètre.

## 2026-09-03 — Réparation appliquée, et ce qu'elle ne répare PAS

Sauvegarde restaurée, version corrigée rejouée : **185 écritures, zéro avertissement**.
La prédiction posée avant le run (« les 185 lignes `LEG-…` doivent disparaître ») s'est
vérifiée — le drapeau `legacy` voyage bien avec le lot.

**CE QUI EST RÉPARÉ** : le registre des lots OUVERTS. Les ~80 actions liquidées en juin
sont désormais fermées au prix et à la date des fills réels, dans leur périmètre d'origine.
P&L de ces fermetures : **−1 391,77 $** — le journal masquait des PERTES, pas des gains.

**CE QUI NE L'EST PAS, et il faut le dire clairement.** Les **39 aller-retours déjà fermés**
du panneau (87 % de réussite, 149,27 $ d'espérance) sont INCHANGÉS. Ils avaient été produits
entre le 27/08 et le 02/09 par `close_sells`, qui les a appariés en FIFO aux lots du vieux
portefeuille — donc à des prix de revient de juin. Fermer les lots orphelins ne rétroagit pas
sur des round-trips déjà écrits. **Les statistiques affichées restent fausses**, et c'est
`reconcilier` qui les marque `fiable: false`.

**Effet attendu sur le résidu** : il se réduit d'environ 1 392 $ (le réalisé total passe de
5 821 $ à ~4 430 $) mais **ne se referme pas**. Restent les 39 lots sans vente
correspondante, l'écart de quantité crypto, et surtout ces 39 round-trips mal fondés.

**Décision à prendre (P1)** : recalculer ces 39 aller-retours suppose de les annuler puis de
les rejouer contre le bon vivier de lots. C'est une opération plus invasive que la
précédente, sur des enregistrements déjà publiés. À ne pas lancer sans l'avoir spécifiée.

## 2026-09-03 — La réparation a marché, et elle a révélé un défaut plus profond

**Le résidu s'est réduit comme annoncé** : −5 557 $ → **−4 195 $**, soit −1 362 $, l'ordre
de grandeur prévu. Le drapeau `legacy` a bien été conservé (zéro avertissement), et la
répartition le confirme : legacy=1 porte désormais 155 fermetures pour **−1 847 $** —
c'est là que dormaient les pertes.

**Le panneau affiché a changé, et dans le bon sens** : 39 → 69 aller-retours, win rate
**87 % → 71 %**, espérance 149,27 $ → 90,97 $. Plus honnête, mais toujours pas juste.

**CE QUE LA TABLE RÉVÈLE, ET QUI EST PIRE.** Les quantités restantes valent EXACTEMENT la
moitié des quantités initiales, symbole après symbole :

    AAPL  47,282434 → 23,641217      BXP  212,619953 → 106,309977
    CNC  228,805493 → 114,402746     D    215,158384 → 107,579192
    EFA  146,212389 →  73,106194     ICLN 603,200213 → 301,600106
    MO   221,628274 → 110,814137     IWM   44,986204 →  22,493102

Une moitié exacte, répétée sur des dizaines de titres, n'est pas un hasard de marché : les
ventes du courtier ont soldé **une copie** et laissé **l'autre**. Le journal enregistre
donc chaque lot DEUX FOIS. C'est cohérent avec tout le reste : QQQ 137,1 au journal contre
70,45 détenus (facteur ~2), et un réalisé qui ne peut structurellement pas se réconcilier.

**Mesure ajoutée plutôt qu'affirmation** : `_doublons` regroupe les lots ouverts par
(symbole, quantité, prix d'entrée, jour) et compte les enregistrements excédentaires. Deux
achats réels identiques au millionième le même jour sont possibles ; c'est pourquoi on
COMPTE et on montre l'échantillon au lieu de conclure.

**AUCUNE ÉCRITURE DE PLUS avant d'avoir trouvé la cause.** Supprimer les doublons dans le
registre traiterait le symptôme et les laisserait revenir au prochain rebalancement. La
cause est dans le chemin d'écriture (`live_journal` / la boucle de réconciliation), et
c'est là qu'il faut regarder.

**Note sur la mesure elle-même** : entre deux runs le compte a changé de composition (le
courtier détient maintenant AAVE, MRNA, PRU, SLG, STT, TER, TROW, TTWO, UNH, ZION en plus).
Le portefeuille bouge pendant qu'on le mesure — à garder en tête avant de lire un écart
comme une anomalie.

## 2026-09-03 — Troisième hypothèse fausse, et la cause enfin mesurée : l'historique était tronqué

**« Le journal écrit chaque lot en double » est FAUX.** La mesure ajoutée le dit sans
ambiguïté : « aucun doublon — les lots ouverts sont tous distincts ». Troisième hypothèse
de ma part réfutée par les données dans cette session (après « ^NDX » et « désalignement de
calendrier »). Les fermetures AAPL portaient d'ailleurs des quantités DIFFÉRENTES
(11,763496 et 11,877721) : des lots distincts, pas des copies.

**LA CAUSE, ET ELLE ÉTAIT SOUS LES YEUX.** J'ai demandé 500 ordres à Alpaca, l'API en a
rendu **202**. `get_orders` plafonne à 500 par appel ET rend les plus RÉCENTS d'abord : un
seul appel ne peut donc pas couvrir un historique plus long, et il le tronque **sans rien
dire**. La moitié manquante de chaque position n'était pas un doublon — c'étaient les
ventes ANCIENNES qui n'étaient jamais arrivées jusqu'au script.

**Corrigé** : `AlpacaBroker.orders` pagine désormais avec `until` = le plus ancien
horodatage déjà vu. La boucle est extraite en fonction PURE (`paginer`) pour être testable
sans le SDK — une boucle de pagination est exactement le genre de code où une condition
d'arrêt mal posée tourne à l'infini ou tronque en silence. Deux garde-fous, pour deux
défaillances différentes : le nombre de pages est borné (API qui répond toujours du neuf)
et l'horodatage doit STRICTEMENT reculer (API qui répond toujours pareil). Cinq tests.

**Le script REND COMPTE de ce qu'il récupère** : nombre d'ordres, nombre de ventes, et un
avertissement explicite si le plafond demandé est atteint — c'est-à-dire si l'historique
peut ENCORE être tronqué. La leçon de la journée tient dans cette ligne : un chiffre qui
peut être tronqué doit dire quand il l'est.

**Ce que ça permet enfin** : rejouer la réconciliation avec l'historique COMPLET. Les 42
lots orphelins devraient trouver leurs ventes, et le résidu se refermer nettement.

## 2026-09-03 — La pagination a marché à moitié, et a révélé que l'outil n'était pas rejouable

**Ce que la pagination a changé** : 202 → **419 ordres** récupérés. Mais **202 ventes**,
exactement comme avant. L'historique des ACHATS était tronqué, celui des VENTES ne l'était
pas. Ma quatrième hypothèse de la journée n'est donc que partiellement vraie — le correctif
est bon, il n'explique pas ce qu'on croyait.

**LE VRAI DÉFAUT, révélé par le second plan.** Sur un journal DÉJÀ réparé, le script
proposait **50 fermetures de plus**, sur les **mêmes 202 ventes**, et **toutes à +0,00 $**.
L'outil n'est pas IDEMPOTENT : à chaque passage il réapplique tout l'historique de ventes
aux lots encore ouverts. Le relancer assez souvent finirait par fermer tous les lots, qu'une
vente les couvre ou non. Un outil de réparation qui n'est pas rejouable est un outil qui
fabrique des données au second passage.

**Le signal était dans le chiffre** : cinquante fermetures d'affilée à exactement +0,00 $
n'est pas une distribution de P&L, c'est la signature d'un appariement qui tourne à vide.

**Corrigé** : chaque fermeture porte désormais l'IDENTIFIANT du fill qui l'a produite
(`reconciliation-journal:<id>`), et un fill déjà consommé n'est jamais rejoué. `orders()`
expose l'id. Quatre tests nouveaux.

**ET UN GARDE-FOU RÉTROACTIF, parce que le mal est déjà fait.** Les 185 fermetures déjà
écrites portent le motif NU, sans identifiant : elles sont intraçables, on ne peut pas
savoir quelles ventes elles ont consommées. Le script REFUSE donc de tourner sur un tel
journal et renvoie à une sauvegarde, plutôt que de deviner. Deviner ici reviendrait à
fabriquer du réalisé — exactement ce que cet outil existe pour empêcher.

**Ce que l'utilisateur doit faire** : restaurer `journal.avant-reconciliation-20260903-195231.db`
(l'état d'AVANT toute réparation) puis relancer UNE fois avec cette version.

## 2026-09-03 — Le « résidu inexpliqué » n'était pas inexpliqué : ma formule était incomplète

**Réponse à la question posée** (« est-ce des ordres passés jamais réalisés ? ») : NON, et
c'est le code qui le dit — `AlpacaBroker.orders` saute tout ordre dont `filled_qty` vaut
zéro. Les ordres non exécutés n'entrent nulle part dans ces chiffres. Piste fermée sans
avoir besoin de mesurer.

**L'ARITHMÉTIQUE QUE J'AURAIS DÛ POSER AU PREMIER JOUR.** L'identité d'une période est :

    Δequity = réalisé + latent(fin) − latent(DÉBUT) + flux − frais

Mon script compare `réalisé + latent(fin)` à `Δequity`. Il **omet `latent(début)`**. Le
« résidu inexpliqué » de −4 210 $ vaut donc, pour l'essentiel, le gain ou la perte NON
RÉALISÉ que portaient déjà les positions au premier point de la courbe (2026-06-22). Les
versements ayant été mesurés à zéro, il ne reste que ce terme et les frais hors P&L.

**Ce n'est donc pas une anomalie à effacer** : c'est la part du P&L qui précède la fenêtre
de mesure. Vouloir la faire tomber à zéro reviendrait à demander qu'un compte n'ait pas
d'histoire avant qu'on commence à le mesurer.

**MESURE AJOUTÉE POUR LE PROUVER — et non pour l'affirmer.** `_base_de_cout` compare le
prix d'entrée de chaque lot à la CLÔTURE de sa date d'entrée dans la base de prix. Si les
positions déjà détenues ont été journalisées au coût moyen du courtier, leur lot porte une
date récente et un prix ancien : l'écart sera massif et systématique. S'il est nul, cette
explication tombe comme les cinq précédentes et le script le dira.

**Mesure ajoutée aussi** : `_couverture_achats` — le journal connaît-il tous les achats du
compte ? Un achat sans lot correspondant est un trou par lequel le réalisé fuit, et aucune
réparation de lots orphelins ne le refermera.

**Vocabulaire corrigé** : « RÉSIDU INEXPLIQUÉ » devient « ÉCART », avec l'identité écrite
sous le tableau. Un mot qui dit « inexpliqué » pousse à chercher un coupable là où il n'y a
qu'un terme manquant dans une formule.

**BILAN DE LA JOURNÉE SUR CE SEUL PROBLÈME — six hypothèses, cinq fausses :** ^NDX,
désalignement de calendrier, double écriture, troncature des ventes, non-idempotence
(vraie, mais défaut de MON outil, pas cause du résidu), et enfin `latent(début)`. Toutes
sont tombées sur des mesures. La leçon n'est pas qu'il fallait mieux deviner : c'est que
la première chose à écrire, face à un écart comptable, est l'IDENTITÉ COMPTABLE.

## 2026-09-03 — La couverture répond : le journal ne connaît que la MOITIÉ des achats

**LA MESURE QUI TRANCHE, enfin.** Sur 87 symboles achetés chez le courtier, **57 sont
couverts par le journal et 30 sont INCOMPLETS** :

    AVAX  acheté 1 238,95  ·  journal   626,49      T     acheté 141,78  ·  journal 80,00
    LINK  acheté   959,31  ·  journal   550,50      AAVE  acheté 141,07  ·  journal 42,55
    LTC   acheté   286,88  ·  journal   114,87      PATH  acheté 138,80  ·  journal  9,00
    SOL   acheté   212,49  ·  journal    63,52      SLG   acheté  69,36  ·  journal 19,54

Le journal enregistre **environ la moitié** des achats crypto, et 9 titres sur 139 pour
PATH. Ces achats n'ont donc AUCUN prix de revient au journal : quand ils sont vendus, le
compte encaisse le résultat et le journal n'a rien à lui opposer.

**CONCLUSION D'INGÉNIERIE, et elle est définitive : le journal ne peut pas être la source
de vérité de la performance du compte.** Il n'enregistre que ce que la boucle de
réconciliation a écrit, jamais l'activité complète. Aucune réparation de lots orphelins ne
refermera cet écart — j'ai passé la soirée à réparer un registre dont le vrai problème est
qu'il est INCOMPLET, pas qu'il est faux.

**Ce qui est déjà correct sur le site, et qu'il faut préserver** : la ligne « Portefeuille
RÉEL » et le verdict GO/NO-GO lisent la COURBE D'EQUITY, pas le journal. Ces chiffres-là
sont justes et le restent.

**Bug de MA mesure, corrigé** : `_cours_du_jour` passait une BARRE à `_jour`, qui attend un
horodatage. La comparaison échouait donc toujours, et le bloc annonçait « 0 lot comparable
» — un zéro qui ressemblait à une absence de données alors qu'il signalait mon bug. C'est
la deuxième fois aujourd'hui qu'une de mes mesures ment par omission ; d'où la règle qui
en sort : **un zéro doit toujours être distingué d'un « je n'ai pas pu mesurer »**.


## Session 2026-09-06 — Réparer le build de l'analyse de portefeuille

La fusion avait entrelacé deux versions des composants : imports, hooks, rendus et variables
redéclarés, avec des accolades manquantes. Rétablissement des blocs cohérents du commit
e65588d pour Evidence, ImportWizard, Scenarios et portfolio-scenarios, conservant la progression
étape 4, le calcul sous plafond et ses compteurs. Workspace réexporte le Client existant pour
éviter deux implémentations. Un job Next.js build contrôle désormais chaque PR dans la CI.

Validation : npm run build réussi, /analyse-portefeuille/ répond HTTP 200 en serveur de production ;
make test : 1942 passed, 1 skipped (156 s). Le contrôle tsc séparé relève seulement deux erreurs
préexistantes dans components/landing/Scene.tsx (types Three.js), hors du correctif.
