# AXE 1 — Pipeline point-in-time & robustesse du backtest

Retour à [[17_AUDIT_INSTITUTIONNEL]].

> Principe directeur (Isichenko) : **une donnée n'existe qu'à partir de l'instant où elle a
> été diffusée.** Une garde qui *vérifie* la règle est utile ; un schéma qui rend la
> violation *impossible à écrire* est ce qu'on cherche. Aujourd'hui `pit_guard.py` est du
> premier type.

## 1. Le schéma bitemporel (fondamentaux, révisions, indices)

Deux axes de temps, jamais un seul :
- **temps d'événement** (`period_end`) : la période à laquelle le fait se rapporte ;
- **temps de connaissance** (`knowledge_time`) : l'instant où il est devenu public.

```sql
CREATE TABLE fundamental_fact (
  entity_id       TEXT      NOT NULL,   -- ID PERMANENT (jamais le ticker)
  metric          TEXT      NOT NULL,   -- 'eps_diluted', 'revenue', 'shares_diluted'…
  period_end      DATE      NOT NULL,   -- fin de trimestre FISCAL
  fiscal_label    TEXT,                 -- 'Q3-2026'
  value           DOUBLE,
  unit            TEXT,
  knowledge_time  TIMESTAMP NOT NULL,   -- horodatage de DIFFUSION
  kt_quality      TEXT      NOT NULL,   -- 'EXACT' | 'INFERRED_LAG' | 'UNKNOWN'
  source          TEXT, source_url TEXT, ingested_at TIMESTAMP,
  PRIMARY KEY (entity_id, metric, period_end, knowledge_time)
);
```

**La clé primaire porte `knowledge_time`** : une révision est une NOUVELLE LIGNE. Aucun
`UPDATE` n'est autorisé sur la table — c'est un journal append-only. C'est la seule
construction qui interdit structurellement la fuite par révision.

Lecture « telle qu'on la voyait à t » :

```sql
SELECT DISTINCT ON (entity_id, metric, period_end) entity_id, metric, period_end, value
FROM fundamental_fact
WHERE knowledge_time <= :as_of AND kt_quality <> 'UNKNOWN'
ORDER BY entity_id, metric, period_end, knowledge_time DESC;
```

### Renseigner `knowledge_time` sans mentir
| Source | Bon horodatage | Piège |
|---|---|---|
| SEC EDGAR | `acceptanceDateTime` du dépôt | `filingDate` (date, pas heure) et surtout `periodOfReport` : utiliser ce dernier = fuite de 30 à 90 jours |
| Communiqué de résultats | horodatage 8-K, ou fil de presse | Le 10-Q arrive souvent **après** le communiqué : prendre le **plus tôt** des deux |
| Révisions d'analystes | date/heure de publication du broker | Les agrégateurs republient un consensus **rétro-corrigé** ; sans horodatage → `UNKNOWN` |
| Macro (FRED/ALFRED) | `realtime_start` du vintage | Déjà correct dans `packages/regime/real_macro.py` — c'est la référence interne à imiter |

Règle dure : `kt_quality='UNKNOWN'` ⇒ **exclu** des backtests, jamais remplacé par une valeur
par défaut. `INFERRED_LAG` ⇒ décalage conservateur documenté (dépôt 10-Q : `period_end + 40 j`
pour un *large accelerated filer*, `+ 45 j` sinon ; 10-K : `+ 60 / + 90 j`), et le résultat du
backtest doit être publié **avec et sans** ces lignes. Si le verdict dépend d'elles, il n'y a
pas de verdict.

### Appartenance à un indice
```sql
CREATE TABLE index_membership (
  index_id TEXT, entity_id TEXT,
  announce_time TIMESTAMP,   -- S&P annonce ~5 jours ouvrés avant
  effective_from DATE, effective_to DATE,   -- NULL = toujours membre
  PRIMARY KEY (index_id, entity_id, effective_from)
);
```
Univers à t = `effective_from <= t AND (effective_to IS NULL OR effective_to > t)`.
`announce_time` est une donnée de recherche à part entière (l'effet d'inclusion se joue entre
l'annonce et l'effectivité) — mais il ne doit **jamais** servir à définir l'univers.
Aujourd'hui `data/universe/wikipedia_source.py` lit la composition **du jour** : finding F9.

### Calendrier de résultats
Les dates de résultats sont elles-mêmes révisées : une société déplace son annonce. Stocker la
date finale, c'est savoir aujourd'hui ce qu'on ignorait la semaine dernière.
```sql
CREATE TABLE earnings_calendar_vintage (
  entity_id TEXT, period_end DATE,
  announced_date DATE, session TEXT,  -- 'BMO' | 'AMC' | 'DMT'
  knowledge_time TIMESTAMP,
  PRIMARY KEY (entity_id, period_end, knowledge_time)
);
```
Le `session` compte plus qu'on ne croit : un résultat **AMC** (après clôture) n'est
exploitable qu'à l'ouverture suivante. Un blackout de résultats calé sur la seule date
capture le mauvais jour une fois sur deux.

---

## 2. Corporate actions : l'algorithme correct (correctif F1)

### Ce qui ne va pas aujourd'hui
`yfinance ... history(auto_adjust=True)` renvoie des OHLC **rétro-ajustés à la date du
téléchargement**, et `_split_drift` relance un backfill complet quand il détecte une dérive.
Trois conséquences :

1. **Non-reproductibilité.** L'historique de 2015 n'est pas le même après le split NVDA de
   2024. Deux runs à deux dates ne sont pas comparables — or DSR et PBO comparent justement
   des essais successifs.
2. **Fuite par les niveaux.** Une série ajustée des dividendes incorpore dans les prix passés
   des dividendes futurs. Toute règle qui compare un prix à une **constante** est contaminée :
   filtre « prix > 5 $ », volume en dollars (prix ajusté × volume brut), seuils de
   capitalisation, niveaux ronds.
3. **Sur 1 h / 4 h**, une barre intraday brute recollée à un historique quotidien ajusté crée
   un trou artificiel = fausse cassure, faux momentum.

### Architecture cible : brut immuable + facteur calculé à la lecture
```sql
CREATE TABLE ohlcv_raw (              -- AS-TRADED, jamais réécrit
  entity_id TEXT, timeframe TEXT, ts TIMESTAMP,
  open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, volume DOUBLE,
  PRIMARY KEY (entity_id, timeframe, ts));

CREATE TABLE corporate_action (
  entity_id TEXT, ex_date DATE,
  action_type TEXT,        -- SPLIT | CASH_DIV | SPECIAL_DIV | SPINOFF | RIGHTS | REDENOM
  ratio DOUBLE,            -- split 2:1 → 2.0
  cash_amount DOUBLE, currency TEXT,
  announce_time TIMESTAMP, knowledge_time TIMESTAMP,
  PRIMARY KEY (entity_id, ex_date, action_type, knowledge_time));
```

### Algorithme d'ajustement `as_of = T`
1. Sélectionner les actions telles que `ex_date <= T` **et** `knowledge_time <= T`.
2. Facteur unitaire de l'action i (date ex `d_i`) :
   - split de ratio r : `f_i = 1 / r`
   - dividende D : `f_i = 1 − D / close_brut(dernière séance avant d_i)`
   (dividende ⇒ série **total return** ; pour une série *price return*, ne garder que les splits)
3. Facteur cumulé d'une barre datée t : `F(t | T) = produit des f_i pour tous les d_i > t`
   (actions futures **par rapport à la barre**, passées par rapport à T).
4. `close_ajusté(t | T) = close_brut(t) × F(t | T)` — idem O/H/L.
   **Volume** : `volume_ajusté(t) = volume_brut(t) × produit des r_i` (splits **seulement** ;
   ne jamais diviser le volume par le facteur dividende — erreur classique qui casse l'ADV).

### Les trois règles qui en découlent (à encoder comme tests)
- **R1** — toute comparaison prix ↔ constante utilise le **brut** (filtres de liquidité, tick,
  volume en dollars = prix brut × volume brut).
- **R2** — toute comparaison prix(t1) ↔ prix(t2) utilise l'**ajusté** avec le **même** `as_of`.
- **R3** — `F(t|T)` n'utilise jamais une action de `ex_date > T`.

Propriété utile : les **rendements** issus de la série ajustée sont invariants en T (les
facteurs se simplifient) ; seuls les **niveaux** ne le sont pas. D'où le partage brut/ajusté
ci-dessus, qui n'est pas une coquetterie mais la frontière exacte du problème.

### Cas particuliers
- **Radiation** : `delist_return = valeur de liquidation / dernier prix − 1`. Inconnue ⇒
  convention CRSP **−30 %** pour une radiation de performance, jamais 0, et drapeau
  `delist_return_source='ASSUMED'`. C'est ce qui manque pour que `survivorship_delta()`
  (livré en #321) produise enfin un Δ Sharpe honnête plutôt qu'un « UNCALIBRATED ».
- **Spin-off** : traité comme un dividende spécial de montant = valeur de marché du spin-off
  à l'ouverture du premier jour *when-issued*.
- **Crypto** : pas de split mais des **redénominations** de token (1:100) et des forks →
  `action_type='REDENOM'`, même mécanique.
- **Fusion** : la série s'arrête ; l'entité cible reçoit un `merger_return`. C'est pour cela
  que la clé est `entity_id` et jamais le ticker (un ticker est recyclé).

### Security master (biais du survivant, correctif structurel)
```sql
CREATE TABLE security_master (
  entity_id TEXT PRIMARY KEY, first_trade_date DATE, last_trade_date DATE,
  status TEXT,        -- ACTIVE | DELISTED | MERGED | LIQUIDATED
  delist_reason TEXT, delist_return DOUBLE, delist_return_source TEXT);
CREATE TABLE symbol_history (
  entity_id TEXT, symbol TEXT, valid_from DATE, valid_to DATE,
  PRIMARY KEY (entity_id, valid_from));
```
Le `symbol_history` est la pièce que presque tous les projets retail oublient : FB→META,
GOOG/GOOGL, les tickers recyclés. Sans lui, un backtest 2015 lit les prix de la mauvaise
société sans jamais lever d'erreur.

---

## 3. Multi-timeframe : l'état réel et ce qu'il faut décider

`packages/storage/bars_repo.py` porte bien `(symbol, timeframe, ts)` et `quality.py` connaît
`1m/5m/1h/4h/1d`. Mais **aucun ingest intraday n'existe** : `scripts/ingest_prices.py` est
quotidien. Les robots 1 h / 4 h n'ont pas de données.

Contraintes à regarder en face avant de choisir une source :
- **yfinance intraday** : 1 h limité à ~730 jours, 60 jours par requête, pas de vintage, pas
  d'horodatage fiable des ajustements. Correct pour explorer, disqualifié pour un backtest
  qu'on veut opposer à un recruteur ou à son propre capital.
- **Alpaca (offre gratuite)** : flux **IEX seul**, ~2 à 3 % du volume consolidé. Les OHLC sont
  approximativement justes, mais l'**ADV et le carnet ne le sont pas** — donc tout modèle
  d'impact calibré dessus est faux d'un facteur ~30 sur le volume. Utilisable pour le signal,
  **pas** pour le coût.
- **Crypto (CCXT / REST exchange)** : gratuit, complet, 24/24, et c'est *le* marché où ton
  chemin d'exécution existe déjà. **Recommandation : le premier robot intraday est un robot
  crypto** — pas par préférence, par disponibilité de données honnêtes.

Conventions à figer dès la première barre intraday (elles ne se rattrapent pas) :
1. Barres étiquetées par leur **heure de clôture**, stockage en **UTC**, séance dérivée d'un
   calendrier d'échange (jours fériés, demi-séances) et non d'un `resample` naïf.
2. Marquer les barres qui contiennent une **enchère** (ouverture/clôture). Le volume de
   l'enchère de clôture représente souvent 10 à 20 % de la séance : l'inclure dans un bucket
   15 h 45–16 h 00 fait croire à une liquidité qui n'existe pas pour un ordre continu.
3. Marquer les **halts** (LULD) : une barre en halt ne remplit aucun ordre.
4. Un seul `timeframe` de vérité (1 m si accessible) ; 1 h et 4 h **dérivés** par agrégation
   déterministe, jamais ingérés séparément (sinon deux vérités divergentes).

---

## 4. Reproductibilité : le contrat de run

Chaque exécution de backtest écrit dans le ledger, en plus du hash de config :
```
data_fingerprint = hash( entity_id triés ‖ intervalle de dates ‖ max(knowledge_time) utilisé
                         ‖ hash de corporate_action ‖ version du security_master )
```
Deux verdicts ne sont comparables que si `data_fingerprint` est identique **ou** si l'écart
est explicité. C'est l'extension naturelle de `packages/research/ledger.py`.

**Test CI à ajouter (`pit_replay`)** — la sentinelle qui vaut tous les audits :
1. reconstruire les features avec `as_of = T − k` ;
2. reconstruire avec `as_of = T`, tronquer à T − k ;
3. exiger l'égalité **bit à bit**.
`packages/common/pit_guard.stable_prefix` fait déjà exactement ça — il suffit de l'appliquer
aux **prix**, ce qui est aujourd'hui impossible et le deviendra après le § 2.
