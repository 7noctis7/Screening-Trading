"""`packages.mlops` NE PEUT PAS EXÉCUTER — contrainte de code, pas convention.

Points 64 et 65 du cahier des charges : un entraînement, local ou distant, ne doit avoir
aucun chemin vers un ordre courtier, une limite de risque ou l'activation du mode live.

Une convention se contourne sans bruit : il suffit d'un import « juste pour lire l'equity »
et la frontière n'existe plus. Ce test lit le graphe d'imports RÉEL, transitivement.
"""

import ast
import pathlib

RACINE = pathlib.Path(__file__).resolve().parents[2]
MLOPS = RACINE / "packages" / "mlops"

# Ce qu'un module d'entraînement ne doit jamais pouvoir atteindre.
INTERDITS = ("packages.execution", "scripts.run_live", "packages.risk")


def _imports(chemin: pathlib.Path) -> set[str]:
    arbre = ast.parse(chemin.read_text(encoding="utf-8"))
    out: set[str] = set()
    for n in ast.walk(arbre):
        if isinstance(n, ast.Import):
            out |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
            out.add(n.module)
    return out


def _module_vers_fichier(mod: str) -> pathlib.Path | None:
    p = RACINE / (mod.replace(".", "/") + ".py")
    if p.exists():
        return p
    p = RACINE / mod.replace(".", "/") / "__init__.py"
    return p if p.exists() else None


def _fermeture(depart: pathlib.Path) -> set[str]:
    """Imports ATTEIGNABLES depuis un fichier, transitivement et dans le dépôt."""
    vus: set[str] = set()
    pile = [depart]
    while pile:
        f = pile.pop()
        for mod in _imports(f):
            if mod in vus or not mod.startswith(("packages.", "scripts.", "apps.")):
                continue
            vus.add(mod)
            if (suivant := _module_vers_fichier(mod)) is not None:
                pile.append(suivant)
    return vus


def test_mlops_n_atteint_aucun_chemin_d_execution():
    for f in sorted(MLOPS.glob("*.py")):
        atteignables = _fermeture(f)
        fautifs = [m for m in atteignables
                   if any(m == i or m.startswith(i + ".") for i in INTERDITS)]
        assert not fautifs, (
            f"{f.name} atteint un chemin d'exécution : {fautifs}. Un entraînement ne doit "
            "avoir AUCUNE route vers un ordre courtier, même transitive.")


def test_aucun_mot_d_execution_dans_le_paquet():
    """Ceinture et bretelles : même par appel dynamique ou getattr, les verbes d'exécution
    n'ont rien à faire ici."""
    for f in sorted(MLOPS.glob("*.py")):
        src = f.read_text(encoding="utf-8")
        for interdit in ("submit_notional", "close_position", "--live --yes", "AlpacaBroker"):
            assert interdit not in src, f"{f.name} contient « {interdit} »"


def test_le_paquet_declare_sa_contrainte():
    """La règle doit être ÉCRITE là où on la lirait : dans le `__init__` du paquet."""
    init = (MLOPS / "__init__.py").read_text(encoding="utf-8")
    assert "packages.execution" in init and "JAMAIS" in init
