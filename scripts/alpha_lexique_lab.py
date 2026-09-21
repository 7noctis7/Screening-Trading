#!/usr/bin/env python3
"""Le LEXIQUE apporte-t-il un alpha mesurable sur le corpus ? — le banc qui tranche.

  python scripts/alpha_lexique_lab.py            (ou : make alpha-lexique)
  python scripts/alpha_lexique_lab.py --hold 10 --tirages 1000

CE BANC NE DÉPEND D'AUCUN LLM. Étude d'événement, comparaison appariée, placebo par
permutation : la mécanique est la même quel que soit le scoreur. La chaîne NLP locale
a été
retirée (ADR-0170) ; la QUESTION qu'elle devait servir, elle, tient toujours — et le
lexique
est un scoreur comme un autre, déjà en production.

IL FAUT DEUX CHOSES, ET ELLES NE VIVENT PAS FORCÉMENT AU MÊME ENDROIT : le corpus daté
(`make news`) ET une base de prix. Le 16/09, le banc a échoué sur « prix absents ou
fenêtre
trop courte » — un message qui ne disait PAS laquelle des deux causes s'appliquait,
sur une
machine qui avait le corpus et pas les prix. Ce banc-ci les compte et les nomme.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

MIN_POUR_PARLER = 200      # ordre de grandeur, pas seuil magique — cf. affichage


def _scoreur_lexique(evenements) -> list[float]:
    from packages.sentiment.lexicon import score_text
    return [float(score_text(e.titre)) for e in evenements]


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


def _diagnostic(corpus: list[dict], data: dict, hold: int) -> str:
    """POURQUOI il n'y a aucun événement. Trois causes, trois remèdes différents.

    « Prix absents ou fenêtre trop courte » envoie chercher au hasard. Un symbole sans
    barres se règle en ingérant des prix ; un titre trop récent se règle en attendant
    que
    la fenêtre de détention s'écoule. Confondre les deux fait croire à une panne là où
    il
    n'y a que du temps qui n'est pas encore passé.
    """
    symboles = {str(r.get("symbol") or "") for r in corpus}
    sans_prix = sorted(s for s in symboles if s and not data.get(s))
    avec = len(symboles) - len(sans_prix)
    lignes = [f"{len(symboles)} symbole(s) au corpus · {avec} avec des prix · "
              f"{len(sans_prix)} SANS"]
    if sans_prix:
        apercu = ", ".join(sans_prix[:8]) + ("…" if len(sans_prix) > 8 else "")
        lignes.append(f"sans barres : {apercu}")
        lignes.append("→ cette machine n'a pas la base de prix : lancer le banc SUR LE "
                      "VPS, ou ingérer les prix ici (`make daily`).")
    else:
        # LA DATE QUI COMPTE N'EST PAS CELLE DE PUBLICATION. Un corpus qui s'étale sur
        # quatre mois de publications peut n'avoir AUCUNE date utilisable ancienne :
        # si la
        # première collecte a eu lieu aujourd'hui, `utilisable_le = max(date, vu_le)`
        # vaut
        # aujourd'hui pour TOUS les titres. Afficher « corpus trop récent » à côté d'un
        # « 19/05 → 16/09 » se lit comme une contradiction, et envoie chercher un bug.
        from packages.sentiment.corpus import utilisable_le
        jours = sorted(j for j in (utilisable_le(r) for r in corpus) if j)
        if not jours:
            lignes.append("→ aucun titre n'a de date utilisable : corpus illisible.")
            return "\n  ".join(lignes)
        dernier = jours[-1]
        au_dernier = sum(1 for j in jours if j == dernier)
        lignes.append("les prix sont là. Dates UTILISABLES "
                      f"(max(publication, vu_le)) : {jours[0]} → {dernier}")
        lignes.append(f"{au_dernier} titre(s) sur {len(jours)} sont utilisables au "
                      f"{dernier} — découverts ce jour-là, pas publiés ce jour-là")
        lignes.append(f"→ il faut {hold} séance(s) APRÈS la date utilisable. Le banc "
                      "deviendra mesurable environ une semaine après la PREMIÈRE "
                      "collecte, pas après la plus ancienne publication.")
    return "\n  ".join(lignes)


def _afficher(rapport: dict, v: dict) -> None:
    print(f"\n  {rapport['n_evenements']} événement(s) · {rapport['n_essais']} "
          "scoreur(s) — la déflation du Sharpe en tient compte")
    print("  " + "─" * 88)
    print(f"  {'scoreur':14s} {'n':>5s} {'IC':>8s} {'Sharpe':>8s} {'DSR':>7s} "
          f"{'placebo':>9s} {'avis':>6s}")
    for nom, m in rapport["mesures"].items():
        print(f"  {nom:14s} {m['n']:5d} {m['ic']:8.4f} {m['sharpe']:8.3f} "
              f"{m['dsr']:7.3f} {m.get('p_placebo', 1.0):9.4f} {m['part_notee']:5.0%}")
        for i in m.get("incidents") or []:
            print(f"      ⚠ {i}")
    for e in rapport["ecarts"]:
        print(f"\n  {e['a']} − {e['b']} : écart moyen "
              f"{e['ecart_moyen_a_moins_b']:+.5f} · t apparié "
              f"{e['t_apparie_a_moins_b']:+.2f}")
    print("\n  " + "─" * 88)
    for ligne in v["scoreurs"]:
        marque = "✅" if ligne["retenu"] else "⛔"
        print(f"  {marque} {ligne['scoreur']:14s} poids {ligne['poids']:.1f} — "
              f"{ligne['motif']}")
    if not v["retenus"]:
        print("\n  Aucun scoreur retenu. Poids sentiment = 0 — un RÉSULTAT, pas un")
        print("  échec : il évite de bâtir sur un signal qui n'existe pas.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--hold", type=int, default=5,
                    help="jours de détention après l'entrée")
    ap.add_argument("--tirages", type=int, default=500, help="tirages du placebo")
    a = ap.parse_args()

    from packages.research.alpha_incremental import comparer, extraire, verdict
    from packages.sentiment.corpus import charger, etat

    e = etat()
    if not e["disponible"]:
        print(f"⛔ {e['motif']}. Lancer `make news` chaque jour — un flux RSS ne se "
              "rejoue pas.", file=sys.stderr)
        return 2
    print(f"  Corpus : {e['n']} titre(s) · {e['n_jours']} jour(s) · "
          f"{e['du']} → {e['au']}")
    if e["n"] < MIN_POUR_PARLER:
        print(f"⛔ {e['n']} titres < {MIN_POUR_PARLER} : une étude d'événement ne "
              "conclurait rien. Continuer à collecter.", file=sys.stderr)
        return 2

    corpus = charger()
    data = _prix(sorted({str(r.get("symbol") or "") for r in corpus}))
    evenements = extraire(data, corpus, hold=a.hold)
    if not evenements:
        print("⛔ Aucun événement exploitable.", file=sys.stderr)
        print("  " + _diagnostic(corpus, data, a.hold), file=sys.stderr)
        return 2

    rapport = comparer(evenements, {"lexique": _scoreur_lexique(evenements)},
                       hold=a.hold, tirages=a.tirages)
    _afficher(rapport, verdict(rapport))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
