"""Livre de comptes parts/cash du ledger — écritures d'achat/vente avec PRU et frais.

Extrait de `preset_backtest.py` le 25/08 (règle < 400 lignes/fichier). L'ORDRE des
écritures est significatif : le P&L latent est attribué en FIFO sur la liste `trades`,
donc cœur avant satellite à chaque rééquilibrage, comme dans la version d'origine.
"""

from __future__ import annotations

import os

from packages.execution.costs import broker_fee

SEUIL_TRADE = 0.004        # variation < max(0,4 % de l'equity, 1 $) → pas de trade


class Livre:
    """Cash, parts, PRU et frais — une écriture par exécution."""

    def __init__(self, init_cap: float, universe: list, acmap: dict) -> None:
        self.cash = float(init_cap)
        self.shares = {s: 0.0 for s in universe}
        self.cost = {s: 0.0 for s in universe}       # PRU (coût moyen pondéré)
        self.acmap = acmap
        self.fees_on = os.environ.get("QUANT_FEES", "1") != "0"
        self.fees_paid = 0.0
        self.realized = 0.0
        self.qsh = self.qcost = 0.0                  # cœur indiciel
        self.ouvert_depuis: dict[str, str] = {}      # symbole → date d'ouverture de la ligne
        self.trades: list[dict] = []

    def frais(self, sym: str, notional: float, side: str = "BUY") -> float:
        """Coût RÉEL de l'exécution ($) — commission + slippage, désactivable via QUANT_FEES=0."""
        return (broker_fee(self.acmap.get(sym, "equity"), notional, side)
                if self.fees_on else 0.0)

    def achat(self, sym: str, date: str, price: float, d_val: float, coeur: bool = False) -> None:
        """ACHAT : met à jour PRU, parts et cash, puis journalise."""
        dq = d_val / price
        anciennes = self.qsh if coeur else self.shares[sym]
        tot = anciennes + dq
        pru = ((self.qcost if coeur else self.cost[sym]) * anciennes + price * dq) / tot \
            if tot > 0 else price
        fee = self.frais(sym, d_val)
        self.fees_paid += fee
        self.cash -= d_val + fee
        if coeur:
            self.qsh, self.qcost = tot, pru
            motif = "cœur indiciel (rééquilibrage)"
        else:
            self.shares[sym], self.cost[sym] = tot, pru
            ouverture = anciennes <= 1e-9
            if ouverture:
                self.ouvert_depuis[sym] = date   # date d'OUVERTURE de la ligne courante
            motif = ("entrée (univers qualité, risk-parity)" if ouverture
                     else "renforcement (risk-parity)")
        self.trades.append({"date": date, "symbol": sym, "side": "BUY", "qty": round(dq, 4),
                            "price": round(price, 2), "notional": round(d_val, 2),
                            "avg_cost": round(pru, 2), "pnl": None, "pnl_pct": None,
                            "fee": round(fee, 2), "reason": motif})

    def vente(self, sym: str, date: str, price: float, sq: float,
              coeur: bool = False, hors_univers: bool = False) -> None:
        """VENTE : P&L réalisé vs PRU, puis journalise."""
        pru = self.qcost if coeur else self.cost[sym]
        pnl = (price - pru) * sq
        self.realized += pnl
        fee = self.frais(sym, sq * price, "SELL")
        self.fees_paid += fee
        self.cash += sq * price - fee
        if coeur:
            self.qsh -= sq
            motif = "cœur indiciel (allègement)"
        else:
            self.shares[sym] -= sq
            if self.shares[sym] <= 1e-6:
                self.ouvert_depuis.pop(sym, None)   # ligne soldée → l'horloge repart à zéro
            motif = ("sortie (hors univers / blackout)"
                     if (hors_univers or self.shares[sym] <= 1e-6)
                     else "allègement (DD-target/risk-parity)")
        self.trades.append({"date": date, "symbol": sym, "side": "SELL", "qty": round(sq, 4),
                            "price": round(price, 2), "notional": round(sq * price, 2),
                            "avg_cost": round(pru, 2), "pnl": round(pnl, 2),
                            "pnl_pct": round(price / pru - 1, 4) if pru > 0 else None,
                            "fee": round(fee, 2), "reason": motif})

    def equity(self, px, idx: dict, universe: list, core_px: float | None) -> float:
        """Valorisation totale : cash + satellite + cœur."""
        val = sum(self.shares[s] * px[idx[s]] for s in universe)
        return self.cash + val + (self.qsh * core_px if core_px is not None else 0.0)

    def rebalance_coeur(self, sym: str, date: str, cpx: float, cible: float,
                        equity: float) -> None:
        """Rééquilibrage du CŒUR (ex. QQQ) vers `cible` dollars."""
        d_val = float(cible - self.qsh * cpx)
        if cpx <= 0 or abs(d_val) < max(SEUIL_TRADE * equity, 1.0):
            return
        if d_val > 0:
            self.achat(sym, date, cpx, d_val, coeur=True)
        else:
            sq = min(self.qsh, -d_val / cpx)
            if sq > 1e-9:
                self.vente(sym, date, cpx, sq, coeur=True)

    def rebalance_satellite(self, universe: list, date: str, px, nw, sat: float,
                            equity: float) -> None:
        """Rééquilibrage du satellite preset vers les poids `nw` × `sat`."""
        for i, s in enumerate(universe):
            price = float(px[i])
            if price <= 0:
                continue
            d_val = float(nw[i] * sat * equity - self.shares[s] * price)
            if abs(d_val) < max(SEUIL_TRADE * equity, 1.0):   # variation négligeable
                continue
            if d_val > 0:
                self.achat(s, date, price, d_val)
            else:
                sq = min(self.shares[s], -d_val / price)
                if sq > 1e-9:
                    self.vente(s, date, price, sq, hors_univers=bool(nw[i] <= 1e-4))
