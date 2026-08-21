# 19 — AUDIT BOARD : quant · architecture · cockpit · business (2026-08-20)

> Audit de `main` selon les 4 piliers demandés. Les piliers 1 et 3-quant sont largement
> couverts par [[17_AUDIT_INSTITUTIONNEL]] et [[18_MODULES_AVANCES]] — cette note ne les
> répète pas, elle traite ce qui n'avait **pas** encore été regardé : asynchronisme,
> calendrier de marché, cannibalisation Core/Satellite, cycle de vie des ordres, cockpit
> de risque, et la question business.

---

## At a Glance — matrice de responsabilité

| Pôle | Constat dominant | Sévérité | Livré aujourd'hui |
|---|---|---|---|
| **Quant** | Régime et persistance non mesurés causalement ; aucune règle ne dit quelle FAMILLE de stratégie a le droit d'exister sur un actif | HAUTE | `regime/hurst.py`, `regime/hmm_causal.py` |
| **Architecture** | Pas de calendrier de marché, pas de boucle asynchrone : crypto 24/7 et séances régulées partagent la même boucle quotidienne | **BLOQUANTE** pour l'intraday | finding F11/F12 documentés, non résolus |
| **Architecture** | Le Satellite peut vendre à découvert ce que le Core accumule — perte sèche invisible | HAUTE | `portfolio/netting.py` |
| **Cockpit** | 20 pages front, aucune matrice d'exposition factorielle, aucune CVaR 99 %, aucune attribution Core vs Satellite | MOYENNE | `netting.attribution` rend l'attribution calculable |
| **Cycle de vie ordre** | Journal d'ENTRÉES + appariement FIFO, mais pas de machine à états d'ordre ni de log d'événements immuable | HAUTE si live | spécifié § 4 |
| **Business** | L'actif défendable n'est pas l'alpha (DSR ≈ 0 assumé) mais l'infrastructure d'intégrité de recherche | — | analyse § 5 |

---

## 1. Nouveaux findings de code

| # | Sévérité | Constat |
|---|---|---|
| **F11** | **HAUTE** | **Aucun calendrier de marché dans le dépôt.** `grep market_hours\|is_open\|calendar` sur `packages/` ne renvoie que mes propres constantes de `impact.py`. Conséquences : les barres crypto (24/7) et actions (6 h 30/j, jours fériés, demi-séances) sont traitées par la même boucle ; une volatilité « quotidienne » mélange des jours de 24 h et de 6 h 30 ; un blackout de résultats calé sur un nombre de barres traverse les week-ends de façon incohérente entre classes d'actifs. |
| **F12** | **HAUTE (si intraday)** | **Le moteur d'exécution est synchrone et piloté par cron.** `asyncio` n'apparaît que dans `apps/api/` et `mcp_tradingview/server.py` — jamais dans `packages/execution/`. `retry.py` gère la reprise par requête, pas la perte d'un flux. Une poche crypto 24/7 sur un cron quotidien ne peut structurellement pas réagir à une cascade de liquidations. |
| **F13** | **HAUTE** | **Aucun netting entre poches.** Rien n'empêchait un short Satellite sur un sous-jacent accumulé par le Core : deux spreads, un coût d'emprunt, un impact — pour finir plat. Résolu par `portfolio/netting.py`, non câblé. |
| **F14** | MOYENNE | **Pas de machine à états d'ordre.** `live_journal.py` écrit les ENTRÉES avec les features de décision (excellent, ADR-0028) et `live_roundtrip.py` apparie les sorties en FIFO. Manquent : les états intermédiaires (soumis, accusé, partiel, rejeté, annulé, expiré), l'horodatage de chaque transition et un log d'événements **append-only** distinct du journal de trades. |

---

## 2. Pilier 1 — Espérance mathématique nette et famille de stratégie

### 2.1 L'équation à faire porter par le code
Sur un horizon h, pour un actif i, en fraction du notionnel :

```
E[R_i(h)] = alpha_i(h)                        (= sigma_i(h) · IC(h) · z_i, cf. axe 2)
          − demi_spread_i − frais_i
          − Y · sigma_fenêtre · sqrt(Q/V)     impact non linéaire   (execution/impact.py)
          − financement · dt                  marge, rebate, dividendes short, capital bloqué
                                              (execution/funding_costs.py)
          − funding_perp · dt                 crypto perpétuels, DANS LES DEUX SENS
          ± gap_ouverture                     actions : le risque overnight n'est pas
                                              tarifé par le spread intraday
```

Le terme de **gap d'ouverture** n'est modélisé nulle part et n'est pas un détail : sur
actions, une part majeure du rendement — et de la variance — se réalise hors séance. Un
robot 1 h qui porte une position overnight prend un risque qu'aucune de ses statistiques
intraday ne mesure. Deux conduites acceptables : fermer avant la clôture (et payer la
rotation), ou mesurer séparément la distribution des gaps et l'inclure dans la CVaR.

### 2.2 Quelle FAMILLE de stratégie a le droit d'exister — `regime/hurst.py`
Avant de choisir un modèle, il faut savoir si l'actif est en régime persistant ou
anti-persistant. R/S corrigé (Anis-Lloyd) + bande nulle par permutation :

```
H < 0,5 hors bande  → anti-persistant  → arbitrage statistique / retour à la moyenne
H > 0,5 hors bande  → persistant       → suivi de tendance / momentum
H dans la bande     → indistinguable d'une marche aléatoire → AUCUNE allocation
```

**Le piège, mesuré et figé en test** : le R/S brut renvoie **H = 0,566 sur du bruit pur** —
on conclurait « tendance » sur une marche aléatoire. Corrigé : 0,507. Toute implémentation
sans correction ni bande nulle produit des régimes fantômes.

### 2.3 Régimes latents sans fuite — `regime/hmm_causal.py`
Baum-Welch complet (forward-backward normalisé), Viterbi, et surtout :
- **fenêtre expansive** — les paramètres à t viennent d'un ajustement sur le passé strict ;
- **probabilité filtrée** `P(S_t | r_1..r_t)`, jamais la lissée ;
- **réordonnancement des états par volatilité** après chaque ajustement (sans quoi l'EM
  permute les étiquettes et « stress » devient « calme » en silence) ;
- **hystérésis** (entrée 0,70 / sortie 0,40) pour ne pas basculer d'exposition en boucle.

Vérifié sur un processus à deux régimes connus : σ retrouvés [0,50 ; 2,51] pour [0,5 ; 2,5],
diagonale de transition 0,97 pour 0,97 vraie. **Sentinelle de non-fuite** : tronquer la série
à t donne exactement le même chemin sur [0, t]. Et l'écart chiffre le coût de l'honnêteté :
Viterbi (lissé, tricheur) 96,9 % de précision contre 94,5 % pour le filtre causal.

---

## 3. Pilier 2 — Architecture, asynchronisme, netting

### 3.1 Calendrier de marché (F11) — la brique absente
```
MarketCalendar (par place : XNYS, XETR, 24/7 crypto)
  is_open(ts) · next_open(ts) · next_close(ts) · session_minutes(date)
  is_half_day(date) · has_auction(ts) · holidays(year)
```
Trois usages non négociables : agréger 1 h → 4 h → Daily sur des bornes de séance réelles
(et non par `resample` calendaire) ; annualiser une volatilité avec le bon nombre de
périodes par classe d'actifs ; interdire tout ordre hors séance. Tant que cette brique
n'existe pas, **l'alignement multi-timeframe est une source de fuite** : une barre Weekly
étiquetée au lundi mais close le vendredi injecte du futur dans toute barre 1 h de la semaine
qui la référence. C'est le look-ahead multi-timeframe classique, et il est ici structurel.

### 3.2 Boucle d'exécution (F12) — ce qu'il faudrait
```
                  ┌── flux crypto (WebSocket, 24/7) ──┐
event loop ──────►│  file d'événements bornée         │──► moteur de décision (synchrone,
                  └── flux actions (séance + gaps) ───┘     déterministe, testable)
                                                              │
     heartbeat ◄────────── dead-man switch ◄──────────────────┘
```
Principe : **une seule boucle asynchrone pour l'E/S, un cœur de décision synchrone et
déterministe**. Mélanger les deux rend le système intestable. La file doit être **bornée** :
sous rafale, on jette les ticks intermédiaires (le dernier prix suffit) plutôt que de laisser
la latence croître sans limite. Reconnexion à backoff exponentiel, et — le point que
`retry.py` ne couvre pas — **détection de flux mort** : pas de tick depuis 2 × l'intervalle
attendu ⇒ le symbole passe en « données périmées », aucun ordre.

Sur la demande d'un moteur C++20 lock-free type LMAX Disruptor : c'est la bonne architecture
pour de la haute fréquence, et **hors sujet ici**. À l'horizon 1 h le budget de latence est
de plusieurs secondes ; la contrainte est la qualité des données et le coût d'exécution, pas
le jitter. Écrire un moteur C++ maintenant, ce serait optimiser le seul poste qui n'est pas
limitant, en ajoutant une frontière de langage à un projet d'une personne.

### 3.3 Netting Core/Satellite (F13) — livré
`portfolio/netting.py` distingue les trois expositions qu'on confond toujours :
**nette** (porte le risque de marché), **brute** (porte le financement et l'emprunt),
**exécutée** (ce que le broker voit). Trois politiques :

| Politique | Effet | Quand |
|---|---|---|
| `net` | exécute la somme algébrique | le moins cher — mais l'attribution DOIT passer par les livres virtuels |
| `core_priority` | le Satellite ne peut jamais retourner une ligne du Core (écrêtage à plat) | défaut recommandé pour un mandat long-only à satellite |
| `block` | tout ordre Satellite en conflit est refusé et tracé | le plus lisible en audit |

Le coût du conflit est chiffré : `2 × chevauchement × coût_bps`. Et le point qu'on oublie —
**netter détruit l'attribution par poche** si l'on ne tient pas de livres virtuels. C'est le
prix caché du netting, et il se paie en instrumentation, pas en performance.

---

## 4. Pilier 3 — Cockpit institutionnel et cycle de vie des ordres

### 4.1 Ce qui manque au front (20 pages, aucune de celles-ci)
| Vue | Contenu | Source déjà disponible |
|---|---|---|
| Matrice d'exposition factorielle | `B' w` par facteur, bêta marché global, contribution au risque | `ranking/orthogonalize.factor_exposure`, `portfolio/factor_risk` |
| Cockpit de queue | CVaR 99 %, indice de queue de Hill, temps sous l'eau, CDaR | `portfolio/evt.py` (+ estimateur PWM à brancher) |
| Attribution Core vs Satellite | rendement passif du Core contre alpha du Satellite, net de frictions | `portfolio/netting.attribution` (livré) |
| Exploitabilité de la covariance | k directions fiables, q = n/T, % de pas dégradés | `backtest/cov_risk` (livré, déjà dans le backtest) |
| Régime | probabilité **filtrée** de stress, H glissant, avec bande nulle | `regime/hmm_causal`, `regime/hurst` (livrés) |

Principe de densité : chaque chiffre affiché porte son **statut** (mesuré / modélisé /
UNCALIBRATED). Le badge « MODÉLISÉ » ajouté en juillet est la bonne pratique — la généraliser
vaut mieux qu'ajouter des graphiques.

### 4.2 Journal d'audit du cycle de vie des ordres (F14)
Le journal actuel enregistre des **trades**. Ce qu'exige un audit institutionnel est un log
d'**événements**, append-only, distinct et plus fin :

```sql
CREATE TABLE order_event (
  event_id      TEXT PRIMARY KEY,         -- ULID : ordonné dans le temps
  client_order_id TEXT NOT NULL,          -- clé d'idempotence, déjà en place
  broker_order_id TEXT,
  ts_event      TIMESTAMP NOT NULL,       -- horloge LOCALE de l'émission
  ts_broker     TIMESTAMP,                -- horloge BROKER (l'écart est une métrique)
  state         TEXT NOT NULL,            -- INTENT|SUBMITTED|ACKED|PARTIAL|FILLED
                                          -- |CANCELED|REJECTED|EXPIRED
  qty           DOUBLE, price DOUBLE, filled_cumul DOUBLE,
  reason        TEXT,                     -- cause de rejet, TOUJOURS renseignée
  decision_ref  TEXT,                     -- lien vers le snapshot de décision (ADR-0028)
  payload_hash  TEXT                      -- hash de la requête envoyée
);
```
Règles : **aucune mise à jour**, seulement des insertions ; toute transition impossible
(`FILLED → SUBMITTED`) lève et alerte ; l'écart `ts_event − ts_broker` est suivi comme
indicateur de dérive d'horloge ; la reconstruction de l'état d'un ordre se fait **par rejeu**
du log, jamais depuis un champ mutable. C'est ce qui permet de répondre, six mois plus tard,
à « pourquoi cet ordre est-il parti ? » — et c'est la condition d'une revue externe.

---

## 5. Pilier 4 — Business : l'analyse honnête

### 5.1 Ce qui n'est pas vendable
Le vault l'écrit déjà ([[12_MANIFESTE_HONNETETE]]) : **DSR ≈ 0 sur le directionnel**. Vendre
des signaux dont l'edge n'est pas démontré à des family offices n'est pas un produit — et,
en Europe comme aux États-Unis, la fourniture de recommandations d'investissement
personnalisées est une activité **réglementée**. Ce point précède toute discussion de
multiple d'ARR : sans statut, il n'y a pas de revenu récurrent à valoriser.

### 5.2 Ce qui est réellement défendable
L'actif rare de ce dépôt n'est pas l'alpha, c'est **l'infrastructure d'intégrité de
recherche** : gate à quatre étages (placebo → DSR → PBO → sabotage), ledger d'hypothèses qui
déflate le Sharpe par le nombre d'essais, point-in-time vérifié par sentinelle, CV purgée —
et désormais CPCV, unicité d'échantillon, diagnostic de covariance et régimes causaux. Très
peu d'équipes, y compris professionnelles, disposent de cet outillage.

Le produit correspondant n'est pas « des signaux », c'est **« prouvez que votre backtest
n'est pas surajusté »** : une API et un rapport qui prennent une courbe d'equity, un ledger
d'essais et des métadonnées de données, et rendent DSR, PBO, chemins CPCV, taille
d'échantillon effective, exploitabilité de la covariance et verdict de sabotage. Les acheteurs
sont ceux qui doivent **justifier** une stratégie devant un comité : gérants émergents,
allocataires, family offices, plateformes de PM externalisés.

### 5.3 Le moat, honnêtement
Ni le code (open source), ni les formules (publiées). Trois barrières réelles, par ordre de
solidité :
1. **Les données point-in-time accumulées** : un historique de vintages — fondamentaux,
   calendriers de résultats révisés, compositions d'indices datées, prix bruts non réécrits —
   ne se rattrape pas après coup. C'est le seul actif dont la valeur croît avec le temps et
   qu'un concurrent ne peut pas acheter d'un coup.
2. **Le ledger d'hypothèses** : la trace horodatée de tout ce qui a été essayé et rejeté. Sans
   elle, le DSR d'un nouvel arrivant n'est pas calculable. C'est un moat épistémique.
3. **La discipline de refus** : un système qui publie ses échecs (`/echecs`) est crédible d'une
   façon que le marketing n'achète pas.

### 5.4 Sur les multiples de 20× à 40× l'ARR
Ce ne sont pas un objectif, c'est une **conséquence** — de la rétention nette, de la croissance
et de la marge brute, dans un régime de taux donné. Les afficher comme cible fausse les
arbitrages produit. La question utile à ce stade est : **cinq personnes paieraient-elles
2 000 €/an pour un rapport d'intégrité de backtest ?** Tant que la réponse n'est pas mesurée,
tout plan de valorisation est de la fiction. Et la précondition reste le RDV paper : sans
courbe réelle réconciliée, ni produit ni levée.

---

## 6. Ce que je n'ai pas fait, et pourquoi

- **Calendrier de marché (F11)** et **boucle asynchrone (F12)** : identifiés, spécifiés, non
  implémentés. Le calendrier exige une source de jours fériés par place (dépendance externe,
  décision de périmètre) ; la boucle asynchrone est une refonte du chemin de production, à ne
  pas mener sans pouvoir la faire tourner contre un vrai flux.
- **Moteur C++20 lock-free** : délibérément écarté (§ 3.2) — optimiser le seul poste non
  limitant.
- **Surface de volatilité et grecques** : aucune chaîne d'options ingérée. Décision de
  périmètre, pas un oubli.
- **Câblage** des modules livrés : aucun. Ils entrent en production par le gate, avec des
  chiffres mesurés sur données réelles.
