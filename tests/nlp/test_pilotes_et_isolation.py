"""Les deux pilotes, et l'interdiction d'exécuter.

LM Studio et Ollama contraignent tous deux la sortie à un schéma JSON, mais par des champs
DIFFÉRENTS : `response_format.json_schema` contre `format`. Écrire le code contre un seul
enfermerait le projet dans ce fournisseur.
"""

import ast
import json
import pathlib

from packages.nlp.pilotes import (
    NOM_SCHEMA,
    PiloteLMStudio,
    PiloteOllama,
    _json_dans,
    choisir,
)
from packages.nlp.schemas import SCHEMA

RACINE = pathlib.Path(__file__).resolve().parents[2]
NLP = RACINE / "packages" / "nlp"


def _charge_envoyee(pilote, monkeypatch) -> dict:
    """Intercepte le POST sans ouvrir de connexion."""
    vu = {}

    def faux_poster(url, charge, timeout):
        vu["url"], vu["charge"], vu["timeout"] = url, charge, timeout
        return None, "fournisseur factice"      # `(reponse, incident)`

    import packages.nlp.pilotes as P
    monkeypatch.setattr(P, "_poster", faux_poster)
    pilote.classer("sys", "usr", 9.0)
    return vu


# ─── Contrainte de schéma : chaque fournisseur a sa syntaxe ────────────────────────────

def test_lmstudio_envoie_un_response_format_json_schema(monkeypatch):
    vu = _charge_envoyee(PiloteLMStudio("qwen2.5-7b-instruct"), monkeypatch)
    rf = vu["charge"]["response_format"]
    assert rf["type"] == "json_schema"
    assert rf["json_schema"]["name"] == NOM_SCHEMA
    assert rf["json_schema"]["strict"] is True
    assert rf["json_schema"]["schema"] == SCHEMA
    assert vu["url"].endswith("/chat/completions")


def test_ollama_envoie_le_schema_dans_format(monkeypatch):
    vu = _charge_envoyee(PiloteOllama("qwen2.5:7b"), monkeypatch)
    assert vu["charge"]["format"] == SCHEMA
    assert vu["charge"]["stream"] is False
    assert vu["url"].endswith("/api/chat")


def test_les_deux_pilotes_demandent_une_temperature_nulle(monkeypatch):
    """Une classification n'a pas à varier d'un appel à l'autre sur le même texte."""
    lm = _charge_envoyee(PiloteLMStudio("m"), monkeypatch)
    ol = _charge_envoyee(PiloteOllama("m"), monkeypatch)
    assert lm["charge"]["temperature"] == 0.0
    assert ol["charge"]["options"]["temperature"] == 0.0


def test_le_delai_est_transmis_au_transport(monkeypatch):
    vu = _charge_envoyee(PiloteLMStudio("m"), monkeypatch)
    assert vu["timeout"] == 9.0


def test_les_deux_pilotes_exposent_la_meme_interface():
    for p in (PiloteLMStudio("m"), PiloteOllama("m")):
        for methode in ("disponible", "modeles", "classer"):
            assert callable(getattr(p, methode))
        assert p.nom


def test_choisir_rend_None_quand_rien_ne_repond(monkeypatch):
    import packages.nlp.pilotes as P
    monkeypatch.setattr(P, "_obtenir", lambda url, timeout: None)
    assert choisir("m", "auto", timeout=0.1) is None


def test_choisir_force_respecte_le_choix_sans_sonder(monkeypatch):
    """`QUANT_NLP_PILOTE` doit trancher quand les deux fournisseurs tournent."""
    import packages.nlp.pilotes as P
    monkeypatch.setattr(P, "_obtenir",
                        lambda url, timeout: (_ for _ in ()).throw(AssertionError("sondé")))
    assert isinstance(choisir("m", "ollama"), PiloteOllama)
    assert isinstance(choisir("m", "lmstudio"), PiloteLMStudio)


# ─── Lecture de la réponse ─────────────────────────────────────────────────────────────

def test_un_bloc_de_code_est_toleré():
    """La sortie structurée devrait rendre ce nettoyage inutile ; il existe parce qu'un
    modèle quantifié agressif ajoute parfois ```json autour."""
    assert _json_dans('```json\n{"a": 1}\n```') == {"a": 1}


def test_un_json_tronque_est_REFUSE():
    """Une extraction par expression régulière accepterait un JSON coupé en croyant
    l'avoir compris — c'est exactement ce qu'on refuse de faire."""
    assert _json_dans('{"a": 1') is None
    assert _json_dans("pas du json") is None


def test_un_tableau_n_est_pas_un_objet():
    assert _json_dans("[1, 2]") is None


def test_une_reponse_mal_formee_du_fournisseur_ne_leve_pas(monkeypatch):
    import packages.nlp.pilotes as P
    monkeypatch.setattr(P, "_poster", lambda *a, **k: ({"inattendu": True}, ""))
    assert PiloteLMStudio("m").classer("s", "u", 1.0) is None
    assert PiloteOllama("m").classer("s", "u", 1.0) is None


def test_le_schema_envoye_est_serialisable():
    """Il part dans un corps JSON : un schéma non sérialisable échouerait au premier appel
    réel, jamais en test."""
    assert json.loads(json.dumps(SCHEMA)) == SCHEMA


# ─── Isolation : le NLP ne peut pas exécuter ───────────────────────────────────────────

INTERDITS = ("packages.execution", "scripts.run_live", "packages.risk")


def _imports(chemin: pathlib.Path) -> set[str]:
    out: set[str] = set()
    for n in ast.walk(ast.parse(chemin.read_text(encoding="utf-8"))):
        if isinstance(n, ast.Import):
            out |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
            out.add(n.module)
    return out


def _fermeture(depart: pathlib.Path) -> set[str]:
    vus: set[str] = set()
    pile = [depart]
    while pile:
        for mod in _imports(pile.pop()):
            if mod in vus or not mod.startswith(("packages.", "scripts.", "apps.")):
                continue
            vus.add(mod)
            f = RACINE / (mod.replace(".", "/") + ".py")
            g = RACINE / mod.replace(".", "/") / "__init__.py"
            if f.exists():
                pile.append(f)
            elif g.exists():
                pile.append(g)
    return vus


def test_le_nlp_n_atteint_aucun_chemin_d_execution():
    """L'IA fournit de l'information. Elle ne doit avoir AUCUNE route vers un ordre,
    fût-elle transitive (points 64-65 du cahier des charges)."""
    for f in sorted(NLP.glob("*.py")):
        fautifs = [m for m in _fermeture(f)
                   if any(m == i or m.startswith(i + ".") for i in INTERDITS)]
        assert not fautifs, f"{f.name} atteint un chemin d'exécution : {fautifs}"


def test_l_invite_interdit_explicitement_la_recommandation():
    """« AI says BUY » est précisément ce qu'on ne veut pas produire — l'interdiction est
    dans l'invite elle-même, pas seulement dans nos intentions."""
    src = (NLP / "invites.py").read_text(encoding="utf-8")
    assert "Tu ne recommandes JAMAIS d'acheter ou de vendre." in src


def test_le_paquet_declare_sa_contrainte():
    init = (NLP / "__init__.py").read_text(encoding="utf-8")
    assert "JAMAIS UNE DÉCISION" in init.upper() or "jamais une décision" in init
