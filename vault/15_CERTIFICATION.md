# Protocole de certification — rien n'entre sans preuve

> Statuts : DRAFT → CANDIDATE (gates passés) → **CERTIFIED** (en prod) → REVOKED.
> Re-certification : trimestrielle + à chaque changement de source/pipeline amont.
> Un composant REVOKED est débranché immédiatement, pas "surveillé".

## Gates par type de composant

### Source de données → CERTIFIED si
- [ ] Contrat pandera passé sur 100% de l'historique (types, bornes, UTC, index unique trié)
- [ ] `certify_ohlcv()` vert (high≥low, close∈[low,high], prix>0, pas de saut >50% non expliqué)
- [ ] Validée contre une **2e source indépendante** (`cross_provider.py`, taux de divergence <1%)
- [ ] Capacité point-in-time documentée (vintages ? date de publication ?) dans 05_DATA_SOURCES
- [ ] Fallback + rate-limiting + cache implémentés ; 30 jours d'ingestion stable sans intervention

### Indicateur technique → CERTIFIED si
- [ ] `certify_indicator()` vert : **invariance par troncature** (anti look-ahead), déterminisme, warmup respecté, pas d'inf
- [ ] Test unitaire vs implémentation de référence (TA-Lib) sur données réelles de la DB
- [ ] Comportement aux NaN/gaps défini et testé

### Facteur → CERTIFIED si
- [ ] Tous ses inputs sont des indicateurs/sources CERTIFIED
- [ ] Neutralisé secteur/bêta ; IC (information coefficient) stable across folds sur données réelles
- [ ] Normalisation cross-sectionnelle calculée uniquement sur l'info disponible à t

### Stratégie → CERTIFIED si
- [ ] leakage-hunter : zéro LEAK ; quant-critic : PASS
- [ ] Coûts complets en waterfall (frais, slippage, spread, borrow/funding)
- [ ] PSR > 0.95, PBO < 0.5, essais comptés au registre, paramètres sur plateau (±20% → perf similaire)
- [ ] Walk-forward OOS séparé de l'IS ; MinTRL calculé → gate le passage paper→live
- [ ] Shadow book paper : critères de promotion YAML atteints

### Modèle ML → CERTIFIED si
- [ ] Purged & embargoed CV uniquement ; features toutes issues de composants CERTIFIED
- [ ] Probabilités calibrées (courbe de calibration vérifiée sur données réelles)
- [ ] Bat le champion en OOS ET respecte le risque ; drift monitor branché

### Règle de risque → CERTIFIED si
- [ ] Testée unitairement sur cas limites ; **drillée** en paper (déclenchement réel vérifié, loggé)

## Registre
Tenir ici le tableau : composant | type | statut | date certif | preuves (liens tests/rapports) | prochaine re-certif.
Le /full-review vérifie ce registre ; tout composant en prod non-CERTIFIED = finding P0.

> ⚠️ **DETTE ASSUMÉE (audit 2026-07-05, P1-8 au TODO)** : registre non peuplé depuis ADR-0026
> (02/07) alors que des composants tournent en prod — le gate viole sa propre règle. À peupler
> en priorité (statut honnête plutôt que tableau vide silencieux) :

| Composant | Type | Statut | Date | Preuves | Re-certif |
|---|---|---|---|---|---|
| `SqliteTradeJournal` | storage | **UNCERTIFIED** (en prod) | — | 8 tests + contrat anti-fuite (`test_journal_sqlite.py`) — protocole /certify PAS déroulé | P1-8 |
| `AlpacaBroker` (paper) | execution | **UNCERTIFIED** (en prod) | — | tests TIF/mappers/crypto — protocole PAS déroulé | P1-8 |
| `live_journal` + `live_roundtrip` | execution | **UNCERTIFIED** (en prod) | — | 13 tests (Phases 1+2) — protocole PAS déroulé | P1-8 |
| Gate DSR/PBO (`psr.py`/`pbo.py`) | research | **UNCERTIFIED** (en prod) | — | tests + 8 négatifs publiés — protocole PAS déroulé | P1-8 |
| `run_live.py` (chemin prod) | script | **UNCERTIFIED** (en prod) | — | dry-run vérifié + garde-fous — protocole PAS déroulé | P1-8 |
