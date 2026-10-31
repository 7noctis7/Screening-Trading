"""Univers : graine, univers complet de la base, mode réel, secteurs.

Extrait TEL QUEL de `apps/api/snapshot.py` le 31/10 (règle des 400 lignes par fichier) : le
texte des définitions n'a pas changé. `apps/api/snapshot.py` reste la façade et ré-exporte
chaque nom, donc `from apps.api.snapshot import X` fonctionne comme avant.
"""

from __future__ import annotations

import csv
from datetime import UTC, datetime
from pathlib import Path

from apps.api.sections_data import GICS_MAP as _GICS_MAP
from apps.api.sections_data import SECTOR_DV as _SECTOR_DV
from apps.api.sections_data import THEME_TICKERS as _THEME_TICKERS
from apps.api.snapshot_parts.base import _NETWORK_KINDS, ROOT
from apps.api.snapshot_parts.prix import _price_db_path
from packages.common import load_yaml


def _seed_universe() -> list[dict]:
    """Univers COMPLET dédupliqué (par symbole) à partir des seeds — source unique.

    Ticket #4 (Thiel, micro-marché) : `QUANT_UNIVERSE=/chemin/niche.csv` restreint l'univers à un
    micro-marché choisi (mêmes colonnes que les seeds) → on domine une niche avant de scaler.
    """
    import os
    seen: dict[str, dict] = {}
    custom = os.environ.get("QUANT_UNIVERSE")
    paths = [Path(custom)] if custom and Path(custom).exists() else \
        sorted((ROOT / "data" / "seed").glob("*.csv"))
    for path in paths:
        with path.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                sym = (r.get("symbol") or "").strip()
                if sym and sym not in seen:
                    seen[sym] = {
                        "symbol": sym, "name": r.get("name") or "",
                        "asset_class": (r.get("asset_class") or "equity").strip() or "equity",
                        "venue": r.get("venue") or "", "currency": r.get("currency") or "",
                        "sector": r.get("sector") or "", "source": path.stem,
                    }
    return list(seen.values())


def _db_full_universe() -> list[dict] | None:
    """Univers EXHAUSTIF depuis YAHOO.db (tous les tickers), si la base est branchée."""
    db = _price_db_path()
    if db is None:
        return None
    try:
        from packages.data.providers.db_provider import DBPriceProvider
        rows = DBPriceProvider(db).universe()
    except Exception:  # noqa: BLE001
        return None
    if not rows:
        return None
    out = []
    for r in rows:
        s = r["symbol"]
        su = s.upper()
        ac = ("crypto" if (su.endswith("USDC") or su.endswith("USDT") or "/USD" in su or "-USD" in su)
              else "forex" if ("/" in s and len(s) <= 7 and "USD" in su)
              else "commodity" if "=F" in su
              else "index" if su.startswith("^")
              else "etf" if (r.get("sector") or "").lower() in ("etf", "fund")
              else "equity")
        out.append({"symbol": s, "name": r.get("name", ""), "asset_class": ac,
                    "venue": r.get("venue", ""), "currency": r.get("currency", ""),
                    "sector": r.get("sector", ""), "source": "YAHOO.db"})
    return out


def _universe_section(instruments: list[dict]) -> dict:
    """Vue UNIVERS : sources déclarées (offline/réseau), seeds, répartition par classe."""
    cfg = load_yaml(ROOT / "config" / "universe.yaml")
    src_rows = []
    for s in cfg.get("sources", []):
        kind = s.get("kind")
        src_rows.append({
            "id": s.get("id"), "kind": kind,
            "enabled": bool(s.get("enabled", True)),
            "network": kind in _NETWORK_KINDS,
            "detail": s.get("file") or s.get("url") or "",
        })
    by_class, by_venue = {}, {}
    for r in instruments:
        ac = (str(r.get("asset_class") or "?")).strip() or "?"
        by_class[ac] = by_class.get(ac, 0) + 1
        ven = (str(r.get("venue") or "?")).strip() or "?"
        by_venue[ven] = by_venue.get(ven, 0) + 1
    seeds = []
    for path in sorted((ROOT / "data" / "seed").glob("*.csv")):
        with path.open(encoding="utf-8") as f:
            cnt = sum(1 for _ in csv.DictReader(f))
        seeds.append({"file": path.name, "count": cnt,
                      "as_of": datetime.fromtimestamp(path.stat().st_mtime,
                                                      UTC).isoformat()})
    rows = sorted(instruments, key=lambda r: (r["asset_class"], r["symbol"]))
    # `as_of` répond « de QUAND datent ces données », jamais « quand cette page a été
    # fabriquée ». Ici il publiait `now()` : la liste d'univers se déclarait donc fraîche
    # du jour même quand ses fichiers sources n'avaient pas bougé depuis des mois, et
    # l'inventaire du gate de publication la comptait parmi les blocs à jour. Une
    # fraîcheur affirmée sans être vraie est pire qu'une date ancienne assumée : elle
    # empêche de repérer la source qui a cessé d'être rafraîchie.
    # La date des données = celle du fichier source le plus récent. La date de
    # fabrication garde sa place, sous son propre nom.
    dates_seed = [s["as_of"] for s in seeds if s.get("as_of")]
    return {
        "as_of": max(dates_seed) if dates_seed else None,
        "genere_le": datetime.now(UTC).isoformat(),
        "rebuild_cadence_days": cfg.get("rebuild_cadence_days"),
        "sources": src_rows,
        "sources_enabled": sum(1 for s in src_rows if s["enabled"]),
        "sources_total": len(src_rows),
        "seeds": seeds,
        "seed_total": len(instruments),
        "by_asset_class": dict(sorted(by_class.items(), key=lambda kv: -kv[1])),
        "by_venue": dict(sorted(by_venue.items(), key=lambda kv: -kv[1])[:12]),
        "instruments": rows,                  # UNIVERS COMPLET (pas un échantillon)
        "instruments_total": len(rows),
    }


def is_real_mode(mode: str | None) -> bool:
    """Le chargement des prix tourne-t-il sur des données RÉELLES (pas de repli synthétique) ?

    `_load_prices` renvoie un libellé LISIBLE (« réel (YAHOO.db) », « mixte (...) »,
    « synthetic »), jamais la chaîne « real ». Trois gardes comparaient pourtant `mode == "real"` :
    elles étaient donc TOUJOURS fausses, et silencieusement — le nettoyage des titres périmés,
    l'audit PwC du snapshot et son rapport d'affichage ne s'exécutaient jamais en production.
    Une comparaison de chaînes n'est pas un contrat ; ce prédicat en est un, et il est testé.
    """
    return bool(mode) and str(mode).startswith("réel")


def contient_des_prix_reels(mode: str | None) -> bool:
    """Y a-t-il des horodatages RÉELS exploitables ? — question distincte de la certification.

    `is_real_mode` répond à « tout l'univers est-il certifié réel ? » et refuse « mixte » à
    juste titre : un seul titre en repli synthétique interdit de certifier l'ensemble. Mais
    le NETTOYAGE DES TITRES PÉRIMÉS ne pose pas cette question-là. Il demande seulement si
    les dernières barres sont de vraies dates comparables entre elles.

    Le 07/09, faire porter les deux questions par le même prédicat a coûté cher : le VPS
    tourne en mode « mixte », le nettoyage ne s'exécutait donc JAMAIS, et des titres arrêtés
    depuis des mois (BK au 18 juin, CA au 26 mai) restaient dans l'univers. Pire, comme les
    séries sont alignées par intersection, un seul de ces morts tronquait la fenêtre de
    calcul de TOUT le portefeuille — la recommandation du jour finissait au 17 juin sans que
    rien ne le signale.
    """
    return bool(mode) and not str(mode).startswith("synthetic")


# « ETF » et « Indices » ne sont pas des secteurs, ce sont des VÉHICULES : `_sector_of`
# les renvoie sur la classe d'actif, avant même de regarder le GICS. Leur appliquer le
# plafond SECTORIEL refait, un cran plus haut, l'erreur que `index_names` corrige sur
# l'axe des noms — mesuré le 09/09 : « nom QQQ 50 % » réparé le matin, « secteur ETF
# 50 % » apparu dans le post-mortem du soir, même actif, même poids, autre libellé.
# Forex/Commodités/Crypto n'y sont PAS : là, 40 % sur une classe est une vraie limite.
_SECTEURS_VEHICULE = frozenset({"ETF", "Indices"})
# Le seau de DERNIER RECOURS de `_sector_of` : une ACTION au champ `sector` vide ou
# hors GICS y tombe. Le nommer ici permet aux limites de dire « secteur inconnu » au
# lieu de « concentration sectorielle » — ce qui envoie chercher au bon endroit :
# le champ `sector` à peupler, pas une allocation à corriger.
_SECTEUR_INCONNU = "Actions diverses"


def _sector_of(m: dict) -> str:
    """Secteur/thème d'un instrument (cohérent entre génération de données et heatmap)."""
    ac = m.get("asset_class")
    if ac == "crypto":
        return "Crypto & Blockchain"
    if ac == "forex":
        return "Forex"
    if ac == "commodity":
        return "Commodités"
    if ac == "index":
        return "Indices"
    if ac == "etf":
        return "ETF"
    if m["symbol"] in _THEME_TICKERS:
        return _THEME_TICKERS[m["symbol"]]
    sec = (m.get("sector") or "").strip()
    if sec in _SECTOR_DV:
        return sec
    return _GICS_MAP.get(sec, "Actions diverses")


def _setup_label(mom: float, trend: float) -> str:
    if mom > 0.05 and trend > 0.02:
        return "tendance haussière confirmée"
    if mom > 0.05 and trend <= 0.02:
        return "momentum naissant"
    if mom < -0.05 and trend < -0.02:
        return "tendance baissière"
    if trend > 0.02 and mom <= 0.05:
        return "rebond au-dessus de la MM50"
    return "neutre / range"
