"""Stockage des publications X. SQLite dédié, jamais mélangé au cache de prix.

UN SEUL ENDROIT SAIT FILTRER. La tentation est de pousser les critères en SQL — c'est
indexable et ce serait plus rapide. Mais la recherche par mot-clé, elle, ne descend pas
proprement (casse, accents, champs multiples, niveaux extraits) : elle resterait en
Python. On aurait alors DEUX sémantiques, l'une pour le serveur et l'autre pour le
navigateur du site statique, qui divergeraient sans que rien ne le signale.

Le store rend donc des `Publication`, et `filtres.appliquer` décide seul. Le volume le
permet largement ; si un jour il ne le permet plus, ce sera une mesure, pas une
supposition — et l'index existe déjà pour ce jour-là.

`ecrire` est IDEMPOTENT : réingérer le même export ne duplique rien. Une ingestion qui
ne l'est pas transforme un incident de réseau en publications fantômes.
"""

from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

from packages.social.modele import Classification, Direction, Publication

DEFAULT_DB = "data/social_x.db"

_DDL = """
CREATE TABLE IF NOT EXISTS publication (
    id TEXT PRIMARY KEY, compte TEXT NOT NULL, ts TEXT NOT NULL, texte TEXT NOT NULL,
    classification TEXT NOT NULL, ticker TEXT, symbole TEXT, direction TEXT,
    extraits TEXT NOT NULL, url TEXT
);
CREATE INDEX IF NOT EXISTS idx_pub_compte ON publication(compte, ts);
CREATE INDEX IF NOT EXISTS idx_pub_classe ON publication(classification);
"""


def chemin_db() -> str:
    """`QUANT_SOCIAL_DB` prime, sinon `data/social_x.db`. Jamais dans le dépôt."""
    return os.environ.get("QUANT_SOCIAL_DB") or DEFAULT_DB


class StorePublications:
    def __init__(self, db_path: str | Path = ":memory:") -> None:
        chemin = str(db_path)
        if chemin != ":memory:":
            Path(chemin).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(chemin)
        self.conn.executescript(_DDL)
        self._migrer()
        self.conn.commit()

    def _migrer(self) -> None:
        """Ajoute les colonnes apparues APRÈS la première base.

        `CREATE TABLE IF NOT EXISTS` ne touche pas une table qui existe déjà : sur une
        base déjà remplie, le DDL passe sans rien faire et la colonne neuve manque. Le
        symptôme serait une erreur SQL à la première écriture, longtemps après le
        déploiement — sur la machine de l'utilisateur, pas ici.
        """
        connues = {r[1] for r in self.conn.execute("PRAGMA table_info(publication)")}
        for nom, typ in (("images", "TEXT"),):
            if nom not in connues:
                self.conn.execute(f"ALTER TABLE publication ADD COLUMN {nom} {typ}")

    def ecrire(self, publications: Iterable[Publication]) -> int:
        rows = [(p.id, p.compte, p.ts.isoformat(), p.texte, str(p.classification),
                 p.ticker, p.symbole, None if p.direction is None else str(p.direction),
                 json.dumps(p.extraits, sort_keys=True), p.url,
                 json.dumps(list(p.images)))
                for p in publications]
        self.conn.executemany(
            "INSERT OR REPLACE INTO publication (id,compte,ts,texte,classification,"
            "ticker,symbole,direction,extraits,url,images) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
        self.conn.commit()
        return len(rows)

    def toutes(self) -> list[Publication]:
        cur = self.conn.execute(
            "SELECT id,compte,ts,texte,classification,ticker,symbole,direction,"
            "extraits,url,images FROM publication ORDER BY ts DESC")
        return [_depuis_ligne(r) for r in cur.fetchall()]

    def comptes(self) -> list[str]:
        """Les comptes RÉELLEMENT présents — la liste du filtre vient des données."""
        cur = self.conn.execute(
            "SELECT DISTINCT compte FROM publication ORDER BY compte")
        return [r[0] for r in cur.fetchall()]

    def symboles(self) -> list[str]:
        cur = self.conn.execute("SELECT DISTINCT symbole FROM publication "
                                "WHERE symbole IS NOT NULL ORDER BY symbole")
        return [r[0] for r in cur.fetchall()]

    def compter(self) -> int:
        return int(self.conn.execute("SELECT COUNT(*) FROM publication").fetchone()[0])

    def close(self) -> None:
        self.conn.close()


def _depuis_ligne(r: tuple) -> Publication:
    return Publication(
        id=r[0], compte=r[1], ts=datetime.fromisoformat(r[2]), texte=r[3],
        classification=Classification(r[4]), ticker=r[5], symbole=r[6],
        direction=None if r[7] is None else Direction(r[7]),
        extraits=json.loads(r[8]), url=r[9],
        images=tuple(json.loads(r[10]) if r[10] else ()))
