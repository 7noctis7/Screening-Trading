"""Deux fournisseurs, une interface — LM Studio et Ollama.

POURQUOI DEUX. LM Studio expose une API compatible OpenAI (`/v1/chat/completions`), Ollama
une API native (`/api/chat`). Les deux savent contraindre la sortie à un schéma JSON, mais
par des champs DIFFÉRENTS : `response_format.json_schema` d'un côté, `format` de l'autre.
Écrire le code contre un seul enfermerait le projet dans ce fournisseur, alors que le choix
dépend de ce qui est installé sur la machine — LM Studio ici, Ollama sur une autre.

CE QUE LES PILOTES NE FONT PAS. Ils n'interprètent rien, ne réessaient pas, ne décident pas
du repli. Ils envoient, lisent, et rendent un dictionnaire ou `None`. Le moteur décide.
Cette séparation est ce qui rend le moteur testable sans réseau.

Bibliothèque standard uniquement : ce paquet doit fonctionner dans l'environnement allégé
de la CI, où ni `requests` ni `openai` ne sont installés.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from packages.nlp.config import MAX_JETONS
from packages.nlp.schemas import SCHEMA

LMSTUDIO_BASE = "http://localhost:1234/v1"
OLLAMA_BASE = "http://127.0.0.1:11434"
NOM_SCHEMA = "signal_marche"


def _poster(url: str, charge: dict, timeout: float) -> tuple[dict | None, str]:
    """POST JSON → `(reponse, incident)`. Aucune exception ne sort d'ici.

    L'INCIDENT EST LA MOITIÉ UTILE, et il manquait. La version d'avant rendait `None`
    sur toute panne : un 400 de LM Studio disant que le modèle ne sait pas
    contraindre sa sortie arrivait au moteur sous le même « rien » qu'un serveur
    éteint, et l'utilisateur lisait « REPONSE_ILLISIBLE » sans voir le motif exact.
    """
    donnees = json.dumps(charge).encode("utf-8")
    req = urllib.request.Request(url, data=donnees,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 — hôte local
            return json.loads(r.read().decode("utf-8")), ""
    except urllib.error.HTTPError as e:
        # Le CORPS d'une erreur HTTP porte le motif EXACT du fournisseur. Le jeter,
        # c'est
        # remplacer « ce modèle ne gère pas response_format » par un silence.
        try:
            corps = e.read().decode("utf-8", "replace").strip()[:400]
        except Exception:  # noqa: BLE001
            corps = ""
        return None, f"HTTP {e.code} — {corps or e.reason}"
    except Exception as e:  # noqa: BLE001
        return None, f"{type(e).__name__}: {e}"


def pourquoi_illisible(contenu: str, message: dict, fin: str, max_jetons: int) -> str:
    """NOMMER la panne plutôt que rendre un « rien » indifférencié.

    Les trois causes vues en vrai sur un modèle local n'ont pas le même remède :
    une réponse tronquée au plafond, un modèle « à raisonnement » qui dépense son quota
    avant d'écrire, et un JSON réellement malformé. Les confondre fait chercher un bug
    de schéma là où il suffisait de lever un plafond.
    """
    if fin == "length":
        # Le remède propose un plafond PLUS HAUT que celui en vigueur — proposer le
        # chiffre courant n'aurait rien changé et aurait fait croire à un mur.
        return (f"réponse TRONQUÉE au plafond de {max_jetons} jetons "
                f"(finish_reason=length) — modèle bavard ou « à raisonnement » : "
                f"QUANT_NLP_MAX_JETONS={max_jetons * 3}")
    raisonnement = str(message.get("reasoning_content")
                       or message.get("reasoning") or "")
    if not contenu.strip() and raisonnement:
        return ("le modèle a produit un RAISONNEMENT mais AUCUN contenu — modèle "
                "« thinking » : désactiver le raisonnement dans LM Studio, ou "
                "prendre la variante « instruct »")
    if not contenu.strip():
        return "contenu VIDE — le fournisseur a répondu sans rien écrire"
    return f"JSON illisible · début reçu : {contenu.strip()[:160]!r}"


def _obtenir(url: str, timeout: float) -> dict | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:  # noqa: S310
            return json.loads(r.read().decode("utf-8"))
    except Exception:  # noqa: BLE001
        return None


def _json_dans(texte: str) -> dict | None:
    """Lit le JSON d'une réponse. Tolère un préambule, refuse de deviner.

    La sortie structurée devrait rendre ce nettoyage inutile ; il existe parce qu'un modèle
    quantifié agressif ajoute parfois « ```json » autour. On retire les clôtures de bloc et
    on tente UN décodage — pas d'extraction par expression régulière, qui accepterait un
    JSON tronqué en croyant l'avoir compris.
    """
    t = (texte or "").strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[-1] if "\n" in t else t
        t = t.rsplit("```", 1)[0].strip()
    try:
        charge = json.loads(t)
    except Exception:  # noqa: BLE001
        return None
    return charge if isinstance(charge, dict) else None


@dataclass
class PiloteLMStudio:
    """API compatible OpenAI — LM Studio, vLLM, llama.cpp server, Jan…"""

    modele: str
    base: str = LMSTUDIO_BASE
    nom: str = "lmstudio"
    # Jetons du DERNIER appel. Mesurer des jetons/seconde en les ESTIMANT depuis la
    # longueur du texte donnerait un chiffre faux de 20 à 40 % selon le tokeniseur — et un
    # comparatif de modèles reposant sur une estimation ne compare pas les modèles.
    dernier_usage: dict = field(default_factory=dict)
    dernier_incident: str = ""
    derniere_reponse: dict | None = None
    max_jetons: int = MAX_JETONS

    def disponible(self, timeout: float = 3.0) -> bool:
        d = _obtenir(f"{self.base.rstrip('/')}/models", timeout)
        return bool(d and d.get("data"))

    def modeles(self, timeout: float = 3.0) -> list[str]:
        d = _obtenir(f"{self.base.rstrip('/')}/models", timeout) or {}
        return [str(m.get("id", "")) for m in (d.get("data") or [])]

    def classer(self, systeme: str, utilisateur: str, timeout: float) -> dict | None:
        charge = {
            "model": self.modele,
            "messages": [{"role": "system", "content": systeme},
                         {"role": "user", "content": utilisateur}],
            "temperature": 0.0,       # une classification n'a pas à varier d'un appel à l'autre
            "max_tokens": self.max_jetons,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": NOM_SCHEMA, "strict": True, "schema": SCHEMA},
            },
        }
        url = f"{self.base.rstrip('/')}/chat/completions"
        d, incident = _poster(url, charge, timeout)
        self.derniere_reponse, self.dernier_incident = d, incident
        if not d:
            self.dernier_usage = {}
            return None
        self.dernier_usage = dict(d.get("usage") or {})
        choix = (d.get("choices") or [{}])[0]
        message = choix.get("message") or {}
        contenu = str(message.get("content") or "")
        charge_lue = _json_dans(contenu)
        if charge_lue is None:
            fin = str(choix.get("finish_reason") or "")
            self.dernier_incident = pourquoi_illisible(contenu, message, fin,
                                                       self.max_jetons)
        return charge_lue


@dataclass
class PiloteOllama:
    """API native Ollama. `format` accepte directement un schéma JSON depuis la 0.5."""

    modele: str
    base: str = OLLAMA_BASE
    nom: str = "ollama"
    dernier_usage: dict = field(default_factory=dict)
    dernier_incident: str = ""
    derniere_reponse: dict | None = None
    max_jetons: int = MAX_JETONS

    def disponible(self, timeout: float = 3.0) -> bool:
        d = _obtenir(f"{self.base.rstrip('/')}/api/tags", timeout)
        return bool(d and d.get("models"))

    def modeles(self, timeout: float = 3.0) -> list[str]:
        d = _obtenir(f"{self.base.rstrip('/')}/api/tags", timeout) or {}
        return [str(m.get("name", "")) for m in (d.get("models") or [])]

    def classer(self, systeme: str, utilisateur: str, timeout: float) -> dict | None:
        charge = {
            "model": self.modele,
            "messages": [{"role": "system", "content": systeme},
                         {"role": "user", "content": utilisateur}],
            "stream": False,
            "format": SCHEMA,
            "options": {"temperature": 0.0},
        }
        d, incident = _poster(f"{self.base.rstrip('/')}/api/chat", charge, timeout)
        self.derniere_reponse, self.dernier_incident = d, incident
        if not d:
            self.dernier_usage = {}
            return None
        # Ollama nomme autrement les mêmes grandeurs : on les ramène au vocabulaire OpenAI
        # pour que le comparatif n'ait pas à connaître le fournisseur.
        self.dernier_usage = {"completion_tokens": d.get("eval_count"),
                              "prompt_tokens": d.get("prompt_eval_count"),
                              "duree_ns": d.get("eval_duration")}
        message = d.get("message") or {}
        contenu = str(message.get("content") or "")
        charge_lue = _json_dans(contenu)
        if charge_lue is None:
            self.dernier_incident = pourquoi_illisible(
                contenu, message, str(d.get("done_reason") or ""), self.max_jetons)
        return charge_lue


def resoudre_modele(pilote, demande: str = "") -> tuple[str, str]:
    """Le modèle RÉELLEMENT exposé par le fournisseur, et POURQUOI celui-là.

    UN IDENTIFIANT EN DUR MENT EN SILENCE. Le pilote envoie `model: "<nom>"` ; LM
    Studio,
    en chargement à la demande, sert ce qu'il a sous la main et répond quand même. Le
    signal repart alors estampillé d'un nom que personne n'a servi — et c'est ce nom que
    `alpha_nlp_lab` inscrira dans la mesure. Le seul moyen de ne pas se mentir est de
    DEMANDER au fournisseur ce qu'il expose, jamais de le supposer.

    Rend `(modele, motif)`. Le motif est fait pour être AFFICHÉ : une résolution muette
    redeviendrait une supposition, simplement mieux cachée.
    """
    charges = []
    if pilote is not None:
        try:
            charges = list(pilote.modeles() or [])
        except Exception:  # noqa: BLE001 — un fournisseur muet n'est pas une panne ici
            charges = []

    if demande:
        if demande in charges:
            return demande, "demandé, et exposé tel quel"
        d = demande.lower()
        proches = [m for m in charges if d in m.lower() or m.lower() in d]
        if len(proches) == 1:
            return proches[0], (f"« {demande} » → « {proches[0]} » "
                                "(identifiant exact du fournisseur)")
        if len(proches) > 1:
            return demande, (f"« {demande} » correspond à {len(proches)} modèles "
                             f"exposés ({', '.join(proches[:3])}…) — AUCUN choix fait")
        if charges:
            return demande, (f"« {demande} » est ABSENT des {len(charges)} "
                             "modèles exposés")
        return demande, "demandé ; le fournisseur n'expose aucune liste"

    if not charges:
        return "", "aucun modèle exposé — fournisseur éteint, ou rien de chargé"
    if len(charges) == 1:
        return charges[0], "seul modèle exposé — aucune ambiguïté"
    return charges[0], (f"{len(charges)} modèles exposés et aucun demandé : premier "
                        "de la liste. Fixer LOCAL_TRADING_MODEL pour trancher")


def choisir(modele: str, pilote: str = "auto", base: str = "",
            timeout: float = 3.0, max_jetons: int = MAX_JETONS):
    """Le pilote à utiliser, ou `None` si aucun fournisseur ne répond.

    En mode `auto`, LM Studio est essayé d'abord : c'est ce qui est installé sur le poste
    de développement. L'ordre est un défaut, pas une préférence technique — `QUANT_NLP_PILOTE`
    tranche quand les deux tournent.
    """
    if pilote == "lmstudio":
        return PiloteLMStudio(modele, base or LMSTUDIO_BASE, max_jetons=max_jetons)
    if pilote == "ollama":
        return PiloteOllama(modele, base or OLLAMA_BASE, max_jetons=max_jetons)
    for p in (PiloteLMStudio(modele, base or LMSTUDIO_BASE, max_jetons=max_jetons),
              PiloteOllama(modele, base or OLLAMA_BASE, max_jetons=max_jetons)):
        if p.disponible(timeout):
            return p
    return None


def pilote_pour(cfg, timeout: float = 3.0):
    """Le pilote décrit par une `ConfigNLP`, tous réglages compris.

    POURQUOI ELLE EXISTE. `choisir()` prend des champs séparés, et six appelants les
    recopiaient à la main. Le jour où `max_jetons` est apparu, TROIS d'entre eux l'ont
    laissé au défaut sans rien dire : `QUANT_NLP_MAX_JETONS=1200` était accepté,
    affiché, et sans effet sur la requête. Un réglage muet est pire qu'un réglage
    absent — l'absent se voit. Passer la config ENTIÈRE ne laisse rien à oublier.
    """
    return choisir(cfg.modele, cfg.pilote, cfg.base, timeout=timeout,
                   max_jetons=cfg.max_jetons)
