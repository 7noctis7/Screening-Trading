# Audit « Hugging Face → alpha » — Quant Terminal

> Date : 2026-09-30 · Base : `4d4ea21` (#411) · Statut : **ANALYSE ET PROPOSITION**.
> Aucun module existant n'a été modifié. Aucun poids, aucun dataset, aucun jeton n'a été
> téléchargé ni commité. Aucun chiffre de performance n'est avancé : ce qui n'a pas été
> mesuré est **UNCALIBRATED**, ce qui n'a pas été trouvé est **n/d**.

**Limite de méthode, à lire d'abord.** Le conteneur d'audit n'atteint pas `huggingface.co`
(politique réseau : `CONNECT` refusé, y compris par récupération web). Aucune model card ni
dataset card n'a donc été lue directement. Les faits sur les modèles et les datasets viennent
de **résultats de moteur de recherche** : papiers arXiv, dépôts GitHub, pages tierces. Chacun
est marqué **« à vérifier »** et la commande exacte de vérification est en annexe C. Le
conteneur n'a pas non plus les bases de prix, ni `data/news.csv`, ni le ledger du VPS.

---

## 0. Les règles qui contraignent la mission (AGENTS.md, ADR)

1. **Aucun signal en production sans le gate 4 étages** (placebo → DSR → PBO → sabotage). Les
   rejets sont publiés (`/api/failures` → `/echecs`, lus depuis `research/hypotheses.jsonl`).
2. **N du DSR compté au ledger, jamais choisi** (`gate.verdict_hors_echantillon`, ADR-0065) ;
   un balayage compte pour tous ses scénarios (ADR-0205).
3. **Mandat données réelles** : synthétique uniquement dans `tests/` (AGENTS.md §5.3).
4. **Pas de LLM ni d'agent dans le chemin chaud** (ADR-0007). `packages/llm` ne sert que du
   texte ; `packages/intelligence` n'importe ni `execution` ni `risk` (test AST).
5. **Plugins** : 1 fichier auto-enregistré, < 400 lignes/fichier, < 50 lignes/fonction.
6. **Point-in-time** : un titre n'est utilisable qu'à `max(date, vu_le)` (ADR-0162).
7. **Mesurer avant de brancher** : un nouveau module naît `STATUT = "SHADOW"` et passe
   `vault/15_CERTIFICATION.md` avant la production (ADR-0202 : la production se mesure par rejeu).
8. **La chaîne NLP locale a été retirée** après quatre échecs mesurés (ADR-0170) ; un GPU
   n'est loué que si une mesure a démontré quelque chose (ADR-0161).
9. **Aucune cible de Sharpe en entrée** (ADR-0050). Tout garde-fou publie son compteur (§8).
10. **Aucun identifiant de modèle** dans le code, les commits ou les artefacts (ADR-0166).

### Contradictions entre le prompt de mission et l'état du dépôt (le dépôt gagne)

| Le prompt dit | Le dépôt dit | Conséquence |
|---|---|---|
| « Le coût du turnover n'est pas instrumenté » (README §« ne sait pas faire » n°2) | ADR-0207 (30/09) : frais estimés au barème et marqués `estimated` ; la colonne `slippage` (implementation shortfall) est écrite à l'ouverture depuis le 30/09 ; la jambe de **vente** n'est pas mesurée. Le rejeu (`preset_rejeu`) applique déjà des frais. | Instrumentation **partielle**. Le coût réel reste UNCALIBRATED (journal trop maigre), le coût modélisé existe. |
| « P0-3 bande d'inaction » comme prérequis | ADR-0206 : la bande de 3 % ne vit que dans les backtests hérités. La production applique max(0,5 % du capital, 5 $) et souffre plutôt d'un excès de rotation (4 082 ordres pour 503 décisions au rejeu du 25/09). `docs/ROADMAP.md` (25/08) est périmé sur ce point. | P0-3 n'est pas le prérequis. Le vrai prérequis est la mesure de rotation au rejeu (TODO P1, ADR-0206). |
| « HRP actuel pour l'allocation » comme baseline | Le robot trade un **ERC** + blackout + tilt momentum + plafond adaptatif + DD-target + portes (`backtest/preset_weights.py::preset_latest_weights_explique`). HRP est l'allocateur de `/risk` et de l'analyse de portefeuille importé (ADR-0100). Le prior Black-Litterman de `portfolio/conviction.py` est l'ERC. | Baseline du robot = **rejeu ERC de production**. HRP n'est la baseline que pour `/risk` et `/analyse-portefeuille`. |
| « Le test sur l'arbre syntaxique doit rester vert » | Il l'est, mais il ne vérifie que le sens intelligence → exécution. Le sens inverse (chaîne d'ordres → modèle) **n'est pas testé et n'est pas tenu** (§1.4). | Prérequis bloquant B1. |

---

## 1. Cartographie du code existant (lecture seule)

« Prod » = atteignable depuis `scripts/run_live.py`, `apps/api/snapshot.py` ou
`apps/api/main.py`. **Attention** : l'outil de `make certification` rate deux formes d'import
(§1.4). La colonne a été recalculée ici par une fermeture AST qui les gère.

### 1.1 Tableau couche → modules → état → faiblesse

| Couche | Modules (chemins exacts) | Entrées → sorties | État | Faiblesse documentée |
|---|---|---|---|---|
| **1. Signal technique** | `packages/indicators/{trend,momentum,volatility,smc_lux_tp}.py` (registre `indicators`), `ranking/factors.py` (registre `factor_calcs`), `screening/`, `backtest/preset_helpers.py` (tilt momentum, régime, ampleur) | OHLCV quotidien → z-scores, sélection top-K, poids | **câblé** (sélection = qualité, repli momentum) | IC du score de sélection +0,0202, t = 0,76 sur 83 fenêtres (`04_JOURNAL`, 07/09) : indiscernable de zéro. La règle tradée est indiscernable de QQQ + cash à même vol (ΔSharpe +0,11, IC [−0,51 ; +0,72], p = 0,73, TODO 25/09). |
| **2. Fondamental** | `fundamentals/{sec_provider,yfinance_provider,fmp_provider,scoring,valuation}.py`, `backtest/preset_weights.py::qualite_de_production` | SEC XBRL companyfacts (US) + cours yfinance → `combined_score` → **choix de l'univers** | **câblé** (décide l'univers du robot) | **Non point-in-time** (ROADMAP P2-5) : le score du jour s'applique au passé ; sélection qualité étiquetée UNCALIBRATED (ADR-0203). |
| **3. Sentiment / news** | `sentiment/{finbert,lexicon,rss,corpus,pit,news_backtest,risk_gate,portefeuille}.py`, `research/alpha_incremental.py` | Titres RSS → score [−1, 1] (FinBERT si `transformers`, sinon lexique) → section `sentiment` du snapshot (affichage, `conviction`) | **câblé en affichage**, jamais dans les poids ; section coupée à l'exécution (`QUANT_LIVE_LITE=1`) | Corpus `data/news.csv` local (gitignoré, absent du conteneur) : 2 375 titres, 84 % rétro-publiés au 16/09 (ADR-0170). `alpha_incremental` n'a jamais produit de mesure : « aucun événement exploitable » (prix absents). `news_backtest` ne score qu'au lexique. |
| **3bis. Événements** | `events/{earnings,ipos}.py`, route `/api/events` | Calendrier FMP/yfinance → BPA/revenus, blackout | **câblé** | `/events` ne contient **aucune news** : ni dédoublonnage ni regroupement à faire là aujourd'hui. |
| **4. Régime / volatilité** | `backtest/cov_risk.py` (Ledoit-Wolf 120 j) → DD-target ; `portfolio/{garch,risk_overlay,vol_managed}.py` ; `regime/{vol_regime,hmm_causal,real_macro,classifier}.py` | Rendements → vol prévue / multiplicateur d'exposition | DD-target sur covariance **échantillon** : **câblé**. GARCH : **affichage `/risk`**. Overlay EWMA : opt-in `QUANT_RISK_OVERLAY=1`. `hmm_causal` : **non câblé** | `vol_regime` ajuste son HMM sur tout l'échantillon (fuite si câblé en backtest, finding F3). GARCH par grille (α, β), jamais comparé en QLIKE à l'EWMA. |
| **5. ML** | `apps/api/snapshot.py::_ml_section` ; `ml/{cv,cpcv,labeling,meta,meta_smc,validation_edge,promotion,calibration,uniqueness}.py` ; `scripts/train_model.py` ; `mlops/` | 10 features prix (mom. 20/60, SMA50, RSI, ATR/prix, mom. ajusté, distance au plus-haut 52 s., reversal 5 j, proxy PEAD, régime de vol) → P(hausse à **H = 21 j**), label binaire `c[t+H] > c[t]`, pas de 5 barres, cross-section | **affichage** (`/ml`, colonne `ml_score`) ; section coupée à l'exécution | Artefact en production : **AUC 0,504, Brier 0,2496, DSR non calculé** (`docs/AI_ARCHITECTURE_AUDIT.md`). Validation : `PurgedKFold` 5 plis, embargo 1 % (jours calendaires, QML-011). Edge UNCALIBRATED tant que la distribution nulle manque (TODO P2). |
| **6. Allocation** | robot : `backtest/preset_weights.py` (ERC + blackout + tilt + plafond + DD-target + portes) ; cœur QQQ ; `portfolio/budget_poches.py` (crypto ≤ 15 %). Affichage : `portfolio/optimize.py` (HRP, min-var, ERC), `black_litterman.py`, `conviction.py` | Covariance → poids | **câblé** (ERC) ; HRP/BL **affichage** | `k_signal` médian = 1 (ROADMAP P3-1) : la covariance n'a qu'une direction fiable. BL n'existe que si l'IC mesuré est robuste, ce qui n'est pas le cas aujourd'hui (`conviction.py`). |
| **7. Entrée / sortie** | `execution/rebalance_plan.py`, `risk/order_gate.py`, `run_live._broker_targets` (bande 0,5 % du capital) ; SHADOW : `execution/bande_adaptative.py`, `strategies/sorties_suiveuses.py`, `backtest/rejeu_sorties.py` | Poids cibles → ordres (ventes d'abord) | **câblé** (sortie = rééquilibrage uniquement) | Aucune sortie entre deux décisions (ADR-0208). Un suiveur ATR a déjà été retiré (ADR-0052 : Sharpe 0,53 → 0,38). `make preset-sorties` et la bande adaptative attendent une mesure sur le VPS. |

### 1.2 Le gate — comment un candidat y entre

- **Checker unique** : `packages/research/gate.py`. `promotion_verdict` (placebo p < 0,05,
  DSR > 0,5, PBO < 0,5, edge net > 0 ; un contrôle `None` est ignoré). `verdict_hors_echantillon`
  **calcule** le DSR et lit N au ledger ; `deployable` exige DSR > 0,95 (`protocole_oos`).
- **Étages** : placebo = permutations propres à chaque banc (`alpha_incremental`,
  `breakout`, `event_study`…) ; DSR = `portfolio/psr.py` ; PBO/CSCV = `portfolio/pbo.py` ;
  sabotage = `research/adversarial.py` (coûts ×1…×5 ancrés sur le spread de Roll, bruit).
- **Comptage des essais** : `research/ledger.py`. **Deux définitions coexistent** :
  `deflation_params` somme, par facteur, le `n_essais` d'un balayage ; `trial_count`, utilisé
  par `essais_du_ledger` → `verdict_hors_echantillon`, compte les **lignes**. Un balayage de
  870 scénarios consigné en une ligne compte donc 870 dans le premier et 1 dans le second
  (prérequis B3).
- **Publication des échecs** : `research/hypotheses.jsonl` (22 lignes dans le dépôt : 7
  `rejete`, 3 `promu`, 7 `en_test`) → `/api/failures` (dernier mot par facteur) → `/echecs`.
  Le ledger du VPS (bancs du 25/09 et du 30/09) n'est pas dans le dépôt : **n/d** ici.

### 1.3 Auto-enregistrement — où créer un fichier sans toucher au cœur

| Famille | Registre | Découverte | Pour ajouter |
|---|---|---|---|
| Indicateur | `indicators/registry.py::indicators` | import explicite dans `indicators/__init__.py` | fichier + `@indicators.register(...)` + **une ligne** d'import |
| Facteur | `ranking/factors.py::factor_calcs` | import du module | fichier + décorateur + import |
| Stratégie | `strategies/registry.py::strategies` | idem | idem |
| Règle de risque | `risk/rules.py::risk_rules` | idem | **hors périmètre de cette mission** |
| Source de prix | `data/registry.py::data_providers` | idem | idem |
| Source sociale | `social/sources/__init__.py::sources` | **automatique** (`pkgutil`) | un fichier suffit |

Aucun registre n'existe pour un **prévisionniste de volatilité** ni pour un **scoreur de
texte**. Les fiches ci-dessous proposent des modules SHADOW à fonction pure, appelés par un
banc (`scripts/*_lab.py`), sans nouveau registre.

### 1.4 Deux angles morts découverts pendant l'audit

1. **La chaîne d'ordres atteint déjà `transformers` par import.** Chemin vérifié par AST :
   `scripts/run_live.py` → `apps.api.snapshot` → `packages.sentiment` (`from packages import
   sentiment as S`) → `packages.sentiment.finbert` → `transformers`. La seule barrière est
   **à l'exécution** : `QUANT_LIVE_LITE=1` court-circuite la section `sentiment`
   (`common/safe_section.py::_LITE_SKIP`), et `QUANT_NEWS` doit valoir 1. Aucun test ne vérifie
   ce sens. Le test d'isolation existant (`tests/intelligence/test_intelligence.py`) ne couvre
   que le sens intelligence → exécution ; celui de `tests/mlops/test_isolation.py`, le sens
   mlops → exécution.
2. **`make certification` ne voit pas ces imports.** Sa regex (`common/certification.py::_IMPORT`)
   capture `packages.x.y` mais ni `from packages import x` ni les imports relatifs
   (`from . import finbert`). Résultat vérifié : `packages.sentiment` est déclaré non
   atteignable alors que `snapshot.py` l'importe. Un module SHADOW importé sous ces formes
   serait déclaré hors production à tort.

### 1.5 Données disponibles

| Source | Profondeur | Fréquence | Point-in-time | Délistés |
|---|---|---|---|---|
| Prix actions/ETF (`YAHOO.db`, `market.db`, locaux) | depuis 2015 en CI (`QUANT_HISTORY_DAYS=4015`) ; 624 séries réelles au banc du 25/09 | quotidien | prix : oui (fusion tracée, ADR-0064) | partiels : `data/delisted*.csv`, `make ingest-delisted` ; biais mesuré en **minorant** |
| Crypto (`crypto.db`, Binance) | n/d (≥ 2018 selon ROADMAP) | quotidien + 1 h (`ingest-crypto-intraday`) | oui | n/d |
| Macro FRED/ALFRED | vintages | variable | **oui** (`MacroStore`, ADR-0015) | — |
| Fondamentaux SEC XBRL | historique XBRL disponible, **non historisé** par le dépôt | trimestriel | **non** (P2-5) | non |
| News `data/news.csv` | depuis ~09/2026 ; 2 375 titres au 16/09 | quotidien (cron) | **oui** (`date` + `vu_le`) | — |
| Flux social `/x` | ~100 publications (24/09) | quotidien | `vu_le` | — |
| Cache OHLCV HuggingFace (`data/hf_cache.py`) | miroir des prix | — | — | — |

Aucune base n'est présente dans le conteneur : **aucune de ces profondeurs n'a été re-mesurée ici**.

---

## 2. Recherche Hugging Face — candidats retenus et écartés

Sources : résultats de recherche web (voir liens). **Toutes les lignes sont « à vérifier »**
par l'annexe C ; « n/d » = introuvable dans les sources consultées.

### 2.1 Retenus (sous conditions)

| Candidat | Éditeur / preuve | Licence (à vérifier) | Matériel | Fin des données d'entraînement | Couche visée |
|---|---|---|---|---|---|
| **FinText-TSFM** (`FinText/*`, ex. `Chronos_Small_2011_US`) | Rahimikia, Ni, Wang, « Re(Visiting) Time Series Foundation Models in Finance », [arXiv 2511.18578](https://arxiv.org/abs/2511.18578v1) ; [dépôt HF](https://huggingface.co/FinText/Chronos_Small_2011_US/commit/18d7c50a4633536d18bb67da21bf32ea800a0f2d) | Apache-2.0 selon [la page FinText](https://huggingface.co/spaces/FinText/README/commit/07f3442c5e9940f269c4b38e07012063417eb9e0) | architectures Chronos/autres, tailles Small+ : CPU plausible, **n/d** | **un modèle par année** (2007 → 2023) ; source des données **n/d** | 4 (vol), 1 (rendements) |
| **Chronos-2** (`amazon/chronos-2`) | Amazon, [arXiv 2510.15821](https://arxiv.org/pdf/2510.15821) | Apache-2.0 | 120 M paramètres, encodeur : CPU | corpus : Chronos + GIFT-Eval pretrain + synthétique ; « pas de données boursières ni de taux » selon [2511.18578](https://arxiv.org/pdf/2511.18578) ; date de fin **n/d** ; publié en 10/2025 | 4 (vol) |
| **TimesFM-2.5** (`google/timesfm-2.5-200m-pytorch`) | Google Research ; évaluation vol : [arXiv 2505.11163](https://arxiv.org/abs/2505.11163v1) | Apache-2.0 ([résumé](https://dev.to/andrew-ooo/timesfm-25-review-googles-time-series-foundation-model-14kp)) | 200 M, contexte 16 k : CPU lent, **n/d** | Google Trends, Wikipedia, synthétique ; date **n/d** | 4 (vol), challenger n°2 |
| **ProsusAI/finbert** | Araci 2019, arxiv:1908.10063 (card lue, §2.3) ; [dépôt GitHub](https://gittrend.io/repo/ProsusAI/finBERT) | **aucun tag de licence sur la card HF** ; Apache-2.0 sur le dépôt GitHub (seconde main) | BERT-base, poids 438 Mo : CPU | BERT (≤ 2018) + fine-tuning Financial PhraseBank (2014) | 3 — **déjà dans le dépôt** ; **sous réserve** (B9) |
| **Qwen/Qwen3-Embedding-0.6B** | Alibaba Qwen ; tête du MTEB en 06/2025 ([S. Willison](https://simonwillison.net/2025/Jun/8/)) | Apache-2.0 | 0,6 B : CPU, débit **n/d** | **n/d** (publié 06/2025) | 2 (10-K), 3bis (dédoublonnage) |
| **BAAI/bge-m3** | BAAI, 01/2024 ([fiche tierce](https://www.datalearner.com/en/ai-models/pretrained-models/BGE-M3-Embedding)) | MIT | ≈ 2,3 Go de poids : CPU | **n/d** | repli du précédent |
| **FNSPID** (`Zihan1004/FNSPID`) | Dong, Fan, Peng, KDD 2024, [arXiv 2402.06698](https://arxiv.org/abs/2402.06698v1) ; [GitHub](https://github.com/Zdong104/FNSPID_Financial_News_Dataset) | CC BY 4.0 | disque : volumineux, **n/d** | 15,7 M news, 4 775 sociétés, **1999 → 2023** | 3 (historique de news) |
| **eloukas/edgar-corpus** | Loukas et al., ECONLP 2021 ([bib](https://aclanthology.org/2021.econlp-1.2.bib)) ; [Zenodo](https://zenodo.org/records/5528490/latest) | Apache-2.0 selon le miroir HF (à vérifier) ; texte SEC public | disque **n/d** | 10-K par section, 1993 → 2020 | 2 (10-K) |
| **Salesforce/GiftEval** (+ `GiftEvalPretrain`) | Salesforce ; [card](https://huggingface.co/datasets/Salesforce/GiftEvalPretrain/blob/617ddbb9f1173b7e44013a55b2b4c9016bc253c8/README.md) | Apache-2.0 | — | — | **outil** : vérifier ce que Chronos-2 a vu |
| **autogluon/chronos_datasets** | Amazon ; [dépôt](https://huggingface.co/datasets/autogluon/chronos_datasets/tree/main/exchange_rate) | **par dataset** (`ds.info.license`) | — | contient `exchange_rate` (**du forex**) | **outil** de contamination |

### 2.2 Écartés — raisons écrites (à verser au Registre des échecs sous `statut: ecarte_amont`)

| Candidat | Raison |
|---|---|
| **SUFE-AIFLM-Lab/Fin-R1** (Apache-2.0, 7 B, base Qwen2.5-7B-Instruct, [arXiv 2503.16252](https://huggingface.co/SUFE-AIFLM-Lab/Fin-R1/blob/refs%2Fpr%2F4/README_en.md)) | (1) L'extraction fondamentale est **redondante** : `sec_provider` lit déjà les chiffres XBRL structurés, exacts et gratuits. (2) C'est un modèle **de raisonnement** : exactement le mode de panne mesuré qui a fait retirer la chaîne locale (raisonnement sans contenu, timeouts ; ADR-0168 à 0170). (3) 7 B sur CPU à 0 € : latence n/d mais défavorable. (4) Fin des données d'entraînement n/d, donc aucune période de test valide datable. |
| **Kronos-small / Kronos-base** comme **prédicteur de rendement** (MIT, [arXiv 2508.02739](https://arxiv.org/html/2508.02739v1), AAAI) | Pré-entraîné jusqu'en **06/2024** sur 12 Md de bougies de 45 places, dont NASDAQ et Binance ([résumé](https://arxiv.org/pdf/2508.02739)) : **notre univers est dans son entraînement**. La seule période valide (≥ 07/2024) fait ~27 mois, trop peu pour un DSR. FinText offre la même promesse **par année**, donc sans cette contamination. Réexaminable si FinText ne tient pas. |
| **Kronos** comme **générateur de données synthétiques** pour l'étage sabotage | **Conflit avec AGENTS.md §5.3** : le synthétique n'est autorisé que dans `tests/`. Un verdict de sabotage tiré de trajectoires générées est une recommandation issue de données synthétiques. Seul le propriétaire peut ouvrir une exception, par ADR. Défaut : écarté. |
| **TSFM zéro-shot sur les rendements** (Chronos, TimesFM, Moirai) | Deux évaluations indépendantes concluent à de mauvais résultats en zéro-shot et en fine-tuning sur les rendements : [2511.18578](https://arxiv.org/abs/2511.18578v1), [2606.27100](https://arxiv.org/pdf/2606.27100). Coûte des essais DSR pour un a priori défavorable. |
| **takala/financial_phrasebank** pour **entraîner** | Licence **CC BY-NC-SA 3.0** ([TFDS](https://tensorflow.org/datasets/community_catalog/huggingface/financial_phrasebank?hl=en)) : non commerciale et virale, incompatible avec un dépôt MIT redistribuable. Toléré au mieux comme jeu d'évaluation local, jamais commité : **à trancher par le propriétaire**. |
| **zeroshot/twitter-financial-news-sentiment** | Licence MIT (à vérifier), mais **pas d'horodatage** : inutilisable pour une mesure d'alpha. Au mieux un jeu d'évaluation du classifieur. |
| **yiyanghkust/finbert-tone** | Licence à vérifier : le HF la donnerait Apache-2.0 selon une [page tierce](https://mixpeek.com/model/yiyanghkust/finbert-tone-chinese), mais HKUST propose une [licence d'exploitation](https://exp-license.hkust.edu.hk/express_licensing/ip_detail?ip_id=25) de FinBERT. Tant que ce n'est pas levé : **non retenu**, et redondant avec ProsusAI/finbert déjà intégré. |
| **Salesforce/moirai-1.0-R-base** (card lue) | Licence **CC BY-NC 4.0** et « release for research purposes only » : incompatible avec un dépôt MIT. |
| **convaiinnovations/laya** (card lue) | Pas un modèle financier. Éditeur sans papier ; comparaisons contre des chiffres tiers « jamais mesurés ici ». Sa propre card dit que les checkpoints de base sont **sous la classe majoritaire** en zéro-shot (0,362 contre 0,461), que `act_probability` ne porte aucun signal et que le modèle sort sur-confiant. C'est un moteur de **décision** : exclu du chemin chaud par ADR-0007, et l'onglet `/x` classe par règles. |
| **sogosonnet/SP500-Chart-Dataset** (soumis) | **Introuvable** par recherche : aucune provenance vérifiable. Et l'usage visé (reconnaissance de figures chartistes) a déjà été mesuré sans succès : ADR-0184, « le motif ne prédit rien, sur deux marchés ». |
| Moirai-2, TiRex, TimeGPT | **Non évalués** (licence non vérifiée ; TimeGPT = API payante, hors infra 0 €). |

### 2.3 Cards lues et candidats soumis par le propriétaire (30/09)

Le propriétaire a collé cinq cards HF, lues **directement** (plus de seconde main pour
elles), et soumis une liste de datasets avec une architecture.

| Candidat | Ce que dit la card / la source | Verdict |
|---|---|---|
| **amazon/chronos-bolt-base** (et tiny 9 M, mini 21 M, small 48 M) | T5 encodeur-décodeur, ~100 Md d'observations, quantiles directs multi-pas, jusqu'à 250× plus rapide que Chronos ; `pip install chronos-forecasting`, `device_map="cpu"` documenté. Licence et fin d'entraînement **absentes du texte collé**. | **Retenu comme variante CPU de H1**, en **remplacement** d'un essai (pas en plus) : le budget DSR ne bouge pas. Les FinText sont des Chronos : la même bibliothèque devrait les charger (à vérifier). |
| **ProsusAI/finbert** | arxiv:1908.10063 ; **aucune licence** dans les tags ; poids en `pytorch_model.bin` (pickle), `tf_model.h5` et `flax_model.msgpack`, **pas de safetensors** ; dernier commit `4556d13` il y a plus de 3 ans. | **Sous réserve.** Par le critère « licence absente », il serait écarté ; le dépôt GitHub dit Apache-2.0. Au propriétaire de trancher. Indépendamment de ça : prérequis **B9**. |
| **Salesforce/moirai-1.0-R-base** | CC BY-NC 4.0, recherche seulement. | **Écarté** (§2.2). |
| **convaiinnovations/laya** | Apache-2.0, classifieur « System 1 ». | **Écarté** (§2.2). |
| **twelvedata/financial-world-model** | MIT, 50,9 Go, barres 1 j / 1 h / 1 min + texte + « trajectoires » ; un contributeur ; ré-uploadé « il y a 6 heures ». README non collé. | **À vérifier.** Intérêt réel : **deuxième source indépendante** pour la porte « source de données » de `15_CERTIFICATION.md` (divergence < 1 %). Conditions : provenance et droit de redistribution de données d'un fournisseur commercial sous MIT, ajustement, délistés, bornes de dates ; **révision épinglée** (le dépôt bouge) ; stockage hors dépôt (50,9 Go). |
| **Traders-Lab/TroveLedger** (soumis) | Selon [son README](https://huggingface.co/datasets/Traders-Lab/TroveLedger/blob/main/README.md) et [l'historique du projet](https://huggingface.co/spaces/Traders-Lab/README/blob/main/history.md) : quotidien sur plusieurs années, minute et horaire sur l'historique récent ; couverture « alignée sur le S&P/TSX Composite » et indices proches, TSX ajoutée le 29/12/2025 ; **intraday temporairement NON ajusté** des splits et dividendes. | **Pas maintenant.** Il comblerait un vrai trou : l'horaire n'existe qu'en crypto dans le dépôt (ADR-0205). Mais une série non ajustée échoue par construction à `make contracts` (saut > 50 % non expliqué). À revoir quand le README annonce l'ajustement, et si la couverture US est confirmée. |
| **Financial-NLP/financial_phrasebank** (soumis) | Miroir du jeu de Malo et al. La source officielle est `takala/financial_phrasebank`, en **CC BY-NC-SA 3.0**, ~4 846 phrases, 16 annotateurs ([TFDS](https://tensorflow.org/datasets/community_catalog/huggingface/financial_phrasebank?hl=en)). | **Même verdict** que §2.2 : jamais pour entraîner ; au mieux une évaluation locale non commitée. Préférer l'original au miroir, dont la provenance n'est pas établie. |
| **edgar-corpus** (soumis) | Déjà retenu (§2.1). | **H2.** Un point à corriger dans la présentation soumise : ce corpus ne dit rien « avant/après les résultats » sans la **date d'acceptation EDGAR**, qu'il ne contient pas. |

**L'architecture soumise, confrontée aux règles du dépôt.**

| Brique proposée | Verdict | Pourquoi |
|---|---|---|
| OHLCV → features | **existe** | `_ml_section` : 10 features point-in-time, CV purgée. |
| FinBERT → score de sentiment → feature | **compatible** | ADR-0007 l'autorise nommément (« sentiment-news comme feature, FinBERT, pas un chat »). C'est H3. |
| **FinGPT** → score | **incompatible en backtest** | Un LLM qui juge une entreprise sur une période couverte par son entraînement fabrique un faux alpha. Usage limité à l'extraction ; la chaîne locale a déjà été retirée (ADR-0170). |
| Chronos → **prédiction de rendement** | **écarté** | Deux évaluations indépendantes, négatives en zéro-shot (§2.2). Chronos garde un rôle : la **volatilité** (H1). |
| LSTM | **non retenu** | Aucune preuve apportée ; coûte des essais DSR. Le modèle actuel (AUC 0,504) montre que le goulot est le signal, pas l'architecture. |
| Modèle → **« Achat / Vente / Stop-loss »** direct | **incompatible** | Aucun signal ne va au courtier sans le gate 4 étages, puis `order_gate`. Les stops sont construits, pas adoptés, en attente de `make preset-sorties` (ADR-0208) ; un suiveur ATR a déjà été retiré (ADR-0052). |

Le dépôt possède déjà cette chaîne, avec les garde-fous en plus : features → ML → méta-labelling
→ gate → preset → portail. Ce qui manque n'est pas une brique, c'est **un signal qui passe
le gate**.

---

## 3. Hypothèses pré-enregistrées

Pour chaque fiche : le seuil, la métrique et la baseline sont fixés **avant** toute mesure.
Aucune ne peut être jugée dans le conteneur (pas de données) : toutes sont **UNCALIBRATED**.

### H1 — Prévision de volatilité FinText-TSFM / Chronos-2 pour le DD-target

- **Couche / module** : 4 → `backtest/cov_risk.py` (vol du DD-target) ; comparateurs
  `portfolio/risk_advanced.ewma_vol`, `portfolio/garch.fit_garch`.
- **Hypothèse** : « La variance à 21 séances prévue par le modèle FinText de l'année Y−1 a une
  perte QLIKE moyenne inférieure à celle de l'EWMA (λ du dépôt) sur l'année Y, pour les
  titres du panel de production, test de Diebold-Mariano unilatéral p < 0,05. »
- **Usage** : prévision de vol pour le dimensionnement (pas un signal alpha).
- **Horizon** 21 séances. **Turnover** : modifie l'exposition brute, donc le rééquilibrage ;
  la sensibilité aux coûts se juge au rejeu (frais du barème déjà modélisés). **Testable
  honnêtement dès maintenant** pour l'étage statistique (sans coûts) ; l'étage économique
  exige le rejeu réel (TODO P0 QML-001).
- **Contamination** : FinText = un modèle par année, ce qui permet un walk-forward 2008 → 2024
  **si** chaque modèle « Y » n'a vu que des données ≤ 31/12/Y (**à vérifier** dans la card).
  Chronos-2 : pas de données boursières déclarées, mais `exchange_rate` (forex) est dans le
  corpus Chronos. La période valide stricte commence à sa publication (10/2025, ~1 an) :
  **challenger secondaire**, puissance faible.
- **Baselines** : (a) covariance Ledoit-Wolf 120 j actuelle (ce qui trade) ; (b) EWMA ;
  (c) GARCH(1,1) du dépôt. Preuve externe : TimesFM fine-tuné bat HAR en QLIKE (DM/GW) et le
  zéro-shot est faible ([2505.11163](https://arxiv.org/abs/2505.11163v1)).
- **Parcours du gate** : étage 1 = DM (joue le rôle du placebo). Si DM passe, étage 2 = rejeu
  ERC avec la vol prévue à la place de la vol échantillon : ΔSharpe apparié (`sharpe_diff`),
  maxDD, DSR. Étage 3 = PBO sur {baseline, FinText, Chronos-2} (3 configurations, puissance
  faible, à dire). Étage 4 = sabotage, coûts ×3 au rejeu.
- **Essais ajoutés au DSR** : 0 pour l'étage DM (pas un Sharpe) ; **2** au rejeu (FinText,
  Chronos-2), TimesFM **non lancé** sauf échec des deux.
- **Plan d'intégration** : `packages/portfolio/vol_fondation.py` (`STATUT = "SHADOW"`,
  fonction pure `prevoir_variance(rendements, horizon, annee_modele) -> dict`, import paresseux
  de la bibliothèque), `scripts/vol_fondation_lab.py`, cible `make vol-fondation`. Extra
  optionnel `tsfm = [...]` dans `pyproject.toml` (dépendances exactes : **à vérifier**, par ex.
  `chronos-forecasting`). Poids en cache `~/.cache/huggingface`, jamais dans le dépôt.
- **Effort** : M. **Risques** : la source des données FinText (licence de redistribution
  des prix d'entraînement) est n/d ; coût CPU n/d ; une variance prévue plus basse **augmente**
  l'exposition, donc le risque de queue. **Prérequis** : B1, B2, B3, B5.

### H2 — « Lazy Prices » : similarité des 10-K successifs → rendement à 63 séances

- **Couche / module** : 2 → nouveau facteur ; données SEC via le même accès que
  `fundamentals/sec_provider.py`.
- **Hypothèse** : « La similarité cosinus entre le 10-K de l'année t et celui de t−1 (sections
  Risk Factors + MD&A) a un RankIC > 0 avec le rendement à 63 séances qui suit la date
  d'**acceptation** EDGAR + 1 séance, hors échantillon. »
  Référence : Cohen, Malloy, Nguyen, *Lazy Prices* (JF 2020), qui utilisent des mesures
  **sans modèle** (cosinus sur fréquences de mots, Jaccard, distance d'édition).
- **Usage** : signal alpha (feature pour le ML ensuite).
- **Deux variantes, deux statuts** : **H2a TF-IDF** (baseline, aucune contamination, aucune
  dépendance HF) est testable sur 1993 → aujourd'hui. **H2b embeddings Qwen3** : Qwen3 a été
  publié en 06/2025, fin d'entraînement n/d. La seule période valide commence donc après
  06/2025, soit **une seule saison de 10-K** : H2b n'est pas jugeable avant plusieurs années.
  Il faut le dire et ne pas le lancer avant.
- **Horizon** 63 séances, signal annuel : **turnover faible**, sensibilité aux coûts faible.
  Testable honnêtement dès maintenant.
- **Contamination / décroissance** : anomalie publiée. Il faut s'attendre à une décroissance
  après publication (McLean-Pontiff) : juger séparément la période post-2020.
- **Baseline à battre** : RankIC = 0 (placebo par permutation des dates) ; puis moyenne de
  z-scores équipondérés avec le momentum existant.
- **Métrique / gate** : RankIC par date (`research/information_coefficient.py`), t de
  Newey-West ; placebo ; DSR du long-short décile ; PBO sur {cosinus TF-IDF, Jaccard} ;
  sabotage coûts ×3.
- **Essais** : **2** (H2a cosinus, H2a Jaccard) ; H2b = +1 plus tard.
- **Plan** : `packages/data/sec_filings_text.py` (source auto-enregistrée, ingestion en base
  **locale**, horodatage = `acceptanceDateTime`), `packages/ranking/facteur_similarite_10k.py`
  (`@factor_calcs.register("similarite_10k")`, + une ligne d'import), `scripts/lazy_prices_lab.py`.
  `eloukas/edgar-corpus` sert à accélérer le backfill 1993-2020, **mais** ses dates de dépôt
  sont n/d : il faut les rejoindre à l'index EDGAR, sinon la ligne est refusée.
- **Effort** : M (ingestion texte) à L. **Risques** : univers US seulement ; les délistés
  manquent (biais du survivant, minorant) ; le volume disque des textes est n/d.
  **Prérequis** : B3, B4, B6.

### H3 — FinBERT contre le lexique, apparié, sur les mêmes titres

- **Couche / module** : 3 → `sentiment/finbert.py` (existant), `research/alpha_incremental.py`
  (existant, apparié + placebo + DSR + |IC|).
- **Hypothèse** : « Sur les mêmes événements, l'IC de rang entre le score FinBERT d'un titre
  et le rendement à 5 séances (entrée J+1 après `utilisable_le`) dépasse celui du lexique ;
  différence appariée p < 0,05. »
- **Usage** : feature pour le ML existant, jamais un ordre direct.
- **Données** : `data/news.csv` est trop court (2 375 titres, 84 % rétro-publiés), donc
  **UNCALIBRATED** pendant des mois. Un historique n'est possible qu'avec **FNSPID (1999-2023)**,
  à **PIT dégradé** : il n'a pas de `vu_le`. Règle proposée : `utilisable = date + 1 séance`,
  et le résultat est **étiqueté** « PIT dégradé », jamais présenté comme équivalent au corpus.
- **Contamination** : FinBERT est un classifieur de ton (BERT ≤ 2018, TRC2 2008-2010,
  PhraseBank 2014). Période valide : **2019 → 2023** dans FNSPID, puis le corpus maison.
- **Horizon** 5 séances : **turnover élevé**, très sensible aux coûts. L'IC brut est testable ;
  un Sharpe net n'est pas honnête tant que le coût réel reste UNCALIBRATED. Seul le sabotage
  (coûts ×3) peut conclure négativement, pas positivement.
- **Baseline** : le lexique (`sentiment/lexicon.py`) ; a priori défavorable (ADR-0024 : quatre
  hypothèses d'alpha directionnel rejetées ; sept négatifs au registre).
- **Essais** : **1** (FinBERT vs lexique, `n_essais` = 2 scoreurs comme le fait déjà le module).
- **Plan** : aucun nouveau scoreur ; `scripts/fnspid_import.py` (hors dépôt pour les données :
  base locale gitignorée), puis `alpha_incremental` tel quel.
- **Effort** : S à M. **Prérequis** : B1, B3, B6.

### H4 — Dédoublonnage et regroupement de news par embeddings (hors signal)

- **Couches** : 3 et 9 (`sentiment/corpus.py`, `intelligence/corroboration.py`). Aujourd'hui
  `/events` n'a pas de news : la cible réelle est le **corpus** et la règle d'intelligence
  « les reprises d'une même origine comptent pour une seule ».
- **Hypothèse** : « Au seuil cosinus fixé sur un échantillon étiqueté à la main, la précision
  des paires déclarées doublons est ≥ 0,95 », et le nombre d'événements distincts de
  `alpha_incremental` baisse (le poids artificiel des reprises disparaît).
- **Usage** : qualité de données. **0 essai DSR.** Le corpus est append-only (ADR-0162) : le
  dédoublonnage est une **vue**, jamais une réécriture.
- **Baseline** : l'empreinte exacte actuelle (`corpus._empreinte`, SHA-256 du titre normalisé).
- **Plan** : `packages/sentiment/quasi_doublons.py` (SHADOW), bge-m3 ou Qwen3-Embedding-0.6B.
  **Effort** : S. **Métrique** : UNCALIBRATED tant que l'échantillon étiqueté n'existe pas.

### H5 — Triple barrière à barrières proportionnelles à la vol prévue + méta-labelling

- **Dépend de H1** (vol prévue) et du verdict de `make preset-sorties` (ADR-0208).
- **Hypothèse** : « Des barrières k·σ̂ (σ̂ de H1) au lieu de `ml/labeling.ewm_volatility`
  améliorent l'AUC hors échantillon du méta-filtre au-delà de sa distribution nulle de
  permutation (`ml/meta_smc`) », puis le ΔSharpe apparié du rejeu contre la sortie par
  rééquilibrage.
- **A priori défavorable** : un suiveur ATR a déjà coupé la queue droite (ADR-0052).
- **Essais** : 1 (réglages conventionnels, pas de balayage). **Effort** : M.

### H6 — Scores comme vues Black-Litterman autour du prior

- **Existant** : `portfolio/conviction.py` : BL, prior ERC, vues = IC mesuré × σ × z, **refus**
  si l'IC n'est pas robuste. Rien à coder : une brique HF n'y entre que **si elle a passé le
  gate seule** (H2 ou H3), avec son IC mesuré. **Essais** : 1. **Effort** : S.

### H7 — Méta-modèle de combinaison

- **Existant** : `research/alpha_combine.py` (w ∝ Ω⁻¹·IC, fenêtre expansive), `ml/cv.PurgedKFold`.
- **Règle** : aucune combinaison avant que **deux** briques aient passé le gate seules. CV
  purgée, embargo ≥ horizon. **Essais** : 1. Aujourd'hui : **sans objet**, aucune brique ne tient.

---

## 4. Feuille de route — solidité des preuves × faisabilité ÷ coût en essais DSR

| Rang | Hypothèse | Preuves externes | Faisabilité (données, CPU) | Essais DSR | Pourquoi ce rang |
|---|---|---|---|---|---|
| 1 | **H1 vol FinText → Chronos-2** | moyenne (TimesFM fine-tuné bat HAR ; FinText pré-entraîné finance bat le zéro-shot) | bonne : prix déjà là, modèles < 200 M | 0 + 2 | Seul candidat à walk-forward **sans contamination** ; vise le seul edge prouvé du dépôt, la réduction du risque (ADR-0024). |
| 2 | **H2a Lazy Prices TF-IDF** | forte (JF 2020) mais anomalie publiée | moyenne : ingestion texte EDGAR | 2 | Turnover faible, testable sans HF. HF n'intervient qu'en H2b, reporté. |
| 3 | **H4 dédoublonnage** | n/a (qualité) | bonne | 0 | Ne coûte aucun essai et assainit H3. En parallèle de H1. |
| 4 | **H3 FinBERT vs lexique** | faible (a priori négatif du dépôt) | infra prête, données faibles (FNSPID à PIT dégradé) | 1 | Peu cher, mais la conclusion positive nette est impossible avant la mesure du coût réel. |
| 5 | H5 triple barrière | faible (ADR-0052) | dépend de H1 et d'ADR-0208 | 1 | Conditionnelle. |
| 6 | H6 BL · H7 méta-modèle | — | code existant | 1 chacun | Sans objet tant qu'aucune brique ne passe. |

**Budget d'essais total proposé : 6 au maximum** (2 + 2 + 1 + 1), consignés **avant** la
mesure. H2b et TimesFM restent hors budget et ne s'ouvrent que par nouvel ADR.

---

## 5. Prérequis bloquants

| # | Prérequis | Pourquoi il bloque | Bloque |
|---|---|---|---|
| **B1** | Test AST dans le **sens chaîne d'ordres → modèle** : la fermeture de `scripts/run_live.py` ne doit atteindre ni `packages.llm`, ni `packages.intelligence`, ni aucun module qui importe `transformers`, `torch`, `chronos`, `timesfm`, `sentence_transformers`. Il **échouera aujourd'hui** (`run_live` → `snapshot` → `sentiment` → `finbert`) : il faut d'abord sortir l'import de `sentiment` de la fermeture de décision (par ex. un snapshot de décision qui n'importe pas les sections d'affichage). | Aujourd'hui, l'isolation ne tient qu'à la variable `QUANT_LIVE_LITE=1`. La mission l'exige structurellement. | H1, H3, H4 |
| **B2** | Corriger l'outil de `make certification` pour `from packages import x` et les imports relatifs. | Un module SHADOW importé sous ces formes serait déclaré hors production à tort (constaté sur `packages.sentiment`). | H1-H4 |
| **B3** | **Une seule définition de N** : `trial_count` (lignes) contre `deflation_params` (somme des `n_essais`). `verdict_hors_echantillon` lit la première. | Un balayage de 870 scénarios compte pour 1 dans le verdict hors échantillon : le DSR serait trop clément. | toutes |
| **B4** | Fondamentaux point-in-time (P2-5) **ou** exclusion explicite des fondamentaux du contrôle de H2. | Un facteur 10-K combiné à un score qualité non PIT hérite de sa fuite. | H2, H6 |
| **B5** | Rejeu de production mesuré sur le VPS (`make preset-replay`, TODO P0 QML-001). | Sans lui, pas de baseline économique pour H1 et H5. | H1, H5 |
| **B6** | Coût réel : jambe de vente mesurée (TODO P2 ADR-0207 a) et journal suffisant. | Un horizon court (H3) ne se juge pas net de coûts avant. | H3 |
| **B7** | Vérification des licences et des cards (annexe C) sur une machine qui atteint `huggingface.co`. | Tous les faits HF de ce document sont de seconde main. | toutes |
| **B8** | Décision du propriétaire sur les P0 ouverts (satellite, banc d'exploration). | Ajouter des hypothèses avant de trancher disperse le budget d'essais. | ordre |
| **B9** | FinBERT : épingler la révision (`revision="4556d13…"` complet, à lire sur la card) et refuser le chargement pickle (`pytorch_model.bin`) sauf si le chargeur garantit `weights_only` ; sinon charger les poids Flax ou TF. Décider aussi de la licence absente sur la card. | `sentiment/finbert.py` charge `ProsusAI/finbert` par son **nom seul** : un dépôt modifié en amont changerait le modèle sans trace. Le format pickle contredit la règle `safe_pickle` du dépôt. | H3, et le code existant |

Le prompt citait « instrumentation des coûts » et « P0-3 » : voir §0. Ils sont **reformulés**
en B5/B6, conformément à ADR-0206 et ADR-0207.

---

## Annexe A — Brouillons d'ADR (statut : **proposé**)

> Numéros provisoires. Ces brouillons ne sont **pas** versés dans `vault/02_DECISIONS.md` :
> ils le seront, numérotés, après validation explicite du propriétaire.

### ADR-0210 (proposé) — La volatilité prévue par un modèle de fondation se mesure contre l'EWMA avant de dimensionner quoi que ce soit (2026-09-30)

**CONTEXTE.** Le seul edge vérifié du dépôt est la réduction du drawdown (ADR-0024). Le
DD-target du robot lit une covariance échantillon Ledoit-Wolf sur 120 séances
(`backtest/cov_risk.py`). Le GARCH du dépôt n'est qu'affiché et n'a jamais été comparé en
QLIKE. Des modèles de fondation de séries temporelles promettent mieux. La littérature
récente dit l'inverse en zéro-shot sur les rendements (arXiv 2511.18578, 2606.27100), et
l'inverse en fine-tuning sur la volatilité (arXiv 2505.11163). FinText publie un modèle **par
année**, ce qui rend un walk-forward sans contamination possible.

**DÉCISIONS PROPOSÉES.**
(1) `packages/portfolio/vol_fondation.py`, en SHADOW : fonction pure, import paresseux, aucun
appelant en production.
(2) Règle pré-enregistrée. Le challenger passe l'étage 1 si et seulement si :
- DM unilatéral sur la QLIKE contre l'EWMA donne p < 0,05 ;
- ET le même test contre la covariance de production aussi ;
- sur des années Y où le modèle utilisé est celui de Y−1.
(3) Étage 2 au rejeu. ADOPTABLE si et seulement si :
- ΔSharpe apparié ≥ 0 ;
- ET le maxDD n'empire pas ;
- ET le sabotage (coûts ×3) conserve le signe.
(4) Deux essais au ledger (FinText, Chronos-2), consignés avant la mesure. TimesFM n'est lancé
que si les deux échouent, par nouvel ADR.
(5) Le banc publie le compteur de ses refus (années sans modèle, séries trop courtes).

**LIMITES.**
- La source des données d'entraînement de FinText et la date de fin de chaque modèle sont
  **à vérifier**.
- Pour Chronos-2, la période valide ne commence qu'à sa publication.
- Une vol prévue plus basse augmente l'exposition.
- Adoptable ≠ adopté : `run_live` ne change que sur décision explicite.

### ADR-0211 (proposé) — Lazy Prices : la mesure sans modèle d'abord ; les embeddings attendront une période qu'ils n'ont pas vue (2026-09-30)

**CONTEXTE.** Les changements de langage entre 10-K successifs prédisent des rendements
(Cohen, Malloy, Nguyen, JF 2020), avec des mesures qui n'exigent aucun modèle. Un embedding
récent (Qwen3, 06/2025) ferait peut-être mieux, mais n'a de période de test valide qu'après sa
fin d'entraînement : une saison de 10-K.

**DÉCISIONS PROPOSÉES.**
(1) Source EDGAR texte auto-enregistrée, horodatée à `acceptanceDateTime`. Une ligne sans date
de dépôt est refusée, jamais datée par défaut.
(2) Facteur `similarite_10k` (cosinus TF-IDF) et variante Jaccard : **2 essais**, entrée à
J+1 de l'acceptation, horizon 63 séances.
(3) Gate complet. La période post-2020 est jugée séparément (décroissance post-publication).
(4) La variante embeddings n'est **pas lancée** avant une période post-entraînement suffisante,
fixée par un ADR ultérieur.

**LIMITES.**
- US seulement.
- Délistés partiels : le biais est un minorant.
- Fondamentaux non PIT à exclure du contrôle (B4).
- Anomalie publiée.

### ADR-0212 (proposé) — FinBERT contre le lexique : même échantillon, PIT dégradé déclaré, aucun Sharpe net sans coût mesuré (2026-09-30)

**CONTEXTE.** `sentiment/finbert.py` existe, `alpha_incremental` sait comparer deux scoreurs
sur les **mêmes** titres (ADR-0163), mais aucune mesure n'a jamais abouti : le corpus maison
est trop jeune (ADR-0170). FNSPID (CC BY 4.0, 1999-2023) fournit l'historique, sans `vu_le`.

**DÉCISIONS PROPOSÉES.**
(1) Import FNSPID en base **locale** gitignorée, jamais commitée.
(2) `utilisable = date + 1 séance`. Chaque résultat porte l'étiquette « PIT dégradé » ; il ne
se compare jamais tel quel au corpus maison.
(3) Période jugée : 2019 → 2023 (après l'entraînement de FinBERT).
(4) **Un essai** au ledger (`n_essais` = 2 scoreurs).
(5) Verdict limité à l'IC apparié et au placebo. Un Sharpe net positif ne sera pas publié tant
que le coût réel reste UNCALIBRATED ; un négatif, oui.

**LIMITES.**
- Univers FNSPID : liste de sociétés, historicité n/d.
- 5 séances = turnover élevé.
- A priori défavorable (ADR-0024).

---

## Annexe B — Ce que cet audit n'a PAS pu établir

- Aucune model card ni dataset card lue directement (réseau). Licences, tailles, dates de fin
  d'entraînement : de seconde main, à vérifier (B7).
- `make test` dans le conteneur : **3 699 passés, 95 ignorés, 12 échecs**, tous
  `ModuleNotFoundError` d'extras absents du conteneur (`sklearn` ×11, `yfinance` ×1), aucun lié
  à ce document. `make certification` : ✅, 9 modules SHADOW, 1 927 lignes de dette, mais
  voir §1.4. `make audit` : « 0 anomalie critique », parce que **aucune base n'est présente** :
  ce n'est pas une mesure.
- Le ledger, le corpus de news et les prix du VPS ne sont pas dans le conteneur : les
  comptes d'essais et les profondeurs réelles sont **n/d** ici.
- Le coût CPU de chaque modèle sur le VPS : **UNCALIBRATED**.
- Le contenu exact des données d'entraînement de FinText (source, licence, bornes par
  année) : **n/d**.

## Annexe C — Commandes de vérification (sur une machine qui atteint huggingface.co)

Aucune ne télécharge de poids ; aucune n'exige de jeton pour un dépôt public.

```bash
python - <<'EOF'
from huggingface_hub import model_info, dataset_info, list_models
M = ["amazon/chronos-2", "google/timesfm-2.5-200m-pytorch", "NeoQuasar/Kronos-small",
     "NeoQuasar/Kronos-base", "ProsusAI/finbert", "yiyanghkust/finbert-tone",
     "Qwen/Qwen3-Embedding-0.6B", "BAAI/bge-m3", "SUFE-AIFLM-Lab/Fin-R1"]
D = ["Zihan1004/FNSPID", "takala/financial_phrasebank",
     "zeroshot/twitter-financial-news-sentiment", "eloukas/edgar-corpus",
     "Salesforce/GiftEval", "Salesforce/GiftEvalPretrain", "autogluon/chronos_datasets"]
for r in M:
    i = model_info(r, files_metadata=False)
    print(r, i.card_data.get("license") if i.card_data else None, i.downloads,
          i.last_modified, [t for t in i.tags if t.startswith(("arxiv:", "license:"))])
for r in D:
    i = dataset_info(r)
    print(r, i.card_data.get("license") if i.card_data else None, i.downloads,
          i.last_modified)
for m in list_models(author="FinText", limit=200):
    print(m.id)          # un modèle par année et par marché attendu
EOF
```

À lire à la main dans chaque card : la fin des données d'entraînement, et pour FinText la
source des prix et la borne exacte de chaque modèle « année ».
