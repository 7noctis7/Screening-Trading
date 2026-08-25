"""Les DEUX couches de risque, et pourquoi elles ne se rencontrent pas.

Décision du 25/08 (option A). Le dépôt contient deux barrières :

  `RiskEngine`  — par SIGNAL et par STOP, barre après barre → moteur événementiel / streaming.
  `order_gate`  — par ORDRE, sans signal ni stop            → chemin de rééquilibrage (run_live).

Brancher la première sur le second exigerait de fabriquer des `Order` et des `signal` factices
pour satisfaire une interface conçue pour autre chose. Un adaptateur factice au milieu d'une
barrière de sécurité produirait deux vérités sur le risque là où il en faut une.

Ces tests fixent la frontière. Ils ne l'imposent pas pour toujours : ils garantissent qu'on ne
la franchira pas par accident.
"""

import ast
import pathlib

RACINE = pathlib.Path(__file__).resolve().parents[2]


def _imports(fichier: pathlib.Path) -> set[str]:
    cibles: set[str] = set()
    for noeud in ast.walk(ast.parse(fichier.read_text(encoding="utf-8"), filename=str(fichier))):
        if isinstance(noeud, ast.Import):
            cibles |= {a.name for a in noeud.names}
        elif isinstance(noeud, ast.ImportFrom):
            cibles.add(noeud.module or "")
    return cibles


def test_le_chemin_de_rebalancement_utilise_order_gate():
    """`run_live.py` est le SEUL script qui envoie des ordres : sa barrière doit y être."""
    src = (RACINE / "scripts" / "run_live.py").read_text(encoding="utf-8")
    assert "packages.risk.order_gate" in src
    assert "evaluer(" in src, "le portail doit être APPELÉ, pas seulement importé"


def test_le_chemin_de_rebalancement_n_importe_PAS_RiskEngine():
    """L'absence est un CHOIX documenté (cf. packages/risk/engine.py), pas un oubli.

    Si ce test tombe un jour, c'est que quelqu'un a branché `RiskEngine` sur le rééquilibrage :
    qu'il le fasse en connaissance de cause, en retirant ce test et en mettant à jour l'ADR."""
    assert "packages.risk.engine" not in _imports(RACINE / "scripts" / "run_live.py")


def test_RiskEngine_reste_le_moteur_du_streaming():
    """Il n'est pas mort — il porte les stops et le reward/risk du moteur événementiel."""
    src = (RACINE / "packages" / "execution" / "live_engine.py").read_text(encoding="utf-8")
    assert "RiskEngine" in src and "self.risk.approve" in src


def test_le_perimetre_est_ECRIT_dans_le_module():
    """Une frontière qui ne vit que dans un test est une frontière qu'on refranchira."""
    doc = (RACINE / "packages" / "risk" / "engine.py").read_text(encoding="utf-8")
    assert "PÉRIMÈTRE" in doc and "order_gate" in doc
    assert "run_live" in doc
