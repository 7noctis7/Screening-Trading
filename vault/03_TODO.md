# 03 — TODO (backlog priorisé)

> **Passation IA (2026-08-29)** — la carte technique consolidée est disponible dans
> `docs/AI_CODEBASE_MAP.md`. Elle décrit le flux complet, les frontières de sécurité et le protocole
> d'audit ; les priorités ci-dessous restent la seule roadmap opérationnelle.

> P0 = socle indispensable · P1 = cœur de la valeur (screening→trading paper) ·
> P2 = sophistication (ML, front, live). On n'ouvre P1 que quand P0 est vert.

- [x] **Copilote IA read-only (2026-08-29)** : chat global contextualisé par page, scopes/outils
      bornés, positions détaillées en opt-in, citations/as-of, garde numérique stricte et compteurs
      de rejets. Séparation AST : aucun import exécution/risque. L'IA reste hors chaîne d'ordres.
      Correctif Gemini : repli automatique vers l'API native si la couche compatible renvoie 404 ;
      comparaison portefeuille/Nasdaq désormais incluse dans les scopes overview/portfolio.
- [x] **Benchmarks dashboard non plats (2026-08-30)** : fusion par date du même ticker entre bases,
      sélection fraîche avant longueur, extension yfinance si le cache est périmé et alignement
      compte/indice sur les dates réelles. Un benchmark périmé est exclu, jamais forward-fill sur
      des mois avec l'étiquette « réel ».

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

## 🟡 Screening-Trading — reste ouvert (2026-08-22)
- [ ] **Câbler `impact.py` / `almgren_chriss.py` à l'exécution réelle** — écrits et testés, non
      branchés : les coûts d'impact sont ignorés au dimensionnement. (Débloqué par ADR-0038.)
- [x] **Débruitage RMT — TRANCHÉ le 26/08 (ADR-0039), sans changement de défaut.** Sur données
      réelles k médian = 1, donc le diagnostic dit « préférer l'inverse-vol » — mais la mesure
      rejette le RMT (ΔSharpe −0,07). Avec l'erreur-type, la contradiction se dissout : −0,07 est
      **indiscernable de zéro**. Ni le diagnostic ni la mesure ne justifient de bouger. On garde
      l'ERC et on documente.
- [ ] **P1 — Allonger la fenêtre du labo.** Le gate promeut à +0,05 alors que 126 pas ne résolvent
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
- [ ] **Accessibilité** : `/ml`, `/conviction`, `/portfolio` gardent leur vocabulaire technique.
- [ ] **Unifier les fenêtres du dashboard** : Sharpe 2,43 en haut, 1,07 dans le bloc honnêteté,
      0,98 pour le preset pur — trois fenêtres, aucune ne le dit dans les tuiles héros.
- [ ] **Bloc décision sur le screener** : il classe mais ne conclut pas (la fiche, elle, conclut).
- [ ] **Registre d'essais complet** sur `/methode` : publier ce qui a marché ET ce qui n'a pas —
      un lecteur ne peut pas juger un taux de réussite s'il ne voit qu'un côté.

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
