# 21 — Audit board élite (2026-08-22)

Audit du dépôt à l'aune du cahier des charges « conseil d'administration quantitatif ».
Chaque exigence a été **vérifiée dans le code**, pas supposée. Les références sont des chemins
réels. Ce qui est déjà en place est dit tel quel — un audit qui ne trouve que des problèmes est
un audit qui n'a pas regardé.

---

## 1. At a Glance

**Trois défauts financiers réels**, tous dans la chaîne de valorisation fondamentale, tous
silencieux (ils produisent un chiffre plausible, jamais une erreur) :

| # | Défaut | Où | Effet |
|---|---|---|---|
| **A** | Capitaux employés au bilan de **clôture**, pas moyen | `corporate_finance.py:36` | ROCE et EVA **surestimés** sur toute activité saisonnière |
| **B** | Croissance perpétuelle = **défaut**, pas contrainte | `corporate_finance.py:99` | Valeur terminale sans plafond → DCF gonflable |
| **C** | Garde-fou splits **asymétrique** | `snapshot.py::_themes_section` | Un split 4:1 passe et corrompt les rendements |

**Ce que le cahier des charges réclame et qui existe déjà** : queues épaisses (EVT/GPD,
Cornish-Fisher, CVaR), cointégration Engle-Granger avec les **bonnes** valeurs critiques,
log-rendements pour la volatilité et rendements simples pour l'agrégation, biais du survivant
(`delisted.csv` + `survivorship_delta`), sur-apprentissage (Sharpe déflaté, CV combinatoire
purgée), disjoncteurs (`dd_kill_switch`, `fail_loud`), impact de marché en racine carrée et
Almgren-Chriss, Polars, Lightweight Charts, mode sombre dense.

**Ce qui est absent, et pourquoi ce n'est pas forcément un défaut** : pas de Black-Scholes ni de
Grecs (aucune option n'est négociée) ; pas d'architecture WebSocket/Redis (le système rééquilibre
**une fois par jour** — y mettre du streaming événementiel serait de la complexité sans contrepartie).

---

## 2. Analyse de scaffolding logique

### A. Le bilan de clôture ment sur les sociétés saisonnières

```python
def capital_employed(f: Financials) -> float:
    return f.total_equity + max(0.0, f.total_debt - f.cash)
```

Une seule photo, prise à la date de clôture. Or la clôture n'est pas un instant neutre : la
plupart des sociétés la placent **après** leur pic d'activité, quand les stocks ont été écoulés
et les créances encaissées. La dette nette y est donc à son **plancher annuel**.

Conséquence mécanique : capitaux employés sous-estimés → `roce_after_tax = NOPAT / CE`
**surestimé** → `economic_profit = (ROCE − WACC) × CE` doublement faussé (le taux ET l'assiette).

Un distributeur qui clôture en janvier peut afficher un ROCE de 18 % là où la moyenne des quatre
trimestres en donnerait 11 %. Le filtre qualité sélectionne alors sur un artefact de calendrier
comptable. **Correctif** : moyenner sur les quatre derniers trimestres, ou à défaut sur ouverture
et clôture, et le DIRE quand seul le bilan de clôture est disponible.

### B. La valeur terminale n'a pas de plafond

```python
def _dcf(f, wacc_rate, growth, terminal_growth: float = 0.025, years: int = 10):
    if f.fcf <= 0 or wacc_rate <= terminal_growth or f.shares <= 0:
        return float("nan")
```

Le défaut de 2,5 % est bon — sous le plafond de 3 % qu'impose le cahier des charges. Mais c'est
un **défaut d'argument**, pas une contrainte : rien n'empêche un appelant de passer 6 %. Le seul
garde-fou, `wacc <= terminal_growth`, n'attrape que l'absurde (valeur infinie), pas le simplement
trop optimiste.

Or la valeur terminale pèse typiquement 60 à 80 % d'un DCF à dix ans. Avec un WACC de 9 %, passer
g de 2,5 % à 5 % multiplie le multiple terminal par **1,6**. C'est le levier le plus puissant du
modèle, et le seul qui ne soit pas borné.

**Correctif** : plafonner dans `_dcf` lui-même (`min(terminal_growth, 0.03)`), pas dans la
signature. Une contrainte économique — aucune entreprise ne croît perpétuellement plus vite que
l'économie — n'a pas à être négociable par l'appelant.

### C. Le filtre anti-glitch ne protège que d'un côté

```python
if rr.size and (np.nanmax(np.abs(rr)) > 1.5 or ...):
    continue
```

Écarte les variations quotidiennes de plus de 150 %. Un **regroupement** 1:10 (+900 %) est bien
attrapé. Un **split** 4:1 fait −75 % : sous le seuil, il passe, et corrompt tous les rendements
qui le traversent. Le filtre protège donc du cas rare et laisse passer le fréquent — les splits
vers le bas frappent précisément les valeurs qui ont beaucoup monté, celles que le momentum
sélectionne.

Aucun ajustement des actions de société n'existe par ailleurs dans le dépôt (vérifié).

### D. Un taux d'impôt unique pour un univers multi-pays

`_TAX` est une constante globale, appliquée à ASML (Pays-Bas), TSM (Taïwan) et aux valeurs
américaines. Le NOPAT, donc le ROCE, donc l'EVA, sont biaisés dans le sens du différentiel de
taux. Effet plus faible que A et B, mais réel sur un classement transversal.

---

## 3. Tableau des corrections

| Module / fonction | Anomalie | Correction requise | Impact |
|---|---|---|---|
| `fundamentals/corporate_finance.py:36` `capital_employed` | Bilan de clôture, instant non neutre | Moyenne 4 trimestres (ou ouverture/clôture) ; déclarer « clôture seule » à défaut | **Risque** : ROCE/EVA surestimés → le filtre qualité sélectionne un artefact de calendrier |
| `corporate_finance.py:99` `_dcf` | `terminal_growth` négociable par l'appelant | `min(terminal_growth, 0.03)` **dans** la fonction | **Alpha** : la valeur terminale pèse 60-80 % du DCF ; g 2,5 %→5 % gonfle le multiple de 1,6× |
| `corporate_finance.py:43` `roce_after_tax` | Taux d'impôt unique multi-pays | Taux par juridiction, ou NOPAT depuis l'impôt réellement payé | **Alpha** : biais transversal sur le classement qualité |
| `apps/api/snapshot.py::_themes_section` | Garde-fou splits asymétrique (>150 % seulement) | Détecter le ratio proche d'une fraction simple (1/2, 1/3, 1/4…) et ajuster, ou exiger des cours ajustés | **Risque** : rendements corrompus sur les valeurs qui montent — celles que le momentum choisit |
| `packages/execution/impact.py`, `almgren_chriss.py` | Écrits et testés, **non branchés** à l'exécution réelle | Câbler `admit_signal` / `no_trade_band` dans `run_live` | **Performance** : coûts d'impact ignorés au dimensionnement |
| `packages/portfolio/rmt_denoise.py` | Débruitage RMT en **opt-in**, défaut inchangé | Décider sur données réelles (k médian) avant activation | **Risque** : si k < 2, l'ERC répartit du risque estimé sur du bruit |

---

## 4. Plan UI/UX et inter-connectivité

**Déjà fait cette session** : la fiche d'un titre va jusqu'à l'ordre — six étages en clair,
verdict traçable, écart cible/détention converti en euros. C'est le maillon qui manquait entre
analyse et décision.

**Ce qui reste en silo**, par ordre de valeur :

1. **Le screener classe mais ne conclut pas.** Le même bloc « décision » a sa place sur chaque
   ligne du screener, pas seulement sur la fiche.
2. **Aucune frontière efficiente interactive.** Sélectionner un facteur ne recalcule rien côté
   portefeuille. `packages/portfolio/` a le nécessaire (Black-Litterman, ERC, HRP) — il manque le
   fil entre l'onglet et le calcul.
3. **Le dimensionnement Kelly existe** (`sizing/kelly_fat_tail.py`, dérivé d'un budget de
   drawdown) mais n'apparaît sur aucun écran.
4. **`/ml`, `/conviction`, `/portfolio`** gardent leur vocabulaire technique — l'accessibilité
   n'a couvert que l'accueil, le tableau de bord, le risque, les positions et la fiche.

**Sur le streaming temps réel** : le cahier des charges réclame WebSockets bidirectionnels et
Redis Pub/Sub. Ce serait une erreur d'ingénierie ici. Le système rééquilibre **une fois par
jour**, sur des barres quotidiennes, avec une bande d'inaction. Une architecture événementielle
ajouterait un mode de panne permanent pour une information que la stratégie n'utilise pas. La
recommandation est bonne pour de la haute fréquence ; ce système n'en fait pas.
