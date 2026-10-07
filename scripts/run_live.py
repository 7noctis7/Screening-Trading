"""Exécuteur live — réplique le portefeuille MODÈLE chez les brokers (DRY-RUN par défaut).

Routage : actions/ETF → **Alpaca (paper)** · crypto /USDC → **Bitmart** (ccxt).
Sécurité maximale :
  - DRY-RUN par défaut : affiche les ordres, n'envoie RIEN ;
  - mode réel uniquement avec `--live --yes` ET clés API présentes ;
  - Alpaca reste en **paper** (is_paper) ; Bitmart protégé par `dry_run` tant que `--live`
    n'est pas passé. Permissions API minimales, jamais de retrait.
  - `QUANT_NO_CRYPTO_LIVE` (défaut `1`) : aucune place crypto instanciée, même avec
    `--live --yes` et des clés présentes (cf. `crypto_live_neutralisee`). Lu ICI,
    pas seulement par `cron_live.sh` : `make live-go` appelle ce script directement.
    Opt-in live crypto : `QUANT_NO_CRYPTO_LIVE=0`.

  python scripts/run_live.py                 # aperçu (dry-run) des ordres cibles
  python scripts/run_live.py --live --yes    # envoie en paper/crypto (clés requises)

Chaque run réel JOURNALISE ses ouvertures (`data/journal.db`, `legacy=0`) avec les features figées
à la DÉCISION (cf. `packages/execution/live_journal.py`) → alimente la calibration ML (P0-4).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packages.common.journal_passage import dire  # noqa: E402 — écran + JSONL


def _parse_args():
    ap = argparse.ArgumentParser(description="Réplique le portefeuille modèle (dry-run par défaut)")
    ap.add_argument("--live", action="store_true", help="envoyer réellement (sinon dry-run)")
    ap.add_argument("--yes", action="store_true", help="confirmation obligatoire pour le mode --live")
    ap.add_argument("--equity", type=float, default=None,
                    help="dry-run : SIMULE un portefeuille neuf de ce capital (détenu "
                         "ignoré). Sans lui, l'aperçu lit l'equity et les positions "
                         "RÉELLES. En live : toujours l'equity réelle du broker.")
    ap.add_argument("--forcer", action="store_true",
                    help="passer outre le garde-fou « déjà rebalancé aujourd'hui ». "
                         "À n'utiliser qu'en sachant ce qui a déjà été envoyé au "
                         "courtier : un second passage recalcule une cible différente.")
    return ap.parse_args()


def _setup_alerts(dry: bool):
    """Bus + moteur d'alertes PROD (Console + Telegram/Discord si clés). None en dry-run."""
    if dry:
        return None, None
    from packages.alerts.wiring import attach_to_bus
    from packages.common.event_bus import EventBus
    bus = EventBus()
    return bus, attach_to_bus(bus)


def _kill_switch(bus, obs=None):
    """Alertes TradingView → veto / réduction d'exposition. Retourne le facteur `reduce` ∈ [0,1].

    `obs` ne fait qu'ASSISTER : il compte ce qui vient d'être décidé, il ne décide pas."""
    from packages.mcp_tradingview.alerts import (
        AGE_MAX_DEFAUT,
        fetch_tv_technical_alerts,
        to_risk_veto,
    )
    # Appel SANS filtre d'âge jusqu'au 25/08 : une alerte critique reçue des
    # semaines plus tôt
    # bloquait encore tout le portefeuille, jusqu'à effacement manuel du drop.
    risk = to_risk_veto(fetch_tv_technical_alerts(max_age_s=AGE_MAX_DEFAUT))
    if risk.get("n_sans_date"):
        dire(f"⚠️  {risk['n_sans_date']} alerte(s) TV sans date lisible — conservées par "
              "prudence (elles pèsent sur la décision sans pouvoir être périmées)")
    for r in risk.get("severites_reinterpretees", []):
        dire(f"⚠️  sévérité TV réinterprétée : {r}")
    reduce = 0.0 if risk.get("veto") else float(risk.get("reduce", 1.0))
    if risk.get("veto"):
        dire(f"⛔ KILL-SWITCH ACTIF (alertes TV critiques) : {', '.join(risk['reasons']) or '—'}")
        dire("   → achats BLOQUÉS ; aucune vente forcée (seuls les allègements de "
              "la stratégie partent).")
        if bus:
            from packages.common.event_bus import Topic
            bus.publish(Topic.KILL_SWITCH,
                        {"drawdown": "veto TV: " + (", ".join(risk["reasons"]) or "—")})
    elif reduce < 1.0:
        dire(f"⚠️  Alertes TV : achats plafonnés à ×{reduce:.2f} de la cible, aucune vente "
              f"forcée ({', '.join(risk['reasons']) or '—'})")
    # MOTIF EN CODE COURT, jamais le texte des alertes : le compte-rendu est un fichier
    # de compteurs, il n'a pas à transporter du contenu de marché.
    from packages.execution.garde_fous import KILL_TV, noter
    noter(obs, KILL_TV, declenche=(reduce < 1.0),
          motif=("veto" if risk.get("veto") else "reduction") if reduce < 1.0 else None)
    return reduce


def _alpaca_ou_rien():
    """Alpaca paper, best-effort — l'indisponibilité est DITE, jamais silencieuse."""
    try:
        from packages.execution.alpaca_broker import AlpacaBroker
        return AlpacaBroker(paper=True)                   # actions TOUJOURS en paper
    except Exception as e:  # noqa: BLE001
        dire(f"Alpaca indisponible ({str(e)[:60]}) → actions ignorées")
        return None


def crypto_live_neutralisee() -> bool:
    """`QUANT_NO_CRYPTO_LIVE` (défaut 1) : neutraliser toute place crypto live.

    Même contrat que `cron_live.sh` (`${QUANT_NO_CRYPTO_LIVE:-1}`) : le flag doit
    tenir DANS `run_live.py` — `make live-go` / `python scripts/run_live.py --live
    --yes` hors cron ne doivent pas contourner le verrou. Couvre Binance (défaut
    via `venue_crypto`) autant que Bitmart. Opt-in live crypto : `=0` / `false` /
    `off` / `no`. Valeurs affirmatives : `1` / `true` / `yes` / `on` (casse ignorée).
    """
    v = os.environ.get("QUANT_NO_CRYPTO_LIVE", "1").strip().lower()
    return v in ("1", "true", "yes", "on")


def _make_brokers(dry: bool, apercu: bool = False):
    """(alpaca paper, place crypto). Rien en SIMULATION ; Alpaca seul en APERÇU.

    Un aperçu doit lire l'equity et les positions RÉELLES, sinon il n'annonce pas le run
    suivant — mesuré le 05/09 : sans broker construit, l'aperçu affichait `détenu
    0 $` sur un compte plein, puis `cible 0 $` une fois l'equity lue sur un broker
    inexistant.
    AUCUN ordre ne peut partir pour autant : `_reconcile` sort sur `if dry or broker is
    None` AVANT tout envoi. La place crypto reste absente en dry-run — et, hors dry-run,
    `QUANT_NO_CRYPTO_LIVE` (défaut 1) force aussi None / no-op sur `venue_crypto()`.

    La place crypto n'est pas codée en dur : elle vient de QUANT_CRYPTO_VENUE (défaut
    Binance, taker 0,10 % contre 0,25 % chez Bitmart). Cf. packages/execution/venues.
    """
    if dry:
        return (_alpaca_ou_rien(), None) if apercu else (None, None)
    if crypto_live_neutralisee():
        dire("QUANT_NO_CRYPTO_LIVE actif → poche crypto ignorée (aucune place)")
        return _alpaca_ou_rien(), None
    from packages.execution.venues import venue_crypto
    _v = venue_crypto()
    try:
        crypto = _v.broker(dry_run=False)
    except Exception as e:  # noqa: BLE001 — clés/dépendance absentes : on continue
        dire(f"{_v.nom} indisponible ({str(e)[:60]}) → poche crypto ignorée")
        crypto = None
    return _alpaca_ou_rien(), crypto


# Garde-fous d'exécution (audit 07/15) : inconnu ≠ zéro, fail-loud, kill-switch DD réel.
# Extraits dans packages/execution/live_guards.py (règle <400 l./fichier).


# CHEMIN D'ORDRES — extrait dans packages/execution/passage_*.py (audit 06/10 : ce
# fichier faisait 1 343 lignes, `_reconcile` 233). Mêmes noms ici : les appelants et
# les tests n'ont rien à changer. Comportement figé par test_reconcile_golden.
import packages.execution.passage_cibles as _pc  # noqa: E402
import packages.execution.passage_diagnostic as _pd  # noqa: E402
import packages.execution.passage_envoi as _pe  # noqa: E402
import packages.execution.passage_gardes as _pg  # noqa: E402
import packages.execution.passage_journal as _pj  # noqa: E402
import packages.execution.passage_reconcile as _pr  # noqa: E402
import packages.execution.passage_ventes as _pv  # noqa: E402

_reconcile = _pr.reconcilier
_nsym, _broker_targets, id_client = _pc.nsym, _pc.broker_targets, _pc.id_client
cible_sous_garde, ordre_de_traitement = _pc.cible_sous_garde, _pc.ordre_de_traitement
sleeve_geometry_missing = _pc.sleeve_geometry_missing
_envoyer, _log_rejet, _recap_differes = _pe.envoyer, _pe.log_rejet, _pe.recap_differes
_deja_rebalance_aujourdhui = _pg.deja_rebalance_aujourdhui
_hors_cadence = _pg.hors_cadence
_disjoncteur, _exposition_gelee = _pg.disjoncteur, _pg.exposition_gelee
_record_garde_fous, _record_equity = _pg.record_garde_fous, _pg.record_equity
releve_equity = _pg.releve_equity
_fills_achats, _positions_repli = _pj.fills_achats, _pj.positions_repli
_garder_les_decisions, _ids_lisibles = _pj.garder_les_decisions, _pj.ids_lisibles
_dire_les_ouvertures = _pj.dire_les_ouvertures
_attendre_les_fills = _pj.attendre_les_fills
_journal_opens = _pj.journal_opens
_fill_vente_jour, _exit_price = _pv.fill_vente_jour, _pv.exit_price
_journal_sells, _dire_les_orphelines = _pv.journal_sells, _pv.dire_les_orphelines
_cotations_arrivee, _journal_tca = _pv.cotations_arrivee, _pv.journal_tca
_diag_preset = _pd.diag_preset


def _sync_obsidian() -> None:
    """Synchronise le coffre Obsidian (journal + attribution + post-mortems). Best-effort strict."""
    try:
        from packages.reporting.obsidian import sync_obsidian_vault
        r = sync_obsidian_vault()
        dire(f"Coffre Obsidian : {len(r.get('written', []))} note(s) · {r.get('incidents', 0)} incident(s).")
    except Exception:  # noqa: BLE001
        pass


def _decision_snapshot() -> dict:
    """Snapshot de DÉCISION en mode LÉGER : la réconciliation n'a besoin que des poids
    cibles + régime + prix. On coupe les sections réseau lentes (fondamentaux, news, ML…)
    → le build passe de plusieurs minutes (souvent interrompu) à quelques secondes.
    Forçable en complet avec QUANT_LIVE_LITE=0 (ex. debug)."""
    import os
    os.environ.setdefault("QUANT_LIVE_LITE", "1")
    if os.environ["QUANT_LIVE_LITE"] == "1":
        dire("Snapshot : mode léger (sections réseau non essentielles coupées pour l'exécution).")
    from apps.api.snapshot import build_snapshot
    return build_snapshot()                                # DÉCISION unique (features figées ici)


def _prepare_brokers(dry: bool, cli_equity: float | None, alert_engine):
    """Brokers vétés + positions lues (inconnu ⇒ broker écarté). Cf. live_guards."""
    from packages.execution.live_guards import (
        current_values,
        fail_loud,
        simule,
        vet_brokers,
    )
    # SIMULATION (`--equity`) vs APERÇU : seule la simulation ignore le détenu. Un aperçu
    # sur détenu vide affiche des achats que le run réel ne fera pas — il annonce un
    # portefeuille à construire là où le compte est déjà plein.
    simulation = simule(dry, cli_equity)
    alpaca, bitmart = _make_brokers(dry, apercu=dry and not simulation)
    alpaca, bitmart, alp_cap, bit_cap, fatal = vet_brokers(alpaca, bitmart, dry, cli_equity)
    mode = ("SIMULATION (capital imposé, détenu ignoré)" if simulation else
            "DRY-RUN sur le compte RÉEL (aucun ordre)" if dry else "LIVE (paper)")
    dire(f"Réplication · capital Alpaca {alp_cap:,.0f} $ · Bitmart {bit_cap:,.0f} $ · "
          f"mode {mode}")
    dire(f"  {'SENS':4s} {'ACTIF':14s} {'BROKER':8s} {'POIDS':>7s} {'MONTANT':>10s}  statut")
    cur_alp, cur_bit = ({}, {}) if simulation else current_values(alpaca, bitmart)
    if cur_alp is None:                                        # inconnu ≠ zéro : broker écarté
        fatal.append("lecture positions Alpaca échouée → broker écarté (0 ordre)")
        alpaca, cur_alp = None, {}
    if cur_bit is None:
        fatal.append("lecture positions Bitmart échouée → broker écarté (0 ordre)")
        bitmart, cur_bit = None, {}
    if not dry and alpaca is None and bitmart is None:
        fail_loud(fatal or ["aucun broker actif en mode LIVE"], alert_engine, code=3)
    return alpaca, bitmart, alp_cap, bit_cap, cur_alp, cur_bit, fatal


def _ouvrir_journal(a, dry: bool) -> None:
    """Journal JSONL du passage + vérification des réglages `QUANT_*` (audit 06/10) :
    une faute de frappe ou une valeur illisible se DIT avant toute décision."""
    from packages.common import journal_passage as jp
    from packages.common.reglages import annoncer
    jp.ouvrir()
    jp.evenement("passage", dry=dry, live=bool(a.live), forcer=bool(a.forcer))
    for x in annoncer(dire=dire):
        jp.evenement("reglage", **x)


def main() -> None:
    a = _parse_args()
    if a.live and not a.yes:
        dire("⚠️  --live exige --yes (confirmation explicite). Abandon.")
        return
    dry = not (a.live and a.yes)
    _ouvrir_journal(a, dry)
    snap = _decision_snapshot()
    targets = snap["live"]["target_orders"]           # poids cibles (% du portefeuille)
    _diag_preset(snap, targets)
    from packages.execution.garde_fous import Collecteur
    from packages.execution.live_guards import fail_loud
    bus, alert_engine = _setup_alerts(dry)
    # TÉMOIN DES GARDE-FOUS. Injecté, jamais global : un état partagé entre deux runs
    # mélangerait leurs compteurs, et un test ne pourrait plus en isoler un seul.
    obs = Collecteur()
    reduce = _kill_switch(bus, obs)
    alpaca, bitmart, alp_cap, bit_cap, cur_alp, cur_bit, fatal = \
        _prepare_brokers(dry, a.equity, alert_engine)
    reduce = _reduction_risque(reduce, dry, (alp_cap, bit_cap), bus, alert_engine,
                               obs, targets)
    brokers = (("Alpaca", alpaca, alp_cap, cur_alp), ("Bitmart", bitmart, bit_cap, cur_bit))
    if not dry and not a.forcer and _deja_rebalance_aujourdhui(brokers, obs):
        _record_garde_fous(obs, dry)
        return                                     # doublon : on sort AVANT tout envoi
    if not dry and not a.forcer and _hors_cadence(brokers, reduce, obs):
        _record_garde_fous(obs, dry)
        return                                     # rythme de la règle mesurée
    cot_arrivee = _cotations_arrivee(targets, cur_alp, alpaca, dry)   # mesure seule
    swing, protect = _sleeve_swing(snap, alp_cap)
    if swing or protect:
        sent, opened, sold = _reconcilier_avec_sleeve(
            targets, swing, protect, (brokers, reduce, alert_engine, dry, obs))
    else:
        sent, opened, sold = _reconcile(targets, brokers, reduce, alert_engine, dry, obs)
    # AVANT la journalisation : plus aucun garde-fou ne parle après `_reconcile`.
    _record_garde_fous(obs, dry)
    _dire_termine(sent, dry)
    if not dry:
        _attendre_les_fills(opened, sold, alpaca, bitmart)
        _journal_tca(snap, opened, sold, alpaca, cot_arrivee)  # coût réel par ordre
        _journal_opens(snap, opened, alpaca, bitmart)
        _journal_sells(snap, sold, alpaca, bitmart)
        _record_equity(alp_cap, bit_cap)
    _sync_obsidian()
    if fatal:              # après journal/equity : rien n'est perdu, mais le run est ROUGE
        fail_loud(fatal, alert_engine, code=4)


def _dire_termine(sent: int, dry: bool) -> None:
    dire(f"\nTerminé : {sent} ordre(s) de réconciliation envoyé(s) (paper, sans levier)."
         if not dry else "\nAperçu (dry-run). Réconciliation réelle : python3 "
         "scripts/run_live.py --live --yes")


def _reconcilier_avec_sleeve(targets, swing, protect, ctx) -> tuple[int, list, list]:
    """Preset qui PROTÈGE la sleeve, puis passe sleeve sans liquidation hors cible."""
    brokers, reduce, alert_engine, dry, obs = ctx
    if not swing:
        dire(f"sleeve swing: protect {len(protect)} symbole(s) journal (multi-jour)")
        return _reconcile(targets, brokers, reduce, alert_engine, dry, obs,
                          proteger=protect)
    dire(f"sleeve swing: {len(swing)} ordres (capital A)")
    sent, opened, sold = _reconcile(
        targets, brokers, reduce, alert_engine, dry, obs, proteger=protect)
    s2, o2, v2 = _reconcile(
        swing, brokers, reduce, alert_engine, dry, obs, liquider_hors_cible=False)
    return sent + s2, opened + o2, sold + v2


def _reduction_risque(reduce: float, dry: bool, caps: tuple, bus, alert_engine, obs,
                      targets: list) -> float:
    """Compose les kill-switches par `min` : drawdown réel (live), puis disjoncteur."""
    from packages.execution.live_guards import dd_kill_switch
    alp_cap, bit_cap = caps
    if not dry:                                   # kill-switch DRAWDOWN RÉEL (pas que TV)
        rel = releve_equity(alp_cap, bit_cap)     # même périmètre (QML-024)
        reduce = min(reduce, dd_kill_switch(sum(rel.values()), bus, alert_engine, obs,
                                            cles=set(rel)))
    # DISJONCTEUR JOURNALIER — second horizon : la perte du JOUR, pas le drawdown.
    # Désarmé par défaut (`QUANT_DISJONCTEUR=1` pour agir) : il OBSERVE d'abord, parce
    # que son déclenchement ferme les positions et qu'il n'a jamais tourné en réel.
    rel = releve_equity(alp_cap, bit_cap)
    reduce = min(reduce, _disjoncteur(sum(rel.values()), obs, cles=set(rel)))
    if reduce <= 0.0:                             # kill-switch total : AUCUN achat
        _exposition_gelee(targets, obs, dry)      # (les allègements de stratégie passent)
    return reduce


def _sleeve_swing(snap: dict, alp_cap: float) -> tuple[list, set]:
    """Arch A3+PR4 — Capital A : le preset protège la sleeve (snap ∪ journal
    multi-jour) ; la passe sleeve ne liquide rien hors cible. Rien à protéger → un seul
    `_reconcile` preset (bit-identique). Protège le journal même si
    `QUANT_SWING_PAPER` est éteint aujourd'hui."""
    from packages.execution.swing_sleeve import (
        load_swing_orders,
        merge_protect_symbols,
        sleeve_open_symbols,
    )
    swing = load_swing_orders(snap)
    for o in swing:
        _poids_swing(o, alp_cap)
        o.setdefault("strategy", "swing")
    try:
        from_journal = sleeve_open_symbols()
    except Exception:  # noqa: BLE001
        from_journal = set()
    return swing, merge_protect_symbols(swing, from_journal, normalize=_nsym)


def _poids_swing(o: dict, alp_cap: float) -> None:
    """Poids absent, illisible ou en pourcents avec un notionnel connu → recalculé
    en fraction du capital Alpaca (notionnel / capital)."""
    wp, notionnel = o.get("weight_pct"), o.get("notionnel")
    try:
        n = float(notionnel) if notionnel is not None else None
    except (TypeError, ValueError):
        n = None
    invalid = False
    try:
        wpf = float(wp) if wp is not None else None
        if wpf is not None and (wpf != wpf or wpf < 0):
            invalid = True
        if wpf is not None and wpf > 1.0 and n is not None and n > 0:
            invalid = True          # percent-like (>1) with known notionnel
    except (TypeError, ValueError):
        invalid = True
    if alp_cap > 0 and n is not None and n > 0 and (wp is None or invalid):
        o["weight_pct"] = n / alp_cap


if __name__ == "__main__":
    main()
