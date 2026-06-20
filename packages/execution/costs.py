"""Modèle de coûts réalistes : frais (bps) + slippage (bps). Dès le backtest."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CostModel:
    fee_bps: float = 5.0       # commission
    slippage_bps: float = 2.0  # impact/spread

    def apply_buy(self, price: float) -> float:
        return price * (1 + self.slippage_bps / 1e4)

    def apply_sell(self, price: float) -> float:
        return price * (1 - self.slippage_bps / 1e4)

    def fee(self, notional: float) -> float:
        return abs(notional) * self.fee_bps / 1e4

    @property
    def round_trip_bps(self) -> float:
        """Coût aller-retour estimé (2× frais + 2× slippage), en points de base."""
        return 2 * (self.fee_bps + self.slippage_bps)

    @classmethod
    def for_asset_class(cls, asset_class: str) -> "CostModel":
        """Coûts calibrés par classe d'actifs (frais + spread/impact réalistes).

        Actions/ETF liquides ≈ faibles ; crypto/forex spreads plus larges ; commodités/indices
        via futures intermédiaires. Valeurs prudentes (retail), surchargeable par config.
        """
        return cls(**_COST_BY_CLASS.get((asset_class or "equity").lower(), _COST_BY_CLASS["equity"]))


# Hypothèses de coûts (bps) par classe — prudentes, pour un compte retail.
_COST_BY_CLASS: dict[str, dict[str, float]] = {
    "equity": {"fee_bps": 2.0, "slippage_bps": 3.0},
    "etf": {"fee_bps": 1.5, "slippage_bps": 2.0},
    "crypto": {"fee_bps": 10.0, "slippage_bps": 15.0},
    "forex": {"fee_bps": 1.0, "slippage_bps": 4.0},
    "commodity": {"fee_bps": 3.0, "slippage_bps": 6.0},
    "index": {"fee_bps": 2.0, "slippage_bps": 4.0},
}


# --- Barèmes RÉELS des courtiers (≈ 2024-2026), en points de base (1 bp = 0,01 %) ---
# commission = frais courtier par exécution ; slippage = demi-spread + impact marché (estimé, sur des
# valeurs liquides / paires majeures). Sources : grilles publiques Alpaca, IBKR, Binance, BitMart.
BROKER_FEES: dict[str, dict[str, float]] = {
    # ACTIONS / ETF US
    "alpaca": {"commission_bps": 0.0, "slippage_bps": 2.0},    # 0 $ commission (frais SEC/TAF ~0,1 bp négligés) + spread serré
    "ibkr": {"commission_bps": 0.5, "slippage_bps": 2.0},      # Pro fixe 0,005 $/action (min 1 $) ≈ 0,5 bp sur large-caps
    # CRYPTO SPOT
    "binance": {"commission_bps": 10.0, "slippage_bps": 6.0},  # 0,10 % taker (0,075 % avec BNB) + spread majors
    "bitmart": {"commission_bps": 25.0, "slippage_bps": 10.0}, # 0,25 % taker ; liquidité moindre → slippage +
}
# Courtier par défaut par classe = TES comptes réels (actions→Alpaca, crypto→BitMart).
# Surchargeable : QUANT_BROKER_EQUITY (alpaca|ibkr) / QUANT_BROKER_CRYPTO (bitmart|binance).
_DEFAULT_BROKER: dict[str, str] = {"equity": "alpaca", "etf": "alpaca", "index": "alpaca",
                                   "crypto": "bitmart", "forex": "ibkr", "commodity": "ibkr"}


def broker_for(asset_class: str) -> str:
    """Courtier retenu pour une classe d'actifs (défaut = comptes réels, surchargeable par env)."""
    import os
    ac = (asset_class or "equity").lower()
    if ac == "crypto":
        return os.environ.get("QUANT_BROKER_CRYPTO", _DEFAULT_BROKER["crypto"]).lower()
    return os.environ.get("QUANT_BROKER_EQUITY", _DEFAULT_BROKER.get(ac, "alpaca")).lower()


def broker_cost_bps(asset_class: str) -> float:
    """Coût ALLER-SIMPLE (commission + slippage) en bps pour la classe, selon le courtier réel.
    C'est ce qu'on déduit du cash à CHAQUE exécution du backtest (achat ou vente)."""
    b = BROKER_FEES.get(broker_for(asset_class), BROKER_FEES["alpaca"])
    return float(b["commission_bps"] + b["slippage_bps"])


def broker_assumptions() -> list[dict]:
    """Table des barèmes courtiers (pour transparence UI / TCA)."""
    return [{"broker": k, **v, "round_trip_bps": 2 * (v["commission_bps"] + v["slippage_bps"])}
            for k, v in BROKER_FEES.items()]


def market_impact_bps(notional: float, adv_usd: float, coef: float = 10.0) -> float:
    """Impact de marché NON-LINÉAIRE (loi en racine carrée, Almgren) : coef·√(notional/ADV), en bps.

    Doubler la taille ne double pas l'impact, il croît en √. coef≈10 bps pour 100 % d'ADV (prudent).
    """
    if adv_usd <= 0 or notional <= 0:
        return 0.0
    return coef * (abs(notional) / adv_usd) ** 0.5


def stochastic_slippage_bps(base_slippage_bps: float, vol_ratio: float = 1.0,
                            beta: float = 1.5, cap: float = 8.0) -> float:
    """Slippage STOCHASTIQUE conditionnel à la volatilité du carnet (Griffin : le spread explose
    sur un choc d'actualité). slippage = base · (1 + β·max(0, vol_ratio − 1)), borné par `cap`×base.

    vol_ratio = vol réalisée récente / vol normale (≈ VIX/VIX_médian). En régime calme vol_ratio≈1
    → slippage = base ; sur un pic de news vol_ratio=3 → slippage ≈ base·(1+β·2).
    """
    mult = 1.0 + beta * max(0.0, vol_ratio - 1.0)
    return base_slippage_bps * min(cap, mult)


def cost_assumptions() -> list[dict]:
    """Table des hypothèses de coûts par classe (pour affichage UI / transparence TCA)."""
    return [{"asset_class": ac, "fee_bps": v["fee_bps"], "slippage_bps": v["slippage_bps"],
             "round_trip_bps": 2 * (v["fee_bps"] + v["slippage_bps"])}
            for ac, v in _COST_BY_CLASS.items()]
