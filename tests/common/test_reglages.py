"""Le registre des `QUANT_*` : complet, typé, et il signale fautes de frappe et
valeurs illisibles au lieu de les ignorer (audit du 06/10)."""

import re
from pathlib import Path

import pytest

from packages.common import reglages as rg

RACINE = Path(__file__).resolve().parents[2]
_MOTIF = re.compile(r"QUANT_[A-Z0-9_]+")       # « QUANT_RISK_* » → préfixe, écarté


def _noms(dossiers, motif="*.py") -> set[str]:
    out = set()
    for d in dossiers:
        for f in (RACINE / d).rglob(motif):
            if (f.is_file() and "__pycache__" not in f.parts
                    and not f.name.startswith("reglages")):
                texte = f.read_text(encoding="utf-8", errors="ignore")
                out |= set(_MOTIF.findall(texte))
    return {n for n in out if not n.endswith("_")}


def test_tout_quant_du_code_est_declare():
    code = _noms(["packages", "apps/api", "scripts"])
    shell = _noms(["scripts"], "*.sh") | {n for n in _MOTIF.findall(
        (RACINE / "Makefile").read_text(encoding="utf-8")) if not n.endswith("_")}
    oublies = sorted((code | shell) - set(rg.REGISTRE))
    assert not oublies, f"à déclarer dans reglages_registre : {oublies}"


def test_aucune_declaration_morte():
    partout = (_noms(["packages", "apps/api", "scripts"])
               | _noms(["scripts", "deploy"], "*.sh") | _noms([".github"], "*.yml")
               | set(_MOTIF.findall((RACINE / "Makefile").read_text(encoding="utf-8")))
               | _noms(["deploy"], "*"))
    assert not sorted(set(rg.REGISTRE) - partout)


@pytest.mark.parametrize("var", rg.REGISTRE.values(), ids=lambda v: v.nom)
def test_le_defaut_declare_se_lit_avec_son_type(var):
    if var.defaut is not None:
        assert rg.valide(var, var.defaut) is None


def test_faute_de_frappe_illisible_et_drapeau_eteint_signales():
    env = {"QUANT_CADENCE_JOUR": "1", "QUANT_DD_TARGET": "25%",
           "QUANT_NEWS": "true", "QUANT_CRYPTO_VENUE": "kraken",
           "QUANT_CADENCE_JOURS": "5", "PATH": "/bin"}
    par_nom = {a["nom"]: a for a in rg.verifier(env)}
    assert set(par_nom) == {"QUANT_CADENCE_JOUR", "QUANT_DD_TARGET", "QUANT_NEWS",
                            "QUANT_CRYPTO_VENUE"}
    assert "QUANT_CADENCE_JOURS" in par_nom["QUANT_CADENCE_JOUR"]["motif"]
    assert par_nom["QUANT_DD_TARGET"]["critique"] is True
    assert par_nom["QUANT_NEWS"]["critique"] is False


def test_effectifs_masque_les_secrets():
    lignes = dict((n, v) for n, v, _ in rg.effectifs(
        {"QUANT_WEBHOOK_TOKEN": "s3cret", "QUANT_DD_TARGET": "0.2"},
        critiques_seulement=False))
    assert lignes["QUANT_WEBHOOK_TOKEN"] == "••••"
    assert lignes["QUANT_DD_TARGET"] == "0.2"
    assert lignes["QUANT_CADENCE_JOURS"] == "défaut (5)"


def test_annoncer_ne_leve_jamais():
    dit = []
    assert rg.annoncer({"QUANT_DD_TARGET": "x"}, dire=dit.append)[0]["critique"]
    assert dit and "QUANT_DD_TARGET" in dit[0]
