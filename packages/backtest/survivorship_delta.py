"""Delta de biais du survivant (audit 07/17, XL-1) — chiffre l'optimisme du backtest.

`preset_backtest` ne voit que les titres ENCORE cotés (`data.items()`) → Sharpe/DD
optimistes (les délistés/faillis ont disparu). Ici on relance le MÊME preset sur deux
univers — survivants seuls vs survivants + délistés — et on publie l'écart.

DEUX CONDITIONS DE VALIDITÉ, ajoutées le 25/08 après avoir constaté un `Δ Sharpe +0,00`
sur données réelles qui ne prouvait rien du tout.

1. ALIGNEMENT TEMPOREL — **résolu**. `preset_backtest` empilait les séries par POSITION
   (`[-L:]`), supposant qu'elles se terminent toutes le même jour : vrai entre survivants, faux
   par construction pour un délisté dont la dernière barre est sa radiation. Ce module demande
   désormais `aligner_dates=True` (défaut) : la grille est indexée par DATE, et une ligne non
   cotée vaut NaN — pas zéro, qui inventerait une perte de 100 % le jour de la radiation.
   `aligner_dates=False` reproduit l'ancien moteur, et le module refuse alors de conclure dès
   qu'un décalage dépasse `TOLERANCE_JOURS`.

2. SÉLECTION EFFECTIVE — **toujours vérifiée**. Un délisté qui n'entre jamais dans le top-K ne
   change rien au résultat : le `Δ = 0` mesure alors la sélection, pas le biais. Le module
   publie `n_delisted_selectionnes` et refuse de conclure quand il vaut zéro.

Un « on ne peut pas mesurer » vaut infiniment mieux qu'un zéro qu'on prendrait pour une absence
de biais.

LIMITE ASSUMÉE DU CHIFFRE PRODUIT. Une ligne radiée est soldée à son DERNIER COURS COTÉ. Le
dernier cours d'une société en liquidation n'est presque jamais zéro : la perte réelle est donc
sous-estimée. Le delta publié est un **MINORANT** du biais du survivant — le vrai biais est au
moins aussi défavorable, jamais moins. C'est publié dans la clé `limite`.

Dépendance dure : les délistés doivent avoir leur OHLCV en base (`make ingest-delisted`).
Sans leurs prix, `delisted_data` est vide → delta indisponible (jamais inventé). numpy pur.
"""

from __future__ import annotations

from packages.backtest.preset_backtest import preset_backtest

# Tolérance d'alignement : quelques jours d'écart sont normaux (jours fériés, suspensions).
# Au-delà, la superposition positionnelle devient un décalage temporel réel.
TOLERANCE_JOURS = 5


def _derniere_date(barres: list):
    ts = getattr(barres[-1], "ts", None) if barres else None
    return getattr(ts, "date", lambda: None)() if ts is not None else None


def _decalage_max(survivants: dict, delistes: dict) -> int | None:
    """Écart, en jours, entre la fin des survivants et la fin la plus ancienne des délistés.

    None si les dates sont illisibles — on ne bloque pas sur une donnée qu'on ne sait pas lire,
    mais on ne prétend pas non plus qu'elle est bonne (le reste du diagnostic prend le relais)."""
    fins_s = [d for d in (_derniere_date(b) for b in survivants.values()) if d]
    fins_d = [d for d in (_derniere_date(b) for b in delistes.values()) if d]
    if not fins_s or not fins_d:
        return None
    return max(0, (max(fins_s) - min(fins_d)).days)


def survivorship_delta(survivor_data: dict, delisted_data: dict | None = None,
                       aligner_dates: bool = True, **preset_kw) -> dict:
    """Compare le preset SANS vs AVEC les délistés. Renvoie l'écart de Sharpe/CAGR/maxDD.

    Args:
        survivor_data: {symbol: [Bar,…]} des titres encore cotés (univers courant).
        delisted_data: {symbol: [Bar,…]} des titres délistés AVEC prix (sinon None/{}).
        preset_kw: mêmes paramètres passés aux deux backtests (comparaison apples-to-apples).

    Returns:
        {available, corrected, n_survivors, n_delisted, with_survivors_only,
         with_delisted, delta:{sharpe, cagr, max_drawdown}} — ou available=False si
         les données délistées manquent (leurs prix ne sont pas en base).
    """
    # ALIGNEMENT PAR DATE par défaut : c'est la seule façon de mêler des séries qui ne se
    # terminent pas le même jour. Le désactiver (`aligner_dates=False`) reste possible pour
    # comparaison, mais le module refusera alors de conclure dès qu'un décalage existe.
    preset_kw = {**preset_kw, "aligner_dates": aligner_dates}
    base = preset_backtest(survivor_data, **preset_kw)
    if not base.get("available"):
        return {"available": False, "reason": "backtest survivants indisponible"}
    if not delisted_data:
        return {
            "available": False,
            "reason": "aucun prix de délisté en base — lancer `make ingest-delisted` "
                      "puis relancer (delisted.csv ne contient que noms+dates, pas l'OHLCV)",
            "n_survivors": len(survivor_data),
            "with_survivors_only": base.get("preset"),
        }
    # CONDITION 1 — alignement temporel. Sans alignement par date, un décalage rend la
    # comparaison absurde ; avec, il est justement ce qu'on veut représenter.
    decalage = _decalage_max(survivor_data, delisted_data)
    if not aligner_dates and decalage is not None and decalage > TOLERANCE_JOURS:
        return {"available": False, "n_survivors": len(survivor_data),
                "n_delisted": len(delisted_data), "decalage_jours": decalage,
                "with_survivors_only": base.get("preset"),
                "reason": (f"les délistés se terminent {decalage} jours avant les survivants, et "
                           "le panel s'aligne par POSITION : leurs prix seraient superposés aux "
                           "mauvaises dates. Un panel aligné PAR DATE est le préalable — sans "
                           "lui, aucun chiffre de biais du survivant n'a de sens")}

    merged = {**survivor_data, **delisted_data}
    full = preset_backtest(merged, **preset_kw)
    if not full.get("available"):
        return {"available": False, "reason": "backtest avec délistés indisponible"}

    # CONDITION 2 — les délistés ont-ils été SÉLECTIONNÉS ? Sinon le delta mesure la sélection.
    retenus = [s for s in (full.get("univers") or []) if s in delisted_data]
    if not retenus:
        return {"available": False, "n_survivors": len(survivor_data),
                "n_delisted": len(delisted_data), "n_delisted_selectionnes": 0,
                "with_survivors_only": base.get("preset"),
                "reason": (f"aucun des {len(delisted_data)} délistés n'entre dans l'univers "
                           f"retenu ({full.get('top_k')} titres) : le test ne mesure rien. Il "
                           "faut des délistés qui auraient été SÉLECTIONNÉS — c'est-à-dire bien "
                           "classés avant leur disparition")}

    def _d(key: str, sub: str = "preset") -> float:
        a = (full.get(sub) or {}).get(key, 0.0)
        b = (base.get(sub) or {}).get(key, 0.0)
        return round(float(a) - float(b), 4)

    return {
        "available": True,
        "corrected": True,
        "aligne_par_date": aligner_dates,
        "decalage_jours": decalage,
        # Le dernier cours coté d'une société en liquidation n'est pas zéro : la ligne est
        # soldée à ce cours, donc la perte est SOUS-ESTIMÉE. Le chiffre est un MINORANT du
        # biais réel, et doit être lu comme tel.
        "limite": ("delta MINORANT : une ligne radiée est soldée à son DERNIER COURS COTÉ, qui "
                   "surestime la valeur de récupération d'une faillite. Le biais réel est donc "
                   "au moins aussi défavorable que ce chiffre, jamais moins"),
        "n_survivors": len(survivor_data),
        "n_delisted": len(delisted_data),
        "n_delisted_selectionnes": len(retenus),
        "delistes_selectionnes": sorted(retenus),
        "with_survivors_only": base.get("preset"),
        "with_delisted": full.get("preset"),
        "delta": {"sharpe": _d("sharpe"), "annualized": _d("annualized"),
                  "max_drawdown": _d("max_drawdown"), "total_return": _d("total_return")},
        "note": ("Écart survivants-seuls → +délistés. Un Sharpe qui CHUTE avec les "
                 "délistés = le backtest survivant était optimiste (attendu). À publier "
                 "sur /echecs comme mesure d'honnêteté du backtest long."),
    }
