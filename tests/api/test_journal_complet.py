"""Le journal montre TOUT le registre, sans jamais dépendre du réseau courtier.

RÉCONCILIATION DU 21/09. Deux implémentations coexistaient, chacune avec ses tests, et
chacune effaçait l'autre : l'une rendait l'historique local complet (imports Alpaca
compris) avec un champ d'origine, l'autre le seul périmètre du ROBOT avec latent, frais
et matérialité. Ce fichier garde les propriétés de la PREMIÈRE — elles étaient justes —
en les exprimant sur l'implémentation fusionnée, où la route délègue à
`apps.api.journal_payload`.

L'une d'elles a d'ailleurs attrapé un vrai défaut de la fusion : en déléguant, la route
s'était mise à appeler `_snap()`, donc à construire le snapshot complet — une à trois
minutes — pour afficher un journal qui ne vit que dans SQLite.
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
API = ROOT / "apps" / "api" / "main.py"
PAYLOAD = ROOT / "apps" / "api" / "journal_payload.py"
PAGE = ROOT / "apps" / "web" / "app" / "journal" / "page.tsx"


def _source(fichier: Path, nom: str) -> str:
    tree = ast.parse(fichier.read_text(encoding="utf-8"))
    node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                and n.name == nom)
    return ast.unparse(node)


def test_le_journal_ne_filtre_plus_les_imports_courtier():
    """La propriété est intacte, elle a changé d'adresse : le filtre `legacy=False` a
    disparu et TOUT le registre est lu, chaque ligne étiquetée par son origine."""
    src = _source(PAYLOAD, "construire")
    assert "journal.all()" in src
    assert "legacy=False" not in src
    assert "origine" in src
    assert "rows_tous" in src


def test_le_journal_ne_declenche_ni_snapshot_ni_appel_courtier():
    """LA PROPRIÉTÉ LA PLUS IMPORTANTE DU FICHIER, et elle a servi : la route doit
    répondre même si Alpaca est lent ou muet. Elle peut se servir du snapshot s'il est
    DÉJÀ en cache, jamais le construire — d'où `bloquant=False`, qui rend un dict vide
    plutôt que d'attendre. Un latent absent se dit ; une page qui ne répond pas, non."""
    src = _source(API, "journal_roundtrips")
    appels = {n.func.id for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Call)
              and isinstance(n.func, ast.Name)}
    assert "_snap" not in appels
    assert "bloquant=False" in src
    for interdit in ("build_snapshot", "AlpacaBroker"):
        assert interdit not in src


def test_le_snapshot_NON_BLOQUANT_ne_construit_jamais():
    """SABOTAGE. Si `_snap_si_pret` appelait `_snap()`, toute la garantie ci-dessus
    tomberait sans qu'aucun autre test ne s'en aperçoive."""
    src = _source(API, "_snap_si_pret")
    assert "_snap(" not in src
    assert "build_snapshot" not in src
    assert "_CACHE" in src


def test_la_page_montre_les_DEUX_perimetres():
    """« Cette page montre un sous-ensemble » ne doit plus être la seule lecture
    possible : l'historique complet est atteignable, et son origine est dite."""
    page = PAGE.read_text(encoding="utf-8")
    assert "rows_tous" in page
    assert "historique Alpaca" in page
    assert "Tout le compte" in page
