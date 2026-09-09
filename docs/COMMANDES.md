# Référence complète des commandes

> Toutes les cibles `make` du dépôt, groupées par intention. `make help` les liste aussi,
> dans l'ordre du `Makefile`. Chaque cible vit dans le `Makefile` à la racine ; le texte
> après `##` en est la description canonique — cette page en est le miroir organisé.

**Convention** : `$(PYTHON)` vaut `.venv/bin/python` si le venv existe, sinon `python3`.
Lancer un script directement avec `python3` échouera (les dépendances sont dans le venv).
Beaucoup de cibles acceptent `ARGS="…"` pour passer des options au script sous-jacent.

**Aucune commande de cette page n'envoie d'ordre réel.** Les seules qui touchent un courtier
sont `live-go` et `cron` (rebalancement paper), et elles forcent Alpaca en paper.

---

## 1. Installation & vie quotidienne

| Commande | Rôle |
|---|---|
| `make install` | installe les dépendances (uv) |
| `make setup` | installation guidée : venv, détection de la base de prix, build, cron — 1 commande |
| `make sync` | **récupère la branche de dev sans jamais créer de conflit** (jamais `git pull`) |
| `make test` | suite de tests — **à lancer avant tout commit** |
| `make coverage` | couverture réelle (pytest-cov) + rappel des trous |
| `make lint` | ruff + mypy |
| `make brief` | brief unifié de session (priorités, journal, changements, audit) |
| `make demos` | exécute les démos hors-ligne |

> ⚠️ **Ne jamais faire `git pull` sur la branche de dev.** Elle est réécrite à chaque
> déploiement ; un `pull` la voit divergée, tente une fusion et laisse des marqueurs de
> conflit dans les sources. `make sync` fait `fetch` + `reset --hard` et abandonne d'abord
> toute fusion en cours.

## 2. Lancer le terminal

### Poste de travail (macOS / Linux, mode manuel)

| Commande | Rôle |
|---|---|
| `make start` | tout-en-un : maj du code, arrêt des vieux process, API en fond, site |
| `make stop` | arrête l'API et le site |
| `make api` | API FastAPI seule sur `localhost:8000` (stable, sans reload) |
| `make api-dev` | API avec reload du code uniquement (ne surveille pas `data/`) |
| `make api-lan` | API accessible depuis le téléphone sur le même Wi-Fi |
| `make web` | front Next.js seul sur `localhost:3000` |
| `make interactive` | preview autonome en un seul fichier HTML, sans rien installer |

### Serveur permanent (Linux, services systemd)

Sur une machine qui doit survivre à la déconnexion SSH, les services remplacent
`make start` — qui refuse alors de démarrer pour ne pas entrer en conflit sur le port.

| Commande | Rôle |
|---|---|
| `make services` | installe l'API et le front en services systemd |
| `make up` | **tout-en-un serveur** : `sync` + relance des services + attente que le front réponde |
| `make services-restart` | relance les services après un `make sync` (reconstruit le front) |
| `make services-logs` | suit les logs des services |

> Le front tourne en mode **production** (`build` + `start`), pas en `next dev` : un serveur
> de développement supporte mal d'être un service au long cours, et son processus enfant
> survivait aux déconnexions SSH en gardant le port occupé.

### Site statique (même rendu qu'en ligne)

| Commande | Rôle |
|---|---|
| `make site` | watchlist + données figées + export Next.js → `localhost:8080` |
| `make site-lite` | variante légère sans Node (terminal autonome) |
| `make watchlist` | (re)génère la watchlist qui borne la PWA en ligne |

> ⚠️ **Après un `make site`, `next dev` ne redémarre pas** : le dossier `.next` reste en mode
> export statique, illisible par le serveur de développement. Faire
> `cd apps/web && rm -rf .next && npm run dev`.

## 3. Données

| Commande | Rôle |
|---|---|
| `make ingest` | backfill des prix réels → base locale |
| `make daily` | mise à jour incrémentale quotidienne |
| `make ingest-crypto` | prix des principales cryptos → base crypto |
| `make ingest-macro` | vintages macro **point-in-time** (clé FRED gratuite requise) |
| `make ingest-mktcap` | capitalisations boursières |
| `make ingest-delisted` | détecte les titres délistés (anti-biais du survivant) |
| `make audit` | audit d'intégrité des bases (complétude, exactitude, point-in-time) — `ARGS=--strict` pour gater |
| `make contracts` | **gate** contrats OHLCV : bloque l'impossible (aussi en CI) |
| `make list-db` | liste ce que contient la base de prix (classes, secteurs) |
| `make diag-fusion` | les bases de prix sont-elles d'accord ? désaccords mesurés par symbole |
| `make diag-source-crypto` | confronte chaque série crypto à une référence indépendante |
| `make audit-univers` | trie les symboles sans nom en périmés / vivants |
| `make noms-univers` | comble les noms manquants depuis les fournisseurs (jamais devinés) |
| `make macro-verify` | vérifie que chaque identifiant macro existe et publie encore |
| `make bench-backend` | SQLite vs DuckDB en lecture OHLCV — règle de décision écrite avant le run |

### Cache de prix partagé

| Commande | Rôle |
|---|---|
| `make hf-push` / `make hf-pull` | cache OHLCV souverain (contourne les limites de débit du fournisseur) |
| `make journal-pull` / `make journal-push` | journal de trades ↔ stockage **privé** (jeton requis) |

## 4. Recherche & backtests

| Commande | Rôle |
|---|---|
| `make backtest-preset` | preset best-practice + overlay de volatilité gérée, sur vos données |
| `make calibrate-preset` | meilleure combinaison (DD × top-K × bande) par **Sharpe déflaté** |
| `make preset-report` | rapport HTML autonome (courbes + drawdowns) |
| `make preset-lab` | labo Sharpe/Sortino : cap adaptatif + overlay risque, mesurés puis gatés |
| `make backtest-ml` | backtest ML walk-forward point-in-time |
| `make backtest-weighting` | équipondéré / inverse-vol / min-var / risk-parity, net de frais |
| `make backtest-earnings` | dérive post-annonce de résultats |
| `make backtest-breakout` | cassures de canal + règle de mesure |
| `make backtest-sentiment` | le signal sentiment a-t-il un edge ? |
| `make backtest-megacap` | top-N méga-caps contre les indices réels |
| `make backtest-pead-smid` | dérive post-résultats small/mid **net de coûts** + gate DSR/PBO |
| `make index-core` | balayage cœur indiciel + preset sur données réelles |
| `make index-core-stress` | stress-test baissier : perte par ratio de cœur pendant les krachs |
| `make index-core-regime` | allocation adaptative haussier/range/baissier contre allocation fixe |
| `make coeur-multi` | cœur multi-actifs contre cœur mono-actif, règle écrite d'avance |
| `make crypto-core` | cœur crypto : référence + panier de majeures |
| `make ledger-sweep` | performance réaliste (journal discret) par combinaison de paramètres |

### Le gate d'honnêteté

| Commande | Rôle |
|---|---|
| `make alpha-lab` | 5 hypothèses pré-enregistrées passées au gate 4 étages |
| `make log-alpha` | **logue un essai** d'hypothèse (registre anti p-hacking) |
| `make sync-alphas` | propage le registre vers les notes du vault |
| `make balayage-ic` | balaie horizons × classes d'actifs, corrigé Benjamini-Hochberg (long) |
| `make ic-screening` | information coefficient hors échantillon du score de sélection (long) |
| `make sensitivity` | sensibilité des seuils — anti sur-optimisation |
| `make repro` | manifeste de reproductibilité (sha git + empreintes config/données) |
| `make event-study` | event-study sur un ticker ou un panier |
| `make event-study-smid` | dérive post-résultats sur small/mid-caps |
| `make funding-study` | event-study funding crypto + placebo |
| `make regime-study` | un indicateur de sentiment est-il contrarian ? gate placebo |
| `make breakout-study` | les cassures de canal prédisent-elles un rendement ? gate placebo |
| `make screen-niche` | exploitabilité d'un univers (score 0-100) avant de s'y engager |
| `make banc-swing` | un moteur de stratégie mérite-t-il d'être branché ? **mesure, ne branche rien** |
| `make labs` | les quatre bancs de mesure d'un coup |
| `make valider-nouveautes` | valide sur données réelles les modules non branchés (lecture seule) |
| `make certification` | **les modules disent-ils la vérité sur leur place ?** (déclaré hors-prod vs réellement atteignable) |

## 5. Sélection & modèle

| Commande | Rôle |
|---|---|
| `make screen` | screener à filtres → candidats triés par z-score |
| `make crypto-screen` | screener crypto en langage naturel |
| `make crypto-cockpit` | cockpit crypto marché |
| `make crypto-brief` | note de marché crypto → vault |
| `make train` | entraîne le modèle ML **hors-ligne** → artefact (le serving ne réentraîne jamais) |
| `make microstructure-poc` | flux d'ordres et toxicité en direct (sans clé) |

## 6. Exécution paper

| Commande | Rôle |
|---|---|
| `make live` | **aperçu** des ordres du prochain run réel — n'envoie rien |
| `make live-sim` | simule un portefeuille neuf à capital imposé (ne décrit pas le compte) |
| `make live-go` | **exécute en paper** — clés API requises, courtier actions forcé en paper |
| `make live-cron-install` | active le rebalancement paper automatique |
| `make live-cron-uninstall` | le désactive |
| `make kill-check` | kill-switch intraday : drawdown réel contre seuil — **aucun ordre** |
| `make risk-check` | exposition brute recommandée (drawdown taper × volatilité prévue) |
| `make paper-watch` | watchdog de dérive paper contre backtest — code de sortie ≠ 0 si dérive |
| `make bitmart-check` | diagnostic courtier crypto **en lecture seule**, zéro ordre |
| `make slippage` | slippage réel mesuré (décision → fill) |
| `make rdv-paper` | verdict GO/NO-GO mécanique du rendez-vous d'évaluation |

> **Le mode réel exige `--live` ET `--yes` ET des clés présentes.** Si l'un des trois manque,
> le moteur retombe en aperçu. Le courtier actions est forcé en paper dans le code.

### Le créneau d'exécution

Le planificateur se réveille **toutes les heures** et demande à
`scripts/fenetre_execution.py` s'il faut agir. La réponse se calcule dans l'heure du
**marché** : une heure de cron figée dériverait deux fois par an, les changements d'heure
américain et européen ne tombant pas le même dimanche.

```bash
.venv/bin/python scripts/fenetre_execution.py --verbeux   # dit aussi pourquoi il ne faut PAS agir
```

Vingt-trois réveils quotidiens sortent en silence : un journal plein de « rien à faire » ne
protège de rien.

## 7. Journal de trades

| Commande | Rôle |
|---|---|
| `make verify-journal` | **le contrôle de routine** : le cron alimente-t-il le journal ? |
| `make diag-journal` | réconcilie le journal avec la courbe du compte réel |
| `make diag-surfermeture` | d'où vient l'écart quand le courtier détient ce que le journal ignore |
| `make diag-pv-latente` | combien de plus-value latente a été rendue, ligne par ligne |
| `make diag-creneau` | à quelle heure exécuter : décompose le rendement nuit / séance |
| `make turnover-audit` | **coût réel du rebalancement** — répond `UNCALIBRATED` si le journal est trop maigre |
| `make calibrer-seuil` | calibre le seuil d'écart sur le vrai panneau — n'écrit rien |
| `make diag-alignement` | d'où vient le gain de l'alignement par date |

### Réparation (à manier avec précaution)

| Commande | Rôle |
|---|---|
| `make reparer-journal` | chaîne complète de réparation, dans l'ordre, **fail-closed** |
| `make completer-ouvertures` | reconstitue les achats exécutés par le courtier — **simulation par défaut** |
| `make reconcilier-journal` | ferme les lots orphelins avec les fills réels — **simulation par défaut** |
| `make annuler-ventes` | retire les lots « ouverts » qui sont en fait des ventes |
| `make annuler-chronologie` | retire les allers-retours dont la sortie précède l'entrée |
| `make annuler-doublons` | retire les lots dont le réalisé double une correction nommée |

> Toutes ces cibles **simulent par défaut** et refusent d'écrire un prix que le marché n'a
> jamais coté. Lire la sortie de la simulation avant d'appliquer quoi que ce soit.

## 8. Rapports & mémoire

| Commande | Rôle |
|---|---|
| `make reports` | notes d'analyse par société → dossier daté + vault |
| `make analytics` | rapport de performance → vault |
| `make tearsheet` | tear sheet de performance (HTML + PDF) |
| `make vault-sync` | régénère le coffre de notes depuis la base de prix |
| `make vault-lint` | intégrité du vault : liens morts, orphelins, doublons, **dates futures** |
| `make vault-search` | recherche sémantique locale — `Q="ta question"` |
| `make vault-ask` | assistant ancré sur le vault, réponse citée |
| `make notion-sync` | miroir des notes vers un espace externe (jeton requis) |
| `make supabase-kpis` | historique des indicateurs vers une base cloud (clés requises) |
| `make preview` | régénère les aperçus HTML |

## 9. Intégrations

| Commande | Rôle |
|---|---|
| `make mcp-tv` | serveur d'outils graphiques (overlays, alertes) |
| `make mcp-selftest` | auto-vérification de ces outils, sans handshake |
| `make mcp-overlays` | calcule les cônes de risque et blackouts, les pousse au graphe |
| `make alerts-test` | envoie une alerte de test sur les canaux configurés |
| `make cron-install` / `cron-uninstall` | maj quotidienne automatique des données |
| `make cron` | la maj quotidienne complète, à la main |

---

## Variables d'environnement

Toutes optionnelles, toutes documentées dans `.env.example`. Absentes, les fonctionnalités
concernées se désactivent proprement — rien ne plante.

### Données & fonctionnalités

| Variable | Effet |
|---|---|
| `QUANT_PRICE_DB` | chemin de votre base de prix locale |
| `QUANT_HISTORY_DAYS` | profondeur d'historique chargée |
| `QUANT_NEWS=1` | actualités RSS réelles (sinon repli sur la tendance 3 mois) |
| `QUANT_FUND` | source des fondamentaux |
| `QUANT_UNIVERSE` | restreint l'univers étudié |
| `QUANT_CRYPTO`, `QUANT_PREDMKT` | sources gratuites optionnelles |

### Garde-fous de risque (lus dans l'environnement seul — c'est ce qui les rend non contournables)

| Variable | Défaut | Effet |
|---|---:|---|
| `QUANT_RISK_MAX_WEIGHT` | `0.20` | une ligne ne dépasse pas 20 % du compte |
| `QUANT_RISK_MAX_POSITIONS` | `40` | au-delà, plus aucune ouverture |
| `QUANT_RISK_MAX_ORDER_PCT` | `0.15` | un ordre ne dépasse pas 15 % du compte |
| `QUANT_RISK_MAX_GROSS` | `1.00` | **aucun levier, jamais** |
| `QUANT_MIN_POSITION` | `1000` | plancher de ligne |
| `QUANT_DISJONCTEUR` | *désarmé* | coupe-circuit sur la perte du jour |
| `QUANT_NO_CRYPTO_LIVE` | `1` | neutralise toute place crypto réelle |
| `QUANT_IBKR_ENABLE` | *absent* | opt-in d'un courtier tiers — **compte démo uniquement** |

### Réseau & accès

| Variable | Effet |
|---|---|
| `QUANT_CORS_ORIGINS` | élargit les origines autorisées (verrouillé sur la boucle locale par défaut) |
| `QUANT_WEBHOOK_TOKEN` | protège les endpoints en écriture ; absent → boucle locale uniquement |
| `NEXT_PUBLIC_API_URL` | adresse de l'API vue par le front |

### Clés externes (toutes facultatives)

Fournisseur de fondamentaux, série macro, cache de données, miroir de notes, base cloud,
canaux d'alerte, modèle de langage local. **Aucune n'est requise** pour faire tourner le
projet : chaque intégration se coupe proprement si sa clé est absente.

> 🔐 Les clés vivent dans `.env`, qui est ignoré par git. Le dépôt est public et un scanner
> de secrets tourne en intégration continue **et** en pre-commit.
