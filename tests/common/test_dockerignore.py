"""Une image Docker ne doit jamais embarquer ce que le dépôt garde en local.

Le Dockerfile copie `data/` ; `data/journal.db` contient les exécutions RÉELLES chez
le courtier. Sans `.dockerignore`, un `docker build` sur le VPS les mettait dans
l'image (constat d'audit du 06/10)."""

from fnmatch import fnmatch
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]


def _motifs() -> list[str]:
    lignes = (RACINE / ".dockerignore").read_text(encoding="utf-8").splitlines()
    return [x.strip() for x in lignes if x.strip() and not x.startswith(("#", "!"))]


def _exclu(chemin: str) -> bool:
    return any(fnmatch(chemin, m.rstrip("/")) or fnmatch(chemin, m.rstrip("/") + "/*")
               or chemin.startswith(m.rstrip("/") + "/") for m in _motifs())


def test_le_journal_reel_et_les_secrets_sont_exclus():
    for chemin in ("data/journal.db", ".env", ".env.production", "out/rapport.md",
                   ".cache/x.parquet", "models/ml.pkl", "data/market.db"):
        assert _exclu(chemin), chemin


def test_tout_ce_que_le_dockerfile_copie_reste_pris():
    for chemin in ("packages/core/models.py", "apps/api/main.py",
                   "config/risk.yaml", "data/delisted_seed.csv", "pyproject.toml"):
        assert not _exclu(chemin), chemin
