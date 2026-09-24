# 03 — TODO (backlog priorisé)

> **Passation IA (2026-08-29)** — la carte technique consolidée est disponible dans
> `docs/AI_CODEBASE_MAP.md`. Elle décrit le flux complet, les frontières de sécurité et le protocole
> d'audit ; les priorités ci-dessous restent la seule roadmap opérationnelle.

> P0 = socle indispensable · P1 = cœur de la valeur (screening→trading paper) ·
> P2 = sophistication (ML, front, live). On n'ouvre P1 que quand P0 est vert.

- [x] **~~P2 — Onglet X : filtres et recherche~~ — LIVRÉ (24/09, ADR-0194).** L'onglet
      n'existait pas : chaîne entière construite (`packages/social/`, `/api/social/x/posts`,
      `/x`, `make x-ingest`). 44 tests. Filtres compte / mot-clé / classification /
      direction / actif, combinables ; recherche insensible à la casse ET aux accents,
      partielle, portant aussi sur les niveaux extraits.
- [x] **~~P1 — L'onglet X n'a JAMAIS vu de donnée réelle~~ — FERMÉ (24/09).** Première
      ingestion : **34 publications** des deux canaux Telegram, dont 6 `TRADE_SIGNAL`.
      Les filtres tournent sur du vrai contenu. Images ajoutées dans la foulée (ADR-0195).
- [x] **~~P1 — Les comptes X suivis n'ont AUCUNE source~~ — FERMÉ (24/09, ADR-0199).**
      Mesuré sur le VPS : twiiit ne lit ni astekz (403) ni eliz883 (page illisible), et
      a changé de comportement en une heure — inutilisable. **RSSHub auto-hébergé lit
      les QUATRE** : astekz 18, eliz883 17, trendspider 19, micro2macr0 12. Première
      ingestion : **66 nouvelles, stock 103**, aucun rejet. eliz883 basculé de Telegram
      vers X à la demande de l'utilisateur (Telegram ne garde que walshwealth1122).
- [x] **~~P1 — Les images des tweets ne s'affichent pas~~ — FERMÉ (24/09).** Diagnostic
      en quatre étapes sur le VPS : RSSHub envoie les images (✓), la base les a
      (trendspider 18/19, astekz 8/18…) (✓), mais **l'API servait
      `?format=jpg&amp;name=orig`**. La description RSS est du HTML, où `&` s'écrit
      `&amp;` — y compris dans l'adresse d'une image, que `rss.py` relayait sans la
      décoder. X refusait le paramètre `amp;name`, la carte masquait l'image cassée :
      TOUTES les images X étaient invisibles, sans un message. Corrigé (`html.unescape`
      sur l'adresse ET sur le texte — « S&amp;P » s'affichait aussi), test qui échoue sur
      l'ancien code. Les lignes déjà stockées se réparent à la réingestion suivante
      (`INSERT OR REPLACE` sur le même lien).
- [x] **~~Telegram retiré de l'onglet~~ — DÉCISION UTILISATEUR (24/09).** « Je ne veux
      voir que les messages des comptes Twitter. » `QUANT_TG_CANAUX` retiré de `.env`
      sur le VPS, publications `https://t.me/…` supprimées de la base. Le code Telegram
      reste (source auto-enregistrée) : il se tait tant qu'aucun canal n'est configuré.
      walshwealth1122, sans compte X, disparaît donc de l'onglet.
- [ ] **P2 — Les posts « Subscribers Only » d'eliz883 (24/09).** Le compte connecté est
      abonné à eliz883 : RSSHub, avec son cookie, DEVRAIT les recevoir. Non vérifié.
      Rappel : si X suspend ce compte, l'abonnement payant part avec.
- [x] **~~P2 — L'ingestion est MANUELLE~~ — FERMÉ (24/09, ADR-0197).** Les trois sources
      réseau rejoignent `scripts/cron_daily.sh`, chacune sous garde de configuration,
      chacune avec un échec NOMMÉ (jamais `|| true`). Le retard ne se rattrape pas : la
      fenêtre publique de Telegram et des miroirs RSS ne rend qu'une vingtaine de
      messages. Déployé ; la chaîne quotidienne tourne sur le VPS (mesuré le 24/09).
- [x] **~~P2 — `walshwealth1122` n'a pas de correspondance de compte~~ — FERMÉ (24/09).**
      Ce n'est pas une lacune : l'utilisateur a confirmé que ce canal **n'a pas de
      compte X**. Il apparaît sous son nom de canal parce que c'est son seul nom. Rien
      à mapper.
- [x] **~~P2 — `packages/intelligence` câblée nulle part~~ — FERMÉ (24/09, revue de #402).**
      Elle l'est désormais par `packages/social/qualification.py` : chaque publication de
      l'onglet X passe par `pipeline.qualifier()`, comme l'impose AGENTS.md §9. Les deux
      taxonomies coexistent — intention DÉCLARÉE d'un côté, nature de l'énoncé de l'autre.
- [ ] **P2 — 32 des 66 comptes de la watchlist portent une réserve non levée (24/09).**
      `Candidat.a_resoudre` documente ce qui empêche de s'en servir ; tant qu'elle n'est
      pas levée, le compte est traité en `E_FAIBLE`. Les QUATRE comptes suivis dans
      l'onglet X en font partie (« expertise et authenticité à établir ») : leurs propos
      sont donc crédités au minimum. Lever une réserve demande une vérification RÉELLE,
      pas une décision d'écriture.
- [x] **~~P1 — L'audit de rotation rendait une moyenne qui ne décrivait pas le compte~~ —
      FERMÉ (23/09, ADR-0192).** 542 positions à +1,59 % de moyenne face à +818,67 $
      réalisés : `sum(pnls)/len(pnls)` pesait une ligne de 40 $ comme une de 12 000 $, et
      le notionnel s'obtenait en additionnant des QUANTITÉS. Pondération par
      `qty × entry_price`, `None` (jamais 0.0) si le poids est inconnu, ligne d'alerte
      au-delà de 3 points d'écart entre les deux moyennes.
- [ ] **P2 — Le cron social n'a pas encore tourné sur le VPS (24/09).** Le code est
      mergé et déployé (`2f18e7d`) ; rien à recharger, la crontab pointe le chemin du
      script. **Vérifier dans `/tmp/quant_daily.log` que les trois lignes d'ingestion
      apparaissent** : c'est le seul moyen de distinguer « ça tourne » de « ça se saute
      en silence ». **Question PRÉALABLE encore ouverte : la chaîne quotidienne
      tourne-t-elle sur ce VPS ?** (`ls -l /tmp/quant_daily.log` · `crontab -l | grep -c
      cron_daily`). Le précédent du 17/09 — `cron_daily.sh` n'avait JAMAIS tourné ici —
      interdit de le supposer.
- [x] **~~P2 — `QUANT_TG_CANAUX` n'était PAS dans `.env`~~ — FERMÉ (24/09).** Mesuré sur
      le VPS : la variable n'existait que dans un shell où elle avait été exportée à la
      main, parti avec la session. L'ingestion des 37 publications avait donc marché
      **une fois, par accident de contexte**. Le correctif du jour (`load_env()` +
      `configuree`) n'aurait rien changé seul : la source se serait déclarée non
      configurée, en silence — exactement le comportement voulu, et exactement ce qui
      rendait le diagnostic nécessaire. Ligne ajoutée à `.env`, vérifiée : `Lues : 34`,
      `Stock : 37`.
- [ ] **P2 — L'aperçu public Telegram a DÉJÀ perdu 3 messages (24/09).** Mesuré :
      `t.me/s/<canal>` ne rend plus que **34** messages quand la base en contient **37**.
      Les 3 manquants ne sont là que parce qu'ils ont été ingérés plus tôt. Ce n'est pas
      un défaut à corriger — c'est la confirmation CHIFFRÉE de ce qui justifie
      l'ingestion quotidienne (ADR-0197), et le rappel qu'un rattrapage n'existe pas.
- [ ] **P1 — 6 % du capital engagé annule les DEUX TIERS du gain (24/09).** Les 35
      fermetures RECONSTRUITES (date et prix retrouvés après coup par le script de
      réparation) pèsent **−0,80 % sur 59 221 $ = −474 $**, face aux **+712 $** des
      décisions du système (+0,08 % sur 889 640 $). Taux de gain **31 %** contre 50 %
      côté système. **L'audit ne peut PAS trancher** : soit ces pertes sont RÉELLES et la
      mesure du système les exclut (le +0,08 % flatte alors la stratégie), soit les prix
      retrouvés après coup sont FAUX (59 221 $ de prix inventés au journal). Ne pas
      choisir par raisonnement — MESURER : confronter ces 35 lots aux relevés du courtier.
- [x] **~~P1 — Le chiffre pondéré lui-même n'est pas encore MESURÉ~~ — MESURÉ (24/09).**
      Passage de référence, après correctif d'unités (`main` = `2f18e7d`, 587 positions
      sur 94,2 jours). Décisions du système : **+1,54 % simple contre +0,08 % pondéré**
      sur **889 640 $**, rapport **19,2×**, t = +4,65, PF 2,15, détention médiane 1,0 jour,
      41,0 clôtures/semaine. L'explication par la poussière de rebalancement TIENT — ce
      n'est plus une hypothèse. (Un premier passage le même jour, avant correctif et sur
      deux jours de moins, donnait +1,59 % / +0,09 % sur 867 604 $, soit 781 $ contre
      +818,67 $ réalisés : la réconciliation tenait déjà.)
- [ ] **P2 — Les frais ne sont MESURÉS sur presque rien (24/09).** 10,40 $ cumulés, mais
      **64 fermetures renseignées sur 597**, et toutes ESTIMÉES depuis un barème, jamais
      observées. Aucune conclusion de coût ne tient là-dessus — et un audit de rotation
      sans coût réel ne peut pas arbitrer « rebalancer plus » contre « rebalancer moins ».
- [ ] **P2 — La capture est calculée sur des effectifs qui ne portent rien (24/09).**
      −5 % côté système sur **5 positions**, −76 % sur le bloc reconstruit sur **10**. Le
      rapport affiche l'effectif — bien — mais le chiffre est cité ailleurs sans lui. À
      trancher : relever le seuil de détention (≥ 3 jours écarte presque tout à 1,0 jour
      de médiane), ou dire UNCALIBRATED tant que l'effectif est sous un seuil MESURÉ.
- [x] **~~P2 — Crypto : « avoir le top 20 » sur la carte des recherches~~ — FERMÉ (23/09,
      ADR-0193).** Le top 20 était IMPOSSIBLE : `/search/trending` rend 15 coins (mesuré
      23/09 : coins 15, nfts 7, categories 6), et rien ne tronquait. Le même appel rendait
      deux listes JETÉES à chaque build. Livré : variation 24 h par ligne (trois sources,
      `None` si inconnue), carte « Les thèmes que le public cherche », carte DISTINCTE
      « Ce qui s'échange le plus » (top 20 par volume, endpoint séparé). Attention ≠
      capital engagé : c'est leur divergence qui informe.
- [x] **~~P0 — Les ventes ne fermaient plus aucun lot depuis le 18/09~~ — FERMÉ (22/09,
      #394, ADR-0188).** `live_roundtrip.open_lots` lisait `all(legacy=False)` : les lots
      rejoués du courtier (`R-`, sans features donc `legacy=1`) étaient invisibles à
      l'appariement. Cinq ventes le 22/09, UN aller-retour. Le périmètre se lit désormais
      sur l'ORIGINE (`P-`/`C-`/`R-`), le drapeau `legacy` survit à la fermeture, et les
      ventes sans lot sont NOMMÉES.
- [x] **~~P0 — 22 695,70 $ de prix de revient absent du journal en une séance~~ — FERMÉ
      (22/09, #395, ADR-0189).** `_journal_opens` lisait le courtier dans la seconde
      suivant l'envoi : 4 achats sur 6 perdus, 2 tronqués. Attente BORNÉE que les ordres
      deviennent lisibles, hors du chemin d'ordre. `QUANT_ATTENTE_FILLS_S` la règle,
      `0` la désarme.
- [x] **~~P1 — Fermer la fuite d'ouvertures : persister les features de DÉCISION~~ —
      FERMÉ (22/09, #397, ADR-0190).** `decisions_store` dépose ce que le robot savait en
      envoyant ; `completer_ouvertures` le rattache au fill et écrit `legacy = pas de
      features`. Fenêtre de 3 jours, jamais une décision postérieure au fill. Décision
      absente → lot aveugle comme avant, et le rapport le dit avec son motif.
      **Reste vrai** : les lots déjà rattrapés restent `legacy=1` (décisions antérieures
      au magasin) — c'est l'entrée ci-dessous qui les concerne.
- [ ] **P1 — L'échantillon de calibration ML est reparti de zéro (22/09).** `make
      diag-journal` affiche `dont legacy=0 (calib. ML) : 4 lots`. La reconstruction du
      18/09 a remplacé les `P-` et leurs `features_snapshot` par des `R-` qui n'en ont
      pas. **Les features ne sont pas perdues** : elles sont dans l'archive
      `data/journal.avant-*.db` du 18/09 sur le VPS. Deux options à trancher — les
      réinjecter sur les lots `R-` correspondants (appariement par fill), ou repartir de
      zéro en acceptant ~3 mois de reconstitution. Ne rien entraîner d'ici là.
- [x] **~~P1 — « LIVE · il y a 15min » : comment avoir des données à jour ?~~ — RÉPONDU
      ET FERMÉ (22/09, #398, ADR-0191).** Ce n'était pas un retard de la donnée mais la
      période de reconstruction du snapshot, lequel mélange un screening sur barres
      QUOTIDIENNES (fenêtre arrêtée à minuit) et un portefeuille qui bouge à chaque
      seconde. Raccourcir le TTL aurait payé un recalcul complet du premier pour
      rafraîchir le second. `/api/portefeuille` lit le courtier directement (deux appels,
      aucun snapshot, cache partagé 20 s) ; `PortefeuilleLive` l'affiche à 30 s sur la
      page Positions. **Ne pas** « optimiser » en y rebranchant `_snap()` : un test de
      source l'interdit, et ce serait annuler tout le bénéfice.
- [ ] **P2 — Le badge `LiveBadge` décrit toujours le snapshot, et c'est exact (22/09).**
      Il reste donc à 15 min et passe en DIFFÉRÉ au-delà — comportement voulu. À revoir
      seulement si la coexistence des deux voyants (bandeau global « LIVE » du snapshot,
      bloc « COURTIER » de la page Positions) prête à confusion à l'usage.
- [ ] **P2 — Quatre écarts de quantité que la réconciliation ne sait pas fermer (22/09).**
      Après réparation complète (couverture 125/125, excédent 0) il reste :
      `T` journal 77,83 vs courtier 126,92 · `QQQ` 31,25 vs 68,26 · `TEN` 80,12 vs 100,15
      (le courtier détient plus que le journal) et `UNI` 0,63 vs 0 (l'inverse, lot du
      18/09). `reconcilier-journal` rend 0 écriture : tout l'appariable l'est. Demande une
      mesure dédiée, symbole par symbole.
- [ ] **P2 — Trancher le saut d'equity du 17/09 (+4 191,13 $) (22/09).** `diag-journal` le
      signale comme candidat VERSEMENT/RETRAIT alors que la réconciliation suppose
      flux = 0. Un versement de ce montant creuserait l'écart au lieu de le combler, donc
      c'est probablement une vraie séance — à confirmer sur le relevé Alpaca.
- [ ] **P2 — Relire l'écart comptable marché FERMÉ (22/09).** Il valait −125,29 $ puis
      −453,50 $ à deux lectures consécutives : `build_snapshot` réécrit le point d'equity
      du jour entre les deux, et le marché était ouvert. Le chiffre n'est stable qu'après
      la clôture.
- [x] **~~P0 — `make up` déployait une branche éphémère figée~~ — FERMÉ (21/09).**
      La valeur par défaut pointait encore vers `claude/screening-trading-platform-me9p11`
      (build 58ab486) : « à jour » signifiait seulement à jour de cette branche ancienne.
      Le déploiement suit désormais `origin/main`; `BRANCHE=x` reste une dérogation explicite.
      Migration ancienne→nouvelle réparée : cible de compatibilité `sync-garde-commits`
      conservée et seconde moitié de `up` relue après le remplacement du Makefile.
- [x] **~~P0 — Le journal masquait 585 lots importés~~ — FERMÉ (21/09).** La route
      `/api/journal` filtrait `legacy=False`, bon périmètre pour calibrer le ML mais faux
      pour demander « tout mon historique ». Elle sert désormais tous les lots, marque
      leur origine et ne déclenche plus le snapshot ou le réseau courtier.
- [x] **~~P1 — Trois restitutions visuelles disparues~~ — FERMÉ (21/09).** L'introduction
      rejoue à chaque visite explicite de `/`; le CAC 40 réel revient dans les courbes du
      dashboard et de performance ; Positions publie le P&L réalisé de tous les lots clos.
- [ ] **P1 — LIRE les compteurs de garde-fous, puis trancher l'armement du disjoncteur
      (21/09, ADR-0186).** `make garde-fous` existe et répond aujourd'hui `UNCALIBRATED` :
      le fichier `.cache/garde_fous.json` est vide tant que le robot n'est pas repassé.
      Commande, après une vingtaine de passages : `make sync && make garde-fous`.
      Ce qu'il faudra y lire, dans cet ordre :
      · `disjoncteur_journalier` → `aurait_declenche` : LA mesure qui manquait pour
        décider de `QUANT_DISJONCTEUR=1` (cf. P1 dette de câblage, ADR-0118). Zéro jour
        sur vingt passages ne veut PAS dire « inutile » — ça veut dire « pas encore
        éprouvé » ;
      · `portail_de_risque` → taux et effet en dollars, par RÈGLE. Un taux nul sur
        plusieurs semaines pose la question d'un plafond hors d'atteinte ;
      · tout `ERROR` → un garde-fou est tombé et le run a continué sans lui ;
      · tout `JAMAIS OBSERVÉ` → il est désarmé, ou le run ne va jamais jusque-là.
      **Ne rien armer sur un rapport vide** : c'est exactement ce que le rapport refuse
      de laisser croire.
- [x] **~~P1 — Le report hors séance revient-il CHAQUE jour ?~~ — MESURÉ, NON (21/09).**
      Premier passage réel observé : `garde_de_seance` = **16 observations, 0
      déclenchement, 0 %**. Le cron tombe DANS la séance. La paire de mesures fait la
      preuve : le même compteur affichait **19 déclenchements / 52 470 $** sur un aperçu
      lancé à 09:17 ET le matin. Le compteur discrimine, l'horaire est bon. Rien à
      changer au planning. *Texte d'origine ci-dessous.*
- [ ] **~~P1 (clos ci-dessus) — Le report hors séance revient-il CHAQUE jour ? (21/09, ADR-0186).~~** Premier
      aperçu mesuré : **19 ordres reportés, 52 596 $**, parce que le run tombe à 08:54 ET
      alors que la séance ouvre à 09:30. Le cron tourne à 19:08 UTC = 15:08 ET, donc DANS
      la séance — mais personne n'a jamais vérifié que c'est bien le cas tous les jours.
      Le compteur `garde_de_seance` répond désormais : taux de report par classe d'actif
      et dollars non envoyés. Si le taux est élevé en mode `live`, ce n'est pas le marché,
      c'est le PLANNING (`QUANT_LIVE_HOUR=21 make live-cron-install`).
- [x] **~~P1 — LIRE les deux `journalctl` de la panne du 21/09~~ — SANS OBJET (21/09).**
      La panne n'était pas côté VPS : le tunnel SSH visait `localhost`, résolu en `::1`
      sur la machine, que les services n'écoutent pas. Le site servait pendant tout
      l'épisode. *(Et le `journalctl` rendait « -- No entries -- » faute de `sudo` : la
      sortie portait l'explication deux lignes plus haut.)*
- [ ] **P2 — Les services n'écoutent qu'en IPv4 (21/09).** `uvicorn --host 127.0.0.1` et
      le front idem. C'est un choix sûr, pas un défaut — mais il rend tout tunnel visant
      `localhost` silencieusement inopérant sur une machine à double pile. Décider : soit
      on documente définitivement `127.0.0.1` (fait), soit on écoute aussi `[::1]`.
      Ne rien changer sans raison : élargir une écoute est une décision de sécurité.
- [ ] **~~P1 (clos ci-dessus) — LIRE les deux `journalctl` de la panne du 21/09.~~** Le site
      n'affichait plus rien pendant ~35 min ; les services tournaient, pas d'OOM, 1,4 Gi
      libre. **La cause n'est pas établie** et la trace existe encore :
      `journalctl -u quant-api --since "13:15" --until "13:56" --no-pager | tail -50`
      (idem `quant-web`). Chercher `snapshot rebuilt` et sa durée. Hypothèse NON
      VÉRIFIÉE : contention — `_warm()` relance une construction complète à chaque
      redémarrage de l'API (pic 1,4 Go), et deux `make live` en ont ajouté deux autres
      dans des processus séparés, sur 3,7 Go **sans swap**. Ne pas conclure sans le log.
- [ ] **P2 — `_warm()` reconstruit à CHAQUE redémarrage, même cache valide (21/09).**
      Le snapshot disque est servi instantanément, puis un rafraîchissement complet part
      en fond — systématiquement. Sur cette machine c'est 1 à 3 min à 1,4 Go après chaque
      `make up`. À confronter au TTL de 15 min : si le cache disque a moins de 15 min,
      cette reconstruction ne sert à rien. **Mesurer l'âge réel au démarrage avant de
      toucher quoi que ce soit** — `/health` publie désormais cet âge.
- [ ] **P1 — Le CAC 40 est-il RÉEL en base ? (21/09).** Absent de l'intro et du
      dashboard. Le code est entièrement branché des deux côtés — `FENETRES` (5 fenêtres),
      `_comparaison` (multi-références), `snapshot.py:2828` et `:2859`,
      `IntroCourbes.referencesUtiles`. Tout dépend de `_cac_real`
      (`_index_series(["^FCHI", "CAC", "EWQ"], …)`) : une série retombée sur son repli
      synthétique n'est affichée NULLE PART, par décision explicite. **Mesurer d'abord** :
      `curl -s localhost:8000/api/intro` → lire `references_noms`. Si le CAC n'y est pas,
      le remède est l'INGESTION de `^FCHI`, pas le code d'affichage.
- [ ] **P2 — `/api/intro` attend le snapshot COMPLET (21/09).** La route rend
      `_snap().get("intro")` : après un `make up`, elle ne répond qu'au bout d'une à trois
      minutes, pendant que le rideau n'attend que 2,5 s. Le motif le DIT désormais, ce qui
      suffit à ne plus se tromper de diagnostic. Deux vraies pistes si ça devient gênant :
      servir la section `intro` du DERNIER snapshot connu pendant la reconstruction, ou
      allonger `ATTENTE_DONNEES_MS`. La première est la bonne — la seconde ne fait que
      déplacer le seuil. **Ne pas la traiter sans mesurer d'abord** combien de temps
      `/api/intro` met réellement à répondre après un `make up`.
- [ ] **P2 — `.cache/stages/*.pkl` en mode 664 sur le VPS (21/09).** `safe_pickle`
      avertit à chaque run : « inscriptible par d'autres utilisateurs ». Sur une machine
      mono-utilisateur c'est bénin ; l'avertissement, lui, est correct et bruyant. Décider :
      `chmod 600` à l'écriture, ou umask du service.
- [ ] **P2 — Le témoin des garde-fous n'est pas exposé sur le site (21/09).** Rapport
      CLI seulement, à dessein : publier des compteurs de garde-fous demande de décider
      ce qui est publiable sur un dépôt PUBLIC. Le fichier est local (`.cache/`,
      gitignoré) et ne contient ni symbole, ni position, ni clé — un test le vérifie.
- [x] **~~P0/P1 — Régime ATR : bascule de modèle~~ — FERMÉE PAR LA MESURE (14/09,
      ADR-0145).** Trois seuils, 820 symboles, t groupé significatif partout — et pourtant
      non. Aux TROIS seuils la journée typique en haute volatilité est moins bonne qu'en
      marché calme : médiane +0,000 % contre +0,437 %, taux de gain 46,9 % contre 56,2 %
      au seuil 2,50. La moyenne est la seule statistique qui favorise le régime. La règle
      sélectionne des billets de loterie, d'autant mieux qu'on la resserre.
      Point décisif : le rendement mesuré est SANS STOP, alors que la production porte
      `atr_stop=4.0` — capter un p90 de +21 % suppose de survivre à un p10 de −18 %.
      Aucun `model_high_volatility.pkl`, aucune bascule, gate placebo sans objet.
      `make regime-atr-lab` reste : c'est lui qui a tranché.
- [x] **~~P0 — Trois planificateurs sur le même compte paper~~ — FERMÉE (15/09,
      ADR-0155/0156).** Actions + launchd du Mac + crontab du VPS, chacun défaisant le
      précédent. −60,79 $ le 15/09. Garde journalière branchée (le COURTIER décide),
      planification `paper.yml` retirée, Mac désinstallé. Test : `schedule:` interdit.
- [x] **~~P0 — Trois planificateurs~~ — DÉFINITIVEMENT CLOS (17/09).** Deux jours
      propres d'affilée : 16/09 (1 passage 19:08:35, 0 A/R) et 17/09 (1 passage 19:08:28,
      0 A/R). La garde journalière tient à vingt secondes près.
- [x] **~~P1 — Chiffrer le coût CUMULÉ du churn~~ — MESURÉ (16/09, ADR-0159).**
      `make churn` : 15 jours sur 32 à plus d'un passage, **−620,13 $** sur **594 362 $**
      brassés. La date de pollution est le **27/08** (premier aller-retour), pas le 07/07
      (premier doublon) — deux passages qui aboutissent à la même cible ne coûtent rien.
- [x] **~~P1 — Rien ne surveille la DÉRIVE d'un planificateur~~ — FERMÉE (16/09).**
      `make brief` porte une section « Passages du robot (7 j) » avec les commandes à
      lancer. Un doublon se voit le lendemain matin.
- [ ] **P0 — Lancer `make news` chaque jour, sans exception (16/09, ADR-0162).** PREMIER
      PASSAGE RÉUSSI sur le VPS le 16/09 : **2 375 titres · 199 symboles · 71 jours**
      (2026-05-19 → 2026-09-16), 1 symbole muet. Reste à VÉRIFIER que le passage
      automatique de `cron_daily.sh` prend le relais demain — un flux RSS ne se rejoue pas.
- [x] **~~P1 — Le motif déviation→reclaim→consolidation~~ — FERMÉ PAR LA MESURE
      (18/09, ADR-0182/0183/0184).** Mesuré sur DEUX marchés et deux timeframes, avec
      le gate du module : **0 scoreur sur 5 passe les quatre portes**, des deux côtés.
      · **Actions 1D** — 200 titres, 499 758 barres, horizon 10 : IC de +0,0071 à
      −0,0131, tous sous le seuil 0,03, et négatifs dès `reclaim`.
      · **Crypto 4h** — 98 paires, 1 187 822 barres (Binance), horizon 10 barres =
      40 h : mêmes ordres de grandeur, IC −0,0120 et −0,0145 sur `reclaim` et
      `consolidation`, et `consolidation + contraction` en Sharpe **NÉGATIF**.
      **La jambe intraday que la spec réclamait a donc été mesurée pour de bon** — et
      elle ne sauve rien. Deux marchés indépendants, même réponse.
      **Ce que la mesure dit de plus, une fois dé-diluée** : à sélectivité égale, les
      barres retenues valent le marché en actions (Sharpe ≈ 0,28-0,32 contre 0,339) et
      MOINS que le marché en crypto, en se dégradant à chaque étage de confirmation
      (0,101 → 0,087 → 0,080 → −0,024). Attendre la confirmation coûte, ça ne rapporte
      pas. `signal_lab` est SANS OBJET : on ne mesure pas le recouvrement d'un signal
      qui n'existe pas.
      **Ce qui reste** : la machine à états et les deux bancs restent au dépôt — ils ont
      servi à trancher, et ils reserviront. Aucun câblage en production.
- [ ] **P2 — Intraday 1h/4h pour les ACTIONS / INDICES / ETF : pas de source gratuite
      honnête (18/09).** La crypto est livrée (`make ingest-crypto-intraday` → Binance,
      sans clé, historique complet de la paire, `data/crypto_intraday.db`). Côté actions,
      les deux sources gratuites déjà branchées dans le dépôt échouent pour des raisons
      DIFFÉRENTES, et aucune des deux n'est réparable par du code :
      **yfinance** plafonne le 1h à ~730 jours d'historique (limite du fournisseur) — de
      quoi faire un banc, pas un entraînement ML sur plusieurs cycles ; et il ne sert PAS
      le 4h, ce qui n'était pas visible avant : `_TF_MAP` renvoyait `"4h" → "1h"` et
      `df_to_bars` étiquetait avec le timeframe DEMANDÉ, donc des barres horaires
      entraient en base avec `timeframe="4h"`. Corrigé : le provider REFUSE désormais
      `4h` explicitement, l'agrégation 1h→4h est à la charge de l'appelant.
      **Alpaca palier gratuit** sert le flux IEX, dont les VOLUMES ne représentent pas le
      marché — or nos détecteurs (`sfp`, `deviation_reclaim`) filtrent sur le volume :
      la donnée est gratuite mais la mesure qu'on en tirerait serait fausse, ce qui est
      pire que pas de donnée.
      **Ce qui reste, donc payant** : Alpaca SIP (~99 $/mois), Polygon, Databento.
      **À NE PAS refaire** : `bars_repo` est DÉJÀ multi-timeframe (clé (symbol, timeframe,
      ts)), le schéma n'est pas le blocage — seule la SOURCE l'est.
      **Décision différée, et la condition est mesurable** : n'ouvrir ce poste que si le
      banc crypto (`make deviation-lab-crypto`) montre que l'intraday apporte quelque
      chose LÀ OÙ les données sont complètes. Si l'apport n'existe pas sur Binance, il
      n'existera pas sur deux ans d'IEX, et on aura économisé l'abonnement.
- [x] **~~P0 — Le journal tient 27 symboles OUVERTS, le courtier en détient 17~~ —
      FERMÉE PAR LA RECONSTRUCTION (18/09, cf. journal 38ᵉ session).** Le registre n'a
      pas été réparé, il a été REJOUÉ depuis les 774 fills réels du courtier : 533
      aller-retours fermés, 52 lots ouverts, ZÉRO vente orpheline, et un contrôle
      fail-closed qui refuse d'écrire tant que les lots ouverts ne correspondent pas,
      symbole par symbole, à l'inventaire réel. Les 13 symboles fantômes et les 3
      positions manquantes n'existent plus : ils venaient de la période à plusieurs
      planificateurs, et le rejeu ne connaît que ce que le courtier a exécuté.
      **Ce qui reste ouvert, et qui est d'une autre nature** : le réalisé est BRUT de
      frais (les `CFEE` crypto sont prélevées en JETONS, hors du flux d'ordres), d'où
      un résidu de −456,29 $ dans l'identité du capital. Suivi par `make frais-courtier`.
      *Texte d'origine conservé ci-dessous pour la trace.*
- [ ] **~~P0 (clos ci-dessus) — Le journal tient 27 symboles OUVERTS, le courtier en détient 17 (17/09).~~**
      Mesuré en confrontant l'onglet « Historique des positions » (61 lots ouverts) aux
      positions Alpaca réelles : **13 symboles** ouverts au journal dont le courtier ne
      détient RIEN (HPQ 4 lots, MPC 3, TSM 3, NTR 2, CF, LNC, MCK, NEM, PATH, STT, TGT,
      TYL, WFC), et **3 positions réelles** absentes du journal (PSX, QRVO, XOM, toutes
      achetées le 16/09). Le mécanisme est lisible sur THC : quatre achats (09, 10, 14,
      15/09) et trois ventes (10/09 19:54, 11/09 19:59, 14/09 21:40) chez le courtier,
      qui n'en détient donc qu'un lot — et le journal a gardé les QUATRE achats ouverts
      sans apparier une seule vente. Les ventes manquantes tombent toutes sur les
      passages SECONDAIRES : c'est le résidu de la période à plusieurs planificateurs.
      Confirmation : **aucun lot orphelin daté du 16 ou du 17/09**, les deux journées à
      un seul passage. La dérive a cessé, le passif reste.
      **RÉPARÉ EN PARTIE (17/09 21:13, `make reparer-journal`).** 85 ouvertures
      reconstituées, 182 écritures de correction postées au prix et à la date des
      fills réels, 9 doublons de fermeture retirés (+376,17 $ de « réalisé » qui
      était compté deux fois). Orphelins 53 → 27, achats non couverts 48 → 8, lots
      ouverts 61 → 22, round-trips fermés 62 → 112.
      **Ce que le panneau affiche a changé de signe** : réalisé +139,75 $ sur 62
      trades (espérance +2,25 $) devient **−23,15 $ sur 112 trades (−0,21 $)**. Le
      premier chiffre était un sous-ensemble favorable — les pertes n'étaient pas
      appariées. Le second est le chiffre honnête.
      RESTE À FAIRE :
      - 27 lots ouverts sur des titres que le courtier ne détient plus (AVAX 378,
        NWL 1151, SOL 68, MAS 86, LTC +99, T +89, OSCR +87) — aucune vente du
        courtier n'en rend compte, les fermer inventerait un prix ;
      - 8 symboles dont les ACHATS ne sont pas couverts (LINK, OSCR, T, VZ, QQQ,
        OKTA, RRC, MPC). Les deux écarts NÉGATIFS (VZ −36,48 · QQQ −7,93) sont
        couverts par ces achats manquants (66,89 · 20,14) : c'est un trou, pas une
        sur-fermeture. La chaîne n'est pas un point fixe après un passage —
        `completer-ouvertures` tourne AVANT la réconciliation, donc un second
        passage complet peut encore en fermer ;
      - NWL (1,74×) et MAS (1,91×) portent deux fois leur achat, tout en `legacy=1`,
        préfixe `LEG` unique : le chemin d'IMPORT crée deux identités. Non traité.
      - **TRANCHÉ (17/09)** : le panneau montre les trades du ROBOT réellement ouverts
        PUIS clôturés. Le périmètre se lit sur l'ORIGINE du lot (`P-` décision, `C-`
        fill reconstitué), plus sur `legacy` — qui répond à la question de la
        calibration ML, pas à celle du panneau. `packages/execution/perimetre_journal`.
- [x] **~~P1 — La réparation recréait un fill déjà journalisé~~ — FERMÉE (17/09).**
      Second passage de `make reparer-journal` : `diag-journal` a vu « QQQ ×2,
      3,586126 @ 716,86 le 17/09 ». La couverture était jugée sur la quantité AGRÉGÉE
      d'un symbole, puis le reste calculé en consommant les fills les plus anciens —
      ce qui suppose que ce que le journal connaît forme un PRÉFIXE CHRONOLOGIQUE des
      achats. Faux : l'achat du 17/09 était journalisé, 20 unités plus anciennes ne
      l'étaient pas. `deja_journalises` apparie d'abord les fills reconnus exactement.
- [ ] **P2 — `sync-garde` protège le travail NON COMMITÉ, pas un commit local.**
      `git reset --hard origin/<branche>` détruit aussi les commits locaux non poussés,
      et le garde-fou du 17/09 ne couvre que l'arbre de travail. Sur une machine restée
      en arrière qui vient de commiter, `make sync` perd le commit en silence — même
      classe de défaut, autre porte. Piste : avertir (ou poser une branche de secours)
      quand `git log origin/<branche>..HEAD` n'est pas vide.
- [x] **~~P1 — `make sync` détruisait en silence un fichier non commité~~ — FERMÉE
      (17/09).** `constraints.txt` régénéré le 16/09 sur le VPS (159 paquets au lieu de
      81) a disparu au `make sync` suivant : la recette fait `git reset --hard`. Le seul
      signal était `make verrou` qui « régressait » à 81, deux commandes plus loin.
      `sync-garde` met désormais de côté (`git stash`) AVANT de réécrire l'arbre, nomme
      ce qu'elle écarte, et interrompt plutôt que de détruire si le stash échoue.
- [x] **~~P1 — Le registre se remplira au prochain entraînement~~ — FAIT (17/09).**
      Première entrée : `Gradient Boosting (sklearn)-20260916-223954-4a0ed2d`,
      **AUC 0,532**, statut `rejected` (non promu). Le câblage fonctionne de bout en bout.
- [x] **~~P1 — AUCUNE version en PRODUCTION au registre~~ — TRANCHÉE (17/09, ADR-0177).**
      Ce n'est pas un trou : le candidat a été refusé pour absence d'edge OOS, et le motif
      dormait dans l'historique sans être affiché. Il s'affiche désormais, et « jamais
      soumis » se distingue de « refusé ». L'artefact en service n'est PAS promu : sans
      manifeste, l'inscrire fabriquerait une provenance. La production restera vide
      jusqu'à ce qu'un modèle la mérite — c'est le gate qui fonctionne, pas une lacune.
- [x] **~~P1 — Éprouver la chaîne NLP sur le Mac~~ — ABANDONNÉE (16/09, ADR-0170).**
      Quatre tentatives, zéro classification. La chaîne locale est RETIRÉE du dépôt.
- [ ] **P1 — Mesurer l'alpha du LEXIQUE sur le corpus (16/09, ADR-0170).** `make
      alpha-lexique` LIVRÉ et LANCÉ (16/09) : 199/199 symboles ont leurs prix, mais la
      première collecte datant du 16/09, `utilisable_le` vaut le 16/09 pour les 2 375
      titres — zéro jour d'observation. **Relancer vers le 23/09** (ADR-0174).
- [ ] **P1 — L'AUC du modèle de production est 0,504 (16/09, ADR-0161).** Indiscernable du
      hasard, Brier à 0,0004 du seuil de rejet, DSR jamais calculé. Aucune accélération de
      calcul ne corrige une absence de signal — c'est le vrai sujet ML du projet.
- [ ] **P1 — Régénérer `constraints.txt` SUR LE VPS (17/09).** J'avais conclu le 16/09
      que « le VPS n'est pas la machine qui entraîne » parce que `xgboost`/`lightgbm`/
      `torch` y sont absents. **C'EST FAUX** : le registre du 17/09 montre un run
      `Gradient Boosting (sklearn)` du 16/09 à 22:39:54, `cpu:x86_64`, sur le VPS. Les
      trois bibliothèques absentes ne sont simplement pas utilisées. Celle qui compte est
      `scikit-learn 1.9.0`, **LIBRE** — donc une mise à jour silencieuse peut changer le
      modèle sans que rien ne le dise. Passe en P1 :
      **DÉFAUT PLUS GRAVE TROUVÉ EN CHEMIN (ADR-0176)** : `constraints.txt` n'était
      appliqué QUE dans les trois workflows GitHub — `make install` n'en tenait aucun
      compte. Le verrou protégeait la CI, qui n'entraîne pas. Corrigé — ainsi que la
      cible elle-même, qui nommait `pip-compile` au lieu d'`uv` (ADR-0178). **Reste à
      lancer SUR LE VPS** : `make verrou-regen && make install`, puis `make verrou` doit
      passer au vert sur ses DEUX lignes.
- [ ] **P2 — Étape 6 (LambdaBackend) — CONDITIONNÉE (16/09, ADR-0161/0164).** L'interface,
      le superviseur et la double protection existent et sont testés sur `BackendLocal`.
      N'écrire le backend distant que si une mesure d'alpha a démontré quelque chose à
      accélérer. La chaîne NLP locale, elle, est retirée (ADR-0170).
- [x] **~~P1 — La courbe d'equity RÉELLE est biaisée depuis le 27/08~~ — TRANCHÉE
      (16/09, ADR-0172).** ANNOTÉE, pas corrigée : retrancher le churn publierait une
      courbe qui n'a jamais existé. `make churn` dépose le rapport, le site le relit sans
      réseau, et « non mesuré » ne se confond pas avec « aucun churn ».
- [ ] **P2 — 3 300 anomalies MAJEURES sur `market.db`, 7 CRITIQUES sur `crypto.db`
      (16/09).** Le brief les affiche à chaque lancement et personne ne les a ouvertes.
      Un compteur qu'on ne regarde plus ne protège de rien : `make audit` puis trancher.
- [ ] **P2 — 91 symboles sur 929 ne rendent aucune donnée (15/09, ADR-0157).** Désormais
      comptés et nommés par `ingest_prices`. Trancher périmés / vivants : `make audit-univers`.
- [ ] **P2 — L'historique des futures a été réécrit chaque jour jusqu'au 15/09
      (ADR-0157).** Le correctif arrête la réécriture, il ne dit pas si les séries
      actuellement en base sont cohérentes. Un `make contracts` / `make audit` ciblé sur
      les `=F` le dirait.
- [ ] **P1 — 57 180 $ en liquidités après le rebalancement du 14/09 (ADR-0149).** Les
      ventes sont passées, aucun achat. Hypothèse NON VÉRIFIÉE : boucle d'achats après
      16:00 ET → `run_live.py:212` reporte toute action. À trancher sur le log :
      `tail -n 200 /tmp/quant_live.log | grep -vE '"level":' | tail -n 60`. Chercher
      `⏸ REPORTÉ`, `disjoncteur`, `sous le plancher`.
- [x] **~~P1 — 57 180 $ en liquidités après le rebalancement~~ — RÉSOLU (14/09,
      ADR-0150).** Ni disjoncteur ni séance : ordre de traitement. Ventes d'abord.
- [ ] **P2 — Le portail reste séquentiel, il ne planifie pas (14/09, ADR-0150).** Il ne
      sait toujours pas qu'un achat refusé aurait pu attendre trois lignes. Résoudre le lot
      comme un sac à dos sous contrainte serait une autre décision — à mesurer d'abord.
- [ ] **P2 — `MAX_POIDS_LIGNE_PANIER = 0,60` est une politique, pas une mesure (14/09,
      ADR-0151).** À confronter à un vrai calcul look-through sur la concentration interne
      de QQQ si le cœur devait monter au-delà.
- [ ] **P1 — Une unité systemd hors git subsiste sur le VPS (14/09, ADR-0148).**
      `quant-rebalance.service` est DÉSACTIVÉ mais présent sur disque, et son
      `Environment=` reste illisible (unité en 600). Décider : la supprimer, ou la
      versionner dans `install_services.sh` si elle porte une configuration utile.
      Tant qu'elle est là, la machine porte un état que le dépôt ne décrit pas.
- [ ] **P1 — Surveiller le PREMIER passage de la chaîne quotidienne (14/09).** Installée
      aujourd'hui, elle n'avait jamais tourné : ingestion, ML, audit, rapports et
      watchlist vont s'enchaîner d'un coup à 22h30. `tail -n 40 /tmp/quant_daily.log`
      le lendemain. Un premier run sur une base qui n'a pas été rafraîchie par cron
      depuis longtemps peut être long et révéler des ruptures.
- [ ] **P0 — Produire les rendements OOS ML avant toute promotion effective (11/09,
      ADR-0142).** Le cron appelle désormais `should_promote` et CONSERVE le champion si
      DSR/Brier/AUC sont incomplets ; il ne remplace donc plus un modèle sans comparaison.
      DSR reste explicitement `null`, car ce classifieur n'a pas de série de rendements OOS.
      Ne pas le déduire de l'AUC : définir un portefeuille, coûts et cadence OOS, puis
      persister ses rendements avant qu'un challenger puisse passer le gate.
- [ ] **P1 — le watchdog demande 100 trades, le journal en a 40 (11/09).** Fenêtre
      glissante win-rate + Sharpe : n = 40 après regroupement des tranches, rendement
      moyen +0,03 %, t = +0,04. Un déclencheur « −15 % vs baseline » sur une baseline
      nulle déclenche sur du bruit. `paper_watch.drift_report` existe et n'est appelé que
      par `make paper-watch` (manuel, hors cron). À câbler en SHADOW, avec un verdict
      capable de dire UNCALIBRATED tant que n < fenêtre.
- [ ] **P2 — boucle d'exécution continue : différée, et pour une raison mesurée (11/09).**
      La spec demande un bot async qui ne « rate aucun tick ». La production décide **une
      fois par jour**, une heure avant la clôture NYSE (`cron_live.sh` + `fenetre_execution.py`),
      et la détention médiane mesurée est de **1 jour**. À cette cadence un hot-swap se
      réduit à « lire le fichier au début du run ». La boucle continue n'a de sens que si
      la détention passe en intraday — question ouverte depuis P0-2.
- [x] **P1 — « Pouls du portefeuille » livré (09/09, ADR-0128).** Sentiment & news du
      portefeuille importé, **pondérés par ses poids**, dans *Analyser mon portefeuille*.
      L'onglet `/sentiment` du robot reste inchangé. Non-persistance garantie par deux
      tests (source + comportement), vérifiés par sabotage.

- [x] **~~P0 — filtre `legacy`~~ — ANNULÉE, elle n'a jamais existé (09/09, ADR-0122).**
      `/api/journal` publie déjà les deux périmètres via `perimetre_affiche`, et la page
      `/journal` affiche le bandeau « Périmètre affiché ≠ compte » avec les deux chiffres.
      J'avais lu la ligne du diagnostic CLI sans vérifier ce qu'elle avait déjà provoqué.

- [x] **~~P0 (annulée) — texte d'origine conservé~~ —** Mesuré le 09/09 sur le
      VPS : `legacy=0` (affiché) = 55 fermés, 58 % de réussite, **+2 660,29 $**. `legacy=1`
      (masqué) = 211 fermés, 51 %, **−2 414,96 $**. Total subi par le compte : 52 %,
      **+245,33 $**. Le panneau ne ment pas, il montre une PART — et l'effet sur qui le lit
      est le même. Deux issues : publier les deux chiffres côte à côte, ou justifier
      l'exclusion là où elle s'affiche. Ne pas laisser un chiffre flatteur sans son total.

- [x] **P0 — Journal du VPS RESTAURÉ (09/09).** `réalisé +245,33 $` au centime près.
      Cause corrigée (ADR-0115) et garde-fou posé AVANT écriture (ADR-0116). Rejouable
      par `make reparer-journal`, qui refuse d'écrire un prix que le marché n'a pas coté.

- [ ] **~~P0 — RESTAURER le journal du VPS~~ (09/09).** La chaîne de
      réparation appliquée ce matin a fabriqué des pertes : écart de réconciliation
      +168,76 $ → **+4 490,52 $**, réalisé +245 $ → **−3 929 $**, pour un compte qui n'a
      bougé que de +28 $. Cause corrigée dans le code (ADR-0115), mais la base porte encore
      les écritures fausses. Commande :
      `cp data/journal.avant-completion-20260909-091516.db data/journal.db`
      puis `make sync && make diag-journal` — l'écart doit revenir à ~+169 $. Rejouer la
      chaîne seulement APRÈS ce contrôle.

- [ ] **P1 — 1 906 lignes de DETTE DE CÂBLAGE (09/09, ADR-0118).** Dix modules déclarés
      SHADOW, aucun atteignable depuis la production. `make certification` les compte et
      bloque si l'un d'eux entre en prod sans changer de statut. À trancher, par ordre de
      valeur : ~~(1) protocole_oos~~ FAIT (ADR-0119) ; ~~(2) disjoncteur~~ FAIT, en
      OBSERVATION — reste à l'ARMER (`QUANT_DISJONCTEUR=1`) après quelques semaines
      d'observation des jours où il aurait coupé ; (3) `frictions` : `signal_inhibe` exige
      un GAIN ATTENDU par ordre que le rebalanceur ne produit pas — produire cette
      estimation d'abord, ne pas l'inventer ; (4) `market_structure`, dont le STATUT dit
      « aucun appelant en production » alors que `make labs` l'utilise.

- [x] **ÎLOT SWING — MESURÉ le 09/09, verdict NON (ADR-0126).** 2 169 trades sur données
      réelles : −0,059 R par trade, 26,8 % de réussite, −127,9 R au total, DSR 0,0001 pour
      un seuil de 0,95. NE PAS BRANCHER. Nuance : 1,7 point sous le seuil d'équilibre, et
      ma règle « stop prioritaire dans la même barre » porte sur ces cas — c'est une BORNE
      INFÉRIEURE. Ne pas supprimer : la question se rejugera sur données INTRADAY, qui
      lèveraient l'ambiguïté. Les coûts, non modélisés, ne peuvent qu'aggraver le résultat.

- [x] **~~P1 — îlot swing mesurable~~ —**
      Ce n'est PAS le swing déjà backtesté (`strategies/swing` + `fast_swing`) : c'est une
      stratégie ICT/Smart Money distincte (Hurst 1W, SFP, BOS, OTE, order blocks, CHoCH).
      Le banc simule ses propositions sur l'historique réel — entrée en LIMITE, stop
      prioritaire sur la cible dans une même barre, résultat en R — et passe le Sharpe par
      trade à la porte DSR. Reste à LANCER sur le VPS, puis décider sur les chiffres.

- [x] **~~P1 — îlot swing : décision sans chiffres~~ —**
      `moteur_swing` et `moteur_sortie` n'ont AUCUN importeur, et tirent `ddm`,
      `garde_swing`, `liquidite_ict`, `caracteristiques_swing`. Brancher ou supprimer est
      une décision de produit, pas de linter — elle appartient à l'utilisateur.

- [ ] **P2 — Barres non temporelles absentes.** Volume/tick/dollar/information-driven :
      zéro implémentation (seul vrai manque de l'audit des 4 axes). N'a d'intérêt qu'une
      fois `protocole_oos` branché — sinon on ajoute une méthode sans porte pour la juger.

- [ ] **P1 — Lots `LEG-` en double : DONNÉES historiques, PAS un bug vivant (09/09).**
      Formulation corrigée : `diag_journal_compte.py:663` établit qu'« aucun script du
      dépôt n'écrit d'identifiant `LEG-` — l'import qui les a produits n'est plus dans
      l'arbre ». Il n'y a donc aucun chemin d'écriture à réparer : c'est une contamination
      historique (NWL 1,74× la quantité achetée, MAS 1,91×). Remède au niveau DONNÉES,
      après lecture des traces : `python scripts/diag_journal_compte.py --symbole NWL`.

- [ ] **~~P0 — chemin d'écriture qui dédouble~~ — REQUALIFIÉ ci-dessus (09/09).** NWL porte 1,74× la
      quantité achetée, MAS 1,91×, sur 7 et 6 identifiants `LEG-…` distincts. Le
      diagnostic le nomme : « un seul préfixe portant 2× = le chemin d'ÉCRITURE crée deux
      identités ». C'est la cause AMONT de tout le reste, et aucune réparation aval ne
      peut converger tant qu'elle est ouverte. À traiter là : qui écrit les `LEG-…`, et
      pourquoi deux fois. Tant que ce n'est pas fermé, NE PAS lancer `make reparer-journal`
      (ADR-0117 : deux tentatives, deux dégradations).

- [x] **~~Réparation du journal à rejouer~~ — GELÉE (09/09, ADR-0117).** Le code est
      correct (ADR-0115/0116, garde-fou vérifié : plus aucun prix incohérent écrit), mais
      la chaîne annonce −222 $ et produit −1 448 $ de réalisé : elle RE-APPARIE le FIFO
      au lieu d'ajouter. Journal restauré, laissé tel quel. Sans effet sur l'exécution. La simulation
      donne : 18 ouvertures à reconstituer (83 804 $ de coût de revient), 23 fermetures
      appariées à un fill réel (+666,76 $), 8 doublons pour +915,37 $ de réalisé compté
      deux fois, 16 lots qu'aucune vente ne justifie et qui RESTENT ouverts. QQQ : 96,78
      unités au journal contre 60,50 au courtier. Réconciliation d'ensemble saine — écart
      +168,76 $ sur +990,08 $, soit `latent(début)`. Reste à lancer avec `--appliquer`.

- [ ] **P2 — `models/ml_*.pkl` en mode 664 sur le VPS.** `safe_pickle` le signale à chaque
      chargement : inscriptible par d'autres utilisateurs. Le garde-fou fonctionne ; la
      permission reste à resserrer (`chmod 600`). Signalé le 09/09.

- [x] **P0 « QQQ 50 % vs plafond 20 % » — FERMÉE, ce n'était pas un arbitrage (2026-09-09).**
      Le projet avait tranché le 06/07 : un tracker relève de `max_index` (60 %), pas de
      `max_name` (20 %). `index_names` étant optionnel, le site d'appel du portefeuille
      preset (`snapshot.py` l. 2641) ne le passait pas — et c'est celui que lit le
      post-mortem. Corrigé + invariant verrouillé par un test qui relit `snapshot.py`.
      Aucun poids ne bouge. ADR-0113.

- [x] **Libellé corrigé (09/09, ADR-0122) : « Actions diverses » sort sous le type
      `secteur inconnu`.** Reste la DONNÉE à peupler — mesurable sur le VPS seulement :
      `make list-db` dit combien d'actions ont un champ `sector` vide.

- [x] **~~P1 — « Actions diverses » n'est pas un secteur~~ —**
      `_sector_of` y range en dernier recours toute ACTION dont le champ secteur est vide ou
      hors GICS (crypto/forex/ETF/indices/commodités ont leur branche avant). Les 47,5 %
      signalés ne disent donc pas « la moitié du livre sur un secteur » mais « la moitié du
      livre non classée » : la concentration sectorielle est NON MESURABLE, pas franchie.
      À faire sur le VPS : lister ce que contient le seau (`make list-db` donne les secteurs
      de YAHOO.db), combler les secteurs manquants, PUIS relire la limite. Tant que le seau
      est gros, le plafond 40 % ne mesure rien — et le lever sans classer serait pire.

- [x] **Horodatage du vault sous contrôle — FERMÉ (2026-09-09).** Douze ADR (0100→0111),
      l'en-tête de séance et un enregistrement d'`hypotheses.jsonl` étaient datés du
      2026-09-10 alors qu'on était le 09. Corrigés, et `make vault-lint` sort désormais en
      erreur sur un en-tête d'ADR ou de séance postérieur au jour. Contrôle borné aux
      EN-TÊTES : une date future dans un corps d'ADR est un rendez-vous, pas une faute.
      ADR-0112.

- [ ] **P2 — `ruff check` est rouge AVANT toute modification.** Hors `packages`/`apps`,
      l'arriéré dépasse 2000 signalements (longueur de ligne pour l'essentiel, plus quelques
      `E741`/`UP034` dans `.claude/hooks/`). `packages apps` en compte davantage encore. Le
      rituel de clôture demande `ruff check .` : rouge de base, il ne distingue plus une
      régression d'un héritage, donc il ne protège plus rien. Soit on résorbe, soit on fixe
      un périmètre et on l'écrit dans le Makefile — mais pas les deux à moitié. Constaté le
      09/09, non traité : ce n'est pas une urgence, c'est une alarme qui ne sonne plus.

- [x] **Build analyse de portefeuille réparé (2026-09-06)** : blocs dupliqués de fusion
      retirés, composant client unique et build Next.js ajouté aux contrôles de PR.

- [~] **Analyse de portefeuille importée (2026-09-05, incrément 1/4)** : parcours local
      manuel/CSV → résolution prudente → confirmation → snapshot versionné livré. Restent le
      raccord aux historiques/FX réels, le diagnostic, l'optimisation sous contraintes, puis
      OCR/simulations/ML facultatif. Contrat d'intégration documenté dans
      `docs/PORTFOLIO_ANALYSIS_INTEGRATION.md`. Jointure read-only screening/fondamentaux/ML/
      résultats/macro livrée ; scénarios min-var/ERC/HRP affichés seulement pour un
      univers exact, avec turnover/coût/veto de plafond. Recalcul historique local livré avec alias
      crypto et alignement par intersection sans fill. Step 4 réparée en deux temps : plafond projeté
      si faisable (06/09), puis (07/09) alias `-USD` + lecture de `crypto.db`, clé `dynamique`
      partagée front/back, `analyze()` purgé de son code mort de fusion. « Dynamique » = HRP, nommé
      comme tel et sans verrou ML (il n'exige aucun μ). Reste FX multi-devises.
      Recommandation d'univers livrée (07/09) : sélection = screening du jour, poids = mêmes
      moteurs de risque, élagage T/N ≥ 30, écart affiché face aux lignes détenues. Reste à
      MESURER l'IC hors échantillon du score de sélection (`packages/research/information_coefficient.py`
      existe ; il manque l'historique des scores) — tant que ce n'est pas fait, la carte reste
      étiquetée non validée OOS. **Fait le 07/09** : `make ic-screening` mesure l'IC
      walk-forward (Spearman, fenêtres disjointes, coupe chronologique) et la carte publie le
      résultat. Reste à LANCER la mesure sur le VPS et à décider de l'horizon retenu — en tester
      plusieurs impose Benjamini-Hochberg. P1.
- [ ] **P1 — univers pollué par des titres délistés** (07/09) : le dry-run de
      `make noms-univers` a listé ATVI, CELG, ABC, CBS, DISCA/DISCK, ETFC, FRC, COL, FLIR, CBG,
      HRS, COG, CXO, DPS, DNB, CA (+ EVHC, SCG vus dans la recommandation) — sociétés acquises,
      renommées ou disparues entre 2018 et 2023. Elles occupent des places dans le screening et
      arrivent sans historique dans la recommandation. Décider : purge des seeds, ou filtre de
      fraîcheur sur la dernière barre. Mesurer d'abord le compte exact via le rapport groupé.

- [ ] **P1 — deux sources de prix pour le même univers** (07/09) : `_screen_section` lit le
      `panel` en mémoire du snapshot, `packages/portfolio/recommendation.py` lit
      YAHOO.db/crypto.db via `load_bars`. Des tickers screenés (EVHC, SCG — délistés 2018/2019)
      n'ont donc aucun historique côté recommandation. Soit passer le panel à la recommandation
      (comme `/analyze` reçoit `series_by_symbol`), soit exclure du screening ce que le loader
      ne sait pas charger. Mesurer d'abord combien de candidats sont concernés un jour normal.

- [x] **Copilote IA read-only (2026-08-29)** : chat global contextualisé par page, scopes/outils
      bornés, positions détaillées en opt-in, citations/as-of, garde numérique stricte et compteurs
      de rejets. Séparation AST : aucun import exécution/risque. L'IA reste hors chaîne d'ordres.
      Correctif Gemini : repli automatique vers l'API native si la couche compatible renvoie 404 ;
      comparaison portefeuille/Nasdaq désormais incluse dans les scopes overview/portfolio.
- [x] **Benchmarks dashboard non plats (2026-08-30)** : fusion par date du même ticker entre bases,
      sélection fraîche avant longueur, extension yfinance si le cache est périmé et alignement
      compte/indice sur les dates réelles. Un benchmark périmé est exclu, jamais forward-fill sur
      des mois avec l'étiquette « réel ».

## ✅ Recherche — livré le 2026-09-05 (soir)

- [x] **Information Coefficient mesurable — `packages/research/information_coefficient.py`.**
      `breadth.py` avait toute la mécanique Grinold-Kahn (souffle effectif, TC, IR,
      `optimal_horizon`) mais prenait l'IC en ENTRÉE. Rien ne le mesurait — vérifié
      par `grep spearmanr` sur tout le dépôt, zéro résultat. `information_coefficient()`
      (Spearman, NaN-safe, seuil N≥20, `None` si dégénéré) + `ic_in_sample_hors_echantillon()`
      (gate robustesse OOS/IS ≥ 0,5, même seuil qu'ADR-0066). 10 tests, vérifié bout en
      bout avec `ir_report` existant. Module d'analyse pur, aucun contact avec
      `order_gate.py` ni l'exécution.
- [ ] **P2 — Brancher l'IC sur un vrai signal de production.** Le module est prêt et
      testé sur synthétique ; il reste à l'alimenter avec de vraies prédictions du
      preset (ou d'un futur modèle ML) et des rendements réels, pour mesurer l'IC
      RÉEL de la stratégie — ce que ce module rend possible, pas ce qu'il fait déjà.

## 🔴 P0 — Le courtier détient ce que le journal ignore (constaté 2026-09-05)

- [ ] **Écart en sens INVERSE, sur 8 symboles — À REFERMER MAINTENANT, pas un nouveau
      bug.** `completer_ouvertures` avait tourné AVANT le retrait des 20 doublons ; en
      supprimant les fermetures en double, `achats_non_journalises` a MÉCANIQUEMENT
      augmenté (AVAX 274 → 605, LINK 66 → 228, LTC 1,5 → 61,6 — cf. `diag-surfermeture`
      après coup). Le trou n'est pas pire qu'avant, il est enfin VISIBLE dans sa
      taille réelle, démasqué par le nettoyage. Le correctif est déjà construit,
      testé, et déjà utilisé cette session — il suffit de le REJOUER dans l'ordre
      habituel, sur la vraie base, maintenant que les doublons sont partis :
      `make completer-ouvertures` (simulation) → `ARGS=--appliquer` →
      `make reconcilier-journal` (simulation) → `ARGS=--appliquer` → `make diag-journal`.
      **À jouer sur la machine qui détient la VRAIE base** (Mac mini ou VPS). Vérifié le
      07/09 : le `data/journal.db` d'une session distante contient 0 trade — c'est un
      fichier d'amorçage vide, non suivi par git. Y lancer `--appliquer` ne réparerait
      rien et produirait une archive trompeuse. Contrôle avant de lancer :
      `sqlite3 data/journal.db "select count(*) from trades"` doit rendre ~313, pas 0.
- [x] **Outillé le 05/09 — l'écart est DÉCOMPOSÉ** : `make diag-surfermeture`
      (`packages/research/sur_fermeture.py`, 7 tests). Identité vérifiée par ligne :
      `manque_ouvert = achats_non_journalises + sur_fermeture`. Sur les chiffres réels
      d'AVAX : 331,847254 = 274,407653 (entrées jamais écrites) + **57,439601 (sorties
      INVENTÉES)**. Les deux causes coexistent ; la seconde produit du « réalisé » sans
      contrepartie et contamine les statistiques.
- [x] **LANCÉ sur le VPS (05/09) — cause racine trouvée.** 95 lignes, TOUTES `P-`,
      AUCUNE `C-` : ce `journal.db` est la version D'AVANT `reconcilier_journal
      --appliquer` du Mac mini. PATH (0 ligne), NWL (1 ligne sur 1554,63) confirment
      un trou de SORTIES massif, pas de l'invention (`invente`=0 partout, vérifié à la
      main sur le relevé brut). Les deux machines n'ont jamais partagé le même fichier.
- [x] **P0 SYNC — FAIT (05/09).** `journal-push` (Mac) → `journal-pull` (VPS) : 313
      lignes des deux côtés. Confirmé, plus un risque théorique.
- [x] **P0 CRITIQUE — invention identifiée ET corrigée dans le code de PRODUCTION
      (05/09).** `diag-surfermeture` sur le journal réparé : +258,33 unités inventées
      (AVAX 60,82 · LINK 74,05 · OSCR 85,27 · LTC 36,00). Dump brut OSCR + calcul
      d'élimination : la ligne `P-20260831-Alpaca-OSCR` (motif `reconciliation paper
      (reduce/close)`, sans UUID) porte à elle seule les 85,27 inventées. Cause : dans
      `run_live.py`, `sold[].notional` portait le DELTA PLANIFIÉ (`cible − détenu`),
      jamais le fill réel — `close_sells` fermait `notional/prix` au lieu du fill.
      **Ce code tourne CHAQUE JOUR OUVRÉ** — sans correctif, la récidive était certaine
      dès lundi. Corrigé : `_fill_vente_jour` lit prix ET quantité du fill réel du jour ;
      `close_sells` accepte `qty_reelle`, prioritaire sur `notional/prix`, sans
      régression quand aucun ordre n'est citable. 6 tests. Détail : `04_JOURNAL`.
- [x] **AVAX + LTC vérifiés (05/09) — même mécanisme, reconstruit à ±0,0001 unité.**
      AVAX +60,8196 (attendu +60,8195), LTC +36,0020 (exact). 6 doublons confirmés au
      total (AVAX ×3, LINK ×2, LTC ×3) : un lot `-Xn` sans nom tombe sur la même
      date+prix qu'une correction nommée postée plus tard. Résidu distinct (pas un
      doublon) : l'ordre AVAX du 07-08 a 264,55 unités de vente réelle jamais
      journalisées.
- [x] **Outil de retrait construit (05/09) : `make annuler-doublons`.**
      `packages/research/doublons_correction.py` + `scripts/annuler_doublons_correction.py`,
      même squelette que `annuler_chronologie_impossible.py` (simulation par défaut,
      sauvegarde + archive JSON, `--appliquer` explicite). Ne retire QUE le lot sans
      nom — la correction nommée reste intacte. 10 tests, 6 cas réels en dur.
- [x] **APPLIQUÉ sur le compte réel (05/09).** 20 doublons retirés (au-delà des 8
      vérifiés à la main) · `INVENTÉ` 258,33 → **85,27** $ · sauvegarde + archive JSON.
- [x] **P2 RÉPONDU par la mesure (05/09, après retrait des doublons).** Le
      `diag-surfermeture` relancé après coup montre `invente = 0.0000` sur les 27
      symboles SAUF OSCR (85,27) — colonne par colonne, isolé, pas un pattern qui se
      répète. Répondu par les données déjà produites, pas par une nouvelle hypothèse.
      Reste ouvert seulement : la CAUSE de ce lot précis (`P-20260831-Alpaca-OSCR`,
      ouvert ET fermé le même jour) — creuser nécessite l'historique complet des
      ordres OSCR chez le courtier, pas disponible hors de l'environnement réel.

## 🟠 P1 — La détention médiane de 0,1 j reste NON expliquée (2026-09-05)

- [ ] **L'hypothèse du plancher de ligne (1 000 $) n'est ni confirmée ni écartée.** L'aperçu
      du 05/09 semblait la confirmer (7 cibles crypto « sous le plancher ») mais c'était un
      artefact de `--equity 10000` : à l'équity réelle ces cibles valent ~2 000-2 600 $ et
      ne touchent pas le plancher. À reprendre avec `make live` corrigé (equity réelle).

## 🔴 P1 — Trois dates d'arrêté distinctes sur le site (constaté 2026-09-04)

- [ ] **`dashboard` racine et `data` sont datés du 18/06** quand `events`, `themes` et
      `universe` le sont du 04/09, et `screener` / `dashboard.regime` du 02/09. Relevé par
      l'inventaire du gate de publication, qui les imprime sans juger. Trois dates sur un
      même site est peut-être légitime (fenêtre de backtest close vs données du jour), peut-être
      pas — **à trancher par la mesure avant d'en dire quoi que ce soit**. C'est exactement le
      genre d'incohérence entre onglets que l'utilisateur ne veut plus voir.

## ✅ Données & recherche — livré le 2026-09-04

- [x] **Verrou de détention minimale : MESURÉ, hypothèse NON retenue (04/09).** Question de
      l'utilisateur : laisser les trades ouverts au moins 10 jours pour « nettoyer » la
      volatilité d'entrée. Paramètre `detention_min` ajouté à `fast_swing_backtest`, balayé
      0/5/10/15 séances dans `sortie_lab`. Le 10 jours demandé est le PIRE des trois verrous
      (177 $ net contre 937 $ sans), la suite des Sharpe zigzague (0.17/0.29/0.18/0.20 — forme
      du bruit, pas d'un effet), la seule colonne monotone est le payoff qui BAISSE (2.65 →
      2.22 : coût mécanique du différé), et aucun DSR n'atteint le tiers de 50 %. La stat du
      journal réel qui motivait l'hypothèse est confondue : ses longues détentions sont des
      tranches d'un même lot crypto sur un seul rallye. Production reste à `detention_min=0` ;
      paramètre et 6 tests conservés pour re-mesurer plus tard. Détail : `04_JOURNAL` suite 13.
- [x] **P1 — Les deux priorités de fusion opposées : CORRIGÉ.** `_load_prices` gardait le
      premier provider, `merge_bars` le dernier, sur les MÊMES bases — 0,71 %/an d'écart sur
      le cœur QQQ. Une seule implémentation (`packages/data/fusion_sources`), premier gagne,
      raison écrite (base longue ajustée vs maj brute → pas de couture raw/ajusté au milieu
      de l'historique). Lignage : chaque jour porte le nom de sa source. ADR-0064. 9 tests.
- [x] **P1 — Les désaccords entre bases sont MESURÉS.** `make diag-fusion` : recouvrement et
      divergences par symbole. « Les bases sont d'accord » cesse d'être une hypothèse.
- [x] **P1 — Un scan compte comme un essai.** `packages/research/scan_registre` : critères
      structurés (liste fermée d'opérateurs), exécution pure, enregistrement au `ledger` sous
      `scan_ad_hoc`/`exploratoire`, empreinte idempotente. Le `N` du DSR était SOUS-estimé —
      les essais manuels ne laissent aucune trace. ADR-0065. 12 tests.
- [x] **P1 — DuckDB : la fabrique n'a AUCUN appelant (constat).** `make bench-backend` mesure
      la lecture SQLite vs DuckDB sur la vraie base, règle de décision écrite avant le run
      (< 1,5× on reste ; ≥ 1,5× conditionné à l'unification `DBPriceProvider` /
      `BarsRepository`). Aucun verdict sans mesure. ADR-0066.
- [ ] **P1 — LANCER les deux mesures (poste local).** `make diag-fusion` puis
      `make bench-backend`. Ce sont elles qui décideront s'il reste du travail sur les
      données ; sans elles, les trois points ci-dessus sont outillés mais pas tranchés.
- [ ] **P2 — Brancher le scanner sur le copilote.** `scan_registre` est prêt et testé ; il
      manque l'outil côté `/api/ai/chat` qui traduit la question en critères, appelle
      `executer` sur les lignes du screener, puis écrit au ledger si l'empreinte est neuve.
- [ ] **P2 — Onze pages hors de la barre**, dont `/data` (l'onglet « entrepôt » demandé
      existe déjà). À trancher explicitement plutôt qu'au fil des signalements.

## 🔴 P0 — DualMarketScreening : deux défauts qui invalident des verdicts (2026-08-22)
Détail et raisonnement : `vault/22_AUDIT_DUALMARKET.md`.
- [ ] **Correction pour tests multiples (Benjamini-Hochberg)** sur le criblage de paires.
      Cribler N paires à `p < 0,05` produit 5 % de faux positifs PAR CONSTRUCTION : sur 100
      paires, ~5 verdicts « tradable » qui ne sont que du bruit. BH plutôt que Bonferroni (sur
      des paires corrélées, Bonferroni ne laisse rien passer). **Publier le nombre de paires
      testées avec le verdict** — un « tradable » issu d'un criblage de 500 ne vaut pas celui
      issu de 5.
- [ ] **Coût dépendant de la DURÉE dans `optimal_band`** : `c(u) = c_fixe + c_portage × E[T(u)]`.
      `E[T(u)]` est déjà calculé par `ou_mfpt`. Sur 2-8 jours en perpétuels, le funding domine et
      change de signe — un spread brut positif peut être négatif net de portage, et le modèle
      actuel ne peut pas le voir puisque le coût ne dépend pas du temps.
- [ ] **CCXT** — prérequis du point précédent : sans funding rates ni open interest, le
      correctif n'a pas de données.
- [ ] P1 — **Calibration Kalman sans look-ahead** : `kalman_calibrate` cherche (δ, r) par MLE sur
      TOUTE la série. Le z-score est sans look-ahead *étant donné* (δ, r), mais (δ, r) a vu le
      futur. Calibrer sur une fenêtre d'apprentissage seule. **Brique causale livrée** dans
      `packages/research/kalman_causal.py` (MLE sur préfixe + filtre avant uniquement) ; reste à
      remplacer l'appel DualMarket et à fournir un benchmark de marché exogène au preset.

## 🟡 P1/P2 — ouverts le 2026-09-02

- [ ] **P1 — Instabilité entre runs : PISTE SÉRIEUSE (03/09).** Deux runs consécutifs sont
      identiques au caractère près → le code est DÉTERMINISTE. L'instabilité 0,65 → 0,38
      s'était produite à un JOUR d'écart, donc après un rafraîchissement de données.
      Hypothèse : c'est le MÊME défaut que l'anomalie du cœur QQQ — `_index_series` laisse
      `market.db` écraser `YAHOO.db`, donc chaque `make daily` peut déplacer le niveau
      d'ajustement de tout l'historique. Tester en gelant market.db entre deux runs.
- [ ] ~~**P1 — ancien libellé : Instabilité entre runs NON EXPLIQUÉE**~~ : Sharpe 0,65 puis 0,38 sur un appel
      identique au caractère près, à un jour d'écart. L'hypothèse du repli VIX est TOMBÉE
      (le run affiche « VIX RÉEL »). Les bancs publient désormais une empreinte (titres,
      barres, dernière date, provenance VIX) — **aucune comparaison entre deux dates n'est
      valide tant que la cause n'est pas trouvée**.
- [x] **P1 — `make coeur-multi` exécuté (03/09)** : aucune variante ne passe. Corrélations
      conformes à la prémisse (GLD/QQQ +0,11, QQQ/TLT −0,09) mais aucun gain de Sharpe, et
      le Calmar reste en faveur de la production (0,605 vs 0,532). Détail complet dans
      `vault/10_BACKTEST_RESULTS.md`.
- [x] **P1 — Les deux sens de fusion : CORRIGÉ le 04/09** (cf. section « Données & recherche »
      en tête de fichier). Ancien libellé conservé ci-dessous.
- [ ] ~~**P1 — `_index_series` et `_load_prices` fusionnent les bases en sens OPPOSÉS.**~~
      Diagnostiqué le 03/09. `_load_prices` fait `setdefault` (YAHOO.db prioritaire,
      market.db comble les trous) — choix DÉLIBÉRÉ, commenté « pas de discontinuité
      d'ajustement raw vs adjusted ». `_index_series` fait `target[jour] = close` via
      `merge_bars` : market.db écrase. Le cœur QQQ de production est donc potentiellement
      recollé entre deux référentiels d'ajustement, pour **0,71 %/an** sur la moitié du
      portefeuille. Deux hypothèses antérieures FALSIFIÉES : ce n'est pas ^NDX (source =
      QQQ frais), ce n'est pas un désalignement de calendrier (0 séance d'écart).
      **Reste à confirmer** par le bloc « COMPARAISON DES DEUX BASES » avant de corriger :
      si les bases sont d'accord partout, le sens de fusion est sans effet et la cause est
      ailleurs. Correctif attendu : aligner `merge_bars` sur la sémantique de
      `_load_prices`, pas l'inverse.
- [x] **P1 — Bêta 0,037 et « contribution alpha 1072 % » sur le tableau de bord : CORRIGÉ le 04/09.**
      Cinquième occurrence de l'empilement positionnel : `packages/reporting/analytics.py` faisait
      `min(len(r), len(b))` puis `[-m:]`. Le correctif du matin (ADR-0067) portait sur
      `compute_attribution` (miroir Obsidian), pas sur ce que le web affiche. Sixième dans la
      foulée : `_bench_series` posait le i-ème cours du S&P sur la i-ème date de l'equity.
      Mesuré : 1,25 % de séances manquantes ramènent un bêta de 1,200 à 0,345 (corr 1,000 → 0,288).
      `alignement` et `n_observations` sont désormais PUBLIÉS, et le front avertit en orange quand
      l'appariement reste positionnel. ADR-0072.
- [x] **P1 — Rebalancement journalier vs. tenir jusqu'au TP/SL : MESURÉ le 04/09.** Réponse :
      la question ne se pose pas comme un réglage. `sortie_lab` (où l'on règle `rr` et le
      suiveur) rejoue `fast_swing_backtest` ; la production applique des poids cibles
      `preset risk-parity`. Deux moteurs. La production n'a ni stop ATR, ni cible, ni
      suiveur — `rr 6 → rr 9` ne changerait pas un ordre. ADR-0073.
      Journal réel, décisions du SYSTÈME seules : 6 positions en 57 j, détention médiane
      **0,1 jour**, t = +0,92 (non significatif), capture −22 % sur 5 mesurables.
- [x] **P0 — VPS bloqué sur `make daily`/`make ingest-crypto` : CORRIGÉ le 04/09.**
      Deux bugs distincts, trouvés en lançant les commandes que j'avais moi-même données :
      (a) `ingest_crypto.py` important `timezone` DEPUIS `apps.api.snapshot`, qui ne
      l'exporte plus (il utilise `UTC`) — `ImportError` immédiat, crypto.db resté figé au
      20/06. Corrigé : import direct depuis `datetime` stdlib.
      (b) `ingest_prices.py` : le `market.db` tiré du cache HuggingFace public a un schéma
      `prices` à 7 colonnes (sans `adj_close`) plus ancien que le code actuel (8 colonnes),
      et `CREATE TABLE IF NOT EXISTS` ne migre pas une table déjà là → `sqlite3.OperationalError`
      sur l'INSERT positionnel. Corrigé : `_migrer_schema` (ALTER TABLE idempotent), 3 tests.
- [ ] **P0 — Pourquoi la production tient-elle ses positions 0,1 jour ?** Le banc de sortie
      suppose 42 à 48 jours ; la production solde en quelques heures. Ce n'est pas un
      désaccord statistique (n=6 n'y change rien), c'est une description de comportement.
      **Hypothèse à vérifier, pas une cause établie** : le plancher de ligne (1 000 $)
      solderait une ligne ouverte la veille dès que sa cible repasse sous le plancher —
      ouvrir puis liquider, en boucle. Méthode : rejouer deux runs consécutifs de
      `run_live.py --live --yes` sur un compte de test et tracer, pour chaque symbole, la
      cible et le détenu d'un run à l'autre. Corriger seulement après avoir vu le cycle.
- [ ] **P1 — `sortie_lab` : verdict instable entre deux fenêtres.** « Sans suiveur » donne
      Sharpe 0,50 sur les données au 04/09 et 0,03 au 20/06 (rallye crypto de juillet-août
      dans l'intervalle). Le banc avertit lui-même qu'on ne compare qu'à empreinte
      identique. Refaire les deux runs sur la MÊME empreinte (le VPS est arrêté au 20/06 :
      `make ingest` d'abord) avant d'accorder le moindre crédit au réglage.
- [x] **P0 — 6 round-trips à chronologie impossible : OUTILLÉ le 04/09 (PATH etc).**
      L'utilisateur a repéré PATH (entrée 03/09, sortie 01/09) directement dans le journal.
      Confirmé : c'est le bug DUOL du 03/09 (`reconcilier_journal._plan` appariait au plus
      ancien lot SANS regarder sa date), déjà corrigé par la garde `_anterieur` — mais la
      garde n'est pas rétroactive. 6 enregistrements déjà écrits (SJM, STT, PATH, DUOL, TYL,
      T) portent -142,33 $ de « réalisé » qui ne correspond à aucune opération.
      `make annuler-chronologie` (simulation par défaut, sauvegarde + archive JSON avant tout
      retrait, 5 tests) — retire, ne corrige pas : rouvrir supposerait de savoir à quel lot
      RÉEL la vente aurait dû s'apparier, ce qui n'est pas mesurable ligne à ligne.
      **Appliqué le 04/09 sur le Mac mini** : 6 round-trips retirés, sauvegarde + archive JSON.
- [x] **P0 — « Deux chaînes fermées par la même vente » sur LINK : FAUSSE ALERTE, vérifiée
      et retirée le 04/09.** Un lot `P-...-X1` (86,88 unités) et un lot `C-LINK-R3`
      (88,60 unités) fermaient tous deux le 27/08 au même prix — j'ai lu ça comme un
      double comptage sans faire l'addition qui aurait dû trancher AVANT de le consigner
      en P0. Vérifié sur l'ordre réel `ee481ad2` (07/08, l'autre paire suspecte) :
      quantité RÉELLE 273,12538382 $. Or 125,613741 (C-LINK-R1) + 147,511643 (P-lot)
      = 273,125384 — exact au dix-millième. `_plan` regroupe déjà `P-` et `C-` dans UN
      SEUL pool par symbole (`scripts/reconcilier_journal.py`, fonction `_plan`) : une
      vente plus grosse que le premier lot de la file en ferme légitimement plusieurs à
      la suite. C'est le comportement voulu, pas un bug. Leçon : `python3 -c` sur
      `AlpacaBroker().orders()` filtré par symbole tranche ce genre de doute en une
      commande — le réflexe à avoir AVANT d'écrire "bug" dans ce fichier.
- [ ] **P1 — Détention minimale : PARAMÈTRE CONSTRUIT le 04/09, PAS ENCORE MESURÉ.**
      Hypothèse de l'utilisateur devant son journal : « les trades < 10 j perdent, mieux
      vaudrait tenir 10 j le temps que la volatilité d'entrée se nettoie ». Le journal ne
      pouvait PAS trancher — toutes les longues détentions y sont des tranches d'un même
      lot crypto du 07/07 sur le rallye de juillet-août, et toutes les courtes sont des
      actions du rebalancement quotidien : comparer les deux compare des classes d'actifs
      et une fenêtre de marché, pas des durées de détention.
      Construit à la place : `fast_swing_backtest(detention_min=N)` (en séances) +
      3ᵉ table dans `make labs` / `sortie_lab.py`, balayage 0/5/10/15 j. Le verrou DIFFÈRE
      les sorties molles (cible, suiveur, cassure MM longue) et laisse TOUJOURS passer le
      stop initial — sinon on mesurerait « tenir sans garde-fou » et le maxDD changerait
      de sens. 6 tests sur la mécanique (`tests/backtest/test_detention_minimale.py`).
      **À FAIRE : lancer `make labs` et lire la 3ᵉ table** — jours ET maxDD ensemble, un
      verrou allonge la détention par construction, la question est ce qu'il coûte en
      baisse maximale. DSR déjà déflaté des 4 essais supplémentaires.
- [x] **Trois copies divergentes — RÉSOLU pour l'état actuel (05/09).** Source de vérité
      tranchée : le VPS (réparé le plus récemment). `journal-push` (VPS) → `journal-pull`
      (Mac mini) : les deux machines ont désormais le MÊME fichier (159 744 octets,
      293 lignes, invention isolée à 85,27 $ sur OSCR). Le trou STRUCTUREL demeure : rien
      n'automatise ce push/pull, donc une nouvelle divergence peut réapparaître si les
      deux machines écrivent sans se resynchroniser. Discipline à tenir : le VPS écrit en
      continu (`cron_live.sh`), le Mac/MacBook restent des postes de LECTURE — jamais un
      second exécuteur live — et un `journal-push` régulier depuis le VPS reste manuel.
- [ ] **P1 — Rebalancement journalier vs. tenir jusqu'au TP/SL : MESURÉ le 24/09, décision ouverte.**
      **Le chiffre est là** (cf. l'entrée « chiffre pondéré » ci-dessus) : 552 décisions
      du système, +0,08 % pondéré sur 889 640 $ engagés, détention médiane **1,0 jour**,
      41,0 clôtures/semaine, et l'audit CONFIRME sur données réelles ce qui n'était qu'un
      constat de code — **aucune sortie n'est déclenchée par un TP ou un SL**. Ce qui
      reste à trancher est la DÉCISION, pas la mesure : bande de tolérance élargie sur le
      rebalancement existant (probable), ou moteur TP/SL parallèle (qui créerait un
      conflit d'arbitrage avec le risk-parity). **Ne rien coder tant que deux entrées
      ci-dessus ne sont pas closes** : les frais ne sont mesurés que sur 64 fermetures sur
      597 (donc aucun arbitrage de coût n'est possible), et la capture repose sur 5
      positions côté système — elle peut venir du rebalancement comme d'une fenêtre `mfe`
      trop courte pour une détention d'un jour, et rien ne le dit à cet effectif.
      Contexte d'origine (04/09) :
      Question de l'utilisateur : le rebalancement quotidien vers les poids cibles coupe-t-il
      des positions gagnantes avant leur potentiel ? Constat de code (pas de mesure) :
      `run_live.py` n'a AUCUNE sortie déclenchée par un TP/SL — une seule cause de clôture
      existe, le rebalancement (`exit_reason` toujours "reconciliation paper (reduce/close)").
      Outil construit : `make turnover-audit` (`packages/research/turnover_audit.py`, 8 tests
      synthétiques) — frais/slippage cumulés, durée de détention médiane, taux de gain, et une
      « capture » (`pnl_pct / mfe`) qui dit si une ligne sort loin de son meilleur point observé
      PENDANT sa détention (limite explicite : ne dit rien de l'après-sortie, `mfe`/`mae` sont
      bornés à la fenêtre [entrée, sortie]). (Le « UNCALIBRATED » de l'époque tenait au
      journal vide du conteneur cloud ; il est levé depuis le passage du 24/09 sur le VPS.)
- [ ] **P1 — Trois occurrences restantes du même moule, IDENTIFIÉES PAR LECTURE, pas mesurées.**
      (a) `eqw` (indice équipondéré, `apps/api/snapshot.py`) : `zip(*norm)` empile la PREMIÈRE
      barre de chaque titre — 2015 pour un ancien, 2023 pour une IPO récente. Il alimente
      `multi_strategy`, `relative_metrics` et le benchmark « Univers (équipondéré) ».
      (b) `fast_swing_backtest` : `n = max(len(b))` et horodatage pris du PREMIER symbole.
      (c) `packages/portfolio/benchmark._align` : tronque par le DÉBUT face à une equity plus
      longue que `eqw` — donc compare deux fenêtres différentes.
      **Mesurer avant de corriger** (l'écart réel se chiffre sur la base locale, pas ici) : dumper
      les longueurs et les dates de début/fin de `equity`, `eqw` et `data[s]`. Semantique à
      préserver pour `eqw` : moyenne de NIVEAUX normalisés (achat-conservation), pas moyenne de
      rendements — sinon deux changements se superposent et on ne sait plus lequel bouge le chiffre.
- [ ] **P2 — L'alignement positionnel de `blend_equity` tombe juste par COÏNCIDENCE.**
      Mesuré : 0 séance d'écart entre le calendrier du cœur et l'axe du preset. Rien ne le
      garantit — un titre ajouté à l'univers change l'axe et casse silencieusement le
      recollage `core_ret[-k:] = xr[-k:]`. Aligner par DATE tant que ça ne coûte rien.
- [x] **P1 — Fenêtre vs code : TRANCHÉ le 03/09.** C'est la FENÊTRE. Sharpe 1,33 reproduit
      exactement sur la fenêtre ancienne. À fenêtre égale le code a AMÉLIORÉ le preset
      (Sharpe 0,99 → 1,12, maxDD −31,7 % → −25,4 %) au prix de 3 points de CAGR. Détail
      dans `vault/04_JOURNAL.md`.
- [x] **P1 — AUDIT DE FUITE sur le momentum sectoriel : FAIT le 04/09.** Trois causes
      séparées par la mesure. (1) Coûts absents — rotation mensuelle sur deux secteurs
      comparée à QQQ, buy-and-hold de turnover nul : **0,64 pt de CAGR** mesuré sur
      panneau synthétique. Corrigé à 5 bps, frais publiés. Réel mais MINEUR. (2) MM50 :
      look-ahead DORMANT dans le préfixe (`out[0]` = moyenne des jours 0..w−1, lue à
      t=10 elle contient l'avenir) — jamais lu aujourd'hui puisque la boucle démarre à
      126, mais un `lookback` plus court le réveillerait en silence. Remplacé par NaN.
      (3) **Univers de SURVIVANTS — la cause principale** : `build_snapshot` retire tout
      titre dont la dernière barre a plus de dix jours, donc tous les délistés, AVANT le
      backtest. Le statut du biais est désormais ATTACHÉ au résultat. ADR-0069. 9 tests.
- [ ] **P1 — Le biais du survivant n'est pas CORRIGÉ, seulement déclaré.** Il faut
      l'historique de prix des délistés ; le dépôt sait le catalogue sous-échantillonné
      (43 symboles). Tant qu'il manque, ce cœur reste INDICATIF et le dit lui-même. À
      trancher : re-sourcer les délistés, ou retirer ce cœur des candidats de production.
- [ ] **P1 — Vérifier si les AUTRES backtests souffrent du même nettoyage d'univers.**
      Le retrait des titres périmés est fait une fois dans `build_snapshot`, en amont de
      TOUS les consommateurs (preset, conviction, megacap…). Le momentum sectoriel n'est
      pas un cas particulier — c'est celui où le symptôme était le plus visible.
- [ ] ~~**P1 — ancien : Fenêtre vs code**~~ Un ancien
      dashboard affichait Sharpe 1,34 / CAGR 20,1 % sur n=2391 depuis 2017-04 ; l'actuel
      0,95 / 14,9 % sur 2 580 séances depuis 2016-03. Treize mois de plus au début. Rejouer
      le code actuel sur la fenêtre ancienne sépare les deux causes en un seul run.
- [ ] **P1 — 610 → 1 299 trades NON EXPLIQUÉ.** Plus du double, pour une fenêtre +8 % et un
      univers-graine inchangé (1 047 lignes, vérifié sur 6 commits). Changement de règle ou
      d'ensemble éligible. À trouver avant d'interpréter le PF 1,48 → 1,08.
- [x] **P2 — `obsidian.attribution` alignait par position : CORRIGÉ le 04/09.** La racine
      était `_index_closes`, qui jetait les dates rendues par `_index_series` une ligne avant
      qu'elles servent. Les dates voyagent (`qqq_dates` au snapshot), l'appariement se fait par
      date (`apparier_deux_series`), et sans les deux calendriers l'attribution REFUSE de
      conclure. Contre-épreuve : un décalage de fin ne reproduit pas le défaut (les séries
      finissent le même jour) — seuls des trous INTÉRIEURS le montrent, 0,29 contre 1,00 sur le
      même actif. ADR-0067. 3 tests.
- [x] **P2 — Les trois conventions de Sortino : UNIFIÉES le 04/09.** `portfolio.deviation`
      porte la définition (RMS de min(r,0) sur N total), en Python pur — `analytics` et
      `company_report` évitent numpy délibérément. Quatre appelants branchés. L'écart réel est
      plus grand que ce que cette note annonçait : mesuré sur 2 520 rendements, ×1,128 pour
      l'écart-type des négatifs et ×1,191 pour celui de min(r,0), pas ×1,04. Les Sortino
      publiés baissent de 12 à 19 % : c'est une flatterie qui disparaît. ADR-0068. 7 tests.
- [ ] ~~**P1 — Expliquer la dégradation du backtest**~~ : PF 1,19 → 1,08, espérance 6 $ → 2 $,
      payoff 2,79 → 2,62, 1 168 → 1 299 trades. Deux causes possibles à départager :
      `trail_atr=0` pas encore dans `main`, ou décalage du jeu de données (même P1 que
      ci-dessus). **Ne rien conclure de ces chiffres avant.**
- [ ] **P2 — Consolider `institutional_price_action` sur `indicators/liquidite_ict`** :
      SFP, order block et cassure de structure existent en deux exemplaires depuis le 02/09.
      Le recouvrement est documenté dans les deux fichiers ; il n'est pas résolu.
- [ ] **P2 — Mesurer les modules SHADOW avant tout branchement** (porte de
      `vault/15_CERTIFICATION.md`) : `liquidite_ict`, `garde_swing`, `caracteristiques_swing`,
      `moteur_swing`, `metriques_survie`. Un composant non certifié en production = P0.
- [ ] **P2 — Données intraday (1H/4H)** : sans elles, la jambe de raffinement de la spec
      swing reste câblée mais non mesurable. Ne pas la déclarer active entre-temps.
- [ ] **P2 — NE PAS explorer l'interaction (sans suiveur × rr 9)** : le classement des
      cibles s'est inversé entre deux jeux de données. Chaque essai supplémentaire relève
      le seuil du DSR sur tout le reste (ADR-0050).

- [ ] **P2 — Texte du panneau « Journal des round-trips » à corriger** : il annonce être
      « la matière première du verdict GO/NO-GO du 2026-08-06 ». C'est FAUX — `rdv_paper`
      lit la courbe d'equity, pas le win rate (vérifié le 03/09). Le texte invite à lire le
      87 % comme une preuve de performance, ce qu'il n'est pas.

- [x] **P0 — La CAUSE des achats manquants : TROUVÉE ET CORRIGÉE le 03/09.**
      `run_live._journal_opens` prenait le fill dans la POSITION du courtier, lue juste
      après l'envoi de l'ordre. Position pas encore rafraîchie → achat introuvable et
      **jamais** journalisé (le message « capturé au prochain run » était faux : rien ne
      le capture). Position lisible → quantité TOTALE et prix de revient MOYEN, pas
      l'achat du jour. Le fill vient désormais des **ordres exécutés du jour**
      (`agreger_achats`, VWAP par symbole canonique) ; la position n'est plus qu'un repli.
      ADR-0056. 6 tests (`tests/execution/test_fills_ouverture.py`).
- [x] **P0 — Rattraper l'historique manquant : OUTIL LIVRÉ le 03/09.**
      `make completer-ouvertures` (simulation par défaut, `ARGS=--appliquer` écrit après
      sauvegarde) reconstitue les achats que le courtier a exécutés et que le registre
      ignore — 30 symboles sur 87 au dernier diagnostic. Prix retenu = VWAP des fills
      **non couverts** (fills consommés en FIFO à hauteur du déjà-journalisé), pas VWAP
      global. Lots en `legacy=1` : leurs features de décision n'existent pas et ne
      peuvent plus exister. ADR-0057. 11 tests.
- [x] **P0 — Idempotence en QUANTITÉ du réconciliateur (03/09).** Écarter un fill de vente
      dès son premier usage condamnait les lots reconstitués après coup à rester ouverts
      pour toujours (leur vente existe, mais était marquée consommée en entier). On compte
      les unités fermées par fill et on rejoue le reste. 3 tests de plus.
- [x] **P0 — Réparation LANCÉE et vérifiée le 03/09.** 30 ouvertures reconstituées
      (99 847 $ de coût de revient), 67 fermetures postées (−3 860 $), couverture
      **57/87 → 87/87, 0 incomplet**. Identité comptable : attendu +1 009,24 $ contre
      +904,50 $ constatés, **écart −104,74 $** (contre −4 198 $ avant) = latent au
      premier point de la courbe + frais hors P&L, ce qui est le comportement attendu.
- [x] **P0 — Cause du 2× TROUVÉE et mesurée à l'échelle (03/09).** Les FERMETURES sont
      justes : 79/87 symboles ferment exactement ce qu'ils achètent, les 8 autres sont
      ceux encore détenus. Tout l'excédent est dans les lots ouverts, et **33 des 52
      portent le symbole, la quantité et le prix EXACTS d'une vente exécutée** — des
      sorties écrites à l'endroit des entrées. Le critère étant strict (fill unique),
      33 est un PLANCHER.
- [x] **P0 — `annuler-ventes` LANCÉ et vérifié (03/09).** 33 lots retirés :
      343 enregistrements → 310 · lots ouverts `legacy` 45 → 12 · fantômes 43 → 10 ·
      symboles à 2× **29 → 3** · excédent 3 308 → 1 317 unités · lots appariés à une vente
      **33/52 → 0/19**. Le reliquat (NWL 1,74×, MAS 1,91×, QQQ 1,56×) vient de ventes
      exécutées en PLUSIEURS fills que le critère strict refuse d'apparier — plancher assumé.
- [ ] **P1 — Le reliquat multi-fills (NWL, MAS, QQQ).** Apparier un lot ouvert à la SOMME de
      plusieurs fills de vente du même jour, pas à un fill unique. Plus permissif, donc à
      n'écrire qu'avec la même discipline : preuve archivée, simulation d'abord.
- [ ] **P1 — Six sorties antérieures à leur entrée, −142,33 $** (SJM, STT, PATH, DUOL, TYL, T).
      La garde `_anterieur` empêche d'en créer ; elle ne rétroagit pas. Les rejouer suppose de
      savoir à quel lot chaque vente aurait dû s'apparier : décision de plan complet.
- [x] **P1 — « Mon profil » : réglages perdus à la navigation + affirmation fausse (03/09).**
      L'effet d'écriture partait au MONTAGE avec les valeurs par DÉFAUT et écrasait le stockage
      avant que la restauration ne s'y réécrive ; quitter la page entre les deux perdait le
      réglage. Drapeau `lu` : rien n'est écrit avant d'avoir lu, et la persistance est séparée
      de l'appel API. Mesuré par ailleurs : `quant.profil` n'est lu QUE par la page qui l'écrit,
      donc « ces chiffres CONTRAIGNENT votre outil » était faux — page et API corrigées.
- [ ] **P2 — Câbler le profil sur la chaîne (budget de perte → dimensionnement).** Aujourd'hui
      c'est un calcul de référence isolé. Tant que ce n'est pas fait, le texte doit le dire.
- [x] **P1 — Onglets introuvables : `/sentiment` et `/events` remis dans « Marché » (03/09).**
      Signalé : « je ne retrouve plus l'onglet des news ». Elles n'avaient pas été supprimées —
      la réduction à 3 groupes les avait laissées hors de tout menu, joignables seulement par
      URL directe ou ⌘K. Une page qu'on ne peut atteindre qu'en connaissant son adresse
      n'existe pas pour l'utilisateur.
- [ ] **P2 — Onze pages restent hors de la barre** (`/fiche`, `/live`, `/trades`, `/portfolio`,
      `/ml`, `/conviction`, `/notes`, `/investors`, `/fundamentals`, `/data`, `/accueil`).
      C'est le résultat de l'audit « simplicité radicale », pas un accident : à trancher
      explicitement, pas à défaire au fil des signalements.
- [x] **P1 — « Série arrêtée » disait faux sur le Bund (03/09).** 94 jours de retard contre un
      seuil de 93 — un dépassement d'UN jour, soit 3,03× la cadence, quand le cas qui a motivé
      la règle (chômage zone euro) valait 43×. La série OCDE des taux longs publie avec deux
      mois de décalage structurel : elle rebasculerait en « arrêtée » chaque trimestre. Deux
      seuils : **retard** au-delà de 3× la cadence, **arrêt** au-delà de 12×. `perimee` reste
      vrai dès le retard (aucun appelant cassé) ; `statut` porte la nuance.
- [x] **P0 — Une SORTIE pouvait précéder son ENTRÉE (03/09).** Signalé par l'utilisateur
      sur DUOL (entrée 03/09, sortie 01/09). `_plan` appariait au plus ancien lot du
      symbole sans regarder sa date : une vente fermait un lot qui n'existait pas encore,
      et son P&L sortait d'un prix de revient postérieur à la sortie. Garde `_anterieur`
      au JOUR (pas à la seconde : le lot porte l'instant du run, le fill celui de
      l'exécution). Le FIFO saute le lot trop récent. 4 tests.
- [ ] **P1 — Les round-trips à chronologie impossible DÉJÀ écrits.** La garde ne
      rétroagit pas. `_sorties_avant_entree` les compte au `diag-journal` ; les rejouer
      suppose de savoir à quel lot la vente aurait dû s'apparier — décision de plan
      complet, pas ligne à ligne. **Lire d'abord le compte et le P&L concernés.**
- [x] **P1 — Le panneau affichait un sous-ensemble favorable sans le dire (03/09).**
      `legacy=0` : +6 260,82 $ et 70 % ; compte réel : +569,31 $ et 56 %, le filtre
      masquant 266 lots et −5 691,51 $. `perimetre_affiche` publie les deux côte à côte,
      chiffrés, sur `/api/journal` et sur la page. Les lots `legacy` ne sont PAS versés
      dans la statistique affichée : sans features de décision, ils rendraient inutilisable
      le chiffre qui sert la calibration ML.
- [x] **P1 — Le panneau du journal disait une chose fausse : CORRIGÉ le 03/09.**
      « C'est la matière première du verdict GO/NO-GO » — non, `rdv_paper` lit la courbe
      d'équité. Le texte dit maintenant que le registre décrit les TRADES et non la
      performance du compte, et que son taux de réussite est biaisé à la hausse par
      construction (le rebalancement solde les gagnants, garde les perdants ouverts).

- [x] **P1 — Réconcilier le journal et le compte : FAIT le 03/09.** Ce ne sont ni les
      retraits (aucun saut > 3 984 $/j) ni le filtre `legacy` (0 $ masqué). Le journal
      porte ~80 actions que le compte ne détient plus, deux fois trop de QQQ, et la
      crypto sous deux conventions de nommage jamais appariées. Les ventes récentes
      s'apparient en FIFO à ces lots morts → 5 821 $ de « réalisé » sans contrepartie.
- [x] **P0 — Lots orphelins : OUTIL LIVRÉ le 03/09.** Ni suppression ni bascule en
      `legacy` (drapeau réservé aux fills importés — le réutiliser le rendrait illisible).
      Écritures de correction datées, appariées aux fills RÉELS d'Alpaca, motif
      `reconciliation-journal`. `make reconcilier-journal` simule ; `--appliquer` écrit
      après sauvegarde. Les lots sans vente correspondante RESTENT ouverts et sont
      signalés — les fermer au dernier prix inventerait un P&L.
- [x] **P0 — Restaurer et rejouer : FAIT le 03/09.** 185 écritures, zéro avertissement.
- [x] **P0 — « Lots en double » : HYPOTHÈSE FAUSSE, mesurée le 03/09** (« aucun doublon »).
      La vraie cause : `AlpacaBroker.orders` ne PAGINAIT pas. 500 demandés, 202 rendus,
      moitié des ventes jamais arrivées. Pagination + fonction pure `paginer` + 5 tests.
      Pagination livrée : 202 → 419 ordres, mais 202 ventes INCHANGÉES (les achats
      étaient tronqués, pas les ventes).
- [ ] **P0 — Restaurer l'état d'AVANT réparation et rejouer UNE fois.** Les 185 fermetures
      actuelles portent un motif sans identifiant de vente : intraçables, donc le script
      refuse désormais de tourner dessus. `cp data/journal.avant-reconciliation-20260903-195231.db
      data/journal.db` puis un seul `make reconcilier-journal ARGS=--appliquer`.
- [ ] ~~**P0 — ancien : le journal écrit chaque lot en double**~~ Découvert le 03/09 après réparation :
      les quantités restantes valent EXACTEMENT la moitié des initiales sur des dizaines de
      titres (AAPL 47,28 → 23,64, BXP 212,62 → 106,31, CNC 228,81 → 114,40). Les ventes ont
      soldé une copie et laissé l'autre. Explique aussi QQQ 137,1 vs 70,45 détenus.
      `make diag-journal` compte désormais les doublons (`_doublons`).
      **Chercher la cause dans le chemin d'ÉCRITURE** (`live_journal`, boucle de
      réconciliation) — supprimer les lignes en aval les ferait revenir au prochain
      rebalancement. AUCUNE écriture de plus avant d'avoir trouvé.
- [ ] **P1 — Les 39 round-trips déjà fermés restent fondés sur de mauvais prix de revient.**
      Produits entre le 27/08 et le 02/09 par `close_sells` contre les lots du vieux
      portefeuille. Fermer les orphelins ne rétroagit pas sur eux : les 87 % et les
      149,27 $ affichés restent faux (marqués `fiable: false`). Les recalculer suppose de
      les ANNULER puis de les rejouer contre le bon vivier — opération plus invasive que
      la précédente, sur des enregistrements déjà publiés. À spécifier avant d'agir.
- [ ] ~~**P0 — ancien : restaurer et rejouer**~~
      Le premier passage a écrit 185 fermetures avec le mauvais périmètre (`legacy` non
      conservé) et des ids de scission en collision. Corrigé, mais le registre porte
      encore les écritures fautives. Restaurer la sauvegarde puis relancer.
- [x] **P1 — Nommage crypto : CORRIGÉ à la source.** `open_lots` apparie par symbole
      canonique. C'est ce qui empêchera de nouveaux orphelins.
- [ ] ~~**P0 — ancien : décider du sort des lots orphelins**~~ Tant qu'ils y sont,
      toute vente s'apparie à eux et fabrique du réalisé. Deux options, à trancher :
      (a) les solder à leur date de sortie réelle — demande un historique de fills que
      nous n'avons peut-être plus ; (b) les basculer en `legacy=1` — les sort du calcul
      sans réécrire le passé. **Aucune correction automatique** : c'est une décision.
- [ ] **P2 — Unifier le nommage crypto à L'ÉCRITURE aussi.** L'appariement est corrigé
      (lecture canonique), mais le journal continue d'écrire « AVAX/USDC » quand le
      courtier dit « AVAXUSD ». Fonctionnel, mais deux conventions cohabitent.
- [ ] ~~**P1 — ancien : Réconcilier le journal et le compte**~~ 39 fermés × 149,27 $ = 5 821 $ réalisés
      + 614 $ de latent ≈ 6,4 % sur ~100 k$, contre **+0,2 % sur deux mois** affiché pour le
      portefeuille RÉEL. À vérifier : (1) `/api/journal` filtre `legacy=False` et exclut donc
      les fills importés que le compte subit ; (2) les aller-retours tombent-ils dans la
      fenêtre d'`equity_history` ? **Outil livré : `make diag-journal`** — il mesure les
      deux et imprime le résidu. Ne rien conclure avant de l'avoir lancé.

- [ ] **P1 — Le panneau « Journal des round-trips » doit cesser de se présenter comme une
      mesure de PERFORMANCE.** Mesuré le 03/09 : le journal ne couvre que 57 des 87
      symboles achetés (moitié de la crypto, 9/139 sur PATH). Ses win rate et espérance
      décrivent des décisions journalisées, PAS le compte. Le titre et le texte du panneau
      doivent le dire ; `fiable: false` est posé mais le libellé induit encore en erreur.
- [ ] **P2 — La boucle de réconciliation n'enregistre qu'une partie des achats.** Cause
      racine de l'incomplétude du journal. À trouver dans `live_journal` / la boucle, pas
      en aval. Tant que ce n'est pas fait, tout nouvel achat creuse l'écart.

## 🟢 Écarté volontairement (avec justification)
- **FinRL / RL profond** : multiplie les degrés de liberté là où le problème est le manque de
  preuve (DSR ≈ 0). Le RL brille quand les données sont abondantes et le signal net.
- **QRL** : aucun apport identifiable. Complexité visible, gain non mesurable.
- **TA-Lib** : doublon de `quant/metrics.py`, qui est en stdlib pure — qualité qu'on perdrait.
- **WebSocket / Redis Pub-Sub** : le système rééquilibre une fois par jour. Une architecture
  événementielle ajouterait un mode de panne permanent pour une information inutilisée.

## 🔧 Dette d'architecture — levée le 2026-08-25 (ADR-0038)
- [x] **`preset_backtest.py` découpé** : 793 l. / 5 fonctions > 50 → 7 modules, le plus gros à 227.
      Équivalence **bit-à-bit** vérifiée sur 10 configurations. Verrou anti-re-dérive :
      `tests/backtest/test_preset_architecture.py`. **Débloque les trois chantiers ci-dessous**,
      qui butaient tous sur le même hook `file_guard`.
- [ ] **P1 — Brancher le rolling universe** (`preset_helpers.select_rolling_universe`, écrit et
      testé) dans `preset_core.univers_backtest`, derrière un flag **par défaut à False**.
      ⚠️ **Mesurer en PROSPECTIF** (sélection à `t`, rendement `t → t+step`) : la mesure
      rétrospective fabrique un Sharpe de +6,8 sur une marche aléatoire pure (cf. journal (12)).
      **Contrôle obligatoire avant toute conclusion : Sharpe sur bruit pur ≈ 0.**

## 🔴 P0 — satellite actions vide : CAUSE TROUVÉE ET CORRIGÉE (2026-08-26, ADR-0045)
- [x] **Le repli sans score qualité prenait les 12 premiers symboles du DICTIONNAIRE.**
      `make live` tourne en mode léger, qui coupe `fundamentals` → `quality` toujours vide en
      exécution. `mkt` (l'indice des portes régime/ampleur) était la moyenne de ces 12 noms
      arbitraires → portes à zéro → exposition brute nulle. Corrigé : repli par MOMENTUM
      (`_price_universe`, aligné par date, sans fondamentaux).
- [x] **L'univers de PRODUCTION était classé sur le momentum de 2015** (2026-08-27, ADR-0046).
      `_price_universe` mesure au DÉBUT de la fenêtre (`s0 = 120` sur 2762 barres) — correct en
      backtest (anti-fuite #2), absurde en production. Titres effondrés depuis 2015 retenus →
      drawdown du panier > 15 % → porte de régime à zéro, pendant que la porte d'AMPLEUR voyait
      100 % du même univers au-dessus de sa MM200. Corrigé par `au_dernier_point=True` sur le
      seul chemin production. Au passage : garde d'indice de `momentum_rank` `> s0` → `>= s0`,
      sans quoi le repli momentum retombait sur l'ordre du dictionnaire au dernier point.
- [x] **Le diagnostic chiffre la porte de régime** (ADR-0047) : drawdown, recul du pic, niveau
      vs MM200, pente 20 j. Trois hypothèses fausses ont été émises faute de cette ligne.
- [ ] **À VÉRIFIER AU PROCHAIN RUN** : `régime` doit cesser d'être à 0,000. Le correctif ferme
      un défaut sans ambiguïté, mais qu'il suffise doit venir de la mesure, pas d'une prédiction.
- [x] **TRANCHÉ le 27/08 par la mesure : `fundamentals` SORT de `_LITE_SKIP`.** Même
      capital, même minute — mode léger : 0 scoré, régime 0,000, satellite VIDE ; mode
      complet : 12 actions réelles, 75 720 $ alloués. Ce n'était pas une section « non
      essentielle », elle décidait de l'univers. Dégradation gracieuse en cas de panne
      réseau (retour au momentum). Échappatoire `QUANT_LIVE_LITE_SKIP_FUNDAMENTALS=1`.
- [x] **Liquidation crypto bloquée par le calendrier ACTIONS** (`AAVEUSD` reporté chaque
      nuit). Toute liquidation hors-univers était classée « equity » (`{"o": None}` →
      défaut). Corrigé par `routing.classe_actif`.
- [ ] **P1 — `mkt` ne mesure pas le marché.** Deux défauts distincts, tous deux confirmés
      par la sortie du 27/08 (indice 52 % au-dessus de sa MM200 ET −23,8 % de drawdown) :
      (a) `A.mean(axis=0)` est la moyenne du panier SÉLECTIONNÉ, donc la porte de régime lit
      sa propre sélection — plus la sélection est agressive, plus la porte se ferme ;
      (b) c'est une moyenne de PRIX BRUTS : un titre à 500 $ y pèse 25 fois un titre à 20 $,
      alors qu'un indice se construit sur des séries normalisées ou des rendements.
      ⚠️ Corriger change ce que la porte MESURE, donc les résultats de backtest → passer par
      le labo, ne PAS livrer à l'aveugle.
- [ ] **P1 — Décider : les autres sections de `_LITE_SKIP` ?** Le repli momentum
      rend la production correcte, mais l'univers reste sélectionné par momentum et non par
      qualité — ce n'est pas ce que le design prévoyait. Arbitrage justesse du signal vs durée
      du snapshot, à trancher explicitement plutôt que par effet de bord.
- [x] **Cron : TRANCHÉ le 27/08 — 22h05, donc crypto automatique, actions manuelles.**
      La machine n'est allumée que vers 22h, or la clôture NYSE tombe à 22h00 pile
      (`_FERMETURE = 16:00 ET`, vérifié sur le code). Les actions seront donc reportées
      chaque jour ; 8 des 9 positions étant du crypto, l'automatisation garde l'essentiel.
      L'heure du script est désormais configurable (`QUANT_LIVE_HOUR`), et le récapitulatif
      des ordres reportés ne ment plus : il disait « ils partiront à la prochaine séance »,
      ce qui est FAUX avec un planning hors séance — rien ne les met en file d'attente.
- [ ] **P2 — Si le report des actions devient gênant** : soit allumer avant 21h un soir par
      semaine (`make live-go`), soit une file d'attente persistante des ordres reportés
      qui les rejoue à la prochaine ouverture. La file n'existe pas aujourd'hui.

## 🔧 Infrastructure — visibilité du dépôt (2026-08-27)
- [x] **`gitleaks` : `pull-requests: read` ajouté.** Le scan des PR était aveugle depuis le
      passage en privé (`403`), alors que `main` restait couvert (scan local sur push).
- [ ] **Repasser le dépôt en PUBLIC** (décidé le 27/08) — réactive GitHub Pages, figé depuis le
      26/08 05:57 (`deploy` en `404 — Ensure GitHub Pages has been enabled` : Pages est
      désactivé sur dépôt privé en plan Free). Contrôle pré-publication fait : aucun secret,
      aucun fichier sensible suivi. **Après bascule : vérifier que `pages.yml` repasse vert.**
- [ ] **Garde-fou à retenir** : un changement de visibilité modifie en SILENCE les permissions
      implicites du jeton Actions et les droits Pages. Aucune alerte, aucun code touché.

## 🏗️ Mandat & moteur déterministe (2026-08-27, ADR-0048/0049/0050)
- [x] **`packages/mandate`** — définition déclarative hashée, cosmétique hors identité, cibles
      de résultat refusées structurellement, harnais de pureté (déterminisme / environnement /
      équivalence des chemins). 50 tests.
- [x] **`packages/research/fdr.py`** — Benjamini-Hochberg. Ferme la moitié du P0
      DualMarketScreening ci-dessous (le criblage de paires doit maintenant l'APPELER).
- [ ] **P1 — Brancher le harnais de pureté sur le preset.** Le contrat est écrit et testé, il
      n'est pas encore appliqué au moteur réel. PR dédiée : elle touche du code de production
      stabilisé le 27/08, et son contrôle d'équivalence backtest/production est le vrai livrable.
- [ ] **P1 — Faire consommer le mandat par `preset_latest_weights`.** Aujourd'hui
      `config/mandats/preset_multi_actifs.json` DÉCRIT le moteur (un test vérifie qu'il ne ment
      pas) mais ne le PILOTE pas. Tant que le pilotage n'est pas fait, le lien d'audit reste
      déclaratif.
- [ ] **P2 — Graver l'identité du mandat dans le journal et les ordres.** C'est la propriété qui
      justifie tout le reste : répondre à « quelle définition exacte a produit cet ordre ».
- [ ] **P2 — Le LLM qui propose des mandats.** EN DERNIER, et seulement après les trois points
      ci-dessus : sans comptage des hypothèses il amplifie le bruit au lieu de produire du signal.

## 🗄️ Data layer élargi — avertissements avant de s'engager (2026-08-27)
- [ ] **Futures et options ne sont pas « plus de lignes »** : expiration, roll, structure par
      terme, grecques. Un contrat continu se CONSTRUIT, et la méthode de roll change
      matériellement les résultats de backtest. Autre modèle de données, pas une extension.
- [ ] **Données alternatives (sentiment, géopolitique)** : c'est là que la règle point-in-time se
      fait violer — ces séries sont presque toujours révisées et rétro-remplies. Toute nouvelle
      source doit porter un horodatage **as-of**, jamais seulement une date de valeur. La règle
      existe déjà, formalisée dans `config/macro_publication_lags.yaml`.
- [ ] **Méthode** : interface universelle dès le départ, couverture élargie UNE classe d'actifs à
      la fois, chacune passant `make contracts` et `make audit`.

## 🧪 Spec utilisateur du 01/09 — 4 modules livrés en SHADOW
Tous à poids capital ZÉRO. Aucun appelant en production ; les brancher est une décision
explicite, module par module, avec mesure.
- [x] **M2 `risk/ddm`** — machine à états DD0/DD1/DD2, remontée asymétrique, sizing par R.
      Complète `convex_drawdown_scaler` (continu sur le drawdown) sans le remplacer.
- [x] **M2.4 `risk/disjoncteur`** — coupe-circuit journalier. Compte le LATENT, et le verrou
      ne se lève pas sur un rebond intrajournalier.
- [x] **M3 `execution/frictions`** — commission / spread / slippage SÉPARÉS (là où
      `CostModel` agrège en bps) + règle d'inhibition à 3× les frictions.
- [x] **M1 `indicators/market_structure`** — extrêmes protégés, échec d'enchère, tendance
      par pivots confirmés, confluence MTF, POC approché. Point-in-time vérifié par test.
- [x] **M4 `research/protocole_oos`** — partition chronologique 60/40, parcimonie ≤ 3
      paramètres, PORTE de déploiement par le DSR. Couche mince sur `portfolio/psr` et
      `research/ledger` — rien de réimplémenté.

### Réserves écrites, à ne pas perdre
- [ ] **M1 est une lecture INTRADAY appliquée à des barres QUOTIDIENNES.** Les primitives
      sont correctes et agnostiques à l'unité de temps, mais l'absorption que vise la spec
      (mèche + volume comme trace de flux institutionnel) ne se lit pas sur du quotidien.
      Pouvoir prédictif NON ÉTABLI à cette fréquence — à mesurer avant tout branchement.
- [ ] **Le DDM ne crée aucun avantage.** Il lisse la courbe et réduit le risque de ruine ;
      à profit factor 1,01 l'espérance par unité de risque est inchangée.
- [ ] **« DSR > 95 % » est une PORTE, jamais une cible.** `n_essais` vient du ledger et
      n'est jamais fourni par l'appelant : sans ça, on contourne l'instrument même censé
      pénaliser la recherche. Cohérent avec ADR-0050 et le refus des cibles de résultat
      dans le schéma de mandat.
- [ ] **P1 — mesurer avant de brancher quoi que ce soit.** Chaque module doit passer le
      gate 4 étages sur données réelles. Un module SHADOW qui passe en production sans
      mesure est un finding P0 selon `vault/15_CERTIFICATION.md`.

## 🩹 Intégrité des séries — corrigé le 01/09
- [x] **Un NaN se propageait EN SILENCE jusqu'aux métriques publiées.** La CI est passée
      du vert au rouge sur un code IDENTIQUE (`assert nan <= nan`, `assert nan > 0`) :
      un téléchargement réseau incomplet laissait un point non fini dans une courbe.
      Amplification par `mc_projection`, qui rééchantillonne AVEC REMISE — un point sur
      2760 apparaissait dans la quasi-totalité des 1000 trajectoires et `cumprod` le
      propageait, mettant les cinq percentiles à `nan`.
      `packages/portfolio/integrite` : on ne remplace jamais un NaN par une valeur
      inventée, on le COMPTE, on le DIT, et on calcule sur ce qui existe.
      Courbe d'equity → TRONQUÉE (recoller fabriquerait un rendement enjambant le trou) ;
      vivier de rendements → FILTRÉ (un rendement inobservable n'est pas dans l'échantillon).
      Benchmarks tronqués ENSEMBLE : couper la seule série fautive désalignerait le graphe
      et rendrait la comparaison fausse tout en restant lisible.
- [x] **Le garde lui-même tombait sur le type qu'il protégeait** (correctif `4a09a3f`).
      `x or []` teste la VÉRITÉ de l'objet : sur un ndarray de plus d'un élément, Python
      lève « truth value ambiguous » avant toute analyse. Or `returns_from_equity` renvoie
      un ndarray que `snapshot.py` passe directement à `mc_projection` → 9 tests rouges.
      Second coût, plus instructif que le premier : la suite est passée de 7 à 38 minutes,
      parce que `lru_cache` NE MÉMORISE PAS UNE EXCEPTION — chaque test reconstruisait le
      snapshot entier. Une exception dans une fonction cachée ne coûte pas un test, elle
      coûte N constructions.
      **Règle de méthode** : sur une séquence, le seul test permis est `is None`. Toute
      autre forme de vérité (`if not x`, `x or []`) est un piège dès qu'un ndarray peut
      arriver — et dans ce dépôt il arrive presque toujours.

## 🩹 Fragilité des trades — mesurée et corrigée le 01/09 (ADR-0051)
- [x] **Cinq trades sur 477 séparaient le système gagnant du perdant.** Profit factor privé des
      cinq meilleurs : 0,89. La concentration n'était pas dans le signal mais dans la TAILLE des
      positions — mesuré par le t en R (2,00) contre le t en dollars (0,94). Cause : `room`
      tronquait les lignes, donc la taille dépendait de combien le carnet était plein ce jour-là.
      Corrigé par `risque_par_trade = 0,005` en production ; PF-5 passe à 1,15.
- [x] **`$VIX: possibly delisted` à chaque build.** `VIX` est un nom de base, pas un ticker Yahoo.
      Risque réel : la collision silencieuse (un small-cap nommé `DJI` lu comme le Dow).
- [ ] **P1 — Le gain de Sharpe n'est PAS démontré** (0,52 → 0,66, p = 0,59) et le net baisse de
      29 %. Réévaluer après ~200 trades supplémentaires en paper. Ne pas affiner la fraction de
      risque entre-temps : sur 11 ans ce serait de l'ajustement a posteriori (ADR-0050).
- [ ] **P2 — La concentration reste mesurée en dollars ET en R.** `couverture_R_pct` vaut 100 %
      aujourd'hui ; si un jour elle tombe sous 90 %, le panneau dit UNCALIBRATED — vérifier que
      le ledger continue de remplir `r_multiple`.

## 🩹 Gestion de sortie et reproductibilité — 02/09 (ADR-0052)
- [x] **Le stop suiveur coupait les gagnants.** `trail_atr` 5 → 0 en production : gagne sur
      payoff, marge, Sharpe, DSR, espérance, net, ET le maxDD s'améliore (−27,8 % vs −29,1 %).
- [x] **Empreinte du jeu de données** sur les trois bancs. Même config, Sharpe 0,65 puis 0,38 à
      un jour d'écart, sur un appel identique au caractère près. Deux runs ne se comparent que si
      l'empreinte l'est.
- [ ] **P1 — Identifier la cause exacte de l'écart 0,65 → 0,38.** Hypothèse du repli VIX émise
      puis NON confirmée (« VIX RÉEL » au 02/09). Reste le jour de données ajouté. Tant que ce
      n'est pas compris, aucune comparaison entre runs de dates différentes n'est valide.
- [ ] **P2 — Ne PAS explorer l'interaction (sans suiveur × rr 9).** Le classement des cibles
      s'est inversé entre deux jeux : c'est du bruit. Chaque essai relève le seuil du DSR.

## 🟡 Screening-Trading — reste ouvert (2026-08-22)
- [ ] **Câbler `impact.py` / `almgren_chriss.py` à l'exécution réelle** — écrits et testés, non
      branchés : les coûts d'impact sont ignorés au dimensionnement. (Débloqué par ADR-0038.)
- [x] **Débruitage RMT — TRANCHÉ le 26/08 (ADR-0039), sans changement de défaut.** Sur données
      réelles k médian = 1, donc le diagnostic dit « préférer l'inverse-vol » — mais la mesure
      rejette le RMT (ΔSharpe −0,07). Avec l'erreur-type, la contradiction se dissout : −0,07 est
      **indiscernable de zéro**. Ni le diagnostic ni la mesure ne justifient de bouger. On garde
      l'ERC et on documente.
- [x] **TRANCHÉ le 31/08 : allonger la fenêtre du labo NE MARCHERAIT PAS.** J'avais proposé
      de raccourcir le pas (21 → 5/10) pour multiplier les observations. C'est faux deux fois.
      (a) Changer le pas change la STRATÉGIE — hebdomadaire au lieu de mensuel quadruple le
      turnover. (b) Surtout, le seuil est INVARIANT à la fréquence : Z·sqrt(var·ppa) avec
      var ∝ 1/n et n = années × ppa → ppa s'annule. Mesuré : 11 ans donnent ±0,118 en
      quotidien COMME en mensuel. Les deux vrais leviers : l'HISTORIQUE (20 ans → ±0,087 ;
      il en faudrait ~60 pour atteindre 0,05) et la CORRÉLATION entre variantes (rho 0,95 →
      0,99 fait passer de ±0,263 à ±0,118) — d'où le protocole apparié, une seule chose
      changée à la fois. Le labo publie désormais ces deux tableaux.
- [x] **P1 — FERMÉ (2026-09-07) : le seuil n'est plus un nombre choisi.** Ni 0,05 ni 0,12 :
      le seuil de promotion DEVIENT la résolution mesurée de l'échantillon
      (`sharpe_diff.seuil_detectable`), avec le plancher d'exécution 0,05 comme borne basse.
      Il se resserre seul quand l'historique s'allonge — 11 ans → +0,118 · 20 → +0,087 ·
      60 → +0,051, soit exactement les valeurs relevées le 31/08. Verdict `🟡 INDISTINCT`
      ajouté pour l'entre-deux (ni promu ni rejeté : la donnée ne tranche pas).
      Garde-fou : `tests/research/test_seuil_de_promotion.py`.
- [ ] **VIX : provenance publiée (31/08).** `vix`, `vix_playbook` et `vix_series` étaient
      publiés sans distinguer une série RÉELLE d'une série `_vix_series()` FABRIQUÉE — le
      graphe s'en protégeait déjà, pas le KPI. Corrigé : `vix_reel` publié, `null` +
      UNCALIBRATED quand aucune série fraîche. **Reste à vérifier chez l'utilisateur** si
      `^VIX` remonte réellement (le warning ne concerne que l'alias de repli `VIX`).
- [ ] **P1 — ancien libellé (à ignorer) : Allonger la fenêtre du labo.** Le gate promeut à +0,05 alors que 126 pas ne résolvent
      que ~+0,14 (ADR-0039) : à ce seuil, promouvoir ou rejeter est un tirage au sort. C'est le
      vrai blocage de la recherche d'alpha — pas le manque de leviers à tester, mais l'incapacité
      à distinguer un levier réel du bruit. Piste : pas plus court (step 5 ou 10 au lieu de 21)
      pour multiplier les observations à fenêtre calendaire égale.
- [ ] **Capitaux employés moyens** : le code sait moyenner, mais les fournisseurs ne remontent pas
      la période précédente. Câbler l'historique trimestriel pour que le correctif prenne effet.
- [ ] **Biais du survivant : élargir la liste des délistés, pas relancer le test.** 0 sur 8
      sélectionné → le test ne mesure rien, et le relancer ne changera pas ça. Il faut des
      délistés qui auraient été BIEN CLASSÉS avant leur disparition.
- [ ] **Séries macro à ajouter** (identifiants à vérifier depuis le Mac, FRED joignable) :
      conditions financières NFCI, anticipations d'inflation 5a5a, dollar index, inscriptions
      hebdomadaires au chômage (seul indicateur haute fréquence), spread investment grade.
- [x] **Accessibilité — FERMÉ (2026-09-07)** : les 26 pages du site sont passées en langage
      courant, à contenu strictement égal (chaque chiffre, seuil et réserve conservé). `/ml`,
      `/conviction` et `/portfolio` traités à la suite 32 ; les treize dernières à la suite 33.
      `accueil` volontairement laissée telle quelle : sa prose était déjà claire. Forme retenue :
      la question posée avant la réponse technique, et l'explication au survol (`Col.title` sur
      `SortableTable`) plutôt qu'en note de bas de page.
- [x] **Lisibilité mobile — FERMÉ (2026-09-07, mesuré)** : 365 éléments étaient hors écran et
      injoignables à 390 px (pire cas `/fundamentals`, +492 px, la moitié de ses colonnes) ;
      0 après correction, témoin à l'ancien CSS rejoué pour valider l'audit. Cause : la
      rencontre de `overflow-x:clip` (garde-fou) et de quatorze tableaux sans conteneur
      défilable. Correction structurelle, pas au cas par cas : sur mobile tout `<table>`
      défile dans lui-même. Bulles d'aide et encoche en paysage corrigées aussi.
      Garde-fou : `tests/web/test_mobile_pas_de_hors_ecran.py`.
- [ ] **P2 — Mobile : passer l'audit de débordement en CI.** L'audit de ce jour tournait avec
      Playwright installé à la volée puis désinstallé. Le figer (navigateur déjà présent dans
      l'image) donnerait la mesure à chaque PR au lieu d'une fois. Le test actuel garde la
      RÈGLE CSS ; il ne mesure pas les pixels.
- [ ] **P2 — `/universe` en 5 colonnes fixes sur mobile** : la grille se rétracte au lieu de
      déborder (donc rien d'injoignable, vérifié), mais « Nom » et « Secteur » y sont tronqués
      à quelques caractères. À repenser en deux lignes par actif sous 640 px.
- [x] **Fenêtres du dashboard — FERMÉ (2026-09-07)** : chacun des trois « gain / risque »
      énonce désormais sa période (tuiles héros = période choisie, avec les dates ; bandeau
      honnêteté = tout l'historique ; socle+stratégie = tout l'historique aussi).
- [x] **Bloc décision sur le screener — FERMÉ (2026-09-07)** : jointure extraite dans
      `apps/web/lib/verdicts.ts`, MÊME moteur `decide()` que la fiche (pas de variante liste
      plus permissive). Colonne « ce qu'on en conclut » + bloc complet dans la modale.
- [x] **Registre d'essais complet — FERMÉ (2026-09-07)** : `/api/failures` publie `par_statut`
      et `n_total` ; `/methode` affiche les quatre statuts. `items` reste les seuls rejets —
      /echecs l'affiche sans filtrer, y glisser une idée retenue la dirait échouée.

## 🖥️ Portabilité matérielle (2026-09-07, ADR-0079)

- [x] **Module de détection — FAIT.** `packages/common/device.py` : CUDA → MPS → CPU,
      `QUANT_DEVICE` pour forcer, bannière « Exécution sur : … », `params_arbres()` pour
      XGBoost/LightGBM/CatBoost, `activer_cudf()`. 20 tests, contrôle négatif vérifié.
- [x] **P2 — Déterminisme du banc — FERMÉ (2026-09-08).** Cause isolée par la mesure :
      `GradientBoostingClassifier` sans `random_state` consomme le générateur aléatoire
      GLOBAL de numpy pour départager les égalités entre découpes d'arbre. Graine posée
      sur l'ESTIMATEUR (`SklearnModel.GRAINE`), jamais par `np.random.seed()`. Trois
      exécutions de `demo_ml.py` désormais identiques au caractère près.
      Garde-fou : `tests/ml/test_determinisme.py`.
- [x] **P1 — VALIDÉ SUR DONNÉES RÉELLES (2026-09-08, six lancements)** — verdicts :
      · `cvar_optimize` : **REJETÉ** hors échantillon (ADR-0087). Premier en échantillon,
        DERNIER hors échantillon, seul à rendement négatif (−5,1 % contre +12,3 % pour HRP).
        Cause : le CVaR 95 % sur 252 jours s'estime sur ~13 points de queue. Inscrit au
        registre des négatifs. HRP reste le meilleur allocateur du projet.
      · `generateur_signaux` : **VALIDÉ**. 96 candidats → 24 essais distincts → 13 retenus
        par le seuil du blueprint NVIDIA → **0 promu** après Benjamini-Hochberg. Le registre
        ne se remplit pas de bruit.
      · `anomalies_panel` : **VALIDÉ**. 5 séries cassées et 7 figées trouvées, toutes des
        paires `/USDC`. Actionnable immédiatement.
      · `ml/explication` : **VALIDÉ** mécaniquement (mesuré EN échantillon : dit ce que le
        modèle utilise, pas ce qui généralise).
- [ ] **P1 — Réparer la source des paires `/USDC`** (trouvé le 08/09) : UNI, ARB, OP, STX,
      TON avec des sauts jusqu'à +1 573 987 % (prix de la veille faux, proche de zéro) ;
      SHIB figé 675 séances sur 1499, ARB 595. Écarter de l'univers tant que ce n'est pas
      réparé — ces séries faussent tout optimiseur de risque.
      **Instrument livré le 09/09** : `make diag-source-crypto` confronte chaque série de
      `crypto.db` à une référence indépendante (Binance klines, sans clé) et sépare les
      quatre causes, qui appellent des gestes OPPOSÉS : collision de ticker (forcer le bon
      symbole), flux arrêté (retirer), précision (changer de source), conforme (l'anomalie
      est réelle). Sans référence il rend « NON VÉRIFIABLE » plutôt qu'un verdict inventé.
      `make ingest-crypto` liste désormais chaque base sans données au lieu de les avaler
      en silence — c'est ce silence qui a laissé douze séries pourrir sans alerte.
      **DIAGNOSTIC PASSÉ SUR LE VPS le 09/09 — causes établies** (ADR-0089, ADR-0090) :
      · 5 collisions de ticker confirmées deux fois chacune (corrélation ≈ 0 contre
        Binance, ET date de début antérieure à l'existence du jeton — la série Yahoo
        d'`ARB-USD` commence en 2017, Arbitrum date de 2023) : TON, UNI, APT, ARB, STX.
        **Réparé** : `SOURCE_FORCEE` route ces cinq bases vers Binance (historique
        paginé, `packages/data/crypto_binance.py`), avec effacement annoncé des lignes
        de l'homonyme — sinon la série serait cousue de deux actifs.
      · SHIB n'est PAS un flux arrêté : corr +0,80 (le bon jeton) mais **3 % de clôtures
        distinctes** — un cours à 0,00001 $ arrondi à six décimales. Cause = précision de
        la source. **Non réparé** : demande une source à plus de décimales pour les
        jetons sub-centimes. Nouveau P2 ci-dessous.
      · **52 bases sur 102 n'avaient jamais été ingérées** — défaut `--top 50` contre un
        univers de 102. **Réparé** : `--top 0` = tout l'univers, par défaut.
      **VÉRIFIÉ LE 09/09 (2ᵉ passage)** : les cinq ressortent **CONFORMES, corr +1,00**,
      et leur début de série change du tout au tout — `ARB` de 2017-11 (impossible) à
      2023-03, `APT` de 2021-11 à 2022-10. Réparation confirmée par une mesure
      indépendante de celle qui l'avait motivée. L'univers réel passe de 774 à **823
      actifs, dont 97 cryptos au lieu de 48** (ADR-0094).
      **2ᵉ LOT VÉRIFIÉ (09/09)** : SUI, TIA, JUP, STRK, APE ressortent CONFORMES à leur
      tour, corr +1,00, avec des dates de naissance redevenues plausibles (`JUP` passe de
      2017-11 à 2024-01). Dix bases réparées et vérifiées sur dix.
      **3ᵉ ET 4ᵉ LOTS ajoutés à `SOURCE_FORCEE`, à vérifier au prochain passage** :
      · collisions visibles seulement grâce à la référence PAGINÉE — IMX, GRT, GMX, GMT
        (leur série s'arrête avant 2024, donc sans recouvrement avec l'ancienne fenêtre) ;
      · `OP` : **SÉRIE RECOLLÉE** — corr −0,00 sur 1559 j mais +1,00 sur les 640 derniers.
        Ticker réattribué : récent juste, ancien étranger (ADR-0096) ;
      · source inadéquate — SHIB, BONK, XEC, FLOKI, COMP (arrondi : 3 % à 17 % de
        clôtures distinctes) et PEPE (Yahoo ne rend que 119 barres). **Prédiction
        falsifiable** : si l'arrondi vient de Yahoo, la part de clôtures distinctes doit
        bondir au prochain passage ; s'il tient au pas de cotation du jeton, non.
      **VÉRIFIÉ LE 09/09, la prédiction tenait** (ADR-0097) : SHIB 3 % → **63 %**,
      BONK 4 % → 84 %, XEC 10 % → 83 %, FLOKI 14 % → 95 %, COMP 17 % → 89 %,
      GMX 32 % → 84 %. Et les plages figées s'effondrent avec : SHIB 61 séances → 3,
      GMX 256 → 2. Ce n'étaient pas des flux morts, c'était la source qui décrochait —
      le geste qu'on aurait fait sans mesurer (retirer les séries) était le mauvais.
      **P1 CLOS.** 102 bases sur 102 ingérées, 21 sources forcées et vérifiées,
      92 séries CONFORMES. `RPL` ajouté au 5ᵉ lot sur la même signature (figée 24,
      corr +1,00) avec la même prédiction — à confirmer au prochain passage.
- [ ] **P2 — Trois séries sans référence indépendante** : OKB, LEO, KAS, que Binance ne
      cote pas. Leur forme est saine (100 % de clôtures distinctes, à jour), mais rien
      ne les confronte. On le DIT au lieu de les déclarer conformes par défaut. Ajouter
      une seconde référence (CoinGecko, avec résolution du symbole par son endpoint de
      recherche plutôt qu'une table écrite à la main) — pour trois bases sur 102, ce
      n'est pas un préalable.
- [ ] **P1 — Refaire les mesures d'allocation sur l'univers assaini** (09/09).
      ADR-0087 (rejet du Mean-CVaR) et la validation de HRP portaient sur 774 actifs dont
      48 cryptos, avec cinq séries décrivant d'AUTRES jetons et six rongées par l'arrondi.
      Le panneau fait maintenant **823 actifs dont 97 cryptos**, tous confrontés à une
      référence. Le rejet du Mean-CVaR ne devrait pas bouger — sa cause est le manque
      d'observations de queue, que l'élargissement aggrave — mais **ce raisonnement n'est
      pas une mesure**. `make valider-nouveautes` refait la comparaison ET applique pour
      la première fois le seuil calibré à 24.
      **FAIT LE 09/09 — et le verdict s'inverse (ADR-0098).** Le seuil tient sa promesse :
      **45 actifs signalés sur 826, soit 5,4 % contre 5,5 % prédits**, zéro série cassée
      (contre 5), une seule figée (contre 7). Mais hors échantillon, le Mean-CVaR
      plafonné passe de DERNIER (2,91 % de CVaR, −5,1 %) à PREMIER (1,04 %, +9,7 %),
      HRP restant stable (1,54 → 1,51 %). **Le rejet d'ADR-0087 est ANNULÉ** — sa mesure
      portait sur cinq séries décrivant d'autres jetons. Ligne datée au registre,
      `allocation_mean_cvar` repasse en `en_test`.
- [ ] **P1 — Trancher le Mean-CVaR avec un protocole qui PEUT conclure** (09/09).
      Le nouveau résultat ne valide rien : cinq fenêtres hors échantillon donnent une
      p-valeur minimale de **2/2⁵ = 0,0625**. Même en gagnant les cinq, le test des
      signes ne peut pas descendre sous 5 % — sans puissance par construction, un fait
      de forme connaissable AVANT de regarder les données. Instrument livré
      (`packages/portfolio/duel_hors_echantillon.py` : duel apparié, plancher de
      puissance et recouvrement imprimés). **RESTE** : `make valider-nouveautes
      ARGS="--pas 21"` (seize fenêtres au lieu de cinq), puis lire le duel apparié —
      pas la moyenne. Deux réserves à porter : le Mean-CVaR sans plafond met 63,7 % sur
      une seule ligne (AGG), et l'allocation gagnante est à 66 % en ETF obligataires —
      vérifier qu'on mesure un allocateur et non la performance des obligations sur
      cette fenêtre-là.
      **RUN À 16 FENÊTRES FAIT LE 09/09 (ADR-0099)** : le Mean-CVaR bat HRP **15 fois
      sur 16** (p = 0,001, écart médian −0,39 %), min-variance 2/16, ERC et équipondéré
      0/16. Le protocole peut conclure. Deux défauts d'affichage corrigés — une coche
      « concluant » s'affichait aussi sur les PERDANTS (le test des signes est
      bilatéral), et le plancher de puissance non nul s'imprimait « 0.0000 ».
      **MAIS LA LIMITE A CHANGÉ DE NATURE** : à `--pas 21` le recouvrement des périodes
      d'ajustement monte à **92 %**. Le test reste valide comme comparaison de deux
      PORTEFEUILLES sur seize périodes disjointes, faible comme comparaison de deux
      MÉTHODES. Avec 601 dates communes, un test à fenêtres d'ajustement disjointes n'en
      donnerait qu'une : **on ne peut pas acheter de l'indépendance qu'on n'a pas.**
- [ ] **P1 — Allonger l'historique commun avant de conclure sur un allocateur** (09/09).
      601 dates communes sur 802 jours de bourse : la grille exige que **tous** les 734
      actifs cotent le même jour, ce qui coûte un quart des séances et borne le test hors
      échantillon à ~1,7 an. Deux pistes, à mesurer avant de choisir : assouplir
      l'intersection (masquer par date plutôt qu'exiger la ligne pleine), ou allonger la
      profondeur d'ingestion. C'est cette contrainte, pas le réglage `--pas`, qui empêche
      aujourd'hui de trancher sur une MÉTHODE d'allocation.
- [ ] **P0 — AUCUN rebalancement planifié sur le VPS** (mesuré le 10/09, ADR-0104).
      `crontab -l` → « no crontab for ubuntu ». Le portefeuille ne bouge que sur
      lancement manuel : cela explique d'un coup les 5 décisions de sortie en 63 jours,
      la détention médiane de 0,1 jour, et la poche QQQ montée à 69 % sans allègement.
      **NON ÉTABLI** : le journal peut venir d'une autre machine (`journal-pull`,
      launchd sur le Mac mini). L'absence de cron ici ne prouve pas que rien ne tourne
      nulle part.
      **À FAIRE, dans cet ordre** :
      1. `make verify-journal` **sur la machine qui porte le planificateur** (le
         Mac mini si c'est lui). Le contrôle sait enfin répondre sur Linux comme sur
         macOS — il renvoyait « ✅ cron actif » sur toute machine Linux jusqu'au 10/09.
      2. `make live-cron-install` sur la machine choisie — **il échouait jusqu'au 10/09**
         sur toute machine sans crontab préexistant, sans le moindre message
         (ADR-0105) : `grep` vide + `set -euo pipefail` tuaient le sous-shell avant
         l'écriture. Corrigé et testé en exécutant vraiment le script. Puis
         `make verify-journal` pour confirmer — **après `make sync`** : le premier
         passage du 10/09 tournait encore l'ancien contrôle et concluait « ✅ cron
         actif » sur un VPS sans crontab.
      3. Laisser tourner une semaine AVANT de rejuger quoi que ce soit sur les sorties :
         les cinq décisions mesurées ne décrivent pas une stratégie, elles décrivent
         cinq lancements manuels.
- [ ] **P0 — L'allocation franchit la politique de risque, tous les jours** (ADR-0111).
      Post-mortems des 05, 07, 08 et 09/09 : `risk_limits_ok: false`, `n_breaches: 3`.
      Le secteur « Actions diverses » pèse **47,5 % contre un plafond de 40 %**
      (`config/risk.yaml`), et le cœur `QQQ` **50 % contre un plafond de nom à 20 %**
      (`packages/risk/limits.py`). Ce sont les poids du portefeuille MODÈLE, pas une
      somme de lots journal : le sur-comptage d'ADR-0109 n'explique rien ici.
      **L'arbitrage, et il t'appartient** : soit la politique de risque reconnaît qu'un
      cœur indiciel n'est pas une ligne comme une autre (plafond de nom séparé pour les
      ETF larges — `max_index` existe déjà, à 60 %), soit le cœur descend sous 20 %.
      En l'état, deux documents du projet se contredisent sur ce que le système doit
      faire. Le rebalancement automatique applique l'allocation telle quelle.
- [x] **P0 — ANNULÉ : les 69 % de QQQ n'existaient pas** (ADR-0109). Le courtier détient
      **43 562 $**, soit 43,3 % du compte, pour une cible à 44,9 % : la position est
      légèrement SOUS sa cible, l'écart est un ACHAT de 1 652 $. Le chiffre de 69 %
      venait du JOURNAL, qui compte trois lots QQQ ouverts (42 862 + 25 977 + 617) là où
      le courtier n'en détient qu'un — **25 894 $ de fantômes**, lots fermés chez le
      courtier et jamais fermés au journal. Le journal n'est pas la source de vérité des
      positions ; il reste celle des DÉCISIONS. Ancien libellé conservé ci-dessous pour
      la trace.
- [ ] ~~**P0 — 69 % du portefeuille sur UN SEUL ETF** (mesuré le 10/09, ADR-0102/0103).~~
      Trois lots de QQQ pèsent ≈ 69 500 $ sur ≈ 100 000 $. Un total qui oscille de 101 k
      à 100,4 k suit d'abord CELA : ±0,9 % sur QQQ font ±0,6 % sur le compte.
      **CORRECTION du 10/09 (ADR-0103)** : j'avais écrit « pourquoi le rebalancement ne
      ramène-t-il pas cette ligne à sa cible ? ». La question était mal posée — **la
      CIBLE elle-même est ≈ 50 %**. Sur un portefeuille neuf de 10 000 $, l'allocateur
      vise QQQ à 5 000 $, soit 54 % du capital réellement alloué, le reste étant
      35 satellites à ~3 % chacun. C'est un cœur-satellite assumé, pas une panne : la
      moitié du compte EST un ETF Nasdaq, et il bouge comme lui. Le yo-yo est
      structurel et voulu.
      **RESTE À TRANCHER — une décision, pas un correctif** : ce poids de cœur est-il
      celui que tu veux ? À 50 % de cœur, le compte suivra le Nasdaq quoi qu'il arrive
      aux 35 satellites. Le seul écart réellement anormal est **69 % constaté contre
      ≈ 54 % visés**, soit ~15 points de surpoids à alléger : `make live` (positions
      RÉELLES, aucun ordre) dit si l'ordre de vente est bien émis.
- [ ] **P0 — Lots crypto incohérents au journal** (mesuré le 10/09) : `BCH` affiche
      −2 509 $ de PV latente sur une position de 512 $, `ETH` −619 $ sur 6 $. Une
      position longue ne peut pas perdre plus qu'elle ne vaut : `avg_price` ou `qty` est
      faux. `make diag-pv-latente` les isole désormais. C'est la P0 de réconciliation du
      journal, qui attend toujours d'être passée.
- [ ] **P0 — Le yo-yo de la PV latente : mesurer, puis décider** (posé le 10/09).
      Symptôme rapporté : total oscillant de 101 k à 100,4 k, PV latente impossible à
      sécuriser. Mécanisme lu dans le code (ADR-0101) : la production n'a ni objectif de
      gain ni stop, sa seule sortie est le rebalancement, et la **bande d'inaction vaut
      ≈ 505 $ par ligne** (0,5 % du capital). Sous cette bande, une ligne ne peut PAS
      être allégée — sa plus-value ne peut que revenir.
      **ÉTAPE 1 FAITE le 10/09** — et elle renvoie ailleurs : frais + slippage = 0,00 $,
      donc pas de friction ; 5 décisions de sortie en 63 jours seulement ; et 69 % du
      portefeuille sur QQQ. Le yo-yo mesuré n'est pas un problème de sortie, c'est une
      concentration. Voir les deux P0 ci-dessus.
      **Commandes** : `make diag-pv-latente
      ARGS="--capital <ton capital>"` puis `make turnover-audit`. Le premier chiffre le
      yo-yo sur les positions VIVANTES (pic, PV du jour, rendu, et combien de lignes
      dorment sous la bande) ; le second donne le coût des allers-retours sur les lots
      clos.
      **ÉTAPE 2, seulement ensuite** : choisir entre (a) resserrer la bande — plus de
      prises de bénéfice mais plus de frais, à arbitrer sur le coût mesuré par
      `turnover-audit` ; (b) brancher une règle de sécurisation explicite (suiveur, ou
      allègement partiel au-delà d'un seuil de gain) — c'est un CHANGEMENT DE MOTEUR au
      sens d'ADR-0073, à valider pour lui-même ; (c) ne rien changer si le rendu mesuré
      est faible et que le yo-yo n'est que la volatilité du marché.
      **NE PAS** régler `rr` ou le suiveur de `sortie_lab` en croyant agir : ce banc
      rejoue `fast_swing_backtest`, pas le chemin de production (ADR-0073).
- [x] **P1 — TRANCHÉ le 10/09 : HRP reste en production** (ADR-0100). La période
      s'affiche : **2024-05-15 → 2026-05-19**, 336 séances — **aucun épisode de hausse
      des taux**, le krach obligataire de 2022 est hors fenêtre. Or l'allocation gagnante
      fait 63 % d'ETF obligataires, et sur le RENDEMENT le duel est indiscernable (7/16,
      p = 0,80) : l'avantage porte sur le seul risque de queue, et ce risque de queue est
      une exposition de classe d'actifs. On mesure « ces ETF ont été calmes deux ans »,
      pas « cette méthode est meilleure ». Le Mean-CVaR reste `en_test` avec sa période
      inscrite au registre ; il sera rejugé quand l'historique couvrira un choc de taux.
- [x] **P1 — Un prix périmé comptait comme un prix RÉEL** (trouvé et corrigé le 10/09).
      Le chargement ne regardait que le nombre de barres : `HYPE/USDC`, arrêtée le
      27/08/2024, figurait dans l'univers réel du 08/09/2026 — le screener pouvait la
      classer, le dimensionnement la dimensionner. `_load_prices` écarte désormais toute
      série en retard de plus de 60 jours **sur la barre la plus fraîche de l'univers**
      (pas sur la date du jour : un férié ne doit condamner personne). 5 tests.
- [x] **P2 — Les splits suspects sont qualifiés, plus listés** (10/09). `corporate_actions`
      existait depuis longtemps et n'était branché nulle part. La liste B se sépare en
      « SPLIT CONFIRMÉ (ratio + volume) » / « volume non concordant » / « inexpliqué ».
      Seule la dernière catégorie demande un œil humain.
- [ ] **P1 — Sortir de l'univers les séries PÉRIMÉES** (trouvé le 09/09) : une douzaine
      de séries s'arrêtent des années avant le reste du lot — MATIC en 2025-03 (migration
      POL), RNDR en 2024-07, FTM en 2025-01, IMX en 2022-07, GRT en 2022-04, GMX en
      2023-11, COMP en 2021-08. Rien ne cloche DANS ces séries : elles sont finies. Elles
      sortaient « CONFORMES » et peuplaient l'univers en se faisant passer pour vivantes.
      Le diagnostic les nomme désormais (verdict PÉRIMÉE, mesuré contre la barre la plus
      fraîche du lot). **Liste arrêtée au 09/09** : HYPE (retard 742 j), TON (70 j, Binance
      a cessé de coter la paire), MATIC (533 j), RNDR (779 j), FTM (603 j), GALA (52 j),
      FXS (490 j). À noter : `RENDER` est DÉJÀ dans l'univers et conforme — `RNDR` y fait
      donc doublon avec sa propre version morte.
      **RESTE** : décider migration (MATIC→POL, RNDR→RENDER, FTM→S) ou retrait, puis
      appliquer à `config/universe.yaml`. Sortir un instrument change l'ensemble
      investissable : c'est une décision, pas un correctif de données — elle t'appartient.
- [ ] **P2 — PEPE : 119 barres chez Yahoo**, sous le seuil des 250 (09/09). Seule base de
      l'univers restée muette après l'ingestion complète. Basculer en `SOURCE_FORCEE`
      vers Binance comme les collisions — à vérifier au prochain passage.
- [x] **P2 — Recalibrer `SEUIL_ECART` : CAUSE TROUVÉE, ce n'était pas le seuil** (09/09).
      430 actifs sur 774 signalés. J'avais écrit « les queues épaisses des marchés » —
      **c'était faux, et mesurable**. Sur un panneau SAIN de 774 séries synthétiques
      multi-classes, sans le moindre défaut injecté : **100 % des cryptos signalées, 0 %
      du forex**, 12 974 événements pour zéro anomalie. La coupe du jour mélangeait des
      échelles sans rapport (0,5 % / 1,5 % / 5 % par jour) : sa médiane et son MAD étaient
      dictés par la classe la plus nombreuse, et une crypto vivant sa journée ordinaire se
      retrouvait à seize écarts de cette coupe-là — signalée pour avoir été elle-même.
      **Correctif** : chaque série est divisée par sa PROPRE échelle robuste avant la
      comparaison (`echelle_par_actif`). Mesuré sur le même panneau sain : 75 actifs
      signalés → **0**, et les quinze défauts injectés (splits ×4 et ticks erronés, dans
      les trois classes) restent tous détectés. La gravité continue de se lire sur le
      rendement RÉEL : « split non ajusté » se décide à −30 % de cours, pas à trente
      unités d'écart normalisé (test dédié, vérifié par sabotage). ADR-0088.
      **CONFRONTÉ AU VRAI PANNEAU LE 09/09 — ma correction était fausse elle aussi.**
      Au seuil 8 AVEC normalisation : **57,6 %** de l'univers signalé, contre 55,6 %
      (430/774) sans elle. La normalisation **n'a pas réduit le taux réel**. Elle corrige
      un artefact démontré (le mélange d'échelles), mais ce n'était pas le facteur
      dominant : le facteur dominant est bien celui que j'avais écrit puis rayé, **les
      queues épaisses**. Un panneau gaussien ne pouvait pas trancher entre les deux
      hypothèses, puisqu'il n'a pas de queues — et j'ai conclu comme s'il le pouvait.
      Par classe à 8 : crypto 94 %, actions 65 %, forex 53 %, commodités 50 %,
      indices 24 %, ETF 11 %. La normalisation est CONSERVÉE (la statistique dit enfin
      ce qu'elle prétend dire), le seuil reste **UNCALIBRATED**.
- [ ] **P2 — Trancher `SEUIL_ECART` avec un instrument réparé** (09/09). La première
      proposition du script (24) est RETIRÉE : elle reposait sur une sensibilité
      sous-estimée par un défaut de l'instrument — l'injection tirait sa date au hasard
      et tombait une fois sur trois sur un jour NON COTÉ, où un défaut ne produit aucun
      rendement (ADR-0091). Corrigé : l'injection ne vise que des séances réellement
      cotées deux jours de suite, et le rapport publie l'effectif de chaque mesure.
      **2ᵉ PASSAGE (09/09) — l'instrument est réparé, la conclusion ne l'est pas.** Les
      sensibilités sont enfin crédibles : **100 % de détection des splits à tous les
      seuils** sans normalisation, contre 33-73 % erratiques avant. Mais la proposition
      (24) tombait sur le **plus grand seuil de la grille**, avec un score encore
      croissant : ce n'était pas un maximum, c'était le dernier point essayé (ADR-0093).
      Grille élargie à 64, avertissement explicite sur les bords, `N_INJECTIONS` 40 → 150.
      **Et le mode n'est pas tranché non plus** (ADR-0092) : à seuil 8 l'ANCIEN mode gagne
      sur les deux axes (coût 55,3 % contre 59,4 %, sensibilité 100 % contre 94 %) ; la
      normalisation ne l'emporte qu'à partir de 12, et par le seul coût. Mode et seuil
      sont couplés — trancher l'un sans l'autre, c'est choisir sur la moitié de la table.
      **TRANCHÉ LE 09/09, 3ᵉ passage (ADR-0095).** Grille élargie, instrument réparé,
      150 injections : **l'optimum est INTÉRIEUR dans les deux modes**. Maximum global à
      **24 avec normalisation** (score 0,905), devant 32 sans (0,889). Les deux questions
      se répondaient bien ensemble. **`SEUIL_ECART = 24,0` appliqué**, normalisation
      conservée : 5,5 % de l'univers signalé (45 actifs au lieu de 489), 93 % des splits
      et 99 % des ticks retrouvés, mesuré sur 138 actifs. Le prix est écrit : cinq points
      de détection des splits contre une lecture divisée par trois, et l'angle mort (un
      split ×4 sur une crypto d'échelle 5 %/jour) est **fixé par un test** qui vérifie
      aussi qu'il ressort à seuil 12 — arbitrage, pas cécité.
- [ ] **P2 — Source à plus de décimales pour les jetons sub-centimes** (trouvé le 09/09) :
      SHIB n'a que 3 % de clôtures distinctes sur 1967 barres — le bon jeton, arrondi à
      six décimales par la source. Un cours qui ne bouge qu'en marches d'escalier
      fabrique une volatilité fausse et des plages figées. Concerne aussi PEPE, BONK,
      FLOKI, XEC dès qu'ils seront ingérés. Binance rend huit décimales : vérifier si le
      passage en `SOURCE_FORCEE` suffit, AVANT d'écrire quoi que ce soit.
      **CONFIRMÉ ET ÉLARGI le 09/09** une fois l'univers complet : SHIB 3 % de clôtures
      distinctes, BONK 4 %, XEC 10 %, FLOKI 14 %, COMP 17 %, GMX 32 %. Six séries, pas
      une.
- [ ] ~~**P1 — ancien libellé : à valider sur données réelles**~~
- [ ] ~~**P2 — ancien libellé : `scripts/demo_ml.py` n'est pas déterministe.**~~ Constaté le 07/09 en cherchant à
      prouver une non-régression : deux exécutions de la MÊME version donnent des accuracies
      différentes (`GradientBoostingClassifier` sans `random_state`). Un banc dont deux runs
      ne coïncident pas ne peut servir à comparer ni deux versions, ni deux matériels — ce
      qui va précisément manquer au moment de valider la migration NVIDIA.
- [ ] **P2 — Mesurer AVANT d'installer RAPIDS.** `cudf.pandas` accélère pandas ; le temps de
      ce projet se passe surtout en lectures SQLite et en numpy. Profiler un `make daily`
      avant de conclure que le GPU aidera — et vérifier que 7 Go tiennent en VRAM (sinon
      déversement disque, qui peut être plus lent que pandas).
- [ ] **P2 — À la migration : relancer un backtest identique sur les deux machines.** Deux
      matériels ne donnent pas le bit près les mêmes flottants. Vérifier que l'écart reste
      dans le bruit AVANT de faire confiance aux chiffres de la nouvelle machine.

## 🔵 Décisions en attente de l'utilisateur
- [ ] **Bot Discord** (projet distinct) : vendre des signaux à des abonnés payants est une
      activité réglementée (conseil en investissement, agrément AMF). Décision à prendre AVANT
      de développer, pas après.
- [ ] **Nouvelles classes d'actifs** : le forex est en base mais marqué non négociable (aucun
      courtier branché) ; les dérivés demandent Grecs, surface de volatilité et échéances — une
      modélisation que l'architecture actuelle ne porte pas.

## 🎯 ALPHA — pipeline fondamental + labo (2026-08-20)
- [x] **Pipeline 4 couches livré** (`screening/alpha_pipeline.py`) : qualité → DCF avec bande de
      sensibilité → momentum → dimensionnement par budget d'ES. Entonnoir publié.
- [ ] **Brancher le pipeline sur les fondamentaux réels** (`fundamentals/fmp_provider` ou
      `sec_provider`) et le lancer sur 500+ tickers → si l'entonnoir sort < 10 lignes, élargir
      l'univers AVANT d'assouplir les seuils.
- [ ] **Ajouter actif/passif courant à `Financials`** pour rendre le quick ratio calculable
      (aujourd'hui `None`, donc exclu de la conjonction — c'est honnête mais incomplet).
- [ ] Ne PAS backtester ce pipeline tant que les fondamentaux ne sont pas point-in-time (F1/F9).

## 🎯 ALPHA — `make alpha-lab` (2026-08-20)
- [x] **Labo d'alpha livré** : 5 hypothèses pré-enregistrées + gate 4 étages + ledger.
- [ ] **CE SOIR SUR LE MAC — la commande qui répond à « où est l'alpha ? »** :
  ```bash
  git fetch origin && git reset --hard origin/main   # après merge de la PR #324
  make alpha-lab
  ```
  → me coller le tableau + le bloc VERDICT. Trois issues possibles, toutes utiles :
  1. **un candidat passe** → re-runner sur une période DISJOINTE avant toute activation ;
  2. **rien ne passe** → c'est un résultat, à publier sur `/echecs` (et cohérent avec le
     manifeste d'honnêteté : le wedge n'est pas l'alpha directionnel) ;
  3. **univers < 30 titres** → le labo refuse de conclure, il faut élargir la base.
- [ ] Après la vague 1 (prix bruts + délistés) : **re-runner alpha-lab**. Les verdicts obtenus
      sur un univers survivant et des prix rétro-ajustés ne sont pas définitifs.

## 🏦 AUDIT BOARD 2026-08-20 — 4 piliers (cf. [[19_AUDIT_BOARD_4_PILIERS]])
- [x] **Hurst R/S** — LIVRÉ `packages/regime/hurst.py` : correction Anis-Lloyd (le R/S brut sort
      H=0,566 sur du BRUIT PUR → « tendance » à tort), bande nulle par permutation, verdict
      opérationnel (momentum / arbitrage stat / aucune allocation), H glissant causal.
- [x] **HMM causal** — LIVRÉ `packages/regime/hmm_causal.py` : Baum-Welch, fenêtre expansive,
      probabilité FILTRÉE, réordonnancement des états par volatilité, hystérésis. Sentinelle de
      non-fuite testée (troncature ⇒ chemin identique). **Correctif du finding F3.**
- [x] **Netting Core/Satellite** — LIVRÉ `packages/portfolio/netting.py` : net vs brut vs
      exécuté, coût du conflit en bps, 3 politiques (net / core_priority / block), livres
      virtuels pour l'attribution. **Correctif du finding F13.**
- [x] **F11 · calendrier de marché — PARTIE EXÉCUTION LIVRÉE le 26/08 (ADR-0040).**
      `packages/execution/market_calendar.py` répond « peut-on envoyer cet ordre maintenant ? »
      (XNYS 09:30-16:00 ET, week-ends, fériés, 24/7 crypto) et `run_live` REPORTE au lieu
      d'envoyer dans le vide. Reste ouvert ci-dessous pour l'intraday.
- [x] **Statut de l'ordre relu après envoi — LIVRÉ le 26/08 (ADR-0042).**
      `packages/execution/order_outcome.py` : quatre issues (REJETE / REMPLI / EN_COURS /
      INCONNU). Un rejet ne compte plus comme envoyé ni comme ouverture journalisée.
      Vérifié contre les quatre courtiers du dépôt avant activation.
- [x] **`/positions` n'annonce plus d'achats impossibles — LIVRÉ (ADR-0043).** Badge
      « bloqué · sous le plancher » + bandeau quand aucune cible ne peut partir.
- [ ] **F11 (suite) · calendrier complet (P0 avant tout intraday)** : `MarketCalendar` par place
      (XNYS/XETR/24-7) — `is_open`, `session_minutes`, demi-séances, enchères, jours fériés.
      Sans lui, l'agrégation 1 h → 4 h → Weekly est une source de fuite structurelle.
- [ ] **F12 · boucle asynchrone** : une seule boucle d'E/S, cœur de décision synchrone et
      déterministe, file BORNÉE, détection de flux mort, dead-man switch. Refonte du chemin de
      prod → ne pas mener sans un vrai flux pour la valider.
- [ ] **F14 · log d'événements d'ordre** append-only (INTENT→SUBMITTED→ACKED→PARTIAL→FILLED
      /REJECTED/CANCELED), reconstruction par rejeu, écart d'horloge suivi. Schéma en § 4.2.
- [ ] **Cockpit** : 5 vues manquantes (exposition factorielle, CVaR/Hill, attribution Core vs
      Satellite, exploitabilité covariance, régime filtré) — toutes les sources existent déjà.
- [ ] **Business** : mesurer avant de valoriser — 5 interlocuteurs paieraient-ils un rapport
      d'intégrité de backtest ? Précondition : le RDV paper.

## 🔬 MODULES AVANCÉS 2026-08-20 — branchements (cf. [[18_MODULES_AVANCES]])
> Code livré et testé, **non câblé**. Chaque branchement passe par le gate.

- [x] **M1 · covariance — BRANCHÉ (opt-in)** : `packages/backtest/cov_risk.py` (porte d'entrée
      unique des 2 rails) + flag `cov_denoise` dans `preset_backtest` ET `preset_latest_weights`.
      **Défaut inchangé au bit près** (non-régression testée) ; le DIAGNOSTIC, lui, est toujours
      calculé et publié dans `cov_diag`. Repli inverse-vol quand `k_signal < 2`.
      Config `+covariance débruitée RMT` ajoutée à `make preset-lab`, section « exploitabilité ».
- [ ] **M1 · CE SOIR SUR LE MAC** : `make preset-lab` → me coller la section
      « COVARIANCE — EXPLOITABILITÉ » + la ligne `+covariance débruitée RMT`.
      C'est LA mesure qui dit si l'ERC du preset répartit du signal ou du bruit.
      Si `k` médian < 2 sur données réelles : l'ERC n'est pas justifiée et le levier RMT
      (ou l'inverse-vol pure) devient le défaut — PR d'activation AVEC ces chiffres.
- [ ] **M2 · labellisation** : corriger `ml/labeling.triple_barrier` — barrières en
      `pt·sigma·sqrt(h)` (aujourd'hui `pt·sigma` : barrière touchée quasi sûrement),
      détection sur `high`/`low` (aujourd'hui close seul = biais optimiste), ex-æquo résolu
      en faveur du stop, barrières inversées pour les shorts.
- [ ] **M2 · CV** : remplacer `PurgedKFold` par `CombinatorialPurgedCV(6, 2)` dans
      `ml_walkforward` → distribution de Sharpe sur 5 chemins → PBO calculé sur cette
      distribution, DSR avec `n_eff` (`uniqueness.effective_sample_size`) et non `n`.
- [ ] **M3 · TC et souffle** : instrumenter `preset_backtest` (2 lignes) — `transfer_coefficient`
      et `ir_report`. Répond à « le problème vient-il du signal ou de mes contraintes ? ».
- [ ] **M4 · exécution** : `trajectory()` dans le chemin d'exécution des blocs, avec
      `cap_by_participation` ; calibrer `eta`/`gamma` sur le TCA réel (N ≥ 100 fills).
- [ ] **M5 · portage** : `carry_costs()` dans le PnL du backtest dès qu'un short existe ;
      exiger `max_borrow_fee()` du courtier AVANT d'ouvrir la moindre position vendeuse.
- [ ] **M5 · EVT** : passer `evt.fit_pot` aux moments pondérés par les probabilités (formules
      fermées vérifiées en [[M5_QUEUES_ET_FINANCEMENT]] § 2) ; ajouter l'estimateur de Hill.
- [ ] **M6 · sentiment** : journaliser le MOTEUR (FinBERT vs lexique) avec chaque score —
      un historique mixte est inexploitable ; puis `neutralize()` sur la surprise de résultats
      avant de mesurer l'IC (sinon le facteur est du PEAD déguisé).
- [ ] **M7 · alt-data** : rien à brancher avant F1 et F2. Quand ce sera le cas : une source à
      la fois, prior écrit d'abord, `granger_both_ways` + `mi_permutation_test` + Šidák.
- [ ] **Décision de périmètre** : options (surface de vol, grecques) — dans le projet ou pas ?
      Aucune chaîne d'options n'est ingérée aujourd'hui ; c'est un choix, pas un oubli.

## 🏛️ AUDIT INSTITUTIONNEL 2026-08-20 — suites (cf. [[17_AUDIT_INSTITUTIONNEL]])
> Ordre imposé par les dépendances, pas par préférence : sans la vague 1, aucune mesure ne vaut.

**Vague 1 — rendre le passé immuable (P0)**
- [ ] **F1 · prix bruts + `corporate_action`** : arrêter `auto_adjust=True` en écriture, stocker
      l'OHLCV AS-TRADED, calculer le facteur à la lecture avec `as_of` (algo : [[AXE1_DATA_PIT]] § 2).
      Étendre `pit_guard.stable_prefix` aux PRIX (test CI `pit_replay`).
- [ ] **F9 · `index_membership` datée** + `symbol_history` (FB→META) + `security_master` avec
      `delist_return` (convention CRSP −30 % si inconnu) → débloque enfin `survivorship_delta()`.

**Vague 2 — installer le thermomètre (P1)**
- [ ] Mesurer **IC réalisé par facteur et par horizon** (rendement RÉSIDUEL, CV purgée), puis
      `breadth.ir_report(...)` : N_eff, T_eff, TC. Publier `ic_required` pour l'IR cible.
- [ ] **TC dans `preset_backtest`** : corrélation(alphas, poids réels) — 2 lignes, répond à
      « le problème vient-il du signal ou de mes contraintes ? ».
- [ ] F5 · aligner `psr.bootstrap_sharpe_ci` sur un bootstrap **par blocs** (le front le fait déjà).
- [ ] F6 · z-score robuste (médiane/MAD + winsorisation ±3 + taille de groupe ≥ 10) dans `ranking/engine.py`.
- [ ] F7 · `evt.fit_pot` par **PWM** au lieu des moments (formules fermées dans [[AXE3_QUEUES_REGIMES]] § 1.2).
- [ ] Estimateur de **Hill** + Hill plot : afficher l'indice de queue α à côté des KPI héros.

**Vague 3 — coût non linéaire partout (P0)**
- [ ] Brancher `impact.total_cost_bps` dans `preset_backtest`, `screening/expectancy_filter`
      et le sabotage. **Peut inverser des verdicts existants** → à faire avant tout nouveau signal.
- [ ] Calibrer `Y` par régression sur les fills réels (`tca.py` + `exec_costs.py`), N ≥ 100.
- [ ] F10 · trancher l'appétit pour le risque : `fraction=0.25` (budget DD 50 %) vs
      `QUANT_DD_TARGET=0.25` (impose λ ≈ 0,175). Un seul nombre doit gouverner les deux.

**Vague 4 — alpha non directionnel (P1)**
- [ ] **Décision préalable** : lever ou non le long-only (ADR-0029). Sans short, pas de paire.
- [ ] Si oui : univers de candidats à prior économique (jamais toutes les paires), fenêtre de
      formation figée, filtre « ≥ 12 traversées de la moyenne », puis gate 4 étages.
- [ ] Kalman causal pour le ratio de couverture ([[AXE3_QUEUES_REGIMES]] § 3).

**Vague 5 — exécution (P0 avant tout live/intraday)**
- [x] **F4 · `exec_lag = 1` par défaut** (0 = option « optimiste » étiquetée) — LIVRÉ PR #342 (2026-08-25).
- [ ] `FillModel` injectable derrière `Broker` : `NextBarPOVFill` (L1) puis `QueueFill` (L2).
- [ ] **Dead-man switch** + machine à états NORMAL/REDUCED/FLATTEN_ONLY/HALTED.
- [ ] Disjoncteur de slippage (médiane glissante 20 fills > 3× le coût modélisé → HALTED).
- [ ] F3 · verrouiller `vol_regime` (fenêtre expansive, probabilité FILTRÉE, réordonnancement
      des états par vol) **avant** tout câblage dans une boucle de backtest.

## 🌙 CE SOIR SUR LE MAC — 2026-07-17 (post-merge #320)
- [ ] **0. Récupérer le merge #320** (audit + dashboard trades + simulateur MC) :
  ```bash
  cd ~/Screening-Trading && git fetch origin && git reset --hard origin/main
  ```
- [ ] **A. Labo Sharpe/Sortino (LE cœur de « rendre performant » — données réelles requises)** :
  ```bash
  make preset-lab
  ```
  → me coller la sortie. Si un levier est ✅ CANDIDAT : je fais la PR d'activation AVEC ces chiffres.
- [ ] **B. Confirmer que le bug de rachat BTC (fin juin→8 juil, ‑5,7 %) est bien clos** (lecture seule) :
  ```bash
  make verify-journal
  ```
  → cherche des BTC buy répétés chaque jour ouvré avant le 8/7 ; si plus rien après, le bug est fermé.
- [ ] **C. Re-runner les 8 hypothèses avec le DSR RÉPARÉ** (verdicts peuvent basculer, 2 sens) :
  ```bash
  make vault-sync
  ```
  → regarder `/echecs` ensuite.
- [ ] **D. Voir le nouveau dashboard + simulateur en local** (optionnel) :
  ```bash
  make start
  ```
  → `localhost:3000/dashboard` (qualité des trades) et `/risk` (simulateur Monte Carlo).
- [ ] **E. Secrets alerting (clics GitHub, 2 min)** : Settings → Secrets → Actions → New :
      `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` (bot via @BotFather). Sinon un run rouge ne notifie personne.

## 🎯 ROADMAP GROSSES AMÉLIORATIONS (priorité = RDV paper 2026-08-06)
> Ce qui reste APRÈS #320. Deadline forçante = le RDV du 06/08 (verdict GO/NO-GO du paper).
- [~] **XL-1 · Univers backtest point-in-time avec délistés** — MÉCANISME LIVRÉ (#PR suivante) :
      `survivorship_delta()` + section dans `make preset-lab`. RESTE À TOI : `make ingest-delisted`
      (ingère l'OHLCV des délistés en base — delisted.csv n'a que noms+dates), puis `make preset-lab`
      affiche le Δ Sharpe → PUBLIER sur `/echecs`. C'est LA crédibilité du backtest.
- [x] **M-1 · Fill t+1** — LIVRÉ : param `exec_lag` (défaut **1** depuis PR #342, 2026-08-25) ; ancien
      « fill t+0 » étiquetée « optimiste » dans `make preset-lab` pour comparaison (mini look-ahead ~‑0,01 Sharpe).
- [x] **M-2 · Sabotage sur Δposition** — LIVRÉ : `stress_returns`/`sabotage_verdict` acceptent
      `turnover` (coût ∝ |Δpoids|, plus par barre). Tests verts.
- [x] **ARC-1 · Alignement par calendrier (PR #341, 2026-08-25)** — LIVRÉ : `aligner_par_date()` + migration
      des trois outputs (equity_curve, trade_log, ledger) vers grille homogène. Stock vs crypto enfin séparé.
      Impact : Sharpe 0,92→1,35 (3 ans de drift ancien calendrier). Cf. ADR-0037.
- [x] **ARC-2 · Périmètres risque fermés (PR #343, 2026-08-25)** — LIVRÉ : `RiskEngine` (streaming) vs
      `order_gate` (rebalancing) avec 4 tests architecturaux + ADR-0036. Violation impossible (test rouge).
- [x] **ARC-3 · Grille sans NaN (PR #341 refactoring, 2026-08-25)** — LIVRÉ : `aligner_sans_trous()` garantit
      zéro NaN au ledger (intersection calendrier, rank-based). Ledger = domaine d'accueil, jamais d'artefact P&L.
      Cf. ADR-0037.
- [ ] **XL-2 · Refactor god-objects** : `snapshot.py` 2467 l + `main.py` 991 l (le hook bloque chaque
      edit ; 2500 l = drapeau rouge pour tout recruteur technique). Découper en modules `sections/` + `routes/`.
- [ ] **L-1 · Preuves terrain du 06/08** : N≥20 round-trips réconciliés au relevé Alpaca + courbe equity
      accumulée (equity_history → HF, fait #320). `make rdv-paper` doit sortir GO, pas INSUFFISANT.
- [ ] **L-2 · Gater l'edge DD÷2,6** (jamais passé au PBO) + brancher VaR-backtest sur le rail prod
      (les caps corr-aware le sont depuis #320 ; le gate VaR ne l'est pas).
- [ ] **L-3 · Fusion pages front** /live + /trades → /positions ; /portfolio → /risk (finding produit :
      4 pages pour « qu'est-ce que je détiens ? » = parcours cassé). Redirects, nav inchangée.
- [ ] **L-4 · ML : trancher honnêtement** — soit gater (CV CALENDAIRE pas par index, Brier OOS),
      soit dégrader en « indicateur » assumé (0 trade réel attribuable aujourd'hui, finding B).
- [ ] **M-1 · Fill t+1** (`preset_backtest.py:176` exécute au close de la barre de signal = mini
      biais optimiste) → variante open t+1, chiffrer l'écart.
- [ ] **M-2 · Sabotage coût sur Δposition** seulement (`adversarial.py`), pas par barre.
- [ ] **M-3 · Attribution par actif + « pourquoi » par round-trip** sur le front (contributeurs/
      détracteurs existent déjà dans `obsidian.py`, jamais exposés en ligne).

## 🌙 CE SOIR SUR LE MAC — 2026-07-06 (post-audit 3 volets, ~10 min)
> Les 4 gestes que l'agent ne peut pas faire à ta place (token Notion local, proxy git, clics GitHub).
- [ ] **1. Resynchroniser le repo local** (récupère #299 : remédiation audit + constraints) :
  ```bash
  qt && git fetch origin && git reset --hard origin/main
  ```
- [ ] **2. Rattraper le miroir Notion** (2 semaines de retard constatées à l'audit) :
  ```bash
  make notion-sync
  ```
- [ ] **3. Supprimer les 3 branches distantes fusionnées** (l'agent a été bloqué par le proxy, 403) :
  ```bash
  git push origin --delete ops-integration feat/ui-analytics feat/journal-features-snapshot
  ```
- [ ] **4. Runner cloud — secrets GitHub** (clics, pas de terminal) : repo → Settings →
      Secrets and variables → Actions → New : `ALPACA_API_KEY` + `ALPACA_API_SECRET` (compte
      **paper**) + `HF_TOKEN` (fine-grained, limité au dataset `Noctis777/quant-journal`).
      Puis Actions → « Rebalancement paper cloud » → **Run workflow** (test).
- [ ] **5bis. ⚠️ RE-BACKFILL AJUSTÉ (une fois, ~10 min)** — le fix P1-4 (splits) ne corrige
      l'HISTORIQUE qu'après ré-ingestion complète :
  ```bash
  python scripts/ingest_prices.py --since 2015-01-01   # OHLC ajustés splits+dividendes
  make ingest-crypto && make hf-push                    # reconstruit le cache HF en AJUSTÉ
  ```
- [ ] **6. Vintages macro RÉELS (P1-3, ~5 min)** : clé gratuite sur
      fred.stlouisfed.org/docs/api/api_key.html → `echo 'FRED_API_KEY=...' >> .env` puis :
  ```bash
  make ingest-macro    # ALFRED → data/macro.db (révisions datées de LEUR publication)
  ```
- [ ] **7. ⚡ BITMART — vérifier que les trades FONCTIONNENT (micro-test, ARGENT RÉEL)**
      ⚠️ Bitmart n'a pas de paper : tout ordre est réel. Protocole minimal (≈12 $, aller-retour) :
  ```bash
  make bitmart-check            # 1) verrous + connexion + MEMO (obligatoire) en lecture seule
  # 2) micro-test CONSCIENT (achat ~6 $ puis revente — teste le fix coût d'achat du 06/07) :
  .venv/bin/python -c "
  from packages.common.env import load_env; load_env()
  from packages.execution.bitmart_broker import BitmartBroker
  from packages.core.models import Side
  b = BitmartBroker(dry_run=False)
  print('ACHAT :', b.submit_notional('BTC/USDT', Side.LONG, 6.0).status)
  print('VENTE :', b.submit_notional('BTC/USDT', Side.SHORT, 6.0).status)"
  ```
      → attendu : FILLED/SUBMITTED aux 2 sens (le bug d'achat silencieux est corrigé). Si REJECTED :
      lire le log (désormais la CAUSE est affichée) — memo manquant = suspect n° 1.
      **Activation PERMANENTE dans le cron** (QUANT_NO_CRYPTO_LIVE=0 + réviser le routage ADR-0032) :
      NON recommandée avant le RDV 2026-08-06 — c'est une décision explicite à part (garde-fou CLAUDE.md).
- [ ] **5. Vérifier le PREMIER run journalisant du jour** (lundi = cron 16h05 a tourné) :
  ```bash
  tail -30 ~/Library/Logs/quant_live.log   # attendu : « Journal : N ouverture(s)/lot(s) fermé(s) »
  make verify-journal                       # legacy=0 doit enfin être > 0 si des ordres sont partis
  ```
  (Si « ✓ déjà aligné » partout = aucun ordre → journal inchangé, c'est normal et honnête.)

## 🚧 EN COURS — reprise 2026-07-03 (branche `feat/broker-hardening`)
> Journée broker-hardening (BLOC 1→4) démarrée. Base : `origin/main` à jour (#292 mergée = `323e53a`).
> Carry-over local non commité : `config/mobile_universe.csv` (data régénérée, hors périmètre — laisser tel quel).
> **Amendements validés** : 1a `_seen` rejoue le résultat RÉEL (y c. rejet), jamais de FILLED fabriqué ·
> 1b ouverture seule (sortie partielle → P2) + si `filled_qty=None` → NE PAS ouvrir + alerte CRITICAL · 1c OK.

- [x] **BLOC 1a — idempotence Bitmart** — LIVRÉ dans `main` via **#293** (audit 2026-07-05) :
      `_seen` rejoue le résultat RÉEL (y c. rejet, y c. qté partielle), `clientOrderId` passé en
      `params` ccxt (dédup côté exchange), `_remember()` après chaque submit définitif.
      Tests `test_bitmart_idempotency.py` verts.
- [x] **BLOC 1b — fills partiels** — LIVRÉ via **#293** : `live_engine.py` gère `PARTIALLY_FILLED`
      (ouvre à `filled_qty` réel + warning reliquat) ; `filled_qty=None` → position NON ouverte +
      alerte CRITICAL. Tests `test_partial_fills.py` verts.
- [x] **BLOC 1c — alerte de réconciliation branchée** — LIVRÉ via **#293** : `packages/alerts/wiring.py`
      (`default_engine` + `attach_to_bus`), `LiveTradingEngine(bus=…)` → `reconcile(bus=…)`,
      hook dans `run_live.py` (`_setup_alerts`).
- [x] **BLOC 2 — FAIT (2026-07-06)** : `make bitmart-check` (lecture seule) affiche les 3 verrous +
      teste la connexion (equity/positions, zéro ordre). Au passage, **vrai bug corrigé** : achat
      marché spot sans prix → `createMarketBuyOrderRequiresPrice` avalé = REJECTED **silencieux**
      (désormais : prix passé pour le coût + rejet LOGGÉ). Activation = décision post-RDV 06/08.
- [ ] **BLOC 3** — Crypto paper via Alpaca (BTC/USD, ETH/USD), sizing vol-target adapté (vol crypto ≫ actions),
      trades crypto → journal SQLite avec `features_snapshot`.
- [ ] **BLOC 4** — Optimisation Alpaca paper (opérationnel, PAS de tuning stratégie) : cron `cron_live.sh`, limit vs
      market, fractional shares, **chaque run alimente `journal.db`** (accumuler des trades avec features = calibration).
- [~] **BLOC 5** — UI/Analytics institutionnel : branche **SÉPARÉE** `feat/ui-analytics` (ne pas mélanger aux brokers).
      Mode plan **écran par écran** (plan avant code). Cf. brief détaillé du 02/07.
  - [x] **Dashboard principal** (2026-07-04, PR #294, commit `d2d11c1`) : `PerformancePanel` (equity+underwater
        synchronisés, zoom LTTB partagé `syncId`), `DrawdownChart`/`PositionsAlertsTable` nouveaux, `MetricCard`
        delta N−1, `RegimeBanner` tokens outline. Fix bug LTTB (pire DD sous-estimé). Cf. **ADR-0030**. `tsc` vert + contrôle visuel headless.
  - [x] **Écran 2 — /positions « réel vs cible »** (2026-07-05) : fusion positions réelles × cible preset
        (poids par poche de capital), barre d'écart divergente + bande de non-trading 3 %, HHI/N effectif/top 3,
        badge earnings, SortableTable (tri/filtre/CSV), route `/api/positions` expose `preset_allocation` +
        `earnings_risk`. Build statique + tests API verts.
  - [ ] **Écran suivant** (à planifier) : candidats `/screener` ou analyse portefeuille dédiée — plan avant code.
  - [ ] **Dette signalée par le hook (02/07, préexistante)** : `apps/api/main.py` 953 l > 400 + 3 fonctions
        >50 l (`_top_syms`, `_build_company_report_cached`, `_enrich_cross_source`) — même famille que le
        god-object `snapshot.py` (P2). Extraire en modules `apps/api/routes/*` lors du refactor sections.
> Contraintes : `make test` vert entre chaque bloc · commits atomiques · rien qui touche `--live` · garde-fous intacts.

## ☁️ RUNNER PAPER CLOUD (Mac éteint, 0 €) — 2 actions à faire par TOI (5 min)
> Livré 2026-07-05 : `.github/workflows/paper.yml` (lun-ven 14h35 UTC, Alpaca PAPER forcé,
> crypto neutralisée) + `scripts/hf_journal.py` (journal persisté sur dataset HF **PRIVÉ**).
> Idempotent vs le launchd du Mac : le 2ᵉ runner du jour voit des deltas ~0 et n'envoie rien.
- [ ] **Créer les secrets GitHub** (repo → Settings → Secrets and variables → Actions → New) :
      `ALPACA_API_KEY` + `ALPACA_API_SECRET` (les clés du compte **paper**) et, recommandé,
      `HF_TOKEN` (token huggingface.co « write » → persistance du journal, dataset créé PRIVÉ
      automatiquement : `Noctis777/quant-journal`).
- [ ] **Tester une fois** : onglet Actions → « Rebalancement paper cloud » → Run workflow ;
      vérifier dans le log « Terminé : N ordre(s) » puis « journal poussé … (privé) ».
- [ ] (Option) **Choisir le runner principal** : garder les deux est SANS DANGER (idempotent),
      mais le journal du Mac et celui du cloud divergent (chacun journalise SES ordres envoyés).
      Recommandé : cloud = principal → `make live-cron-uninstall` sur le Mac, et pour consulter :
      `make journal-pull && make verify-journal`.

## 🚨 FULL-REVIEW 2026-07-02 — findings (voir `vault/14_FULL_REVIEW.md`)
> Revue complète multi-agents sur `ops-integration`. **P0 = invalide des résultats → avant toute feature.**
### 🔴 P0 (bloqueurs capital réel)
- [x] **P0-1 FUITE — CODE CORRIGÉ** (fix `f78e18f`, 2026-07-02, dans `main`) : les 3 fonctions dashboard +
      `preset_backtest` sélectionnent désormais l'univers par **momentum prix-only** (`_price_universe`),
      jamais par le score `quality` du jour. Aucun appelant ne réactive la fuite (`legacy_quality_universe`
      reste `False` partout). **Verrou de non-régression ajouté** : `tests/backtest/test_dashboard_no_leak.py`
      (2 dicts `quality` opposés → sortie identique ; le mode legacy diverge = le test a du mordant).
  - [x] **Reliquat FERMÉ (2026-07-05, sur le Mac)** : `make vault-sync` a régénéré `Preset_Performance.md` →
        **`alpha_annual` 0.0755 → 0.0445** (la fuite gonflait l'alpha de ~3 pts — preuve empirique de P0-1).
        Lecture honnête : le 4,45 % restant est un **alpha d'attribution** (régression vs QQQ, beta 0.37,
        R² 0.63), **PAS un alpha gaté** (placebo/DSR/PBO/sabotage jamais passés dessus) — DSR≈0 reste le
        claim public. Edge prouvé = réduction du drawdown, pas la direction.
- [x] **P0-2 — FERMÉ (2026-07-05)** : manifeste honnête (« DSR≈0 après correction d'une fuite d'univers le
      02/07 ») + artefact local régénéré post-fix (alpha 4,45 % non gaté, cohérent avec le claim).
- [x] **P0-3 — coûts déduits** : `preset_equity_daily`/`preset_ledger` déduisent le coût de turnover par classe
      (`reb_cost`/`_tc`) à chaque rebalancement → equity NETTE, plus « brute ». (Vérifié dans le code courant.)
- [~] **P0-4 JOURNAL LIVE VIDE** (découvert BLOC 4, 2026-07-04) : le chemin de prod du cron
      (`cron_live.sh → run_live.py`) réconciliait chez le broker sans **jamais** écrire dans `data/journal.db`
      (seul `LiveEngine`, fantôme, journalisait) → **0 trade `legacy=0`** = calibration ML bloquée en paper.
      **Décision d'archi : (b) journal direct via `SqliteTradeJournal`** (validée 2026-07-04 ; (a) unifier sur
      LiveEngine = trop gros/risqué près de `--live`).
      - ✅ **Phase 1 (fait, 2026-07-04)** : `packages/execution/live_journal.py` + refactor `run_live.py`
        (main scindé en helpers ≤50 l) journalise chaque ACHAT envoyé (`legacy=0`). **Features figées à la
        DÉCISION** dans `build_snapshot()` (screener `score`+facteurs, poids cible, régime), transportées via
        le snapshot, **jamais reconstruites** ; **faits de fill** (prix/qté) lus des positions RÉELLES du broker
        (lookup tolérant BTC/USD↔BTCUSD). `id` déterministe/jour → idempotent. 7 tests (`test_live_journal.py`).
        `make verify-journal` passe de `UNCALIBRATED` à ✅ au 1er run réel.
      - [x] **Phase 2 (fait, 2026-07-05)** : round-trip — `packages/execution/live_roundtrip.py`
        (`open_lots`/`close_sells` FIFO, vente partielle = scission de lot id `-Xn` déterministe,
        UPSERT idempotent) + `run_live.py` capture les VENTES envoyées et ferme les lots
        (`exit_ts/exit_price/pnl/pnl_pct/is_win/duration_s` + **MFE/MAE** depuis la série OHLC du
        snapshot). Prix de sortie = FAIT broker (fill du jour via `orders()` → `last_price` →
        prix de position ; introuvable = lot laissé OUVERT, jamais estimé). 6 tests
        (`test_live_roundtrip.py`), suite 811 verts. Débloque expectancy/Kelly au RDV 2026-08-06.
      - [x] **Décision prise (2026-07-05, validée utilisateur)** : `LiveTradingEngine` **RÉTROGRADÉ**
        en moteur de simulation (docstring de statut, exports conservés, zéro churn tests/démos).
        Chemin de prod UNIQUE = `run_live.py`. Cf. **ADR-0031**.
### ⛔ P0-SI-LIVE — bloquants AVANT toute activation d'un broker réel (audit adverse 02/07, cf. `14_FULL_REVIEW.md`)
> Prouvés, sévérité capital/ops. **Ne jamais passer le broker concerné en live tant que son P0-SI-LIVE n'est pas fermé** (garde-fou CLAUDE.md).
- [x] **#4 Idempotence Bitmart — FERMÉ** (via #293, vérifié 2026-07-05) : `clientOrderId` en `params`
      ccxt + court-circuit `_seen` (rejoue le résultat réel, jamais de FILLED fabriqué). Tests verts.
- [x] **#5 Fills partiels — FERMÉ** (via #293, vérifié 2026-07-05) : `PARTIALLY_FILLED` ouvre à
      `filled_qty` réel (reliquat loggé) ; `filled_qty=None` → pas d'ouverture + alerte CRITICAL ;
      alerte de réconciliation branchée (bus → `default_engine`). Tests verts.
> ✅ Plus aucun P0-SI-LIVE ouvert. L'activation d'un broker réel reste conditionnée au RDV paper
> du 2026-08-06 (cf. garde-fou CLAUDE.md : jamais de live sans décision explicite).
### 🟠 P1
- [x] **Cron paper multi-venue sûr (2026-08-30)** : neutralisation explicite des clés Binance et
      Bitmart par valeurs vides, empêchant le reload `.env`; test statique de non-régression.
- [ ] **Price-action causal UNCALIBRATED (2026-08-30)** : plugin BOS/FTB/FVG/SFP et backtest
      1R/TP partiels livrés, mais **non câblés en production**. À évaluer sur données réelles L2/tick
      en walk-forward purgé avec DSR/PBO/Reality Check avant toute promotion paper.
- [x] **Rotation des modèles cloud (2026-08-30)** : le preset fournisseur ne fige plus un modèle
      périssable ; si le modèle enregistré est retiré, le client choisit un autre modèle texte
      annoncé par le catalogue et republie le transport/modèle réellement utilisé.
- [x] **P1-1** ✅ (2026-07-02, suite) : `SqliteTradeJournal` (`data/journal.db`, JSON features, UPSERT
      idempotent, flag `legacy` requêtable) + `LiveTradingEngine` persiste par défaut + `import_legacy_fills.py` (script one-shot, retiré 05/07)
      (137 fills importés `legacy=1`) + 8 tests (dont contrat anti-fuite). Cf. **ADR-0028**, commits `834338a`→`3c1c771`.
      **Reste** : la calibration MFE/MAE/expectancy/Kelly attend N>0 sur `legacy=0` (paper live → RDV 2026-08-06).
- [x] **P1-2 — FERMÉ côté FMP (2026-07-06)** : `as_of` = `fillingDate` (dépôt public), plus la
      clôture d'exercice (look-ahead). Test dédié. Reste `sec_provider` (filtrer `filed`) → P2.
- [x] **P1-3 — CODE FERMÉ (2026-07-06)** : MacroStore persistant (`data/macro.db`, env
      `QUANT_MACRO_DB`) + `make ingest-macro` (vintages ALFRED réels, `published` = realtime_start).
      Test PIT à travers une réouverture. Reste : lancer l'ingestion sur Mac (CE SOIR 6).
- [x] **P1-4 — CODE FERMÉ (2026-07-06)** : ingestion `auto_adjust=True` + détection de couture
      post-split (`_split_drift` → re-backfill auto du symbole). ⚠️ Historique corrigé seulement
      après le re-backfill complet sur Mac + `make hf-push` (cf. CE SOIR 5bis).
- [ ] **P1-5** : `pbo` **dupliqué** — consolider en 1 (garder `portfolio/pbo.py`, retirer `backtest/validation/pbo.py`).
- [ ] **P1-6** : 9 modules top1pct **orphelins** — câbler ou marquer « en attente » ; enregistrer `vol_target`/`kelly_uncertain` au registre Sizer.
- [x] **P1-7 — FERMÉ (2026-07-05, audit 3 volets)** : `01_ARCHITECTURE.md` réécrit (table d'état
      + Mermaid = 14 packages réels), ADR-0029 dédoublonné (→0032), TODO purgé (469→~300 l),
      `vault-lint` câblé en CI (informatif), orphelins liés, notes `paper_*` créées (09_References).
- [~] **P1-8 — passe 1 FAITE (2026-07-06)** : gates « exécution/infra » ajoutés au protocole +
      5 composants prod évalués sur preuves → **CANDIDATE** (registre daté). Reste la promotion
      CERTIFIED, mécanique après 20 j paper + drills (≈ RDV 2026-08-06).
### 🟢 P2
- [ ] **P2 (audit 02/07)** — **#1 Fuite Platt** (`snapshot.py:670-675`, LOW, non-capital) : fit Platt sur une tranche
      60-80 % **distincte** du test 80-100 % (aujourd'hui `brier_calibrated` est in-sample = optimiste, mais n'atteint
      ni les probas servies ni le sizing). **#3 Doublons DSR/PBO** : supprimer les 2 impl. **mortes** `validation/sharpe_stats.deflated_sr`
      + `validation/pbo.pbo_cscv` (0 importeur hors `test_smoke_all.py`) — étend P1-5.
- [ ] **P2** : câbler `macro_publication_lags.yaml` + `risk_top1pct.yaml` · crypto DB 13 j de retard + délistés ·
      tests `packages/macro` (0) · refactor `snapshot.py` (2526 l) · `overnight`/`ts_momentum` dans `factors.yaml` ·
      corriger `08_DATA_MODEL.md` (schéma flat prod v1).

## 📅 RENDEZ-VOUS — 2026-08-06 : REVUE COURBE PAPER (paper vs backtest)
> Audit 3× passé (score ~83/100, **PRÊT POUR CAPITAL RÉEL LIMITÉ** sous conditions).
> Paper défensif lancé le 2026-06-25 (`QUANT_DD_TARGET=0.15`). On laisse tourner ~6 semaines.
- [ ] **2026-08-06** — comparer la courbe paper réelle au backtest preset (Sharpe/MaxDD/CAGR
      concordent-ils ?). Décision : **premier euro réel limité** OU re-calibrage.
  - sortir la courbe : `make analytics` (QuantStats) + `make ledger-sweep` (journal discret).
  - critère GO : paper cohérent avec le backtest (pas de dérive Sharpe>1pt, MaxDD non dépassé).
  - si concordant → engager un capital réel **limité** + sizing défensif ; sinon → re-calibrer.

## 🗄️ Sessions « CE SOIR SUR LE MAC » de juin — CLÔTURÉES (purge 2026-07-05)
> 9 sections opérationnelles (2026-06-24 → 06-30) purgées : tout est LIVRÉ et mergé
> (PR #287/#288/#289 + suivantes). Les faits sont consignés là où ils doivent vivre :
> verdicts de gate → `12_MANIFESTE_HONNETETE.md` (F&G p=0,905 · cassure canal DSR 0/PBO 0,88…) ·
> récits de session → `04_JOURNAL.md` · reliquats réels repris ci-dessus (RDV 06-08, runner cloud).
> Historique complet : `git log vault/03_TODO.md`.

## 🎯 SPRINT « ALPHA / CALMAR » — à démarrer (2026-06-24)
> Objectif : **Calmar 0.17 → 0.6-0.9** en **divisant le Max DD par 2** + alpha honnête.
> Cible code : `packages/backtest/preset_backtest.py` (cœur de la stratégie de production).
> ✅ déjà fait : réplication idempotente **anti-levier** (`run_live.py`, réconciliation au delta).

### 🔴 P0 — Réduire le Max DD (le plus gros levier sur le Calmar)
- [x] **#6 Frein drawdown (marché)** : suivre DD depuis le pic ; `dd<-10%→gross×0.5`, `dd<-15%→gross×0` (ré-arme à la reprise). `preset_backtest.py` boucle `for t`.
- [x] **#5 Porte de régime sur le gross** : plein risque si `^NDX>MM200 & pente>0` ; 0.6 en distribution ; 0.2 sous MM200. (`packages/regime/` + passer la courbe NDX au backtest.)
- [x] **#3 Covariance Ledoit-Wolf** dans `_cov_annual` (`preset_backtest.py:27`) — utiliser `packages.data.engine.ledoit_wolf_shrinkage` (déjà dispo) au lieu de `np.cov` brut.
- [~] **#9 Rebalancement déclenché par la vol** : DIFFÉRÉ (parcimonie) — les portes #5/#6/#8 dé-risquent déjà à chaque step ; marginal. À n'ajouter QUE si le backtest réel le justifie.

### 🟠 P1 — Booster l'alpha (sans β subi)
- [x] **#1 Anti cash-drag (sans levier, k_dd→1.6)** : `preset_backtest.py:71` `gross=min(1,tgt_vol/pv)` → `clip(tgt_vol/pv,0,GROSS_MAX≈1.5)`, `tgt_vol≈0.15`.
- [x] **#4 Tilt momentum sur ERC** : `w ∝ w_erc × max(0,mom_12m)^γ` (renormalisé) — l'ERC pur étouffe les leaders (NVDA…).
- [~] **#7 Sizing demi-Kelly** : DIFFÉRÉ — conflit avec le sizing ERC+momentum déjà en place ; +1 paramètre = +overfit. À évaluer en A/B vs ERC seulement si besoin.
- [x] **#8 Gate breadth cross-asset** : `gross×clip(%univers>MM200 / 0.5, 0, 1)`.

### 🟢 Anti-overfitting (OBLIGATOIRE — rigueur López de Prado)
- [x] **#2 CRITIQUE — fuite de données (corrigée : univers backtest momentum prix-only)** : `preset_backtest.py:46-48` le tilt qualité utilise le score fondamental **actuel** sur tout l'historique (look-ahead + survivorship). → qualité **point-in-time** (vintages) OU univers **prix-only** (momentum 12-1). *Le 6.9 % d'alpha est probablement surestimé tant que ce n'est pas corrigé.*
- [x] **#10 Gate DSR (robuste/défensif)** sur `make calibrate-preset` : n'accepter des params que si **DSR>0 & PBO<0.5** (purged CV — briques `packages/ml` + `portfolio/psr.py`).

### 🌙 CE SOIR sur le Mac (ce que TOI tu dois faire)
- [ ] **Récupérer le code** : `qt && git pull origin main`.
- [ ] **Backtester les 2 nouveaux signaux d'alpha** (overnight, ts_momentum) sur tes données réelles :
  ```bash
  make backtest-preset          # vérifie que rien n'a régressé
  make calibrate-preset         # loggue + synchronise le DSR dans le ledger/notes (auto)
  # tester un signal isolé via le screener (édite config/screening.yaml -> weights: {overnight: 1}) :
  make screen
  ```
  → reporte le DSR obtenu : un facteur n'est **promu** que si DSR>0.5 ET PBO<0.5 (sinon il reste `hypothese`).
- [ ] **Installer + tester le plugin Obsidian Dataview** : Réglages → Modules complémentaires → désactiver
  le mode restreint → Parcourir → **Dataview** → activer. Ouvrir `vault/08_Alphas/00_Alpha_Dashboard.md`
  (les 7 hypothèses doivent apparaître, triées par DSR). Si vide : vérifier le frontmatter `type: alpha_hypothesis`.
- [ ] **Tester le connecteur prediction-markets** (lecture seule, sans clé, nécessite le réseau) :
  ```bash
  python -c "from packages.data.prediction_markets import fetch_markets; print(fetch_markets()[:3])"
  ```
- [ ] **Lancer un PREMIER event-study sur données réelles** (étape qui décide si on continue le ML/LLM) :
  ```bash
  python - <<'PY'
  from packages.data.sec_insiders import fetch_recent_form4   # ou tes dates d'earnings (PEAD)
  from packages.research.event_study import significance
  # 1) construire la série de rendements d'un ticker (ex. depuis ta YAHOO.db)
  # 2) trouver les indices de barres correspondant aux events (insiders / earnings)
  # 3) significance(returns, event_indices, post=5)  -> {mean_car, t_stat, placebo_p_value, significant}
  PY
  ```
  → **règle d'or** : si `significant=False` (p≥0.05 vs placebo) → on **ne code PAS** le ML/LLM (mirage).
  Si `True` → feu vert pour les étapes 4-6. Reporte-moi le résultat.
- [ ] **(rappel)** le LLM ne sert qu'à l'extraction de texte **as-of** (≤ ts_public), jamais à prédire.

### ⚙️ Opérationnel (rapide, côté utilisateur)
- [x] **Mesuré sur données réelles (2026-06-23)** : `make backtest-preset` → Preset CAGR 80,5 % · Sharpe 2,44 ·
  **MaxDD -9,0 %** vs équipondéré MaxDD -23,3 % (DD ÷ ~2,6). `make calibrate-preset` → 27 combos,
  **Sharpe déflaté ≤ 1 % partout = DSR≈0 CONFIRMÉ** (aucun alpha directionnel robuste).
- [ ] **Adopter le réglage défensif recommandé** : `echo 'QUANT_DD_TARGET=0.15' >> .env`
  (combo le moins overfit : DD-cible 15 % · top-K 20 · bande 3 % · turnover 0,20×).
- [ ] **Reset Alpaca paper + 1 seul `make live-go`** → annule le levier ~1,85× actuel.
- [ ] **Ménage disque macOS** (Data volume ~12 Go libres) : `prediction-market-analysis` 50 Go, `Desktop` 21 Go, `Library` 16 Go.
- [ ] Plugins Obsidian : **Smart Connections** + **Obsidian Git** (si pas encore activés).
- [ ] (Optionnel) Supabase : créer projet + table `daily_kpis` → `make supabase-kpis`.

### ✅ Audit « 5 entités » — feuille de route 5 lots FAITE (PR #242 + #243, 567 tests)
- [x] **Lot 1** chirurgie : indices `^` exclus du screener + retry/backoff broker (`packages/common/retry.py`).
- [x] **Lot 2** ADF + Minimum FFD (`ml/features.py` : `adf_stat`, `min_ffd`).
- [x] **Lot 3** Monte Carlo par séquences de trades (`portfolio/stress.monte_carlo_trades`).
- [x] **Lot 4** calendrier crypto 365 j (`data/audit` conscient de la classe).
- [x] **Lot 5** corrélation conditionnelle + kill-switch intraday (`make kill-check`).

### 🟢 PISTE D'ALPHA ACTIVE (2026-06-24) — PEAD significatif sur AAPL
- [x] **event-study AAPL/earnings SIGNIFICATIF** : CAR +2,0 % / 5 j · t=2,18 · placebo p=0,008 (`make event-study`).
- [ ] **VALIDER en cross-sectionnel** : event-study sur un PANIER (pas 1 ticker) → PEAD généralise-t-il ?
- [ ] **Backtester le signal `pead_signal`** comme stratégie (coûts + DSR>0.5 & PBO<0.5) avant d'y croire.
- [x] **#6 prediction-markets** (connecteur macro/actifs/résultats + page Macro) — FAIT [#249].
- [x] **Obsidian research-infra** (ledger + dashboard Dataview) — FAIT.
- [x] **Insider Form 4 buy/sell via XML** (`parse_form4_xml` + `net_insider_signal`) — FAIT.

### 🔭 Chantiers code restants (non urgents — palier déjà très bon)
- [ ] **Insider event-study par ticker** : `fetch_recent_form4` ne ramène que les dépôts GLOBAUX récents
  → requête EDGAR par CIK/ticker nécessaire pour l'historique d'une société (sinon 0 event).
- [ ] _(legacy)_ Obsidian research-infra — voir ci-dessus, fait.
  (frontmatter statut/dsr) + ledger d'essais `research/hypotheses.jsonl` + dashboard Dataview → boucle idée↔DSR.
- [ ] **#6** Facteur prediction-markets (Kalshi/Polymarket, API publiques gratuites) — vrai wedge data.
- [ ] **#9** GARCH(1,1) au sizing vol-target (module `packages/portfolio/garch.py` déjà présent) — derrière flag + A/B.
- [ ] **Suite #2** : extraction des sections du god-object `snapshot.py` en modules `packages/sections/*` + registre.
- [ ] **Burn-down ruff/mypy** (~3800) par lots → puis passer les gates **bloquants**.

### 📐 Méthode (chaque amélioration)
1. coder dans `preset_backtest.py` derrière un **flag** (comparer avant/après) ;
2. `make backtest-preset` + `make calibrate-preset` → vérifier **Calmar ↑ & MaxDD ↓** ;
3. **walk-forward OOS** (pas d'overfitting) ; 4. test pytest ; 5. PR → merge.
> ✅ **Sprint alpha 8/10** : #3 #5 #6 #1 #4 #2 #8 #10. **Audit « Conseil Suprême » 10/10 livrés** (gate
> publication, repro, lignage, property tests, isolation des fautes, PSR/honnêteté, Six Sigma, garde LLM,
> screener bout-en-bout, CI gate) + **verdict d'attribution honnête** (gaté sur t-stat). DSR≈0 confirmé en réel.

## ✅ Fait
- [x] **Sprint-0 Gouvernance (audit Conseil Suprême, 0 €)** : gate publication anti « site muet »
  (`check_build.py`), `_SNAP_VERSION` auto-hash + `make repro`, lignage/réconciliation
  (`packages/data/lineage.py`), tests de propriété hypothesis, `pip-audit` CI, manifeste honnêteté.
  Reportés : #2 god-object, #9 GARCH, #3 DSR-UI, #5 SPC, #8 validateur LLM, #6 prediction-markets.
- [x] **Design « radical » (robuste, 0 dép)** [PR #229] : aurora CSS (`body::after`), accents OKLCH
  (`@supports`+fallback), typo display (optical-sizing/ligatures/balance), nav desktop groupée (3 menus).
  Écartés (best practice, risque build CI) : WebGL/OGL, `next-view-transitions`, `next/font`.
- [x] **S13** Excellence op (drift PSI, audit trail, télémétrie, backup, tear sheets HTML/PDF)
- [x] **S12** Alertes multi-canal (moteur/sinks/throttle/handlers event-bus)
- [x] **S11** Analyse de portefeuille (relatif/risque/corrélation/attribution/stress/revue) + écrans portefeuille & positions
- [x] **S10** API FastAPI (payloads testés) + front Next.js (tokens+dashboard) + aperçu HTML statique
- [x] **S9** Module ML : triple-barrier, CV purgée/embargo, frac-diff, modèles, gouvernance champion/challenger
- [x] **S8** Exécution paper Alpaca + moteur live (parité backtest↔live) + idempotence + réconciliation
- [x] **S7** Macro & régime POINT-IN-TIME (vintages, délai publication, surprises, cartographie, cycle)
- [x] **S6** Providers réels yfinance/FMP via wrappers (fallback/cache/rate-limit) + DuckDB drop-in (même interface)
- [x] **S5** Feature store GOLD (anti-skew) + walk-forward + deflated Sharpe (anti-surapprentissage)
- [x] **S4** Univers MENSUEL (cadence + scheduler) + Russell 1000/3000 (iShares) + dédoublonnage par symbole
- [x] **S4** Module fondamental (ratios Vernimmen + valo Damodaran/DCF) → facteurs value/quality
- [x] **S3** Univers multi-marchés source-driven (CAC40/SP500/Nasdaq/NYSE/LSE/SBF120/MIB/Nikkei/KOSPI/CSI300/ETF/crypto/forex/commodities/indices) + snapshots datés point-in-time
- [x] **S3** Ranking multi-facteur explicable (momentum/trend/low-vol)
- [x] **S0** Monorepo + `core` (interfaces/models/registry) + `common` (config/log/event bus)
- [x] **S0** Vault initialisé + schéma vivant Mermaid + ADR-0001
- [x] **S0** Configs YAML d'exemple (universe/risk/factors/strategy) + tests d'archi

## P0 — Socle (sans quoi rien ne tient)
- [x] **CI** : **pytest bloquant** + **ruff & mypy informatifs** en GitHub Actions
  (`.github/workflows/ci.yml`), cache pip + concurrency. pre-commit en place (gitleaks/clé/gros fichiers).
  `(reste : ruff/mypy bloquants après burn-down du legacy ~3800)`
- [x] **Storage** : bronze/silver + **GOLD feature store** (SQLite, upsert idempotent, multi-TF, anti-skew) `(reste : DuckDB+Parquet, Alembic, Feast)`
- [x] **DataProvider** : synthetic + **yfinance** + wrappers **fallback/cache/rate-limit** + **FMP fondamental** + backend **DuckDB** pluggable `(reste : Finnhub/Alpaca temps réel)`
- [x] **Qualité DB** : contrats OHLCV (prix>0, cohérence, ts, gaps, fraîcheur) → **pipeline bloquant** `(reste : pandera/GE, alerte branchée)`
- [x] **Indicateurs** (familles, auto-enregistrés) : SMA/EMA/MACD/**régression log-linéaire z**/RSI/ROC/ATR/Bollinger — **tests anti-look-ahead verts** `(reste : ADX, Ichimoku, volume)`
- [x] **Backtest v0** : moteur event-driven maison + coûts réalistes (CostModel) — démo runnable `(reste : wrapper VectorBT recherche)`

## P1 — Cœur de la valeur (screening → paper trading)
- [x] **Macro & régime point-in-time** : MacroStore (vintages ALFRED) + FRED provider + surprises éco + cartographie macro→actifs + classifieur cycle `(reste : FMI/OCDE international, breadth)` + FMI/OCDE, **surprises éco (réalisé vs consensus)**, cartographie macro→actifs, classification cycle + risk-on/off → `RegimeState` quotidien point-in-time
- [x] **Fondamental & valo** : ratios Vernimmen + multiples/**DCF** Damodaran + facteurs **value/quality** sector-neutral `(reste : providers réels FMP/yfinance, DuPont détaillé, point-in-time réel)`
- [x] **Screening** : moteur de filtres YAML + scoring z-score cross-sectional
  (`packages/screening/` : `engine.py` filtres durs op/between/on_missing → survivants notés par
  composite z-score ; `metrics.py` réutilise le registre de facteurs + métriques prix ;
  `config/screening.yaml` ; 12 tests). Réutilise `_zscore` du ranking (DRY).
  **Branché** : section snapshot `screen` + `GET /api/screen` + dump statique + page front `/screener`
  (nav groupe Marché) + `make screen`. Smoke réel : 25 candidats / 929.
- [x] **Ranking multi-facteur** : momentum/trend/low-vol (z-score cross-sectional), pondérations **régime × classe** + applicabilité, top N **explicable** `(reste : value/quality du fondamental)`
- [x] **Stratégies** (plugins) : `ma_crossover` (trend), `rsi_reversion` (mean-rev), stop/target ATR `(reste : breakout, pairs, short, trailing, scaling)`
- [x] **Sizing** : `fixed_fractional`, `vol_target` (cap) `(reste : Kelly bridé, risk-parity)`
- [x] **Risk engine** : règles veto (R:R, max positions, expo/actif) + **kill-switch drawdown** — testé `(reste : expo par classe/corrélé)`
- [ ] **Portefeuille & risque global** : corrélation glissante + clustering, allocation (risk-parity/vol-target), **benchmarks BTC/SP500/Nasdaq/CAC40 + attribution**, métriques (Sharpe/Sortino/Calmar/DD via quantstats), VaR/CVaR, stress test (2008/COVID) + Monte Carlo, **revue experte CFA/FRM/CPA/CAIA** (ancrée sur métriques calculées)
- [x] **Exécution paper** : AlpacaBroker (interface Broker) + **moteur live (parité)** + retries idempotents + **réconciliation** + kill-switch `(reste : CCXT testnet crypto)`
- [x] **Journal de trades** (mémoire + export CSV) + **snapshot features à l'entrée** `(reste : persistance DuckDB + feature store)`
- [x] **Walk-forward + OOS + deflated Sharpe** (maison, stdlib) `(reste : Backtesting.py, Optuna pour l'optim fine)`

## P2 — Sophistication
- [ ] **ML** : triple-barrier + meta-labeling, features (techn.+fonda+macro point-in-time+frac. diff.), **purged & embargoed CV**, XGBoost/LightGBM, MLflow + champion/challenger, drift → re-train
- [ ] **Alertes** multi-canal (Telegram/Discord), hiérarchisées + throttling
- [ ] **Excellence op** : observabilité (logs JSON, dashboard santé), monitoring ML/drift, audit trail rejouable, sauvegardes testées, CI/CD Docker, tear sheets PDF
- [ ] **Front Next.js** : design system + API FastAPI + WebSocket ; écrans dashboard/screener/détail actif/**portefeuille-analyse**/positions/backtest
- [ ] **Live (optionnel, sur feu vert explicite)** : NautilusTrader, capital limité, monitoring renforcé
- [ ] **Boucle d'amélioration** : réentraînement walk-forward, drift, retour features→screening

## Garde-fous permanents (à ne jamais relâcher)
- Paper par défaut · pas de leverage par défaut · kill-switch testé avant tout live
- `.env` jamais commité · permissions exchange minimales (jamais retrait)
- Point-in-time partout · biais (survivorship/look-ahead/lag) traqués · Kelly bridé
