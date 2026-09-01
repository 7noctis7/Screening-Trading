"""Frictions d'exécution explicites + règle d'inhibition du sur-trading.

SPÉCIFIÉ PAR L'UTILISATEUR (01/09), module 3. Complète `execution/costs.CostModel`, qui
agrège frais et slippage en points de base, par les trois frictions SÉPARÉES que la spec
exige : commission, fourchette bid/ask, glissement en ticks.

POURQUOI SÉPARER CE QUE `CostModel` AGRÈGE. Un aller-retour à 10 bps peut être 10 de
commission ou 10 de spread — même chiffre, décisions opposées. La commission baisse en
tradant moins souvent ; le spread baisse en tradant plus gros et plus liquide. Agrégés,
on ne sait pas lequel attaquer. Le total reste identique : ce module DÉCOMPOSE, il ne
renchérit pas.

LA RÈGLE D'INHIBITION (3.2) est la partie qui rapporte. Sur une stratégie à profit
factor 1,01, la question n'est pas « ce trade est-il bon ? » mais « son espérance
couvre-t-elle trois fois ses frictions ? ». Un signal qui ne passe pas ce test coûte de
l'argent en moyenne, même quand il a raison sur la direction.

STATUT : SHADOW. Aucun appelant en production ; `rebalance_plan` porte déjà la bande
d'inaction active. Le brancher est une décision explicite.
"""

from __future__ import annotations

from dataclasses import dataclass

STATUT = "SHADOW_UNCALIBRATED"
MULTIPLE_INHIBITION = 3.0          # spec : espérance ≥ 3 × frictions


@dataclass(frozen=True)
class Frictions:
    """Frictions d'un aller-retour, en unités NATIVES et non agrégées."""

    commission_pct: float = 0.0005     # 0,05 % du notionnel, À CHAQUE JAMBE
    spread_bps: float = 3.0            # écart bid/ask complet, en points de base
    slippage_ticks: float = 1.0        # glissement défavorable sur ordre au marché
    tick: float = 0.01

    def __post_init__(self) -> None:
        for nom, v in (("commission_pct", self.commission_pct),
                       ("spread_bps", self.spread_bps),
                       ("slippage_ticks", self.slippage_ticks), ("tick", self.tick)):
            if v < 0:
                raise ValueError(f"{nom} négatif : une friction ne rapporte pas")
        if self.tick <= 0:
            raise ValueError("tick doit être > 0")

    def prix_execute(self, prix_mid: float, achat: bool) -> float:
        """Prix réellement obtenu : demi-spread + glissement, TOUJOURS défavorable.

        Un achat paie l'ask (mid + demi-spread) puis glisse encore vers le haut ; une
        vente touche le bid et glisse vers le bas. Modéliser le glissement comme
        symétrique — parfois favorable — est l'erreur qui rend un backtest optimiste.
        """
        p = max(0.0, float(prix_mid))
        demi = p * (self.spread_bps / 2.0) / 1e4
        gliss = self.slippage_ticks * self.tick
        return p + demi + gliss if achat else max(0.0, p - demi - gliss)

    def cout_jambe(self, notionnel: float, prix_mid: float) -> float:
        """Coût en devise d'UNE jambe : commission + demi-spread + glissement."""
        n = max(0.0, float(notionnel))
        p = max(1e-12, float(prix_mid))
        qte = n / p
        return (n * self.commission_pct
                + n * (self.spread_bps / 2.0) / 1e4
                + qte * self.slippage_ticks * self.tick)

    def cout_aller_retour(self, notionnel: float, prix_mid: float) -> float:
        """Entrée + sortie. C'est ce chiffre que l'espérance doit battre."""
        return 2.0 * self.cout_jambe(notionnel, prix_mid)

    def detail(self, notionnel: float, prix_mid: float) -> dict:
        """Décomposition — pour savoir QUELLE friction attaquer."""
        n, p = max(0.0, float(notionnel)), max(1e-12, float(prix_mid))
        qte = n / p
        com = 2.0 * n * self.commission_pct
        spr = 2.0 * n * (self.spread_bps / 2.0) / 1e4
        gli = 2.0 * qte * self.slippage_ticks * self.tick
        total = com + spr + gli
        return {"statut": STATUT, "commission": round(com, 4), "spread": round(spr, 4),
                "slippage": round(gli, 4), "total": round(total, 4),
                "bps_du_notionnel": round(total / n * 1e4, 2) if n > 0 else None}


def signal_inhibe(gain_attendu: float, notionnel: float, prix_mid: float,
                  frictions: Frictions, multiple: float = MULTIPLE_INHIBITION) -> dict:
    """Le signal doit-il être ANNULÉ faute de marge sur ses frictions ?

    `gain_attendu` est en DEVISE et déjà net de probabilité — c'est une espérance, pas
    un objectif. Passer un objectif brut ferait passer le test à tout signal ayant une
    cible lointaine, quelle que soit sa probabilité de l'atteindre.
    """
    cout = frictions.cout_aller_retour(notionnel, prix_mid)
    seuil = multiple * cout
    g = float(gain_attendu)
    inhibe = g < seuil
    return {
        "statut": STATUT, "inhibe": inhibe,
        "gain_attendu": round(g, 4), "cout_aller_retour": round(cout, 4),
        "seuil": round(seuil, 4),
        "ratio": round(g / cout, 2) if cout > 0 else None,
        "motif": (f"espérance {g:.2f} < {multiple:g}× frictions ({seuil:.2f}) — "
                  "trader ce signal coûte de l'argent en moyenne" if inhibe else ""),
    }
