"""Round-trip du journal paper (P0-4 Phase 2) — appariement des VENTES aux lots ouverts.

Séparation stricte des sources (anti-invention, garde-fou CLAUDE.md) :
- **lots ouverts** = `data/journal.db` (`legacy=0`, `exit_ts` NULL), écrits en Phase 1
  avec les features figées à la DÉCISION — jamais retouchées ici ;
- **faits de VENTE** = montant $ réellement envoyé par la réconciliation + prix broker
  au moment de l'exécution (vérité terrain). Pas de prix exploitable → lot laissé
  OUVERT, jamais estimé ;
- **MFE/MAE** = série OHLC du snapshot entre l'entrée et la sortie ; absente → None.

Appariement **FIFO** (le lot le plus ancien ferme d'abord). Vente partielle →
scission : un enregistrement FERMÉ (id suffixé `-Xn`, déterministe) porte la fraction
vendue, le lot restant garde son id (UPSERT idempotent) avec la quantité réduite.
Un re-run du même jour ne revend rien : la réconciliation recalcule le delta sur les
positions broker déjà réduites.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone

from packages.core.models import TradeRecord

_EPS = 1e-6


def open_lots(journal, instrument: str | None = None,
              venue: str | None = None) -> list[TradeRecord]:
    """Lots encore ouverts (`legacy=0`, sans exit), FIFO (entry_ts croissant).

    APPARIEMENT PAR SYMBOLE CANONIQUE, et c'est un CORRECTIF (03/09). La comparaison
    était `t.instrument == instrument`, exacte au caractère près. Or les lots crypto
    sont écrits « AVAX/USDC » tandis que les ventes reviennent d'Alpaca en « AVAXUSD » :
    aucune vente crypto ne pouvait donc fermer son lot. Mesuré ce jour-là sur le compte
    réel : 41,9 AVAX au journal contre 214,6 détenus, 7,2 LTC contre 37,1 — la poche
    crypto s'accumulait en orphelins depuis l'origine, sans qu'aucune erreur ne sorte.

    Le dépôt connaissait déjà ce piège ailleurs : `execution/routing` le documente avec
    l'incident du 27/08 (liquidation crypto bloquée par le calendrier NYSE parce
    qu'`AAVEUSD` n'était pas reconnu comme crypto). Même cause, autre symptôme.
    """
    from packages.research.biais_fermeture import symbole_canonique
    lots = [t for t in journal.all(legacy=False) if t.exit_ts is None]
    if instrument is not None:
        cible = symbole_canonique(instrument)
        lots = [t for t in lots if symbole_canonique(t.instrument) == cible]
    if venue is not None:
        lots = [t for t in lots if t.venue == venue]
    return sorted(lots, key=lambda t: t.entry_ts)


def mfe_mae(series: list[dict] | None, entry_ts: datetime, exit_ts: datetime,
            entry_price: float) -> tuple[float | None, float | None]:
    """(MFE, MAE) en fraction du prix d'entrée, barres [entrée, sortie] ; None sinon."""
    if not series or entry_price <= 0:
        return None, None
    d0, d1 = entry_ts.date().isoformat(), exit_ts.date().isoformat()
    win = [b for b in series if "t" in b and d0 <= b["t"][:10] <= d1]
    highs = [b["h"] for b in win if b.get("h")]
    lows = [b["l"] for b in win if b.get("l")]
    if not highs or not lows:
        return None, None
    return round(max(highs) / entry_price - 1, 6), round(min(lows) / entry_price - 1, 6)


def _close_record(lot: TradeRecord, qty: float, price: float, ts: datetime,
                  series: list[dict] | None, *,
                  split_id: str | None = None) -> TradeRecord:
    """TradeRecord FERMÉ pour `qty` du lot (features d'entrée conservées)."""
    fe, ae = mfe_mae(series, lot.entry_ts, ts, lot.entry_price)
    pnl = round((price - lot.entry_price) * qty, 6)
    return dataclasses.replace(
        lot, id=split_id or lot.id, qty=qty, exit_ts=ts, exit_price=price,
        exit_reason="reconciliation paper (reduce/close)",
        pnl_gross=pnl, pnl_net=pnl,      # paper Alpaca/Bitmart spot : frais inconnus
        pnl_pct=round(price / lot.entry_price - 1, 6) if lot.entry_price > 0 else None,
        is_win=pnl > 0, duration_s=max(0.0, (ts - lot.entry_ts).total_seconds()),
        mfe=fe, mae=ae)


def close_sells(journal, sells: list[dict], series_by_sym: dict | None = None,
                *, ts: datetime | None = None) -> int:
    """Apparie les ventes aux lots ouverts (FIFO). Retourne le nb de fermetures.

    `sells` : dicts {symbol, venue, exit_price, notional, qty_reelle?}. Sans
    `exit_price` > 0 la vente est IGNORÉE (lot ouvert — on n'invente jamais un prix).
    Vente excédant les ouverts : l'excédent est ignoré (position antérieure au
    journal Phase 1).

    QUANTITÉ FERMÉE : `qty_reelle` (le fill RÉEL cité par un ordre du courtier), quand
    fourni, prime STRICTEMENT sur `notional / exit_price` (le delta PLANIFIÉ par le
    rebalancement). Mesuré le 05/09 sur le compte réel (OSCR) : le delta planifié
    dépassait le fill réel de ~85 unités, et l'écart se fermait au journal comme s'il
    avait été vendu — du « réalisé » sans contrepartie. `notional` reste le repli pour
    les ventes sans ordre citable (ex. liquidation totale via `close_position`)."""
    ts = ts or datetime.now(timezone.utc)
    closed = 0
    for s in sells:
        price = float(s.get("exit_price") or 0.0)
        if price <= 0:
            continue
        qty_reelle = float(s.get("qty_reelle") or 0.0)
        if qty_reelle > _EPS:
            remaining = qty_reelle                    # fill RÉEL, prioritaire
        elif float(s.get("notional") or 0.0) > 0:
            remaining = float(s["notional"]) / price       # repli : delta planifié
        else:
            continue
        series = (series_by_sym or {}).get(s["symbol"])
        for lot in open_lots(journal, instrument=s["symbol"], venue=s.get("venue")):
            if remaining <= _EPS:
                break
            take = min(lot.qty, remaining)
            if take >= lot.qty * (1 - _EPS):                   # fermeture TOTALE du lot
                journal.append(_close_record(lot, lot.qty, price, ts, series),
                               legacy=False)
            else:                                              # PARTIELLE → scission
                n = 1 + sum(1 for t in journal.all(legacy=False)
                            if t.id.startswith(lot.id + "-X"))
                journal.append(_close_record(lot, take, price, ts, series,
                                             split_id=f"{lot.id}-X{n}"), legacy=False)
                journal.append(dataclasses.replace(lot, qty=round(lot.qty - take, 10)),
                               legacy=False)         # lot restant (même id, UPSERT)
            closed += 1
            remaining -= take
    return closed
