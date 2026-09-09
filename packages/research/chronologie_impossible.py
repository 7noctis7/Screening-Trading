"""Retire du journal les round-trips dont la SORTIE précède l'ENTRÉE.

D'où ça vient (mesuré le 03/09 sur DUOL, confirmé le 04/09 sur PATH et cinq
autres). `reconcilier_journal._plan` appariait une vente au plus ancien lot du
symbole sans jamais regarder sa date d'entrée — une vente pouvait donc fermer un
lot qui n'existait pas encore. La garde `_anterieur` l'empêche désormais d'en
créer de nouveaux (ADR déjà consignée), mais elle ne rétroagit PAS : les
enregistrements déjà écrits portent toujours leur chronologie impossible, et leur
P&L a été calculé sur un prix de revient POSTÉRIEUR à la sortie — un chiffre qui
ne correspond à aucune opération.

Pourquoi RETIRER et non corriger. `journal_sqlite.py::supprimer` porte déjà ce
principe : on corrige une valeur fausse, on ne « corrige » pas une opération
imaginaire — on la retire. Rouvrir ces lots supposerait de savoir à quel lot
RÉEL la vente aurait dû s'apparier, ce qui n'est pas mesurable ligne à ligne
(diag_journal_compte.py::_sorties_avant_entree le dit déjà : « à rejouer sur un
plan complet »). Ici on ne rejoue rien : on retire ce qui ne peut PAS avoir eu
lieu, sans inventer ce qui aurait dû le remplacer.
"""

from __future__ import annotations


def identifier(trades: list) -> list:
    """Round-trips clos dont `exit_ts` précède `entry_ts`, à la granularité du JOUR."""
    return [t for t in trades if t.exit_ts is not None and t.entry_ts is not None
            and t.exit_ts.date() < t.entry_ts.date()]


def archive(t) -> dict:
    """Ligne d'archive JSON : tout ce qu'il faut pour rejuger le retrait plus tard."""
    return {
        "id": t.id, "instrument": t.instrument, "venue": t.venue,
        "qty": float(t.qty or 0), "entry_ts": str(t.entry_ts),
        "entry_price": float(t.entry_price or 0), "exit_ts": str(t.exit_ts),
        "exit_price": float(t.exit_price or 0), "pnl_net": float(t.pnl_net or 0),
        "entry_reason": t.entry_reason, "exit_reason": t.exit_reason,
    }
