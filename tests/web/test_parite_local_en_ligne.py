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

# Filet de dernier recours : ce qui n'est NI dans la table NI écrit par un `_write`
# littéral. Y ajouter un nom revient à affirmer sans preuve — à n'utiliser que pour
# un fichier produit autrement (boucle, nom calculé), et à justifier ici même.
# `portefeuille` en fait partie À DESSEIN : il est écrit en CONSTANTE, jamais appelé —
# cf. `test_le_portefeuille_live_n_est_JAMAIS_appele_par_le_build_statique`.
HORS_TABLE = {"overlays", "notes", "portefeuille"}


def _routes_appelees() -> set[str]:
    """Noms de fichiers que le front demandera en mode statique.

    Même transformation que `_staticUrl` : on retire le préfixe `/api/`, on coupe la
    query (neutralisée en statique) et on remplace les `/` par des `_`."""
    src = API_TS.read_text(encoding="utf-8")
    return {chemin.split("?")[0].replace("/", "_")
            for chemin in re.findall(r'["\']/api/([a-z_0-9/]+)', src)}


def _fichiers_publies() -> set[str]:
    """Noms écrits par le build statique : table `routes` ET appels `_write` directs.

    Ne lire que la table obligeait à inscrire dans `HORS_TABLE` tout fichier écrit
    ailleurs — c'est-à-dire à DÉCLARER qu'il est publié au lieu de le CONSTATER. Une
    liste blanche se remplit vite et ne vérifie plus rien : il suffit d'y ajouter un nom
    pour que le test se taise, même si l'écriture n'a jamais été branchée. Les appels
    `_write("nom", …)` sont, eux, la publication elle-même.
    """
    src = DUMP.read_text(encoding="utf-8")
    debut = src.index("routes = {")
    bloc = src[debut:src.index("}", debut)]
    ecritures = set(re.findall(r'_write\(\s*"([a-z_0-9]+)"', src))
    return set(re.findall(r'"([a-z_0-9]+)":', bloc)) | ecritures | HORS_TABLE


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


def test_le_portefeuille_live_n_est_JAMAIS_appele_par_le_build_statique():
    """Deux raisons, la seconde rédhibitoire.

    Un portefeuille figé au build et servi sous un voyant « COURTIER · il y a 12s » serait
    un mensonge : cette route n'a de sens que lue en direct. Et surtout, le site statique
    est PUBLIÉ — appeler la route sur une machine qui a les clés graverait les positions
    réelles du compte dans des pages publiques. Le dépôt est public et ces positions sont
    local-only ; ce garde-fou ne doit pas dépendre de l'absence de clés sur le runner.
    """
    # ON NE JUGE QUE LE CODE. Un commentaire a le DROIT de nommer la règle qu'il
    # explique — c'est même souhaitable, et c'est ce que fait `dump_static`. Sans ce
    # filtre, la première version de ce test tombait sur sa propre justification
    # (même précédent que `test_la_fermeture_de_production_ne_retranche_PAS_le_slippage`).
    src = "\n".join(l for l in DUMP.read_text(encoding="utf-8").splitlines()
                    if not l.lstrip().startswith("#"))
    assert "M.portefeuille" not in src, (
        "`dump_static` appelle la route portefeuille : les positions réelles seraient "
        "gravées dans un site PUBLIC.")
    assert '_write("portefeuille"' in src, "le build doit écrire un payload neutre"
    bloc = src[src.index('_write("portefeuille"'):]
    assert '"disponible": False' in bloc[:900], (
        "le payload statique doit se déclarer INDISPONIBLE, pas publier un total figé")


def test_les_fichiers_publies_mais_jamais_appeles_sont_CONNUS():
    """Du poids mort n'est pas une faute, mais une surprise en est une : on liste ce
    qu'on sait inutile pour qu'un nouvel orphelin se remarque."""
    orphelins = sorted(_fichiers_publies() - _routes_appelees())
    assert orphelins == ["overlays"], (
        f"orphelins inattendus : {orphelins}. `overlays` est neutralisé en statique "
        "(cf. `dump_static`) ; tout autre est soit à publier, soit à retirer.")
