# AXE 5 — Architecture du moteur d'exécution

Retour à [[17_AUDIT_INSTITUTIONNEL]].

> Un backtest ne se trompe presque jamais sur le signal ; il se trompe sur les **fills**. Le
> biais d'exécution optimiste est celui qui transforme une stratégie ruineuse en stratégie
> rentable sans qu'aucune ligne de code n'ait l'air fausse.

## 1. État actuel et pourquoi il ne tient pas en intraday

`packages/execution/sim_broker.py` : fill **immédiat**, **intégral**, au dernier prix marqué,
± un slippage forfaitaire. Aucune file d'attente, aucun rejet, aucun fill partiel, aucune
contrainte de volume. C'est acceptable pour un rebalancement mensuel de mégacaps ; c'est
inutilisable pour arbitrer une stratégie horaire, où le fill *est* la stratégie.

À cela s'ajoute `exec_lag = 0` par défaut dans `preset_backtest` (finding F4) : le signal est
calculé sur le close de la barre t et exécuté à ce même close — un prix qui n'existe qu'une
fois la barre terminée. Le paramètre existe depuis M-1 ; **son défaut doit passer à 1**, et 0
doit rester une option explicitement étiquetée « optimiste, non-régression seulement ».

## 2. Les trois niveaux de réalisme, et lequel viser quand

### L1 — Barre suivante plafonnée (à faire maintenant, peu coûteux)
1. Signal calculé à la clôture de la barre `t` → ordre soumis pour la barre `t+1`.
2. Prix de référence : **ouverture de `t+1`** (ordre au marché) ou **VWAP de `t+1`**
   (exécution étalée). Jamais le close de `t`, jamais le plus haut/plus bas de la barre.
3. Quantité exécutée `= min(quantité voulue, POV · volume de la barre)`. Le reliquat est
   **reporté** sur la barre suivante, pas annulé silencieusement — un ordre de 3 jours d'ADV
   doit prendre 3 jours et payer 3 jours de dérive.
4. Coût = `impact.total_cost_bps(...)` avec la vol et le volume **de la barre** (axe 4 § 3).
5. Barres en **halt** ou en enchère : aucun fill.

À lui seul, L1 supprime la majorité du biais optimiste. C'est le meilleur rapport
effort/vérité de tout le dépôt.

### L2 — File d'attente du carnet (obligatoire avant tout ordre limite en 1 h)
Un ordre limite ne se remplit pas parce que le prix a « touché » son niveau : il se remplit
quand le volume échangé à ce niveau dépasse ce qui était **devant** lui.
```
à la soumission au niveau p :   Q_devant = taille affichée en p à l'instant d'arrivée
à chaque trade en p :           Q_devant ← max(0, Q_devant − volume_échangé)
fill  quand Q_devant == 0 :     quantité = volume_échangé − Q_devant_avant   (partiel possible)
```
Hypothèse par défaut : **les annulations devant nous ne nous font pas avancer** (elles sont
réparties uniformément et on ne modélise que les trades). C'est l'hypothèse pessimiste, donc
la bonne par défaut ; l'hypothèse optimiste inverse est le second biais classique.

Deux mesures à produire systématiquement avec L2 :
- **markout** à +1 s, +10 s, +60 s après chaque fill : si le prix bouge contre nous juste après
  nos exécutions, notre alpha est de la **sélection adverse** déguisée ;
- **taux de fill conditionnel** : le pourcentage d'ordres limites remplis, et ce qu'aurait fait
  la stratégie sur les ordres non remplis. Un backtest qui suppose 100 % de fill sur des
  limites passives surestime l'alpha *et* sous-estime le coût — les deux dans le même sens.

### L3 — Rejeu MBO (message-by-order)
Moteur d'appariement complet sur données MBO (Databento & assimilés). Hors périmètre
aujourd'hui : coût des données et complexité sans commune mesure avec l'enjeu actuel.

## 3. Parité backtest ↔ live

`SimBroker` sert déjà au backtest et au paper : c'est le bon principe et il faut le préserver.
La bonne façon de l'étendre est un **modèle de fill injectable** derrière l'interface `Broker`,
pas un second broker :
```
FillModel (protocole)
 ├── ImmediateFill   (existant — à étiqueter « OPTIMISTE, tests seulement »)
 ├── NextBarPOVFill  (L1)
 └── QueueFill       (L2, exige un carnet L1/L2)
```
Ainsi le plugin reste « un fichier auto-enregistré » conforme à la discipline du dépôt, et le
chemin de production `run_live.py` ne change pas.

## 4. Sécurités automatisées : la machine à états qui manque

Le dépôt possède de bons garde-fous **individuels** (`dd_kill_switch`, `live_guards`,
`reconcile`, idempotence `_seen`, alertes, `convex_drawdown_scaler`). Il manque le **concept
unifiant** : un état d'exécution explicite, et des transitions déclenchées par des garde-fous.

```
NORMAL  ──(1 seuil franchi)──►  REDUCED       gross × 0,5, aucun nouveau nom
        ──(2 seuils / DD dur)─►  FLATTEN_ONLY  seuls les ordres RÉDUCTEURS de risque passent
        ──(incohérence/perte de flux)──► HALTED  annulation de tout, plus aucun envoi
retour à NORMAL : humain + réconciliation propre, JAMAIS automatique
```

### 4.1 Contrôles pré-trade (par ordre, avant envoi)
| Contrôle | Seuil de départ | Notes |
|---|---|---|
| Notionnel maximum | 5 × le notionnel médian récent | anti-fat-finger, y compris bug de sizing |
| Collier de prix | limite à plus de 3 % du mid → rejet | protège des prix aberrants du fournisseur |
| Participation | `q ≤ POV · V_fenêtre` | axe 4 |
| Cadence | N ordres/minute max, N/jour max | un bug en boucle est un risque de **compte**, pas de marché |
| Idempotence | `client_order_id` déterministe | déjà en place — rejouer le résultat **réel**, jamais un FILLED fabriqué |
| Autorisation | whitelist symboles, short autorisé, marché ouvert | |

### 4.2 Limites de perte **par unité de temps** (l'échelle réclamée par le prompt)
Chaque robot a son propre budget, et le budget du livre n'est pas la somme des budgets :
| Horizon | Perte → REDUCED | Perte → FLATTEN_ONLY |
|---|---|---|
| 1 h / 4 h | −0,5 % du NAV du sleeve sur la séance | −1,0 % |
| Daily | −1,5 % | −2,5 % |
| Weekly | −3 % | −5 % |
| Monthly / livre | −8 % | `QUANT_INTRADAY_DD` (−15 %) — déjà branché |
Ces valeurs sont des **points de départ cohérents entre eux**, pas des paramètres calibrés :
elles doivent découler du budget de drawdown de l'axe 4 § 1 et être re-gatées ensemble.

### 4.3 Disjoncteur de slippage (à construire, la brique existe)
`research/exec_costs.measured_slippage` calcule déjà le slippage réel décision→fill.
Règle : si la **médiane glissante sur 20 fills** dépasse `3 ×` le coût modélisé
(`impact.total_cost_bps`) → **HALTED** + alerte CRITICAL. Distinguer avec le markout deux
causes qui n'appellent pas la même réaction : « le marché a bougé » (subir) contre « on se
fait ramasser systématiquement » (arrêter).

### 4.4 Fraîcheur des données et dead-man switch
- **Jamais trader sur une donnée périmée** : aucune nouvelle barre depuis 2 × l'intervalle
  attendu ⇒ pas d'ordre. Spread > 5 × sa médiane, ou carnet croisé/verrouillé ⇒ symbole ignoré.
- **Dead-man switch — la brique manquante la plus importante pour le live.** Le processus de
  risque émet un battement de cœur ; si l'exécution ne le reçoit pas pendant N minutes, elle
  **annule tout et se met en FLATTEN_ONLY**, sans instruction. Aujourd'hui, si `run_live.py`
  meurt entre l'envoi d'un ordre et la boucle suivante, personne ne ferme rien. Les exits 3/4
  et l'alerte Telegram de juillet préviennent un humain ; ils ne protègent pas le capital.
- **Réconciliation avant chaque cycle** : positions courtier == état interne, à la tolérance
  près. Écart ⇒ lecture seule + alerte. `live_guards` en fait déjà une partie (positions
  illisibles ⇒ broker écarté) : le principe « inconnu ≠ zéro » est le bon, il faut l'étendre
  à l'écart non nul.

### 4.5 Post-trade
- **TCA quotidien** modèle vs réalisé, par symbole et par sleeve.
- **Moniteur d'IC** : IC réalisé glissant sur 60 jours ; s'il est négatif avec `|t| > 2`,
  rétrogradation **automatique** en paper. C'est la version exécutable du principe
  champion/challenger déjà présent dans `ml/promotion.py`.
- **Journal de rejets** : toute erreur courtier stockée avec sa **cause** (acquis du correctif
  BitMart de juillet — à généraliser à tous les brokers).
- **Instantané de décision** conservé à la décision, pas à l'exécution (ADR-0028) : c'est ce
  qui permet de mesurer le slippage et l'IC sans reconstruire le passé. À préserver
  absolument — c'est un actif rare dans un projet de cette taille.

## 5. Ordre de mise en œuvre

1. `exec_lag = 1` par défaut + `NextBarPOVFill` (L1) → chiffre le biais optimiste actuel.
2. Coût non linéaire branché partout (backtest, screening, sabotage) → certains verdicts vont
   bouger ; c'est le but.
3. Machine à états + dead-man switch → condition de tout passage en live réel.
4. `QueueFill` (L2) → condition de tout robot intraday à ordres limites, donc condition de la
   seule voie économiquement viable vers le 1 h (axe 4 § 4.5).
