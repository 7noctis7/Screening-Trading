# Passer en données RÉELLES + persistance + déploiement

Ce guide explique comment alimenter le terminal avec de vraies données de marché
(yfinance / FMP), brancher votre base historique **YAHOO.db**, l'enrichir chaque jour,
ré-entraîner le ML, et utiliser le site **en ligne / en local / sur mobile**.

---

## 1. Comment le projet choisit sa source de données

`apps/api/snapshot.py` → `_load_prices()` applique cet ordre :

1. **Base réelle locale** si présente : variable d'environnement `QUANT_PRICE_DB`,
   sinon `data/YAHOO.db`, sinon `data/market.db`.
2. **Synthétique sectorisé** en repli (et pour les symboles absents de la base).

Le mode effectif est affiché partout (`meta.mode` : `réel (YAHOO.db)`, `mixte (N réels / …)`
ou `synthetic`) et dans le bandeau « Données au … » de chaque onglet.

Le lecteur `packages/data/providers/db_provider.py` **auto-détecte le schéma** :
- **format long** : une table avec colonnes `symbol/ticker`, `date`, `open/high/low/close/volume` ;
- **format par ticker** : une table par symbole (nom de table = ticker), au minimum `date` + `close`.

> Aucune dépendance hors `sqlite3` (stdlib). `.db/.sqlite/.duckdb` sont git-ignorés.

### Utiliser votre YAHOO.db (4,3 Go) tout de suite
```bash
export QUANT_PRICE_DB=/chemin/vers/YAHOO.db
uvicorn apps.api.main:app --reload          # l'API lit la base réelle
python apps/web/preview/build_interactive.py # ou la preview autonome
```
Les symboles présents dans la base sont tradés/screenés/affichés en **réel** ; les autres
restent synthétiques pour garder l'univers complet.

---

## 2. Pourquoi YAHOO.db ne peut pas aller dans GitHub — et quoi faire

GitHub refuse les fichiers > 100 Mo et déconseille les dépôts volumineux. **Ne committez pas
la base** (déjà couverte par `.gitignore`). Trois stratégies, par ordre de simplicité :

| Option | Pour qui | Comment |
|---|---|---|
| **Local + env var** (recommandé pour démarrer) | usage perso / 1 machine | garder `YAHOO.db` hors dépôt, pointer `QUANT_PRICE_DB` dessus |
| **Stockage objet** (S3 / GCS / R2 / Backblaze) | en ligne / CI / équipe | uploader la base, la télécharger au boot du serveur (script de setup), puis `QUANT_PRICE_DB` |
| **Git LFS** | versionner de gros binaires | `git lfs track "*.db"` — coûteux à 4,3 Go (quotas), à éviter sauf besoin de versionnage |

Pour un hébergement en ligne, l'option **stockage objet** est la bonne : la base vit dans un
bucket, le serveur la récupère (ou l'attaque en streaming via DuckDB `read_parquet`/httpfs si
vous convertissez en Parquet partitionné par symbole).

---

## 3. Ingestion + mise à jour QUOTIDIENNE (append, jamais d'écrasement)

`scripts/ingest_prices.py` écrit dans `data/market.db` (table `prices`, clé primaire
`(symbol, date)` → idempotent) :

```bash
# Backfill complet de l'univers (une fois)
python scripts/ingest_prices.py --since 2015-01-01

# Mise à jour incrémentale (chaque jour, après clôture) : n'ajoute que les barres manquantes
python scripts/ingest_prices.py --daily

# Quelques tickers seulement
python scripts/ingest_prices.py --symbols AAPL NVDA PLTR --since 2020-01-01
```

- Source : **yfinance** par défaut ; **FMP** en repli si `FMP_API_KEY` est défini.
- La barre du jour vient **s'empiler** sur l'historique de **chaque actif** — la base grossit,
  rien n'est écrasé. Le snapshot a un TTL de 15 min et une fenêtre qui se termine « aujourd'hui »,
  donc les nouvelles données apparaissent automatiquement.

### Automatiser (cron / GitHub Actions)
```cron
# tous les jours de semaine à 23h10
10 23 * * 1-5  cd /chemin/projet && python scripts/ingest_prices.py --daily
```
`scripts/scheduler.py` peut orchestrer ingestion → contrôles qualité → rebuild snapshot.

> Pour **enrichir directement depuis YAHOO.db** : pointez `QUANT_PRICE_DB` dessus ; pour la
> faire grandir avec yfinance, fusionnez `market.db` dans `YAHOO.db` (même schéma `prices`)
> ou utilisez `market.db` comme base vivante et gardez YAHOO.db comme socle historique.

---

## 4. Ré-entraîner le ML sur la vraie base

Le score ML (`apps/api/snapshot.py` → `_ml_section`) est entraîné **en cross-section sur tout
l'univers chargé**. Dès que `QUANT_PRICE_DB` pointe une base réelle, l'entraînement se fait sur
les **vraies séries** (mêmes features : momentum 1m/3m, tendance vs MM50, RSI, volatilité ;
label = hausse à ~1 mois ; validation hors-échantillon AUC).

Boucle d'amélioration continue :
1. `ingest_prices.py --daily` (nouvelles barres) →
2. rebuild snapshot (le ML se ré-entraîne automatiquement sur l'historique élargi) →
3. le score ML enrichit le screener et confirme les setups →
4. (production) brancher l'exécution paper/live (`packages/execution`, Alpaca paper) pour des
   trades réels, avec garde-fous risque (`packages/risk`).

Pour une vraie pipeline MLOps (CV purgée + embargo, triple-barrière, drift, gouvernance), voir
`packages/ml/` — déjà présent et conforme López de Prado.

---

## 5. En ligne / en local / sur mobile

- **Local** : `uvicorn apps.api.main:app --reload` + `cd apps/web && npm run dev`.
  Ou, sans rien installer, ouvrir la preview autonome `apps/web/preview/interactive.html`.
- **En ligne** : API (Render/Fly/railway, `uvicorn`) + front Next.js (Vercel). Définir
  `NEXT_PUBLIC_API_URL` côté front et `QUANT_PRICE_DB` (ou téléchargement depuis le bucket)
  côté API.
- **Mobile** : l'interface est **responsive** (grilles qui s'adaptent, onglets défilables au
  doigt, horloge masquée sur petit écran, tableaux à défilement). La preview HTML s'ouvre
  directement dans le navigateur du téléphone ; le front Next.js est utilisable en PWA.

---

## 6. Monte-Carlo — déjà intégré, et pourquoi c'est pertinent

Oui, c'est pertinent **et déjà en place** :
- **proba de ruine / VaR de trajectoire / pire drawdown** (`packages/portfolio/stress.py:monte_carlo`,
  onglet Portefeuille → Risque) ;
- **éventail de projection à 1 an** (`mc_projection`, cône p5–p95 + médiane) ajouté à l'onglet
  Portefeuille → quantifie l'incertitude des résultats futurs.

C'est complémentaire du backtest (passé) : le MC donne la **distribution** des futurs possibles,
indispensable pour un profil offensif (dimensionnement, tolérance au drawdown, proba d'atteindre
un objectif).

---

## 7. Automatisation quotidienne (cron / launchd)

Mise à jour automatique des prix + régénération du terminal, chaque jour de bourse :

```bash
make cron          # exécute scripts/cron_daily.sh (idempotent : append, jamais d'écrasement)
```

**crontab** (Linux/macOS) — tous les jours de semaine à 22h30 (après clôture US) :
```cron
30 22 * * 1-5 /Users/vous/Screening-Trading/scripts/cron_daily.sh >> /tmp/quant_daily.log 2>&1
```

**launchd** (macOS, recommandé) — `~/Library/LaunchAgents/com.quant.daily.plist` :
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.quant.daily</string>
  <key>ProgramArguments</key>
  <array><string>/Users/vous/Screening-Trading/scripts/cron_daily.sh</string></array>
  <key>StartCalendarInterval</key><dict><key>Hour</key><integer>22</integer><key>Minute</key><integer>30</integer></dict>
  <key>StandardOutPath</key><string>/tmp/quant_daily.log</string>
  <key>StandardErrorPath</key><string>/tmp/quant_daily.err</string>
</dict></plist>
```
Activation : `launchctl load ~/Library/LaunchAgents/com.quant.daily.plist`.

## 8. Tear sheet de performance (HTML + PDF)

Rapport de performance autonome (métriques clés + courbe d'equity) :
```bash
make tearsheet     # → out/tearsheet.html (toujours) + out/tearsheet.pdf (si reportlab installé)
```
