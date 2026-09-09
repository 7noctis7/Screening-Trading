"""Sentiment & news d'un portefeuille DONNÉ — pondéré par ses poids.

POURQUOI UN MODULE À PART DE `_sentiment_section`.
L'onglet du robot moyenne ses lignes à POIDS ÉGAL : c'est le sentiment de l'univers
détenu, pas celui du capital. Une ligne à 2 % franchement baissière y pèse autant
qu'une ligne à 30 % haussière — le chiffre décrit alors un portefeuille que personne
ne détient. Dès qu'on connaît les poids (portefeuille importé par l'utilisateur), la
moyenne PONDÉRÉE est la seule qui décrive ce que le capital subit réellement. Les deux
sont renvoyées : leur ÉCART est l'information (« le pessimisme est-il sur les grosses
lignes ou sur les miettes ? »).

CE QUE CE MODULE NE FAIT PAS. Il n'écrit rien (`history.delta`, pas
`history.record_and_delta`) : un portefeuille de passage n'a pas à polluer l'historique
de sentiment du robot. Il n'invente aucun score : sans news ET sans historique de prix,
la ligne sort `disponible: False` et le dit, elle ne sort pas 0,0 — un zéro se lit
« neutre », pas « non mesuré ».
"""

from __future__ import annotations

FENETRE_MOMENTUM = 63          # ~3 mois de bourse, identique au repli de l'onglet robot
AMPLITUDE_MOMENTUM = 3.0       # +33 % sur 3 mois → score saturé à +1
PLAFOND_SYMBOLES = 40          # borne du contrat d'API ; borne aussi les flux RSS


def score_momentum(closes: list[float],
                   fenetre: int = FENETRE_MOMENTUM) -> float | None:
    """Repli HORS-LIGNE : la tendance 3 mois, bornée à [-1, +1]. `None` si trop court.

    Ce n'est PAS du sentiment, et c'est renvoyé comme tel par l'appelant (`origine`).
    C'est une mesure de prix qui remplit la case quand aucune actualité n'est
    disponible — utile pour ne pas afficher une page vide, jamais présentable comme
    l'opinion de la presse sur le titre.
    """
    if len(closes) <= fenetre + 1 or closes[-fenetre - 1] <= 0:
        return None
    variation = closes[-1] / closes[-fenetre - 1] - 1.0
    return round(max(-1.0, min(1.0, variation * AMPLITUDE_MOMENTUM)), 4)


def symbole_flux(symbole: str) -> str:
    """Symbole tel que le flux RSS Yahoo l'indexe : « BTC/USDC » n'y existe pas.

    Sans cette traduction, toute paire crypto rend 0 titre et bascule sur le repli
    momentum — silencieusement, donc en se lisant comme « pas d'actualité » alors que
    la vraie cause est un symbole que le fournisseur ne connaît pas.
    """
    s = (symbole or "").upper()
    return s.split("/")[0] + "-USD" if "/" in s else s


def _closes_tries(serie: dict[str, float] | None) -> list[float]:
    """Clôtures triées par DATE — un dict n'a pas d'ordre chronologique garanti."""
    if not serie:
        return []
    return [serie[d] for d in sorted(serie)]


def ligne(symbole: str, *, use_news: bool, serie: dict[str, float] | None = None,
          nom: str = "", secteur: str = "") -> dict:
    """Sentiment d'UN actif : news si dispo, sinon repli momentum, sinon rien."""
    from packages import sentiment as S

    score, n, heads, origine = None, 0, [], "indisponible"
    if use_news:
        try:
            r = S.news_sentiment(symbole_flux(symbole))
            if r["n"]:
                score, n, heads, origine = r["score"], r["n"], r["headlines"], "news"
        except Exception:  # noqa: BLE001 — réseau absent : on tombe sur le repli
            pass
    if score is None:
        momentum = score_momentum(_closes_tries(serie))
        if momentum is not None:
            score, origine = momentum, "momentum"
    return {"symbol": symbole, "name": nom, "sector": secteur,
            "score": score,
            "label": S.label_of(score) if score is not None else "inconnu",
            "n_news": n, "headlines": heads[:5], "origine": origine,
            "disponible": score is not None}


def lignes(symboles: list[str], *, use_news: bool, series: dict | None = None,
           noms: dict | None = None, secteurs: dict | None = None) -> list[dict]:
    """Une ligne par symbole, dans l'ordre reçu, bornée à `PLAFOND_SYMBOLES`."""
    series, noms, secteurs = series or {}, noms or {}, secteurs or {}
    return [ligne(s, use_news=use_news, serie=series.get(s),
                  nom=noms.get(s, ""), secteur=secteurs.get(s, ""))
            for s in (symboles or [])[:PLAFOND_SYMBOLES]]


def humeur(rows: list[dict], poids: dict[str, float] | None = None) -> dict:
    """Humeur simple ET pondérée, sur les seules lignes MESURÉES.

    Les lignes non mesurées sont exclues du calcul et leur poids est renvoyé
    (`poids_non_mesure`) : une humeur calculée sur 40 % du capital doit se lire comme
    telle. Le poids est renormalisé sur les lignes mesurées — sans quoi une couverture
    partielle tirerait mécaniquement l'humeur vers zéro et se lirait « neutre ».
    """
    from packages import sentiment as S

    poids = poids or {}
    mesurees = [r for r in rows if r.get("disponible")]
    total_poids = sum(poids.values()) or 0.0
    couvert = sum(poids.get(r["symbol"], 0.0) for r in mesurees)
    simple = (round(sum(r["score"] for r in mesurees) / len(mesurees), 4)
              if mesurees else None)
    pondere = (round(sum(poids.get(r["symbol"], 0.0) * r["score"]
                     for r in mesurees) / couvert, 4)
               if couvert > 0 else None)
    reference = pondere if pondere is not None else simple
    return {
        "mood": simple,
        "mood_label": S.label_of(simple) if simple is not None else "inconnu",
        "mood_pondere": pondere,
        "mood_pondere_label": S.label_of(pondere) if pondere is not None else "inconnu",
        "reference": reference,
        "n_mesurees": len(mesurees), "n_lignes": len(rows),
        "poids_mesure": round(couvert, 4),
        "poids_non_mesure": round(max(0.0, total_poids - couvert), 4),
        "couverture_news": round(
            sum(poids.get(r["symbol"], 0.0) for r in mesurees if r["origine"] == "news")
            / total_poids, 4) if total_poids > 0 else 0.0,
    }


def contributions(rows: list[dict], poids: dict[str, float],
                  pondere: float | None) -> list[dict]:
    """Part de chaque ligne dans l'humeur PONDÉRÉE — qui tire le chiffre, et de combien.

    Une humeur à −0,30 portée par une seule ligne à 35 % n'est pas la même situation
    qu'une humeur à −0,30 partagée par douze lignes : la première se règle en vendant
    une ligne, la seconde décrit le marché. Le tableau seul ne le montre pas.
    """
    couvert = sum(poids.get(r["symbol"], 0.0) for r in rows if r.get("disponible"))
    if couvert <= 0 or pondere is None:
        return []
    out = []
    for r in rows:
        if not r.get("disponible"):
            continue
        w = poids.get(r["symbol"], 0.0) / couvert
        out.append({"symbol": r["symbol"], "poids": round(w, 4),
                    "score": r["score"], "contribution": round(w * r["score"], 4)})
    return sorted(out, key=lambda c: -abs(c["contribution"]))


def _fils(limite_marche: int = 8, limite_macro: int = 6) -> tuple[list, list]:
    """Fils RSS marché + macro, scorés. Silencieux hors-ligne (listes vides)."""
    from packages import sentiment as S
    from packages.sentiment.rss import MACRO_FEEDS, fetch_headlines

    def _lot(feeds, limite):
        heads = fetch_headlines(feeds, limit=limite, timeout=3.0,
                                current_year_only=True)
        scores = S.analyze([h["title"] for h in heads])
        return [{"title": h["title"], "link": h.get("link", ""),
                 "date": h.get("date", ""), "label": sc["label"], "score": sc["score"]}
                for h, sc in zip(heads, scores, strict=False)]

    try:
        return _lot(None, limite_marche), _lot(MACRO_FEEDS, limite_macro)
    except Exception:  # noqa: BLE001
        return [], []


def analyse(positions: list[dict], *, use_news: bool, series: dict | None = None,
            noms: dict | None = None, secteurs: dict | None = None,
            fils: bool = True) -> dict:
    """Sentiment + news d'un portefeuille `[{symbol, weight}]`. N'écrit rien."""
    from packages import sentiment as S
    from packages.sentiment.history import delta

    poids = {str(p["symbol"]).upper(): float(p.get("weight") or 0.0)
             for p in (positions or [])}
    symboles = list(poids)[:PLAFOND_SYMBOLES]
    rows = lignes(symboles, use_news=use_news, series=series,
                  noms=noms, secteurs=secteurs)
    for r in rows:
        r["poids"] = round(poids.get(r["symbol"], 0.0), 6)
    h = humeur(rows, poids)
    try:                                       # lecture SEULE de l'historique
        revisions = delta({r["symbol"]: r["score"] for r in rows if r["disponible"]})
        for r in rows:
            r["score_change"] = revisions["by_symbol"].get(r["symbol"])
        mood_change, jours = revisions["mood_delta"], revisions["history_days"]
    except Exception:  # noqa: BLE001
        mood_change, jours = None, 0
    marche, macro = _fils() if fils else ([], [])
    a_des_news = any(r["n_news"] for r in rows) or bool(marche)
    return {
        "available": bool(rows), **h,
        "mood_change": mood_change, "historique_jours": jours,
        "engine": S.engine_name() if a_des_news else "momentum 63 j (repli hors-ligne)",
        # Dire « dérivé du momentum » quand AUCUN momentum n'a pu être calculé
        # attribuerait le vide à une méthode qui n'a jamais tourné.
        "source": ("news RSS — portefeuille importé" if a_des_news
                   else "dérivé du momentum (QUANT_NEWS=1 pour les news par actif)"
                   if h["n_mesurees"] else
                   "aucune mesure possible : ni actualité, ni historique local"),
        "rows": sorted(rows, key=lambda r: -r["poids"]),
        "contributions": contributions(rows, poids, h["mood_pondere"])[:8],
        "market_news": marche, "macro_news": macro,
    }
