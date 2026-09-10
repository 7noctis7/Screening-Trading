"""Aucun fichier de DONNÉES ne doit être suivi par git. Le dépôt est public.

`CLAUDE.md` l'interdit depuis toujours — mais l'interdiction vivait dans un
`.gitignore` dont le motif `*.db` **ne matche pas** `market.db-wal` : le suffixe casse
le glob. Quatre sidecars SQLite étaient donc suivis, dont deux de 32 Ko. Mesuré le
10/09, repéré dans la sortie de `make sync` (`M data/market.db-shm`), pas par un
garde-fou.

Un `-wal` porte les pages écrites et pas encore intégrées à la base : c'est de la
donnée, pas un artefact vide. Et `journal.db-wal` — les fills réels du courtier —
tombait dans le même trou.

Ce test lit l'INDEX GIT, pas le disque : il constate ce qui est réellement publié.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]

# Extensions dont AUCUN fichier ne doit être suivi. Chaque motif a coûté quelque chose.
INTERDITS = (
    ".db", ".db-wal", ".db-shm", ".db-journal",   # bases et leurs sidecars
    ".sqlite", ".sqlite3",
    ".env",                                        # secrets
)
# Fichiers d'exemple : ils ne contiennent que des noms de variables.
TOLERES = {".env.example", ".env.sample"}


def _fichiers_suivis() -> list[str]:
    out = subprocess.run(["git", "ls-files"], cwd=RACINE, capture_output=True,
                         text=True, check=True)
    return [ligne for ligne in out.stdout.splitlines() if ligne.strip()]


def test_aucune_base_de_donnees_n_est_suivie():
    suivis = _fichiers_suivis()
    assert suivis, "git ls-files n'a rien rendu — le test a perdu sa cible"
    coupables = [f for f in suivis
                 if Path(f).name not in TOLERES
                 and any(f.endswith(ext) for ext in INTERDITS)]
    assert not coupables, (
        f"{len(coupables)} fichier(s) de données suivis sur un dépôt PUBLIC : "
        f"{coupables}. "
        "Retirer avec `git rm --cached` et compléter `.gitignore`.")


def test_le_gitignore_couvre_les_SIDECARS_pas_seulement_les_bases():
    """`*.db` ne matche pas `market.db-wal`. Le motif doit être explicite, sinon le
    prochain fichier passera par le même trou."""
    motifs = (RACINE / ".gitignore").read_text(encoding="utf-8")
    for suffixe in ("*.db-wal", "*.db-shm"):
        assert suffixe in motifs, f"`{suffixe}` absent de .gitignore"


def test_le_journal_de_trades_est_bien_ignore():
    """Le journal porte les fills RÉELS du courtier — la donnée la plus sensible du
    dépôt. Sa base ET son sidecar doivent être ignorés."""
    for chemin in ("data/journal.db", "data/journal.db-wal", "data/journal.db-shm"):
        r = subprocess.run(["git", "check-ignore", "-q", chemin],
                           cwd=RACINE, capture_output=True)
        assert r.returncode == 0, f"{chemin} n'est PAS ignoré par git"
