"""Gel des features tant que le classement TRADÉ ne bat pas sa nulle.

`make ic-classement` mesure. Ce module ne remesure pas : il lit le JSON et dit
si un laboratoire de features a le droit de consommer un essai.

Un horizon « bat » seulement si, ensemble :
- il est mesuré (pas UNCALIBRATED) ;
- `p_signes` passe le seuil de Šidák des horizons mesurés (ils se lisent ensemble) ;
- les deux moitiés chronologiques ont le signe de l'IC moyen ;
- |IC| dépasse le 95e centile de la nulle.

Aucun horizon dans ce cas → GELÉ. Fichier absent ou rien de mesurable →
UNCALIBRATED, gelé aussi : on n'ouvre pas les features dans le brouillard.
"""

from __future__ import annotations

import json
from pathlib import Path

ALPHA = 0.05


def seuil_sidak(k: int, alpha: float = ALPHA) -> float:
    """Seuil individuel pour `k` horizons lus ensemble."""
    if k <= 1:
        return alpha
    return 1.0 - (1.0 - alpha) ** (1.0 / k)


def _bat(r: dict, seuil: float) -> bool:
    if not r.get("available"):
        return False
    p, ic = r.get("p_signes"), r.get("ic_moyen")
    a, b = r.get("ic_premiere_moitie"), r.get("ic_seconde_moitie")
    p95 = r.get("nulle_p95")
    if None in (p, ic, a, b, p95) or ic == 0:
        return False
    if p >= seuil or abs(ic) < p95:
        return False
    return a * ic > 0 and b * ic > 0


def juger(resultats: list[dict] | None) -> dict:
    """Verdict à partir des lignes de `mesurer`, sans relire le disque."""
    lignes = [r for r in (resultats or []) if r.get("available")]
    if not lignes:
        return {"statut": "UNCALIBRATED", "gele": True, "n_mesures": 0,
                "n_qui_battent": 0, "seuil": None,
                "ligne": "IC : UNCALIBRATED — features gelées (rien de mesuré)."}
    seuil = seuil_sidak(len(lignes))
    gagnants = [r["horizon"] for r in lignes if _bat(r, seuil)]
    if not gagnants:
        return {"statut": "GELE", "gele": True, "n_mesures": len(lignes),
                "n_qui_battent": 0, "seuil": seuil,
                "ligne": (f"IC : GELÉ — {len(lignes)} horizon(s), aucun ne bat "
                          f"la nulle (Šidák {seuil:.4f}). Features arrêtées.")}
    return {"statut": "OUVERT", "gele": False, "n_mesures": len(lignes),
            "n_qui_battent": len(gagnants), "seuil": seuil,
            "horizons": gagnants,
            "ligne": (f"IC : OUVERT — horizons {gagnants} battent la nulle. "
                      "Un essai de features peut être lancé, pas adopté.")}


def lire(chemin: str | Path) -> dict:
    """Verdict du dernier `out/ic_classement.json`. Absent → UNCALIBRATED."""
    p = Path(chemin)
    if not p.is_file():
        return juger(None)
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return juger(None)
    if isinstance(doc.get("verdict"), dict) and doc["verdict"].get("statut"):
        return doc["verdict"]
    return juger(doc.get("resultats"))


def autoriser_features(chemin: str | Path) -> tuple[bool, str]:
    """(autorisé, phrase). Autorisé seulement si le verdict est OUVERT."""
    v = lire(chemin)
    return (not v["gele"], v["ligne"])
