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
from datetime import UTC, datetime
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
from packages.execution.passage_cibles import (  # noqa: E402
    broker_targets as _broker_targets,
)
from packages.execution.passage_cibles import (  # noqa: E402, F401 — réexport
    cible_sous_garde,
    id_client,
    ordre_de_traitement,
    sleeve_geometry_missing,
)
from packages.execution.passage_cibles import nsym as _nsym  # noqa: E402
from packages.execution.passage_envoi import (  # noqa: E402, F401 — réexport
    envoyer as _envoyer,
)
from packages.execution.passage_envoi import (  # noqa: E402, F401 — réexport
    log_rejet as _log_rejet,
)
from packages.execution.passage_envoi import (  # noqa: E402, F401 — réexport
    recap_differes as _recap_differes,
)
from packages.execution.passage_reconcile import (  # noqa: E402
    reconcilier as _reconcile,
)


def _fills_achats(brokers: tuple, jour: str) -> dict:
    """Achats RÉELLEMENT exécutés `jour`, par (place, symbole canonique) :
    quantité + VWAP.

    C'est la VÉRITÉ TERRAIN de l'ouverture. La position du courtier ne l'est pas : elle
    porte la quantité TOTALE et le prix de revient MOYEN, et elle peut n'être pas encore
    rafraîchie à l'instant du run — l'achat devenait alors introuvable et n'était JAMAIS
    journalisé (mesuré le 03/09 : 30 symboles sur 87 couverts à moitié ou moins).

    Best-effort par courtier : un courtier muet n'empêche pas l'autre d'être lu."""
    from packages.execution.live_journal import agreger_achats
    out: dict = {}
    for bn, br in brokers:
        if br is None or not hasattr(br, "orders"):
            continue
        try:
            ordres = br.orders(limit=500)
        except Exception:  # noqa: BLE001
            continue                     # courtier muet : le repli position reste
        for sym, fill in agreger_achats(ordres, jour).items():
            out[(bn, sym)] = fill
    return out


def _positions_repli(brokers: tuple) -> dict:
    """Positions du courtier par (place, symbole canonique) — REPLI quand aucun
    fill n'est lisible.

    Approximation assumée (quantité totale, prix moyen) : mieux qu'une ouverture perdue,
    moins bon qu'un fill. Jamais prioritaire sur `_fills_achats`."""
    from packages.execution.live_journal import normaliser
    pos: dict = {}
    for bn, br in brokers:
        if br is None:
            continue
        try:
            detail = br.positions_detailed()
        except Exception:  # noqa: BLE001
            continue
        for p in detail:
            pos[(bn, normaliser(p["symbol"]))] = {"avg_price": p.get("avg_price"),
                                                  "qty": p.get("qty"),
                                                  "origine": "position"}
    return pos


def _garder_les_decisions(opens: list, jour: str) -> None:
    """Dépose sur disque ce que le robot savait en envoyant — pour le rattrapage d'après.

    Écrit pour TOUTES les ouvertures, y compris celles qui viennent d'être journalisées :
    un lot peut être réécrit plus tard (correction, reconstruction), et la décision, elle,
    n'existe qu'ici et qu'aujourd'hui. Le coût est nul, la perte serait définitive.

    Un échec d'écriture est ANNONCÉ. Un magasin muet ferait croire à une mémoire alimentée
    alors qu'elle est vide, et le manque ne se découvrirait qu'au moment d'entraîner."""
    try:
        from packages.execution.decisions_store import enregistrer
        if not enregistrer(opens, jour):
            dire("  ⚠ décisions du jour NON enregistrées (.cache en écriture ?) — "
                  "un rattrapage ultérieur écrira des lots SANS features.")
    except Exception as e:  # noqa: BLE001 — conserver un contexte ne casse jamais un run
        dire(f"  ⚠ décisions du jour non enregistrées ({str(e)[:60]}).")


def _dire_les_ouvertures(n: int, skipped: int, opens: list) -> None:
    """Combien d'ouvertures écrites, et LESQUELLES manquent.

    Le 22/09 cette ligne disait « 4 sans achat exécuté LISIBLE ce jour » — un nombre,
    sans un nom. On ne pouvait ni vérifier, ni rattraper, ni même savoir si c'étaient
    les mêmes titres d'un jour sur l'autre. Un défaut qu'on ne peut pas nommer ne se
    corrige pas : il se subit.
    """
    tete = f"Journal : {n} ouverture(s) enregistrée(s) (legacy=0, features de décision)"
    if not skipped:
        dire(tete + "."); return
    muets = sorted({o["symbol"] for o in opens if not o.get("fill")})
    dire(tete + f" · {skipped} SANS achat exécuté lisible"
          + (f" : {', '.join(muets[:10])}" if muets else "")
          + " — ni fill, ni position ; rien n'est inventé.")
    dire("    Rattrapage (le fill devient lisible après coup) : "
          "make completer-ouvertures")


def _ids_lisibles(brokers: tuple) -> set:
    """Identifiants des ordres que le courtier rend comme EXÉCUTÉS, à cet instant.

    `limit=100` et non 500 : on ne cherche que les ordres du jour, les plus récents, et
    cette lecture est répétée toutes les trois secondes pendant l'attente."""
    ids = set()
    for _bn, br in brokers:
        if br is None or not hasattr(br, "orders"):
            continue
        ids |= {str(o.get("id")) for o in (br.orders(limit=100) or []) if o.get("id")}
    return ids


def _attendre_les_fills(opened: list, sold: list, alpaca, bitmart) -> None:
    """Laisse au courtier le temps de CLÔTURER ce qu'on vient de lui envoyer.

    Placée entre l'exécution et la journalisation, jamais dans le chemin d'ordre : rien
    n'est envoyé, réduit ni décidé ici. Best-effort strict — une attente qui échoue
    journalise comme avant, elle ne peut pas coûter un run."""
    from packages.execution.attente_fills import DELAI_S, attendre, message
    brokers = (("Alpaca", alpaca), ("Bitmart", bitmart))
    noms = {o["order_id"]: o.get("broker_symbol") or o.get("symbol")
            for o in (list(opened) + list(sold)) if o.get("order_id")}
    # DÉLAI RÉGLABLE, ET `0` LE DÉSARME. Le module reste pur — c'est le script qui lit
    # l'environnement. `QUANT_ATTENTE_FILLS_S=0` rend l'ancien comportement (journaliser
    # tout de suite) sans toucher au code, et les tests s'en servent pour ne pas dormir.
    try:
        delai = max(0.0, float(os.environ.get("QUANT_ATTENTE_FILLS_S", DELAI_S)))
    except ValueError:
        delai = DELAI_S
    try:
        dire(message(attendre(lambda: _ids_lisibles(brokers), set(noms),
                               delai_s=delai), noms))
    except Exception as e:  # noqa: BLE001
        dire(f"Attente des fills : ignorée ({str(e)[:60]}).")


def _journal_opens(snap: dict, opened: list, alpaca, bitmart) -> None:
    """Journalise les ouvertures (`legacy=0`) : features de DÉCISION (snap) + faits de fill (broker).

    Ordre des sources de fill : fills d'achat du jour (vérité terrain), puis
    position (repli).

    Best-effort STRICT : ne lève jamais → ne peut pas bloquer l'exécution."""
    if not opened:
        return
    try:
        from packages.execution.live_journal import (
            feature_map,
            journal_opens,
            normaliser,
            regime_context,
        )
        from packages.storage import SqliteTradeJournal

        feats_by_sym = feature_map(snap)
        regime_lbl, regime_ctx = regime_context(snap)
        _series = (snap.get("dashboard") or {}).get("chart_series") or {}

        def _decision_px(sym):                        # dernier close CONNU à la décision
            bars = _series.get(sym) or []
            return float(bars[-1]["c"]) if bars else None

        # ts_arrival = instant de DÉCISION (features figées), pas le fill.
        # Meilleur PIT dispo : meta.generated_at du snapshot. Pas de mid/quotes inventés.
        _ts_arrival = None
        _raw_gen = (snap.get("meta") or {}).get("generated_at")
        if isinstance(_raw_gen, datetime):
            _ts_arrival = _raw_gen
        elif isinstance(_raw_gen, str) and _raw_gen:
            try:
                _ts_arrival = datetime.fromisoformat(_raw_gen.replace("Z", "+00:00"))
            except ValueError:
                _ts_arrival = None

        brokers = (("Alpaca", alpaca), ("Bitmart", bitmart))
        jour = datetime.now(UTC).date().isoformat()
        fills = _fills_achats(brokers, jour)
        repli = _positions_repli(brokers)

        def _fill(op):          # le fill du jour d'abord, la position ensuite
            cle = (op["venue"], normaliser(op["broker_symbol"]))
            return fills.get(cle) or repli.get(cle)
        def _merge_feats(op: dict) -> dict:
            """Features decision-time pour le journal — clés TCA figées, jamais inventées.

            Clés : rank_score, decision_price, target_weight, regime_expo, notionnel,
            ts_decision (ISO), expectancy_R / rr / p_calibrated / risk_$ / gain_attendu
            seulement si evaluate_setup (ou équivalent) les a fournis sur l'ordre.
            gain_attendu = expectancy_R * risk_$ ; JAMAIS REALIZED_PNL ni ASSUMED_EDGE.
            """
            feats = {**feats_by_sym.get(op["symbol"], {}), **regime_ctx}
            # rank_score : feature_map OU cible ouverte (preset attaché au snap)
            if "rank_score" not in feats:
                rs = op.get("rank_score")
                if isinstance(rs, (int, float)) and not isinstance(rs, bool) and rs == rs:
                    feats["rank_score"] = float(rs)
            tw = op.get("weight_pct")
            if isinstance(tw, (int, float)) and not isinstance(tw, bool) and tw == tw:
                feats["target_weight"] = float(tw)
            dpx = _decision_px(op["symbol"])
            if dpx is not None:
                feats["decision_price"] = float(dpx)
            # notionnel (orthographe FR) : qty fill × decision_price (prix de décision).
            # Pas de proxy |weight|×equity ici (non documenté) ; pas de PnL réalisé.
            fill = _fill(op)
            qty = float((fill or {}).get("qty") or 0.0)
            if dpx is not None and qty > 0:
                feats["notionnel"] = round(qty * float(dpx), 6)
            # ts_decision ISO — features_snapshot accepte cette seule string (TCA).
            # TradeRecord.ts_arrival reste la colonne dédiée (même instant).
            if _ts_arrival is not None:
                feats["ts_decision"] = _ts_arrival.isoformat()
            # evaluate_setup / sleeve géom : uniquement si déjà sur l'ordre — jamais inventé.
            # expectancy_R / p_calibrated / gain_attendu : HOLD (pas inventés ici).
            for k in ("expectancy_R", "rr", "p_calibrated", "risk_$",
                      "entry", "stop", "target"):
                v = op.get(k)
                if isinstance(v, (int, float)) and not isinstance(v, bool) and v == v:
                    feats[k] = float(v)
            # setup_id : exception str (même famille que ts_decision) — copie si non vide.
            _sid = op.get("setup_id")
            if isinstance(_sid, str) and _sid.strip():
                feats["setup_id"] = _sid.strip()
            # ts_decision depuis op seulement si feats ne l'a pas déjà (snap ISO prioritaire).
            if "ts_decision" not in feats:
                _td = op.get("ts_decision")
                if isinstance(_td, str) and _td.strip():
                    feats["ts_decision"] = _td.strip()
            er, risk = feats.get("expectancy_R"), feats.get("risk_$")
            if (isinstance(er, (int, float)) and isinstance(risk, (int, float))
                    and er == er and risk == risk):
                feats["gain_attendu"] = round(float(er) * float(risk), 6)
            # sinon : gain_attendu absent (null) — jamais de proxy
            return feats

        opens = []
        n_miss_rank_score = 0
        for op in opened:
            feats = _merge_feats(op)
            if "rank_score" not in feats:
                n_miss_rank_score += 1
            opens.append({
                "symbol": op["symbol"], "venue": op["venue"],
                "asset_class": op.get("asset_class"),
                "fill": _fill(op),
                "features": feats,
                "regime": regime_lbl,
                "strategy": op.get("strategy") or "preset",
                "order_id": op.get("order_id"),
                "ts_arrival": _ts_arrival,
            })
        if n_miss_rank_score:
            dire(f"Journal : n_miss_rank_score={n_miss_rank_score}/{len(opened)} "
                  f"(lookup screener/screen/target vide).")
        _garder_les_decisions(opens, jour)
        n = journal_opens(SqliteTradeJournal(), opens)
        _dire_les_ouvertures(n, len(opened) - n, opens)
    except Exception as e:  # noqa: BLE001
        dire(f"Journal : journalisation ignorée ({str(e)[:60]}).")


def _fill_vente_jour(br, bsym: str) -> dict | None:
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
                    and float(o.get("price") or 0) > 0 and (o.get("date") or "")[:10] == today):
                return {"price": float(o["price"]), "qty": float(o.get("qty") or 0)}
    except Exception:  # noqa: BLE001
        pass
    return None


def _exit_price(br, bsym: str) -> float:
    """Prix de sortie FACTUEL, par ordre de fiabilité : fill VENTE du jour (`orders`),
    sinon ticker broker (`last_price`), sinon prix courant de la position. 0.0 = inconnu
    (le lot restera OUVERT — on n'invente jamais un prix)."""
    if br is None:
        return 0.0
    fait = _fill_vente_jour(br, bsym)
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


def _journal_sells(snap: dict, sold: list, alpaca, bitmart) -> None:
    """Round-trip (P0-4 Phase 2) : ferme les lots du journal touchés par les VENTES envoyées.

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
            fait = _fill_vente_jour(br, s["broker_symbol"])
            if fait is not None:                 # fill réel citable → quantité VRAIE
                s["exit_price"], s["qty_reelle"] = fait["price"], fait["qty"]
            else:                                     # repli : ancien comportement
                s["exit_price"] = _exit_price(br, s["broker_symbol"])
        series = (snap.get("dashboard") or {}).get("chart_series") or {}
        orphelines: list[dict] = []
        n = close_sells(SqliteTradeJournal(), sold, series, orphelines=orphelines)
        skipped = sum(1 for s in sold if not s.get("exit_price"))
        dire(f"Journal : {n} lot(s) fermé(s) (round-trip, PnL/MFE/MAE)"
              + (f" · {skipped} vente(s) sans prix broker (lots laissés ouverts)." if skipped else "."))
        _dire_les_orphelines(orphelines)
    except Exception as e:  # noqa: BLE001
        dire(f"Journal : round-trip ignoré ({str(e)[:60]}).")


def _dire_les_orphelines(orphelines: list[dict]) -> None:
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


def _diag_preset(snap: dict, targets: list) -> None:
    """Dit POURQUOI le satellite actions est vide, au lieu de le laisser deviner.

    Le 26/08, un compte paper sans AUCUNE action a résisté à trois hypothèses
    successives (plancher, horaires de marché, mode léger) simplement parce que
    rien ne disait où la chaîne s'arrêtait. Affiché seulement en cas de problème."""
    # CHEMIN EXACT. `preset_diagnostic` est publié sous `dashboard`, pas à la racine :
    # le lire à la racine renvoyait toujours {} et affichait « aucun diagnostic publié »
    # alors qu'il existait. Repli sur la racine au cas où le schéma évoluerait.
    d = ((snap.get("dashboard") or {}).get("preset_diagnostic")
         or snap.get("preset_diagnostic") or {})
    # NE PAS compter les cibles par classe d'actifs : le CŒUR indiciel (QQQ) est
    # une action, donc un satellite vide passait pour rempli et le diagnostic se
    # taisait — le défaut qu'il devait justement révéler. Le signal direct est
    # l'étage « poids retenus », inscrit seulement si au moins une ligne sort.
    _ = targets          # conservé pour la signature ; le signal vient du diagnostic
    a_des_poids = any(e.get("etape") == "poids retenus"
                      for e in (d.get("etapes") or []))
    if a_des_poids and not d.get("bloque"):
        return
    dire("\n  DIAGNOSTIC DU SATELLITE ACTIONS")
    for e in d.get("etapes") or []:
        dire(f"    {e.get('etape', ''):<22} {e.get('detail', '')}")
    portes = d.get("portes") or {}
    if portes:
        tot = 1.0
        for v in portes.values():
            tot *= v
        detail = " × ".join(f"{k} {v:.3f}" for k, v in portes.items())
        dire(f"    {'exposition brute':<22} {detail}  =  {tot:.4f}")
    if d.get("arret"):
        dire(f"    ⛔ ARRÊT : {d['arret']}")
    elif not d.get("etapes"):
        dire("    (aucun diagnostic publié — snapshot antérieur à l'ADR-0044 ?)")
    elif not a_des_poids:
        dire("    (aucun poids produit, sans étage bloquant signalé — anomalie)")


def _prepare_brokers(dry: bool, cli_equity: float | None, alert_engine):
    """Brokers vétés + positions lues (inconnu ⇒ broker écarté). Cf. live_guards."""
    from packages.execution.live_guards import (
        current_values, fail_loud, simule, vet_brokers,
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


def _deja_rebalance_aujourdhui(brokers: tuple, obs=None) -> bool:
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


def _cotations_arrivee(targets: list, cur_alp: dict, alpaca, dry: bool) -> dict:
    """Bid / ask JUSTE AVANT l'envoi des ordres (Alpaca). MESURE seulement : rien n'en
    dépend dans la décision ni dans l'envoi, et une lecture ratée rend {}."""
    if dry or alpaca is None:
        return {}
    from packages.execution.cotations import cotations
    syms = {o.get("broker_symbol", o["symbol"]) for o in targets
            if o.get("capital") != "bitmart"} | set(cur_alp or {})
    return cotations(syms)


def _journal_tca(snap: dict, opened: list, sold: list, alpaca, arrivee: dict) -> None:
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


def _hors_cadence(brokers: tuple, reduce: float, obs=None) -> bool:
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
        dire("⚠️  --live exige --yes (confirmation explicite). Abandon."); return
    dry = not (a.live and a.yes)
    _ouvrir_journal(a, dry)
    snap = _decision_snapshot()
    targets = snap["live"]["target_orders"]                # poids cibles (% du portefeuille)
    _diag_preset(snap, targets)

    from packages.execution.garde_fous import Collecteur
    from packages.execution.live_guards import dd_kill_switch, fail_loud
    bus, alert_engine = _setup_alerts(dry)
    # TÉMOIN DES GARDE-FOUS. Injecté, jamais global : un état partagé entre deux runs
    # mélangerait leurs compteurs, et un test ne pourrait plus en isoler un seul.
    obs = Collecteur()
    reduce = _kill_switch(bus, obs)
    alpaca, bitmart, alp_cap, bit_cap, cur_alp, cur_bit, fatal = \
        _prepare_brokers(dry, a.equity, alert_engine)
    if not dry:                                                # kill-switch DRAWDOWN RÉEL (pas que TV)
        _rel = releve_equity(alp_cap, bit_cap)                 # même périmètre (QML-024)
        reduce = min(reduce, dd_kill_switch(sum(_rel.values()), bus, alert_engine, obs,
                                            cles=set(_rel)))
    # DISJONCTEUR JOURNALIER — second horizon : la perte du JOUR, pas le drawdown.
    # Désarmé par défaut (`QUANT_DISJONCTEUR=1` pour agir) : il OBSERVE d'abord, parce
    # que son déclenchement ferme les positions et qu'il n'a jamais tourné en réel.
    _rel = releve_equity(alp_cap, bit_cap)
    reduce = min(reduce, _disjoncteur(sum(_rel.values()), obs, cles=set(_rel)))
    if reduce <= 0.0:                                          # kill-switch total : AUCUN achat
        _exposition_gelee(targets, obs, dry)      # (les allègements de stratégie passent)

    brokers = (("Alpaca", alpaca, alp_cap, cur_alp), ("Bitmart", bitmart, bit_cap, cur_bit))
    if not dry and not a.forcer and _deja_rebalance_aujourdhui(brokers, obs):
        _record_garde_fous(obs, dry)
        return                                     # doublon : on sort AVANT tout envoi
    if not dry and not a.forcer and _hors_cadence(brokers, reduce, obs):
        _record_garde_fous(obs, dry)
        return                                     # rythme de la règle mesurée
    cot_arrivee = _cotations_arrivee(targets, cur_alp, alpaca, dry)   # mesure seule

    # Arch A3+PR4 — Capital A : preset protège sleeve (snap ∪ journal multi-jour) ;
    # pass sleeve sans liquidation hors-cible. Rien à protéger → un seul _reconcile
    # preset (bit-identique). Protect journal même si QUANT_SWING_PAPER OFF aujourd'hui.
    from packages.execution.swing_sleeve import (
        load_swing_orders, sleeve_open_symbols, merge_protect_symbols,
    )
    swing = load_swing_orders(snap)
    for o in swing:
        wp = o.get("weight_pct")
        notionnel = o.get("notionnel")
        try:
            n = float(notionnel) if notionnel is not None else None
        except (TypeError, ValueError):
            n = None
        missing = wp is None
        invalid = False
        try:
            wpf = float(wp) if wp is not None else None
            if wpf is not None and (not (wpf == wpf) or wpf < 0):
                invalid = True
            # percent-like (>1) with known notionnel → recompute as fraction
            if wpf is not None and wpf > 1.0 and n is not None and n > 0:
                invalid = True
        except (TypeError, ValueError):
            invalid = True
            wpf = None
        if alp_cap > 0 and n is not None and n > 0 and (missing or invalid):
            o["weight_pct"] = n / alp_cap
        o.setdefault("strategy", "swing")

    try:
        from_journal = sleeve_open_symbols()
    except Exception:
        from_journal = set()
    protect = merge_protect_symbols(swing, from_journal, normalize=_nsym)

    if swing:
        dire(f"sleeve swing: {len(swing)} ordres (capital A)")
        sent, opened, sold = _reconcile(
            targets, brokers, reduce, alert_engine, dry, obs, proteger=protect)
        s2, o2, v2 = _reconcile(
            swing, brokers, reduce, alert_engine, dry, obs, liquider_hors_cible=False)
        sent += s2
        opened.extend(o2)
        sold.extend(v2)
    elif protect:
        dire(f"sleeve swing: protect {len(protect)} symbole(s) journal (multi-jour)")
        sent, opened, sold = _reconcile(
            targets, brokers, reduce, alert_engine, dry, obs, proteger=protect)
    else:
        sent, opened, sold = _reconcile(targets, brokers, reduce, alert_engine, dry, obs)
    # AVANT la journalisation, et c'est voulu : plus aucun garde-fou ne parle après
    # `_reconcile`, tandis qu'un échec de `_journal_opens` emporterait sinon le
    # compte-rendu du run avec lui — sans une ligne pour le dire.
    _record_garde_fous(obs, dry)
    dire(f"\nTerminé : {sent} ordre(s) de réconciliation envoyé(s) (paper, sans levier)." if not dry else
          "\nAperçu (dry-run). Réconciliation réelle : python3 scripts/run_live.py --live --yes")

    if not dry:
        _attendre_les_fills(opened, sold, alpaca, bitmart)
        _journal_tca(snap, opened, sold, alpaca, cot_arrivee)  # coût réel par ordre
        _journal_opens(snap, opened, alpaca, bitmart)
        _journal_sells(snap, sold, alpaca, bitmart)
        _record_equity(alp_cap, bit_cap)
    _sync_obsidian()
    if fatal:                                        # après journal/equity : rien n'est perdu, mais le run est ROUGE
        fail_loud(fatal, alert_engine, code=4)


def _disjoncteur(equity: float, obs=None, cles: set | None = None) -> float:
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


def _exposition_gelee(targets: list, obs, dry: bool) -> None:
    """Kill-switch total : on annonce ce qui ne sera PAS acheté (QML-007).

    Ce n'est plus une sortie : la réconciliation suit, avec des cibles bornées au détenu
    (`cible_sous_garde`). Aucun achat ne part ; les allègements de la stratégie, eux,
    partent. Le compte-rendu des garde-fous est enregistré une fois, en fin de passage.
    `obs` et `dry` restent dans la signature pour les appelants existants.
    """
    _ = obs, dry
    for o in targets:
        dire(f"  {o['side'].upper():4s} {o.get('broker_symbol', o['symbol']):14s} "
              f"{o['broker']:8s} {o['weight_pct']*100:6.1f}%  achat bloqué (kill-switch)")
    dire("\n⛔ Kill-switch : aucun achat. Les allègements de stratégie partent ; "
          "aucune vente n'est forcée.")


def _record_garde_fous(obs, dry: bool) -> None:
    """Persiste le compte-rendu des garde-fous de CE run. Best-effort — jamais silencieux.

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

    `run_live` écrivait « bitmart » quand le snapshot écrivait la place active (« binance ») :
    deux périmètres dans une même série. Une place en bac à sable, ou vide, n'y figure pas —
    son solde n'est pas de l'argent du compte."""
    from packages.execution.venues import venue_crypto
    v = venue_crypto()
    out = {"alpaca": alp_cap}
    if bit_cap > 0 and not v.en_testnet():
        out[v.cle] = bit_cap
    return out


def _record_equity(alp_cap: float, bit_cap: float) -> None:
    """Enregistre l'equity RÉELLE du jour → alimente la courbe paper de `make rdv-paper`.

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


if __name__ == "__main__":
    main()
