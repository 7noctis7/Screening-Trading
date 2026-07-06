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

### Exécution / Infra (broker, journal, chemin de prod) → CERTIFIED si  *(ajouté 2026-07-06, P1-8)*
- [ ] Tests unitaires verts SANS réseau (fakes) : idempotence, fills partiels, cas limites
- [ ] Idempotence prouvée : re-run du même jour = zéro doublon (test + observation réelle)
- [ ] 20 jours ouvrés d'exploitation paper SANS intervention manuelle (log launchd/cloud)
- [ ] Alerte branchée sur CHAQUE échec silencieux possible (submit, réconciliation, journal)
- [ ] Round-trip vérifié sur ≥1 vente réelle (exit/PnL cohérents avec le relevé broker)

### Règle de risque → CERTIFIED si
- [ ] Testée unitairement sur cas limites ; **drillée** en paper (déclenchement réel vérifié, loggé)

## Registre
Tenir ici le tableau : composant | type | statut | date certif | preuves (liens tests/rapports) | prochaine re-certif.
Le /full-review vérifie ce registre ; tout composant en prod non-CERTIFIED = finding P0.

> Passe P1-8 du 2026-07-06 : gates « exécution/infra » ajoutés au protocole, 5 composants évalués
> sur preuves disponibles → **CANDIDATE** (pas de CERTIFIED de complaisance : les gates terrain
> — 20 j, drills, relevés — n'ont pas encore pu être constatés).

| Composant | Type | Statut | Date | Preuves | Gates restants → CERTIFIED |
|---|---|---|---|---|---|
| `SqliteTradeJournal` | exécution/infra | **CANDIDATE** | 2026-07-06 | 8 tests (UPSERT idempotent, contrat anti-fuite, legacy requêtable) | 20 j d'exploitation sans intervention |
| `AlpacaBroker` (paper) | exécution/infra | **CANDIDATE** | 2026-07-06 | tests TIF crypto/actions, mappers, notional ; paper forcé dans le code | 20 j d'exploitation · alerte sur échec submit observée en réel |
| `live_journal` + `live_roundtrip` | exécution/infra | **CANDIDATE** | 2026-07-06 | 13 tests (features à la décision, FIFO, scission, MFE/MAE, jamais de prix inventé) | ≥1 round-trip réel vérifié vs relevé broker · 20 j |
| Gate DSR/PBO (`psr.py`/`pbo.py`) | research | **CANDIDATE** | 2026-07-06 | suite research 99 tests ; N=essais distincts ; 8 négatifs publiés (le gate rejette VRAIMENT) | revue quant-critic dédiée + doc plateau de paramètres |
| `run_live.py` (chemin prod) | script | **CANDIDATE** | 2026-07-06 | dry-run par défaut, anti-levier, kill-switch TV, alertes branchées, journal 2 sens | drill kill-switch loggé en réel · 20 j sans intervention |

> Promotion CANDIDATE → CERTIFIED : mécanique, à l'issue des 20 j paper (≈ RDV 2026-08-06),
> preuves = logs launchd/cloud + relevés broker. Aucun statut accordé sans la preuve terrain.
