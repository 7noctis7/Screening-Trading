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
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packages.common.device import activer_cudf, banniere  # noqa: E402

activer_cudf()
banniere()

import numpy as np  # noqa: E402

SEPARATEUR = "=" * 72


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


def etape_anomalies(champs, symboles) -> None:
    _titre(1, "ANOMALIES CROISÉES — ce qu'un contrôle ligne par ligne ne voit pas",
           "lecture seule, aucun risque")
    from packages.storage.anomalies_panel import auditer_panel
    rapport = auditer_panel(champs["close"])
    print(f"  {rapport['n_actifs']} actifs sur {rapport['n_dates']} dates")
    print(f"  → {rapport['resume']}")
    figees = rapport["series_figees"]
    if figees:
        print("\n  SÉRIES FIGÉES (le cas le plus dangereux : un cours immobile")
        print("  paraît sans risque à TOUS les optimiseurs, et hériterait d'un poids")
        print("  qu'il ne mérite pas) :")
        for f in figees[:12]:
            print(f"    · {symboles[f['actif_index']]:12s} {f['motif']}")
        if len(figees) > 12:
            print(f"    … et {len(figees) - 12} autre(s)")
    sauts = rapport["sauts_isoles"]
    if sauts:
        pires = sorted(sauts, key=lambda s: -s["ecarts_robustes"])[:8]
        print("\n  MOUVEMENTS INCOHÉRENTS AVEC LE MARCHÉ (split non ajusté ?) :")
        for s in pires:
            print(f"    · {symboles[s['actif_index']]:12s} {s['motif']}")
    if rapport["ok"]:
        print("  ✓ rien à signaler — l'audit croisé ne trouve aucune incohérence")
    print("\n  À LIRE : beaucoup de séries figées expliquerait les concentrations")
    print("  vues en min-variance. Beaucoup de faux positifs = seuil à revoir.")


def etape_cvar(champs, symboles) -> None:
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
    complets = np.isfinite(r).all(axis=0)
    r = np.nan_to_num(r[:, complets], nan=0.0)
    noms = [s for s, ok in zip(symboles, complets, strict=True) if ok]
    if r.shape[1] < 5:
        print("  ⛔ moins de 5 actifs à historique complet : comparaison impossible")
        return
    print(f"  {r.shape[1]} actifs à historique complet, {r.shape[0]} séances")
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
    etape_anomalies(champs, symboles)
    etape_explication(champs, symboles)
    etape_cvar(champs, symboles)
    etape_generateur(champs, args.appliquer)
    print(f"\n{SEPARATEUR}\n Rien n'a été mis en production. La décision reste un geste"
          f"\n humain, séparé, après lecture des chiffres ci-dessus.\n{SEPARATEUR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
