"""Journal des OUVERTURES d'un passage : fills, repli position, features de décision.

Extrait de `scripts/run_live.py` (audit du 06/10). `_journal_opens` (123 lignes, une
fonction imbriquée de 52) devient `journal_opens` + un `_Contexte` : mêmes clés, mêmes
sources, même ordre de priorité. Best-effort strict : rien ici ne bloque un passage.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime

from packages.common.journal_passage import dire


def fills_achats(brokers: tuple, jour: str) -> dict:
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


def positions_repli(brokers: tuple) -> dict:
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


def garder_les_decisions(opens: list, jour: str) -> None:
    """Dépose sur disque ce que le robot savait en envoyant — pour le rattrapage.

    Écrit pour TOUTES les ouvertures, y compris celles qui viennent d'être
    journalisées : un lot peut être réécrit plus tard (correction, reconstruction), et
    la décision, elle, n'existe qu'ici et qu'aujourd'hui. Le coût est nul, la perte
    serait définitive.

    Un échec d'écriture est ANNONCÉ. Un magasin muet ferait croire à une mémoire
    alimentée alors qu'elle est vide, et le manque ne se découvrirait qu'au moment
    d'entraîner."""
    try:
        from packages.execution.decisions_store import enregistrer
        if not enregistrer(opens, jour):
            dire("  ⚠ décisions du jour NON enregistrées (.cache en écriture ?) — "
                  "un rattrapage ultérieur écrira des lots SANS features.")
    except Exception as e:  # noqa: BLE001 — conserver un contexte ne casse jamais un run
        dire(f"  ⚠ décisions du jour non enregistrées ({str(e)[:60]}).")


def dire_les_ouvertures(n: int, skipped: int, opens: list) -> None:
    """Combien d'ouvertures écrites, et LESQUELLES manquent.

    Le 22/09 cette ligne disait « 4 sans achat exécuté LISIBLE ce jour » — un nombre,
    sans un nom. On ne pouvait ni vérifier, ni rattraper, ni même savoir si c'étaient
    les mêmes titres d'un jour sur l'autre. Un défaut qu'on ne peut pas nommer ne se
    corrige pas : il se subit.
    """
    tete = f"Journal : {n} ouverture(s) enregistrée(s) (legacy=0, features de décision)"
    if not skipped:
        dire(tete + ".")
        return
    muets = sorted({o["symbol"] for o in opens if not o.get("fill")})
    dire(tete + f" · {skipped} SANS achat exécuté lisible"
          + (f" : {', '.join(muets[:10])}" if muets else "")
          + " — ni fill, ni position ; rien n'est inventé.")
    dire("    Rattrapage (le fill devient lisible après coup) : "
          "make completer-ouvertures")


def ids_lisibles(brokers: tuple) -> set:
    """Identifiants des ordres que le courtier rend comme EXÉCUTÉS, à cet instant.

    `limit=100` et non 500 : on ne cherche que les ordres du jour, les plus récents, et
    cette lecture est répétée toutes les trois secondes pendant l'attente."""
    ids = set()
    for _bn, br in brokers:
        if br is None or not hasattr(br, "orders"):
            continue
        ids |= {str(o.get("id")) for o in (br.orders(limit=100) or []) if o.get("id")}
    return ids


def attendre_les_fills(opened: list, sold: list, alpaca, bitmart) -> None:
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
        dire(message(attendre(lambda: ids_lisibles(brokers), set(noms),
                               delai_s=delai), noms))
    except Exception as e:  # noqa: BLE001
        dire(f"Attente des fills : ignorée ({str(e)[:60]}).")


def journal_opens(snap: dict, opened: list, alpaca, bitmart) -> None:
    """Journalise les ouvertures (`legacy=0`) : features de DÉCISION (snap) + faits de
    fill (broker).

    Ordre des sources de fill : fills d'achat du jour (vérité terrain), puis
    position (repli).

    Best-effort STRICT : ne lève jamais → ne peut pas bloquer l'exécution."""
    if not opened:
        return
    try:
        from packages.execution.live_journal import journal_opens as ecrire
        from packages.storage import SqliteTradeJournal
        ctx = _Contexte.depuis(snap, alpaca, bitmart)
        opens, n_miss_rank_score = [], 0
        for op in opened:
            feats = ctx.features(op)
            if "rank_score" not in feats:
                n_miss_rank_score += 1
            opens.append({
                "symbol": op["symbol"], "venue": op["venue"],
                "asset_class": op.get("asset_class"),
                "fill": ctx.fill(op),
                "features": feats,
                "regime": ctx.regime_lbl,
                "strategy": op.get("strategy") or "preset",
                "order_id": op.get("order_id"),
                "ts_arrival": ctx.ts_arrival,
            })
        if n_miss_rank_score:
            dire(f"Journal : n_miss_rank_score={n_miss_rank_score}/{len(opened)} "
                 f"(lookup screener/screen/target vide).")
        garder_les_decisions(opens, ctx.jour)
        n = ecrire(SqliteTradeJournal(), opens)
        dire_les_ouvertures(n, len(opened) - n, opens)
    except Exception as e:  # noqa: BLE001
        dire(f"Journal : journalisation ignorée ({str(e)[:60]}).")


def _instant_decision(snap: dict):
    """ts_arrival = instant de DÉCISION (features figées), pas le fill. Meilleur PIT
    disponible : meta.generated_at du snapshot. Pas de mid/quotes inventés."""
    brut = (snap.get("meta") or {}).get("generated_at")
    if isinstance(brut, datetime):
        return brut
    if isinstance(brut, str) and brut:
        try:
            return datetime.fromisoformat(brut.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _nombre(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v


def _texte(v) -> bool:
    return isinstance(v, str) and bool(v.strip())


@dataclass
class _Contexte:
    """Ce que le passage savait au moment de décider, et ce que le courtier a rempli."""

    feats_by_sym: dict
    regime_lbl: object
    regime_ctx: dict
    series: dict
    ts_arrival: object
    jour: str
    fills: dict
    repli: dict

    @classmethod
    def depuis(cls, snap: dict, alpaca, bitmart) -> _Contexte:
        from packages.execution.live_journal import feature_map, regime_context
        regime_lbl, regime_ctx = regime_context(snap)
        brokers = (("Alpaca", alpaca), ("Bitmart", bitmart))
        jour = datetime.now(UTC).date().isoformat()
        return cls(feature_map(snap), regime_lbl, regime_ctx,
                   (snap.get("dashboard") or {}).get("chart_series") or {},
                   _instant_decision(snap), jour, fills_achats(brokers, jour),
                   positions_repli(brokers))

    def decision_px(self, sym):                   # dernier close CONNU à la décision
        bars = self.series.get(sym) or []
        return float(bars[-1]["c"]) if bars else None

    def fill(self, op):         # le fill du jour d'abord, la position ensuite
        from packages.execution.live_journal import normaliser
        cle = (op["venue"], normaliser(op["broker_symbol"]))
        return self.fills.get(cle) or self.repli.get(cle)

    def features(self, op: dict) -> dict:
        """Features decision-time pour le journal — clés TCA figées, jamais inventées.

        Clés : rank_score, decision_price, target_weight, regime_expo, notionnel,
        ts_decision (ISO), expectancy_R / rr / p_calibrated / risk_$ / gain_attendu
        seulement si evaluate_setup (ou équivalent) les a fournis sur l'ordre.
        gain_attendu = expectancy_R * risk_$ ; JAMAIS REALIZED_PNL ni ASSUMED_EDGE.
        """
        feats = {**self.feats_by_sym.get(op["symbol"], {}), **self.regime_ctx}
        # rank_score : feature_map OU cible ouverte (preset attaché au snap)
        if "rank_score" not in feats and _nombre(op.get("rank_score")):
            feats["rank_score"] = float(op["rank_score"])
        if _nombre(op.get("weight_pct")):
            feats["target_weight"] = float(op["weight_pct"])
        dpx = self.decision_px(op["symbol"])
        if dpx is not None:
            feats["decision_price"] = float(dpx)
        # notionnel : qty fill × decision_price. Pas de proxy |weight|×equity.
        qty = float((self.fill(op) or {}).get("qty") or 0.0)
        if dpx is not None and qty > 0:
            feats["notionnel"] = round(qty * float(dpx), 6)
        # ts_decision ISO — TradeRecord.ts_arrival reste la colonne dédiée.
        if self.ts_arrival is not None:
            feats["ts_decision"] = self.ts_arrival.isoformat()
        return _completer(feats, op)


def _completer(feats: dict, op: dict) -> dict:
    """Géométrie et espérance UNIQUEMENT si déjà sur l'ordre — jamais inventées."""
    for k in ("expectancy_R", "rr", "p_calibrated", "risk_$", "entry", "stop",
              "target"):
        if _nombre(op.get(k)):
            feats[k] = float(op[k])
    if _texte(op.get("setup_id")):
        feats["setup_id"] = op["setup_id"].strip()
    # ts_decision depuis op seulement si feats ne l'a pas déjà (snap ISO prioritaire).
    if "ts_decision" not in feats and _texte(op.get("ts_decision")):
        feats["ts_decision"] = op["ts_decision"].strip()
    er, risk = feats.get("expectancy_R"), feats.get("risk_$")
    if (isinstance(er, (int, float)) and isinstance(risk, (int, float))
            and er == er and risk == risk):
        feats["gain_attendu"] = round(float(er) * float(risk), 6)
    return feats                     # sinon : gain_attendu absent — jamais de proxy
