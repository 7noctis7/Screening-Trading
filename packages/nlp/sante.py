"""État de la chaîne IA — ce que l'interface doit pouvoir montrer sans deviner.

TROIS ÉTATS, ET UN SEUL EST AMBIGU. `EN_LIGNE` : le fournisseur répond et le modèle demandé
est chargé. `HORS_LIGNE` : rien ne répond — sans NLP, le reste du système fonctionne, c'est
un choix d'architecture et pas une panne. `DÉGRADÉ` : le fournisseur répond mais quelque
chose cloche — le modèle demandé n'est pas celui qui est chargé, ou le disjoncteur s'est
ouvert. C'est l'état qui compte, parce que c'est le seul qu'on peut avoir sans s'en
apercevoir : tout a l'air de marcher, et les signaux sont des replis.

LA VERSION DU MODÈLE ET CELLE DES DONNÉES VIENNENT DU REGISTRE, pas d'une constante. Un
numéro de version écrit en dur se détache de ce qu'il désigne — c'est la leçon des chiffres
de la landing (ADR-0154), et elle vaut ici aussi.

Ce module ne fait AUCUN appel au LLM : il lit des états déjà mesurés. Un voyant qui déclenche
une inférence coûterait une seconde à chaque rafraîchissement de page.
"""

from __future__ import annotations

EN_LIGNE = "EN_LIGNE"
DEGRADE = "DEGRADE"
HORS_LIGNE = "HORS_LIGNE"


def etat_chaine(moteur=None, sonder: bool = True) -> dict:
    """État de la chaîne NLP locale. `sonder=False` pour ne pas toucher au réseau."""
    from packages.nlp.config import ConfigNLP
    cfg = (moteur.cfg if moteur is not None else ConfigNLP.depuis_env())
    base: dict = {"modele_demande": cfg.modele, "config": cfg.resume(),
                  "etat": HORS_LIGNE, "motif": "", "pilote": None,
                  "modeles_charges": [], "disjoncteur": None, "metriques": None}
    if moteur is not None:
        base["metriques"] = moteur.metriques()
        base["disjoncteur"] = moteur.disjoncteur.etat_public()
    if not sonder:
        base["motif"] = "non sondé (sonder=False)"
        return base

    pilote = _pilote(moteur, cfg)
    if pilote is None:
        base["motif"] = ("aucun fournisseur local ne répond — LM Studio (port 1234) "
                         "ou Ollama (11434)")
        return base
    base["pilote"] = pilote.nom
    charges = pilote.modeles()
    base["modeles_charges"] = charges
    base.update(_verdict(cfg.modele, charges, base.get("disjoncteur")))
    return base


def _pilote(moteur, cfg):
    if moteur is not None:
        return moteur.pilote()
    from packages.nlp.pilotes import choisir
    return choisir(cfg.modele, cfg.pilote, cfg.base)


def _verdict(demande: str, charges: list[str], disjoncteur: dict | None) -> dict:
    """Le voyant doit tester ce que fera le BOUTON, pas seulement le port.

    Même leçon que `/api/ai/status` sur l'assistant (25/08) : un statut fondé sur la seule
    réponse du serveur affichait « connecté » puis échouait en 404 dès qu'on générait,
    parce que le modèle demandé n'appartenait pas au fournisseur de l'URL.
    """
    if (disjoncteur or {}).get("etat") == "OPEN":
        return {"etat": DEGRADE,
                "motif": ("disjoncteur OUVERT : les appels partent en repli sans être "
                          f"envoyés, réouverture dans {disjoncteur.get('reouverture_dans_s')} s")}
    if not charges:
        return {"etat": DEGRADE, "motif": "le fournisseur répond mais aucun modèle n'est chargé"}
    if not any(demande.lower() in m.lower() or m.lower() in demande.lower()
               for m in charges):
        return {"etat": DEGRADE,
                "motif": (f"le modèle demandé « {demande} » n'est pas chargé — "
                          f"disponibles : {', '.join(charges[:4])}")}
    return {"etat": EN_LIGNE, "motif": ""}


def etat_modeles() -> dict:
    """Version en production et dernier entraînement, LUS DANS LE REGISTRE."""
    try:
        from packages.mlops.registre import Registre
        reg = Registre()
    except Exception as e:  # noqa: BLE001 — l'état IA ne doit pas tomber avec le registre
        return {"disponible": False, "motif": f"{type(e).__name__}: {e}"}
    prod = reg.production()
    candidats = reg.par_statut("candidate")
    m = (prod.manifest if prod else {}) or {}
    return {
        "disponible": True,
        "production": prod.version if prod else None,
        "dataset_hash": (m.get("dataset_hash") or "")[:16] or None,
        "git_commit": (m.get("git_commit") or "")[:12] or None,
        "feature_version": m.get("feature_version"),
        "metriques": m.get("metriques") or {},
        "entraine_le": m.get("cree_le"),
        # Un arbre git sale au moment du run signifie que ce modèle n'est PAS reproductible
        # depuis ce commit — l'information la plus utile avant d'essayer de le refaire.
        "reproductible": not str(m.get("git_commit") or "").endswith("-sale"),
        "candidats": [e.version for e in candidats],
        "archives": [e.version for e in reg.archives()][:5],
        "incoherences": reg.incoherences(),
    }
