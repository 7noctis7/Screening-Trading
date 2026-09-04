"""Ce qui marche en LOCAL doit marcher EN LIGNE — et inversement.

Le front a deux modes, et c'est la source d'incohérence la plus facile à créer sans
s'en apercevoir :

    STATIC=1  →  <base>/data/<nom>.json      (GitHub Pages : téléphone et ordinateur)
    sinon     →  http://localhost:8000/api/… (Mac, API vivante)

`lib/api.ts` transforme `/api/portfolio` en `data/portfolio.json`. Si une page appelle
une route que `dump_static` n'écrit PAS, elle fonctionne parfaitement en local et rend
404 en ligne. Le développeur ne le voit jamais : il travaille sur le mode qui marche.

Ce test compare les deux ensembles. Il n'a rien trouvé le 04/09 — c'est justement le
moment de l'écrire, pendant que c'est vert : un test ajouté après la panne ne protège
que du passé.
"""

from __future__ import annotations

import re
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
API_TS = RACINE / "apps" / "web" / "lib" / "api.ts"
DUMP = RACINE / "scripts" / "dump_static.py"

# Écrits hors du tableau `routes` de `dump_static`, vérifiés séparément ici.
HORS_TABLE = {"overlays", "notes"}


def _routes_appelees() -> set[str]:
    """Noms de fichiers que le front demandera en mode statique.

    Même transformation que `_staticUrl` : on retire le préfixe `/api/`, on coupe la
    query (neutralisée en statique) et on remplace les `/` par des `_`."""
    src = API_TS.read_text(encoding="utf-8")
    return {chemin.split("?")[0].replace("/", "_")
            for chemin in re.findall(r'["\']/api/([a-z_0-9/]+)', src)}


def _fichiers_publies() -> set[str]:
    """Noms écrits par le build statique (table `routes` + écritures explicites)."""
    src = DUMP.read_text(encoding="utf-8")
    debut = src.index("routes = {")
    bloc = src[debut:src.index("}", debut)]
    return set(re.findall(r'"([a-z_0-9]+)":', bloc)) | HORS_TABLE


def test_aucune_route_appelee_n_est_absente_du_build():
    """LE test qui compte. Une route manquante = 404 sur le téléphone, invisible en
    local — la pire incohérence : elle ne se voit que chez l'utilisateur."""
    manquantes = sorted(_routes_appelees() - _fichiers_publies())
    assert not manquantes, (
        f"{len(manquantes)} route(s) appelée(s) par le front mais jamais écrite(s) par "
        f"`dump_static` : {manquantes}. Elles rendront 404 en ligne alors qu'elles "
        "fonctionnent en local.")


def test_le_front_et_le_build_partagent_bien_des_routes():
    """Garde-fou du test lui-même : si une regex casse, les deux ensembles deviennent
    vides et l'assertion ci-dessus passerait pour de mauvaises raisons."""
    appelees, publiees = _routes_appelees(), _fichiers_publies()
    assert len(appelees) >= 15, f"{len(appelees)} routes lues — regex cassée ?"
    assert len(publiees) >= 15, f"{len(publiees)} fichiers lus — regex cassée ?"
    assert len(appelees & publiees) >= 15, "les deux ensembles ne se recoupent plus"


def test_les_fichiers_publies_mais_jamais_appeles_sont_CONNUS():
    """Du poids mort n'est pas une faute, mais une surprise en est une : on liste ce
    qu'on sait inutile pour qu'un nouvel orphelin se remarque."""
    orphelins = sorted(_fichiers_publies() - _routes_appelees())
    assert orphelins == ["overlays"], (
        f"orphelins inattendus : {orphelins}. `overlays` est neutralisé en statique "
        "(cf. `dump_static`) ; tout autre est soit à publier, soit à retirer.")
