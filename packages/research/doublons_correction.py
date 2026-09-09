"""Doublons de fermeture — un ordre réel cité deux fois, une fois nommé, une fois pas.

Constat du 05/09, prouvé ORDRE PAR ORDRE sur AVAX/LINK/LTC (cf. `sur_fermeture.py`,
`diag_sur_fermeture.py`, et l'historique complet des ventes du courtier) :
`reconcilier_journal --appliquer` a posté des corrections NOMMÉES
(`reconciliation-journal:<uuid>`) qui citent un ordre de vente réel — sans retirer un
lot `-Xn` PRÉEXISTANT que l'ancien `close_sells` (avant le correctif du 05/09 sur
`qty_reelle`, cf. `live_roundtrip.py`) avait déjà fermé sur CE MÊME ordre, des
semaines plus tôt, en utilisant le delta PLANIFIÉ plutôt que le fill réel. Les deux
enregistrements restent côte à côte : le même ordre réel finance deux « réalisé »
distincts.

LA RÈGLE DE DÉTECTION, vérifiée à la main sur les six cas réels (AVAX ×3, LINK ×2,
LTC ×3, croisés contre l'historique complet des ordres du courtier — écart net
reconstruit à ±0,0001 unité du `sur_fermeture` publié par `sur_fermeture.py`) :
même symbole canonique, même DATE de sortie, même PRIX de sortie — un enregistrement
qui cite un ordre (`reconciliation-journal:<uuid>`), un qui n'en cite aucun. Le
second est le doublon : il a été écrit AVANT la correction, sur un ordre qu'elle a
depuis pleinement consommé.

CE QUE CETTE RÈGLE N'ATTRAPE PAS, ET C'EST VOULU :
  - Un couple où les DEUX enregistrements citent le MÊME uuid (LINK/LTC du 07-08,
    AVAX du 09-03) : fermeture multi-lots légitime d'un seul ordre — le piège déjà
    vérifié le 04/09 sur LINK (P0 posé puis retiré). Exiger que l'un cite un ordre ET
    l'autre aucun exclut ce cas par construction.
  - Une sortie sans homologue nommé à la MÊME date (LINK -X3/-X4/-X5, AVAX -X4/-X5,
    LTC -X4/-X5) : ce sont des ventes réelles NON doublées — cf. le résidu
    `vente_non_journalisee` de `sur_fermeture.py`, un problème différent (un trou,
    pas une invention) que ce module ne touche pas.
"""
from __future__ import annotations

from dataclasses import dataclass

from packages.core.models import TradeRecord
from packages.research.sur_fermeture import ordre_reference


def _canon(sym: str) -> str:
    from packages.research.biais_fermeture import symbole_canonique
    return symbole_canonique(sym or "")


def _memes_prix(a: float, b: float) -> bool:
    """Tolérance RELATIVE — jamais de comparaison nue sur des flottants accumulés."""
    return abs(a - b) <= 1e-4 * max(1.0, abs(a))


@dataclass(frozen=True)
class Doublon:
    """Un doublon détecté : la correction NOMMÉE qui a droit à l'ordre, et le lot
    SANS NOM qui l'avait déjà réclamé avant elle."""
    nomme: TradeRecord
    doublon: TradeRecord


def identifier(trades: list[TradeRecord]) -> list[Doublon]:
    """Doublons de fermeture : même symbole, même date+prix de sortie, un nommé + un
    sans nom. Ne regarde que les enregistrements FERMÉS (`exit_ts` non None)."""
    fermes = [t for t in trades if t.exit_ts is not None and t.exit_price is not None]
    nommes = [t for t in fermes if ordre_reference(t.exit_reason) is not None]
    sans_nom = [t for t in fermes if ordre_reference(t.exit_reason) is None]
    vus: set[str] = set()
    out: list[Doublon] = []
    for n in nommes:
        cle_n = (_canon(n.instrument), n.exit_ts.date())
        for s in sans_nom:
            if s.id in vus:
                continue
            if (_canon(s.instrument), s.exit_ts.date()) != cle_n:
                continue
            if not _memes_prix(n.exit_price, s.exit_price):
                continue
            out.append(Doublon(nomme=n, doublon=s))
            vus.add(s.id)
            break
    return out


def archive(d: Doublon) -> dict:
    """Trace JSON de la preuve avant retrait — la correction nommée ET le doublon."""
    def _brut(t: TradeRecord) -> dict:
        return {"id": t.id, "instrument": t.instrument, "qty": t.qty,
                "exit_ts": str(t.exit_ts), "exit_price": t.exit_price,
                "pnl_net": t.pnl_net, "exit_reason": t.exit_reason}
    return {"doublon": _brut(d.doublon), "correction_nommee": _brut(d.nomme)}
