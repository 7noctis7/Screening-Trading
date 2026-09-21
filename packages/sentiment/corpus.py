"""Le corpus de news DATÉES — sans lui, aucune mesure du NLP n'est possible.

CE QUE L'AUDIT A DÉCOUVERT LE 16/09. Le dépôt sait lire des flux RSS (`rss.py`), scorer un
texte (`lexicon.py`), faire une étude d'événement avec IC et Sharpe déflaté
(`news_backtest.sentiment_event_study`) et gérer le point-in-time (`pit.py`). Tout est là —
sauf le corpus. `data/news.csv` n'existe pas et RIEN ne l'écrit. `.cache/sentiment_history`
ne garde que des SCORES agrégés par jour : on ne peut pas les re-scorer avec un autre
modèle, donc on ne peut pas comparer un LLM au lexique.

Conséquence : mesurer si le NLP apporte un alpha incrémental est impossible aujourd'hui, et
le resterait dans trois mois — parce que chaque jour qui passe sans collecte est un jour de
données perdu DÉFINITIVEMENT. Un flux RSS ne se rejoue pas.

LES DEUX HORODATAGES, ET POURQUOI IL EN FAUT DEUX
    `date`   quand l'éditeur dit avoir publié
    `vu_le`  quand NOUS l'avons effectivement lu
Ils diffèrent, et la différence est exactement une fuite. Un flux qui rétro-publie un article
daté de la semaine dernière nous le fait découvrir aujourd'hui ; utiliser `date` seule
laisserait une stratégie « savoir » une semaine avant d'avoir pu savoir. Le seul instant
utilisable dans un backtest est `max(date, vu_le)` — et il n'est calculable que si l'on a
enregistré les deux au moment de la collecte. Après coup, c'est perdu.

Format : CSV append-only, une ligne par titre, dédupliqué. Versionné dans git à dessein —
des titres de presse sont publics, et un corpus qui vit dans `.cache/` disparaît au premier
nettoyage de disque, ce qui annule des mois de collecte.
"""

from __future__ import annotations

import csv
import hashlib
from datetime import UTC, datetime
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
CHEMIN = RACINE / "data" / "news.csv"
COLONNES = ("symbol", "date", "headline", "source", "vu_le", "empreinte")


def _empreinte(symbole: str, titre: str) -> str:
    """Identité d'un titre pour UN symbole. Le même titre repris par trois agrégateurs ne
    doit compter qu'une fois : trois occurrences d'une même nouvelle gonfleraient
    artificiellement le poids de l'événement dans l'étude."""
    brut = f"{symbole.upper()}|{' '.join(titre.lower().split())}"
    return hashlib.sha256(brut.encode("utf-8")).hexdigest()[:20]


def charger(chemin: Path = CHEMIN) -> list[dict]:
    """Le corpus, tel qu'il est sur disque. Vide s'il n'existe pas encore."""
    if not chemin.exists():
        return []
    with chemin.open(encoding="utf-8", newline="") as f:
        return [dict(r) for r in csv.DictReader(f)]


def _empreintes(lignes: list[dict]) -> set[str]:
    return {str(r.get("empreinte") or "") for r in lignes}


def normaliser(brut: dict, symbole: str, maintenant: datetime | None = None) -> dict | None:
    """Une entrée de flux → une ligne de corpus. `None` si inexploitable.

    Un titre SANS DATE est refusé. On pourrait lui attribuer la date du jour — et ce serait
    la pire des options : l'article pourrait avoir des semaines, et on lui donnerait une
    fraîcheur qu'il n'a pas, dans un jeu qui sert justement à mesurer de la prédiction.
    """
    titre = str(brut.get("title") or brut.get("headline") or "").strip()
    if not titre:
        return None
    d = brut.get("date") or brut.get("ts")
    jour = _jour(d)
    if jour is None:
        return None
    vu = (maintenant or datetime.now(UTC)).date().isoformat()
    return {"symbol": symbole.upper(), "date": jour, "headline": titre,
            "source": str(brut.get("source") or "")[:60], "vu_le": vu,
            "empreinte": _empreinte(symbole, titre)}


def _jour(valeur) -> str | None:
    if valeur is None or valeur == "":
        return None
    try:
        if isinstance(valeur, datetime):
            return valeur.date().isoformat()
        return datetime.fromisoformat(str(valeur).replace("Z", "+00:00")).date().isoformat()
    except (TypeError, ValueError):
        try:
            return datetime.strptime(str(valeur)[:10], "%Y-%m-%d").date().isoformat()
        except (TypeError, ValueError):
            return None


def ajouter(nouvelles: list[dict], chemin: Path = CHEMIN) -> dict:
    """Ajoute au corpus, sans jamais réécrire l'existant.

    APPEND-ONLY, et ce n'est pas un détail : réécrire le fichier permettrait de modifier
    rétroactivement un `vu_le`, c'est-à-dire de fabriquer une antériorité qu'on n'avait pas.
    Un corpus qu'on peut réécrire ne prouve plus rien.
    """
    connues = _empreintes(charger(chemin))
    a_ecrire: list[dict] = []
    for n in nouvelles:
        e = str(n.get("empreinte") or "")
        if not e or e in connues:
            continue
        connues.add(e)
        a_ecrire.append(n)
    if not a_ecrire:
        return {"ajoutees": 0, "doublons": len(nouvelles), "total": len(connues)}
    chemin.parent.mkdir(parents=True, exist_ok=True)
    nouveau = not chemin.exists()
    with chemin.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(COLONNES))
        if nouveau:
            w.writeheader()
        for n in a_ecrire:
            w.writerow({c: n.get(c, "") for c in COLONNES})
    return {"ajoutees": len(a_ecrire), "doublons": len(nouvelles) - len(a_ecrire),
            "total": len(connues)}


def utilisable_le(ligne: dict) -> str:
    """L'instant à partir duquel un titre peut entrer dans une décision.

    `max(date, vu_le)` : ni avant sa publication, ni avant qu'on ait pu la lire. C'est la
    seule borne qui ne fuit pas.
    """
    return max(str(ligne.get("date") or ""), str(ligne.get("vu_le") or ""))


def etat(chemin: Path = CHEMIN) -> dict:
    """De quoi savoir si le corpus est encore trop court pour conclure."""
    lignes = charger(chemin)
    if not lignes:
        return {"disponible": False, "motif": "corpus vide — la collecte n'a jamais tourné",
                "n": 0}
    jours = sorted({str(r.get("date") or "")[:10] for r in lignes if r.get("date")})
    symboles = {str(r.get("symbol") or "") for r in lignes}
    retards = sum(1 for r in lignes if utilisable_le(r) != str(r.get("date") or ""))
    return {
        "disponible": True, "n": len(lignes),
        "n_symboles": len(symboles), "n_jours": len(jours),
        "du": jours[0] if jours else "", "au": jours[-1] if jours else "",
        # Un titre découvert APRÈS sa date de publication : la mesure même de la fuite
        # qu'on aurait introduite en se fiant à `date` seule.
        "retro_publies": retards,
        "part_retro": round(retards / len(lignes), 4),
    }
