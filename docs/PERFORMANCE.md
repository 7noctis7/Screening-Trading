# Vitesse des moteurs de backtest

> Mesuré le 31/10 avec `make bench-moteur` (`scripts/bench_moteur.py`). Charge **synthétique
> seedée** : elle sert de chronomètre reproductible, jamais de résultat financier.
> Machine : conteneur Linux, Intel Xeon 2,10 GHz, 4 cœurs, Python 3.13.16. Médiane de 3 passages.

## Résultats

| Moteur | Actifs | Barres/actif | Médiane | Débit (barres·actif/s) |
|---|---:|---:|---:|---:|
| event-driven (chaîne complète) | 10 | 3 650 | 43,5 s | 840 |
| vectorisé (`fast_swing_backtest`) | 10 | 3 650 | 0,14 s | 268 637 |
| event-driven (chaîne complète) | 50 | 3 650 | 230,7 s | 791 |
| vectorisé (`fast_swing_backtest`) | 50 | 3 650 | 0,60 s | 303 641 |

Le vectorisé est environ **300 fois** plus rapide : c'est lui qui balaie les grilles, et c'est
voulu. L'event-driven rejoue la chaîne de production (régime → stratégie → risque → sizing →
broker → journal, exécution à l'ouverture de t+1) : il sert à juger une règle, pas à en
balayer mille.

## Constat : le coût de l'event-driven croît avec la LONGUEUR de l'historique

5 actifs, un passage, machine au repos :

| Historique | Barres/actif | Temps | ms par barre·actif |
|---|---:|---:|---:|
| 1 an | 365 | 0,40 s | 0,22 |
| 2 ans | 730 | 1,38 s | 0,38 |
| 4 ans | 1 460 | 3,39 s | 0,46 |
| 10 ans (10 actifs) | 3 650 | 42,1 s | 1,15 |

Un coût par barre constant donnerait une colonne constante ; elle est multipliée par cinq
entre 1 et 10 ans. Profil (cProfile, 5 actifs × 4 ans) : **94 % du temps** dans
`MaCrossover.generate_signals`, qui recalcule l'ATR (`indicators/volatility.py`, boucle
Python) et les moyennes mobiles (`indicators/trend.py`) sur **tout** l'historique accumulé,
à chaque barre. Le travail total est donc quadratique en nombre de barres.

**Pas corrigé ici.** Calculer les indicateurs une fois sur la série puis lire l'indice `t`
serait identique *si et seulement si* chaque indicateur est causal ; c'est un changement de
l'API des stratégies, avec un risque de fuite du futur, qui mérite sa propre PR et son test
d'équivalence (mêmes signaux, barre par barre). En attendant : un backtest event-driven de
50 actifs sur 10 ans prend environ 4 minutes.

## Reproduire

```
make bench-moteur                               # 10 et 50 actifs × 10 ans, 3 passages
make bench-moteur ARGS="--actifs 5 --ans 4 --passages 1"
```
