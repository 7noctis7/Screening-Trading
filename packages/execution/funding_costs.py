"""Coûts de portage et de financement institutionnels — l'écart entre PnL brut et PnL réel.

Un backtest long-short non financé n'existe pas. Quatre postes manquent presque toujours,
et leur somme dépasse couramment l'alpha revendiqué d'une stratégie à faible Sharpe :

  1. FINANCEMENT DE LA MARGE : la partie longue au-delà des fonds propres est empruntée.
  2. EMPRUNT DE TITRES (short rebate) : le vendeur à découvert emprunte le titre. Le
     rebate versé = taux de référence − frais de prêt. Frais > taux ⇒ rebate NÉGATIF, on
     paie pour être short. Sur un titre difficile à emprunter, 20 %/an est courant.
  3. DIVIDENDES DE LA JAMBE COURTE : décaissés, jamais encaissés.
  4. COÛT D'OPPORTUNITÉ DU CAPITAL IMMOBILISÉ : la marge initiale bloquée ne travaille pas
     au taux de rendement exigé. Ignoré par tous les backtests retail.

Équation de rendement net, en fraction du NAV et sur la période (jours/daycount) :

  r_net = r_brut
        − coûts_de_transaction
        − (L − NAV)+ · r_marge · dt
        + S · (r_ref − frais_emprunt) · dt        (rebate, signe conservé)
        − dividendes_short · dt
        − marge_initiale · (hurdle − r_ref) · dt

Convention retenue : produits de la vente à découvert conservés en garantie (Reg-T), donc
ils ne réduisent PAS la base de financement de la jambe longue. Toute autre convention est
défendable — mais elle doit être ÉCRITE, sinon deux backtests ne sont pas comparables.

stdlib pure.
"""

from __future__ import annotations

BPS = 1e4


def _ann(rate: float, days: float, daycount: float) -> float:
    return float(rate) * float(days) / float(daycount)


def carry_costs(nav: float, long_notional: float, short_notional: float,
                margin_rate: float = 0.055, reference_rate: float = 0.045,
                borrow_fee: float = 0.005, short_dividend_yield: float = 0.0,
                initial_margin: float | None = None, hurdle_rate: float = 0.08,
                days: float = 365.0, daycount: float = 360.0) -> dict:
    """Décomposition du portage sur `days` jours, en fraction du NAV et en bps.

    Args:
        margin_rate: taux débiteur du courtier sur le cash emprunté.
        reference_rate: taux sans risque servi sur les garanties (SOFR/ESTR).
        borrow_fee: frais de prêt du titre vendu à découvert (0,5 % = facile à emprunter,
            au-delà de 5 % = *hard-to-borrow*, au-delà de 20 % = l'edge est mort).
        initial_margin: capital réglementaire bloqué. Défaut = 50 % du brut (Reg-T).
        hurdle_rate: rendement exigé du capital — c'est lui qui rend le blocage COÛTEUX.
    """
    nav = float(nav)
    if nav <= 0:
        return {"available": False}
    L, S = max(0.0, float(long_notional)), max(0.0, float(short_notional))
    gross, net_exp = L + S, L - S
    borrowed = max(0.0, L - nav)
    im = float(initial_margin) if initial_margin is not None else 0.5 * gross

    margin_cost = borrowed * _ann(margin_rate, days, daycount)
    rebate = S * _ann(reference_rate - borrow_fee, days, daycount)   # signe conservé
    div_short = S * _ann(short_dividend_yield, days, daycount)
    capital_cost = max(0.0, im) * _ann(max(0.0, hurdle_rate - reference_rate), days, daycount)
    idle_yield = max(0.0, nav - L) * _ann(reference_rate, days, daycount)

    total = -margin_cost + rebate - div_short - capital_cost + idle_yield
    to_bps = lambda v: round(v / nav * BPS, 2)                        # noqa: E731
    return {"available": True, "days": days,
            "gross_leverage": round(gross / nav, 3),
            "net_exposure": round(net_exp / nav, 3),
            "borrowed": round(borrowed, 2), "initial_margin": round(im, 2),
            "margin_cost_bps": to_bps(-margin_cost),
            "short_rebate_bps": to_bps(rebate),
            "short_dividend_bps": to_bps(-div_short),
            "capital_opportunity_bps": to_bps(-capital_cost),
            "idle_cash_yield_bps": to_bps(idle_yield),
            "total_carry_bps": to_bps(total),
            "hard_to_borrow": bool(borrow_fee > 0.05)}


def net_expected_return(gross_return_bps: float, trading_cost_bps: float,
                        carry_bps: float) -> dict:
    """Rendement NET = brut − transaction + portage (le portage est déjà signé)."""
    net = float(gross_return_bps) - abs(float(trading_cost_bps)) + float(carry_bps)
    return {"gross_bps": round(float(gross_return_bps), 2),
            "trading_cost_bps": round(-abs(float(trading_cost_bps)), 2),
            "carry_bps": round(float(carry_bps), 2),
            "net_bps": round(net, 2), "profitable": bool(net > 0)}


def breakeven_gross_bps(trading_cost_bps: float, carry_bps: float,
                        margin: float = 1.0) -> float:
    """Alpha BRUT minimal pour être à l'équilibre, avec une marge de sécurité multiplicative."""
    return float(margin * (abs(trading_cost_bps) - float(carry_bps)))


def max_borrow_fee(gross_alpha_bps: float, trading_cost_bps: float, short_notional: float,
                   nav: float, reference_rate: float = 0.045, days: float = 365.0,
                   daycount: float = 360.0) -> float | None:
    """Frais d'emprunt AU-DELÀ desquels la paire cesse d'être rentable.

    Le nombre à exiger du courtier AVANT d'ouvrir un short : au-dessus, l'edge appartient
    au prêteur de titres, pas à toi. Ne considère QUE la jambe de financement du short
    (rebate) — ni le rendement du cash oisif, ni le coût du capital bloqué, qui ne
    dépendent pas des frais d'emprunt.

    coût_short = S · (frais − r_ref) · dt  ≤  budget  ⇒  frais ≤ r_ref + budget/(S·dt)
    """
    if short_notional <= 0 or nav <= 0 or days <= 0:
        return None
    budget = (float(gross_alpha_bps) - abs(float(trading_cost_bps))) / BPS * nav
    if budget <= 0:
        return 0.0
    fee = reference_rate + (budget * daycount) / (short_notional * days)
    return float(max(0.0, fee))
