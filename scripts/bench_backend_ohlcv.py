#!/usr/bin/env python3
"""SQLite ou DuckDB pour l'OHLCV ? On MESURE avant de conclure.

CE QUE L'AUDIT A TROUVÉ (04/09). `packages/storage/bars_factory.make_bars_repository`
choisit entre `sqlite` et `duckdb`… et n'est **appelé nulle part** dans le dépôt. Le
dépôt DuckDB existe (79 lignes, `export_parquet` partitionné), son docstring dit
« écrit pour l'environnement de prod ; non exécuté hors-ligne », et rien ne l'exécute.
Le chemin colonnaire est donc CONÇU, pas branché — et la question « DuckDB irait-il plus
vite ? » n'a jamais reçu de chiffre.

LA RÈGLE DE DÉCISION, ÉCRITE AVANT LE RUN. C'est la méthode du dépôt : sans règle
préalable, tout résultat se justifie après coup.

    · gain médian < 1,5×  → on RESTE sur SQLite. Une dépendance de plus et une seconde
      abstraction à maintenir ne se paient pas avec 30 % ;
    · gain médian ≥ 1,5×  → le basculement se justifie, mais il exige d'abord d'unifier
      `DBPriceProvider` (chemin réellement utilisé) et `BarsRepository` (chemin de la
      fabrique) : ce sont DEUX abstractions sur la même donnée, et c'est la vraie
      raison pour laquelle la fabrique n'a jamais eu d'appelant ;
    · DuckDB absent ou base illisible → aucun verdict, et on le dit.

CE QUE CE BANC NE MESURE PAS. L'écriture, l'ingestion, la taille sur disque. Le coût qui
pèse sur les bancs de décision est la LECTURE répétée du même historique — c'est
celui-là qu'on chronomètre, avec le motif d'accès réel : N symboles ×
l'historique de production.

    python scripts/bench_backend_ohlcv.py              # 40 symboles de l'univers
    python scripts/bench_backend_ohlcv.py --n 200      # plus large
"""

from __future__ import annotations

import statistics
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SEUIL_BASCULEMENT = 1.5      # gain médian requis pour justifier une seconde abstraction
JOURS = 4015                 # profondeur de production (QUANT_HISTORY_DAYS)
N_DEFAUT = 40


def _symboles(n: int) -> list[str]:
    csv = ROOT / "config" / "mobile_universe.csv"
    if not csv.exists():
        return ["QQQ", "SPY", "AAPL", "MSFT"][:n]
    lignes = csv.read_text(encoding="utf-8").splitlines()[1:]
    return [x.split(",")[0].strip() for x in lignes if x.strip()][:n]


def _chrono(lire, symboles: list[str], depuis) -> tuple[float, int]:
    """(secondes, barres lues). Une seule passe : c'est le motif des bancs."""
    t0 = time.perf_counter()
    total = 0
    for s in symboles:
        try:
            total += len(lire(s, depuis))
        except Exception:  # noqa: BLE001 — un symbole absent ne fausse pas le chrono
            continue
    return time.perf_counter() - t0, total


def _sqlite(chemin: Path):
    from packages.data.providers.db_provider import DBPriceProvider
    prov = DBPriceProvider(chemin)
    return lambda s, depuis: prov.fetch_ohlcv(s, "1d", depuis, None)


def _duckdb(chemin: Path):
    """Lecture DuckDB du MÊME fichier SQLite, via son extension `sqlite_scanner`.

    Comparer deux bases différentes ne mesurerait pas le moteur mais leur contenu. On
    lit donc le même fichier : seule la couche de lecture change."""
    import duckdb
    conn = duckdb.connect(":memory:")
    conn.execute("INSTALL sqlite; LOAD sqlite;")
    conn.execute(f"ATTACH '{chemin}' AS src (TYPE sqlite);")

    def lire(symbole: str, depuis):
        return conn.execute(
            "SELECT ts, close FROM src.bars WHERE symbol = ? AND ts >= ? ORDER BY ts",
            [symbole, depuis.isoformat()]).fetchall()
    return lire


def _verdict(gain: float) -> None:
    print(f"\n  GAIN MÉDIAN : ×{gain:.2f}   (seuil écrit avant le run : "
          f"×{SEUIL_BASCULEMENT})")
    if gain >= SEUIL_BASCULEMENT:
        print("\n  → Le basculement SE JUSTIFIE sur ce chiffre. Il reste conditionné à")
        print("    l'unification de `DBPriceProvider` et `BarsRepository` : deux")
        print("    abstractions sur la même donnée, et la raison pour laquelle la")
        print("    fabrique n'a jamais eu d'appelant. Ne pas brancher avant.")
    else:
        print("\n  → On RESTE sur SQLite. Une dépendance de plus et une seconde")
        print("    abstraction à maintenir ne se paient pas à ce prix-là.")


def main() -> None:
    print(__doc__.split("    python")[0].rstrip())
    from apps.api.snapshot import _price_db_path
    chemin = _price_db_path()
    if chemin is None or not Path(chemin).exists():
        print("\n  Base de prix introuvable — aucun verdict.")
        return
    chemin = Path(chemin)
    try:
        lire_duck = _duckdb(chemin)
    except Exception as e:  # noqa: BLE001
        print(f"\n  DuckDB indisponible ({str(e)[:70]}).")
        print("  `uv pip install duckdb` puis relancer. Aucun verdict sans mesure.")
        return
    n = N_DEFAUT
    if "--n" in sys.argv:
        n = int(sys.argv[sys.argv.index("--n") + 1])
    symboles = _symboles(n)
    depuis = datetime.now(UTC) - timedelta(days=JOURS)
    print(f"\n  Base : {chemin.name} · {len(symboles)} symbole(s) · "
          f"{JOURS} jours d'historique\n")
    gains = []
    for essai in range(1, 4):        # trois passes : la première charge le cache
        t_sq, n_sq = _chrono(_sqlite(chemin), symboles, depuis)
        t_dk, n_dk = _chrono(lire_duck, symboles, depuis)
        gain = t_sq / t_dk if t_dk > 0 else float("inf")
        gains.append(gain)
        print(f"    passe {essai} : sqlite {t_sq:6.2f} s ({n_sq} barres) · "
              f"duckdb {t_dk:6.2f} s ({n_dk} barres) · ×{gain:.2f}")
    _verdict(statistics.median(gains))


if __name__ == "__main__":
    main()
