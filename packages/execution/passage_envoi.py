"""Envoi d'un ordre décidé, et ce qu'on en retient (suite de `passage_reconcile`).

Extrait de `scripts/run_live.py` (audit du 06/10). Comportement figé par
`tests/execution/test_reconcile_golden.py`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from packages.common.journal_passage import dire
from packages.execution.passage_cibles import id_client

if TYPE_CHECKING:
    from packages.execution.passage_reconcile import Compte, Ligne, Passage


def envoyer(broker, bsym: str, side, montant: float, cid: str):
    """`submit_notional` AVEC l'identifiant quand l'adaptateur le déclare.

    Les trois courtiers réels le déclarent ; les faux courtiers des tests et
    l'adaptateur IBKR (démo) non — on ne casse pas un contrat pour ceux qui ne le
    connaissent pas."""
    import inspect
    try:
        accepte = "client_id" in inspect.signature(broker.submit_notional).parameters
    except (TypeError, ValueError):
        accepte = False
    if accepte:
        return broker.submit_notional(bsym, side, montant, client_id=cid)
    return broker.submit_notional(bsym, side, montant)


def log_rejet(bsym: str, bname: str, intention, issue: str) -> None:
    """Trace structurée d'un refus courtier. Best-effort : ne casse jamais le run."""
    try:
        import logging
        logging.getLogger("live.execution").error(
            "ordre refusé par le courtier",
            extra={"symbole": bsym, "broker": bname, "action": intention.action,
                   "montant": intention.montant, "issue": issue})
    except Exception:  # noqa: BLE001
        pass


def _envoyer_ligne(p: Passage, c: Compte, ln: Ligne, intention) -> None:
    from packages.execution.order_outcome import compte_comme_envoye, resume
    try:
        res = _soumettre(p, c, ln, intention)
        # UN ORDRE ENVOYÉ N'EST PAS UN ORDRE EXÉCUTÉ. Compter dès l'absence
        # d'exception comptait comme réussi un ordre qu'Alpaca venait de REJETER
        # (ADR-0040).
        if not compte_comme_envoye(res):
            dire(ln.tag + "  " + resume(res))
            p.rejetes.append({"symbol": ln.bsym, "broker": c.bname,
                              "action": intention.action,
                              "montant": round(intention.montant, 2),
                              "issue": resume(res)})
            log_rejet(ln.bsym, c.bname, intention, resume(res))
            return            # ni compté, ni journalisé comme une ouverture
        p.sent += 1
        # Le plafond d'exposition doit voir les ordres DÉJÀ envoyés dans cette
        # boucle, sinon chacun est jugé contre l'état initial et la somme dépasse.
        c.expo += (intention.montant if intention.action == "acheter"
                   else -intention.montant)
        if intention.action == "acheter" and ln.detenu <= 0:
            c.npos += 1
        dire(ln.tag + {"acheter": "  ▲ achat", "alleger": "  ▼ vente",
                       "solder": "  ▼ SOLDE (quantité)"}[intention.action])
        _noter_envoi(p, c, ln, res)
    except Exception as e:  # noqa: BLE001
        _echec(p, c, ln, intention, e)


def _soumettre(p: Passage, c: Compte, ln: Ligne, intention):
    from packages.common.retry import retry
    from packages.core.models import Side
    side = Side.LONG if intention.action == "acheter" else Side.SHORT
    if intention.liquidation and hasattr(c.broker, "close_position"):
        # Sortie totale EN QUANTITÉ : aucun résidu, donc aucune poussière future.
        return retry(lambda: c.broker.close_position(ln.bsym), attempts=3)
    # Le MÊME identifiant à chaque tentative : un envoi accepté puis perdu en route
    # n'est plus renvoyé, il est retrouvé (QML-006).
    cid = id_client(p.run_id, ln.bsym, intention.action)
    return retry(lambda: envoyer(c.broker, ln.bsym, side, intention.montant, cid),
                 attempts=3)


def _noter_envoi(p: Passage, c: Compte, ln: Ligne, res) -> None:
    """L'IDENTITÉ DE L'ORDRE VOYAGE AVEC LUI. `close_position` rend un booléen : pas
    d'identité, donc None."""
    oid = str(getattr(res, "id", "") or "") or None
    o = ln.o
    if ln.delta > 0 and o is not None:            # ACHAT/ADD → ouverture à journaliser
        op = {"symbol": o["symbol"], "venue": c.bname, "broker_symbol": ln.bsym,
              "asset_class": o.get("asset_class"), "weight_pct": o.get("weight_pct"),
              "order_id": oid}
        # rank_score / expectancy* / géométrie : uniquement si déjà figés sur la
        # cible (snapshot) — jamais inventés ici.
        for k in ("rank_score", "expectancy_R", "rr", "p_calibrated", "risk_$",
                  "entry", "stop", "target"):
            v = o.get(k)
            if isinstance(v, (int, float)) and not isinstance(v, bool) and v == v:
                op[k] = float(v)
        for k in ("strategy", "setup_id", "ts_decision"):
            v = o.get(k)
            if isinstance(v, str) and v.strip():
                op[k] = v.strip()
        p.opened.append(op)
    elif ln.delta < 0:                            # VENTE/REDUCE → round-trip à fermer
        p.sold.append({"symbol": (o or {}).get("symbol", ln.bsym), "venue": c.bname,
                       "broker_symbol": ln.bsym, "notional": abs(ln.delta),
                       "order_id": oid})


def _echec(p: Passage, c: Compte, ln: Ligne, intention, e: Exception) -> None:
    """Le motif COMPLET va au journal structuré, un extrait large à l'écran : un
    rejet tronqué (« invalid time_in_force », « market closed »…) devenait illisible."""
    msg = str(e).replace("\n", " ")
    dire(ln.tag + f"  ❌ ÉCHEC après retries : {msg[:200]}")
    try:
        import logging
        logging.getLogger("live.execution").error(
            "ordre refusé",
            extra={"symbole": ln.bsym, "broker": c.bname, "action": intention.action,
                   "montant": intention.montant, "erreur": msg})
    except Exception:  # noqa: BLE001 — journaliser ne casse jamais le run
        pass
    if p.alert_engine:
        from packages.alerts import Alert, Severity
        p.alert_engine.emit(Alert("execution", Severity.CRITICAL,
            f"Ordre {'achat' if ln.delta > 0 else 'vente'} {ln.bsym} ({c.bname}) "
            "échoué "
            f"après retries : {str(e)[:80]}",
            dedup_key=f"execution:submit_fail:{ln.bsym}"))


def _recapituler(p: Passage) -> None:
    if p.rejetes:
        tr = f"{sum(abs(r['montant']) for r in p.rejetes):,.0f}".replace(",", " ")
        dire(f"\n  ❌ {len(p.rejetes)} ordre(s) REFUSÉ(S) par le courtier, "
             f"{tr}$ au total.")
        dire("     Ils ne comptent PAS comme envoyés. Motif par ligne ci-dessus.")
    if p.differes:
        recap_differes(p.differes)


def recap_differes(differes: list) -> None:
    """Le report n'est pas une erreur — mais il ne doit pas être SUBI.

    L'ancien message disait « ils partiront à la prochaine séance ». C'est faux dès
    que le rebalancement est planifié hors séance : la prochaine exécution sera elle
    aussi hors séance, et les mêmes ordres seront reportés indéfiniment. Un ordre
    reporté ne part QUE si une exécution tombe DANS la séance — rien ne le met en
    file d'attente.
    """
    tot = f"{sum(abs(d['montant']) for d in differes):,.0f}".replace(",", " ")
    par_classe: dict[str, int] = {}
    for d in differes:
        cl = d.get("asset_class", "?")
        par_classe[cl] = par_classe.get(cl, 0) + 1
    detail = ", ".join(f"{n} {c}" for c, n in sorted(par_classe.items()))
    dire(f"\n  ⏸  {len(differes)} ordre(s) REPORTÉ(S) hors séance ({detail}), "
          f"{tot}$ au total.")
    dire("     Ils ne sont PAS mis en file d'attente : un ordre reporté ne part que")
    dire("     si une exécution tombe DANS la séance NYSE"
          " (15:30-22:00, heure de Paris).")
    dire("     Si ce report revient chaque jour, c'est le planning, pas le marché :")
    dire("       • à la main, un soir avant 22h  →  make live-go")
    dire("       • ou décaler le rebalancement   →  "
          "QUANT_LIVE_HOUR=21 make live-cron-install")
    dire("     Le crypto n'est jamais concerné : il tourne 24/7.")
