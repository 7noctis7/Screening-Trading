# 10 — BACKTEST RESULTS

> Résultats datés + hash de config + version données (DVC à venir).
> **Toujours OOS / walk-forward + deflated Sharpe.** Un Sharpe in-sample ne vaut rien.

## Méthodologie (S5)
- **Walk-forward** : fenêtres roulantes train→test (warm-up pour indicateurs valides),
  sélection params in-sample, évaluation **out-of-sample**, segments OOS concaténés.
- **Deflated Sharpe (DSR)** : corrige le multiple testing (nb total d'essais = grille ×
  fenêtres). Règle : ne passer en prod qu'avec **DSR élevé** (~>0.95). PSR en complément.

## Journal des runs
| Date | Stratégie | Données | Fenêtres | Essais | OOS Sharpe | PSR | DSR | Verdict |
|---|---|---|---|---|---|---|---|---|
| S5 (démo) | ma_crossover | synthétique seed=7 (4 actifs, 7 ans) | 16 | 64 | 0.46 | 0.90 | 0.00 | NON significatif |

> ⚠️ Données SYNTHÉTIQUES : aucune conclusion d'edge. Le DSR=0 confirme juste que le
> pipeline ne fabrique pas d'alpha. Refaire sur données réelles (yfinance/FMP) ensuite.

---

## 2026-09-30 — Horizons × stratégies × sorties × fréquences, grille PRÉ-ENREGISTRÉE [73dd06226a20], 4 actifs réels (FMP)

**Protocole.**
- Grille déposée AVANT tout calcul (commit `cdd6cd8`) : 6 stratégies × 4 critères de
  sortie × 5 fréquences = 120 scénarios par actif, soit 480 essais consignés.
- Horizons de 1, 3, 5 et 10 ans sur des fenêtres glissantes mensuelles, comparées au
  buy & hold sur les mêmes fenêtres.
- Moteur `signal_long_tp`, depuis 2020.

**Par dimension** (médianes sur actifs × autres dimensions) :

| Stratégie | Sharpe | CAGR | maxDD | 1 an : rend. / bat B&H | 3 ans | 5 ans |
|---|---|---|---|---|---|---|
| tendance_mm200 | 0,86 | +32,3 % | −53,1 % | +19,8 % / 33 % | +26,0 % / 29 % | +33,7 % / 8 % |
| smclxtp | 0,77 | +25,3 % | −62,2 % | +18,5 % / 35 % | +23,1 % / 21 % | +25,3 % / 0 % |
| momentum_12_1 | 0,77 | +27,8 % | −53,4 % | +13,6 % / 30 % | +20,4 % / 13 % | +30,8 % / 0 % |
| ma_crossover | 0,72 | +22,6 % | −60,1 % | +14,9 % / 32 % | +17,3 % / 8 % | +25,7 % / 0 % |
| swing | 0,17 | +1,1 % | −32,1 % | 0 % / 33 % | +0,6 % / 9 % | +1,5 % / 0 % |
| rsi_reversion | 0,04 | 0 % | −36,3 % | 0 % / 33 % | 0 % / 2 % | 0 % / 0 % |

| Sortie | Sharpe | CAGR | maxDD |
|---|---|---|---|
| tendance_mm200 | 0,78 | +27,9 % | −50,9 % |
| signal | 0,70 | +23,6 % | −55,6 % |
| suiveur 3 ATR | 0,44 | +8,0 % | −42,2 % |
| TP 3 ATR | 0,38 | +5,5 % | −54,5 % |

| Fréquence | Sharpe | CAGR | maxDD |
|---|---|---|---|
| jour | 0,82 | +31,1 % | −56,7 % |
| semaine | 0,73 | +25,4 % | −55,2 % |
| mois | 0,66 | +19,5 % | −49,4 % |
| trimestre | 0,44 | +8,0 % | −45,3 % |
| année | 0,26 | +2,4 % | −48,2 % |

**Par horizon** (médiane sur les 4 actifs) :
- 1 an : B&H +72,3 %/an ; le meilleur scénario, `momentum_12_1|signal|semaine`, fait
  +47,0 %/an.
- 3 ans : B&H +71,7 %/an ; le meilleur, `smclxtp|signal|mois`, fait +56,6 %/an.
- 5 ans : B&H +48,5 %/an ; le meilleur, `ma_crossover|tendance_mm200|jour`, fait
  +59,6 %/an. C'est le seul horizon où le meilleur dépasse le B&H médian, sur environ
  20 fenêtres qui se chevauchent.
- 10 ans : UNCALIBRATED, l'historique fait 6,3 ans.

**Surapprentissage.**
- PBO : 0,29 (PLTR), 0,33 (NVDA), 0,64 (BTC), 0,69 (ETH).
- DSR du meilleur scénario : entre 0,25 et 0,43. Aucun ne survit à la déflation.

**Lecture.** Trois résultats convergent avec le banc portefeuille du VPS (870 scénarios)
et avec l'ADR-0052 :
1. Décider souvent (jour, semaine) vaut mieux que rarement (trimestre, année).
2. Le filtre de tendance et le momentum sont les familles les plus robustes.
3. Les prises de profit et les suiveurs coupent la queue droite.

Aucun scénario ne bat le buy & hold ajusté du risque de façon établie. Il n'y a que
4 actifs, tous grands gagnants 2020-2026 : la mesure qui compte est le tirage aléatoire
sur le VPS, depuis 2015.

## 2026-09-30 — SMCLXTP-A face aux stratégies du bot, mêmes règles, 4 actifs réels (FMP), depuis 2020

**Protocole.**
- Même moteur (`signal_long_tp`) : signal au close → ouverture suivante, frais de 5 pb sur
  les actions et 25 pb sur la crypto.
- Chaque stratégie garde SES sorties : stops et cibles du registre honorés en séance, avec
  l'hypothèse défavorable.
- `institutional_price_action` est écartée : aucun réglage connu (UNCALIBRATED).
- 16 essais consignés.

| Stratégie | Trades | Win | Durée méd. | PF méd. | PnL méd./trade | Sharpe méd. | Sortino méd. | CAGR méd. | maxDD méd. | Bat le B&H (Sharpe) |
|---|---|---|---|---|---|---|---|---|---|---|
| smclxtp | 39 | 59 % | 125 j | 2,80 | +41,4 % | 0,69 | 1,05 | 24,6 % | −61,4 % | 0/4 |
| ma_crossover | 86 | 47 % | 21 j | 2,19 | +4,6 % | 0,71 | 1,16 | 12,9 % | −43,7 % | 1/4 (ETH) |
| rsi_reversion | 51 | 47 % | 18 j | 1,13 | +2,6 % | 0,15 | 0,23 | 0,9 % | −41,3 % | 0/4 |
| swing | 74 | 30 % | 8 j | 1,00 | +0,2 % | −0,01 | 0,06 | −0,9 % | −39,2 % | 0/4 |
| buy & hold | — | — | — | — | — | 1,01 | 1,59 | 60,5 % | −78,0 % | — |

**Lecture.**
- SMCLXTP-A et `ma_crossover` sont à égalité en Sharpe (0,69 contre 0,71) ; l'écart est
  hors de portée statistique.
- `rsi_reversion` et `swing` ne rapportent rien sur ces actifs.
- Aucune stratégie ne bat le buy & hold ajusté du risque, sauf `ma_crossover` sur ETH.
- 4 actifs, tous grands gagnants : ni la conclusion ni son inverse ne se généralisent.
- Le tirage aléatoire sur le VPS (`make comparer-strategies`) est la vraie mesure.

## 2026-09-30 — SMCLXTP-A (LONG → TP), 4 actifs sur 12, données RÉELLES (FMP), depuis 2020

**Source.** Connecteur FMP : EOD ajusté des dividendes pour les actions, EOD pour la
crypto. Chaque fichier a été lu en entier et contrôlé : aucune barre OHLC incohérente,
aucun trou en crypto. Les 8 autres actifs (ASTS, CLSK, PL, RKLB, ABCL, QQQ, CRWD, CRWV)
sont refusés par l'abonnement FMP, et Yahoo et Binance sont bloqués par la politique
réseau du conteneur : ils restent à mesurer sur le VPS (`make smclxtp-backtest`).

**Règles** (`backtest/signal_long_tp.py`, écrites avant les chiffres) :
- signal au close → ordre à l'ouverture suivante ;
- une position à la fois, pas de stop ;
- frais de 5 pb par jambe sur les actions, 25 pb sur la crypto ;
- 10 000 $ réinvestis ;
- indicateur causal, réglages du Pine (50/50, pivots manqués) ;
- une position encore ouverte en fin de période est exclue des stats de trades.

| Actif | Trades | Win | Durée moy. | PF | MaxDD | Sharpe | Sortino | CAGR | PnL moy./trade | B&H CAGR | B&H MaxDD | B&H Sharpe |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PLTR (dès 30/09/2020) | 7 | 71 % | 146 j | 3,53 | −73,7 % | 0,62 | 1,00 | 21,1 % | +2 882 $ · +61,3 % | 64,4 % | −84,6 % | 1,05 |
| NVDA | 7 | 86 % | 218 j | 32,3 | −54,2 % | 1,25 | 1,97 | 50,4 % | +20 270 $ · +55,1 % | 71,6 % | −66,3 % | 1,31 |
| BTCUSD | 13 | 46 % | 103 j | 2,07 | −61,2 % | 0,76 | 1,10 | 28,1 % | +2 812 $ · +27,7 % | 43,9 % | −76,7 % | 0,91 |
| ETHUSD | 12 | 50 % | 102 j | 1,52 | −61,5 % | 0,62 | 0,87 | 20,0 % | +1 247 $ · +15,6 % | 56,6 % | −79,4 % | 0,96 |

**Verdict.**
- Sur les 4 actifs, le CAGR ET le Sharpe sont INFÉRIEURS au buy & hold.
- Le maxDD est réduit de 11 à 18 points, mais reste entre −54 et −74 % : l'indicateur
  n'a pas de stop.
- 7 à 13 trades par actif, ce n'est pas significatif : un win rate de 6/7 a un IC 95 %
  d'environ [42 %, 100 %].
- Le méta-labelling ne compte que 54 événements (< 200) : UNCALIBRATED, le filtre n'est
  pas entraînable.

**Biais à garder en tête :**
- la liste d'actifs a été choisie après coup, parmi les grands gagnants 2023-2025 ;
- le PnL moyen en dollars est gonflé par le réinvestissement ; le pourcentage est la
  mesure comparable.

## 2026-09-25 — Banc d'exploration, grille quotidienne [8fa32ef0], EN ÉCHANTILLON (VPS, réel)

870 scénarios. Données : 624 séries réelles. Période : 2016-10-26 → 2022-12-30 (251 barres
par an). La période cachée (2023 → 2026) n'a PAS été lue.

**Verdict en échantillon : aucun scénario ne franchit la déflation.** Le meilleur DSR est
de 0,89, sous le seuil de 0,95. La PBO vaut 0,57 : le champion en échantillon finit plus
souvent qu'à son tour sous la médiane hors échantillon, donc le classement brut ressemble
à du bruit.

| Scénario | CAGR | Sharpe | maxDD | DSR |
|---|---|---|---|---|
| n°1 crypto·tout·égal·régime MM200·trimestre | 158,6 % | 1,57 | −77,7 % | 0,88 |
| n°2 crypto·tendance MM200·ERC·vol cible 15·mois | 33,6 % | 1,56 | −21,0 % | 0,89 |
| BTC acheté-conservé (rang 299) | 67,2 % | 1,06 | −83,0 % | 0,47 |
| QQQ acheté-conservé (rang 583) | 14,1 % | 0,67 | −35,6 % | 0,15 |

Sharpe médian par dimension :

| Dimension | Résultat |
|---|---|
| Univers | crypto 1,25 · actions US 1,07 · multi-actifs 0,76 · QQQ 0,68 · ETF 0,51 |
| Sélection | tendance MM200 1,06 ≈ momentum 6-1 1,04 > basse vol 0,84 > momentum 12-1 0,78 ≈ tout 0,77 |
| Protection | régime MM200 0,99 > aucune 0,87 > vol cible 15 0,79 |
| Rythme | jour 0,98 ≈ semaine 0,96 ≈ 3 jours 0,95 > mois 0,85 > trimestre 0,75 |

**Lecture.**

1. Le classement mesure surtout l'UNIVERS, pas la règle : les 25 premiers sont crypto.
2. Les univers crypto et actions US sont les listes ACTUELLES. Les radiés en sont absents
   (QML-002) : LUNA, FTT et les autres cryptos mortes ne peuvent pas peser. Leur avance
   sur QQQ est donc en partie un biais du survivant, et n'est pas mesurée.
3. Les écarts entre sélections, protections et rythmes (≈ 0,1 à 0,3 de Sharpe médian)
   sont du même ordre que l'IC d'un ΔSharpe sur 6 ans (±0,6, cf. rejeu).
4. Le momentum ETF quotidien est le pire : rotation de 41 par an pour un Sharpe de 0,1.

À faire avant `--holdout` : classer DANS chaque univers contre son propre
équipondéré-conservé.

## 2026-09-25 — Première mesure de la règle TRADÉE (rejeu, VPS, données réelles)

`make preset-replay` sur le VPS (`115dcd4`), market.db seule (819 séries réelles, 624
négociables), 2016-09-28 → 2026-09-24, décision tous les 5 jours, exécution au close
suivant, bande/plancher/portail de `run_live`, frais par classe. Branche MOMENTUM de la
sélection (la sélection qualité de production n'est pas rejouable : UNCALIBRATED).

| Configuration | CAGR | Sharpe | maxDD | Ordres | Frais (10 ans, 100 k$) |
|---|---|---|---|---|---|
| Satellite + cœur QQQ 50 % (production) | 17,9 % | 1,09 | −25,7 % | 3 393 | 7 898 $ |
| Satellite seul | 15,1 % | 1,04 | −26,0 % | 4 078 | 14 320 $ |
| `preset_backtest` (autre règle, autre fenêtre) | 9,7 % | 0,86 | −19,3 % | — | — |

**Références sur les MÊMES dates (2e passage, `ee81704`, satellite seul) :**

| | CAGR | Sharpe | maxDD |
|---|---|---|---|
| Satellite (rejeu) | 15,1 % | 1,04 | −26,0 % |
| QQQ acheté-conservé | 20,2 % | 0,93 | −35,6 % |
| Équipondéré des titres cotés | 19,9 % | 0,99 | −38,4 % |

| QQQ à MÊME volatilité (dilué en cash, ex post) | 13,3 % | 0,93 | −23,9 % |

**Test apparié (Jobson-Korkie/Memmel, `2ebe356`) :** ΔSharpe vs QQQ **+0,11 [−0,51 ; +0,72],
p = 0,73** ; vs équipondéré **+0,04 [−0,58 ; +0,67], p = 0,89**. **INDISCERNABLE.** À
volatilité égale, le satellite fait +1,8 pt/an de CAGR que QQQ + cash, avec un drawdown
légèrement PIRE (−26,0 % contre −23,9 %) — et cela avec le cash rémunéré à ZÉRO dans les
deux cas : en réalité le cash de l'alternative passive rapporterait le taux court, ce qui
l'avantage. Tous les biais connus (survivants, réglage sur tout l'historique) jouent EN
FAVEUR du satellite. Lecture cohérente avec le manifeste :
de la GESTION DU RISQUE (exposition partielle), pas d'alpha démontré.

**Ce qui n'est PAS établi.** Aucun alpha, univers de SURVIVANTS (listes actuelles, délistés absents du VPS), paramètres
réglés sur tout l'historique (QML-005), DSR non recalculé avec le nombre réel d'essais.
Le satellite seul fait presque le Sharpe du mélange : le cœur QQQ réduit surtout les frais.

**IC du screening (même soir, par date) : −0,068, t = −1,98, 74 fenêtres, seconde moitié
−0,110.** Le score de sélection ne prédit pas le mois suivant ; l'ancienne mesure
positionnelle (+0,041 sur le Mac, autre base) était un artefact d'alignement. Ne PAS
inverser le signe (choix a posteriori). « Conviction » reste fermé.

---

## 2026-09-03 — Cœur multi-actifs (QQQ + obligations longues + or) — **REJETÉ par la règle**

**Protocole.** Part de cœur figée à 50 %, identique à la production : SEULE la composition
change. Règle d'acceptation écrite AVANT le run (ADR-0053). 24 essais comptés dans la
déflation. Fenêtre commune 2016-05-31 → 2026-09-02, 2 580 séances. Rééq. mensuel du cœur à
5 bps ; le cœur QQQ ne paie aucun rééquilibrage → comparaison défavorable au nouveau venu.

**La prémisse de la construction TIENT.** Corrélations quotidiennes : GLD/QQQ **+0,11**,
QQQ/TLT **−0,09**, GLD/TLT +0,25. Les diversifiants sont réellement décorrélés du Nasdaq —
ce n'est pas là que ça échoue.

| variante | CAGR | Sharpe | Sortino | maxDD | PSR | DSR | ΔSharpe | p |
|---|---|---|---|---|---|---|---|---|
| **PRODUCTION 50 % QQQ** | **15,3 %** | **0,96** | 0,90 | −25,3 % | 100 % | 86 % | — | — |
| contrôle QQQ ETF | 14,9 % | 0,94 | 0,88 | −25,3 % | 100 % | 84 % | −0,02 | **0,000** |
| multi 60/25/15 | 11,4 % | 0,92 | 0,87 | −20,9 % | 100 % | 83 % | −0,03 | 0,674 |
| multi 50/30/20 | 10,6 % | 0,92 | 0,87 | −20,2 % | 100 % | 83 % | −0,04 | 0,684 |
| multi 40/35/25 | 9,8 % | 0,90 | 0,86 | −19,5 % | 100 % | 81 % | −0,06 | 0,650 |
| multi inverse-vol | 9,1 % | 0,90 | 0,87 | **−17,1 %** | 100 % | 81 % | −0,06 | 0,750 |

**Verdict : aucune variante ne passe.** Le critère (a) échoue partout — tous les ΔSharpe
sont NÉGATIFS, avec p entre 0,65 et 0,75 (indiscernables de zéro). Le cœur QQQ reste.

**L'issue secondaire déclarée d'avance s'est produite** : trois variantes améliorent le
maxDD de plus de 5 points (jusqu'à **−8,2 pts** pour l'inverse-vol, soit un tiers du
drawdown en moins). Ce n'était PAS un feu vert automatique, et l'analyse qui suit explique
pourquoi ça n'en devient pas un.

**LA RÉDUCTION DE RISQUE COÛTE PLUS QU'ELLE NE RAPPORTE.** Sur le rendement par unité de
drawdown (Calmar), la production reste devant PARTOUT :

| | CAGR / |maxDD| |
|---|---|
| PRODUCTION | **0,605** |
| contrôle ETF | 0,589 |
| inverse-vol | 0,532 |
| 60/25/15 | 0,545 |
| 50/30/20 | 0,525 |
| 40/35/25 | 0,503 |

Le maxDD baisse de 8,2 points, mais le CAGR baisse de 6,2 points — proportionnellement
plus. Et le levier ne rattrape rien : **le Sharpe est la mesure invariante au levier**, et
c'est précisément lui qui ne s'améliore pas. Lever le cœur diversifié jusqu'au drawdown de
production redonnerait ~13,5 % de CAGR avant coût de financement, contre 15,3 %.

**LIMITE DE L'ÉCHANTILLON, DITE SANS EN FAIRE UN PRÉTEXTE.** La fenêtre contient 2022, pire
année obligataire depuis un siècle (TLT ≈ −31 %). Le test est donc défavorable aux
obligations. Ce n'est PAS une raison de rejouer sur une autre fenêtre : choisir la période
après avoir vu le résultat est exactement ce que la déflation du DSR punit. Le chiffre reste
tel quel.

**FINDING SECONDAIRE, PLUS IMPORTANT QUE LE VERDICT (P1).** La ligne de contrôle — le QQQ
ETF replacé sur l'axe du preset — rend **−0,4 %/an** de moins que le cœur de production,
avec **t(α) = −6,15** et p = 0,000. Écart minuscule, mais massivement significatif, sur une
ligne censée mesurer le MÊME actif. Deux causes possibles, aux conséquences très
différentes : soit `choose_history` retient **^NDX**, un indice non achetable (le tableau de
bord surestimerait alors la moitié « cœur » de ~0,4 %/an, en permanence), soit
`blend_equity` désaligne positionnellement (`core_ret[-k:] = xr[-k:]`) le cœur et l'axe du
preset — quatrième occurrence du même défaut. `make diag-coeur-qqq` tranche entre les deux.

**Ce que le verdict ne doit PAS à cette anomalie** : les variantes multi-actifs perdent
aussi contre la ligne de CONTRÔLE (0,90-0,92 contre 0,94), qui est, elle, correctement
alignée par date. Le rejet tient quelle que soit l'issue du diagnostic.

---

## 2026-09-03 — Fenêtre vs code : le Sharpe 1,33 est reproduit à l'identique

`QUANT_HISTORY_DAYS=3600 make index-core`. Objectif : savoir si la baisse observée
(Sharpe 1,34 → 0,95) venait de la fenêtre de mesure ou d'une régression du code.

**Réponse : la fenêtre.** Blend 50 % QQQ + 50 % preset → Sharpe **1,33**, contre 1,33 dans
l'ancien tableau et 0,96 sur le plein historique. Le backtest actuel démarre treize mois
plus tôt et inclut une période plus difficile.

**À fenêtre égale, le code a amélioré le portefeuille** (preset pur) : Sharpe 0,99 → 1,12,
maxDD −31,7 % → −25,4 %, pour 3 points de CAGR en moins. Les correctifs d'alignement ont
retiré du rendement qui venait avec un risque disproportionné.

| Cœur QQQ | CAGR | Sharpe | Sortino | maxDD | DSR | ΔSharpe vs 50 % | p |
|---|---|---|---|---|---|---|---|
| 0 % | 14,7 % | 1,12 | 1,58 | −25,4 % | 91 % | −0,21 | 0,522 |
| 25 % | 16,9 % | **1,42** | 2,09 | **−18,2 %** | 99 % | +0,09 | 0,612 |
| **50 % (prod)** | 18,5 % | 1,33 | 1,96 | −22,4 % | 98 % | — | — |
| 75 % | 19,6 % | 1,09 | 1,57 | −28,7 % | 90 % | −0,24 | **0,027** |
| 100 % | 20,2 % | 0,91 | 1,29 | −35,1 % | 77 % | −0,42 | **0,011** |

**La ligne 25 % ne déclenche aucun changement.** Elle bat la production sur le Sharpe ET le
drawdown, mais p = 0,612 pour un seuil détectable de ±0,29 : c'est du bruit de sélection sur
cinq ratios. Seuls 75 % et 100 % sont discernables — et dans le sens PIRE.

**Alerte non résolue** : le cœur « momentum sectoriel » affiche CAGR 55,5 % à 100 % et
26,8 % à 25 %, DSR 100 %. Un tel chiffre sur 9,4 ans appelle un audit de fuite et de biais du
survivant avant toute lecture. Aucune conclusion n'en est tirée ici.

