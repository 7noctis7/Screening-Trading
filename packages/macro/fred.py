"""Client FRED (Réserve fédérale de St. Louis) — données macro CHIFFRÉES, gratuit.

FRED agrège US + international (OCDE/Eurostat/BCE). Clé gratuite : https://fred.stlouisfed.org →
My Account → API Keys, puis `export FRED_API_KEY=...`. Chaque série est récupérée indépendamment
(dégrade proprement si absente/hors-ligne). `units` : lin (niveau), pc1 (variation a/a %),
chg (variation période). stdlib (urllib).
"""

from __future__ import annotations

import json
import os
import urllib.request
from datetime import date

_BASE = "https://api.stlouisfed.org/fred/series/observations"

# (series_id, libellé, groupe, unité, suffixe d'affichage)
SERIES: list[tuple] = [
    ("UNRATE", "Chômage", "🇺🇸 États-Unis", "lin", "%"),
    ("CPIAUCSL", "Inflation (IPC, a/a)", "🇺🇸 États-Unis", "pc1", "%"),
    ("FEDFUNDS", "Taux directeur Fed", "🇺🇸 États-Unis", "lin", "%"),
    ("DGS2", "Taux 2 ans", "🇺🇸 États-Unis", "lin", "%"),
    ("DGS10", "Taux 10 ans", "🇺🇸 États-Unis", "lin", "%"),
    ("INDPRO", "Production indus. (a/a)", "🇺🇸 États-Unis", "pc1", "%"),
    ("UMCSENT", "Confiance ménages", "🇺🇸 États-Unis", "lin", ""),
    # ("LRHUTTTTEZM156S", "Chômage", "🇪🇺 Zone euro", …) — RETIRÉE le 25/08 : dernière observation
    # 2023-01-01, soit 1332 jours de retard au contrôle. Série arrêtée, pas en retard. Aucun
    # remplaçant n'est proposé ici : je ne sais pas en vérifier un depuis l'environnement de
    # développement, et deviner un identifiant reviendrait à remplacer une série morte par une
    # série peut-être morte. À re-sourcer (cf. docs/ROADMAP.md).
    ("CP0000EZ19M086NEST", "Inflation (IPCH, a/a)", "🇪🇺 Zone euro", "pc1", "%"),
    ("IRLTLT01DEM156N", "Taux 10 ans (Bund)", "🇩🇪 Allemagne", "lin", "%"),
    ("DCOILWTICO", "Pétrole WTI", "🛢️ Marchés", "lin", "$"),
    ("VIXCLS", "VIX (volatilité)", "🛢️ Marchés", "lin", ""),
    ("T10Y2Y", "Courbe 10a − 2a", "🛢️ Marchés", "lin", " pts"),
    ("BAMLH0A0HYM2", "Spread haut rendement", "🛢️ Marchés", "lin", "%"),
    # --- AJOUTS DU 25/08 : séries qui informent une DÉCISION, pas un tableau de bord ---
    # Le critère de sélection n'est pas « c'est de la macro » mais « par quel canal ceci
    # peut-il déplacer une exposition ? ». Chacune répond à une question que le régime actuel
    # (MM200 + drawdown) ne sait pas poser.
    #
    # ⚠️ IDENTIFIANTS NON VÉRIFIÉS contre l'API depuis l'environnement de développement : le
    # policy réseau y refuse api.stlouisfed.org. `make macro-verify` les contrôle en une
    # commande. Un identifiant erroné n'est pas silencieux — il apparaît dans `manquantes`.
    ("ICSA", "Inscriptions chômage (hebdo)", "🇺🇸 États-Unis", "lin", ""),
    ("SAHMREALTIME", "Règle de Sahm (récession)", "🇺🇸 États-Unis", "lin", " pts"),
    ("T5YIFR", "Inflation anticipée 5a dans 5a", "🇺🇸 États-Unis", "lin", "%"),
    ("NFCI", "Conditions financières (Chicago Fed)", "💧 Liquidité & crédit", "lin", ""),
    ("BAMLC0A0CM", "Spread investment grade", "💧 Liquidité & crédit", "lin", "%"),
    ("WALCL", "Bilan de la Fed", "💧 Liquidité & crédit", "lin", " M$"),
    ("DTWEXBGS", "Indice dollar (large)", "🛢️ Marchés", "lin", ""),
]

# Ce que chaque série APPORTE — écrit ici plutôt que dans une note séparée, pour que la
# justification vieillisse avec le code. Une série dont on ne sait plus dire ce qu'elle informe
# est une série à retirer.
POURQUOI: dict[str, str] = {
    "ICSA": "signal du marché du travail le plus RAPIDE (hebdomadaire) : le chômage mensuel "
            "confirme un retournement que celui-ci a déjà signalé",
    "SAHMREALTIME": "règle mécanique de détection de récession, en temps réel — pas une opinion "
                    "d'économiste mais un seuil sur le chômage",
    "T5YIFR": "ce que le marché anticipe de l'inflation À LONG TERME, donc la contrainte réelle "
              "qui pèse sur la Fed ; l'IPC publié, lui, est du passé",
    "NFCI": "conditions financières agrégées : se resserre AVANT que les actions ne baissent",
    "BAMLC0A0CM": "spread investment grade. Le dépôt suivait déjà le haut rendement ; c'est leur "
                  "ÉCART qui distingue un stress de crédit généralisé d'une aversion au risque "
                  "cantonnée aux émetteurs fragiles",
    "WALCL": "bilan de la Fed : la liquidité qui entre ou sort du système",
    "DTWEXBGS": "dollar large. Un dollar qui monte resserre les conditions hors des États-Unis "
                "et pèse sur les matières premières",
}


# Au-delà de ce multiple de sa CADENCE habituelle, une série est déclarée périmée. Trois fois
# l'intervalle observé laisse passer un retard de publication ordinaire (un mois de décalage sur
# une série mensuelle) sans laisser passer une série morte.
_FACTEUR_RETARD = 3.0

# Nombre d'observations lues pour estimer la cadence. Il en faut assez pour VOIR un week-end :
# avec 4 observations d'une série quotidienne on ne voit que des espacements de 1 jour, et le
# lundi suivant la série paraît morte. 12 observations couvrent au moins deux week-ends.
_N_OBS_CADENCE = 12

# Quantile des espacements retenu comme cadence. Le MINIMUM était le mauvais choix : pour une
# série quotidienne il vaut 1 jour, si bien qu'un simple week-end (3 jours) dépassait déjà le
# seuil de 3×. Contrôle du 25/08 : 4 des 5 séries signalées « périmées » l'étaient à tort —
# DGS2, DGS10 et DTWEXBGS à 4 jours un mardi, c'est-à-dire un vendredi plus un week-end.
# Un détecteur qui se trompe 4 fois sur 5 n'est pas prudent, il apprend à être ignoré.
# Le maximum serait trop indulgent (une interruption exceptionnelle relèverait le seuil pour
# toujours) ; un quantile haut absorbe les week-ends et les jours fériés sans absorber un arrêt.
_QUANTILE_CADENCE = 0.9


def _retard(dates: list[str]) -> tuple[int, bool]:
    """(jours depuis la dernière observation, périmée ?) — cadence déduite de la série elle-même.

    Aucune table de fréquence à maintenir : on mesure l'espacement RÉEL entre les dernières
    observations. Une série qui publiait tous les mois et n'a rien donné depuis un an est
    périmée, quelle que soit sa fréquence théorique.
    """
    try:
        ds = [date.fromisoformat(x) for x in dates]
    except ValueError:
        return 0, False
    if not ds:                      # liste vide : rien à mesurer, et surtout pas d'index [0]
        return 0, False
    retard = (date.today() - ds[0]).days
    if len(ds) < 2:
        return retard, False
    espacements = sorted(e for e in ((ds[i] - ds[i + 1]).days for i in range(len(ds) - 1)) if e > 0)
    if not espacements:
        return retard, False
    rang = min(len(espacements) - 1, int(_QUANTILE_CADENCE * len(espacements)))
    cadence = max(1, espacements[rang])
    return retard, retard > _FACTEUR_RETARD * cadence


def _fetch(series_id: str, units: str, key: str) -> dict | None:
    try:
        # Assez d'observations pour VOIR un week-end (cf. _N_OBS_CADENCE) : avec 4 points,
        # une série quotidienne n'exhibe que des espacements de 1 jour et paraît morte le lundi.
        url = (f"{_BASE}?series_id={series_id}&api_key={key}&file_type=json"
               f"&units={units}&sort_order=desc&limit={_N_OBS_CADENCE}")
        with urllib.request.urlopen(url, timeout=6) as r:  # noqa: S310
            obs = json.loads(r.read().decode()).get("observations", [])
        vals = [(o["date"], float(o["value"])) for o in obs if o.get("value") not in (".", None, "")]
        if not vals:
            return None
        (d0, v0) = vals[0]
        delta = round(v0 - vals[1][1], 2) if len(vals) > 1 else None
        retard, perimee = _retard([d for d, _ in vals])
        return {"value": round(v0, 2), "date": d0, "delta": delta,
                "retard_jours": retard, "perimee": perimee}
    except Exception:  # noqa: BLE001
        return None


def macro_snapshot() -> dict:
    """Tableau macro chiffré (FRED). {available, groups:{groupe:[{label,value,unit,date,delta}]}}."""
    key = os.environ.get("FRED_API_KEY")
    if not key:
        return {"available": False, "reason": "FRED_API_KEY absente (clé gratuite sur fred.stlouisfed.org)"}
    groups: dict[str, list] = {}
    # Une série qui ne répond pas était SILENCIEUSEMENT ignorée : un identifiant erroné ou une
    # série retirée disparaissait du tableau sans laisser de trace, et personne ne s'en apercevait.
    manquantes: list[str] = []
    perimees: list[str] = []
    for sid, label, group, units, unit in SERIES:
        d = _fetch(sid, units, key)
        if not d:
            manquantes.append(f"{label} ({sid})")
            continue
        if d.get("perimee"):
            perimees.append(f"{label} ({sid}) — dernière valeur {d['date']}, "
                            f"{d['retard_jours']} j de retard")
        groups.setdefault(group, []).append({"label": label, "unit": unit, **d})
    if not groups:
        return {"available": False, "reason": "FRED injoignable (réseau ou clé invalide)"}
    return {"available": True, "groups": groups,
            "manquantes": manquantes, "perimees": perimees, "pourquoi": POURQUOI,
            "source": "FRED (Réserve fédérale de St. Louis) — agrège OCDE/Eurostat/BCE. Dernière valeur publiée."}
