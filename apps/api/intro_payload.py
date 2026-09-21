"""Chiffres de l'intro — calculés, jamais tapés à la main.

POURQUOI CE MODULE EXISTE. La landing affichait « −9 % » de drawdown, tiré d'un run
de `backtest-preset` du 23/06 sur le PRESET SEUL et une fenêtre courte (son indice de
comparaison y affiche 180 % de CAGR). Le même dépôt enregistre, pour l'allocation de
PRODUCTION sur 2016→2026, un maxDD de −25,3 %. Les deux chiffres sont vrais ; ils ne
décrivent pas la même chose, et rien à l'écran ne le disait.

Un nombre recopié dans un composant se détache de ce qu'il mesure — silencieusement,
et d'autant plus vite qu'il est flatteur. Ici tout dérive de la MÊME courbe d'equity
que le tableau de bord, avec la fenêtre écrite à côté du chiffre.

Régénéré à chaque construction du snapshot : `make site` le réécrit chaque jour ouvré
(CI Pages), `cron_daily.sh` aussi. Aucune étape manuelle, donc aucune dérive.
"""

from __future__ import annotations

from datetime import date, timedelta

# Fenêtres proposées. « Depuis le début » n'a pas de borne : c'est la série entière.
FENETRES: tuple[tuple[str, str, int | None], ...] = (
    ("ytd", "DEPUIS LE 1ᵉʳ JANVIER", 0),
    ("3a", "3 ANS", 3),
    ("5a", "5 ANS", 5),
    ("10a", "10 ANS", 10),
    ("tout", "DEPUIS LE DÉBUT", None),
)

# Sous ce nombre de points, annualiser MENT : trois mois de hausse extrapolés donnent
# un taux à trois chiffres qu'aucune année ne reproduira. On rend alors la croissance
# brute et on dit pourquoi le taux manque.
MIN_POINTS_CAGR = 190

# Points par courbe envoyés au front. Soixante suffisent à dessiner une décennie
# sans escalier visible, et gardent le JSON à quelques kilo-octets pour CINQ
# fenêtres × deux séries. Envoyer 2 580 séances pèserait plus que toute la page.
POINTS_COURBE = 60


def _jour(v) -> date | None:
    try:
        return date.fromisoformat(str(v)[:10])
    except Exception:  # noqa: BLE001
        return None


def _tranche(courbe: list[dict], depuis: date | None) -> list[tuple[date, float]]:
    """Points à partir de `depuis`. Sans borne, la série entière."""
    out: list[tuple[date, float]] = []
    for p in courbe:
        d, v = _jour(p.get("t")), p.get("v")
        if d is None or v is None:
            continue
        if depuis is None or d >= depuis:
            out.append((d, float(v)))
    return out


def _max_drawdown(vals: list[float]) -> float:
    """Pire recul depuis un sommet, en fraction NÉGATIVE. Zéro si rien ne recule."""
    pic = vals[0]
    pire = 0.0
    for v in vals:
        if v > pic:
            pic = v
        if pic > 0:
            pire = min(pire, v / pic - 1.0)
    return pire


def _reechantillonner(pts: list[tuple[date, float]], n: int) -> list[float]:
    """Garde `n` points RÉGULIÈREMENT espacés, extrémités comprises.

    Le dernier point est toujours conservé : c'est lui qui porte la performance finale,
    et l'amputer par un pas qui tombe mal fausserait la courbe de quelques pour cent
    sans que rien ne le signale.
    """
    if len(pts) <= n:
        return [v for _, v in pts]
    pas = (len(pts) - 1) / (n - 1)
    return [pts[min(len(pts) - 1, round(i * pas))][1] for i in range(n)]


def _base100(vals: list[float]) -> list[float]:
    """Ramène une série à 100 au départ. Deux séries ainsi traitées se comparent."""
    if not vals or vals[0] <= 0:
        return []
    return [round(v / vals[0] * 100.0, 2) for v in vals]


def periode(courbe: list[dict], cle: str, libelle: str, ans: int | None,
            aujourdhui: date, reference: list[dict] | None = None,
            references: dict[str, list[dict]] | None = None) -> dict:
    """Croissance, CAGR et drawdown sur UNE fenêtre. Rien d'inventé si c'est court."""
    if ans is None:
        depuis = None
    elif ans == 0:
        depuis = date(aujourdhui.year, 1, 1)
    else:
        depuis = aujourdhui - timedelta(days=round(365.25 * ans))

    pts = _tranche(courbe, depuis)
    if len(pts) < 2 or pts[0][1] <= 0:
        return {"cle": cle, "libelle": libelle, "disponible": False,
                "motif": "moins de deux points dans la fenêtre"}

    debut, fin = pts[0], pts[-1]
    croissance = fin[1] / debut[1] - 1.0
    jours = max(1, (fin[0] - debut[0]).days)
    annees = jours / 365.25
    assez = len(pts) >= MIN_POINTS_CAGR and annees >= 0.75 and croissance > -1
    cagr = ((1 + croissance) ** (1 / annees) - 1) if assez else None

    return {
        "cle": cle, "libelle": libelle, "disponible": True,
        "debut": debut[0].isoformat(), "fin": fin[0].isoformat(),
        "n_points": len(pts), "annees": round(annees, 2),
        "croissance": round(croissance, 4),
        "cagr": None if cagr is None else round(cagr, 4),
        "cagr_motif": None if assez else "fenêtre trop courte pour annualiser",
        "max_drawdown": round(_max_drawdown([v for _, v in pts]), 4),
        **_comparaison(pts, reference, debut[0], references),
    }


def _une_reference(nom: str, serie: list[dict] | None,
                   depuis: date) -> dict:
    """Une référence ramenée en base 100 au MÊME jour que nous. Son ABSENCE est dite.

    La référence est tranchée à la date de début EFFECTIVE de notre série, pas à la
    borne théorique : si le backtest commence après l'indice, comparer depuis la borne
    donnerait à l'indice une avance qu'il n'a pas eue face à nous.
    """
    if not serie:
        return {"nom": nom, "courbe": None, "croissance": None,
                "motif": "aucune série fournie"}
    rp = _tranche(serie, depuis)
    if len(rp) < 2:
        return {"nom": nom, "courbe": None, "croissance": None,
                "motif": "série trop courte sur cette fenêtre"}
    return {"nom": nom, "courbe": _base100(_reechantillonner(rp, POINTS_COURBE)),
            "croissance": round(rp[-1][1] / rp[0][1] - 1.0, 4) if rp[0][1] else None,
            "motif": ""}


def _comparaison(pts: list[tuple[date, float]], reference: list[dict] | None,
                 depuis: date, references: dict[str, list[dict]] | None = None) -> dict:
    """Notre courbe et CHAQUE référence, toutes en base 100 au même jour.

    PLUSIEURS RÉFÉRENCES, ET C'EST STRUCTURANT : comparer à un seul indice laisse croire
    que le choix de l'indice n'a pas d'importance. Un robot qui bat le S&P 500 et perd
    contre le CAC 40 ne raconte pas la même histoire selon celui qu'on affiche.

    Les clés `reference` / `reference_croissance` sont CONSERVÉES pour la PREMIÈRE
    référence. Le site statique déployé les lit encore ; les retirer d'un coup casserait
    la page en ligne jusqu'à sa prochaine reconstruction — un déploiement ne doit jamais
    dépendre de la simultanéité de deux artefacts.
    """
    nous = _base100(_reechantillonner(pts, POINTS_COURBE))
    out: dict = {"courbe": nous}

    toutes = dict(references or {})
    if reference and not toutes:
        toutes = {"référence": reference}
    calculees = [_une_reference(nom, serie, depuis) for nom, serie in toutes.items()]
    out["references"] = calculees

    premiere = next((r for r in calculees if r["courbe"]), None)
    if premiere is None:
        out["reference"] = None
        out["reference_motif"] = (calculees[0]["motif"] if calculees
                                  else "aucune série de référence fournie")
        return out
    out["reference"] = premiere["courbe"]
    out["reference_croissance"] = premiere["croissance"]
    return out


def trades(stats: dict) -> dict:
    """R:R, profit factor et espérance — depuis les trades CLÔTURÉS.

    `avg_loss` est négatif dans le payload ; le ratio prend sa valeur absolue. Une
    perte moyenne nulle rend le ratio indéfini — on le DIT plutôt que de diviser.
    """
    n = int(stats.get("count") or 0)
    if n <= 0:
        return {"disponible": False, "motif": "aucun trade clôturé"}
    perte = abs(float(stats.get("avg_loss") or 0.0))
    gain = float(stats.get("avg_win") or 0.0)
    total = float(stats.get("pnl_total") or 0.0)
    return {
        "disponible": True, "n": n,
        "taux_reussite": stats.get("win_rate"),
        "profit_factor": stats.get("profit_factor"),
        "ratio_gain_perte": round(gain / perte, 2) if perte > 0 else None,
        "esperance_par_trade": round(total / n, 2),
        "esperance_pct": stats.get("avg_pnl_pct"),
        "pnl_total": round(total, 2),
    }


def construire(dashboard: dict, trade_stats: dict, univers: dict,
               aujourdhui: date | None = None, reference: list[dict] | None = None,
               reference_nom: str = "S&P 500",
               references: dict[str, list[dict]] | None = None) -> dict:
    """Section `intro` du snapshot. Tout est dérivé ; rien n'est saisi."""
    jour = aujourdhui or date.today()
    courbe = [p for p in (dashboard.get("equity") or []) if isinstance(p, dict)]
    return {
        "disponible": bool(courbe),
        "genere_le": jour.isoformat(),
        "univers": univers,
        "reference_nom": reference_nom,
        # Les NOMS des références réellement fournies, dans l'ordre d'affichage. Le
        # front
        # en tire ses couleurs et sa légende : il ne les devine pas, et n'en invente
        # aucune quand une série manque.
        "references_noms": list((references or {}).keys()) or ([reference_nom]
                                                               if reference else []),
        "periodes": [periode(courbe, c, lib, a, jour, reference, references)
                     for c, lib, a in FENETRES],
        "trades": trades(trade_stats or {}),
        # La nature de la série est écrite ICI, pas laissée à l'interprétation :
        # c'est la précaution qui manquait au « −9 % » de la landing.
        "source": "backtest du preset de production · courbe d'equity du dashboard",
        "avertissement": "Backtest — pas un rendement réalisé. Paper par défaut.",
    }
