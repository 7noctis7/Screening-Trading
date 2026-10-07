"""Journal des VENTES (round-trip) et coût réel par ordre (TCA) d'un passage.

Extrait de `scripts/run_live.py` (audit du 06/10). Prix et quantités de sortie = FAITS
du courtier ; introuvable → lot laissé ouvert, jamais un prix inventé. Best-effort
strict : rien ici ne bloque un passage.
"""

from __future__ import annotations

from datetime import UTC, datetime

from packages.common.journal_passage import dire


def fill_vente_jour(br, bsym: str) -> dict | None:
    """Fill de VENTE réel du jour pour ce symbole, ou None : {"price", "qty"}.

    Isolé de `_exit_price` pour que `_journal_sells` lise aussi la QUANTITÉ vraiment
    exécutée. Jusqu'ici seul le PRIX de ce même ordre était repris ; la quantité
    fermée au journal venait de `notional / prix`, où `notional` = le delta PLANIFIÉ
    par le rebalancement (`abs(cible − détenu)`), jamais relu contre le fill réel.
    Mesuré le 05/09 sur le compte réel (OSCR) : le delta planifié dépassait le fill
    réel de ~85 unités, closes au journal comme si elles avaient été vendues — du
    « réalisé » sans contrepartie, à chaque écart entre plan et exécution."""
    if br is None or not hasattr(br, "orders"):
        return None
    try:
        today = datetime.now(UTC).date().isoformat()
        for o in br.orders(limit=50):
            if (o.get("symbol") == bsym and o.get("side") == "sell"
                    and float(o.get("price") or 0) > 0
                    and (o.get("date") or "")[:10] == today):
                return {"price": float(o["price"]), "qty": float(o.get("qty") or 0)}
    except Exception:  # noqa: BLE001
        pass
    return None


def exit_price(br, bsym: str) -> float:
    """Prix de sortie FACTUEL, par ordre de fiabilité : fill VENTE du jour (`orders`),
    sinon ticker broker (`last_price`), sinon prix courant de la position. 0.0 = inconnu
    (le lot restera OUVERT — on n'invente jamais un prix)."""
    if br is None:
        return 0.0
    fait = fill_vente_jour(br, bsym)
    if fait is not None:
        return fait["price"]
    try:
        if hasattr(br, "last_price"):
            px = float(br.last_price(bsym) or 0.0)
            if px > 0:
                return px
        for p in br.positions_detailed():
            if p.get("symbol") == bsym and float(p.get("price") or 0) > 0:
                return float(p["price"])
    except Exception:  # noqa: BLE001
        pass
    return 0.0


def journal_sells(snap: dict, sold: list, alpaca, bitmart) -> None:
    """Round-trip (P0-4 Phase 2) : ferme les lots touchés par les VENTES envoyées.

    Prix de sortie = FAIT broker (cf. `_exit_price`) ; introuvable → lot laissé OUVERT.
    Best-effort strict : ne lève jamais → ne peut pas bloquer l'exécution."""
    if not sold:
        return
    try:
        from packages.execution.live_roundtrip import close_sells
        from packages.storage import SqliteTradeJournal
        brokers = {"Alpaca": alpaca, "Bitmart": bitmart}
        for s in sold:
            br = brokers.get(s["venue"])
            fait = fill_vente_jour(br, s["broker_symbol"])
            if fait is not None:                 # fill réel citable → quantité VRAIE
                s["exit_price"], s["qty_reelle"] = fait["price"], fait["qty"]
            else:                                     # repli : ancien comportement
                s["exit_price"] = exit_price(br, s["broker_symbol"])
        series = (snap.get("dashboard") or {}).get("chart_series") or {}
        orphelines: list[dict] = []
        n = close_sells(SqliteTradeJournal(), sold, series, orphelines=orphelines)
        skipped = sum(1 for s in sold if not s.get("exit_price"))
        dire(f"Journal : {n} lot(s) fermé(s) (round-trip, PnL/MFE/MAE)"
              + (f" · {skipped} vente(s) sans prix broker (lots laissés ouverts)."
                 if skipped else "."))
        dire_les_orphelines(orphelines)
    except Exception as e:  # noqa: BLE001
        dire(f"Journal : round-trip ignoré ({str(e)[:60]}).")


def dire_les_orphelines(orphelines: list[dict]) -> None:
    """Ventes exécutées chez le courtier qu'AUCUN lot du journal n'a soldées.

    Ce bloc existe parce que son absence a coûté quatre aller-retours le 22/09 : les
    ventes partaient, le journal n'en fermait qu'une, et la ligne « 1 lot(s) fermé(s) »
    ne disait rien des quatre autres. Un appariement qui échoue doit être aussi bruyant
    qu'un ordre refusé — sinon le registre diverge du compte sans qu'aucune sortie ne le
    signale, et l'écart ne se découvre qu'en comparant à la main des mois plus tard."""
    if not orphelines:
        return
    dire(f"  ⚠ {len(orphelines)} vente(s) SANS LOT au journal — le compte a vendu, le "
          "registre n'a rien à fermer :")
    for o in orphelines[:10]:
        reste = float(o["qty_demandee"]) - float(o["qty_fermee"])
        dire(f"      {o['symbol']:<10} {reste:12.6f} unité(s) non soldée(s) "
              f"sur {o['qty_demandee']:.6f} vendue(s)")
    dire("      Origines possibles : lot d'import (`LEG-`, écarté à dessein), position "
          "antérieure au journal,")
    dire("      ou lot déjà fermé. `python scripts/diag_journal_compte.py --symbole "
          "<TICKER>` tranche.")


def cotations_arrivee(targets: list, cur_alp: dict, alpaca, dry: bool) -> dict:
    """Bid / ask JUSTE AVANT l'envoi des ordres (Alpaca). MESURE seulement : rien n'en
    dépend dans la décision ni dans l'envoi, et une lecture ratée rend {}."""
    if dry or alpaca is None:
        return {}
    from packages.execution.cotations import cotations
    syms = {o.get("broker_symbol", o["symbol"]) for o in targets
            if o.get("capital") != "bitmart"} | set(cur_alp or {})
    return cotations(syms)


def journal_tca(snap: dict, opened: list, sold: list, alpaca, arrivee: dict) -> None:
    """Une ligne `tca_executions` par ordre Alpaca rempli : spread à l'arrivée, dérive
    depuis le close de décision, shortfall d'exécution. Ne lève jamais."""
    try:
        from packages.execution.cotations import cotations
        from packages.execution.tca_journal import enregistrer, ligne
        ordres = ([{**o, "cote": "buy"} for o in opened]
                  + [{**v, "cote": "sell"} for v in sold])
        ordres = [o for o in ordres if o.get("venue") == "Alpaca" and o.get("order_id")]
        if not ordres or alpaca is None:
            return
        fills = {f.get("id"): f for f in alpaca.orders(limit=200)}
        apres = cotations({o["broker_symbol"] for o in ordres})
        series = (snap.get("dashboard") or {}).get("chart_series") or {}
        jour = datetime.now(UTC).date().isoformat()
        lignes = []
        for o in ordres:
            f = fills.get(o["order_id"])
            if not f or float(f.get("price") or 0) <= 0:
                continue
            barres = series.get(o["symbol"]) or []
            close = float(barres[-1]["c"]) if barres else None
            lignes.append(ligne(o, prix_fill=float(f["price"]), qty=float(f["qty"]),
                                close_decision=close, jour=jour,
                                arrivee=arrivee.get(o["broker_symbol"]),
                                apres=apres.get(o["broker_symbol"])))
        n = enregistrer(lignes)
        avec = sum(1 for li in lignes if li["bench_quality"] == "quote")
        dire(f"TCA : {n} ordre(s) mesuré(s), {avec} avec cotation d'arrivée "
              "(spread, dérive, shortfall → table tca_executions).")
    except Exception as e:  # noqa: BLE001
        dire(f"TCA : mesure ignorée ({str(e)[:60]}).")
