"""Le rebalancement coûte-t-il plus qu'il ne rapporte ? — mesurer, ne pas déduire.

Question posée par l'utilisateur (04/09) : plutôt qu'un rebalancement vers les poids
cibles chaque jour, ne vaudrait-il pas mieux ne toucher une ligne que lorsqu'elle
s'approche de son TP ou de son SL, et laisser les autres courir ? Réponse honnête :
**aucune donnée pour trancher aujourd'hui.** Le journal de CETTE session est vide (0
trade) — c'est un conteneur cloud fraîchement cloné, pas la machine qui a réellement
tradé. La vraie histoire vit sur le Mac mini (et bientôt le VPS).

Ce module ne choisit rien : il mesure ce que le journal RÉEL, une fois branché,
permet de dire. Trois angles, chacun avec sa limite explicite :

  1. COÛT du turnover — nombre d'allers-retours, frais + slippage cumulés.
  2. DURÉE de détention — le rebalancement journalier coupe-t-il les trades tôt ?
  3. CAPTURE du potentiel — `pnl_pct / mfe` (MFE = excursion favorable max PENDANT
     la détention). Un ratio bas dit qu'une ligne est sortie loin de son meilleur
     point observé PENDANT qu'elle était ouverte. Ça ne dit PAS si elle serait allée
     plus loin après la sortie — cette information n'existe pas dans le schéma
     actuel (`mfe`/`mae` sont bornés à la fenêtre [entrée, sortie], cf.
     `packages/execution/live_roundtrip.py::mfe_mae`).

`exit_reason` est bien renseigné (`packages/execution/live_roundtrip.py::_close_record`)
mais porte TOUJOURS le même texte constant, « reconciliation paper (reduce/close) »,
qu'il s'agisse d'une ligne tombée à 0 dans les poids cibles ou d'un simple trim. Ce
n'est pas un trou de collecte : c'est la confirmation STRUCTURELLE qu'il n'existe
aujourd'hui aucune sortie déclenchée par un TP ou un SL dans le chemin live — une
seule cause de sortie existe, le rebalancement. Ce module compte le nombre de motifs
DISTINCTS observés plutôt que de supposer le résultat.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class AuditTurnover:
    n_trades: int
    n_jours_couverts: float
    frais_totaux: float
    duree_mediane_j: float | None
    taux_gain: float | None
    capture_mediane: float | None      # médiane de pnl_pct / mfe, trades avec mfe > 0
    n_capture_mesurable: int
    motifs_de_sortie: frozenset[str]   # distincts observés — voir le module docstring
    rendement_moyen_pct: float | None  # moyenne de pnl_pct
    profit_factor: float | None        # gains/pertes — rentable même si taux bas


def _jours(a: datetime, b: datetime) -> float:
    return max(0.0, (b - a).total_seconds() / 86400.0)


def _mediane(xs: list[float]) -> float | None:
    v = sorted(xs)
    n = len(v)
    if n == 0:
        return None
    m = n // 2
    return v[m] if n % 2 else (v[m - 1] + v[m]) / 2.0


def auditer(trades: list) -> AuditTurnover:
    """`trades` : `TradeRecord` (legacy=False). Les lots encore ouverts sont ignorés."""
    clos = [t for t in trades if t.exit_ts is not None]
    if not clos:
        return AuditTurnover(0, 0.0, 0.0, None, None, None, 0, frozenset(), None, None)

    debut = min(t.entry_ts for t in clos)
    fin = max(t.exit_ts for t in clos)
    frais = sum((t.fees or 0.0) + (t.slippage or 0.0) for t in clos)

    durees = [_jours(t.entry_ts, t.exit_ts) for t in clos if t.exit_ts]
    gains = [t.is_win for t in clos if t.is_win is not None]
    taux_gain = (sum(1 for g in gains if g) / len(gains)) if gains else None

    captures = [t.pnl_pct / t.mfe for t in clos
                if t.mfe is not None and t.mfe > 1e-9 and t.pnl_pct is not None]
    motifs = frozenset((t.exit_reason or "").strip() for t in clos
                       if (t.exit_reason or "").strip())

    pnls = [t.pnl_pct for t in clos if t.pnl_pct is not None]
    rendement_moyen = sum(pnls) / len(pnls) if pnls else None
    gains_ = sum(p for p in pnls if p > 0)
    pertes_ = -sum(p for p in pnls if p < 0)
    pf = (gains_ / pertes_) if pertes_ > 1e-9 else None

    return AuditTurnover(
        n_trades=len(clos), n_jours_couverts=round(_jours(debut, fin), 1),
        frais_totaux=round(frais, 2),
        duree_mediane_j=round(_mediane(durees), 2) if durees else None,
        taux_gain=round(taux_gain, 3) if taux_gain is not None else None,
        capture_mediane=round(_mediane(captures), 3) if captures else None,
        n_capture_mesurable=len(captures), motifs_de_sortie=motifs,
        rendement_moyen_pct=(round(rendement_moyen, 4)
                            if rendement_moyen is not None else None),
        profit_factor=round(pf, 2) if pf is not None else None,
    )


def rapport(a: AuditTurnover) -> str:
    if a.n_trades == 0:
        return ("UNCALIBRATED — aucun round-trip clos. Rien à mesurer : brancher le "
                "journal RÉEL (Mac mini / VPS) avant toute décision.")
    par_semaine = a.n_trades / max(a.n_jours_couverts, 1) * 7
    L = [f"{a.n_trades} round-trip(s) clos sur {a.n_jours_couverts} jour(s) "
         f"({par_semaine:.1f} / semaine).",
         f"Frais + slippage cumulés : {a.frais_totaux:.2f} $."]
    if a.duree_mediane_j is not None:
        L.append(f"Détention médiane : {a.duree_mediane_j:.1f} jour(s).")
    if a.taux_gain is not None:
        L.append(f"Taux de gain : {a.taux_gain * 100:.0f} %.")
    if a.rendement_moyen_pct is not None:
        L.append(f"Rendement moyen par trade : {a.rendement_moyen_pct * 100:+.2f} %.")
    if a.profit_factor is not None:
        v = "rentable malgré taux bas" if a.profit_factor > 1 else "perdant net"
        L.append(f"Profit factor (gains / pertes) : {a.profit_factor:.2f} ({v}).")
    if a.n_trades < 30:
        L.append(f"⚠ Échantillon de {a.n_trades} trade(s) : trop petit pour distinguer "
                 "un vrai effet du bruit. À reconfirmer avec plus de données.")
    if a.capture_mediane is not None:
        L.append("Capture médiane du potentiel observé (pnl / MFE) : "
                 f"{a.capture_mediane * 100:.0f} % sur {a.n_capture_mesurable} "
                 f"trade(s) mesurable(s).")
    else:
        L.append("Capture du potentiel : non mesurable "
                 "(MFE absent — série de prix non jointe).")
    if len(a.motifs_de_sortie) <= 1:
        L.append("⚠ Un seul motif de sortie observé dans tout le journal : le système "
                 "live n'a AUCUNE sortie déclenchée par un TP ou un SL aujourd'hui — "
                 "toute clôture vient du rebalancement vers les poids cibles.")
    else:
        L.append(f"Motifs de sortie distincts : {sorted(a.motifs_de_sortie)}.")
    return "\n".join(L)
