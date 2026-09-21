#!/usr/bin/env python3
"""Le motif déviation → reclaim → consolidation prédit-il quelque chose ? — MESURÉ.

LA QUESTION, ET POURQUOI ELLE PASSE AVANT TOUTE STRATÉGIE. Une spec décrivant un motif
de price action est une HYPOTHÈSE, pas un résultat. Ce banc la met à l'épreuve sur
l'historique réel avant qu'une ligne de stratégie ne soit écrite — dix minutes ici
évitent des semaines de câblage inutile, comme pour `signal_lab`.

CE QU'IL COMPARE, ET C'EST LE POINT. La primitive `liquidite_ict.sfp` existe depuis le
02/09 : la mèche prend la liquidité, la clôture la rend, en UNE barre. La machine à
états ajoute la séparation déviation/reclaim sur plusieurs barres, puis l'acceptation.
Si l'ajout n'améliore pas la prédiction, il ne sert à rien — et c'est une réponse, pas
un échec. Les scoreurs sont donc notés sur EXACTEMENT les mêmes événements, ce qui rend
la comparaison APPARIÉE : même barre, plusieurs avis, une différence testable.

LE PIÈGE QU'IL FERME. Un motif qui se déclenche rarement finit toujours par « marcher »
sur un échantillon choisi. Mesuré ici sur une marche aléatoire de 400 barres, la machine
atteint CONSOLIDATION_CONFIRMED dix fois : le motif existe dans le bruit pur. D'où le
gate emprunté à `alpha_incremental` — placebo par permutation, Sharpe déflaté, et
correction de tests multiples sur TOUS les scoreurs essayés.

CE QUE CE BANC NE FAIT PAS. Il ne note pas le setup (aucun score 0-100 : les poids
seraient choisis, pas mesurés), il ne calcule pas de reward/risk comme filtre (cible et
résistance sortent de la même analyse que le ratio, qui mesurerait alors sa propre
générosité), et il ne conclut rien sur un timeframe 4H — la base de ce dépôt est
QUOTIDIENNE, et tout chiffre intraday serait inventé.

DEUX SOURCES, ET LA CRYPTO EST LA SEULE OÙ LE 4H EXISTE (18/09). `--source actions` lit
le socle QUOTIDIEN ; `--source crypto --tf 1h|4h` lit `data/crypto_intraday.db`, ingéré
depuis Binance. Le motif demandait un timeframe d'exécution intraday : c'est ici, et
seulement ici, qu'il devient mesurable sans payer ni dépendre d'un flux partiel.

`hold` se compte en BARRES, pas en jours. Cinq barres valent cinq jours en quotidien et
cinq heures en 1h — l'oublier ferait comparer deux horizons sous le même nom.

    python scripts/deviation_reclaim_lab.py                      # actions, quotidien
    python scripts/deviation_reclaim_lab.py --source crypto --tf 4h --hold 6
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packages.indicators.deviation_reclaim import (  # noqa: E402
    CONSOLIDATION_CONFIRMED,
    DEVIATION_DETECTED,
    EXPANSION_CONFIRMED,
    PIVOT,
    RECLAIM_CONFIRMED,
    agreger_hebdo,
    etat,
    pivots_causaux,
)
from packages.research.alpha_incremental import (  # noqa: E402
    Evenement,
    comparer,
    verdict,
)

# Rang des états : « au moins RECLAIM » se lit sur un ordre, pas sur une égalité.
RANG = {DEVIATION_DETECTED: 1, RECLAIM_CONFIRMED: 2,
        CONSOLIDATION_CONFIRMED: 3, EXPANSION_CONFIRMED: 4}
# Le nom du témoin sert deux fois : à le reconnaître dans le tableau, et à le retrouver
# dans les écarts appariés. Il est écrit UNE fois, et court — les colonnes du rapport
# TRONQUENT, et un étalon qu'on ne reconnaît pas dans le tableau ne sert à rien.
TEMOIN = "TÉMOIN — toujours long"
# LES SEUILS SONT CEUX DU MODULE, et ce n'est pas un détail (18/09). Ce banc en portait
# de plus doux — DSR > 0,5 et AUCUNE condition sur l'IC — tout en annonçant « gate
# emprunté à alpha_incremental ». Deux scoreurs ont donc été affichés RETENUS avec un
# IC NÉGATIF : le banc décernait sa meilleure mention à des barres qui SOUS-performent.
SEUIL_P, SEUIL_DSR, SEUIL_IC = 0.05, 0.90, 0.03


def _rendement(barres, i: int, hold: int, lag: int) -> float | None:
    """Rendement FORWARD, entrée au close suivant le signal.

    `lag=1` n'est pas une précaution cosmétique : entrer au close de la barre qui porte
    le signal suppose d'avoir vu, décidé et exécuté avant cette clôture. C'est le
    look-ahead que tout le monde dénonce et que beaucoup d'études commettent.
    """
    e, s = i + lag, i + lag + hold
    if s >= len(barres) or float(barres[e].close) <= 0:
        return None
    return float(barres[s].close) / float(barres[e].close) - 1.0


def _sfp_long(barres, i: int) -> bool:
    from packages.indicators.liquidite_ict import sfp
    return bool(sfp(barres, i).get("sens") == "long")


def _scores(e: dict, barres, i: int) -> dict[str, float]:
    """Les avis des scoreurs à cette barre. Binaires : 1 = allumé, 0 = muet.

    LE TÉMOIN N'EST PAS UN SCOREUR DE PLUS, c'est l'étalon qui manquait. Sans lui, un
    Sharpe positif se lit comme une découverte alors qu'il peut n'être que la DÉRIVE du
    marché captée par n'importe quelle barre. Être long en permanence ne sélectionne
    rien : tout scoreur qui ne bat pas cette ligne ne vaut pas le câblage, quel que soit
    son DSR. Il entre aussi dans les écarts APPARIÉS, où la question devient exacte :
    « ces barres-là valent-elles mieux que toutes les barres ? »
    """
    rang = RANG.get(e["etat"], 0)
    conso = e.get("consolidation") or {}
    return {
        TEMOIN: 1.0,
        "sfp_seul (primitive du 02/09)": float(_sfp_long(barres, i)),
        "deviation": float(rang >= 1),
        "reclaim": float(rang >= 2),
        "consolidation": float(rang >= 3),
        "consolidation + contraction":
            float(rang >= 3 and bool(conso.get("contraction"))),
    }


def _donnees_crypto(tf: str, titres: int) -> tuple[dict, int]:
    """Barres crypto intraday depuis la base sidecar, ou ({}, 0) si absente.

    Aucune donnée n'est fabriquée ici : si la base n'existe pas ou ne porte pas ce
    timeframe, le banc s'arrête sur UNCALIBRATED plutôt que de rendre un verdict sur un
    univers vide.
    """
    from packages.storage.bars_repo import SqliteBarsRepository
    chemin = ROOT / "data" / "crypto_intraday.db"
    if not chemin.exists():
        return {}, 0
    repo = SqliteBarsRepository(chemin)
    try:
        cur = repo.conn.execute(
            "SELECT DISTINCT symbol FROM silver WHERE timeframe=? "
            "ORDER BY symbol", (tf,))
        syms = [r[0] for r in cur.fetchall()][:titres or None]
        return {s: repo.read(s, tf) for s in syms}, len(syms)
    finally:
        repo.close()


def _collecter(data: dict, syms: list[str], hold: int, pas: int, lag: int,
               depart: int) -> tuple[list[Evenement], dict[str, list[float]]]:
    """Un passage unique : les événements ET tous les avis, sur le même échantillon."""
    evenements: list[Evenement] = []
    scores: dict[str, list[float]] = {}
    for sym in syms:
        barres = data[sym]
        if len(barres) < depart + hold + lag + 10:
            continue
        piv = pivots_causaux(barres, PIVOT)
        # Le contexte macro est DÉRIVÉ de la série — une agrégation, pas une source
        # nouvelle. En quotidien c'est la semaine ; en intraday, `agreger_hebdo` groupe
        # aussi par semaine ISO, ce qui reste le bon horizon supérieur.
        hebdo = agreger_hebdo(barres)
        for i in range(depart, len(barres) - hold - lag, pas):
            r = _rendement(barres, i, hold, lag)
            if r is None:
                continue
            e = etat(barres, i, pivots=piv, hebdo=hebdo)
            evenements.append(Evenement(symbole=sym, jour=str(barres[i].ts)[:16],
                                        titre=e["etat"], rendement=r))
            for nom, v in _scores(e, barres, i).items():
                scores.setdefault(nom, []).append(v)
    return evenements, scores


def _n_effectif(evenements: list[Evenement], hold: int) -> int:
    """Combien d'observations INDÉPENDANTES, réellement ?

    Deux dépendances, qui se cumulent et qui vont toutes deux dans le sens d'une
    précision surestimée. Le rendement forward à `hold` barres est recalculé à CHAQUE
    barre : deux barres voisines partagent hold−1 barres de leur rendement. Et 200
    titres notés le MÊME jour subissent la même séance — ce ne sont pas 200 mesures,
    c'est une séance vue 200 fois.

    On prend donc le nombre de DATES distinctes, divisé par l'horizon. C'est une borne
    grossière, et volontairement pessimiste : mieux vaut un garde-fou trop sévère qu'un
    garde-fou qui affiche 1,000 sur du bruit.
    """
    return max(2, len({e.jour for e in evenements}) // max(1, hold))


def _afficher(res: dict, hold: int) -> None:
    """Le tableau des mesures. Il NOTE, il ne tranche pas — `_verdict` tranche."""
    print(f"\n  {res['n_evenements']} barres notées · horizon {hold} barres · "
          f"{res['n_essais']} scoreurs (correction de tests multiples appliquée)")
    print(f"  n EFFECTIF retenu pour le DSR : {res.get('n_effectif', 0):,} "
          "observations indépendantes\n".replace(",", " "))
    print(f"  {'scoreur':<36} {'allumé':>7} {'IC':>8} {'Sharpe':>8} {'DSR':>7} "
          f"{'placebo':>9}")
    print("  " + "-" * 80)
    for nom, m in res["mesures"].items():
        print(f"  {nom:<36} {m['part_notee']:>6.1%} {m['ic']:>+8.4f} "
              f"{m['sharpe']:>+8.3f} {m['dsr']:>7.3f} {m.get('p_placebo'):>9.6f}")


def _verdict(res: dict) -> list[str]:
    """Les TROIS portes du module, plus le SENS. Chaque rejet dit pourquoi.

    Le sens n'est pas une quatrième porte décorative : `placebo` teste |IC|, donc il est
    BILATÉRAL. Un scoreur dont les barres sous-performent significativement le passe
    aussi bien qu'un scoreur qui prédit. Ces scoreurs-ci sont LONGS — un IC négatif dit
    d'éviter ces barres, pas de les acheter.
    """
    lignes = verdict(res, seuil_p=SEUIL_P, seuil_dsr=SEUIL_DSR,
                     seuil_ic=SEUIL_IC)["scoreurs"]
    retenus = []
    print("\n  LES QUATRE PORTES — placebo · DSR · |IC| · SENS\n")
    for ligne in lignes:
        nom = ligne["scoreur"]
        ic = res["mesures"][nom]["ic"]
        motif = ligne["motif"]
        ok = bool(ligne["retenu"]) and ic > 0 and nom != TEMOIN
        if ligne["retenu"] and ic < 0:
            motif = f"IC NÉGATIF ({ic:+.4f}) — ces barres sous-performent"
        if nom == TEMOIN:
            motif = "témoin — il n'est pas candidat, il sert d'étalon"
        if ok:
            retenus.append(nom)
        print(f"    {'RETENU' if ok else 'rejeté':<7} {nom:<36} {motif}")
    return retenus


def _ecarts(res: dict) -> None:
    """Les écarts appariés, EN ENTIER — ils étaient tronqués à 88 caractères.

    La section posait « le motif complet apporte-t-il quelque chose ? » et coupait la
    ligne avant le t apparié, c'est-à-dire avant la réponse. Un rapport qui pose une
    question et masque son résultat est pire qu'un rapport muet : on croit avoir lu.
    """
    ecarts = res.get("ecarts") or []
    if not ecarts:
        return
    print("\n  ÉCARTS APPARIÉS — même barre, deux avis, une différence testable")
    print("  (t apparié > +2 : A bat B · < −2 : A perd contre B)\n")
    print(f"    {'A':<30} {'B':<30} {'A−B':>9} {'t':>7}")
    print("    " + "-" * 78)
    for e in sorted(ecarts, key=lambda x: -abs(x.get("t_apparie_a_moins_b") or 0)):
        marque = " ←" if TEMOIN in (e["a"], e["b"]) else ""
        print(f"    {e['a'][:30]:<30} {e['b'][:30]:<30} "
              f"{e['ecart_moyen_a_moins_b']:>+9.5f} "
              f"{e['t_apparie_a_moins_b']:>+7.2f}{marque}")
    print("\n    ← : comparaison contre le témoin. ATTENTION À CE QU'ELLE MESURE :")
    print("        sur une barre ÉTEINTE le témoin encaisse r et le scoreur 0, donc")
    print("        l'écart vaut le rendement du marché sur les barres NON retenues.")
    print("        C'est le TAUX D'INVESTISSEMENT, pas la qualité des barres :")
    print("        dans un marché qui monte, tout filtre y perd avec un t énorme.")
    print("        La question posée est traitée par la PRIME DE SÉLECTION ci-dessous.")


def _prime_selection(evenements: list[Evenement], scores: dict[str, list[float]],
                     n_effectif: int) -> None:
    """Les barres ALLUMÉES valent-elles mieux que TOUTES les barres ?

    C'EST LA QUESTION QUE LE TÉMOIN DEVAIT POSER, et que l'écart apparié ne pose pas.
    La colonne « Sharpe » note une stratégie qui reste à ZÉRO hors signal : elle vaut
    donc à peu près √(part allumée) × le Sharpe des barres retenues. Un scoreur allumé
    1 % du temps y est écrasé sans avoir démérité, et un scoreur allumé 50 % y paraît
    bon en ne faisant que suivre le marché à mi-temps. Les deux colonnes mélangeaient
    la SÉLECTIVITÉ et la QUALITÉ, ce qui rend le tableau lisible à l'envers.

    Ici, une seule chose : la moyenne des barres retenues, moins la moyenne de toutes
    les barres. Le t est calculé sur le n EFFECTIF ramené à la part allumée — pas sur
    le nombre de barres, qui se recouvrent et partagent leurs séances.
    """
    import math

    import numpy as np
    r = np.asarray([e.rendement for e in evenements], dtype=float)
    moy_tout = float(r.mean())
    print("\n  PRIME DE SÉLECTION — les barres ALLUMÉES valent-elles mieux "
          "que TOUTES ?\n")
    print(f"    référence : moyenne de TOUTES les barres = {moy_tout:+.5f}\n")
    print(f"    {'scoreur':<36} {'allumé':>7} {'moy. allumées':>14} "
          f"{'prime':>10} {'t':>7}")
    print("    " + "-" * 78)
    for nom, sc in scores.items():
        on = np.asarray(sc, dtype=float) > 0
        n_on = int(on.sum())
        if n_on < 2:
            continue
        moy, ecart = float(r[on].mean()), float(r[on].std())
        n_eff = max(2, int(n_effectif * n_on / max(1, len(r))))
        t = ((moy - moy_tout) / (ecart / math.sqrt(n_eff))) if ecart > 0 else 0.0
        print(f"    {nom:<36} {n_on / len(r):>6.1%} {moy:>+14.5f} "
              f"{moy - moy_tout:>+10.5f} {t:>+7.2f}")


def _timeframes(a) -> None:
    """Quels timeframes ont RÉELLEMENT servi — le pied de page suit la source.

    Il annonçait « Principal : 1D · aucune donnée intraday n'existe dans ce dépôt »
    quelle que soit la source. Vrai sur actions, FAUX dès la première mesure crypto en
    1h — et c'est la pire espèce d'erreur : un rapport qui décrit autre chose que ce
    qu'il vient de calculer, sans que rien ne cloche à l'écran.
    """
    print("\n  TIMEFRAMES RÉELLEMENT UTILISÉS")
    if a.source == "crypto":
        print(f"    principal / exécution : {a.tf} (Binance, gratuit et sans clé)")
        print("    macro                 : semaine ISO, DÉRIVÉE de la série")
        print("    → la jambe d'exécution intraday que la spec demandait est ici")
        print("      RÉELLEMENT mesurée, pas approchée par du quotidien.")
    else:
        print("    principal / exécution : 1D — la résistance de confirmation est lue")
        print("                            en 1D, PAS en 4H")
        print("    macro                 : 1W dérivé du 1D (une agrégation)")
        print("    → aucune donnée intraday ACTIONS dans ce dépôt (vault/03_TODO.md) :")
        print("      la jambe 4H reste UNCALIBRATED sur ce périmètre. En crypto, elle")
        print("      existe :  make deviation-lab-crypto")
    print()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=("actions", "crypto"), default="actions")
    ap.add_argument("--tf", default="1h", help="timeframe crypto : 1h ou 4h")
    ap.add_argument("--titres", type=int, default=120)
    ap.add_argument("--hold", type=int, default=5)
    ap.add_argument("--pas", type=int, default=1)
    ap.add_argument("--lag", type=int, default=1)
    ap.add_argument("--depart", type=int, default=60)
    ap.add_argument("--tirages", type=int, default=500)
    a = ap.parse_args()

    print(__doc__.split("    python")[0].rstrip())
    if a.source == "crypto":
        data, n_reels = _donnees_crypto(a.tf, a.titres)
        mode = f"crypto {a.tf} (Binance)"
        if not n_reels:
            print(f"\n  ⚠ UNCALIBRATED — aucune barre crypto {a.tf} en base.")
            print("    Ingérer d'abord :  make ingest-crypto-intraday")
            return 2
    else:
        from scripts.sizing_lab import _donnees
        data, _ac, mode, n_reels, _d, _f = _donnees()
        if n_reels < 30:
            print("\n  ⚠ UNCALIBRATED — aucune base de prix réelle branchée.")
            print("    Ce banc ne décide de rien : le lancer sur la machine")
            print("    qui porte les bases.")
            return 2
    syms = sorted(data)[:a.titres]
    print(f"\n  {len(syms)} série(s) · {mode} · pas {a.pas} · entrée à +{a.lag}")

    evenements, scores = _collecter(data, syms, a.hold, a.pas, a.lag, a.depart)
    if len(evenements) < 30:
        print(f"\n  ⚠ UNCALIBRATED — {len(evenements)} événements, "
              "trop peu pour conclure.")
        return 2

    res = comparer(evenements, scores, hold=a.hold, tirages=a.tirages,
                   n_effectif=_n_effectif(evenements, a.hold))
    _afficher(res, a.hold)
    retenus = _verdict(res)
    _ecarts(res)
    _prime_selection(evenements, scores, res.get("n_effectif") or len(evenements))

    print(f"\n  VERDICT : {len(retenus)} scoreur(s) passent les QUATRE portes "
          f"(placebo < {SEUIL_P} · DSR > {SEUIL_DSR} · |IC| ≥ {SEUIL_IC} · IC > 0)")
    if not retenus:
        print("    → RIEN à câbler. Le motif ne se distingue pas du hasard sur cet")
        print("      échantillon, et c'est une réponse — pas un échec du banc.")
    else:
        print("    → " + " · ".join(retenus))
        print("    Prochaine étape : PAS une stratégie. D'abord `signal_lab` pour le")
        print("    recouvrement avec le filtre de production — un signal qui répète")
        print("    l'existant n'ajoute rien, quel que soit son IC.")
    _timeframes(a)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
