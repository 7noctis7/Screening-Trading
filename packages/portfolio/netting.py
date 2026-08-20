"""Netting Core/Satellite — empêcher les poches de se cannibaliser.

Le système fait coexister une poche **Core** (DCA / buy & hold, horizon mensuel) et une
poche **Satellite** (swing tactique long/short, horizon 1 h à hebdomadaire). Rien
n'empêche aujourd'hui le Satellite de vendre à découvert un sous-jacent que le Core
accumule : on paie deux spreads, un coût d'emprunt et un impact de marché… pour se
retrouver plat. C'est une perte sèche, invisible dans l'attribution par poche.

Trois notions à ne jamais confondre :
  - exposition **nette**  = ce qui porte le risque de marché ;
  - exposition **brute**  = ce qui porte le financement, la marge et le coût d'emprunt ;
  - exposition **exécutée** = ce qu'on envoie réellement au broker, après netting.

Principe retenu : **exécuter le net, attribuer le brut.** Les poches gardent des livres
VIRTUELS pour l'attribution de performance ; le broker ne voit que la position nette. Sans
les livres virtuels, netter détruit la capacité à répondre à « le Satellite gagne-t-il de
l'argent ? » — c'est le prix caché du netting, et il se paie en instrumentation.

Poids exprimés en fraction du NAV, signés (négatif = short). stdlib + numpy.
"""

from __future__ import annotations

POLICIES = ("net", "core_priority", "block")


def net_exposures(sleeves: dict[str, dict[str, float]]) -> dict:
    """Par instrument : détail par poche, exposition nette et brute."""
    par_instrument: dict[str, dict[str, float]] = {}
    for sleeve, poids in (sleeves or {}).items():
        for sym, w in (poids or {}).items():
            par_instrument.setdefault(sym, {})[sleeve] = float(w)
    out = {}
    for sym, d in par_instrument.items():
        vals = list(d.values())
        out[sym] = {"par_poche": d,
                    "net": round(sum(vals), 6),
                    "brut": round(sum(abs(v) for v in vals), 6),
                    "oppose": bool(any(v > 0 for v in vals) and any(v < 0 for v in vals))}
    net_total = sum(v["net"] for v in out.values())
    brut_total = sum(v["brut"] for v in out.values())
    return {"instruments": out, "net_total": round(net_total, 6),
            "brut_total": round(brut_total, 6),
            "netting_ratio": round(brut_total / abs(net_total), 3) if net_total else None}


def conflicts(sleeves: dict[str, dict[str, float]], cost_bps: float = 10.0,
              min_overlap: float = 1e-4) -> dict:
    """Instruments où des poches se neutralisent, et coût ALLER-RETOUR de ce gaspillage.

    Le chevauchement est le minimum entre la somme des longs et celle des shorts : c'est la
    part qui s'annule. Elle coûte deux fois le coût aller (on l'achète ET on la vend) sans
    porter le moindre risque, donc sans espérance de gain.
    """
    expo = net_exposures(sleeves)["instruments"]
    lignes = []
    gaspillage = 0.0
    for sym, d in expo.items():
        vals = list(d["par_poche"].values())
        longs = sum(v for v in vals if v > 0)
        shorts = -sum(v for v in vals if v < 0)
        overlap = min(longs, shorts)
        if overlap <= min_overlap:
            continue
        cout = 2.0 * overlap * cost_bps
        gaspillage += cout
        lignes.append({"symbole": sym, "overlap": round(overlap, 6),
                       "net": d["net"], "brut": d["brut"],
                       "cout_bps_du_nav": round(cout, 3),
                       "poches": dict(d["par_poche"])})
    lignes.sort(key=lambda r: -r["cout_bps_du_nav"])
    return {"n_conflits": len(lignes), "conflits": lignes,
            "cout_total_bps": round(gaspillage, 3),
            "propre": len(lignes) == 0}


def resolve(sleeves: dict[str, dict[str, float]], policy: str = "net",
            core_sleeve: str = "core", cost_bps: float = 10.0) -> dict:
    """Applique une politique de netting. Renvoie l'ordre EXÉCUTABLE + les livres virtuels.

    - `net`           : on exécute la somme algébrique. Le moins cher, mais la position
                        réelle ne reflète plus aucune poche : l'attribution DOIT passer par
                        les livres virtuels renvoyés ici.
    - `core_priority` : le Core est intouchable ; un short Satellite est écrêté pour ne
                        jamais faire passer le net sous zéro sur une ligne détenue en Core.
                        C'est la politique par défaut d'un mandat long-only avec satellite.
    - `block`         : tout ordre Satellite en conflit avec le Core est REFUSÉ et signalé.
                        Le plus strict, le plus lisible en audit.
    """
    if policy not in POLICIES:
        raise ValueError(f"policy inconnue : {policy} (attendu {POLICIES})")
    detail = conflicts(sleeves, cost_bps=cost_bps)
    expo = net_exposures(sleeves)["instruments"]
    executable: dict[str, float] = {}
    ajustements: list[dict] = []
    for sym, d in expo.items():
        poches = d["par_poche"]
        net = d["net"]
        if policy == "net" or not d["oppose"]:
            executable[sym] = round(net, 6)
            continue
        core = float(poches.get(core_sleeve, 0.0))
        autres = net - core
        if policy == "core_priority":
            cible = core + autres
            if core > 0 and cible < 0:                       # le satellite ne peut pas
                cible = 0.0                                  # retourner une ligne du Core
                ajustements.append({"symbole": sym, "action": "short écrêté à plat",
                                    "demande": round(net, 6), "retenu": 0.0})
            executable[sym] = round(cible, 6)
        else:                                                # block
            if core != 0 and autres != 0 and (core > 0) != (autres > 0):
                executable[sym] = round(core, 6)
                ajustements.append({"symbole": sym, "action": "ordre satellite refusé",
                                    "demande": round(net, 6), "retenu": round(core, 6)})
            else:
                executable[sym] = round(net, 6)
    return {"policy": policy, "executable": executable,
            "livres_virtuels": {s: dict(w) for s, w in (sleeves or {}).items()},
            "conflits": detail, "ajustements": ajustements,
            "economie_bps": detail["cout_total_bps"] if policy == "net" else 0.0,
            "note": ("attribution par poche = livres virtuels, PAS les positions broker"
                     if policy == "net" else "positions broker alignées sur les poches")}


def orders_from_targets(current: dict[str, float], target: dict[str, float],
                        band: float = 0.0, nav: float = 1.0) -> dict:
    """Ordres à envoyer = cible − courant, après bande de non-trading. Jamais d'auto-croisement.

    Un même instrument ne peut produire qu'UN ordre par cycle : envoyer un achat et une vente
    sur la même ligne, c'est se croiser soi-même et payer deux fois le spread pour rien.
    """
    syms = set(current or {}) | set(target or {})
    ordres = {}
    ignores = []
    for s in sorted(syms):
        delta = float((target or {}).get(s, 0.0)) - float((current or {}).get(s, 0.0))
        if abs(delta) <= band:
            if delta != 0.0:
                ignores.append({"symbole": s, "delta": round(delta, 6), "raison": "bande"})
            continue
        ordres[s] = round(delta, 6)
    turnover = sum(abs(v) for v in ordres.values())
    return {"ordres": ordres, "n_ordres": len(ordres), "ignores": ignores,
            "turnover": round(turnover, 6),
            "notional": round(turnover * float(nav), 2)}


def attribution(virtual_books: dict[str, dict[str, float]],
                returns: dict[str, float]) -> dict:
    """Attribution de performance PAR POCHE depuis les livres virtuels.

    C'est ce qui permet de répondre à « le rendement vient-il du bêta passif du Core ou de
    l'alpha du Satellite ? » alors même que le broker n'a jamais vu les poches séparément.
    """
    out = {}
    total = 0.0
    for sleeve, poids in (virtual_books or {}).items():
        contrib = sum(float(w) * float(returns.get(s, 0.0)) for s, w in (poids or {}).items())
        out[sleeve] = round(contrib, 6)
        total += contrib
    return {"par_poche": out, "total": round(total, 6),
            "part": {k: (round(v / total, 4) if total else None) for k, v in out.items()}}
