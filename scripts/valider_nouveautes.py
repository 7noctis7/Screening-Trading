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
    return champs, symboles, mode


def etape_anomalies(champs, symboles) -> set[str]:
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
    print(f"\n  À LIRE : les {len(casses)} actifs de la liste A n'ont pas leur place")
    print("  dans une allocation, et ceux de la liste C fausseraient tout optimiseur")
    print(f"  de risque. Ces {len(ecarter)} actifs sont ÉCARTÉS de l'étape 3.")
    return ecarter


def etape_cvar(champs, symboles, ecarter: set[str] | None = None) -> None:
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

    # ALIGNEMENT PAR INTERSECTION, jamais par remplissage.
    #
    # La première version exigeait un historique fini sur TOUTES les dates. Sur un
    # univers qui mêle actions et crypto, c'est impossible : la crypto cote le samedi,
    # les actions non, donc la grille commune est trouée par construction. Résultat
    # mesuré sur le VPS (08/09) : « moins de 5 actifs », et l'étape ne mesurait rien.
    #
    # On garde donc les actifs assez COUVERTS, puis on ne retient que les dates où ils
    # ont tous une valeur. Jamais de remplissage vers l'avant : prolonger un cours
    # absent invente une séance sans mouvement, ce qui abaisse la volatilité mesurée et
    # ferait justement paraître l'actif plus sûr qu'il n'est.
    couverture = np.isfinite(r).mean(axis=0)
    gardes = couverture >= COUVERTURE_MIN
    # Exclusion des séries que l'étape 1 a signalées. Comparer des allocateurs sur des
    # prix faux mesure la sensibilité au bruit, pas la qualité de l'allocation.
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
    sous = r[:, gardes]
    dates_pleines = np.isfinite(sous).all(axis=1)
    sous = sous[dates_pleines]
    noms = [s for s, ok in zip(symboles, gardes, strict=True) if ok]
    if sous.shape[0] < 250:
        print(f"  ⛔ {sous.shape[0]} dates communes seulement : trop peu pour comparer")
        return
    r = sous
    print(f"  {r.shape[1]} actifs couverts à {COUVERTURE_MIN:.0%}+ · "
          f"{r.shape[0]} dates communes (sur {len(dates_pleines)} possibles)")
    cov = np.cov(r, rowvar=False)
    d = mean_cvar_detail(r, alpha=0.95)
    lignes = [("Mean-CVaR (nouveau)", d["poids"]),
              ("min-variance", min_variance_weights(cov)),
              ("risk parity (ERC)", equal_risk_contribution(cov)),
              ("HRP", hrp_weights(cov)),
              ("équipondéré", [1.0 / r.shape[1]] * r.shape[1])]
    print(f"  méthode de résolution : {d['methode']}\n")
    entetes = f"  {'allocation':24s} {'CVaR 95%':>10s} {'pire jour':>10s}"
    print(entetes + f" {'poids max':>10s}")
    for nom, w in lignes:
        w = np.asarray(w, float)
        pertes = -(r @ w)
        print(f"  {nom:24s} {cvar_du_portefeuille(r, w):>9.2%} "
              f"{pertes.max():>9.2%} {w.max():>9.1%}")
    top = sorted(zip(noms, d["poids"], strict=True), key=lambda t: -t[1])[:8]
    print("\n  Lignes proposées par Mean-CVaR : "
          + ", ".join(f"{n} {p:.1%}" for n, p in top if p > 0.001))
    print("\n  À LIRE : si le CVaR du Mean-CVaR n'est pas NETTEMENT sous les autres,")
    print("  on ne branche pas. La démonstration synthétique ne vaut pas verdict.")


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

    champs, symboles, mode = charger_panel(args.jours)
    print(f"\nPanneau réel chargé : {len(symboles)} actifs · mode « {mode} »")

    # CHAQUE ÉTAPE EST ISOLÉE. Le premier lancement sur le VPS (08/09) s'est arrêté à
    # l'étape 2 — scikit-learn absent de cet environnement — et a emporté les étapes 3
    # et 4 avec elle. Or l'ordre du script sert justement à obtenir les mesures
    # sans risque D'ABORD : les perdre à cause d'une dépendance optionnelle manquante
    # sur une étape ultérieure est exactement l'inverse du but recherché.
    etat: dict = {}
    etapes = [
        ("anomalies croisées", lambda: etat.update(
            ecarter=etape_anomalies(champs, symboles) or set())),
        ("explicabilité", lambda: etape_explication(champs, symboles)),
        ("Mean-CVaR", lambda: etape_cvar(champs, symboles,
                                        etat.get("ecarter"))),
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
