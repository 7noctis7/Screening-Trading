"""Garde-fous d'un passage : doublon du jour, cadence, disjoncteur, kill-switch total,
compte-rendu, equity du jour.

Extrait de `scripts/run_live.py` (audit du 06/10). Chacun publie son compteur au
témoin (`garde_fous.Collecteur`) ; aucun ne lève — un garde-fou en panne le DIT et
laisse passer, il ne gèle pas le robot sur sa propre erreur.
"""

from __future__ import annotations

from packages.common.journal_passage import dire


def deja_rebalance_aujourdhui(brokers: tuple, obs=None) -> bool:
    """Le COURTIER dit s'il a déjà tradé aujourd'hui — pas l'horloge, pas un fichier.

    La question est posée au seul endroit que le VPS, le Mac, GitHub Actions et la main
    humaine ont en commun : le compte. Un verrou sur disque ne verrouillerait que la
    machine qui le porte, et c'est justement la mauvaise granularité — cf.
    `packages/execution/garde_journaliere`.
    """
    from packages.execution.garde_fous import (
        ACTIVE,
        DESARME,
        GARDE_JOUR,
        UNCALIBRATED,
        noter,
    )
    from packages.execution.garde_journaliere import evaluer, message
    fills: list[dict] = []
    for bname, br, _cap, _cur in brokers:
        if br is None:
            continue
        try:
            fills += br.orders(limit=200) or []
        except Exception as e:  # noqa: BLE001
            # Historique illisible ⇒ on N'EMPÊCHE PAS le passage : un garde-fou qui se
            # déclenche sur sa propre panne gèlerait le robot une journée sans motif.
            dire(f"· garde journalière : historique {bname} illisible ({str(e)[:60]}) "
                  "— contrôle non concluant, le passage continue.")
            # NON CONCLUANT ≠ RIEN À SIGNALER. Le passage continue (c'est le bon choix),
            # mais le rapport doit dire que ce jour-là le garde-fou n'a rien pu garder.
            noter(obs, GARDE_JOUR, etat=UNCALIBRATED, motif="historique_illisible")
            return False
    d = evaluer(fills)
    if not d["deja_rebalance"]:
        if d["desarme"]:
            dire("· garde journalière : DÉSARMÉE (QUANT_REBAL_MULTI=1).")
        noter(obs, GARDE_JOUR, etat=DESARME if d["desarme"] else ACTIVE)
        return False
    dire(message(d))
    noter(obs, GARDE_JOUR, etat=ACTIVE, declenche=True, motif="deja_rebalance")
    return True


def hors_cadence(brokers: tuple, reduce: float, obs=None) -> bool:
    """True si ce passage tombe AVANT l'échéance de cadence (`execution.cadence`).

    Même source que la garde journalière : l'historique du courtier. Une réduction de
    risque passe toujours ; un historique illisible aussi (le doute profite au
    passage)."""
    from datetime import UTC, datetime

    from packages.execution.cadence import evaluer
    from packages.execution.garde_fous import ACTIVE, CADENCE, UNCALIBRATED, noter
    fills: list[dict] = []
    for bname, br, _cap, _cur in brokers:
        if br is None:
            continue
        try:
            fills += br.orders(limit=200) or []
        except Exception as e:  # noqa: BLE001
            dire(f"· cadence : historique {bname} illisible ({str(e)[:60]}) "
                  "— passage.")
            noter(obs, CADENCE, etat=UNCALIBRATED, motif="historique_illisible")
            return False
    d = evaluer(fills, datetime.now(UTC).date(), reduction=reduce)
    if d["passer"]:
        noter(obs, CADENCE, etat=ACTIVE, motif=d["motif"])
        return False
    dire(f"· cadence : {d['seances']} séance(s) depuis le rebalancement du "
          f"{d['dernier']} (< {d['cadence']}) — aucun ordre aujourd'hui. "
          "QUANT_CADENCE_JOURS=1 pour le rythme quotidien, --forcer pour un passage "
          "exceptionnel.")
    noter(obs, CADENCE, etat=ACTIVE, declenche=True, motif=d["motif"])
    return True


def disjoncteur(equity: float, obs=None, cles: set | None = None) -> float:
    """Facteur d'exposition dicté par la perte du JOUR. 1.0 = rien à signaler.

    Renvoie un FACTEUR et non un booléen pour se composer avec les autres kill-switches
    par un simple `min` — un garde-fou qui aurait sa propre voie d'application finirait
    par diverger de celle des autres.
    """
    from packages.execution.garde_fous import (
        ACTIVE,
        DISJONCTEUR,
        ERREUR,
        UNCALIBRATED,
        noter,
    )
    try:
        from packages.execution.coupe_circuit import evaluer
        d = evaluer(equity, cles=cles) if cles else evaluer(equity)
    except Exception as e:  # noqa: BLE001 — un garde-fou muet ne bloque jamais un run
        dire(f"· disjoncteur : évaluation indisponible ({str(e)[:60]}).")
        noter(obs, DISJONCTEUR, etat=ERREUR, motif="evaluation_indisponible")
        return 1.0
    if not d.get("disponible"):
        noter(obs, DISJONCTEUR, etat=UNCALIBRATED, motif="equity_veille_inconnue")
        return 1.0
    if not d["verrouille"]:
        dire(f"· disjoncteur : perte du jour {-d['variation_jour']:,.0f} $ "
              f"sous le seuil ({d['limite']:,.0f} $).".replace(",", " "))
        noter(obs, DISJONCTEUR, etat=ACTIVE)
        return 1.0
    if d["agit"]:
        dire(f"\n⛔ DISJONCTEUR ARMÉ — {d['motif']}. Aucune entrée aujourd'hui.")
        noter(obs, DISJONCTEUR, etat=ACTIVE, declenche=True, motif="perte_du_jour")
        return 0.0
    dire(f"\n⚠️  DISJONCTEUR (observation) — {d['motif']}.")
    dire("   Il AURAIT coupé. Rien n'est appliqué : QUANT_DISJONCTEUR=1 pour l'armer.")
    # LA LIGNE QUI DÉBLOQUE SON ARMEMENT. `coupe_circuit` demande de voir « sur
    # plusieurs semaines les jours où il AURAIT coupé » : sans ce compteur, cette
    # condition ne pouvait pas être remplie — personne n'enregistrait ces jours.
    noter(obs, DISJONCTEUR, etat=ACTIVE, aurait=True, motif="perte_du_jour")
    return 1.0


def exposition_gelee(targets: list, obs, dry: bool) -> None:
    """Kill-switch total : on annonce ce qui ne sera PAS acheté (QML-007).

    Ce n'est plus une sortie : la réconciliation suit, avec des cibles bornées au détenu
    (`cible_sous_garde`). Aucun achat ne part ; les allègements de la stratégie, eux,
    partent. Le compte-rendu des garde-fous est enregistré une fois, en fin de passage.
    `obs` et `dry` restent dans la signature pour les appelants existants.
    """
    _ = obs, dry
    for o in targets:
        dire(f"  {o['side'].upper():4s} {o.get('broker_symbol', o['symbol']):14s} "
              f"{o['broker']:8s} {o['weight_pct']*100:6.1f}%  "
              "achat bloqué (kill-switch)")
    dire("\n⛔ Kill-switch : aucun achat. Les allègements de stratégie partent ; "
          "aucune vente n'est forcée.")


def record_garde_fous(obs, dry: bool) -> None:
    """Persiste le compte-rendu des garde-fous de CE run. Best-effort, jamais muet.

    Appelé à CHAQUE sortie de `main` postérieure aux garde-fous, y compris celles qui
    n'envoient aucun ordre : un run coupé par un kill-switch est précisément celui qu'on
    veut retrouver dans le rapport. Ne l'enregistrer qu'au passage nominal reviendrait à
    ne compter les garde-fous que les jours où ils ne servent à rien. Un rapport vide
    (sortie avant toute évaluation) n'écrit rien — une ligne à zéro serait un run
    fantôme.
    """
    try:
        from packages.execution.garde_fous_store import record
        rapport = obs.rapport() if obs else {}
        if not rapport:
            return
        if not record(rapport, mode="dry" if dry else "live"):
            dire("⚠️  garde-fous : compte-rendu du run NON enregistré (écriture .cache "
                  "impossible) — `make garde-fous` sous-comptera ce passage.")
    except Exception as e:  # noqa: BLE001 — observer ne coûte jamais un run
        dire(f"⚠️  garde-fous : compte-rendu non enregistré ({str(e)[:60]}).")


def releve_equity(alp_cap: float, bit_cap: float) -> dict:
    """Relevé d'equity du passage, sous LA clé de la place crypto (QML-024).

    `run_live` écrivait « bitmart » quand le snapshot écrivait la place active
    (« binance ») : deux périmètres dans une même série. Une place en bac à sable, ou
    vide, n'y figure pas — son solde n'est pas de l'argent du compte."""
    from packages.execution.venues import venue_crypto
    v = venue_crypto()
    out = {"alpaca": alp_cap}
    if bit_cap > 0 and not v.en_testnet():
        out[v.cle] = bit_cap
    return out


def record_equity(alp_cap: float, bit_cap: float) -> None:
    """Enregistre l'equity RÉELLE du jour → courbe paper de `make rdv-paper`.

    Corrige un trou (06/07) : l'equity_history n'était écrite que par `build_snapshot()`
    (donc seulement à un `make start`). Le chemin de PROD (cron Mac + runner cloud) ne
    l'alimentait pas → la courbe paper du RDV 2026-08-06 ne se serait jamais accumulée
    si le Mac restait éteint. Best-effort strict."""
    try:
        from packages.execution.equity_history import record
        record(releve_equity(alp_cap, bit_cap))
        dire(f"Equity : point du jour enregistré (Alpaca {alp_cap:,.0f} $ · crypto "
              f"{bit_cap:,.0f} $).")
    except Exception as e:  # noqa: BLE001
        dire(f"Equity : enregistrement ignoré ({str(e)[:50]}).")
