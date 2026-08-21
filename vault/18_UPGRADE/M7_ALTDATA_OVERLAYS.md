# M7 — Pipeline de données alternatives et overlays de risque

Retour à [[18_MODULES_AVANCES]]. Code : `packages/research/causality.py`.
Existant réutilisable : `packages/storage/` (bronze/silver/gold), `packages/common/pit_guard.py`,
`packages/regime/real_macro.py` (vintages ALFRED — la référence interne), `packages/data/funding.py`.

## 1. Architecture d'ingestion — trois couches, une seule règle

```
BRONZE   réponse brute de l'API, telle quelle, horodatée à la RÉCEPTION, jamais réécrite
   ↓     (c'est la seule couche qui autorise de rejouer l'histoire quand un parseur change)
SILVER   normalisé : unités, fuseaux, désaisonnalisation, révisions comme NOUVELLES LIGNES
   ↓     clé (source, entité, période, knowledge_time) — jamais d'UPDATE
GOLD     features alignées sur le calendrier d'univers, décalées de la latence de publication
```

**La règle unique** : une observation d'alt-data n'entre en GOLD qu'avec un
`realtime_start = date_observation + latence_de_publication`, et `pit_guard.pit_filter` la
filtre à chaque date de backtest. `causality.pit_align()` construit ces enregistrements.
Toute étude qui compare `x(t)` au rendement de `t` à `t+1` sans cette latence mesure une
information dont personne ne disposait — c'est la fuite la plus banale et la plus fatale de
l'alt-data, parce qu'elle produit des résultats spectaculaires.

## 2. Protocole de validation d'une source (dans cet ordre, sans exception)

1. **Prior économique écrit avant le test.** Par quel mécanisme cette série influencerait-elle
   ce prix ? Sans réponse en une phrase, ne pas tester : on entre dans le data-mining.
2. **Stationnariser.** Différences logarithmiques ou variations en glissement annuel, jamais
   les niveaux. Granger sur des niveaux non stationnaires rejette pour des raisons de tendance
   commune (`difference=True` par défaut dans le module).
3. **Granger dans les DEUX SENS** (`granger_both_ways`). Une source n'est exploitable que si
   `x → y` est significatif **et** `y → x` ne l'est pas. Si le marché prédit la donnée autant
   que l'inverse, il n'y a aucune avance à capter — seulement une co-évolution.
4. **Information mutuelle avec test par permutation** (`mi_permutation_test`) pour les
   relations non linéaires que Granger rate (seuils, saturations, effets en U). Vérifié :
   sur `y = x² + bruit`, Granger ne conclut pas, l'IM oui.
5. **Correction multi-tests** : `k` sources × `h` horizons essais. `sidak_level(0,05, k·h)` —
   12 sources sur 5 horizons donnent un seuil individuel sous 0,1 %. Ce n'est pas une
   sévérité gratuite : sans elle, 60 essais à 5 % produisent 3 « découvertes » par pur hasard.
6. **Horizon compatible avec la latence.** Une série publiée avec 20 jours de retard ne peut
   pas alimenter un robot 4 h. Tester l'horizon que la latence autorise, pas celui qui donne
   le meilleur résultat.
7. **Gate standard** (`packages/research/gate.py`) : placebo → DSR → PBO → sabotage. Une
   source alt-data est un candidat comme un autre.

## 3. Les cinq familles, et ce qui les casse

### 3.1 Semi-conducteurs et matériel (MoEA Taïwan, SEMI, revenus mensuels)
- **Latence** : les statistiques douanières taïwanaises paraissent au cours du mois suivant ;
  les revenus mensuels des sociétés cotées à Taïwan sortent vers le 10. Horizon exploitable :
  mensuel, au mieux hebdomadaire par interpolation — **jamais intraday**.
- **Le piège qui invalide tout : le Nouvel An chinois se déplace entre janvier et février.**
  Une variation en glissement annuel de janvier compare un mois de production à un mois de
  congés. Correction standard : agréger **janvier + février** en une seule observation, ou
  désaisonnaliser sur le calendrier lunaire. Sans cela, on « découvre » chaque année une
  causalité qui n'est qu'un décalage de calendrier.
- **Révisions** : les douanes révisent. Chaque révision est une ligne, jamais un écrasement.
- **Mapping vers les titres** : les exportations taïwanaises ne se répartissent pas
  proportionnellement aux capitalisations. Le signal est **sectoriel** ; l'attribuer à un nom
  précis suppose une clé de répartition qui, elle, n'est pas mesurée.

### 3.2 IA et logiciel (Hugging Face, GitHub)
- **Les compteurs de téléchargements sont cumulés et révisés** : ne jamais les différencier
  naïvement (une correction rétroactive produit un pic de −40 % qui n'a jamais existé).
- **Les étoiles sont une métrique de vanité**, largement gonflée par des campagnes et des
  bots. Les **commits** et le **nombre de contributeurs distincts** résistent mieux ; la
  bonne transformation est `log(1 + commits)` en écart à la moyenne du dépôt.
- **Saisonnalité hebdomadaire et jours fériés** très marqués : désaisonnaliser par jour de
  semaine avant tout test, sinon Granger détecte le week-end.
- **Biais du survivant** : les dépôts abandonnés cessent d'apparaître dans les classements.
  Figer la liste des dépôts suivis **à la date d'entrée** dans l'étude, jamais aujourd'hui.
- **Mapping vers les cotés** : la majorité de l'infrastructure IA open-source n'appartient à
  aucune entité cotée. Signal de **thème**, à brancher sur une exposition sectorielle, pas sur
  un classement de titres.

### 3.3 Blockchain et actifs numériques (nœuds RPC, agrégateurs on-chain)
- **Finalité** : un bloc récent peut être réorganisé. Ne traiter une donnée comme connue
  qu'après une profondeur de confirmation (Bitcoin : ~6 blocs ; Ethereum : époque finalisée).
  Sans cela, le backtest utilise des transactions qui n'ont jamais existé.
- **Les étiquettes d'adresses sont révisées rétroactivement.** Un flux « sortie d'exchange »
  d'il y a six mois change de valeur quand une adresse est reclassée aujourd'hui : c'est une
  violation point-in-time **invisible**, car la série se réécrit silencieusement. Conserver le
  vintage d'étiquetage avec la donnée, ou n'utiliser que des métriques **non étiquetées**.
- **Métriques robustes** (sans étiquetage) : vélocité de la monnaie, gas burn, frais médians,
  taille moyenne des transactions, hashrate. Le hashrate porte la structure d'ajustement de
  difficulté (paliers de ~2 semaines) : lisser sur cette période, sinon on mesure le protocole.
- **Whale alerts** : majoritairement des transferts internes entre portefeuilles d'une même
  entité. Signal très bruité, à ne retenir que net des transferts intra-entité connus.
- **Funding et open interest** : `packages/data/funding.py` et `deriv_normalizer.py` existent.
  Ce qui manque : l'**open interest** normalisé par capitalisation, et le **skew** de
  volatilité — les deux prédisent mieux les liquidations que le funding seul.

### 3.4 Liquidité bancaire (FRED, BCE)
- `packages/regime/real_macro.py` gère déjà les vintages ALFRED : c'est la référence interne,
  et toute nouvelle source macro doit être branchée dessus, jamais sur l'API temps réel.
- **Séries utiles** : spread SOFR − OIS, volumes SOFR/ESTR, utilisation des facilités de repo
  (RRP/SRF), spreads de swap, base cross-currency. Elles mesurent le **stress de financement**,
  qui est un régime, pas un signal transversal.
- **Piège de calendrier** : les publications ont un décalage d'un jour ouvré et les jours
  fériés diffèrent entre zones. Aligner sur le calendrier de l'univers, pas sur le calendrier
  de la source.
- **Piège d'interprétation** : les niveaux de facilités reflètent souvent des changements de
  règles (plafonds, éligibilité) et non du stress. Toute rupture de série doit être datée et
  traitée comme une variable indicatrice, sinon le modèle apprend une réforme réglementaire.

### 3.5 Logistique, climat, activité physique (NOAA/Copernicus, GDELT, fréquentation)
- **GDELT** : mise à jour toutes les 15 minutes, mais le volume est dominé par la
  démultiplication médiatique. Toujours normaliser par le **nombre total d'articles** de la
  fenêtre, sinon on mesure l'activité de la presse.
- **Imagerie satellite** : les données manquantes ne le sont **pas au hasard** — la couverture
  nuageuse est corrélée à la météo, donc à l'activité mesurée. Imputer, c'est fabriquer du
  signal ; il faut modéliser l'absence, ou restreindre aux fenêtres claires et l'assumer.
- **Météo** : effet réel mais faible et déjà largement arbitragé sur les matières premières.
  Prior économique exigeant.

## 4. Overlays : comment une source agit sur le système

Un signal d'alt-data validé n'entre **jamais** directement dans le classement transversal.
Il agit comme **modificateur d'exposition** ou **disjoncteur sectoriel** — deux mécanismes
distincts, avec des exigences distinctes.

### 4.1 Modificateur de levier (continu, borné)
```
z      = z robuste de la source (médiane/MAD, écrêté à ±3, dans son propre historique)
m      = clip( 1 + beta_overlay · z , m_min , 1.0 )
gross  = gross_vol_target · m(régime) · m(overlay_1) · … · taper(drawdown)
```
Quatre règles non négociables :
1. **`m <= 1` toujours.** Un overlay réduit l'exposition, il ne l'augmente jamais. Autoriser
   `m > 1` revient à faire du market timing avec une donnée non gatée, et à mettre le levier
   maximal au moment où l'on est le plus confiant — c'est-à-dire le plus exposé à l'erreur.
2. **Bornes explicites** : `m_min = 0,4` par défaut. Un overlay qui peut aller à 0 est un
   disjoncteur, pas un modificateur : le traiter comme tel (§ 4.2).
3. **Hystérésis** : activer à `z < −1,5`, désactiver à `z > −0,8`. Un seuil unique produit des
   allers-retours coûteux exactement quand les coûts explosent.
4. **Produit, pas somme.** Trois overlays multiplicatifs à 0,7 donnent 0,34 : la composition
   doit être plafonnée globalement (`m_total >= m_floor`), sinon l'empilement d'overlais
   raisonnables éteint le portefeuille.

### 4.2 Disjoncteur sectoriel (discret, asymétrique)
Réservé aux ruptures : effondrement du hashrate, dépeg d'un stablecoin, spread SOFR-OIS
au-delà d'un seuil historique, arrêt d'exportations.
```
condition franchie  →  sleeve concerné en FLATTEN_ONLY (cf. axe 5), pas en REDUCED
retour à la normale →  humain + délai minimal (24 h), jamais automatique
```
L'asymétrie est délibérée : sortir vite est peu coûteux, rentrer vite dans un régime
d'illiquidité est ce qui ruine.

### 4.3 Ce qu'un overlay doit prouver avant d'être branché
Un overlay est un **paramètre de plus**, donc un essai de plus : seuils, `beta_overlay`,
bornes et hystérésis se comptent dans le DSR au même titre qu'un signal d'alpha. Le test
minimal : le backtest **avec** overlay doit dominer le backtest **sans** sur le Sharpe **et**
sur le max drawdown, sur des chemins CPCV — pas sur une seule courbe. C'est exactement le
protocole de `make preset-lab`, à étendre aux overlays.

## 5. Ce qu'il ne faut pas espérer

La quasi-totalité des sources ci-dessus est **mensuelle ou hebdomadaire**, avec des latences
de plusieurs jours. Elles ne peuvent donc pas alimenter les robots 1 h / 4 h — et par
[[M3_M4_DECAY_ET_EXECUTION]], un signal de demi-vie longue n'y aurait de toute façon pas sa
place. Leur usage naturel est :
- **Monthly / Weekly** : inclinaison sectorielle et thématique ;
- **tous horizons** : overlays de risque et disjoncteurs.

Enfin, l'ordre de priorité honnête : ces sources sont **le dernier** chantier, pas le premier.
Tant que l'historique de prix mute à chaque dividende (finding F1) et que le coût est un
forfait linéaire (finding F2), ajouter douze flux exogènes ajoute douze occasions de se
tromper avec plus de conviction.
