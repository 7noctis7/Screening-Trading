"""Le brief ne doit pas déguiser un appel cassé en état normal.

CE QUE CE TEST PROTÈGE. `_data_audit` lançait `["python", "scripts/data_audit.py"]` —
un binaire nommé exactement `python`, que le VPS n'expose pas (Ubuntu n'installe que
`python3`). Le `FileNotFoundError` tombait dans un `except Exception` qui rendait
« (audit indisponible) », lequel se lit comme une situation prévue. Le brief du matin
affichait donc tous les jours un audit vide sans que rien ne signale la panne.

Même famille que les treize commandes mortes (ADR-0139) : ce n'est pas l'appel cassé
qui coûte, c'est le repli silencieux qui le rend invisible.
"""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
SOURCE = RACINE / "scripts" / "daily_brief.py"


def _module():
    spec = importlib.util.spec_from_file_location("daily_brief_sous_test", SOURCE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _appels_subprocess() -> list[ast.Call]:
    arbre = ast.parse(SOURCE.read_text(encoding="utf-8"))
    return [n for n in ast.walk(arbre)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr == "run"]


def test_aucun_interpreteur_en_dur_dans_le_brief():
    """`python` / `python3` codés en dur suivent le PATH, pas le venv du Makefile."""
    en_dur = []
    for appel in _appels_subprocess():
        if not appel.args or not isinstance(appel.args[0], ast.List):
            continue
        for elt in appel.args[0].elts:
            nom = elt.value if isinstance(elt, ast.Constant) else None
            if isinstance(nom, str) and (nom in ("python", "python3")
                                         or nom.endswith("/python")):
                en_dur.append(nom)
    assert not en_dur, f"interpréteur en dur : {en_dur} — utiliser sys.executable"


def test_l_audit_passe_par_l_interpreteur_courant():
    arbre = ast.parse(SOURCE.read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(arbre)
              if isinstance(n, ast.FunctionDef) and n.name == "_data_audit")
    noms = {ast.unparse(n) for n in ast.walk(fn) if isinstance(n, ast.Attribute)}
    assert "sys.executable" in noms


def test_un_echec_est_NOMME_pas_masque(monkeypatch, tmp_path):
    """Le repli doit dire ce qui a cassé — sinon la panne se lit comme un état."""
    mod = _module()

    def explose(*a, **k):
        raise FileNotFoundError("No such file or directory: 'python'")

    monkeypatch.setattr(mod.subprocess, "run", explose)
    sortie = mod._data_audit()
    assert "FileNotFoundError" in sortie
    assert "indisponible" not in sortie      # l'ancien message, poli et muet


def test_un_code_retour_non_nul_remonte_le_message(monkeypatch):
    mod = _module()

    class Resultat:
        stdout, stderr, returncode = "", "ImportError: No module named 'pandas'", 1

    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **k: Resultat())
    sortie = mod._data_audit()
    assert "code 1" in sortie and "pandas" in sortie


def test_une_base_absente_reste_un_etat_normal(monkeypatch):
    """Tout n'est pas une panne : zéro base auditée est une situation légitime."""
    mod = _module()

    class Resultat:
        stdout, stderr, returncode = "rien à signaler\n", "", 0

    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **k: Resultat())
    assert mod._data_audit() == "(pas de base locale auditée)"


def test_le_brief_montre_bien_la_DERNIERE_entree():
    """Le brief lit la PREMIÈRE entrée du fichier ; elle doit porter la date la plus
    récente.

    Ce qui a cassé : deux entrées écrites le même jour par deux mains ont mis
    une entrée vieille de trois jours en tête. Le brief annonçait « dernière
    entrée de journal » sur du périmé, sans rien signaler.

    On ne contrôle QUE le sommet, délibérément. Le fichier compte 185 entrées et deux
    ruptures chronologiques anciennes ; imposer l'ordre total reviendrait à
    réécrire de l'historique que personne ne lit, pour protéger une ligne que
    tout le monde lit.
    """
    import re
    texte = (RACINE / "vault" / "04_JOURNAL.md").read_text(encoding="utf-8")
    dates = re.findall(r"^## Session (\d{4}-\d{2}-\d{2})", texte, re.M)
    assert dates, "aucune entrée datée dans le journal"
    assert dates[0] == max(dates), (
        f"en tête : {dates[0]}, alors que la plus récente est {max(dates)}")


def test_le_sommet_du_journal_ne_porte_pas_deux_fois_le_meme_numero():
    """Le numéro de session repart à 2 après 28 — ce n'est PAS un identifiant unique.

    On ne vérifie donc que le voisinage immédiat : deux entrées adjacentes portant le
    même numéro signalent une insertion concurrente mal fusionnée — ce qui
    vient d'arriver.
    """
    import re
    texte = (RACINE / "vault" / "04_JOURNAL.md").read_text(encoding="utf-8")
    nums = re.findall(r"^## Session \d{4}-\d{2}-\d{2} \((\d+)ᵉ\)", texte, re.M)
    collisions = [(a, b) for a, b in zip(nums, nums[1:], strict=False) if a == b]
    assert not collisions, f"entrées adjacentes de même numéro : {collisions}"


def test_le_module_se_charge_sans_effet_de_bord():
    assert _module().ROOT == RACINE
    assert "sys" in sys.modules
