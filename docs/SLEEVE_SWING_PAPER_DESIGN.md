# SLEEVE swing paper — design TA (signaux / géométrie)

| | |
|---|---|
| **Owner** | TA Desk (§A) · consolidation Alpha Lab |
| **Date** | 2026-09-30 PT |
| **Statut** | READY design TA · paper-only · pas commit/push |
| **Doc complet (lab)** | `/workspace/lab-ab-runs/sleeve-swing-paper-design.md` (§A+§C QT ; §B Arch pending) |
| **Canon rr** | `docs/AXE_A_swing_paper_rr.md` |
| **Canon risk_$** | `lab-ab-runs/risk-axe-a-risk-dollar-swing-paper.md` |

**HOLD expectancy** : `p` / `p_calibrated` **non inventé** ; `evaluate_setup` seulement si p calibré ; sinon omit E_R / gain_attendu.

**Gap Arch** : hook SHADOW (`moteur_swing`/IPA) → `target_orders` **absent** (G11).

**Setups** : SFP + OTE (`Proposition`) ; IPA via mapping (pas `Signal.reward_risk`). `swing.py` registry hors v1.

---

### A — TA Desk (signaux / géométrie) — **READY design**

| | |
|---|---|
| **Owner** | TA Desk |
| **Date** | 2026-09-30 ~23:05 PT |
| **Statut** | READY design (paper-only) — merge avec §C QT |
| **Refs canon** | `docs/AXE_A_swing_paper_rr.md` (rr PIT ACCEPT) · `lab-ab-runs/risk-axe-a-risk-dollar-swing-paper.md` (`risk_$` ACCEPT) · `lab-ab-runs/swing-paper-expectancy-map.md` |

#### A.0 Les 10 exigences dures (intégrées QT §C)

| # | Exigence TA | Implication QT (§C) |
|---|---|---|
| **1** | **PIT only** — entry/stop/target/rr sur barre d’engagement ; no look-ahead | Features figées au snap (`ts_decision` = `meta.generated_at`) ; jamais recalcul post-fill |
| **2** | `rr = \|T−E\|/\|E−S\|` ; FLAT/invalide → **omit clé** | Copier `rr` float fini seulement ; jamais 0 inventé |
| **3** | Source `rr` = **`Proposition.rr` seul** (SFP/OTE) ; IPA = mapping A.3 (**INTERDIRE** `Signal.reward_risk`) | Pas de fallback models.py ; reject si `rr` absent |
| **4** | Setups v1 = **SFP, OTE, IPA only** | `setup_id` ∈ {SFP, OTE, IPA} ; autre → reject sleeve |
| **5** | `risk_$ = qty×\|E−S\|` (= `risque_devise`) **IFF** prop swing/IPA | Attacher sur ordre sleeve sized ; **omit** sur preset |
| **6** | `evaluate_setup` `accept=False` → **skip open + log** | Phase 2 (quand p dispo) ; phase 1 = pas de gate E |
| **7** | **HOLD p** — ne pas inventer `p_calibrated` ; sans p pas de claim expectancy | Omit p / E_R / gain_attendu ; pas de proxy rank_score |
| **8** | Shadow→paper : **entry, stop, target\|rr, setup_id, ts_decision** obligatoires sinon **reject** | Pre-submit guard chemin sleeve avant `_envoyer` |
| **9** | Stops/TP **structurels moteur** ; pas sortie rebalance preset | Exit = stop/cible/ExitEngine (PR ult.) |
| **10** | Régime : **filtre moteur** ; pas HTF multi-TF | Hurst + `RiskManager.plan` ; pas L8 |

#### A.1 Scope / non-goals

**In scope TA** : setups SFP/OTE (`moteur_swing`) + IPA (mapping) ; géométrie PIT ; gates shadow→paper ; interfaces Risk/Alpha (HOLD p).

**Non-goals** : wire expectancy E2E ; inventer p ; preset weights ; live ; §B Arch ; §C QT (déjà READY) ; registry `swing.py` ATR pullback (hors v1).

#### A.2 Geometry PIT — pointer Axe A

**Canon** : `docs/AXE_A_swing_paper_rr.md` §2–3.

\[
rr = \frac{|T - E|}{|E - S|}
\]

Gardes : long ⇒ `S < E < T` ; short ⇒ `T < E < S` ; sinon **omit** `rr` (jamais 0). FLAT = pas de géométrie d’ouverture.

| Champ `Proposition` | Alias ordre | Code |
|---|---|---|
| `entree` | `entry` | `moteur_swing.py:86`, `as_dict` `:94` |
| `stop` | `stop` | `:87/:95` |
| `cible` | `target` | `:88/:95` |
| `rr` | `rr` | `_verifier` `:201-210` → `:96` |
| `sens` / `scenario` | side / `setup_id` | `:85/:84` → `"SFP"`\|`"OTE"` |

Réf conforme : `rr = abs(cible-entree)/distance` + `rr_min` (`RR_MINIMUM=3.0` `:51`).

**PIÈGE** : `Signal.reward_risk` (`models.py:174-190`) ≈ 1 — **interdit**. Sleeve v1 = `Proposition` (SFP/OTE) ou mapping IPA A.3 (features `entry` + stop/target).

**Risk `$`** (consommé) : `risk_$ = qty×|E−S|` = `RiskManager.taille` → `risque_devise` (`:261-263`). Politique : `lab-ab-runs/risk-axe-a-risk-dollar-swing-paper.md`.

#### A.3 Setups éligibles

##### SFP — scénario A (`moteur_swing`)

| | |
|---|---|
| Détection | `liquidite_ict.sfp` (`:89-114`) — BSL/SSL fen.50 + close réintègre + vol ≥1,5× moy.20 |
| Prop | `_proposition_sfp` (`moteur_swing.py:158-177`) |
| PIT | close **1D** ; stop = extrême ±0,5·ATR14 ; cible = E ± `rr_min`·risk |
| `setup_id` | `SFP` |

##### OTE — scénario B (`moteur_swing`)

| | |
|---|---|
| Détection | `continuation_ote` (`liquidite_ict.py:220-244`) — BOS + OB non mitigé ∩ OTE 61,8–78,6 % |
| Prop | `_proposition_ote` (`:179-192`) |
| PIT | **limite** bord OB ; stop derrière OB ±0,5·ATR ; cible `rr_min`·risk |
| `setup_id` | `OTE` |

Les deux émis ensemble ; `contradiction` si sens opposés (`:155-156`).

**Réponse Q7 (TA)** : défaut sleeve v1 = **skip** symbole contradictoire + log (aligné QT C.7) — pas d’auto-priorité SFP vs OTE.

##### IPA — mapping (`institutional_price_action`)

| | |
|---|---|
| Signal | `_signal` `:283-327` — entry=close ; stop zone±buffer ; target = entry+dir×`tp2_rr`×risk (`tp2_rr≥3`) |
| Features | `entry`, `risk_per_unit`, `tp1`, `tp2` — **pas** de champ `rr` nommé |
| Prod | UNCALIBRATED ; 0 caller `run_live` |

**Mapping → dict type Proposition** (Q8 CONFIRM) :

```
setup_id / scenario = "IPA"
sens   = long|short depuis direction
entree = features["entry"]     # PAS reward_risk
stop   = Signal.stop
cible  = Signal.target         # = features["tp2"]
rr     = abs(cible-entree)/abs(entree-stop)   # = tp2_rr si gardes OK
```

Invalide (mauvais côté / dist≤0) → omit, ne pas inventer.

##### Hors v1
`packages/strategies/swing.py` ATR pullback ; label snapshot `"swing"` = poids modèle ≠ moteur_swing.

#### A.4 Filtres

| Filtre | Fichier:ligne | Scope |
|---|---|---|
| `_verifier` rr/côté | `moteur_swing.py:194-210` | **IN** (HARD) |
| Volume SFP 1,5× | `liquidite_ict.py:60,97,107` | **IN** (dans détection) |
| OB non mitigé + zone OTE | `liquidite_ict.py:220-244` | **IN** |
| Hurst 1W > 0,55 | `persistance` `:117-132` | **IN soft** — indécidable (<64 pts) → log, **pas** auto-pass |
| Raffinement 1H CHoCH | `raffiner_entree` `:212-231` | **Q9 ACCEPT v1 sans 1H** : base dépôt = 1D → `indecidable` nominal ; **ne pas** forcer `pret=True` ; paper 1D-only OK |
| IPA FTB/SFP/LVN/rr veto | `institutional_price_action.py:264-279` | **IN** si IPA ON |
| MM200 + corr. 30j | `garde_swing` / `RiskManager.plan` | Risk/Arch consomme |
| ADV$ / carnet | — | **hors scope TA** |
| ML / `p_calibrated` | — | **HOLD** — hors scope TA |

#### A.5 Gates shadow → paper (checklist)

HARD sauf mention soft. Proposition `SHADOW_UNCALIBRATED` → ordre paper **ssi** :

| # | Gate | Niveau |
|---|---|---|
| G1 | Source = `Proposition.as_dict()` (SFP/OTE) ou mapping IPA A.3 — pas preset, pas `reward_risk` | HARD |
| G2 | sens long/short ; E>0 ; stop/target bons côtés ; \|E−S\|>0 | HARD |
| G3 | `rr` fini ≥ `rr_min` (3,0) présent | HARD |
| G4 | symbole univers paper + barres 1D PIT | HARD |
| G5 | opt-in paper-only (`QUANT_SWING_PAPER`) — pas live | HARD |
| G6 | sizing → qty + `risk_$` (ou omit risk_$ si sizing différé — alors pas `gain_attendu`) | HARD si open dimensionné |
| G7 | sans `p_calibrated` : **pas** `evaluate_setup` ; omit E_R/gain ; open géom OK (**HOLD** expectancy) | HARD policy |
| G8 | si p un jour : `accept=False` → skip open + log | HARD quand p |
| G9 | contradiction SFP↔OTE → **skip** + log (Q7) | soft→défaut |
| G10 | Hurst/1H indécidable ≠ feu vert | soft / Q9 |
| G11 | Hook producteur SHADOW → `live.target_orders` / `props_by_sym` **existe** | HARD — **GAP Arch** |

**État** : G11 **faux** aujourd’hui → 0 opens swing paper. Design débloque ; n’implémente pas.

#### A.6 Interfaces Risk & Alpha

- **Risk** : `risk_$ = qty×|E−S|` ; `accept=False` → skip+log ; notionnel ≠ risk_$. → `risk-axe-a-risk-dollar-swing-paper.md`
- **Alpha** : `evaluate_setup(p, rr)` seulement si `p_calibrated` **réel**. **`p` NON INVENTÉ.** Tant que absent : **HOLD** wire expectancy ; journal peut porter entry/stop/target/rr/risk_$ ; omit p/E_R/gain_attendu. Interdit : rank_score / score brut / ASSUMED_EDGE comme p.

#### A.7 Points d’attache + gap Arch

| # | Fichier:ligne | Rôle | Qui |
|---|---|---|---|
| 1 | `moteur_swing.py:134-210` | props SFP/OTE + rr | existant lab |
| 2 | `moteur_swing.py:249-265` | `risque_devise` → risk_$ | Risk/QT |
| 3 | `institutional_price_action.py:283-327` | géom IPA | mapping A.3 |
| 4 | `snapshot.py:464-472` / `:2569-2573` | pattern attach | **Arch** `_attach_swing_geometry` |
| 5 | `run_live.py:417-422` / `:653-693` | copie + merge | **QT** §C |
| 6 | `expectancy_filter.py:17-29` | E_R | Alpha — HOLD sans p |

**GAP Arch (bloquant sleeve)** : aucun hook prod `MarketStructureEngine.detecter` / IPA → `props_by_sym` → `target_orders`. `run_live` = preset only. `STATUT = "SHADOW_UNCALIBRATED"` (`:46`) ; callers = banc/tests only. Sans §B, G1–G10 documentés mais non actionnables.

#### A.8 Open Q restants (hors réponses Q7–Q9 ci-dessus)

**Arch** : voir §10.1–6 + gap G11 (injection snap, poche capital A/B, parité banc_swing).  
**QT** : PR1–5 §C.8 — TA valide contrat champs A.0 / C.1.  
**Alpha** : READY design §A+§C ; bloquant impl = §B + go Thierry ; HOLD expectancy non-bloquant pour sleeve géom paper (Q13 : **oui** ouvrir paper géom sans E_R).

---
*Fin §A TA. §B / §C non modifiés par ce merge.*

