# Audit de l'espérance nette — Phase 0 (lecture seule)

> **Date** : 2026-10-06 · **Base** : `main` = `b8b2863` · **Périmètre** : revue du code et
> des mesures déjà consignées. **Aucun code de stratégie modifié.**
> Étiquettes : **CONFIRMÉ** (lu dans le code ou mesuré sur données réelles, source citée),
> **INFÉRÉ** (déduit du code, non mesuré), **n/d** (aucune donnée),
> **UNCALIBRATED** (coût ou seuil non mesuré). Le conteneur d'audit n'a **aucune donnée de
> marché ni journal réel** : tout chiffre ci-dessous vient du vault (mesures VPS datées).

---

## 0. Verdict en cinq lignes

1. La règle tradée est **indiscernable de QQQ + cash à même volatilité** (rejeu 10 ans,
   ΔSharpe +0,17 [−0,08 ; +0,42], p = 0,17). Aucun alpha établi. Le DSR ≈ 0 est confirmé.
2. Le seul effet mesuré est une **réduction du drawdown** (−25,7 % contre −35,6 % pour QQQ),
   obtenue par l'exposition partielle, pas par la sélection.
3. **Le terme limitant est le signal, pas les coûts** : l'IC du score de screening est
   **négatif** (−0,068, t = −1,98) et l'IC du classement **réellement tradé** n'a jamais
   été mesuré (n/d). Réduire les coûts ne crée pas d'espérance là où le brut est nul.
4. Le second terme est la **rotation** : en paper, 587 positions closes en 94 jours,
   détention médiane **1,0 jour**, espérance pondérée **+0,08 %** par position close.
   C'est du rebalancement de poussière, pas des « trades » au sens d'un setup.
5. Plusieurs prémisses de la mission sont **inexactes** (§1). À corriger avant la Phase 1.

---

## 1. Prémisses de la mission confrontées au dépôt

| Prémisse | Ce que dit le dépôt | Statut |
|---|---|---|
| Rebalancement hebdo/mensuel | **Quotidien**, lun-ven (`make live-cron-install`, `scripts/cron_live.sh`), avec une bande d'inaction de max(0,5 % du capital, 5 $) (`scripts/run_live.py:193`). Le rejeu décide tous les 5 jours. | CONFIRMÉ |
| Allocation HRP/ERC | **ERC** en production (`preset_weights._erc_blackout` → `equal_risk_contribution`). HRP n'existe que pour l'allocation affichée (`packages/portfolio/optimize.py`). | CONFIRMÉ |
| + vol-target | « DD-target » : exposition = min(1, (dd_target/k_dd) / vol du portefeuille) (`preset_weights._exposition`). | CONFIRMÉ |
| P0-3 : turnover non instrumenté | Le **P0-3 du TODO est FERMÉ**, mais il ne concerne que le **backtest** (coûts déduits de `preset_equity_daily`). En **live**, le spread n'est jamais capté et le « slippage » mesuré compare le fill au **dernier close** (§3, F6). Ta formulation est juste pour le live. | CONFIRMÉ |
| Registre des échecs | `research/hypotheses.jsonl` (41 entrées), publié par `/api/failures` et la page `/echecs` du site. | CONFIRMÉ |
| Gate à 4 étages | placebo → DSR → PBO → sabotage (`packages/research/gate.py`, `adversarial.py`). **Un contrôle non mesuré (None) est IGNORÉ** : un candidat peut être « promu » sur un seul contrôle (`gate.py:8, 47`). | CONFIRMÉ |
| Compteur d'essais DSR | Deux comptes coexistent : `ledger.trial_count()` = **41** enregistrements ; `deflation_params` = **5 738** essais (somme des `n_essais`). `verdict_hors_echantillon` lit le second. | CONFIRMÉ |
| Modules /risk, /sentiment, /events | Présents. **Aucun n'alimente la sélection de production.** Sentiment et événements sont affichés seulement. | CONFIRMÉ |

---

## 2. Cartographie du pipeline de PRODUCTION

Chemin d'ordres unique : `scripts/run_live.py` → `risk/order_gate` → courtier (Alpaca paper).

| Étage | Fichier | Entrées → sorties | Paramètres | Tests | Dette |
|---|---|---|---|---|---|
| Données | `apps/api/snapshot._load_prices` → `packages/data` | bases SQLite (market.db, YAHOO.db, crypto.db) → barres daily | `QUANT_HISTORY_DAYS` | `tests/data`, `make contracts` | univers = **listes actuelles** (survivants) ; 20 délistés ingérés seulement |
| Features | `preset_config.momentum_rank` | clôtures alignées par date → rendement 252 j | `lookback=120` (cov), 252 (momentum) | `tests/backtest/test_preset*` | momentum **12-0** (F1) |
| Signal / sélection | `preset_weights._selection` | momentum → top-12 | `top_k=12`, `QUANT_QUALITY_SELECTION` (off) | idem | branche qualité non PIT (F8) |
| Filtre | `_erc_blackout`, `regime_mult`, `breadth` | poids → poids | `blackout_move=0,12`, `dd_hard=−0,15`, `dd_soft=−0,10` | `tests/backtest` | portes calculées sur le **panier sélectionné** (F2), sans hystérésis (F3) |
| Sizing | ERC → `mom_tilt` → `adaptive_cap` → `_exposition` → `_concentrate` | cov 120 j → poids finaux | `max_weight=0,10`, `min_weight=0,025`, `dd_target=0,25`, `k_dd=1,6` | idem | `band` reçu mais **inutilisé** (F9) ; DD ajusté des queues non appliqué (F4) |
| Cœur indiciel | `preset_rejeu.avec_coeur` / snapshot | QQQ 50 % | `QUANT_CORE_SPEC` | `tests/backtest/test_preset_rejeu.py` | — |
| Exécution | `run_live._reconcile`, `_broker_targets`, `rebalance_plan` | cibles → ordres | bande 0,5 % du capital ; plancher 1 000 $ ; hystérésis 80 % | `tests/execution` (nombreux) | créneau décidé par `fenetre_execution.py` |
| Portail pré-trade | `packages/risk/order_gate.evaluer` | ordre → ordre réduit ou refusé | `config/risk.yaml` | `tests/risk/test_order_gate.py` | — (hors périmètre) |
| Sortie | implicite : une ligne qui sort du top-12 est liquidée (`val=0`) | — | — | `tests/execution` | **aucune sortie TP/SL** ; confirmé en réel (§4) |
| ML | `packages/ml/edge_*` | features → score affiché | — | `tests/ml` | **hors chemin d'ordres** ; edge UNCALIBRATED |

---

## 3. Revue orientée espérance — constats

Gravité : **H** = fausse une mesure ou une décision ; **M** = coût ou biais probable ;
**B** = dette.

| # | Constat | Preuve | Effet sur E_net × N | Grav. |
|---|---|---|---|---|
| F1 | Le momentum de production est un **12-0** : `M[s][s0-1] / M[s][b0]`, avec `b0 = s0 − 253`. Le mois le plus récent est inclus, alors que la convention 12-1 l'exclut (retournement court terme). `vault/12_FACTORS.md` annonce un 12-1. | `preset_config.py:67-75, 129` | signal contaminé par le retournement à 1 mois — à MESURER, pas à présumer | M |
| F2 | La porte d'**ampleur** lit la part des 12 titres **sélectionnés** au-dessus de leur MM200. Des gagnants du momentum y sont presque toujours : la porte est probablement inerte. Même famille que QML-009(a), corrigé sous drapeau pour la porte de régime seulement. | `preset_weights.py:272-273`, `preset_helpers.py:40` | protection supposée qui ne protège pas | M (INFÉRÉ) |
| F3 | Portes **discrètes sans hystérésis** : régime (1 / 0,6 / 0,2, ×0,5), plafond adaptatif (10 % → 5 % au seuil de corrélation 0,60), blackout (poids 0 si \|r₂ⱼ\| > 12 %). En décision quotidienne, chaque bascule ré-ordonne tout le livre. | `preset_helpers.py:8-24, 66-76` ; `preset_weights.py:63-64` | source probable de rotation (N ↑ sans E ↑) | M (INFÉRÉ) |
| F4 | Le DD-cible **ajusté des queues** (`_dd_eff`) est calculé, mais la production reçoit le DD **nominal** `_dd`. | `snapshot.py:1913` contre `snapshot.py:2061-2063` | incohérence entre risque affiché et risque tradé | B |
| F5 | Le **gate promeut sur un seul contrôle** : un contrôle à None est ignoré. Le ledger porte 3 entrées `promu` (momentum, trend, low_vol, juin) avec un **DSR de 0,0 à 0,01**. | `gate.py:8, 47` ; `research/hypotheses.jsonl` | statuts du registre trompeurs | M |
| F6 | Le « slippage » live = fill / **dernier close connu** − 1. Il inclut le gap de nuit et la dérive intraday : ce n'est pas un coût d'exécution. **Spread non capté** : les colonnes `P_mid_*` et `P_bid/ask_fill` existent mais ne sont jamais remplies par `run_live`. Le « 12 bps » publié a été retiré (doublons). | `run_live.py:716-717` ; `exec_costs.py:4-8` ; `journal_sqlite.py` ; JOURNAL l.2494 | coûts réels UNCALIBRATED → le sabotage ne peut pas être calibré | **H** |
| F7 | `features_snapshot` live = rank_score, target_weight, decision_price, régime, notionnel. **Absents** : features complètes, version du modèle, poids ERC/tilt, multiplicateurs de portes. | `run_live.py:739-790` | décisions **non rejouables** ; aucune ventilation possible par feature | **H** |
| F8 | Fondamentaux **non point-in-time** : `_latest` prend la dernière valeur annuelle par date de **fin d'exercice**, le dépôt amendé écrase l'original, et `as_of` n'est pas utilisé pour filtrer. Valeurs **inventées** si absentes : `gross_profit = revenue × 0,4`, `ebit = net_income × 1,3`, `equity = revenue × 0,5`, `fcf = 0`. Contraire au mandat données réelles. Hors production depuis QML-001, mais alimente les scores affichés et les notes. | `sec_provider.py:101-103, 122, 255-262` | toute recherche fondamentale historique serait en look-ahead | **H** (recherche) |
| F9 | `band` est passé à `preset_latest_weights*` mais n'est **pas utilisé** (la bande vit dans `run_live`). | `preset_weights.py:195, 217` | paramètre mort, confusion | B |
| F10 | **Rotation live ≫ rejeu (à confirmer)** : 587 fermetures en 94 jours calendaires en paper (≈ 2 300/an), contre 3 386 **ordres** (achats et ventes) en 10 ans au rejeu (≈ 340/an). Les unités diffèrent (fermetures de lots ou ordres), mais l'écart dépasse un facteur 5. La fenêtre paper contient des incidents connus (trois planificateurs avant le 15/09, lots reconstruits). | JOURNAL 24/09 ; 10_BACKTEST 30/09 | l'écart live ↔ rejeu n'est pas expliqué ; N live mesuré contaminé | **H** |
| F11 | Le rejeu exécute au **close suivant** ; le live exécute en séance, dans la fenêtre de `fenetre_execution.py`. | `preset_rejeu.py` docstring ; `cron_live.sh:10` | biais d'exécution non chiffré | M |
| F12 | Biais connus et ouverts, tous en faveur de la stratégie : **survivants** (QML-002), paramètres réglés sur tout l'historique (QML-005), période cachée 2023-2026 lue par certains labos. | TODO QML-002, QML-005 | — | **H** (déjà connu) |

**Aucune fuite trouvée dans le chemin de production :**
- exécution décalée (t+1) ;
- HMM filtré (`hmm_causal.py`) ;
- `tronquer` du rejeu en point-in-time ;
- indice exogène sous drapeau en point-in-time ;
- recherche des motifs `shift(-n)`, `bfill`, `center=True` négative.

---

## 4. Inventaire des features

« Prod » = lue par la sélection ou le sizing tradés.

| Famille | Feature | Source / module | Timeframe | Dispo réelle | Prod ? | Preuve empirique |
|---|---|---|---|---|---|---|
| Technique | Momentum 252 j (12-0) | `preset_config.momentum_rank` | daily | close t | **oui** | IC **n/d** pour CE classement |
| Technique | Tilt momentum 12 m | `preset_helpers.mom_tilt` | daily | close t | **oui** | n/d (ablation jamais faite) |
| Technique | Vol / covariance 120 j | `cov_risk.cov_for_step` | daily | close t | **oui** (ERC, DD-target) | gestion du risque, pas d'alpha |
| Technique | Choc 2 j (blackout) | `_erc_blackout` | daily | close t | **oui** | n/d |
| Régime | MM200, pic, pente de l'indice | `preset_helpers.regime_mult` | daily | close t | **oui** | protection « régime MM200 » : Sharpe médian **0,99** contre 0,87 sans (870 scénarios, en échantillon) |
| Régime | Ampleur (> MM200) | `preset_helpers.breadth` | daily | close t | **oui** | n/d ; probablement inerte (F2) |
| Régime | Corrélation moyenne | `adaptive_cap` | daily | close t | **oui** | n/d |
| Technique (écran) | Momentum 12-1, tendance MM200, basse vol (z-score) | `packages/ranking`, `screening/engine` | daily | close t | non (affichage) | IC **−0,068**, t = −1,98, 74 fenêtres, horizon 1 mois |
| Technique (ML) | 10 features (momentum 1/3 mois, MM50, RSI, ATR, momentum ajusté, distance au plus-haut 52 sem., retournement 5 j, choc 10 j, régime de vol) | `packages/ml/edge_transversal` | daily | close t | non | AUC : UNCALIBRATED (pas de distribution nulle) ; label refait le 06/10 |
| Fondamental | Score qualité / valeur | `packages/fundamentals` | annuel | **non PIT** (F8) | non (QML-001) | aucune |
| Sentiment | News RSS / FinBERT, X du jour | `packages/sentiment`, `packages/social` | daily | horodaté à la collecte | non | aucune |
| Événements | Calendrier des résultats, PEAD | `packages/events`, `research/pead.py` | événementiel | date de publication | non | ledger : `event_earnings` en_test, sans mesure |
| Macro | VIX, proxy ISM, FRED | `packages/regime/real_macro` | daily / mensuel | PIT (vintages FRED) | non (porte macro affichée) | n/d |
| Volume / microstructure | OFI, vPIN (POC) | `research/microstructure.py` | intraday | — | non | POC seulement |

**Redondances (corrélation > 0,8)** : **n/d**, aucune matrice calculée sur données réelles.
Deux redondances sont probables par construction : momentum 12-0 / tilt 12 m (même
quantité), momentum 3 mois / momentum ajusté du risque (ML).

---

## 5. Décomposition de l'espérance

**Sources** : rejeu VPS du 30/09 (10 ans) ; `make turnover-audit` du 24/09 (paper, 94 jours) ;
grille du 30/09.

| Composante | Valeur | Source / statut |
|---|---|---|
| Taux de gain (décisions du système, paper) | **50 %** | turnover-audit 24/09, 587 fermetures |
| Espérance par position close, pondérée par le notionnel | **+0,08 %** (+712 $ sur 889 640 $) | idem |
| Espérance simple (non pondérée) | +1,54 % | idem — domine par la poussière (rapport 19×) |
| Profit factor | 2,15 | idem |
| Gain moyen / perte moyenne | **n/d** | non publiés par l'audit |
| Détention médiane | **1,0 jour** | idem |
| Fréquence | 41,0 fermetures / semaine (paper, chiffre de l'audit) ; ≈ 340 ordres / an (rejeu) | F10 : écart non expliqué |
| Frais | **UNCALIBRATED** : 64 fermetures sur 597 renseignées, toutes estimées | idem |
| Spread / slippage | **UNCALIBRATED** (F6) | — |
| Coût modèle actions | 10,28 bps aller-retour (0 commission, 5 bps de slippage par côté, 0,28 bps réglementaire) | `CostModel.for_asset_class("equity")` |
| Frais du rejeu, 10 ans | 7 976 $ pour 3 386 ordres (bande fixe) | rejeu 30/09 |
| Sharpe net (rejeu) | 1,10 ; QQQ 0,93 ; ΔSharpe +0,17 [−0,08 ; +0,42], p = 0,17 | rejeu 30/09 |
| Drawdown max (rejeu) | −25,7 % (QQQ −35,6 %) | rejeu 30/09 |
| MAE / MFE | **n/d** : capture sur 5 positions seulement | turnover-audit 24/09 |
| Ventilation par setup, actif, régime, taille, famille | **n/d** : features non journalisées (F7) | — |
| IC / RankIC à 1, 5, 10, 20, 60 jours | **n/d** pour le classement tradé. Le score d'écran : −0,068 à 1 mois seulement | `make ic-screening` |
| Sorties alternatives sur la production | ATR −0,04, structure +0,04, structure + prise +0,00 de ΔSharpe ; **3/3 rejetées** | `make preset-sorties`, 30/09 |
| Méta-filtre LightGBM (SMCLXTP-A) | AUC hors échantillon **0,5004**, p = 0,47 ; **rejeté** | `make meta-smc`, 30/09 |

---

## 6. Le terme limitant

**Le brut, pas les coûts.**
- Aucune mesure ne montre que la sélection apporte quelque chose au-delà de l'exposition :
  - ΔSharpe face à QQQ non significatif ;
  - IC du score d'écran négatif ;
  - méta-filtre au hasard (AUC 0,50) ;
  - sorties alternatives nulles.
- Les coûts sont un second terme réel. ≈ 8 k$ sur 10 ans au rejeu ; en live, une rotation
  qui semble bien plus forte (F10), dont le coût exact est inconnu (F6).
- Les réduire améliore E_net × N **mécaniquement**, mais ne fera pas apparaître un alpha
  absent.

**Conséquence pour les Phases 2-3** : ajouter des familles de features et un LightGBM n'a de
sens qu'une fois l'IC du classement tradé mesuré **par horizon**, avec une distribution
nulle. Sinon chaque famille ajoutée consomme des essais DSR pour chercher un signal dont
l'existence n'est pas établie. Si l'IC reste nul après la Phase 2, l'écrire : la stratégie
honnête est alors **QQQ + cash à exposition pilotée** (option a de ADR-0211).

---

## 7. Plan priorisé

Score indicatif = (impact sur E_net × N) × solidité des preuves ÷ (effort + essais DSR),
chaque terme noté de 1 à 3. Ce score sert à ordonner, il ne mesure rien.

| Rang | Action | Phase | Impact | Preuve | Effort | Essais | Score |
|---|---|---|---|---|---|---|---|
| 1 | **Mesurer l'IC / RankIC du classement TRADÉ** (momentum 12-0) à 1, 5, 10, 20 et 60 j, avec une distribution nulle par permutation transversale. Lecture seule ; le compteur d'essais déclare explicitement les 5 horizons. | 0 bis | 3 | 3 | 1 | 1 | **4,5** |
| 2 | Instrumentation des coûts : capter bid/ask/mid à l'arrivée et au fill (Alpaca), shortfall = fill / mid à l'arrivée ; séparer gap de nuit et exécution (F6). Journal uniquement. | 1A | 3 | 3 | 2 | 0 | **4,5** |
| 3 | Journal enrichi : toutes les features à l'entrée, multiplicateurs de portes, version du code et du modèle, raison de sortie, MAE/MFE (F7). | 1B | 3 | 3 | 2 | 0 | **4,5** |
| 4 | Expliquer F10 : décomposer la rotation live par cause (bande, plancher, blackout, régime, plafond, sortie du top-12) sur le journal et le rejeu. | 1D | 3 | 2 | 2 | 0 | 3,0 |
| 5 | Fondamentaux PIT : date de dépôt (`filed`), retraitements versionnés, **suppression des valeurs inventées** (F8), test interdisant toute feature postérieure à la décision. | 1C | 2 | 3 | 3 | 0 | 2,0 |
| 6 | Hystérésis sur les portes discrètes (F3), sous drapeau, jugée au rejeu par le nombre d'ordres à Sharpe et DD égaux. | 3 (M3) | 2 | 2 | 2 | 1 | 1,3 |
| 7 | Momentum 12-1 contre 12-0 (F1), sous drapeau, une seule variante. | 3 | 2 | 2 | 1 | 1 | 2,0 |
| 8 | Ampleur et régime sur un indice exogène (F2 ; QML-009a déjà codé pour le régime). | 3 | 2 | 2 | 1 | 1 | 2,0 |
| 9 | Cohérence : appliquer `_dd_eff` à la production (F4), ou documenter pourquoi pas. | 1D | 1 | 3 | 1 | 1 | 1,5 |
| 10 | Gate : exiger que les 4 contrôles soient mesurés pour « promu » ; requalifier les 3 « promu » du ledger (F5). **Tes interdits** (« ne modifie jamais les seuils ») exigent ton accord, même si ce n'est pas un seuil. | — | 1 | 3 | 1 | 0 | 1,5 |
| 11 | Familles de features de la Phase 2 (fondamental PIT, volume, bougies, texte, vol DL). **Conditionnées au rang 1** : si l'IC du classement tradé est nul, ces familles doivent battre une base nulle, pas une base existante. | 2 | ? | 1 | 3 | 3+ | ≤ 0,5 |

**Ordre recommandé** : 1 → 2 → 3 → 4, puis décision. Les rangs 6 à 8 sont trois
hypothèses distinctes : trois PR, trois essais au ledger.

---

## 8. Commandes VPS pour combler les n/d existants (lecture seule)

```bash
make turnover-audit        # taux de gain, PF, détention, capture — à refaire hors période d'incident
make slippage              # slippage décision → fill (au sens de F6 : inclut le gap de nuit)
make ic-screening          # IC du score d'écran (PAS du classement tradé — cf. rang 1)
make rdv-paper             # verdict paper contre backtest
make combler-mfe           # MFE/MAE des trades clos qui n'en ont pas (simulation par défaut)
```

---

*Rien n'a été activé, aucun seuil, limite ni kill-switch n'a été modifié. Ce document est le
seul fichier ajouté par la Phase 0.*
