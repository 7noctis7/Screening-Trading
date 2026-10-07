"""Réconciliation d'UN passage : du détenu vers la cible, ordre par ordre.

Extrait de `scripts/run_live.py` (audit du 06/10) : `_reconcile` faisait 233 lignes
dans un fichier de 1 343. Découpé en étapes de moins de 50 lignes, SANS changer une
décision : `tests/execution/test_reconcile_golden.py` compare, sur six comptes
factices, le texte affiché, les valeurs rendues, les appels au courtier (identifiant
client compris), les compteurs des garde-fous et les alertes à une référence
enregistrée AVANT le découpage.

Une ligne traverse, dans l'ordre : négociable ? → séance ouverte ? → décision (bande,
plancher) → portail de risque (réduit ou refuse, jamais n'augmente) → géométrie swing
→ envoi (ou aperçu). Les imports restent locaux aux fonctions : les tests remplacent
`market_calendar.is_open` & co. au moment de l'appel.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from packages.common.journal_passage import dire
from packages.execution.passage_cibles import (
    broker_targets,
    nsym,
    ordre_de_traitement,
    sleeve_geometry_missing,
)


@dataclass
class Passage:
    """État d'UN appel : ce qui est envoyé, ouvert, vendu, reporté, rejeté."""

    run_id: str
    dry: bool
    obs: object
    alert_engine: object
    verif_seance: bool
    sent: int = 0
    opened: list = field(default_factory=list)
    sold: list = field(default_factory=list)
    differes: list = field(default_factory=list)
    rejetes: list = field(default_factory=list)


@dataclass
class Compte:
    """Un courtier pendant la boucle : l'exposition voit les ordres DÉJÀ envoyés."""

    bname: str
    broker: object
    cap: float
    lim: object
    expo: float
    npos: int


@dataclass
class Ligne:
    o: dict | None
    bsym: str
    val: float
    detenu: float
    tag: str

    @property
    def delta(self) -> float:
        return self.val - self.detenu                 # >0 acheter · <0 vendre


def reconcilier(targets, brokers, reduce, alert_engine, dry, obs=None, *,
                proteger=None, liquider_hors_cible: bool = True
                ) -> tuple[int, list, list]:
    """Réconciliation idempotente + ANTI-LEVIER. Rend (nb ordres, ouvertures, ventes).

    On n'échange que le DELTA (cible − détenu). `opened` = achats RÉELLEMENT envoyés
    (à journaliser, `legacy=0`) ; `sold` = ventes RÉELLEMENT envoyées (round-trip
    Phase 2)."""
    import uuid

    from packages.execution.market_calendar import feries_a_jour
    # ÉCHAPPATOIRE EXPLICITE. `QUANT_IGNORE_SESSION=1` envoie quand même hors séance —
    # utile pour empiler des ordres avant l'ouverture en connaissance de cause, et pour
    # les tests qui isolent le PORTAIL DE RISQUE du calendrier. Jamais le défaut : un
    # ordre qui ne peut pas se remplir doit être dit, pas envoyé dans le vide.
    verif = os.environ.get("QUANT_IGNORE_SESSION", "") != "1"
    p = Passage(uuid.uuid4().hex, dry, obs, alert_engine, verif)  # identité (QML-006)
    if verif and not feries_a_jour():
        dire("  ⚠️  fériés NYSE périmés — voir packages/execution/market_calendar")
    for bname, broker, cap, cur in brokers:
        _reconcilier_compte(p, targets, (bname, broker, cap, cur), reduce, proteger,
                            liquider_hors_cible)
    _recapituler(p)
    return p.sent, p.opened, p.sold


def _reconcilier_compte(p: Passage, targets, compte: tuple, reduce, proteger,
                        liquider_hors_cible: bool) -> None:
    from packages.risk.order_gate import Limites
    bname, broker, cap, cur = compte
    tgt, band = broker_targets(targets, bname, cap, reduce, cur, proteger=proteger,
                               liquider_hors_cible=liquider_hors_cible)
    curn: dict[str, float] = {}                 # détenu par clé NORMALISÉE (cumul)
    for k, v in cur.items():
        curn[nsym(k)] = curn.get(nsym(k), 0.0) + v
    # PORTAIL DE RISQUE — indépendant de la stratégie, lu depuis l'environnement seul.
    # Jusqu'ici les limites du projet (`packages.risk`) n'existaient que dans les
    # démos : le chemin de production n'avait aucun veto PAR ORDRE.
    lim = Limites.depuis_env()
    c = Compte(bname, broker, cap, lim, sum(abs(v) for v in curn.values()),
               sum(1 for v in curn.values() if abs(v) > 0))
    if not p.dry:
        dire(f"  portail de risque : {lim.resume()} · brut actuel {c.expo:.0f}$ / "
             f"{cap:.0f}$")
    for nkey, info in ordre_de_traitement(tgt, curn):
        detenu = curn.get(nkey, 0.0)
        delta = info["val"] - detenu
        tag = (f"  {info['sym']:14s} {bname:8s} cible {info['val']:8.0f}$ détenu "
               f"{detenu:8.0f}$ Δ {delta:+8.0f}$")
        _traiter(p, c, Ligne(info["o"], info["sym"], info["val"], detenu, tag), band)


def _traiter(p: Passage, c: Compte, ln: Ligne, band: float) -> None:
    from packages.execution.rebalance_plan import decider
    from packages.execution.routing import classe_actif
    if ln.o is not None and ln.o.get("tradeable") is False:
        dire(ln.tag + "  non négociable")
        return
    ac = classe_actif(ln.bsym, (ln.o or {}).get("asset_class") or "")
    if not _seance(p, c, ln, ac):
        return
    # Décision déléguée (testée) : solder hors bande, ne pas ouvrir sous le plancher.
    intention = decider(ln.val, ln.detenu, band)
    if not intention.agit:
        dire(ln.tag + f"  ✓ {intention.motif}")
        return
    intention = _portail(p, c, ln, intention, ac)
    if intention is None or _geometrie_manquante(c, ln):
        return
    if p.dry or c.broker is None:
        _apercu(p, c, ln, intention)
        return
    _envoyer_ligne(p, c, ln, intention)


def _seance(p: Passage, c: Compte, ln: Ligne, ac: str) -> bool:
    """SÉANCE OUVERTE ? Les actions partent en TimeInForce.DAY sans extended_hours :
    hors séance l'ordre ne peut PAS se remplir. La crypto (GTC, 24/7) passe. Constat
    du 26/08 : un run lancé d'Europe (03 h à NY) remplissait tout le crypto et AUCUNE
    action. On REPORTE en le disant, et l'effet se compte en dollars non envoyés
    (le 21/09 : 19 lignes pour 52 596 $ reportées sans que rien ne le compte)."""
    from packages.execution.garde_fous import DESARME, SEANCE, noter
    from packages.execution.market_calendar import (
        is_open,
        prochaine_ouverture,
        raison_fermeture,
    )
    if not p.verif_seance:
        noter(p.obs, SEANCE, etat=DESARME)
        return True
    if not is_open(asset_class=ac):
        pq = prochaine_ouverture()
        dire(ln.tag + f"  ⏸  REPORTÉ — {raison_fermeture(asset_class=ac)}"
             f" · prochaine ouverture {pq:%d/%m %H:%M ET}")
        p.differes.append({"symbol": ln.bsym, "broker": c.bname, "asset_class": ac,
                           "montant": round(ln.delta, 2)})
        noter(p.obs, SEANCE, declenche=True, motif=ac, effet_usd=abs(ln.delta))
        return False
    noter(p.obs, SEANCE, effet_usd=0.0)
    return True


def _portail(p: Passage, c: Compte, ln: Ligne, intention, ac: str):
    """DERNIÈRE BARRIÈRE : le portail peut réduire ou refuser, jamais augmenter. Un
    désengagement le traverse toujours. Un ETF indiciel porte un risque d'émetteur,
    pas celui d'un titre unique : il a son propre plafond de ligne (`panier`). Rend
    l'intention (éventuellement réduite), ou None si l'ordre est refusé."""
    from dataclasses import replace

    from packages.execution.garde_fous import noter_portail
    from packages.risk.order_gate import EtatCompte, evaluer, ligne_journal
    etat = EtatCompte(equity=c.cap, exposition_brute=c.expo, n_positions=c.npos,
                      detenu_ligne=ln.detenu, panier=(ac == "etf"))
    v = evaluer(intention.action, intention.montant, etat, c.lim,
                liquidation=intention.liquidation)
    # TÉMOIN : il compte le verdict APRÈS qu'il a été rendu et ne peut pas le modifier.
    noter_portail(p.obs, v, intention.montant)
    if not v.autorise:
        dire(ln.tag + f"  ⛔ REFUSÉ par le portail [{v.regle}] {v.motif}")
        if p.alert_engine:
            from packages.alerts import Alert, Severity
            p.alert_engine.emit(Alert("risk", Severity.WARNING,
                f"Ordre {ln.bsym} refusé par le portail de risque : {v.motif}"))
        return None
    if v.reduit:
        dire(ln.tag + f"  ⚠️  {v.motif}")
        intention = replace(intention, montant=v.montant)
    if not p.dry:
        dire("  " + ligne_journal(ln.bsym, intention.action, v.montant, v))
    return intention


def _geometrie_manquante(c: Compte, ln: Ligne) -> bool:
    """Guard géométrie sleeve (TA#8) — inactif pour preset / strategy absente."""
    miss = sleeve_geometry_missing(ln.o)
    if not miss:
        return False
    dire(ln.tag + f"  ⛔ reject_missing_geometry ({','.join(miss)})")
    try:
        import logging
        logging.getLogger("live.execution").warning(
            "reject_missing_geometry",
            extra={"symbole": ln.bsym, "broker": c.bname, "manquants": list(miss),
                   "strategy": (ln.o or {}).get("strategy")})
    except Exception:  # noqa: BLE001
        pass
    return True


def _apercu(p: Passage, c: Compte, ln: Ligne, intention) -> None:
    dire(ln.tag + f"  {'aperçu' if p.dry else 'broker absent'} ({intention.action})")
    if p.dry:      # l'aperçu SIMULE l'effet de l'ordre, comme le réel le compterait :
        #  sans cela une vente ne libère rien et l'achat suivant s'affiche refusé à
        #  tort (constaté le 25/09).
        c.expo += (intention.montant if intention.action == "acheter"
                   else -intention.montant)
        if intention.action == "acheter" and ln.detenu <= 0:
            c.npos += 1


from packages.execution.passage_envoi import (  # noqa: E402 — étape suivante
    _envoyer_ligne,
    _recapituler,
    envoyer,
    log_rejet,
    recap_differes,
)

__all__ = ["reconcilier", "envoyer", "log_rejet", "recap_differes", "Passage", "Compte",
           "Ligne"]
