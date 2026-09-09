"""Le rebalancement coûte-t-il plus qu'il ne rapporte ? — mesurer, ne pas déduire.

Question posée par l'utilisateur (04/09) : plutôt qu'un rebalancement vers les poids
cibles chaque jour, ne vaudrait-il pas mieux ne toucher une ligne que lorsqu'elle
s'approche de son TP ou de son SL, et laisser les autres courir ?

TROIS PIÈGES DE COMPTAGE, découverts sur le journal RÉEL du Mac mini (04/09), qui
faisaient dire à la première version de ce module +10,26 % par trade, profit factor
15 et t = 5,50 — des chiffres flatteurs et faux :

  1. UNE POSITION VENDUE EN PLUSIEURS FOIS N'EST PAS PLUSIEURS TRADES. `close_sells`
     scinde un lot soldé en tranches (`<lot>-X1`, `-X2`, …), chacune écrite comme un
     enregistrement fermé portant la MÊME entrée. Huit lots crypto ouverts le 07/07
     revenaient ainsi six fois chacun, avec leur +25 à +47 %. Compter les tranches
     gonfle n, donc |t| (qui croît en racine de n), donc la « significativité ».
     On agrège désormais par lot d'origine, pondéré par la quantité.

  2. TOUTES LES SORTIES NE SONT PAS DES DÉCISIONS DE STRATÉGIE. Les motifs
     `reconciliation-journal:<uuid>` viennent du script de réparation qui a fermé des
     lots orphelins à partir des fills courtier : la sortie a bien eu lieu, mais sa
     date et son prix sont reconstruits après coup, pas choisis par le système. On les
     compte à part au lieu de les mélanger silencieusement.

  3. LES PERDANTS ENCORE OUVERTS NE SONT NULLE PART. Ce module, comme le panneau du
     tableau de bord, ne voit que les lots CLOS — le taux de réussite est donc biaisé
     à la hausse par construction. Dit ici, pas caché.

Ce que le module mesure, avec ses limites :

  1. COÛT du turnover — allers-retours, frais + slippage cumulés.
  2. DURÉE de détention — le rebalancement coupe-t-il les trades tôt ?
  3. CAPTURE du potentiel — `pnl_pct / mfe` (MFE = excursion favorable max PENDANT la
     détention). Négative = la ligne est passée en positif puis sortie en perte. Ne
     dit RIEN de l'après-sortie : `mfe`/`mae` sont bornés à [entrée, sortie]
     (cf. `packages/execution/live_roundtrip.py::mfe_mae`).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime

_SPLIT = re.compile(r"-X\d+$")
_ADMIN = "reconciliation-journal:"


@dataclass(frozen=True, slots=True)
class AuditTurnover:
    n_positions: int                   # lots d'origine (tranches regroupées)
    n_fermetures: int                  # enregistrements clos (tranches comprises)
    n_administratives: int             # fermetures reconstruites après coup
    n_jours_couverts: float
    frais_totaux: float
    duree_mediane_j: float | None
    taux_gain: float | None
    capture_mediane: float | None      # médiane de pnl_pct / mfe, positions mfe > 0
    n_capture_mesurable: int
    motifs_de_sortie: frozenset[str]
    rendement_moyen_pct: float | None  # moyenne PAR POSITION, pas par tranche
    profit_factor: float | None
    rendement_tstat: float | None      # t-stat vs 0, sur les positions (ADR-0072)
    rendement_significatif: bool


def _jours(a: datetime, b: datetime) -> float:
    return max(0.0, (b - a).total_seconds() / 86400.0)


def _mediane(xs: list[float]) -> float | None:
    v = sorted(xs)
    n = len(v)
    if n == 0:
        return None
    m = n // 2
    return v[m] if n % 2 else (v[m - 1] + v[m]) / 2.0


def _lot_origine(identifiant: str) -> str:
    """`abc-X3` → `abc`. Les tranches d'une même vente partagent une seule entrée."""
    return _SPLIT.sub("", identifiant or "")


def _tstat_vs_zero(xs: list[float]) -> tuple[float | None, bool]:
    """t-stat de la moyenne vs 0 — MÊME test que l'alpha du dashboard (ADR-0072).
    Sur les POSITIONS : sur les tranches, |t| serait gonflé par un n artificiel."""
    n = len(xs)
    if n < 2:
        return None, False
    m = sum(xs) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))
    se = sd / math.sqrt(n)
    if se <= 1e-12:
        return None, False
    t = m / se
    return round(t, 2), abs(t) >= 2.0


def _agreger(clos: list) -> list[dict]:
    """Tranches → positions. Rendement pondéré par la quantité, durée la plus longue."""
    par_lot: dict[str, list] = {}
    for t in clos:
        par_lot.setdefault(_lot_origine(t.id), []).append(t)
    positions = []
    for tranches in par_lot.values():
        qtes = [abs(t.qty or 0.0) for t in tranches]
        poids = sum(qtes) or float(len(tranches))
        pnls = [(t.pnl_pct, q) for t, q in zip(tranches, qtes, strict=False)
                if t.pnl_pct is not None]
        total_q = sum(q or 1.0 for _, q in pnls) or 1.0
        pnl = (sum(p * (q or 1.0) for p, q in pnls) / total_q) if pnls else None
        mfes = [t.mfe for t in tranches if t.mfe is not None]
        durees = [t.duration_s for t in tranches if t.duration_s is not None]
        positions.append({
            "pnl_pct": pnl, "poids": poids, "tranches": tranches,
            "mfe": max(mfes) if mfes else None,
            "duree_j": (max(durees) / 86400.0) if durees else None,
            "admin": any((t.exit_reason or "").startswith(_ADMIN) for t in tranches),
        })
    return positions


def auditer(trades: list, *, seulement: str | None = None) -> AuditTurnover:
    """`trades` : `TradeRecord` (legacy=False). Les lots encore ouverts sont ignorés.

    `seulement="systeme"` ne garde que les positions fermées par une DÉCISION du
    système ; `"administratif"` que celles reconstruites après coup par le script de
    réparation. C'est la séparation qui compte : sur le journal réel du 04/09, 31
    positions sur 37 étaient administratives — les mélanger faisait passer un rallye
    crypto réparé a posteriori pour la performance de la stratégie."""
    clos_tout = [t for t in trades if t.exit_ts is not None]
    pos = _agreger(clos_tout)
    if seulement == "systeme":
        pos = [p for p in pos if not p["admin"]]
    elif seulement == "administratif":
        pos = [p for p in pos if p["admin"]]
    clos = [t for p in pos for t in p["tranches"]]
    if not clos:
        return AuditTurnover(0, 0, 0, 0.0, 0.0, None, None, None, 0, frozenset(),
                             None, None, None, False)

    pnls = [p["pnl_pct"] for p in pos if p["pnl_pct"] is not None]
    gains_ = sum(x for x in pnls if x > 0)
    pertes_ = -sum(x for x in pnls if x < 0)
    captures = [p["pnl_pct"] / p["mfe"] for p in pos if p["mfe"] is not None
                and p["mfe"] > 1e-9 and p["pnl_pct"] is not None]
    durees = [p["duree_j"] for p in pos if p["duree_j"] is not None]
    tstat, signif = _tstat_vs_zero(pnls)

    return AuditTurnover(
        n_positions=len(pos), n_fermetures=len(clos),
        n_administratives=sum(1 for p in pos if p["admin"]),
        n_jours_couverts=round(_jours(min(t.entry_ts for t in clos),
                                      max(t.exit_ts for t in clos)), 1),
        frais_totaux=round(sum((t.fees or 0.0) + (t.slippage or 0.0) for t in clos), 2),
        duree_mediane_j=round(_mediane(durees), 2) if durees else None,
        taux_gain=round(sum(1 for x in pnls if x > 0) / len(pnls), 3) if pnls else None,
        capture_mediane=round(_mediane(captures), 3) if captures else None,
        n_capture_mesurable=len(captures),
        motifs_de_sortie=frozenset((t.exit_reason or "").strip() for t in clos
                                   if (t.exit_reason or "").strip()),
        rendement_moyen_pct=round(sum(pnls) / len(pnls), 4) if pnls else None,
        profit_factor=round(gains_ / pertes_, 2) if pertes_ > 1e-9 else None,
        rendement_tstat=tstat, rendement_significatif=signif,
    )


def _lignes_comptage(a: AuditTurnover) -> list[str]:
    par_sem = a.n_positions / max(a.n_jours_couverts, 1) * 7
    L = [f"{a.n_positions} position(s) close(s) sur {a.n_jours_couverts} jour(s) "
         f"({par_sem:.1f} / semaine)."]
    if a.n_fermetures != a.n_positions:
        L.append(f"  ({a.n_fermetures} enregistrements — une vente en plusieurs fois "
                 f"est UNE position, pas plusieurs trades.)")
    if a.n_administratives:
        L.append(f"⚠ {a.n_administratives} position(s) fermée(s) par le script de "
                 "réconciliation (date et prix reconstruits après coup, pas une "
                 "décision du système).")
    return L


def rapport(a: AuditTurnover) -> str:
    if a.n_positions == 0:
        return ("UNCALIBRATED — aucun round-trip clos. Rien à mesurer : brancher le "
                "journal RÉEL (Mac mini / VPS) avant toute décision.")
    L = _lignes_comptage(a)
    L.append(f"Frais + slippage cumulés : {a.frais_totaux:.2f} $.")
    if a.duree_mediane_j is not None:
        L.append(f"Détention médiane : {a.duree_mediane_j:.1f} jour(s).")
    if a.taux_gain is not None:
        L.append(f"Taux de gain : {a.taux_gain * 100:.0f} % "
                 "(biaisé à la hausse : les perdants encore OUVERTS n'y sont pas).")
    if a.rendement_moyen_pct is not None:
        L.append("Rendement moyen par position : "
                 f"{a.rendement_moyen_pct * 100:+.2f} %.")
    if a.rendement_tstat is not None:
        etat = ("significatif" if a.rendement_significatif
                else "NON significatif (bruit ?)")
        L.append(f"Significativité (t-stat vs 0, |t|≥2) : {a.rendement_tstat:+.2f} "
                 f"({etat}).")
    if a.profit_factor is not None:
        v = "positif" if a.profit_factor > 1 else "perdant net"
        L.append(f"Profit factor (gains / pertes) : {a.profit_factor:.2f} ({v}).")
    if a.n_positions < 30:
        L.append(f"⚠ Échantillon de {a.n_positions} position(s) : trop petit pour "
                 "distinguer un vrai effet du bruit.")
    if a.capture_mediane is not None:
        L.append(f"Capture médiane du potentiel (pnl / MFE) : "
                 f"{a.capture_mediane * 100:.0f} % sur {a.n_capture_mesurable} "
                 "position(s) mesurable(s)"
                 + (" — NÉGATIVE : passées en positif puis sorties en perte."
                    if a.capture_mediane < 0 else "."))
    else:
        L.append("Capture du potentiel : non mesurable (MFE absent).")
    strategie = {m for m in a.motifs_de_sortie if not m.startswith(_ADMIN)}
    if len(strategie) <= 1:
        L.append("⚠ Un seul motif de sortie côté système : aucune sortie déclenchée "
                 "par un TP ou un SL — toute clôture vient du rebalancement.")
    return "\n".join(L)


def rapport_complet(trades: list) -> str:
    """Deux blocs SÉPARÉS. Mélanger les réparations et les décisions du système fait
    passer un rallye crypto retrouvé a posteriori pour la performance de l'algo."""
    blocs = ["═══ TOUTES POSITIONS CLOSES ═══", rapport(auditer(trades))]
    sys_ = auditer(trades, seulement="systeme")
    blocs += ["", "═══ DÉCISIONS DU SYSTÈME SEULEMENT ═══",
              "(le seul sous-ensemble qui mesure la stratégie)", rapport(sys_)]
    admin = auditer(trades, seulement="administratif")
    if admin.n_positions:
        blocs += ["", "═══ FERMETURES RECONSTRUITES (script de réparation) ═══",
                  "(sorties réelles, mais dates et prix retrouvés après coup — "
                  "ne mesurent AUCUNE décision)", rapport(admin)]
    return "\n".join(blocs)
