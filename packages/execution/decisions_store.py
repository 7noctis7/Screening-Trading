"""Ce que le robot SAVAIT en envoyant l'ordre — conservé pour la journalisation d'après.

POURQUOI (22/09). Un achat dont le fill n'est pas encore lisible n'est pas journalisé
pendant le run ; `completer_ouvertures` le rattrape plus tard, depuis les seuls ordres
exécutés du courtier. Or le courtier ne connaît ni le rang du titre, ni le régime, ni le
prix de décision : le lot rattrapé arrive donc SANS features, `legacy=1`, et sort de
l'échantillon de calibration ML. Mesuré ce jour-là : cet échantillon était tombé à
QUATRE lots.

Le contexte de décision, lui, existe — en mémoire, dans le snapshot du run qui a envoyé
l'ordre. Il ne manque que d'être écrit avant que le processus ne meure. C'est tout
ce que fait ce module : il dépose sur disque ce que le robot savait, pour qu'un
rattrapage puisse le rattacher au fill au lieu de publier un lot aveugle.

CE QU'IL N'EST PAS. Ni une source de vérité, ni un cache de prix. Un enregistrement
absent n'autorise AUCUNE reconstitution : le rattrapage écrit alors `legacy=1`, comme
avant, et le dit. Mieux vaut un lot sans features qu'un lot aux features inventées — ce
sont les features qui entraînent le modèle.

FENÊTRE DE RATTACHEMENT. Une décision vaut pour un fill du MÊME jour, ou des trois jours
suivants : un ordre reporté hors séance, ou une crypto en `GTC`, se remplit après
coup, et c'est bien CETTE décision-là qui l'a produit. On prend la décision la plus
RÉCENTE qui précède le fill. Au-delà de trois jours on ne rattache plus : le lien
devient une
supposition, et une supposition n'a rien à faire dans un jeu d'entraînement.

RÉTENTION. Soixante jours. Le fichier sert un rattrapage de quelques jours ; le garder
indéfiniment ferait grossir un cache local sans que personne ne le lise jamais.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

_F = Path(__file__).resolve().parents[2] / ".cache" / "decisions_ouvertures.json"

FENETRE_J = 3          # une décision vaut pour un fill jusqu'à 3 jours plus tard
RETENTION_J = 60


def _charger(fichier: Path) -> list[dict]:
    try:
        d = json.loads(fichier.read_text()) if fichier.exists() else []
        return d if isinstance(d, list) else []
    except Exception:  # noqa: BLE001 — un cache illisible n'est pas une panne
        return []


def _cle(venue: object, symbole: object) -> tuple[str, str]:
    """Clé insensible à la casse et à la place : « alpaca »/« Alpaca » sont la même."""
    return (str(venue or "").strip().lower(), str(symbole or "").strip().upper())


def enregistrer(entrees: list[dict], jour: str, *, fichier: Path | None = None) -> bool:
    """Dépose les décisions du jour. Rend False si l'écriture a échoué — À DIRE.

    Un `record` silencieux ferait croire à un magasin alimenté alors qu'il est vide, et
    le manque ne se découvrirait qu'au moment d'entraîner, des semaines plus tard.

    Les entrées du même (jour, place, symbole) s'écrasent : un re-run du même jour
    remplace sa propre trace au lieu de l'empiler.
    """
    f = fichier or _F
    utiles = [{"jour": jour, "venue": str(e.get("venue") or ""),
               "symbole": str(e.get("symbol") or ""),
               # `v == v` ÉCARTE LES NaN, et ce dépôt connaît le piège : un JSON qui
               # en contient n'est plus du JSON standard, et c'est ce qui a déjà bloqué
               # l'export statique en chargement perpétuel (`dump_static._clean`).
               "features": {k: v for k, v in (e.get("features") or {}).items()
                            if isinstance(v, (int, float))
                            and not isinstance(v, bool) and v == v},
               "regime": e.get("regime")}
              for e in (entrees or []) if e.get("symbol")]
    if not utiles:
        return True
    neufs = {(u["jour"], *_cle(u["venue"], u["symbole"])) for u in utiles}
    limite = (date.fromisoformat(jour) - timedelta(days=RETENTION_J)).isoformat()
    garde = [d for d in _charger(f)
             if str(d.get("jour", "")) >= limite
             and (str(d.get("jour")),
                  *_cle(d.get("venue"), d.get("symbole"))) not in neufs]
    try:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(garde + utiles, ensure_ascii=False, indent=1))
        return True
    except Exception:  # noqa: BLE001
        return False


def retrouver(symbole: str, venue: str, jour_fill: str, *,
              fichier: Path | None = None) -> dict | None:
    """La décision qui a produit ce fill, ou None. JAMAIS une décision postérieure.

    Rend `{"features", "regime", "jour"}`. `jour` est conservé pour que l'appelant
    puisse dire de QUAND vient le contexte qu'il rattache — un rattachement muet
    serait aussi opaque qu'une absence.
    """
    try:
        fin = date.fromisoformat(str(jour_fill)[:10])
    except ValueError:
        return None
    debut = (fin - timedelta(days=FENETRE_J)).isoformat()
    cible = _cle(venue, symbole)
    candidats = [d for d in _charger(fichier or _F)
                 if _cle(d.get("venue"), d.get("symbole")) == cible
                 and debut <= str(d.get("jour", "")) <= fin.isoformat()]
    if not candidats:
        return None
    d = max(candidats, key=lambda x: str(x.get("jour")))
    feats = d.get("features") or {}
    if not feats:
        return None                       # une décision sans features n'en apporte pas
    return {"features": feats, "regime": d.get("regime"), "jour": d.get("jour")}
