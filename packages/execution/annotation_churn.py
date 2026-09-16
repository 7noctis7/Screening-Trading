"""Ce qu'il faut DIRE à côté d'une courbe d'equity réelle polluée par du churn.

LE CHOIX, ET IL EST STRUCTURANT : on ANNOTE, on ne corrige pas. Retrancher le churn de
la
série reviendrait à publier une courbe qui n'a jamais existé — le compte a bien encaissé
ces allers-retours. Une performance « telle qu'elle aurait été sans notre erreur » est
une
simulation, et elle porterait le nom d'un compte réel. L'annotation dit ce qui s'est
passé
et de combien ; le lecteur garde la série vraie sous les yeux.

TROIS ÉTATS, ET ILS NE SE CONFONDENT PAS :
  · non mesuré — l'historique du courtier n'est pas lisible d'ici (clés absentes en
  CI).
  · mesuré, sain — l'historique est lisible et ne montre aucun aller-retour de doublon.
  · mesuré, pollué — il en montre, et l'annotation dit depuis quand et combien.

Le premier et le deuxième se ressemblent à l'écran si on n'y prend pas garde, et c'est
précisément la confusion la plus coûteuse de ce projet : un silence qui se lit comme un
feu vert. `applicable` ne suffit donc pas, `mesure` l'accompagne.
"""

from __future__ import annotations

import json
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
CACHE = RACINE / ".cache" / "churn.json"


def ecrire_cache(rapport: dict, quand: str, chemin: Path = CACHE) -> None:
    """Le rapport de churn, posé sur disque par `make churn`.

    POURQUOI UN CACHE. Le rapport se calcule sur l'historique du COURTIER — un appel
    réseau, avec des clés que le build public n'a pas. Le faire depuis le snapshot le
    rendrait lent, faillible, et impossible en CI. Il est donc calculé une fois par jour
    par la commande qui le mesure déjà, et relu sans réseau par ce qui l'affiche.
    """
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps({"le": quand, "rapport": rapport}, ensure_ascii=False),
                      encoding="utf-8")


def lire_cache(chemin: Path = CACHE) -> tuple[dict | None, str]:
    """`(rapport, quand)`. `(None, "")` si le cache n'existe pas ou n'est pas lisible —
    et surtout PAS un rapport vide, qui se lirait comme « aucun churn »."""
    try:
        d = json.loads(chemin.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — un cache absent est le cas NOMINAL en CI
        return None, ""
    rap = d.get("rapport")
    return (rap if isinstance(rap, dict) else None), str(d.get("le") or "")


def annotation(rapport: dict | None, capital: float | None = None,
               mesure_le: str = "") -> dict:
    """`rapport` vient de `passages.rapport()`. `capital` sert à exprimer des POINTS.

    Sans capital, le montant est rendu seul : convertir −620 $ en points de performance
    exige de savoir sur quoi, et un dénominateur supposé fabriquerait un chiffre faux
    d'autant plus crédible qu'il est précis.
    """
    if not rapport:
        return {"applicable": False, "mesure": False,
                "motif": "historique du courtier illisible — churn NON MESURÉ, "
                         "ce qui n'est pas la même chose qu'un churn nul"}

    # LA DATE QUI COMPTE EST CELLE DU PREMIER DOUBLON QUI SE CONTREDIT, pas celle du
    # premier aller-retour tout court. Mesuré le 16/09 : le 23/06 porte un A/R de
    # −1,56 $
    # sur un jour à UN SEUL passage — du va-et-vient intra-passage, pas deux robots
    # qui se
    # défont. Dater l'annotation du 23/06 attribuait à la double planification neuf
    # semaines qu'elle n'a pas causées, et condamnait à tort les mesures de la période.
    depuis = rapport.get("depuis_doublon_cout")
    pnl = float(rapport.get("pnl_doublon") or 0.0)
    autre = float(rapport.get("pnl_hors_doublon") or 0.0)
    if not depuis:
        return {"applicable": False, "mesure": True,
                "motif": "aucun aller-retour de doublon : la courbe est saine"}

    jours = len(rapport.get("jours_a_doublon_cout") or [])
    notionnel = float(rapport.get("notionnel_churn") or 0.0)
    points = None if not capital or capital <= 0 else round(pnl / capital * 100.0, 2)

    signe = "coûté" if pnl < 0 else "rapporté"
    texte = (f"Depuis le {_fr(depuis)}, cette courbe porte le churn de rebalancements"
             f" en "
             f"double : {jours} jour(s) concerné(s), {_montant(pnl)} $ {signe} sur "
             f"{_montant(notionnel, 0)} $ brassés.")
    if points is not None:
        texte += (f" Soit {_montant(points)} point(s) de performance "
                  f"cumulée, {'en moins' if points < 0 else 'en plus'}.")
    texte += (" La série n'est PAS corrigée : elle montre ce que le compte a vraiment"
              " fait."
              " Toute comparaison « modèle contre réel » postérieure à cette date doit"
              " le retrancher, ou le dire.")
    # LA DATE DE LA MESURE, pas seulement son résultat. Un cache d'une semaine
    # sous-estime
    # le churn survenu depuis, et rien à l'écran ne le dirait — le lecteur croirait lire
    # l'état du jour.
    # LE RESTE DU CHURN EXISTE AUSSI, et il n'a pas la même cause. Le taire ferait
    # croire que tout le va-et-vient vient de la double planification — et le corriger
    # un
    # jour laisserait un écart inexpliqué.
    if abs(autre) >= 0.01:
        mot = "coûté" if autre < 0 else "rapporté"
        texte += (f" S'y ajoute {_montant(autre)} $ {mot} par des allers-retours "
                  "INTRA-passage, de cause différente.")
    if mesure_le:
        texte += f" (Mesuré le {_fr(mesure_le[:10])}.)"

    return {"applicable": True, "mesure": True, "depuis": depuis, "pnl": round(pnl, 2),
            "notionnel": round(notionnel, 2), "jours": jours, "points": points,
            "pnl_hors_doublon": round(autre, 2),
            "mesure_le": mesure_le[:10], "texte": texte}


def _montant(v: float, decimales: int = 2) -> str:
    """Format français : espace pour les milliers, virgule pour les décimales.

    Une première version passait un `replace(",", " ")` sur la PHRASE entière — et
    effaçait donc aussi les virgules de ponctuation. Formater le nombre, pas le texte
    qui le contient : une règle de typographie appliquée trop loin devient une faute.
    """
    return f"{abs(v):,.{decimales}f}".replace(",", " ").replace(".", ",")


def _fr(iso: str) -> str:
    """`2026-08-27` → `27/08/2026`. Découpé à la main : `fromisoformat` lèverait sur
    une valeur inattendue, et l'annotation ne fait jamais tomber une courbe."""
    p = str(iso).split("-")
    return f"{p[2]}/{p[1]}/{p[0]}" if len(p) == 3 and len(p[0]) == 4 else str(iso)
