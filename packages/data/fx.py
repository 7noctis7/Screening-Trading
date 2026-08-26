"""Taux de change GRATUITS (yfinance) avec cache disque — best-effort, jamais bloquant.

Sert à convertir les états financiers d'un ADR (devise locale, ex. TWD) dans la devise de son cours
(ex. USD) afin que la valorisation (multiples, DCF) soit cohérente. Hors-ligne / paire inconnue →
renvoie None et l'appelant retombe sur le comportement « valorisation masquée ».

DÉFAUT CORRIGÉ LE 25/08 : le TTL portait sur le FICHIER, pas sur l'entrée. Le cache était un
simple `{paire: valeur}` et `_save` réécrivait tout le fichier — donc récupérer une paire
quelconque remettait le compteur de fraîcheur à zéro pour TOUTES les autres. Une paire peu
utilisée (TWD, par exemple) pouvait ainsi être servie indéfiniment avec un taux de plusieurs
mois, et rien ne permettait de le savoir : le code ne stockait aucun horodatage par entrée, il
ne POUVAIT donc pas distinguer un taux d'une minute d'un taux d'un semestre.

Un taux de change périmé ne fait pas échouer une valorisation, il la fausse silencieusement —
c'est le pire des deux mondes. Chaque entrée porte désormais sa propre date, et `age_heures()`
la rend lisible.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

_CACHE = Path(__file__).resolve().parents[2] / ".cache" / "fx" / "rates.json"
_TTL = 86_400.0     # 24 h : un taux journalier suffit pour une note fondamentale


def _load() -> dict:
    """Cache brut, SANS filtrage d'âge — la fraîcheur se juge entrée par entrée (cf. `rate`)."""
    try:
        if _CACHE.exists():
            d = json.loads(_CACHE.read_text())
            return d if isinstance(d, dict) else {}
    except Exception:  # noqa: BLE001
        pass
    return {}


def _save(d: dict) -> None:
    try:
        _CACHE.parent.mkdir(parents=True, exist_ok=True)
        _CACHE.write_text(json.dumps(d))
    except Exception:  # noqa: BLE001
        pass


def _lire_entree(brut) -> tuple[float, float] | None:
    """(valeur, horodatage) d'une entrée de cache, ou None si inexploitable.

    L'ANCIEN format était une valeur nue, sans date. Une telle entrée est traitée comme
    d'ÂGE INCONNU, donc périmée : on la re-récupère. Lui accorder le bénéfice du doute
    reviendrait à conserver exactement le défaut qu'on corrige."""
    if isinstance(brut, dict):
        try:
            return float(brut["v"]), float(brut["t"])
        except (KeyError, TypeError, ValueError):
            return None
    return None


def age_heures(base: str, quote: str = "USD") -> float | None:
    """Âge du taux en cache, en heures. None si absent ou d'âge inconnu (ancien format).

    Publié pour que l'appelant puisse DIRE qu'il utilise un taux de trois jours plutôt que de
    le supposer frais."""
    e = _lire_entree(_load().get(f"{(base or '').upper().strip()}{(quote or 'USD').upper().strip()}"))
    return round((time.time() - e[1]) / 3600.0, 2) if e else None


def rate(base: str, quote: str = "USD") -> float | None:
    """1 unité de `base` = ? `quote` (ex. rate('TWD','USD') ≈ 0.031).

    None si indisponible, hors-ligne, ou si l'une des deux devises est VIDE.

    Identité si base == quote. Cache disque avec TTL de 24 h **par entrée** ; source yfinance
    `BASEQUOTE=X`."""
    # `quote or "USD"` réécrivait en silence une chaîne vide en « USD » (une chaîne
    # vide est falsy) : rate("TWD", "") renvoyait le taux TWD/USD au lieu de None, et
    # le garde-fou ci-dessous ne voyait jamais le cas. Une devise cible vide n'est pas
    # une demande d'USD, c'est une devise INCONNUE — convertir des comptes à un taux
    # qu'on prétend être celui d'une autre devise fausse la valorisation sans rien
    # signaler. Le défaut USD reste porté par la signature, pour l'appelant qui OMET
    # l'argument.
    base = (base or "").upper().strip()
    quote = (quote or "").upper().strip()
    if not base or not quote:
        return None
    if base == quote:
        return 1.0
    cache = _load()
    key = f"{base}{quote}"
    entree = _lire_entree(cache.get(key))
    if entree is not None and (time.time() - entree[1]) < _TTL:
        return entree[0]
    try:
        import yfinance as yf
        hist = yf.Ticker(f"{base}{quote}=X").history(period="5d")
        if hist is None or getattr(hist, "empty", True):
            return None
        val = float(hist["Close"].dropna().iloc[-1])
        if val > 0:
            cache[key] = {"v": val, "t": time.time()}
            _save(cache)
            return val
    except Exception:  # noqa: BLE001
        return None
    return None
