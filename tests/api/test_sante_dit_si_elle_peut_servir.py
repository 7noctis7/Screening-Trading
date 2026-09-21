"""`/health` doit répondre « peux-tu servir une page MAINTENANT ? », pas « es-tu vivante ? ».

CE QUI S'EST PASSÉ LE 21/09. Le site n'affichait plus rien. Les deux services étaient
`active (running)`, aucun OOM, 1,4 Gi de RAM libre — et `make up` annonçait « ✓ API 200 ».
Ce 200 venait d'un `return {"status": "ok"}` en dur : une constante, qui ne regarde jamais
le snapshot. Or les pages sont rendues côté client, donc sans snapshot en cache la
première requête en CONSTRUIT un pendant une à trois minutes, et tout reste sur les
squelettes. Le voyant était vert, l'écran tournait, et rien ne reliait les deux.

Ces tests portent sur `apps/api/sante`, volontairement sans fastapi : la logique qui
décide de l'état doit être vérifiable partout où la suite tourne (même choix que
`test_fraicheur_snapshot.py`).
"""

from __future__ import annotations

import ast
from pathlib import Path

from apps.api.sante import (
    A_CONSTRUIRE,
    EN_CONSTRUCTION,
    PRET,
    PRET_RAFRAICHISSEMENT,
    etat,
    sante,
)

RACINE = Path(__file__).resolve().parents[2]
API = RACINE / "apps" / "api" / "main.py"
VERIF = RACINE / "scripts" / "verifier_service.sh"


def test_les_quatre_situations_sont_distinctes():
    """Deux booléens, quatre états — et aucun ne doit se confondre avec un autre."""
    assert etat(cache_present=True, construction=False) == PRET
    assert etat(cache_present=True, construction=True) == PRET_RAFRAICHISSEMENT
    assert etat(cache_present=False, construction=True) == EN_CONSTRUCTION
    assert etat(cache_present=False, construction=False) == A_CONSTRUIRE
    assert len({PRET, PRET_RAFRAICHISSEMENT, EN_CONSTRUCTION, A_CONSTRUIRE}) == 4


def test_la_seule_question_qui_compte_est_publiee():
    """« sert_immediatement » est ce qu'un opérateur doit lire : le reste est du détail."""
    assert sante(True, False)["sert_immediatement"] is True
    assert sante(True, True)["sert_immediatement"] is True      # sert l'ancien pendant le refresh
    assert sante(False, True)["sert_immediatement"] is False
    assert sante(False, False)["sert_immediatement"] is False


def test_sans_cache_l_age_est_INCONNU_jamais_zero():
    """Un âge de zéro se lirait « tout frais » alors qu'il signifie « il n'y a rien »."""
    assert sante(False, False, age_s=0.0)["age_s"] is None
    assert sante(False, True, age_s=12.0)["age_s"] is None
    assert sante(True, False, age_s=12.0)["age_s"] == 12.0


def test_le_contrat_existant_est_preserve():
    """Des appelants lisent déjà `status`. Un contrôle de santé qui change de contrat
    casse les outils qui s'en servaient."""
    for c in (True, False):
        for b in (True, False):
            assert sante(c, b)["status"] == "ok"


def test_chaque_etat_dit_ce_QUE_L_UTILISATEUR_verra():
    """« stale-while-revalidate » est exact et n'aide personne devant un écran qui tourne."""
    assert "immédiatement" in sante(True, False)["message"]
    assert "immédiatement" in sante(True, True)["message"]
    for msg in (sante(False, True)["message"], sante(False, False)["message"]):
        assert "attente" in msg and "1 à 3 min" in msg


def _code(nom: str) -> str:
    """Le CODE de la fonction, sa docstring RETIRÉE.

    Première version de ce test : rouge, parce que la docstring de `health` cite
    `_snap()` et `build_snapshot()` — pour expliquer qu'elle ne les appelle PAS. Un test
    qui lit la prose d'une fonction ne contrôle pas ce qu'elle fait ; il interdit d'en
    parler."""
    arbre = ast.parse(API.read_text(encoding="utf-8"))
    for n in ast.walk(arbre):
        if isinstance(n, ast.FunctionDef) and n.name == nom:
            corps = list(n.body)
            if (corps and isinstance(corps[0], ast.Expr)
                    and isinstance(corps[0].value, ast.Constant)
                    and isinstance(corps[0].value.value, str)):
                corps = corps[1:]
            return "\n".join(ast.unparse(x) for x in corps)
    raise AssertionError(f"{nom} introuvable dans {API}")


def test_health_ne_DECLENCHE_aucune_construction():
    """SABOTAGE. Un contrôle de santé qui appellerait `_snap()` construirait lui-même le
    snapshot qu'il est censé décrire : le voyant allumerait l'incendie qu'il signale, et
    chaque `make up` paierait trois minutes pour afficher une ligne."""
    src = _code("health")
    assert "_snap(" not in src
    assert "build_snapshot" not in src
    # Il lit l'état, il ne le provoque pas.
    assert "_CACHE" in src and "_BUILDING" in src


def test_le_controle_de_service_PUBLIE_l_etat_du_snapshot():
    """Le script disait « ✓ API 200 » et s'arrêtait là. Son propre en-tête soutient
    pourtant, pour le front, que « quelque chose répond » n'est pas « le service sert »."""
    src = VERIF.read_text(encoding="utf-8")
    assert "/health" in src
    assert "sert_immediatement" in src
    assert "snapshot" in src.split("✓ API", 1)[1]


def test_un_snapshot_non_pret_n_est_pas_traite_comme_une_PANNE():
    """Après un changement du code de construction, « pas encore de cache » est l'état
    NORMAL. Faire échouer `make up` là-dessus transformerait une information en fausse
    alerte — et on finirait par ne plus la lire."""
    src = VERIF.read_text(encoding="utf-8")
    bloc = src.split("✓ API", 1)[1]
    assert "statut=1" not in bloc
