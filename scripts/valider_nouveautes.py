"""Valide sur DONNÉES RÉELLES les modules livrés cette semaine — avant toute production.

  python scripts/valider_nouveautes.py            # lecture seule, ne touche à rien
  python scripts/valider_nouveautes.py --appliquer  # inscrit au VRAI registre

Quatre modules ont été écrits et testés sur des cas synthétiques. Les tests prouvent que
la mathématique est juste ; ils ne prouvent RIEN sur le marché. Ce script fait passer
chacun sur le vrai panneau de prix et imprime de quoi trancher.

L'ORDRE VA DU SANS-RISQUE AU STRUCTURANT, et ce n'est pas un détail : les deux premiers
ne font que lire, le troisième propose une allocation, le quatrième écrit au registre de
recherche (et seulement si on le demande explicitement).

RIEN N'EST BRANCHÉ ICI. Ce script MESURE et IMPRIME. La décision de mettre en production
reste un geste humain, séparé, après lecture des chiffres.

Si la base réelle est absente, on le DIT et on s'arrête : mesurer sur du synthétique
donnerait des chiffres d'apparence sérieuse qui ne voudraient rien dire — c'est
exactement le piège que le mandat données-réelles interdit.
"""

from __future__ import annotations

import argparse
import sys
import traceback
import warnings
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packages.common.device import activer_cudf, banniere  # noqa: E402

activer_cudf()
banniere()

import numpy as np  # noqa: E402

# Les fenêtres entièrement vides sont ATTENDUES au démarrage de chaque série (la
# fenêtre n'est pas encore pleine) et sur les actifs à trous. numpy prévient à chaque
# occurrence ; sur 774 actifs, ces avertissements noient la sortie qu'on est venu lire.
# On les tait ICI, dans le script d'affichage, jamais dans les modules de calcul.
warnings.filterwarnings("ignore", message="Mean of empty slice")
warnings.filterwarnings("ignore", message="Degrees of freedom <= 0")
warnings.filterwarnings("ignore", message="All-NaN slice encountered")
warnings.filterwarnings("ignore", category=RuntimeWarning, module="numpy")

SEPARATEUR = "=" * 72
# Part minimale de séances cotées pour qu'un actif entre dans la comparaison
# d'allocation. Sous ce seuil, ses rendements sont trop lacunaires pour qu'une
# covariance ou un CVaR estimés dessus veuillent dire quelque chose.
COUVERTURE_MIN = 0.90
# Part d'actifs cotant un jour donné pour qu'on le tienne pour un JOUR DE BOURSE. Sous
# ce seuil, seul le crypto cote : c'est un week-end ou un férié, pas une séance.
PRESENCE_JOUR_MIN = 0.60
# Plafond par ligne de la variante contrainte. Une allocation qui met la moitié du
# capital sur un actif réduit peut-être la perte extrême MESURÉE, mais elle expose à ce
# que la mesure n'a pas vu.
PLAFOND_LIGNE = 0.25
# Classes présentes en base mais qu'AUCUN courtier branché ne dessert. Les laisser dans
# une comparaison d'allocateurs produit une allocation qu'on ne peut pas exécuter.
NON_NEGOCIABLE = ("forex", "index", "commodity")


def _titre(n: int, texte: str, risque: str) -> None:
    print(f"\n{SEPARATEUR}\n {n}. {texte}\n    ({risque})\n{SEPARATEUR}")


def charger_panel(jours: int = 1500):
    """Panneau réel (T dates × N actifs) + noms. Lève si la base réelle est absente."""
    from apps.api.snapshot import (
        _load_prices,
        _sector_of,
        _seed_universe,
        contient_des_prix_reels,
    )
    instruments = _seed_universe()
    secteur = {m["symbol"]: _sector_of(m) for m in instruments}
    fin = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    data, mode, reels = _load_prices(instruments, secteur, fin - timedelta(days=jours),
                                     fin, 7)
    if not contient_des_prix_reels(mode) or not reels:
        raise SystemExit(
            f"\n⛔ Aucune base de prix RÉELLE trouvée (mode : {mode}).\n"
            "   Définir QUANT_PRICE_DB vers YAHOO.db, ou lancer depuis la machine qui\n"
            "   détient les bases. Mesurer sur du synthétique donnerait des chiffres\n"
            "   d'apparence sérieuse qui ne voudraient rien dire."
        )
    symboles = sorted(s for s in reels if len(data.get(s, [])) > 300)
    dates = sorted({b.ts for s in symboles for b in data[s]})[-jours:]
    index = {d: i for i, d in enumerate(dates)}
    champs = {c: np.full((len(dates), len(symboles)), np.nan) for c in
              ("open", "high", "low", "close", "volume")}
    for j, s in enumerate(symboles):
        for b in data[s]:
            i = index.get(b.ts)
            if i is not None:
                for c in champs:
                    champs[c][i, j] = float(getattr(b, c))
    classes = {m["symbol"]: m.get("asset_class", "?") for m in instruments}
    return champs, symboles, mode, [classes.get(x, "?") for x in symboles]


def etape_anomalies(champs, symboles, etat_partage: dict | None = None) -> set[str]:
    _titre(1, "ANOMALIES CROISÉES — ce qu'un contrôle ligne par ligne ne voit pas",
           "lecture seule, aucun risque")
    from packages.storage.anomalies_panel import auditer_panel, resumer_par_actif
    rapport = auditer_panel(champs["close"])
    print(f"  {rapport['n_actifs']} actifs sur {rapport['n_dates']} dates")
    print(f"  → {rapport['resume']}")
    if rapport["ok"]:
        print("  ✓ rien à signaler — l'audit croisé ne trouve aucune incohérence")
        return set()

    # PAR ACTIF, pas événement par événement : ce qui se décide, ce n'est pas « ce
    # point du 12 mars », c'est « cette série est-elle exploitable ».
    lignes = resumer_par_actif(rapport, symboles)
    casses = [x for x in lignes if x["gravite"] == "donnée cassée"]
    splits = [x for x in lignes if x["gravite"] == "split non ajusté ?"]
    figes = sorted([x for x in lignes if x["jours_figes"]],
                   key=lambda d: -d["jours_figes"])

    print(f"\n  {len(lignes)} actifs concernés sur {rapport['n_actifs']}")
    if casses:
        print(f"\n  A. DONNÉES CASSÉES — {len(casses)} actif(s). Un rendement au-delà")
        print("     de +1000 % en une séance n'est pas un mouvement de marché : c'est")
        print("     que le prix de la VEILLE était faux, souvent proche de zéro.")
        print("     À retirer de l'univers tant que la source n'est pas réparée.")
        for x in casses[:15]:
            print(f"       · {x['symbole']:14s} pire saut {x['pire']:+.0%}"
                  f"   ({x['sauts']} événements)")
        if len(casses) > 15:
            print(f"       … et {len(casses) - 15} autre(s)")
    if splits:
        print(f"\n  B. SPLITS POSSIBLES — {len(splits)} actif(s), à ajuster :")
        for x in splits[:10]:
            print(f"       · {x['symbole']:14s} pire saut {x['pire']:+.0%}")
        if len(splits) > 10:
            print(f"       … et {len(splits) - 10} autre(s)")
    if figes:
        total = sum(x["jours_figes"] for x in figes)
        print(f"\n  C. SÉRIES FIGÉES — {len(figes)} actif(s), {total} séances.")
        print("     C'est le cas le plus dangereux : un cours immobile n'a ni")
        print("     dispersion ni queue, donc il paraît SANS RISQUE à tous les")
        print("     optimiseurs — variance comme CVaR — et hérite d'un poids indu.")
        for x in figes[:15]:
            print(f"       · {x['symbole']:14s} {x['jours_figes']:4d} séances figées"
                  f"   ({x['figees']} épisodes)")
        if len(figes) > 15:
            print(f"       … et {len(figes) - 15} autre(s)")
    # LES LISTES A ET C SONT TRANSMISES À L'ÉTAPE 3, et ce n'est pas un confort.
    #
    # Premier lancement complet (08/09) : Mean-CVaR proposait TRX/USDC 56,2 %,
    # BTC/USDC 42,4 % et TON/USDC 1,3 % — or TON/USDC figurait dans la liste A (données
    # cassées) et TRX/USDC dans la liste B. Le CVaR de 4,61 % était donc mesuré SUR DES
    # PRIX FAUX, et le « gain » face à min-variance ne prouvait rien.
    #
    # Un audit qui trouve des séries corrompues et laisse l'étape suivante les utiliser
    # ne sert à rien. Pire : il fabrique un résultat flatteur, donc convaincant.
    ecarter = {x["symbole"] for x in casses} | {x["symbole"] for x in figes}
    # La liste B est SIGNALÉE, pas exclue. Un saut de +90 % en séance peut être un split
    # non ajusté comme une vraie nouvelle (MRNA +177 % le jour d'un résultat d'essai
    # clinique). Écarter les deux biaiserait le risque vers le bas — l'erreur inverse,
    # et plus dangereuse que celle qu'on corrige.
    if etat_partage is not None:
        etat_partage["surveiller"] = {x["symbole"] for x in splits}
    print(f"\n  À LIRE : les {len(casses)} actifs de la liste A n'ont pas leur place")
    print("  dans une allocation, et ceux de la liste C fausseraient tout optimiseur")
    print(f"  de risque. Ces {len(ecarter)} actifs sont ÉCARTÉS de l'étape 3.")
    return ecarter


def etape_cvar(champs, symboles, ecarter: set[str] | None = None,
               surveiller: set[str] | None = None,
               classes: list[str] | None = None) -> None:
    _titre(3, "MEAN-CVaR contre les allocateurs actuels — sur rendements RÉELS",
           "propose une allocation, n'en applique aucune")
    from packages.portfolio.cvar_optimize import cvar_du_portefeuille, mean_cvar_detail
    from packages.portfolio.optimize import (
        equal_risk_contribution,
        hrp_weights,
        min_variance_weights,
    )
    c = champs["close"]
    with np.errstate(divide="ignore", invalid="ignore"):
        r = np.diff(c, axis=0) / np.where(c[:-1] == 0, np.nan, c[:-1])

    # ALIGNEMENT EN DEUX TEMPS : d'abord les JOURS, ensuite les ACTIFS.
    #
    # La première version filtrait les actifs sur leur couverture d'une grille
    # CALENDAIRE. Or une action cote 5 jours sur 7 : sa couverture plafonne à 71 %,
    # sous n'importe quel seuil raisonnable. Le filtre à 90 % ne retenait donc QUE du
    # crypto — 36 actifs, tous de la famille dont l'étape 1 venait de dire que les
    # données étaient abîmées. La comparaison d'allocateurs portait sur un univers
    # crypto pur, ce qui ne ressemble à aucun portefeuille réel.
    #
    # On repère donc d'abord les vrais JOURS DE BOURSE — ceux où une large majorité
    # d'actifs cote — ce qui écarte les week-ends sans avoir à connaître le calendrier
    # d'aucune place. La couverture des actifs se mesure ensuite SUR CES JOURS, où une
    # action saine est à 100 %. Aucun remplissage : prolonger un cours absent
    # inventerait une séance sans mouvement, ce qui abaisse la volatilité mesurée et
    # ferait paraître l'actif plus sûr qu'il n'est.
    presence = np.isfinite(r).mean(axis=1)
    jours_bourse = presence >= PRESENCE_JOUR_MIN
    if jours_bourse.sum() < 250:
        print(f"  ⛔ {int(jours_bourse.sum())} jours de bourse identifiés : trop peu")
        return
    r_jours = r[jours_bourse]
    couverture = np.isfinite(r_jours).mean(axis=0)
    gardes = couverture >= COUVERTURE_MIN
    # INVESTABLE UNIQUEMENT — la même règle que le screener, plus les classes qu'aucun
    # courtier ne dessert.
    #
    # Le run du 08/09 a fait proposer à Mean-CVaR : USD/HKD 41,7 %, AUD/USD 12,9 %,
    # USD/SGD 12,1 %… soit CENT POUR CENT de forex, alors que le TODO dit noir sur blanc
    # que le forex est en base mais NON NÉGOCIABLE (aucun courtier branché). Un
    # allocateur qui propose ce qu'on ne peut pas acheter ne se compare à rien.
    #
    # Pire, USD/HKD est un cours ANCRÉ par la banque centrale de Hong Kong dans une
    # bande étroite : sa volatilité est proche de zéro par construction, pas par
    # qualité. Le détecteur de séries figées ne l'attrape pas — il bouge, à peine — mais
    # économiquement il joue le même rôle : un actif qui paraît sans risque et rafle la
    # mise chez tout minimiseur.
    if classes is not None:
        negociable = np.array([c not in NON_NEGOCIABLE and not s.startswith("^")
                               for s, c in zip(symboles, classes, strict=True)])
        n_hors = int((gardes & ~negociable).sum())
        gardes = gardes & negociable
        if n_hors:
            print(f"  {n_hors} actif(s) écarté(s) : non négociables "
                  f"({', '.join(sorted(NON_NEGOCIABLE))}, indices)")
    if ecarter:
        propres = np.array([s not in ecarter for s in symboles])
        n_retires = int((gardes & ~propres).sum())
        gardes = gardes & propres
        if n_retires:
            print(f"  {n_retires} actif(s) écarté(s) : séries signalées à l'étape 1")
    if gardes.sum() < 5:
        print(f"  ⛔ {int(gardes.sum())} actifs couverts à "
              f"{COUVERTURE_MIN:.0%}+ : comparaison impossible")
        return
    sous = r_jours[:, gardes]
    dates_pleines = np.isfinite(sous).all(axis=1)
    sous = sous[dates_pleines]
    noms = [s for s, ok in zip(symboles, gardes, strict=True) if ok]
    if sous.shape[0] < 250:
        print(f"  ⛔ {sous.shape[0]} dates communes seulement : trop peu pour comparer")
        return
    r = sous
    print(f"  {int(jours_bourse.sum())} jours de bourse identifiés sur "
          f"{len(presence)} dates calendaires")
    print(f"  {r.shape[1]} actifs couverts à {COUVERTURE_MIN:.0%}+ · "
          f"{r.shape[0]} dates communes")
    cov = np.cov(r, rowvar=False)
    d = mean_cvar_detail(r, alpha=0.95)
    # AVEC PLAFOND, à côté du sans plafond. Sur le run du 08/09, Mean-CVaR posait 54,6 %
    # sur une ligne et 45,4 % sur une autre : PLUS concentré que min-variance (39,3 %),
    # l'allocateur qu'on lui reproche justement de concentrer. Réduire la perte extrême
    # en misant tout sur deux actifs n'est pas un progrès, c'est un autre risque —
    # celui que la mesure ne voit pas, parce que le passé n'a pas encore montré ce que
    # ces deux-là font quand ils tombent ensemble. Publier les deux versions laisse
    # l'arbitrage visible au lieu de le trancher en silence.
    d_cap = mean_cvar_detail(r, alpha=0.95, plafond=PLAFOND_LIGNE)
    # Un allocateur qui lève sur une matrice dégénérée ne doit pas emporter les cinq
    # autres : on perdrait toute la comparaison pour un cas particulier.
    lignes = []
    for nom_alloc, calculer in (
            ("Mean-CVaR (nouveau)", lambda: d["poids"]),
            (f"Mean-CVaR plafonné {PLAFOND_LIGNE:.0%}", lambda: d_cap["poids"]),
            ("min-variance", lambda: min_variance_weights(cov)),
            ("risk parity (ERC)", lambda: equal_risk_contribution(cov)),
            ("HRP", lambda: hrp_weights(cov)),
            ("équipondéré", lambda: [1.0 / r.shape[1]] * r.shape[1])):
        try:
            lignes.append((nom_alloc, calculer()))
        except Exception as e:  # noqa: BLE001 — un allocateur absent, pas une panne
            print(f"  ⚠ {nom_alloc} indisponible : {type(e).__name__}: {e}")
    print(f"  méthode de résolution : {d['methode']}\n")
    entetes = f"  {'allocation':24s} {'CVaR 95%':>10s} {'pire jour':>10s}"
    print(entetes + f" {'poids max':>10s}")
    for nom, w in lignes:
        w = np.asarray(w, float)
        pertes = -(r @ w)
        print(f"  {nom:24s} {cvar_du_portefeuille(r, w):>9.2%} "
              f"{pertes.max():>9.2%} {w.max():>9.1%}")
    if classes is not None:
        cls = [c for c, ok in zip(classes, gardes, strict=True) if ok]
        _repartition_par_classe(lignes, cls)
    for etiquette, detail in (("sans plafond", d), (f"plafonné à {PLAFOND_LIGNE:.0%}",
                                                    d_cap)):
        top = sorted(zip(noms, detail["poids"], strict=True),
                     key=lambda t: -t[1])[:8]
        retenues = [(n, w) for n, w in top if w > 0.005]
        print(f"\n  Mean-CVaR {etiquette} — {len(retenues)} ligne(s) : "
              + ", ".join(f"{n} {w:.1%}" for n, w in retenues))
        suspects = [n for n, _ in retenues if n in (surveiller or set())]
        if suspects:
            print(f"    ⚠ dont {', '.join(suspects)} — signalé(s) à l'étape 1 comme "
                  "possible(s) split(s) non ajusté(s), à vérifier avant d'y croire")
    _hors_echantillon(r)


def _allocateurs(r: np.ndarray) -> list[tuple[str, callable]]:
    """Les allocateurs comparés, sous forme de FONCTIONS d'un historique.

    Sous forme de fonctions et non de poids figés : le test hors échantillon doit
    pouvoir les réajuster sur chaque fenêtre passée, ce qu'une liste de poids calculée
    une fois pour toutes interdit.
    """
    from packages.portfolio.cvar_optimize import mean_cvar_weights
    from packages.portfolio.optimize import (
        equal_risk_contribution,
        hrp_weights,
        min_variance_weights,
    )
    return [
        ("Mean-CVaR (nouveau)", lambda h: mean_cvar_weights(h, alpha=0.95)),
        (f"Mean-CVaR plafonné {PLAFOND_LIGNE:.0%}",
         lambda h: mean_cvar_weights(h, alpha=0.95, plafond=PLAFOND_LIGNE)),
        ("min-variance", lambda h: min_variance_weights(np.cov(h, rowvar=False))),
        ("risk parity (ERC)",
         lambda h: equal_risk_contribution(np.cov(h, rowvar=False))),
        ("HRP", lambda h: hrp_weights(np.cov(h, rowvar=False))),
        ("équipondéré", lambda h: [1.0 / h.shape[1]] * h.shape[1]),
    ]


def _hors_echantillon(r: np.ndarray, fenetre: int = 252, pas: int = 63) -> None:
    """LE test qui décide. Ajuster sur le passé, mesurer sur la SUITE.

    Tout ce qui précède est mesuré EN ÉCHANTILLON : chaque allocateur est ajusté sur les
    mêmes jours que ceux qui servent à le noter. Mean-CVaR minimise exactement le nombre
    qu'on rapporte — il ne PEUT PAS perdre ce concours, c'est sa fonction objectif. Et
    min-variance perd sur le CVaR par construction, pas par infériorité. « 0,58 % contre
    1,65 % » ne prouve donc rien d'autre que « l'optimiseur a bien optimisé ce qu'on lui
    a demandé ».

    Ici, les poids sont calculés sur une fenêtre passée puis appliqués à la fenêtre
    SUIVANTE, jamais vue. Les segments hors échantillon sont mis bout à bout et notés
    ensemble. Un avantage qui survit à ça est réel ; un avantage qui s'évapore était du
    surajustement — et les deux se ressemblent parfaitement en échantillon.

    Le RENDEMENT est publié à côté du risque. Un allocateur qui divise la perte extrême
    par trois en divisant aussi le rendement par trois n'a rien amélioré : il a
    simplement moins investi.
    """
    from packages.portfolio.cvar_optimize import cvar_du_portefeuille
    if r.shape[0] < fenetre + pas:
        print(f"\n  (hors échantillon impossible : {r.shape[0]} dates, il en faut "
              f"{fenetre + pas} au minimum)")
        return
    decoupes = list(range(fenetre, r.shape[0] - pas + 1, pas))
    print(f"\n  HORS ÉCHANTILLON — ajusté sur {fenetre} jours, mesuré sur les {pas}")
    print(f"  suivants, {len(decoupes)} fois de suite. C'est le seul test qui décide.")
    print(f"\n  {'allocation':24s} {'CVaR 95%':>10s} {'pire jour':>10s} "
          f"{'rendement':>11s}")
    for nom, calculer in _allocateurs(r):
        morceaux = []
        for t in decoupes:
            try:
                w = np.asarray(calculer(r[t - fenetre:t]), float)
            except Exception:  # noqa: BLE001 — un allocateur en échec ne fausse pas
                continue        # les autres ; il sera simplement absent du décompte
            morceaux.append(r[t:t + pas] @ w)
        if not morceaux:
            print(f"  {nom:24s} {'—':>10s} {'—':>10s} {'—':>11s}")
            continue
        suite = np.concatenate(morceaux)
        cumul = float(np.prod(1.0 + suite) - 1.0)
        print(f"  {nom:24s} "
              f"{cvar_du_portefeuille(suite[:, None], [1.0]):>9.2%} "
              f"{(-suite).max():>9.2%} {cumul:>10.1%}")
    print("\n  À LIRE : si l'avantage du Mean-CVaR disparaît ici, il était du")
    print("  surajustement. S'il tient, il est réel — et le rendement dit son coût.")


def _repartition_par_classe(lignes, classes: list[str]) -> None:
    """Où chaque allocateur met son capital, par classe d'actifs.

    C'est la lecture qui manquait. Un minimiseur de risque appliqué à un univers mêlant
    forex (~0,3 %/jour), obligataire, actions (~1,8 %) et crypto (~4,5 %) ne produit pas
    une allocation : il choisit la classe la moins agitée et y reste. Le CVaR obtenu est
    alors imbattable et ne veut rien dire — il mesure le choix de la classe, pas la
    qualité de la répartition. Publier la répartition rend ce piège VISIBLE ; le
    dissimuler ferait passer une dégénérescence pour une performance.
    """
    familles = sorted(set(classes))
    print(f"\n  {'répartition par classe':24s}"
          + "".join(f"{f:>12s}" for f in familles))
    for nom, w in lignes:
        w = np.asarray(w, float)
        parts = [w[[c == f for c in classes]].sum() for f in familles]
        print(f"  {nom:24s}" + "".join(f"{x:>11.1%} " for x in parts))


def etape_generateur(champs, appliquer: bool) -> None:
    _titre(4, "GÉNÉRATEUR DE SIGNAUX — le compte d'essais monte-t-il vraiment ?",
           "écrit au registre UNIQUEMENT avec --appliquer")
    import tempfile

    from packages.research import generateur_signaux as gen
    c = champs["close"]
    horizon = 21
    futurs = np.full_like(c, np.nan)
    with np.errstate(divide="ignore", invalid="ignore"):
        futurs[:-horizon] = c[horizon:] / np.where(c[:-horizon] == 0, np.nan,
                                                   c[:-horizon]) - 1.0
    candidats = gen.enumerer()
    with tempfile.TemporaryDirectory() as tmp:
        chemin = None if appliquer else Path(tmp) / "essai.jsonl"
        bilan = gen.campagne(candidats, champs, np.nan_to_num(futurs), horizon,
                             chemin_ledger=chemin)
    print(f"  {bilan['n_candidats']} candidats évalués sur le panneau RÉEL")
    print(f"  essais au registre : {bilan['essais_avant']} → {bilan['essais_apres']}")
    nvidia = sum(1 for x in bilan["resultats"] if x["accepte_par_le_blueprint"])
    print(f"  retenus par le seuil |IC| >= 0,02 (blueprint NVIDIA) : {nvidia}")
    print(f"  promus par NOTRE gate (t ≥ 2 sur fenêtres disjointes) : "
          f"{len(bilan['promus'])}")
    for p in bilan["promus"][:10]:
        print(f"    ✓ {p['facteur']:34s} IC {p['ic_moyen']:+.4f}  {p['motif']}")
    if not appliquer:
        print("\n  (registre TEMPORAIRE — relancer avec --appliquer pour inscrire)")
    print("\n  À LIRE : des promus ici valent d'être creusés. Aucun promu n'est un")
    print("  échec — c'est le comportement attendu d'un gate qui corrige les essais.")


def etape_explication(champs, symboles) -> None:
    """Sur quoi un modèle entraîné sur CES données s'appuie-t-il ?

    On entraîne ici un modèle jetable sur des variables issues de la grammaire de
    signaux, plutôt que de charger l'artefact de production : l'artefact a ses propres
    variables, et le but est de vérifier que la MÉCANIQUE d'explication fonctionne sur
    des données réelles. Brancher l'explication sur le modèle de production est l'étape
    d'après, une fois cette mécanique validée.
    """
    _titre(2, "EXPLICABILITÉ — sur quoi un modèle s'appuie-t-il vraiment ?",
           "lecture seule, aucun risque")
    from packages.ml.explication import importance_par_permutation
    from packages.ml.model import make_model
    from packages.research import generateur_signaux as gen

    expressions = gen.enumerer(temporels=("momentum", "volatilite",
                                          "ecart_a_la_moyenne", "ratio_de_volume"),
                               transversaux=("rang",), fenetres=(21, 63))
    horizon = 21
    c = champs["close"]
    colonnes, noms = [], []
    for e in expressions:
        colonnes.append(gen.evaluer(e, champs))
        noms.append(gen.nom(e))
    with np.errstate(divide="ignore", invalid="ignore"):
        futur = c[horizon:] / np.where(c[:-horizon] == 0, np.nan, c[:-horizon]) - 1.0

    lignes, cible = [], []
    for t in range(200, c.shape[0] - horizon, horizon):
        for j in range(c.shape[1]):
            vecteur = [col[t, j] for col in colonnes]
            if np.isfinite(vecteur).all() and np.isfinite(futur[t, j]):
                lignes.append(vecteur)
                cible.append(1.0 if futur[t, j] > 0 else 0.0)
    X, y = np.asarray(lignes, float), np.asarray(cible, float)
    if X.shape[0] < 200 or len(set(cible)) < 2:
        print(f"  ⛔ pas assez d'observations exploitables ({X.shape[0]})")
        return
    print(f"  {X.shape[0]} observations × {X.shape[1]} variables")
    modele = make_model("sklearn").fit(X, y)
    for rang, d in enumerate(importance_par_permutation(
            modele.predict_proba, X, y, noms, n_repetitions=5), 1):
        fleche = "↑" if d["importance"] > 0 else " "
        print(f"    {rang:2d}. {fleche} {d['variable']:34s} "
              f"{d['importance']:+.4f} ± {d['ecart_type']:.4f}")
    print("\n  À LIRE : si les variables en tête n'ont aucun sens économique, c'est")
    print("  une information de premier ordre sur le modèle lui-même.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--appliquer", action="store_true",
                    help="inscrit la campagne de signaux au VRAI registre")
    ap.add_argument("--jours", type=int, default=1500)
    args = ap.parse_args()

    champs, symboles, mode, classes = charger_panel(args.jours)
    print(f"\nPanneau réel chargé : {len(symboles)} actifs · mode « {mode} »")

    # CHAQUE ÉTAPE EST ISOLÉE. Le premier lancement sur le VPS (08/09) s'est arrêté à
    # l'étape 2 — scikit-learn absent de cet environnement — et a emporté les étapes 3
    # et 4 avec elle. Or l'ordre du script sert justement à obtenir les mesures
    # sans risque D'ABORD : les perdre à cause d'une dépendance optionnelle manquante
    # sur une étape ultérieure est exactement l'inverse du but recherché.
    etat: dict = {}
    etapes = [
        ("anomalies croisées", lambda: etat.update(
            ecarter=etape_anomalies(champs, symboles, etat) or set())),
        ("explicabilité", lambda: etape_explication(champs, symboles)),
        ("Mean-CVaR", lambda: etape_cvar(champs, symboles, etat.get("ecarter"),
                                        etat.get("surveiller"), classes)),
        ("générateur de signaux", lambda: etape_generateur(champs, args.appliquer)),
    ]
    echecs = []
    for nom_etape, executer in etapes:
        try:
            executer()
        except ModuleNotFoundError as e:
            echecs.append((nom_etape, f"dépendance absente : {e.name}"))
            print(f"\n  ⚠ étape « {nom_etape} » ignorée — {e.name} absent de cet "
                  "environnement.\n    Les autres étapes continuent.")
        except Exception as e:  # noqa: BLE001 — un banc de mesure ne doit jamais
            echecs.append((nom_etape, f"{type(e).__name__}: {e}"))  # tout emporter
            print(f"\n  ⚠ étape « {nom_etape} » en échec — {type(e).__name__}: {e}")
            traceback.print_exc(limit=3)

    print(f"\n{SEPARATEUR}")
    if echecs:
        print(" ÉTAPES NON ABOUTIES :")
        for nom_etape, motif in echecs:
            print(f"   · {nom_etape} — {motif}")
        print(" (une étape manquante n'invalide pas les autres)")
    print(" Rien n'a été mis en production. La décision reste un geste humain,")
    print(f" séparé, après lecture des chiffres ci-dessus.\n{SEPARATEUR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
