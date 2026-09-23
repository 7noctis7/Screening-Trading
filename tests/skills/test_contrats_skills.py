"""Un contrat de Skill non vérifié se dégrade en silence.

Ce dépôt connaît le motif : six garde-fous décidaient sans qu'un seul compteur existe,
et il a fallu une panne pour s'en apercevoir (ADR-0186). Un fichier de spécification
subit exactement le même sort — sauf qu'il ne tombe jamais en panne, il devient
simplement faux.

Ce que ces tests épinglent :
  1. tous les contrats du dépôt sont conformes au schéma commun ;
  2. un champ PRÉSENT MAIS VIDE ne passe pas — « falsification_conditions: [] » est une
     thèse infalsifiable qui se cache derrière une clé ;
  3. un contrat qui se dit mûr mais cite un module inexistant est refusé ;
  4. le linter sait dire « rien à vérifier » sans mentir sur son verdict.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from packages.common.skills_contrat import champs_requis, message, rapport, verifier

RACINE = Path(__file__).resolve().parents[2]
SCHEMA = yaml.safe_load((RACINE / "skills" / "_schema" / "skill.schema.yaml")
                        .read_text(encoding="utf-8"))
REQUIS = champs_requis(SCHEMA)


def _contrat_minimal(**surcharge) -> dict:
    s = {k: (["x"] if k in ("inputs", "outputs", "failure_modes") else {"x": "y"})
         for k in REQUIS}
    s.update({"id": "exemple_valide", "version": "1.0.0", "title": "Exemple",
              "domain": "research", "maturity": "experimental",
              "calibration_status": "UNCALIBRATED", "risk_tier": "low"})
    s.update(surcharge)
    return {"skill": s}


def test_tous_les_contrats_du_depot_sont_conformes():
    r = rapport()
    assert r["n"] >= 2, "aucun contrat trouvé — le balayage est cassé"
    assert not r["ecarts"], message(r)


def test_un_champ_VIDE_ne_passe_pas_pour_un_champ_present():
    """« falsification_conditions: [] » satisfait un schéma naïf et ne dit rien."""
    manque = verifier(_contrat_minimal(economic_thesis={}), REQUIS)
    assert any("economic_thesis" in m for m in manque)
    for vide in ([], "", None):
        assert verifier(_contrat_minimal(purpose=vide), REQUIS)


def test_un_contrat_complet_ne_signale_rien():
    assert verifier(_contrat_minimal(), REQUIS) == []


def test_un_contrat_MUR_qui_cite_un_module_inexistant_est_refuse(tmp_path):
    """Un contrat peut PRÉCÉDER son code — mais alors il reste `experimental`. Se dire
    `production` en décrivant un module qui n'existe pas, c'est décrire un fantôme."""
    fantome = {"implementation": {"modules": ["packages/inexistant/nulle_part.py"]}}
    assert verifier(_contrat_minimal(maturity="experimental", **fantome), REQUIS) == []
    manque = verifier(_contrat_minimal(maturity="production", **fantome), REQUIS)
    assert any("inexistant" in m for m in manque)


def test_les_modules_cites_par_les_contrats_reels_existent_ou_sont_assumes():
    """Le contrôle d'ancrage sur les vrais fichiers, pas sur des doublures."""
    for f in sorted((RACINE / "skills").rglob("*.skill.yaml")):
        s = yaml.safe_load(f.read_text(encoding="utf-8"))["skill"]
        for m in (s.get("implementation") or {}).get("modules", []):
            existe = (RACINE / m).exists()
            assert existe or s["maturity"] == "experimental", (
                f"{f.name} se dit « {s['maturity']} » mais {m} n'existe pas")


def test_le_linter_dit_rien_a_verifier_sans_mentir(tmp_path):
    (tmp_path / "skills" / "_schema").mkdir(parents=True)
    (tmp_path / "skills" / "_schema" / "skill.schema.yaml").write_text(
        yaml.safe_dump(SCHEMA), encoding="utf-8")
    r = rapport(tmp_path / "skills", racine=tmp_path)
    assert r["n"] == 0 and not r["ecarts"]
    assert "rien à vérifier" in message(r)


def test_un_schema_absent_est_DIT_et_non_traite_comme_un_succes():
    """Le piège classique : zéro fichier trouvé → zéro écart → « tout va bien »."""
    r = rapport(RACINE / "skills_qui_n_existent_pas")
    assert r["sans_schema"] is True
    assert "introuvable" in message(r)
