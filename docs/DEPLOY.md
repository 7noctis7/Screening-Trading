# Déploiement gratuit — en ligne & sur téléphone (données réelles, sans Mac allumé)

Le terminal autonome (`apps/web/preview/interactive.html`) est une **PWA** (installable, hors-ligne).
On le publie sur **GitHub Pages** via **GitHub Actions**, qui **récupère les données réelles
gratuitement dans le cloud** (yfinance / SEC EDGAR) à chaque build. Résultat :

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
python scripts/build_site.py        # → dossier site/ (index.html + PWA)
# puis : ouvrir site/index.html, ou servir : python -m http.server -d site 8080
```

## Personnaliser
- **Univers / profondeur** : variables d'env dans le workflow (`QUANT_UNIVERSE`, fenêtre `--since`).
- **Fréquence** : champ `schedule.cron` du workflow.
- **Fondamentaux réels** : `QUANT_FUND=yf` (défaut du workflow) — bascule SEC EDGAR automatique.

## Alternatives (pour mémoire)
- **Tunnel Cloudflare** (`cloudflared tunnel --url http://localhost:8000`) : expose ton API locale
  avec **toutes** tes données et l'intraday — mais seulement quand ton Mac tourne.
- **HuggingFace Space** (`deploy/hf_space/`) : démo Gradio publique (synthétique).
