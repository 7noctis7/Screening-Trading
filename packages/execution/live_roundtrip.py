"""Round-trip du journal paper (P0-4 Phase 2) — appariement des VENTES aux lots ouverts.

Séparation stricte des sources (anti-invention, garde-fou CLAUDE.md) :
- **lots ouverts** = `data/journal.db`, `exit_ts` NULL, d'ORIGINE robot (`P-`/`C-`/`R-`,
  cf. `perimetre_journal`) — features d'entrée jamais retouchées ici ;
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
from packages.execution.costs import broker_charge

_EPS = 1e-6


def open_lots(journal, instrument: str | None = None,
              venue: str | None = None) -> list[TradeRecord]:
    """Lots du ROBOT encore ouverts (sans exit), FIFO (entry_ts croissant).

    LE PÉRIMÈTRE SE LIT SUR L'ORIGINE, PAS SUR `legacy`, ET C'EST UN CORRECTIF (22/09).
    Cette fonction lisait `all(legacy=False)`. Or `legacy` répond à une AUTRE question —
    « ce lot porte-t-il les features de la décision ? », celle de la calibration ML.
    `perimetre_journal` avait déjà nommé cette confusion le 17/09 et corrigé le panneau
    du site ; l'appariement des ventes, lui, était resté sur l'ancien axe.

    Conséquence mesurée le 22/09 sur le compte réel : les lots rejoués depuis
    l'historique des ordres du courtier (`reconstruire_journal`, préfixe `R-`) sont
    écrits `legacy=1` — ils n'ont pas de features, et c'est exact. Ils étaient donc
    INVISIBLES ici. Ce jour-là le robot a envoyé 5 ventes ; une seule a produit un
    aller-retour — la seule dont le lot venait d'une décision journalisée (`P-`). Les
    quatre autres ventes ont bien été exécutées chez le courtier, n'ont rien fermé au
    journal, et leurs lots sont restés OUVERTS : du réalisé perdu d'un côté, des
    positions fantômes de l'autre. C'est exactement le désordre que
    `reconstruire_journal` avait été écrit pour solder le 18/09, re-fabriqué par l'outil
    qui consomme sa sortie.

    CE QUI RESTE EXCLU, ET POURQUOI. `LEG-` (import historique) et les préfixes inconnus.
    Leur prix d'entrée n'est rattachable à aucun fill lisible — deux symboles y portent
    jusqu'à 1,9 fois leur achat. Les apparier à une vente RÉELLE attribuerait un prix
    d'entrée inventé à une sortie vraie, donc publierait un réalisé fabriqué. Ils ne
    sont pas écartés en silence pour autant : `close_sells` nomme les ventes restées
    sans lot.

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
    from packages.execution.perimetre_journal import pris_par_le_robot
    from packages.research.biais_fermeture import symbole_canonique
    lots = [t for t in journal.all()
            if t.exit_ts is None and pris_par_le_robot(t.id)]
    if instrument is not None:
        cible = symbole_canonique(instrument)
        lots = [t for t in lots if symbole_canonique(t.instrument) == cible]
    if venue is not None:
        lots = [t for t in lots if t.venue == venue]
    return sorted(lots, key=lambda t: t.entry_ts)


def mfe_mae(series: list[dict] | None, entry_ts: datetime, exit_ts: datetime,
            entry_price: float) -> tuple[float | None, float | None]:
    """(MFE, MAE) en fraction du prix d'entrée, sur les barres APRÈS le jour d'entrée.

    POURQUOI LE JOUR D'ENTRÉE EST EXCLU. L'exécution tombe une heure avant la clôture :
    le plus haut de la journée d'entrée est presque toujours ANTÉRIEUR à l'achat — un
    prix que la position n'a jamais pu toucher. L'inclure surestime la MFE, donc
    sous-estime la capture, exactement dans le sens qui fabriquerait la conclusion
    « nos sorties rendent les gains ».

    Mesuré le 10/09 : sur un achat à 100 le jour où le marché avait fait +8 % le matin
    avant de finir à +1,5 %, la capture d'une sortie à +1 % passait de **67 % à 12 %** —
    un facteur 5, du même ordre que le signal cherché.

    Conséquence assumée : un aller-retour intraday (entrée et sortie le même jour) rend
    `None`. Une excursion intraday ne se mesure pas sur des barres quotidiennes, et le
    dire vaut mieux que publier un chiffre qu'on ne peut pas défendre.
    """
    if not series or entry_price <= 0:
        return None, None
    d0, d1 = entry_ts.date().isoformat(), exit_ts.date().isoformat()
    win = [b for b in series if "t" in b and d0 < b["t"][:10] <= d1]
    highs = [b["h"] for b in win if b.get("h")]
    lows = [b["l"] for b in win if b.get("l")]
    if not highs or not lows:
        return None, None
    # BORNÉES À ZÉRO. Le chemin d'un trade commence au prix d'ENTRÉE : l'excursion
    # favorable minimale est nulle, l'adverse maximale l'est aussi. Sans ce bornage,
    # un titre qui gappe à la baisse sans jamais revenir rendait une MFE NÉGATIVE —
    # « maximum favorable excursion » défavorable, une contradiction dans les termes.
    # Mesuré le 10/09 : BTC/USDC −0,35 %, LTC/USDC −2,28 %, AVAX/USDC −2,30 %.
    return (round(max(0.0, max(highs) / entry_price - 1), 6),
            round(min(0.0, min(lows) / entry_price - 1), 6))


def _close_record(lot: TradeRecord, qty: float, price: float, ts: datetime,
                  series: list[dict] | None, *,
                  split_id: str | None = None) -> TradeRecord:
    """TradeRecord FERMÉ pour `qty` du lot (features d'entrée conservées)."""
    fe, ae = mfe_mae(series, lot.entry_ts, ts, lot.entry_price)
    pnl = round((price - lot.entry_price) * qty, 6)
    # COMMISSION ESTIMÉE des DEUX jambes, marquée `estimated`. Celle de l'entrée est
    # déjà portée par le lot ; on y ajoute celle de la sortie (le réglementaire SEC/TAF
    # ne frappe QU'À la vente). Ne JAMAIS retrancher le slippage ici : il est déjà
    # contenu dans les deux prix de fill, donc déjà dans `pnl` — le retrancher
    # compterait deux fois le même coût.
    classe = getattr(lot.asset_class, "value", str(lot.asset_class))
    charge = round((lot.fees or 0.0) + broker_charge(classe, price * qty, side="SELL"), 6)
    return dataclasses.replace(
        lot, id=split_id or lot.id, qty=qty, exit_ts=ts, exit_price=price,
        exit_reason="reconciliation paper (reduce/close)",
        fees=charge, fees_source="estimated",
        pnl_gross=pnl, pnl_net=round(pnl - charge, 6),
        pnl_pct=round(price / lot.entry_price - 1, 6) if lot.entry_price > 0 else None,
        is_win=pnl > 0, duration_s=max(0.0, (ts - lot.entry_ts).total_seconds()),
        mfe=fe, mae=ae)


def _quantite_vendue(s: dict) -> float:
    """Unités à fermer pour cette vente, ou 0.0 si la vente n'est pas exploitable.

    `qty_reelle` (le fill RÉEL cité par un ordre du courtier) prime STRICTEMENT sur
    `notional / exit_price` (le delta PLANIFIÉ par le rebalancement). Mesuré le 05/09
    sur le compte réel (OSCR) : le delta planifié dépassait le fill réel de ~85 unités,
    et l'écart se fermait au journal comme s'il avait été vendu — du « réalisé » sans
    contrepartie. `notional` reste le repli pour les ventes sans ordre citable
    (ex. liquidation totale via `close_position`).
    """
    prix = float(s.get("exit_price") or 0.0)
    if prix <= 0:
        return 0.0
    qty_reelle = float(s.get("qty_reelle") or 0.0)
    if qty_reelle > _EPS:
        return qty_reelle
    notional = float(s.get("notional") or 0.0)
    return notional / prix if notional > 0 else 0.0


def close_sells(journal, sells: list[dict], series_by_sym: dict | None = None,
                *, ts: datetime | None = None,
                orphelines: list[dict] | None = None) -> int:
    """Apparie les ventes aux lots ouverts du ROBOT (FIFO). Rend le nb de fermetures.

    `sells` : dicts {symbol, venue, exit_price, notional, qty_reelle?}. Sans
    `exit_price` > 0 la vente est IGNORÉE (lot ouvert — on n'invente jamais un prix).

    `orphelines`, s'il est fourni, REÇOIT LES VENTES QUI N'ONT RIEN FERMÉ, en tout ou en
    partie : `{"symbol", "venue", "qty_demandee", "qty_fermee"}`. Sans cette liste, un
    appariement qui échoue est indiscernable d'un appariement qui n'avait rien à faire —
    et c'est précisément ce silence qui a laissé quatre ventes réelles sans aller-retour
    le 22/09 sans qu'aucune ligne ne sorte. L'excédent d'une vente sur les lots ouverts
    (position antérieure au journal) y figure donc aussi : au retour, l'appelant a de
    quoi dire CE QU'IL N'A PAS SU FERMER.

    LE DRAPEAU `legacy` DU LOT EST CONSERVÉ. Il dit « ce lot porte-t-il les features de
    la décision ? » ; le réécrire à 0 en fermant un lot rejoué (`R-`, sans features)
    ferait entrer dans l'échantillon de calibration ML des enregistrements qui n'en ont
    pas — et `append` fait un UPSERT où `legacy` est dans les colonnes mises à jour.
    """
    ts = ts or datetime.now(timezone.utc)
    anciens_legacy = set(journal.legacy_ids()) if hasattr(journal, "legacy_ids") else set()
    closed = 0
    for s in sells:
        demande = _quantite_vendue(s)
        if demande <= _EPS:
            continue
        price = float(s["exit_price"])
        series = (series_by_sym or {}).get(s["symbol"])
        remaining = demande
        for lot in open_lots(journal, instrument=s["symbol"], venue=s.get("venue")):
            if remaining <= _EPS:
                break
            remaining -= _fermer(journal, lot, remaining, price, ts, series,
                                 legacy=lot.id in anciens_legacy)
            closed += 1
        if remaining > _EPS and orphelines is not None:
            orphelines.append({"symbol": s["symbol"], "venue": s.get("venue"),
                               "qty_demandee": round(demande, 6),
                               "qty_fermee": round(demande - remaining, 6)})
    return closed


def _fermer(journal, lot: TradeRecord, remaining: float, price: float,
            ts: datetime, series: list[dict] | None, *, legacy: bool) -> float:
    """Ferme tout ou partie de `lot` et rend la quantité effectivement fermée."""
    take = min(lot.qty, remaining)
    if take >= lot.qty * (1 - _EPS):                       # fermeture TOTALE du lot
        journal.append(_close_record(lot, lot.qty, price, ts, series), legacy=legacy)
        return lot.qty
    n = 1 + sum(1 for t in journal.all()                   # PARTIELLE → scission
                if t.id.startswith(lot.id + "-X"))
    journal.append(_close_record(lot, take, price, ts, series,
                                 split_id=f"{lot.id}-X{n}"), legacy=legacy)
    journal.append(dataclasses.replace(lot, qty=round(lot.qty - take, 10)),
                   legacy=legacy)                          # lot restant (même id, UPSERT)
    return take
