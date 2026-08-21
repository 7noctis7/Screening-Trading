"""Impact de marché NON LINÉAIRE (loi en racine carrée) + test d'admission d'un signal.

`costs.py` modélise le coût comme un forfait en bps : linéaire en notionnel, aveugle à la
taille et à la volatilité. C'est faux dès qu'on trade plus de ~1 % de l'ADV, et c'est le
piège n°1 des robots à haute rotation (1 h / 4 h) : l'alpha estimé y est de l'ordre de
quelques bps, exactement l'ordre de grandeur du coût qu'on ignore.

Modèle retenu (Almgren-Chriss / Torre-BARRA, consensus buy-side) :

  impact_bps = Y · sigma_bucket_bps · (Q / V_bucket) ** psi        (psi ≈ 0,5)
  coût_total_bps = demi_spread_bps + frais_bps + impact_bps

- `sigma_bucket` = volatilité sur l'HORIZON D'EXÉCUTION, pas la vol annuelle :
  sigma_bucket = sigma_daily · √(minutes_bucket / minutes_séance).
- `V_bucket` = volume échangeable pendant l'exécution (ADV pour une journée, ADV × part
  du bucket pour 1 h / 4 h) — jamais l'ADV entier sur une barre horaire.
- Y ≈ 0,5–1,0 (actions liquides). Défaut prudent 0,8, à RECALIBRER sur le TCA réel
  (`packages/execution/tca.py` + `packages/research/exec_costs.py`).

Fonctions pures (stdlib), testables hors-ligne.
"""

from __future__ import annotations

MINUTES_PER_SESSION = 390.0        # séance actions US (6 h 30)
MINUTES_PER_DAY_CRYPTO = 1440.0    # crypto : 24/24


def bucket_sigma_bps(sigma_daily: float, minutes: float,
                     session_minutes: float = MINUTES_PER_SESSION) -> float:
    """Volatilité sur la fenêtre d'exécution, en bps (racine du temps)."""
    if sigma_daily <= 0 or minutes <= 0 or session_minutes <= 0:
        return 0.0
    return float(sigma_daily * (minutes / session_minutes) ** 0.5 * 1e4)


def bucket_volume(adv_shares: float, minutes: float,
                  session_minutes: float = MINUTES_PER_SESSION) -> float:
    """Volume attendu sur la fenêtre (profil plat — prudent ; U-shape = raffinement)."""
    if adv_shares <= 0 or minutes <= 0 or session_minutes <= 0:
        return 0.0
    return float(adv_shares * min(1.0, minutes / session_minutes))


def square_root_impact_bps(qty: float, venue_volume: float, sigma_bps: float,
                           y: float = 0.8, psi: float = 0.5) -> float:
    """Impact temporaire en bps. `venue_volume` = volume DE LA FENÊTRE, pas l'ADV brut."""
    if qty <= 0 or venue_volume <= 0 or sigma_bps <= 0:
        return 0.0
    part = min(1.0, qty / venue_volume)          # participation bornée à 100 %
    return float(y * sigma_bps * part ** psi)


def total_cost_bps(qty: float, adv_shares: float, sigma_daily: float,
                   spread_bps: float, fee_bps: float, minutes: float = MINUTES_PER_SESSION,
                   session_minutes: float = MINUTES_PER_SESSION, y: float = 0.8) -> dict:
    """Coût ALLER complet d'un ordre : demi-spread + frais + impact racine carrée."""
    sig = bucket_sigma_bps(sigma_daily, minutes, session_minutes)
    vol = bucket_volume(adv_shares, minutes, session_minutes)
    impact = square_root_impact_bps(qty, vol, sig, y=y)
    half_spread = max(0.0, spread_bps) / 2.0
    total = half_spread + max(0.0, fee_bps) + impact
    return {"total_bps": round(total, 3), "impact_bps": round(impact, 3),
            "half_spread_bps": round(half_spread, 3), "fee_bps": round(float(fee_bps), 3),
            "participation": round(qty / vol, 4) if vol > 0 else None,
            "sigma_bucket_bps": round(sig, 2), "bucket_volume": round(vol, 1)}


def max_qty_for_budget(budget_bps: float, adv_shares: float, sigma_daily: float,
                       spread_bps: float, fee_bps: float,
                       minutes: float = MINUTES_PER_SESSION,
                       session_minutes: float = MINUTES_PER_SESSION,
                       y: float = 0.8) -> float:
    """Taille MAXIMALE dont le coût total reste sous `budget_bps` (inversion de la racine).

    Q* = V_bucket · ((budget − demi_spread − frais) / (Y · sigma_bucket))²
    Renvoie 0 si le budget ne couvre même pas spread + frais (⇒ ne pas trader).
    """
    sig = bucket_sigma_bps(sigma_daily, minutes, session_minutes)
    vol = bucket_volume(adv_shares, minutes, session_minutes)
    room = budget_bps - max(0.0, spread_bps) / 2.0 - max(0.0, fee_bps)
    if room <= 0 or sig <= 0 or vol <= 0 or y <= 0:
        return 0.0
    return float(vol * (room / (y * sig)) ** 2)


def participation_cap(adv_shares: float, minutes: float = MINUTES_PER_SESSION,
                      pov: float = 0.10,
                      session_minutes: float = MINUTES_PER_SESSION) -> float:
    """Plafond de participation (POV) — contrainte DURE, indépendante du budget de coût."""
    return float(max(0.0, pov) * bucket_volume(adv_shares, minutes, session_minutes))


def admit_signal(alpha_bps: float, cost_bps: float, k: float = 2.0) -> dict:
    """Admission : l'alpha attendu sur l'horizon doit dominer le coût ALLER-RETOUR × k.

    k = marge de sécurité (2 = l'alpha doit doubler le coût). Sous k = 1 on trade
    l'espérance nulle de Bachelier en payant le spread : ruine lente et certaine.
    """
    rt = 2.0 * max(0.0, cost_bps)
    ok = alpha_bps > k * rt
    return {"admitted": bool(ok), "alpha_bps": round(float(alpha_bps), 3),
            "round_trip_bps": round(rt, 3), "hurdle_bps": round(k * rt, 3),
            "edge_after_cost_bps": round(float(alpha_bps) - rt, 3),
            "reason": "" if ok else f"alpha {alpha_bps:.2f} bps ≤ seuil {k * rt:.2f} bps"}


def no_trade_band(cost_bps: float, alpha_bps: float, kappa: float = 0.10) -> float:
    """Largeur de bande de non-trading, FORME en racine cubique (Constantinides ;
    Garleanu-Pedersen) : band ∝ (coût / alpha)^(1/3).

    Sous cette dérive de poids, rebalancer détruit plus de valeur que de suivre la cible.
    ⚠️ `kappa` est une CONSTANTE D'ÉCHELLE À CALIBRER sur le portefeuille réel (aversion
    au risque × variance) : seule la FORME est théorique, le niveau ne l'est pas. Le
    défaut 0,10 est un placeholder explicite, pas une recommandation calibrée.
    """
    if alpha_bps <= 0 or cost_bps <= 0 or kappa <= 0:
        return 0.0
    return float(min(0.5, kappa * (cost_bps / alpha_bps) ** (1.0 / 3.0)))
