"""Assemble un snapshot complet de l'app depuis un run OFFLINE (synthétique).

Sert de source de données à l'API (et au front en mode démo) sans réseau. En prod, les
routes liront l'état live (broker, DB, régime du jour) au lieu de ce snapshot.
"""

from __future__ import annotations

import csv
from datetime import UTC, datetime, timedelta
from pathlib import Path

from packages.common.env import load_env as _load_env

_load_env()   # charge .env (clés brokers, FMP, QUANT_PRICE_DB, QUANT_NEWS, LLM_*) au plus tôt

from apps.api import payloads as PL
from packages.backtest.fast_swing import fast_swing_backtest
from packages.common import load_yaml
from packages.common.safe_section import safe_section
from packages.data import data_providers
from packages.execution import CostModel
from packages.portfolio import (
    attribution,
    cluster,
    correlation_matrix,
    expert_review,
    mc_projection,
    monte_carlo,
    relative_metrics,
    risk_metrics_fn,
)
from packages.portfolio.metrics import returns_from_equity
from packages.reporting.bench_curves import bench_series
from packages.ranking import RankingEngine
from packages.regime import MacroImpactMap, MacroRegimeClassifier, synthetic_macro
from packages.storage import MacroStore

# DÉCOUPAGE DU 31/10 : les définitions vivent dans `apps/api/snapshot_parts/`, texte inchangé.
# Ce fichier ré-exporte chaque nom : `from apps.api.snapshot import X` et `snapshot.X`
# marchent comme avant ; la forme `X as X` rend le ré-export explicite pour mypy (strict).
# `build_snapshot` reste ici.


# Données de référence (secteurs/thèmes/GICS) extraites dans `sections_data.py` (dé-god-objectage).
# Alias privés conservés → le reste du fichier est inchangé.
from apps.api.sections_data import GICS_MAP as _GICS_MAP  # noqa: E402
from apps.api.sections_data import SECTOR_DV as _SECTOR_DV  # noqa: E402
from apps.api.sections_data import THEME_TICKERS as _THEME_TICKERS  # noqa: E402
from packages.execution.rebalance_plan import min_ligne as _min_ligne  # noqa: E402


# Modèle d'edge ML : extrait vers `packages/ml/edge_transversal` le 06/10 (un module
# qui sert des pages n'entraîne pas de modèle). Noms conservés pour `make train`.
from packages.ml.edge_transversal import section_ml as _ml_section  # noqa: E402
import os as _os_hist  # noqa: E402, F401
from apps.api.snapshot_parts.base import (  # noqa: E402, F401 — ré-export
    ROOT as ROOT,
    _HISTORY_DAYS as _HISTORY_DAYS,
    _NETWORK_KINDS as _NETWORK_KINDS,
)
from apps.api.snapshot_parts.prix import (  # noqa: E402, F401 — ré-export
    RETARD_MAX_JOURS as RETARD_MAX_JOURS,
    _curve_stats as _curve_stats,
    _index_closes as _index_closes,
    _index_closes_dates as _index_closes_dates,
    _index_series as _index_series,
    _load_prices as _load_prices,
    _noms_sources as _noms_sources,
    _price_db_path as _price_db_path,
    _r as _r,
    _series_perimees as _series_perimees,
    _yahoo_aliases as _yahoo_aliases,
)
from apps.api.snapshot_parts.univers import (  # noqa: E402, F401 — ré-export
    _SECTEURS_VEHICULE as _SECTEURS_VEHICULE,
    _SECTEUR_INCONNU as _SECTEUR_INCONNU,
    _db_full_universe as _db_full_universe,
    _sector_of as _sector_of,
    _seed_universe as _seed_universe,
    _setup_label as _setup_label,
    _universe_section as _universe_section,
    contient_des_prix_reels as contient_des_prix_reels,
    is_real_mode as is_real_mode,
)
from apps.api.snapshot_parts.marche import (  # noqa: E402, F401 — ré-export
    _VIX_NON_CALIBRE as _VIX_NON_CALIBRE,
    _attach_rank_scores as _attach_rank_scores,
    _data_section as _data_section,
    _rank_score_map as _rank_score_map,
    _themes_section as _themes_section,
    _vix_playbook as _vix_playbook,
    _vix_series as _vix_series,
)
from apps.api.snapshot_parts.live import (  # noqa: E402, F401 — ré-export
    _live_section as _live_section,
    _live_with_rebalance as _live_with_rebalance,
    _sentiment_section as _sentiment_section,
)
from apps.api.snapshot_parts.fondamentaux import (  # noqa: E402, F401 — ré-export
    SANS_SOURCE_REELLE as SANS_SOURCE_REELLE,
    _fund_provider as _fund_provider,
    _fund_provider_chain as _fund_provider_chain,
    _fundamentals_section as _fundamentals_section,
    _investor_section as _investor_section,
    fetch_financials_chain as fetch_financials_chain,
)
from apps.api.snapshot_parts.divers import (  # noqa: E402, F401 — ré-export
    _TICKER_STOCKS as _TICKER_STOCKS,
    _conviction_section as _conviction_section,
    _crypto_cockpit_section as _crypto_cockpit_section,
    _env_int as _env_int,
    _essais_de_recherche as _essais_de_recherche,
    _intro_section as _intro_section,
    _psr_block as _psr_block,
    _psr_dsr as _psr_dsr,
    _screen_section as _screen_section,
    _serie_datee as _serie_datee,
    _ticker_section as _ticker_section,
    _vol_annualisee as _vol_annualisee,
)
from apps.api.snapshot_parts.compte import (  # noqa: E402, F401 — ré-export
    _account_compare as _account_compare,
    _courbes_bots_tiers as _courbes_bots_tiers,
    _earnings_risk as _earnings_risk,
    _top_traded as _top_traded,
)
from apps.api.snapshot_parts.etapes_1 import (  # noqa: E402, F401 — ré-export
    _sb_01 as _sb_01,
    _sb_02 as _sb_02,
    _sb_03 as _sb_03,
    _sb_04 as _sb_04,
    _sb_05 as _sb_05,
    _sb_06 as _sb_06,
    _sb_07 as _sb_07,
    _sb_08 as _sb_08,
)
from apps.api.snapshot_parts.etapes_2 import (  # noqa: E402, F401 — ré-export
    _sb_09 as _sb_09,
    _sb_10 as _sb_10,
    _sb_11 as _sb_11,
    _sb_12 as _sb_12,
    _sb_13 as _sb_13,
    _sb_14 as _sb_14,
    _sb_15 as _sb_15,
    _sb_16 as _sb_16,
)
from apps.api.snapshot_parts.etapes_3 import (  # noqa: E402, F401 — ré-export
    _sb_17 as _sb_17,
    _sb_18 as _sb_18,
    _sb_19 as _sb_19,
    _sb_20 as _sb_20,
    _sb_21 as _sb_21,
    _sb_22 as _sb_22,
    _sb_23 as _sb_23,
    _sb_24 as _sb_24,
)
from apps.api.snapshot_parts.etapes_4 import (  # noqa: E402, F401 — ré-export
    _sb_25 as _sb_25,
    _sb_26 as _sb_26,
    _sb_27 as _sb_27,
    _sb_28 as _sb_28,
    _sb_29 as _sb_29,
    _sb_30 as _sb_30,
    _sb_31 as _sb_31,
    _sb_32 as _sb_32,
)
from apps.api.snapshot_parts.etapes_5 import (  # noqa: E402, F401 — ré-export
    _sb_33 as _sb_33,
    _sb_34 as _sb_34,
    _sb_35 as _sb_35,
    _sb_36 as _sb_36,
    _sb_37 as _sb_37,
    _sb_38 as _sb_38,
    _sb_39 as _sb_39,
)


def build_snapshot(seed: int = 7) -> dict:
    # Étapes extraites telles quelles (ADR-0220) : chacune lit ses entrées dans `sb`
    # et y écrit ses sorties ; l'ordre ci-dessous est l'ordre d'origine.
    from types import SimpleNamespace
    sb = SimpleNamespace(seed=seed)
    for etape in (_sb_01, _sb_02, _sb_03, _sb_04, _sb_05, _sb_06, _sb_07, _sb_08,
                  _sb_09, _sb_10, _sb_11, _sb_12, _sb_13, _sb_14, _sb_15, _sb_16,
                  _sb_17, _sb_18, _sb_19, _sb_20, _sb_21, _sb_22, _sb_23):
        etape(sb)
    # NEWS RECENTRÉES SUR TON PORTEFEUILLE : on reconstruit les lignes de sentiment à partir des
    # positions RÉELLES (Alpaca + Bitmart) + de l'allocation PRESET (production), pas du modèle legacy
    # → les actualités collent enfin à ce que tu détiens réellement.
    try:
        _sb_24(sb)
    except Exception:  # noqa: BLE001
        pass
    for etape in (_sb_25, _sb_26, _sb_27, _sb_28, _sb_29, _sb_30):
        etape(sb)
    if sb._pe.get("available") and sb._preset_alloc:
        try:
            for etape in (_sb_31, _sb_32, _sb_33):
                etape(sb)
        except Exception:  # noqa: BLE001 — au moindre souci, on garde l'analyse swing (jamais de page cassée)
            pass
    for etape in (_sb_34, _sb_35, _sb_36, _sb_37, _sb_38, _sb_39):
        etape(sb)
    return sb._payload
