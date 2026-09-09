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
    assert 'if r.get("statut") == "rejete"' in bloc, (
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


def _dernier_mot():
    """Extrait la fonction sans importer fastapi, absent de cet environnement."""
    debut = MAIN.index("def _dernier_mot")
    espace: dict = {}
    exec(MAIN[debut : MAIN.index("\n\n\n", debut)], espace)  # noqa: S102
    return espace["_dernier_mot"]


def test_une_hypothese_rouverte_ne_reste_pas_affichee_comme_rejetee() -> None:
    """Le ledger est APPEND-ONLY : rouvrir une hypothèse s'y écrit en ajoutant une
    ligne, jamais en corrigeant l'ancienne — c'est la trace qui fait sa valeur. Mais le
    registre des négatifs montre un ÉTAT : sans dédoublonnage, une hypothèse rejetée
    puis rouverte resterait affichée comme un échec pour toujours.

    Cas réel du 09/09 : le rejet du Mean-CVaR reposait sur des séries de prix depuis
    réparées, et la mesure d'origine ne vaut plus.
    """
    dernier_mot = _dernier_mot()
    recs = [
        {"facteur": "x", "date": "2026-09-01", "statut": "rejete"},
        {"facteur": "x", "date": "2026-09-09", "statut": "en_test"},
        {"facteur": "y", "date": "2026-09-02", "statut": "rejete"},
    ]
    etat = {r["facteur"]: r["statut"] for r in dernier_mot(recs)}
    assert etat == {"x": "en_test", "y": "rejete"}, etat


def test_le_dedoublonnage_ne_perd_pas_les_lignes_sans_facteur() -> None:
    """Une ligne sans facteur ne prétend pas décrire un état : la jeter effacerait des
    essais du décompte, donc fausserait le taux de réussite publié."""
    dernier_mot = _dernier_mot()
    recs = [{"statut": "rejete"}, {"statut": "rejete"},
            {"facteur": "z", "date": "2026-01-01", "statut": "promu"}]
    assert len(dernier_mot(recs)) == 3


def test_le_registre_reel_ne_montre_plus_le_mean_cvar_comme_rejete() -> None:
    """Contrôle sur les VRAIES données : le rejet du 08/09 a été annulé le 09/09 par
    une ligne plus récente, parce que sa mesure portait sur des prix faux."""
    from packages.research.ledger import read_records

    dernier_mot = _dernier_mot()
    etat = {r.get("facteur"): r.get("statut") for r in dernier_mot(read_records())
            if r.get("facteur")}
    statut = etat.get("allocation_mean_cvar")
    assert statut == "en_test", statut
