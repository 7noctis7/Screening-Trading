#!/usr/bin/env python3
"""Le NLP apporte-t-il un alpha que le lexique n'avait pas ? — le banc qui tranche.

  python scripts/alpha_nlp_lab.py                 (ou : make alpha-nlp)
  python scripts/alpha_nlp_lab.py --hold 3 --tirages 2000

CE QU'IL DÉCIDE. Le poids du NLP : validé, ou ZÉRO. C'est la seule mesure qui justifie ou
non la suite du chantier — un GPU loué pour accélérer un signal qui n'existe pas est une
dépense, pas un investissement.

CE QU'IL EXIGE POUR PARLER. Un corpus de news DATÉES (`make news`, accumulé quotidiennement)
et une base de prix. Sans corpus suffisant il le DIT et sort : une étude d'événement sur
quelques dizaines d'observations ne conclut rien, et prétendre le contraire serait la pire
sortie possible de ce banc.

TOUS LES SCOREURS NOTENT LE MÊME ÉCHANTILLON. C'est le piège qui invalide la plupart des
comparaisons publiées : écarter les événements « sans avis » les mesurerait sur des jeux
différents, et l'écart mélangerait alors pouvoir prédictif et sélection.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

MIN_POUR_PARLER = 200      # ordre de grandeur, pas seuil magique — cf. affichage


def _scoreur_lexique(evenements) -> list[float]:
    from packages.sentiment.lexicon import score_text
    return [float(score_text(e.titre)) for e in evenements]


def _scoreur_nlp(evenements) -> list[float] | None:
    """Classe chaque titre avec le LLM local. `None` si aucun fournisseur ne répond.

    Le sentiment devient un score SIGNÉ pondéré par la confiance : un BULLISH à 0,3 de
    confiance ne doit pas peser autant qu'un BULLISH à 0,9. Un repli vaut 0 — c'est-à-dire
    « pas d'avis », et surtout pas « neutre convaincu ».
    """
    from packages.nlp.config import ConfigNLP
    from packages.nlp.moteur import MoteurNLP
    from packages.nlp.pilotes import pilote_pour, resoudre_modele
    cfg = ConfigNLP.depuis_env()
    pilote = pilote_pour(cfg)
    if pilote is None:
        return None
    # LE NOM DU MODÈLE EST UNE DONNÉE DE LA MESURE, pas un détail d'affichage : c'est
    # lui qui dira, dans six mois, QUI a produit l'alpha qu'on paiera. On le fait
    # donc trancher par le fournisseur avant le premier appel.
    resolu, motif = resoudre_modele(pilote, cfg.modele)
    pilote.modele = resolu
    cfg = cfg.avec_modele(resolu)
    print(f"  Modèle : {resolu or '(aucun)'} — {motif}")
    moteur = MoteurNLP(cfg=cfg, pilote=pilote)
    items = [(e.symbole, e.titre) for e in evenements]
    signaux = asyncio.run(moteur.classer_lot(items))
    signe = {"BULLISH": 1.0, "BEARISH": -1.0, "NEUTRAL": 0.0}
    m = moteur.metriques()
    print(f"  NLP : {m['succes']} classé(s) · {m['replis']} repli(s) · "
          f"latence médiane {m['latence_mediane_ms']} ms")
    return [0.0 if s.repli else signe[s.sentiment] * s.confiance for s in signaux]


def _prix(symboles: list[str]):
    from datetime import UTC, datetime, timedelta

    from apps.api.snapshot import (
        _HISTORY_DAYS,
        _load_prices,
        _sector_of,
        _seed_universe,
    )
    instruments = [m for m in _seed_universe() if m["symbol"] in set(symboles)]
    if not instruments:
        return {}
    fin = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    secteurs = {m["symbol"]: _sector_of(m) for m in instruments}
    data, _mode, _reels = _load_prices(instruments, secteurs,
                                       fin - timedelta(days=_HISTORY_DAYS), fin, 7)
    return data


def _afficher(rapport: dict, v: dict) -> None:
    print(f"\n  {rapport['n_evenements']} événement(s) · {rapport['n_essais']} scoreur(s) "
          "comparé(s) — la déflation du Sharpe en tient compte")
    print("  " + "─" * 88)
    print(f"  {'scoreur':14s} {'n':>5s} {'IC':>8s} {'Sharpe':>8s} {'DSR':>7s} "
          f"{'placebo':>9s} {'avis':>6s}")
    for nom, m in rapport["mesures"].items():
        print(f"  {nom:14s} {m['n']:5d} {m['ic']:8.4f} {m['sharpe']:8.3f} {m['dsr']:7.3f} "
              f"{m.get('p_placebo', 1.0):9.4f} {m['part_notee']:5.0%}")
        for i in m.get("incidents") or []:
            print(f"      ⚠ {i}")
    for e in rapport["ecarts"]:
        print(f"\n  {e['a']} − {e['b']} : écart moyen {e['ecart_moyen_a_moins_b']:+.5f} "
              f"· t apparié {e['t_apparie_a_moins_b']:+.2f}")
    print("\n  " + "─" * 88)
    for ligne in v["scoreurs"]:
        marque = "✅" if ligne["retenu"] else "⛔"
        print(f"  {marque} {ligne['scoreur']:14s} poids {ligne['poids']:.1f} — {ligne['motif']}")
    if not v["retenus"]:
        print("\n  Aucun scoreur retenu. Poids NLP = 0, et c'est un RÉSULTAT, pas un échec :")
        print("  il évite de louer du calcul pour accélérer un signal qui n'existe pas.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--hold", type=int, default=5, help="jours de détention après l'entrée")
    ap.add_argument("--tirages", type=int, default=500, help="tirages du placebo")
    ap.add_argument("--sans-nlp", action="store_true", help="lexique seul (pas de LLM)")
    a = ap.parse_args()

    from packages.research.alpha_incremental import comparer, extraire, verdict
    from packages.sentiment.corpus import charger, etat

    e = etat()
    if not e["disponible"]:
        print(f"⛔ {e['motif']}. Lancer `make news` chaque jour — un flux RSS ne se rejoue pas.",
              file=sys.stderr)
        return 2
    print(f"  Corpus : {e['n']} titre(s) · {e['n_jours']} jour(s) · {e['du']} → {e['au']}")
    if e["n"] < MIN_POUR_PARLER:
        print(f"⛔ {e['n']} titres < {MIN_POUR_PARLER} : une étude d'événement ne conclurait "
              "rien. Continuer à collecter.", file=sys.stderr)
        return 2

    corpus = charger()
    data = _prix(sorted({str(r.get("symbol") or "") for r in corpus}))
    evenements = extraire(data, corpus, hold=a.hold)
    if not evenements:
        print("⛔ Aucun événement exploitable : prix absents ou fenêtre trop courte.",
              file=sys.stderr)
        return 2

    scoreurs = {"lexique": _scoreur_lexique(evenements)}
    if not a.sans_nlp:
        nlp = _scoreur_nlp(evenements)
        if nlp is None:
            print("  ⚠ aucun fournisseur LLM — comparaison au lexique seul.")
        else:
            scoreurs["nlp"] = nlp

    rapport = comparer(evenements, scoreurs, hold=a.hold, tirages=a.tirages)
    v = verdict(rapport)
    _afficher(rapport, v)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
