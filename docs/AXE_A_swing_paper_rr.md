# AXE A — décision-time `rr` (swing / IPA / paper) — design

| | |
|---|---|
| **Owner** | TA Desk / Alpha Lab |
| **Mission** | CEO Axe A — paper-only |
| **Date** | 2026-09-30 (Europe/Paris) |
| **Statut** | DESIGN (pas de patch prod) |
| **Périmètre** | path swing / IPA / `moteur_swing` → ordres paper → journal |
| **Hors scope** | live ; inventer `rr` sur le **preset** ; L8 multi-TF / campagne HTF |

Copie archive : `vault/10_Backtests/AXE_A_swing_paper_rr_20260930.md`.

---

## 1. Contexte Alpha Lab

Le sink journal paper est déjà **ACCEPT** pour les features de décision :
`rank_score`, `notionnel`, `ts_decision` (cf. `scripts/run_live.py` `_merge_feats` +
`packages/execution/live_journal.py` `build_open`).

`packages/screening/expectancy_filter.py::evaluate_setup(p, rr) → E_R` est **prêt**,
mais ses inputs (`p_calibrated`, `rr`) sont **absents** des `target_orders` preset →
`expectancy_R` / `gain_attendu` restent N/A (clés omises, jamais inventées).

Interface coordonnée :
- **Alpha** : `evaluate_setup(p_calibrated, rr) → SetupDecision(accept, expectancy_R, reason)`
- **Risk** : `risk_$` = risque devise figé à la décision
  (`moteur_swing.RiskManager.taille` → `risque_devise`, ou `qty × |entry − stop|`)

---

## 2. Formule `rr` exacte PIT

Unité : **sans dimension** (prix / prix). Instant PIT = barre de décision
(close 1D pour SFP / IPA / swing ATR ; prix limite OB pour OTE).

Soit `E` = entry (prix d’engagement), `S` = stop, `T` = target (cible).

### Long (`sens == "long"`)
Préconditions : `E > 0`, `S < E`, `T > E`, `E − S > 0`.

\[
rr = \frac{T - E}{E - S}
\]

### Short (`sens == "short"`)
Préconditions : `E > 0`, `S > E`, `T < E`, `S − E > 0`.

\[
rr = \frac{E - T}{S - E}
\]

### Forme unifiée (après validation de côté)
\[
rr = \frac{|T - E|}{|E - S|}
\]
avec garde : stop du **bon côté** (long ⇒ `S < E` ; short ⇒ `S > E`), sinon **rejeter**
la proposition (ne pas écrire `rr`).

### FLAT
Pas d’entrée : **pas de `rr`**. Un `SignalDirection.FLAT` (sortie) n’attache aucune
géométrie d’ouverture.

### Cas invalides → clé omise (jamais 0 inventé)
- distance stop nulle / négative / mauvais côté ;
- `E ≤ 0` ;
- target du mauvais côté ;
- absence de proposition swing/IPA pour le symbole (path **preset weights**).

**Référence code déjà conforme** : `packages/strategies/moteur_swing.py:201-210`
(`_verifier` : `rr = abs(cible - entree) / distance` + filtre `rr_min`).

---

## 3. Où `rr` / entry / stop / target existent déjà

| Source | Fichier:ligne | Champs | Comment `rr` naît |
|--------|---------------|--------|-------------------|
| **moteur_swing Proposition** | `moteur_swing.py:79-96`, `:194-210` | `entree`, `stop`, `cible`, `rr`, `sens` | Calculé PIT dans `_verifier` ; propagé via `as_dict()` / `detecter` → `propositions[]` |
| SFP | `moteur_swing.py:158-177` | stop = extrême ± 0,5·ATR ; cible = E ± `rr_min`·risk | `rr` ≈ `rr_min` (3,0) par construction |
| OTE | `moteur_swing.py:179-192` | entrée = bord OB ; stop derrière OB | idem |
| RiskManager taille | `moteur_swing.py:249-265` | `risque_devise`, `notionnel`, `quantite` | **`risk_$` candidat** = `risque_devise` |
| **IPA** `_signal` | `institutional_price_action.py:283-327` | `Signal.stop`, `Signal.target` ; `features.entry`, `risk_per_unit`, `tp1`, `tp2` | `target = entry + direction × tp2_rr × risk` → **rr structurel = `tp2_rr` (≥ 3)** ; **pas** de champ `rr` nommé sur le Signal |
| swing ATR registry | `swing.py:45-50` | `stop`, `target` ; pas d’entry explicite | `target − price = rr × atr_stop × atr` → rr param = 3,0 ; entry implicite = close |
| ExitEngine | `moteur_sortie.py:96-130`, `:156-167` | `entree`, `stop_initial`, plancher R | Sortie / R unitaire **après** entrée — pas la source décision-time d’ouverture |
| expectancy | `expectancy_filter.py:17-29` | `evaluate_setup(p, rr)` | Consommateur ; n’émet pas `rr` |
| Signal.reward_risk | `models.py:174-190` | propriété | **PIÈGE** : `_entry_ref = (stop+target)/2` ⇒ `reward_risk ≈ 1` toujours. **Ne pas** utiliser comme `rr` PIT. Préférer entry explicite (`Proposition.entree` / `features["entry"]` / close). |

Propagation propositions : `MarketStructureEngine.detecter` →
`propositions: [p.as_dict()…]` (`moteur_swing.py:153-154`). Statut moteur :
**SHADOW_UNCALIBRATED** — aucun appelant prod aujourd’hui.

---

## 4. Path paper orders → journal (où brancher)

```
build_snapshot()
  └─ _live_section / _live_with_rebalance
       └─ live.target_orders[]          # poids preset (souvent SANS géométrie)
            └─ _attach_rank_scores(...) # modèle d’attache (rr à mimer)
run_live._reconcile
  └─ à l’envoi achat : opened[] copie clés depuis l’ordre o
       (rank_score, expectancy_R, rr, p_calibrated, risk_$)
  └─ _journal_opens → _merge_feats(op) → features_snapshot
       └─ journal_opens / build_open → data/journal.db (legacy=0)
```

**Règle d’or** : ne **jamais** fabriquer `rr` / `entry` / `stop` à partir de
`weight_pct` du preset. Omettre la clé si aucune proposition swing/IPA PIT n’est
disponible pour le symbole.

### Tableau points d’attache

| # | Fichier:ligne | Rôle | Champs à injecter sur l’ordre paper |
|---|---------------|------|-------------------------------------|
| 1 | `apps/api/snapshot.py:464-472` | Pattern `_attach_rank_scores` | Miroir : `_attach_swing_geometry(orders, props_by_sym)` — `entry`/`entree`, `stop`, `target`/`cible`, `rr`, optionnel `risk_$` |
| 2 | `apps/api/snapshot.py:560-604` | Construction `target_orders` | Après append des dicts poids ; **ne pas** remplir si source = preset weights seul |
| 3 | `apps/api/snapshot.py:2569-2573` | Site actuel d’attache `rank_score` | Même site pour géométrie si map propositions fournie (sleeve swing paper) |
| 4 | `scripts/run_live.py:413-422` | Copie ordre → `opened[]` | Déjà prêt : boucle `("rank_score", "expectancy_R", "rr", "p_calibrated", "risk_$")` — ajouter `entry`/`stop`/`target` dans la même liste **si** présents |
| 5 | `scripts/run_live.py:653-694` | `_merge_feats` → `features_snapshot` | Déjà prêt pour `rr` / `risk_$` / `expectancy_R` / `p_calibrated` ; étendre pour `entry`, `stop`, `target` (floats finis) |
| 6 | `packages/execution/live_journal.py:203-226` | `build_open` sink | Accepte tout float fini dans `features` (+ `ts_decision` string) — **aucun changement requis** si les clés arrivent déjà dans `features` |

Champs journal ACCEPT déjà câblés : `rank_score`, `notionnel`, `ts_decision`,
`decision_price`, `target_weight`, `regime_expo`.  
Champs **prévus** mais vides tant que non sur l’ordre : `rr`, `p_calibrated`,
`expectancy_R`, `risk_$`, `gain_attendu` (= `expectancy_R * risk_$`).

---

## 5. Pseudo-API (mini, pas de gros patch)

```python
# packages/screening/rr_pit.py  (proposition — non implémenté)

def rr_pit(sens: str, entree: float, stop: float, cible: float) -> float | None:
    """R:R point-in-time. None si invalide / FLAT. Jamais 0 inventé."""
    if sens not in ("long", "short") or entree <= 0:
        return None
    dist = abs(entree - stop)
    if dist <= 0:
        return None
    if sens == "long" and not (stop < entree < cible):
        return None
    if sens == "short" and not (cible < entree < stop):
        return None
    return abs(cible - entree) / dist


def attach_decision_geometry(
    orders: list[dict],
    props_by_sym: dict[str, dict],
) -> None:
    """Attache entry/stop/target/rr(/risk_$) IFF proposition présente.
    Omet les clés sinon — ne touche pas au preset weights."""
    for o in orders or []:
        p = props_by_sym.get(o.get("symbol") or "")
        if not p:
            for k in ("entry", "stop", "target", "rr", "risk_$",
                      "expectancy_R", "p_calibrated"):
                o.pop(k, None)
            continue
        entree = float(p["entree"])  # ou p["entry"]
        stop, cible = float(p["stop"]), float(p["cible"])
        rr = rr_pit(p["sens"], entree, stop, cible)
        if rr is None:
            continue
        o["entry"], o["stop"], o["target"], o["rr"] = entree, stop, cible, round(rr, 6)
        if "risque_devise" in p:           # Risk interface
            o["risk_$"] = float(p["risque_devise"])
        # Alpha interface — seulement si p_calibrated déjà fourni (calibrateur ML)
        p_cal = p.get("p_calibrated")
        if isinstance(p_cal, (int, float)) and p_cal == p_cal:
            from packages.screening.expectancy_filter import evaluate_setup
            d = evaluate_setup(float(p_cal), rr)
            o["p_calibrated"] = float(p_cal)
            if d.accept:
                o["expectancy_R"] = d.expectancy_R
```

Branche sleeve paper (futur) : produire `props_by_sym` depuis
`MarketStructureEngine.detecter` / IPA `_signal` **avant** `_attach_rank_scores`,
sans modifier `preset_latest_weights` ni les poids.

---

## 6. Ce qui manque pour `E_R`

| Input `evaluate_setup` | État path paper preset | Action |
|------------------------|------------------------|--------|
| `rr` | Absent des `target_orders` | Brancher attache géométrie depuis propositions swing/IPA (points 1–3) |
| `p_calibrated` | Absent | Calibrateur ML / méta-filtre **hors** ce design ; UNCALIBRATED ⇒ pas d’invention |
| `cost_R` | Défaut 0,05 dans `evaluate_setup` | OK pour paper ; ne pas hardcoder un autre coût sans mesure |
| `risk_$` | Absent (Risk) | Mapper `RiskManager.taille(...).risque_devise` quand sizing swing actif |
| `gain_attendu` | Dérivé dans `_merge_feats` | Automatique dès que `expectancy_R` **et** `risk_$` sont sur l’ordre |

Tant que preset-only : **`evaluate_setup` → N/A** (comportement actuel correct).

---

## 7. Contraintes respectées

- Paper-only ; pas live.
- Pas d’invention de `rr` sur le preset (clé omise).
- STOP HTF / pas d’ouverture L8 multi-TF dans ce design (IPA HTF structure existant
  hors scope d’extension).
- Pas commit / push ; pas ping Thierry.
- Design-only : pseudo-API ci-dessus, pas de patch prod.

---

## 8. Prochaine étape (hors ce livrable)

1. Sleeve paper opt-in qui émet des propositions `moteur_swing` / IPA par symbole.
2. `_attach_swing_geometry` au site `snapshot.py:2569`.
3. Étendre la liste de copie `run_live.py:419` avec `entry`/`stop`/`target`.
4. Brancher `p_calibrated` seulement quand un calibrateur ACCEPT existe.
5. Tests : attach omis si pas de prop ; rr PIT long/short ; pas de clé sur ordre preset pur.
