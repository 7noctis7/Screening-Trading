"""Ouverture, plus haut ou plus bas à 0 : une valeur ABSENTE, pas un prix.

LE CONSTAT (31/10). Le build Pages du 30/10 comptait 23 anomalies critiques à l'audit :
NDX à open = high = low = 0 sur des séances de juin 2026 (Yahoo ne renseignait que la
clôture), et la première barre de huit cryptos à open/low = 0. `packages/data/audit.py`
le dit déjà : un `0.0` exact est « la signature d'une valeur manquante convertie en
nombre ». Le lecteur de barres remplaçait une ouverture ABSENTE par la clôture, mais
laissait passer un ZÉRO : un ordre exécuté « à l'ouverture » d'une telle barre aurait pu
l'être à 0.

LA RÈGLE. Pour open, high et low d'une barre dont la clôture est positive :
- `0` exact → absent (NULL), sur tout instrument, y compris un contrat à terme ;
- négatif → absent, SAUF sur un contrat à terme (`=F`), qui peut coter sous zéro
  (WTI, 20/04/2020 : −37,63 $).
Rien n'est inventé : une valeur absente reste absente, et les lecteurs appliquent leur
convention existante (repli sur la clôture). La clôture n'est jamais touchée.
"""

from __future__ import annotations

import sqlite3

COLONNES = ("open", "high", "low")

# Même convention que `audit._peut_coter_negatif` : un contrat à terme finit par `=F`.
_ABSENT_SQL = "({col} = 0 OR ({col} < 0 AND UPPER(symbol) NOT LIKE '%=F'))"


def est_absent(symbole: str, valeur: float | None) -> bool:
    """Vrai si `valeur` (open/high/low) doit être lue comme absente."""
    if valeur is None:
        return True
    if valeur == 0:
        return True
    return valeur < 0 and not symbole.upper().endswith("=F")


def reparer(conn: sqlite3.Connection, table: str = "prices") -> dict[str, int]:
    """Passe à NULL les open/high/low absents d'une table de barres. Idempotent.

    Renvoie le nombre de valeurs modifiées par colonne. Les lignes à clôture ≤ 0 ne sont
    pas touchées : elles sont inutilisables de toute façon, et l'audit les signale."""
    n = {}
    for col in COLONNES:
        cond = _ABSENT_SQL.format(col=col)
        n[col] = int(conn.execute(
            f'UPDATE "{table}" SET {col} = NULL '
            f"WHERE close > 0 AND {col} IS NOT NULL AND {cond}").rowcount)
    conn.commit()
    return n


def compter(conn: sqlite3.Connection, table: str = "prices") -> int:
    """Nombre de valeurs open/high/low encore à réparer (lecture seule)."""
    return sum(int(conn.execute(
        f'SELECT COUNT(*) FROM "{table}" WHERE close > 0 AND {col} IS NOT NULL AND '
        f"{_ABSENT_SQL.format(col=col)}").fetchone()[0]) for col in COLONNES)
