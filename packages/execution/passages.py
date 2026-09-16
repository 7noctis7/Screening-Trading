"""COMBIEN de fois le robot est-il passé, et qu'a coûté un passage de trop ?

L'INVARIANT QUI REND LA MESURE POSSIBLE. `run_live._reconcile` parcourt les cibles et
envoie AU PLUS UN ordre par symbole : un delta, un ordre. Donc deux ordres sur le MÊME
symbole le MÊME jour ne décrivent aucune stratégie — ils décrivent DEUX PASSAGES. Et deux
ordres de SENS OPPOSÉ sur le même symbole le même jour, c'est un aller-retour, la seule
chose qu'une réconciliation ne peut pas produire toute seule.

Cet invariant est ce qui permet de lire l'historique du courtier comme un compte-rendu de
planificateurs, sans rien savoir des planificateurs eux-mêmes. C'est la bonne granularité :
crontabs, LaunchAgents et workflows changent de machine et d'heure ; le compte, lui, voit
tout le monde.

DEUX USAGES, UN SEUL INSTRUMENT :
  · EN ARRIÈRE — `rapport()` chiffre ce que les doublons passés ont coûté, et DEPUIS QUAND
    la courbe d'equity est polluée. Le 15/09 a coûté −60,79 $ ; la question ouverte était
    « et les semaines d'avant ? ».
  · EN AVANT — `passages()` compte les passages du jour. Plus d'un ⇒ un planificateur est
    revenu. C'est exactement la dérive que personne n'a vue quand le retard de GitHub est
    passé de trente minutes à trois heures et demie.

CE QUE LA MESURE N'EST PAS. La quantité « appariée » d'un aller-retour n'est pas un P&L
comptable : c'est ce qui a été ouvert puis refermé dans la journée, valorisé aux prix
moyens de chaque sens. C'est une BORNE du gâchis, pas une écriture de grand livre.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from packages.execution.garde_journaliere import jour_utc

# Écart au-delà duquel deux ordres n'appartiennent plus au même passage. Une
# réconciliation envoie ses vingt ordres en quelques SECONDES (mesuré le 15/09 : 13 ordres
# en 1 s, 22 en 3 s). Cinq minutes laissent donc une marge de deux ordres de grandeur, tout
# en séparant sans ambiguïté deux passages distants de trente minutes.
ECART_PASSAGE_S = 300.0


def instant(iso: str) -> datetime | None:
    """Horodatage UTC d'un ordre. Illisible → None, et l'ordre est ignoré."""
    if not iso:
        return None
    try:
        d = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return (d if d.tzinfo else d.replace(tzinfo=UTC)).astimezone(UTC)


def _remplis(ordres: list[dict]) -> list[tuple[datetime, dict]]:
    """Ordres réellement remplis, horodatés, triés. Le reste ne prouve rien."""
    out = [(instant(str(o.get("date") or "")), o) for o in (ordres or [])]
    return sorted([(t, o) for t, o in out
                   if t is not None and float(o.get("qty") or 0) > 0],
                  key=lambda x: x[0])


def passages(ordres: list[dict], ecart_max_s: float = ECART_PASSAGE_S) -> list[dict]:
    """Regroupe les ordres en PASSAGES : des paquets séparés par un silence."""
    grappes: list[list[tuple[datetime, dict]]] = []
    for t, o in _remplis(ordres):
        if grappes and (t - grappes[-1][-1][0]).total_seconds() <= ecart_max_s:
            grappes[-1].append((t, o))
        else:
            grappes.append([(t, o)])
    return [_decrire(g) for g in grappes]


def _decrire(grappe: list[tuple[datetime, dict]]) -> dict:
    notionnel = sum(abs(float(o.get("notional") or 0)) for _, o in grappe)
    return {
        "jour": grappe[0][0].date().isoformat(),
        "debut": grappe[0][0].isoformat(),
        "fin": grappe[-1][0].isoformat(),
        "n_ordres": len(grappe),
        "notionnel": round(notionnel, 2),
        "symboles": sorted({str(o.get("symbol") or "") for _, o in grappe}),
    }


def _cumul(ordres: list[dict], sens: str) -> tuple[float, float]:
    """(quantité, notionnel) d'un sens. Le notionnel manquant est reconstruit du prix."""
    q = n = 0.0
    for o in ordres:
        if str(o.get("side") or "").lower() != sens:
            continue
        qi = float(o.get("qty") or 0)
        ni = abs(float(o.get("notional") or 0)) or qi * float(o.get("price") or 0)
        q += qi
        n += ni
    return q, n


def allers_retours(ordres: list[dict], jour: date) -> dict:
    """Ce qui a été ouvert PUIS refermé dans la même journée, ligne par ligne.

    Un aller-retour intra-journalier sur un symbole est, par l'invariant du module, la
    signature de deux passages qui se contredisent. On le chiffre aux prix moyens de
    chaque sens — c'est une borne du gâchis, pas une écriture comptable.
    """
    du_jour = [o for o in (ordres or []) if jour_utc(str(o.get("date") or "")) == jour]
    lignes: list[dict] = []
    for sym in sorted({str(o.get("symbol") or "") for o in du_jour}):
        si = [o for o in du_jour if str(o.get("symbol") or "") == sym]
        qa, na = _cumul(si, "buy")
        qv, nv = _cumul(si, "sell")
        apparie = min(qa, qv)
        if apparie <= 0 or qa <= 0 or qv <= 0:
            continue                      # un seul sens : pas d'aller-retour
        pxa, pxv = na / qa, nv / qv
        lignes.append({
            "symbole": sym, "qte_appariee": round(apparie, 8),
            "px_achat": round(pxa, 6), "px_vente": round(pxv, 6),
            "notionnel": round(apparie * (pxa + pxv), 2),
            "pnl": round(apparie * (pxv - pxa), 2),
        })
    return {
        "jour": jour.isoformat(),
        "n_lignes": len(lignes),
        "notionnel": round(sum(x["notionnel"] for x in lignes), 2),
        "pnl": round(sum(x["pnl"] for x in lignes), 2),
        "lignes": lignes,
    }


def rapport(ordres: list[dict], ecart_max_s: float = ECART_PASSAGE_S) -> dict:
    """Vue d'ensemble : passages par jour, allers-retours, coût cumulé, DEPUIS QUAND."""
    ps = passages(ordres, ecart_max_s)
    par_jour: dict[str, list[dict]] = {}
    for p in ps:
        par_jour.setdefault(p["jour"], []).append(p)

    jours: list[dict] = []
    for j in sorted(par_jour):
        ar = allers_retours(ordres, date.fromisoformat(j))
        jours.append({"jour": j, "n_passages": len(par_jour[j]),
                      "heures": [p["debut"][11:19] for p in par_jour[j]],
                      "n_ordres": sum(p["n_ordres"] for p in par_jour[j]),
                      "allers_retours": ar})

    doubles = [j for j in jours if j["n_passages"] > 1]
    # DEUX DATES, ET ELLES DIFFÈRENT — l'historique réel l'a appris au module le 16/09.
    # Les doublons du 07/07 et du 24/08 n'ont produit AUCUN aller-retour : deux passages
    # qui aboutissent à la même cible ne se contredisent pas, ils se répètent. Le gâchis
    # commence le 27/08. Ne rendre que la première date ferait dater la pollution de la
    # courbe d'equity de sept semaines trop tôt — et condamnerait à tort des mesures qui
    # sont bonnes.
    couteux = [j for j in jours if j["allers_retours"]["n_lignes"] > 0]
    # TROISIÈME POPULATION, et c'est ELLE qui date la pollution par double
    # planification.
    # Le 23/06 porte un aller-retour pour −1,56 $ sur un jour à UN SEUL passage :
    # c'est du
    # va-et-vient intra-passage, pas deux robots qui se contredisent. Dater
    # l'annotation de
    # ce jour-là attribue à la double planification neuf semaines qu'elle n'a pas
    # causées —
    # et condamne à tort toutes les mesures de cette période.
    doubles_jours = {j["jour"] for j in doubles}
    doubles_couteux = [j for j in couteux if j["jour"] in doubles_jours]
    pnl_doublon = round(sum(j["allers_retours"]["pnl"] for j in doubles_couteux), 2)
    total = round(sum(j["allers_retours"]["pnl"] for j in jours), 2)
    return {
        # Ce que la DOUBLE PLANIFICATION a coûté, distinct du churn total.
        "depuis_doublon_cout": doubles_couteux[0]["jour"] if doubles_couteux else None,
        "jours_a_doublon_cout": [j["jour"] for j in doubles_couteux],
        "pnl_doublon": pnl_doublon,
        "pnl_hors_doublon": round(total - pnl_doublon, 2),
        "n_jours": len(jours),
        "jours": jours,
        "jours_a_doublon": [j["jour"] for j in doubles],
        "jours_a_cout": [j["jour"] for j in couteux],
        # Premier jour où le robot est passé DEUX FOIS, coûteux ou non.
        "depuis": doubles[0]["jour"] if doubles else None,
        # Premier jour où ces passages se sont CONTREDITS — la vraie date de pollution.
        "depuis_cout": couteux[0]["jour"] if couteux else None,
        "pnl_churn": round(sum(j["allers_retours"]["pnl"] for j in jours), 2),
        "notionnel_churn": round(sum(j["allers_retours"]["notionnel"] for j in jours), 2),
    }
