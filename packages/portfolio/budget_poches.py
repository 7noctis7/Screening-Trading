"""Budget DÉCLARÉ des deux poches du compte : actions (+ cœur indiciel) et crypto (QML-023).

AVANT. Les deux poches étaient calculées indépendamment — chacune comme si elle disposait de
tout le compte — puis routées sur le même capital Alpaca (ère paper, ADR-0029). L'anti-levier
de `run_live._broker_targets` ramenait ensuite leur somme à 100 %. La part crypto n'était donc
décidée par personne : elle sortait du rapport entre deux cibles de volatilité. Mesuré le
25/09 : « QQQ 50 % » devenait 31 à 42 % du compte, la crypto 25 à 56 %, et une porte de régime
qui réduisait les actions AUGMENTAIT mécaniquement la part crypto.

APRÈS. La crypto reçoit au plus `part` du compte (`QUANT_CRYPTO_PCT`, 15 % par défaut) ; les
actions et le cœur se partagent `1 − part`. Une poche sous-investie (cible de volatilité)
laisse sa part en CASH — elle ne la cède pas à l'autre poche : un budget qui se redistribue
selon la volatilité redevient l'accident qu'on corrige.
"""

from __future__ import annotations

import os

PART_CRYPTO_DEFAUT = 0.15


def part_crypto() -> float:
    """`QUANT_CRYPTO_PCT` borné à [0, 1] ; illisible → défaut (jamais une exception)."""
    brut = os.environ.get("QUANT_CRYPTO_PCT", "")
    try:
        v = float(brut) if brut.strip() else PART_CRYPTO_DEFAUT
    except ValueError:
        return PART_CRYPTO_DEFAUT
    return max(0.0, min(1.0, v))


def negociables(crypto: dict) -> dict:
    """Poids crypto des seules paires que le courtier paper sait trader (`routing.route`).

    Une paire écartée au routage ne doit pas consommer de budget : sinon 15 % du compte
    restent en cash pour une poche vide, et le cœur actions est rogné pour rien."""
    from packages.execution.routing import route
    return {s: w for s, w in (crypto or {}).items() if route(s, "crypto")["tradeable"]}


def repartir(actions: dict, crypto: dict, part: float) -> tuple[dict, dict]:
    """(poids actions, poids crypto) en fraction du COMPTE, somme ≤ 1.

    `actions` : poids du compte (cœur compris). `crypto` : poids DANS la poche (somme ≤ 1).
    Sans poche crypto, ou budget nul, les actions gardent tout le compte."""
    part = max(0.0, min(1.0, float(part)))
    cryptos = {s: w for s, w in (crypto or {}).items() if w > 0}
    if not cryptos or part <= 0.0:
        return dict(actions or {}), {}
    return ({s: w * (1.0 - part) for s, w in (actions or {}).items()},
            {s: w * part for s, w in cryptos.items()})
