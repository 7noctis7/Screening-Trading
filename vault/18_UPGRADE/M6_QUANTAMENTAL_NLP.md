# M6 — Quantamental : transcriptions, experts et facteur de sentiment orthogonal

Retour à [[18_MODULES_AVANCES]].
Existant : `packages/sentiment/` (FinBERT + lexique + RSS point-in-time + `history.record_and_delta`),
`packages/fundamentals/` (ratios, DCF, scoring), `packages/llm/` (garde anti-hallucination).
Nouveau code utile ici : `packages/ranking/orthogonalize.py`.

> Ce module n'a pas besoin d'un moteur de scoring supplémentaire — il en a déjà deux. Il a
> besoin d'un **protocole** : d'où vient le texte, à quelle seconde il devient public,
> comment on le standardise, et de quoi on le débarrasse avant de l'appeler alpha.

## 1. Le risque n° 1 est un look-ahead d'un genre nouveau

Un LLM interrogé sur une transcription de 2015 **connaît la suite**. Son jugement
« ce discours est optimiste » est contaminé par ce qu'il a lu du cours des années suivantes.
Aucune purge, aucun embargo, aucune CV ne protège de cela : la fuite est dans les **poids du
modèle**, pas dans les données.

Trois parades, par ordre de rigueur :
1. **Extraction mécanique seulement** : compter des mots d'un dictionnaire figé
   (Loughran-McDonald), mesurer des densités, extraire des chiffres. Aucun jugement demandé
   au modèle → aucune contamination possible.
2. **Modèle à cutoff antérieur** à la période de test, et le prouver : le hash du modèle et
   sa date de coupe entrent dans le ledger au même titre que le hash de config.
3. **Tâches strictement locales** : « cette phrase contient-elle une prévision chiffrée ?
   laquelle ? » est extractif et vérifiable. « Cette société va-t-elle surperformer ? » ne
   l'est pas et ne doit jamais être demandé.

En pratique : un backtest est **honnête** sous (1), **défendable** sous (2), et **nul** sans
l'un des deux. Le live, lui, n'a pas ce problème — d'où un piège supplémentaire : un backtest
sous (1) et un live sous LLM libre ne mesurent pas la même stratégie.

## 2. Ingestion et horodatage

| Source | Temps de connaissance | Piège |
|---|---|---|
| Transcription d'*earnings call* | **fin de l'appel** (souvent 60–90 min après l'ouverture) | La transcription écrite paraît 2 à 24 h plus tard ; utiliser sa date de publication, c'est retarder ; utiliser la date de l'appel, c'est anticiper si l'on n'a pas le texte à ce moment. Retenir : `max(fin d'appel, disponibilité du texte)`. |
| Communiqué de résultats (8-K) | horodatage du dépôt / du fil | Le tableau chiffré arrive avant l'appel : deux événements distincts, deux lignes. |
| 10-K / 10-Q (section MD&A) | `acceptanceDateTime` EDGAR | Jamais `periodOfReport`. |
| Notes de recherche, révisions d'analystes | date/heure de publication du broker | Les agrégateurs republient un consensus **rétro-corrigé** : sans horodatage individuel, marquer `UNKNOWN` et exclure. |
| Presse / RSS | horodatage de l'item | Les republications rétro-datées sont fréquentes ; dédupliquer par hash du titre normalisé. |

Toutes ces lignes entrent dans le schéma bitemporel de [[17_AUDIT_INSTITUTIONNEL]] axe 1 :
clé primaire incluant `knowledge_time`, révision = nouvelle ligne.

## 3. Quantification : ce qu'on extrait réellement

**a) Ton (tone)** — sur dictionnaire **financier** (Loughran-McDonald), jamais généraliste :
en finance, « liability », « tax » ou « cost » ne sont pas négatifs.
```
tone = (n_positifs − n_négatifs) / (n_positifs + n_négatifs)
```

**b) Incertitude et prudence du management** — les listes `uncertainty`, `weak modal`
(« may », « could », « might ») et `strong modal` (« will », « must ») de LM :
```
ratio_incertitude = n_uncertainty / n_mots
ratio_certitude   = n_strong_modal / (n_strong_modal + n_weak_modal)
```
La littérature est constante sur un point : **l'incertitude prédit mieux que le ton**, et
elle prédit surtout la **volatilité** future, pas le signe du rendement. En conséquence, ce
signal a sa place dans le **dimensionnement** (réduire la taille avant une publication à
forte incertitude) plutôt que dans le classement directionnel.

**c) Séparer discours préparé et questions-réponses.** Les remarques préparées sont écrites
et relues ; l'information est dans le **Q&A** : longueur des réponses, taux d'esquive,
nombre de questions non répondues, écart de ton entre les deux sections. `delta_tone =
tone(Q&A) − tone(préparé)` est un signal à part entière, et il est mécanique à calculer.

**d) « Lazy prices » — le changement plutôt que le niveau.** La similarité cosinus entre la
section MD&A d'un dépôt et celle du dépôt précédent de la MÊME société : une réécriture
substantielle précède les mauvaises nouvelles. Purement mécanique, sans LLM, et robuste.
```
signal_changement = 1 − cos( tfidf(MD&A_t), tfidf(MD&A_(t−1)) )
```

**e) Momentum de révision des analystes** — deux formes, complémentaires :
```
ampleur : (consensus_t − consensus_(t−3m)) / |consensus_(t−3m)|
souffle : (n_révisions_hausse − n_révisions_baisse) / n_révisions        sur 3 mois
```
Le **souffle** est plus robuste que l'ampleur (insensible aux valeurs proches de zéro).

## 4. Standardisation : la seule qui ne fabrique pas de signal

Un score de sentiment brut est dominé par le **jargon sectoriel** et par le style de chaque
direction. Trois standardisations à empiler, dans cet ordre :

1. **Intra-société** (série temporelle) : `z = (score_t − médiane des k derniers scores de la
   MÊME société) / MAD`. C'est ce que fait déjà `sentiment/history.record_and_delta`, et
   c'est le bon réflexe : le niveau absolu est dans le prix, la **variation** ne l'est pas.
2. **Intra-secteur** (coupe transversale), avec taille de groupe minimale ≥ 10
   (`orthogonalize.group_z`).
3. **Robuste** : médiane/MAD, écrêtage à ±3. Les distributions de sentiment ont des queues
   franches (une seule alerte fraude déplace une moyenne).

## 5. Intégration comme facteur orthogonal

Un facteur de sentiment non nettoyé est presque toujours du **PEAD déguisé** ou du
**momentum déguisé** : le sentiment est haut parce que le titre monte. Procédure :

```
1. z_sent  = group_z( score_sentiment, secteurs )
2. B       = [ surprise_de_résultats , momentum_12_1 , taille , bêta , indicatrices secteur ]
3. z_pur   = neutralize( z_sent, B, weights = 1/variance_spécifique )
4. IC(z_pur) mesuré HORS ÉCHANTILLON, sur rendement RÉSIDUEL, par horizon
5. combine_signals( [autres facteurs, z_pur], ics_mesurés )   →   Omega^-1 · ic
```

Le test qui décide de l'admission n'est pas « l'IC de `z_sent` est-il positif ? » mais
**« l'IC de `z_pur` reste-t-il positif une fois la surprise de résultats retirée ? »**. Si
non, le facteur n'apporte rien que `packages/events/` ne capture déjà — et il faut le dire,
pas l'empiler.

## 6. Horizon : où ce facteur a le droit de vivre

Par [[M3_M4_DECAY_ET_EXECUTION]], l'horizon optimal vaut `1,81 × demi-vie de l'IC`. La
demi-vie d'un signal de sentiment de presse se compte en **jours**, celle d'un signal de
transcription en **semaines** (l'information est plus dense et moins largement traitée).
Conclusion opérationnelle : le sentiment de presse appartient au robot **Daily**, la
transcription au robot **Weekly**, et aucun des deux n'a d'utilité en Monthly. Mesurer la
demi-vie avant de brancher — c'est une ligne de `alpha_decay`.

## 7. Pièges

- **Deux moteurs, deux distributions.** `sentiment/__init__.py` bascule entre FinBERT et
  lexique selon la présence de `transformers`. Les scores ne sont pas comparables : un
  historique construit moitié FinBERT moitié lexique est inexploitable. Journaliser le
  moteur avec chaque score, et refuser de mélanger dans une même série.
- **Couverture inégale.** Les grandes capitalisations ont dix fois plus d'articles. Un
  z-score transversal compare alors un signal bien estimé à du bruit. Pondérer par
  `sqrt(n_articles)` ou exclure sous un seuil de couverture.
- **Le sentiment de marché n'est pas un facteur transversal.** L'agrégat (indice de peur,
  ton global de la presse) est un signal de **régime**, à brancher sur l'exposition, pas sur
  le classement.
- **Coût des LLM.** Un scoring quotidien sur 200 sociétés × 20 articles est un budget récurrent.
  `packages/llm/` route déjà vers Ollama en local : c'est le bon choix par défaut, et il rend
  la reproductibilité possible (modèle figé, température 0, prompt hashé au ledger).
