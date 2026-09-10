"""Doublons du journal introduits par les scripts de réparation.

LE MÉCANISME. `live_journal.build_open` fabrique un identifiant DÉTERMINISTE —
`P-{jour}-{courtier}-{symbole}` — dont l'UPSERT rend le re-run du même jour idempotent :
deux passages écrivent la même ligne. Un script de réparation qui ajoute un suffixe
`-R1`, `-R2` produit des identifiants NEUFS, donc des lignes NEUVES : il contourne
la garantie par construction.

CE QUE ÇA COÛTE. Mesuré le 09/09 sur le journal réel : 15 doublons sur 66. Le slippage
moyen passait de −0,16 à +11,97 bps — le signe s'inversait. Et le regroupement des
tranches de `turnover_audit` ne reconnaît que `-X` : ces doublons comptent donc
comme des positions distinctes dans l'expectancy et le profit factor.

RÈGLE FAIL-CLOSED. Une ligne suffixée n'est déclarée supprimable QUE si la ligne de BASE
existe et que leur économie est identique. Au moindre écart — quantité, prix d'entrée,
date, sortie — elle passe en `ambigus` : on garde tout et on le dit. Une réparation qui
efface un lot légitime détruit une position réelle, et c'est arrivé deux fois sur ce
projet le 09/09.
"""

from __future__ import annotations

import re

# Suffixe des scripts de RÉPARATION. `-X\d+` (tranches d'une vente en plusieurs fois)
# est délibérément absent : ce sont des lignes légitimes.
_SUFFIXE_REPARATION = re.compile(r"^(?P<base>.+)-R\d+$")


def _economie(t) -> tuple:
    """Ce qui doit être identique pour parler de doublon. Les arrondis suivent ceux du
    journal : au-delà, deux fills réellement distincts se ressembleraient."""
    return (t.instrument, t.venue, str(t.side),
            round(float(t.qty or 0.0), 10),
            round(float(t.entry_price or 0.0), 10),
            t.entry_ts.date().isoformat() if t.entry_ts else None,
            None if t.exit_price is None else round(float(t.exit_price), 10),
            t.exit_ts.date().isoformat() if t.exit_ts else None)


def doublons_suffixes(trades: list) -> dict:
    """Classe les lignes suffixées `-R` en supprimables / ambiguës.

    Returns:
        `{supprimables, ambigus, conserves}` — trois listes d'identifiants. `conserves`
        nomme les lignes de base dont au moins un doublon est supprimable, pour que le
        rapport dise ce qui SURVIT et pas seulement ce qui part.
    """
    par_id = {t.id: t for t in trades if getattr(t, "id", None)}
    supprimables: list[str] = []
    ambigus: list[str] = []
    conserves: set[str] = set()
    for tid, t in par_id.items():
        m = _SUFFIXE_REPARATION.match(tid)
        if not m:
            continue
        base = par_id.get(m.group("base"))
        if base is None or _economie(base) != _economie(t):
            ambigus.append(tid)          # rien à comparer, ou économie différente
            continue
        supprimables.append(tid)
        conserves.add(base.id)
    return {"supprimables": sorted(supprimables), "ambigus": sorted(ambigus),
            "conserves": sorted(conserves)}


def rapport(d: dict) -> str:
    """Rapport lisible. Silencieux — et honnête — quand il n'y a rien à faire."""
    if not d["supprimables"] and not d["ambigus"]:
        return "Journal sain : aucun doublon de réparation détecté."
    lignes = []
    if d["supprimables"]:
        lignes.append(f"{len(d['supprimables'])} doublon(s) SUPPRIMABLE(S) — la "
                      "ligne de base existe et l'économie est identique :")
        lignes += [f"  − {i}" for i in d["supprimables"][:20]]
        if len(d["supprimables"]) > 20:
            lignes.append(f"  … et {len(d['supprimables']) - 20} autre(s)")
        lignes.append(f"  → {len(d['conserves'])} ligne(s) de base conservée(s).")
    if d["ambigus"]:
        lignes.append(f"⚠ {len(d['ambigus'])} ligne(s) suffixée(s) AMBIGUË(S) — pas de "
                      "base, ou économie différente. RIEN n'y sera touché :")
        lignes += [f"  ? {i}" for i in d["ambigus"][:20]]
    return "\n".join(lignes)
