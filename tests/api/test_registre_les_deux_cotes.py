"""Un taux de réussite ne se juge pas en n'en voyant qu'un côté.

Le site publiait ses rejets — c'est rare, et c'est à son honneur — mais SEULEMENT ses
rejets. « 6 hypothèses rejetées » se lit alors de deux façons opposées : une rigueur
écrasante, ou un projet qui ne trouve jamais rien. Aucune des deux n'était vérifiable
par le lecteur, et rien ne lui permettait de trancher.

`/api/failures` publie donc aussi le décompte complet du registre. `items` reste
strictement les rejets — c'est le contrat de la page /echecs, qui l'affiche sans
filtrer ; y glisser une idée retenue la présenterait comme un échec.

Le test lit le registre réel et la source de l'endpoint : `fastapi` n'est pas installé
partout où cette suite tourne, et un test qui ne s'exécute nulle part ne garde rien.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
MAIN = (RACINE / "apps" / "api" / "main.py").read_text(encoding="utf-8")


def _bloc_failures() -> str:
    deb = MAIN.index('@app.get("/api/failures")')
    return MAIN[deb : MAIN.index("@app.get(", deb + 10)]


def test_le_decompte_complet_est_publie() -> None:
    bloc = _bloc_failures()
    for cle in ('"par_statut"', '"n_total"', '"n_rejected"'):
        assert cle in bloc, (
            f"{cle} n'est plus publié : /methode ne peut plus montrer que les rejets, "
            "et le lecteur n'a plus de quoi juger un taux de réussite."
        )


def test_items_ne_contient_que_des_rejets() -> None:
    """La page /echecs affiche `items` sans filtrer."""
    bloc = _bloc_failures()
    assert 'rejected = [r for r in recs if r.get("statut") == "rejete"]' in bloc, (
        "La sélection des rejets a changé : vérifier que `items` ne peut pas "
        "contenir une idée retenue, que /echecs afficherait comme un échec."
    )
    assert '"items": rejected' in bloc, "`items` ne porte plus les seuls rejets."


def test_le_registre_reel_porte_bien_plusieurs_statuts() -> None:
    """Si tout était « rejete », le décompte n'apprendrait rien et le bloc de /methode
    serait un graphique à une seule barre — signe que le registre n'est plus tenu."""
    from packages.research.ledger import read_records

    statuts = Counter(str(r.get("statut") or "inconnu") for r in read_records())
    assert statuts, (
        "Registre vide : les études n'ont jamais tourné, ou le fichier a bougé."
    )
    assert len(statuts) > 1, (
        f"Un seul statut dans le registre ({dict(statuts)}) : soit les idées retenues "
        "n'y sont plus inscrites, soit rien n'a été essayé depuis longtemps."
    )
