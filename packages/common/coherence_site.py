"""Ce que TOUTES les pages doivent dire ensemble — invariants, pas préférences.

LE CONTEXTE. Les 24 payloads publiés dérivent d'UN SEUL snapshot (`dump_static` appelle
`M._snap()` une fois). Deux pages qui énoncent la même quantité ne peuvent donc pas
diverger à cause des données : si elles divergent, c'est que le même nombre est calculé
à deux endroits, et l'un des deux est faux. Ce dépôt en a l'historique — PSR affiché
0,0 % et 100 % sur la même page, trois conventions de Sortino, un bêta de 0,006 issu
d'un appariement positionnel, et le 04/09 un CAGR de −100 % avec un Sharpe positif.

LE PRINCIPE DE CONCEPTION : AUCUN FAUX POSITIF. Un gate qui crie au loup finit
désactivé, et ce dépôt l'a déjà vécu — le détecteur de fraîcheur macro se trompait
4 fois sur 5 et « apprenait à être ignoré ». Chaque règle ci-dessous est donc une
IMPOSSIBILITÉ, vérifiable sans connaître l'intention :

  1. Une courbe strictement positive ne peut pas porter une statistique de −100 %.
     Aucun argument de flux, de frais ou de fenêtre ne rend cela possible : si le
     capital n'a jamais touché zéro, il n'a pas été anéanti. C'est la règle qui aurait
     attrapé la panne du 04/09 par la donnée plutôt que par le symptôme.
  2. Une courbe et ses dates doivent avoir la MÊME longueur. C'est la signature de la
     famille de défauts la plus fréquente du dépôt — l'empilement positionnel, quatre
     occurrences — et elle se vérifie sans rien savoir du contenu.

CE QUI EST INVENTORIÉ PLUTÔT QUE BLOQUÉ. Les dates d'arrêté (`as_of`) diffèrent
LÉGITIMEMENT entre domaines : la crypto cote le week-end, les actions non. En faire une
règle bloquante produirait un faux positif chaque samedi. On les RECENSE donc pour
lecture humaine, sans échouer — mesurer sans juger vaut mieux qu'une règle fausse.
"""

from __future__ import annotations

import math
from typing import Any

# Sous ce seuil, une statistique affirme que le capital est anéanti.
ANEANTISSEMENT = -0.999

# Clés portant une courbe de valeurs. `dates` est traitée à part (elle les indexe).
CLES_COURBES = ("equity", "curve", "preset", "qqq", "megacap", "sector_mom", "values")

# Statistiques d'amplitude d'une courbe, donc contraintes par ses extrêmes.
CLES_AMPLITUDE = ("total_return", "cagr", "max_drawdown", "maxdd")


def _fini(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _nombres(serie: Any) -> list[float]:
    return [float(x) for x in serie if _fini(x)] if isinstance(serie, list) else []


def courbe_vs_amplitude(bloc: dict, chemin: str = "") -> list[str]:
    """Une courbe strictement positive interdit toute statistique d'anéantissement.

    Le raisonnement tient en une phrase : si le minimum de la courbe est > 0, le capital
    n'a jamais été anéanti, donc aucune statistique d'amplitude ne peut valoir −100 %.
    Les flux, les frais et le choix de fenêtre déplacent ces chiffres — ils ne les font
    pas franchir cette borne.

    On cherche les statistiques DANS le bloc et dans ses sous-blocs directs de stats
    (`metrics`, `stats`), là où le dépôt les range."""
    motifs = []
    for cle in CLES_COURBES:
        valeurs = _nombres(bloc.get(cle))
        if len(valeurs) < 2 or min(valeurs) <= 0:
            continue
        for nom_stats, stats in _blocs_de_stats(bloc):
            for k in CLES_AMPLITUDE:
                v = stats.get(k)
                if _fini(v) and v <= ANEANTISSEMENT:
                    motifs.append(
                        f"{chemin}/{cle} : courbe strictement positive "
                        f"(min {min(valeurs):.4g}) mais {nom_stats}{k} = "
                        f"{v * 100:.1f} % "
                        "— le capital n'a jamais été anéanti")
    return motifs


def _blocs_de_stats(bloc: dict) -> list[tuple[str, dict]]:
    """Le bloc lui-même, plus ses sous-blocs de statistiques usuels."""
    out = [("", bloc)]
    for nom in ("metrics", "stats"):
        sous = bloc.get(nom)
        if isinstance(sous, dict):
            out.append((f"{nom}.", sous))
    return out


def longueurs_courbe_dates(bloc: dict, chemin: str = "") -> list[str]:
    """Une courbe et ses dates doivent avoir la même longueur.

    Signature de l'empilement positionnel — quatre occurrences dans ce dépôt. Une courbe
    plus longue que ses dates décale l'axe : le graphe affiche les bons montants aux
    mauvais jours, et rien ne le signale."""
    dates = bloc.get("dates")
    if not isinstance(dates, list) or not dates:
        return []
    motifs = []
    for cle in CLES_COURBES:
        serie = bloc.get(cle)
        if isinstance(serie, list) and serie and len(serie) != len(dates):
            motifs.append(f"{chemin}/{cle} : {len(serie)} point(s) pour "
                          f"{len(dates)} date(s) — l'axe est décalé")
    return motifs


def dates_d_arrete(payload: Any, chemin: str = "") -> dict[str, str]:
    """Recense les `as_of` du payload. INVENTAIRE, pas règle : voir l'en-tête."""
    out: dict[str, str] = {}
    if isinstance(payload, dict):
        v = payload.get("as_of")
        if isinstance(v, str) and v:
            out[chemin or "racine"] = v[:10]
        for k, sous in payload.items():
            if isinstance(sous, dict):
                out.update(dates_d_arrete(sous, f"{chemin}/{k}"))
    return out


def auditer(payload: Any, chemin: str = "") -> list[str]:
    """Tous les motifs de refus d'un payload, à toute profondeur.

    Récursif parce que les courbes et leurs stats sont imbriquées différemment selon les
    pages : une règle qui ne regarde qu'un chemin connu rate le prochain endroit où le
    défaut apparaîtra."""
    motifs: list[str] = []
    if isinstance(payload, dict):
        motifs += courbe_vs_amplitude(payload, chemin)
        motifs += longueurs_courbe_dates(payload, chemin)
        for k, sous in payload.items():
            if isinstance(sous, dict):
                motifs += auditer(sous, f"{chemin}/{k}")
            elif isinstance(sous, list):
                for i, item in enumerate(sous[:50]):     # bornage : payloads longs
                    if isinstance(item, dict):
                        motifs += auditer(item, f"{chemin}/{k}[{i}]")
    return motifs
