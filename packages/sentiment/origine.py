"""D'où vient un score de sentiment — une news, une tendance, ou rien.

Le repli « pas de titre RSS → momentum 63 jours » a la forme d'une humeur de
marché. Ce n'en est pas une. Un score absent ne devient pas 0 : 0 se lit
« neutre ».
"""

from __future__ import annotations

from packages.sentiment.lexicon import label_of


def qualifier_ligne(n_news: int, score_news: float | None,
                    score_tendance: float | None) -> dict:
    """Une ligne : score, origine, étiquette. Jamais un zéro à la place d'un trou."""
    if n_news > 0 and score_news is not None:
        return {"score": float(score_news), "origine": "news",
                "label": label_of(float(score_news))}
    if score_tendance is not None:
        return {"score": float(score_tendance), "origine": "momentum",
                "label": label_of(float(score_tendance))}
    return {"score": None, "origine": "indisponible", "label": "n/d"}


def humeur(lignes: list[dict]) -> dict:
    """L'humeur affichée. S'il y a des news, elle n'inclut pas le momentum.

    Mélanger les deux produisait une « humeur de marché » dont une partie
    était le graphique. Sans aucune news, le chiffre reste, mais il n'est
    pas un fil.
    """
    news = [r for r in lignes
            if r.get("origine") == "news" and r.get("score") is not None]
    tendance = [r for r in lignes
                if r.get("origine") == "momentum" and r.get("score") is not None]
    vides = sum(1 for r in lignes if r.get("origine") == "indisponible")
    base = news or tendance
    mood = round(sum(r["score"] for r in base) / len(base), 4) if base else None
    return {
        "market_mood": mood,
        "market_label": label_of(mood) if mood is not None else "n/d",
        "humeur_est_fil": bool(news),
        "n_lignes_news": len(news),
        "n_lignes_tendance": len(tendance),
        "n_lignes_vides": vides,
    }
