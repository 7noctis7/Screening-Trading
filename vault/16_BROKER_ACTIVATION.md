# 16 — Activation d'un broker réel (procédure & diagnostic)

> **État au 2026-07-03 : Bitmart reste OFF.** Ce document est le diagnostic LECTURE SEULE des
> verrous de sécurité crypto (BLOC 2) et la checklist d'activation *future*. Aucune activation
> n'est faite ici. Garde-fou CLAUDE.md : **jamais un broker en live tant que ses P0-SI-LIVE ne sont pas fermés.**

## Diagnostic Bitmart — triple verrou (confirmé, read-only)

Un ordre crypto RÉEL n'est envoyé que si **les trois** conditions tombent **simultanément**.
Il suffit qu'une seule soit active pour garantir le paper.

| # | Verrou | Où | Effet |
|---|--------|-----|-------|
| 1 | `dry_run=True` par défaut | `bitmart_broker.py:23` · `_live()` `:35` = `not dry_run and bool(key and secret)` | `run_live.py` ne passe `dry_run=False` que dans la branche `--live --yes`. Sans elle → aperçu seul, rien n'est envoyé. |
| 2 | `QUANT_NO_CRYPTO_LIVE=1` (défaut du cron) | `cron_live.sh:29-31` | Le cron `unset` `BITMART_API_KEY/SECRET/MEMO` → `_live()` False même sous `--live --yes`. Le rebalancement quotidien reste 100 % paper (Alpaca). |
| 3 | Clés `.env` absentes | `_live()` exige `key AND secret` | Sans clés, `submit/positions/equity/last_price` sortent inertes (`SUBMITTED`/`[]`/`0.0`). Aucun appel réseau d'ordre. |

**Lecture des positions** (`snapshot.py:415`, `BitmartBroker(dry_run=False)`) : chemin **read-only**
d'affichage ; sans clés `_live()` est False → `[]`. Ce n'est pas une voie d'ordre.

## P0-SI-LIVE Bitmart — état

- **#4 Idempotence** — ✅ **FERMÉ** (BLOC 1a, commit `ca3b71c`) : `submit()` court-circuite les
  `client_id` déjà vus (rejoue le résultat RÉEL, jamais de FILLED fabriqué) + `clientOrderId` transmis
  en `params` ccxt → dédup côté exchange. Un retry ne redouble plus l'ordre.
- **#5 Fills partiels** — ✅ **FERMÉ** (BLOC 1b `1ee8adb` + BLOC 1c `ca2648c`) : `PARTIALLY_FILLED` géré
  (ouverture à `filled_qty` réel ; `filled_qty=None` → aucune position + alerte CRITICAL) et l'alerte de
  réconciliation est branchée en prod (`packages/alerts/wiring.py`).

> Les deux bloquants Bitmart sont donc levés côté code. **L'activation reste néanmoins volontairement
> différée** : d'abord valider ces correctifs en conditions réelles (petits montants) avant tout capital significatif.

## Checklist d'activation FUTURE (à ne PAS exécuter aujourd'hui)

1. **Pré-requis** : P0-SI-LIVE #4/#5 fermés (fait). Sortie partielle à la revente (P2) idéalement traitée.
2. **Clés** : créer sur Bitmart une clé API **spot uniquement, lecture + trade, JAMAIS retrait** ;
   renseigner `BITMART_API_KEY/SECRET/MEMO` dans `.env` (jamais committé). Laisser `BITMART_MARKET=spot`.
3. **Canaux d'alerte** : configurer au moins un canal hors-console (`TELEGRAM_*` ou `DISCORD_WEBHOOK_URL`)
   pour recevoir les divergences de réconciliation et les fills partiels de qté inconnue.
4. **Débrider le cron** : `QUANT_NO_CRYPTO_LIVE=0` (verrou #2) — n'activer QUE lorsqu'on veut réellement
   trader la crypto en automatique. Tant qu'on teste à la main, laisser `=1`.
5. **Poche minuscule** : `QUANT_CRYPTO_PCT` très faible (ex. 0.02) + montants plafonnés ; vérifier le
   `min_cost` du marché. Premier run **manuel** : `python scripts/run_live.py --live --yes`.
6. **Vérifier** : réconciliation broker↔DB sans divergence, journal SQLite alimenté, aucune alerte CRITICAL,
   pas de doublon d'ordre (idempotence). Puis augmenter très progressivement.
7. **Rollback immédiat** : remettre `QUANT_NO_CRYPTO_LIVE=1` et/ou retirer les clés `.env` → retour paper instantané.

## Rappel

Alpaca est **toujours** en paper (`run_live.py:56`, `is_paper=True`) — actions jamais en réel, quoi qu'il arrive.
Le mandat du système : **paper par défaut**, capital réel seulement après la revue de courbe paper (RDV 2026-08-06, cf. `03_TODO.md`).
