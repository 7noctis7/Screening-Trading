# Déploiement gratuit — en ligne & sur téléphone (données réelles, sans Mac allumé)

On publie le **vrai front Next.js (parité totale avec `make start`** : notes 📄, page `/notes`,
Snowflake, Risque, Données, etc.) **exporté en statique** sur **GitHub Pages** via **GitHub Actions**,
qui **récupère les données réelles gratuitement dans le cloud** (yfinance / SEC EDGAR) à chaque build
et les **fige en JSON**. Résultat :

- 🌐 **URL permanente** : `https://<ton-user>.github.io/Screening-Trading/`
- 📱 **Installable sur téléphone** : ouvrir l'URL → « Ajouter à l'écran d'accueil » → vraie app, **hors-ligne**.
- 🔄 **Données réelles rafraîchies chaque nuit** (cron Actions), **Mac éteint**, **100 % gratuit**.
- 🔒 Ta `YAHOO.db` privée n'est **jamais** publiée : le build télécharge des données publiques fraîches.

> Limite : c'est un **instantané quotidien** (pas d'intraday temps réel) — idéal pour un terminal de
> recherche. Pour l'intraday live avec tes comptes, garde l'usage local (`make start`).

## Activation (une seule fois, 30 secondes)
1. Sur GitHub : **Settings → Pages → Build and deployment → Source = GitHub Actions**.
2. C'est tout. Le workflow `.github/workflows/pages.yml` se déclenche au prochain push sur `main`,
   chaque nuit, ou manuellement (**Actions → Déploiement PWA → Run workflow**).

## Tester en local
```bash
# Front complet exporté en statique (comme en ligne) — nécessite Node + apps/web/node_modules :
NEXT_PUBLIC_BASE_PATH="" python scripts/build_static_site.py   # → dossier site/
python -m http.server -d site 8080                             # http://localhost:8080
# Aperçu léger sans Node (terminal autonome) : make site
```

## Univers : téléphone **borné**, Mac **illimité**
- **En local (Mac)** : `make start` n'utilise PAS d'univers restreint → tu cherches sur **tous** les actifs.
- **En ligne / mobile (PWA)** : bornée à `config/mobile_universe.csv` = **watchlist fixe + top 200 par note**.
- Régénérer cette liste (en local, données réelles) :
  ```bash
  make watchlist            # → config/mobile_universe.csv (watchlist + top 200) + rapport Obsidian
  git add config/mobile_universe.csv && git commit -m "maj univers mobile" && git push
  ```
  La prochaine build Pages prend automatiquement la nouvelle liste. La **watchlist** (PLTR, TSLA,
  BMNR, CLSK, SBET, ABCL, SPCX + BTC/ETH/ONDO/NEAR/RENDER-USD) est **toujours incluse**.
  `make watchlist` écrit aussi `vault/04_Companies/_TOP200.md` (rapport classé) et les notes des
  valeurs suivies dans ton coffre Obsidian. Lancé aussi par le cron quotidien.

## Personnaliser
- **Univers / profondeur** : variables d'env dans le workflow (`QUANT_UNIVERSE`, fenêtre `--since`).
- **Fréquence** : champ `schedule.cron` du workflow.
- **Fondamentaux réels** : `QUANT_FUND=yf` (défaut du workflow) — bascule SEC EDGAR automatique.

## Alternatives (pour mémoire)
- **Tunnel Cloudflare** (`cloudflared tunnel --url http://localhost:8000`) : expose ton API locale
  avec **toutes** tes données et l'intraday — mais seulement quand ton Mac tourne.
- **HuggingFace Space** (`deploy/hf_space/`) : démo Gradio publique (synthétique).
