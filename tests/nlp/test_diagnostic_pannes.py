"""Une panne doit NOMMER son remède. C'est tout ce qui est vérifié ici.

Le 16/09, `nlp-check` a rendu trois échecs sur un modèle local : deux TIMEOUT et un
REPONSE_ILLISIBLE. Aucun des trois ne disait quoi changer — et les remèdes sont pourtant
différents et exclusifs : lever un plafond de jetons, désactiver un mode «
raisonnement »,
ou corriger une invite. Un motif indifférencié envoie chercher un bug de schéma là où il
suffisait d'un réglage.

Même famille que les zéros qui ressemblent à des absences, déjà vue deux fois sur ce
projet : une panne silencieuse coûte plus qu'une panne bruyante.
"""

import asyncio
import io
import urllib.error

import packages.nlp.pilotes as P
from packages.nlp.config import ConfigNLP
from packages.nlp.moteur import MoteurNLP
from packages.nlp.pilotes import PiloteLMStudio, pourquoi_illisible

BON = {"ticker": "AAPL", "sentiment": "BULLISH", "confidence_score": 0.7,
       "impact_horizon": "SWING", "catalyst_summary": "Résultats."}


# ─── Les trois causes, et leurs trois remèdes
# ──────────────────────────────────────────

def test_une_reponse_TRONQUEE_nomme_le_plafond_de_jetons():
    """Le cas le plus traître : la réponse est coupée au milieu du JSON, donc
    illisible — et rien, dans le texte reçu, ne dit que c'est une troncature."""
    m = pourquoi_illisible('{"ticker": "AAPL", "sentim', {}, "length", 400)
    assert "TRONQUÉE" in m and "400" in m
    assert "QUANT_NLP_MAX_JETONS=1200" in m


def test_le_remede_propose_un_plafond_PLUS_HAUT_que_celui_en_vigueur():
    """Répéter le plafond courant ferait croire à un mur : il reste un réglage."""
    m = pourquoi_illisible("{tronqu", {}, "length", 1200)
    assert "QUANT_NLP_MAX_JETONS=3600" in m


def test_un_modele_a_RAISONNEMENT_est_reconnu_comme_tel():
    """Contenu vide + raisonnement rempli : le modèle a dépensé son quota à réfléchir.
    Chercher un défaut de schéma ici ne mène nulle part."""
    m = pourquoi_illisible("", {"reasoning_content": "Analysons…"}, "stop", 400)
    assert "RAISONNEMENT" in m and "thinking" in m


def test_un_contenu_VIDE_sans_raisonnement_se_distingue_du_precedent():
    m = pourquoi_illisible("", {}, "stop", 400)
    assert "VIDE" in m and "RAISONNEMENT" not in m


def test_un_vrai_JSON_malforme_MONTRE_ce_qui_a_ete_recu():
    """Le seul cas où le remède est l'invite — encore faut-il voir la réponse."""
    m = pourquoi_illisible("Je pense que AAPL va monter.", {}, "stop", 400)
    assert "illisible" in m and "Je pense que AAPL" in m


# ─── Le corps d'une erreur HTTP porte le motif du fournisseur
# ──────────────────────────

def test_une_erreur_HTTP_remonte_le_CORPS_pas_seulement_le_code(monkeypatch):
    """LM Studio explique dans le corps pourquoi il refuse. Jeter ce corps, c'est
    transformer « ce modèle ne gère pas response_format » en silence."""
    corps = b'{"error": "model does not support response_format"}'

    def leve(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 400, "Bad Request", {},
                                     io.BytesIO(corps))

    monkeypatch.setattr(P.urllib.request, "urlopen", leve)
    reponse, incident = P._poster("http://x/y", {"a": 1}, 1.0)
    assert reponse is None
    assert "HTTP 400" in incident and "response_format" in incident


def test_un_serveur_injoignable_se_distingue_d_une_erreur_HTTP(monkeypatch):
    def leve(req, timeout=None):
        raise urllib.error.URLError("Connection refused")

    monkeypatch.setattr(P.urllib.request, "urlopen", leve)
    reponse, incident = P._poster("http://x/y", {"a": 1}, 1.0)
    assert reponse is None and "HTTP" not in incident
    assert "URLError" in incident


# ─── Le motif voyage jusqu'à l'utilisateur
# ─────────────────────────────────────────────

class PiloteIllisible:
    nom = "factice"
    dernier_incident = "réponse TRONQUÉE au plafond de 400 jetons"

    def disponible(self, timeout=3.0):
        return True

    def classer(self, systeme, utilisateur, timeout):
        return None


def test_le_repli_PORTE_le_motif_du_pilote_jusqu_au_rapport():
    """Sans cela, `nlp-check` affiche « REPONSE_ILLISIBLE » et laisse devant un mur :
    le pilote SAVAIT pourquoi, l'information était simplement perdue."""
    m = MoteurNLP(cfg=ConfigNLP(modele="test"), pilote=PiloteIllisible())
    s = asyncio.run(m.classer("AAPL", "texte"))
    assert s.repli and "REPONSE_ILLISIBLE" in s.resume
    assert "TRONQUÉE" in s.resume and "400 jetons" in s.resume


def test_un_TIMEOUT_dit_le_plafond_qui_a_expire():
    class Lent:
        nom = "factice"

        def disponible(self, timeout=3.0):
            return True

        def classer(self, systeme, utilisateur, timeout):
            import time
            time.sleep(0.5)
            return BON

    m = MoteurNLP(cfg=ConfigNLP(modele="test", timeout_s=0.05), pilote=Lent())
    s = asyncio.run(m.classer("AAPL", "texte"))
    assert s.repli and "TIMEOUT" in s.resume and "jetons" in s.resume


# ─── Le plafond est un réglage, plus une constante
# ─────────────────────────────────────

def test_le_plafond_de_jetons_part_VRAIMENT_dans_la_requete(monkeypatch):
    vu = {}

    def faux(url, charge, timeout):
        vu["charge"] = charge
        return None, ""

    monkeypatch.setattr(P, "_poster", faux)
    PiloteLMStudio("m", max_jetons=1200).classer("s", "u", 1.0)
    assert vu["charge"]["max_tokens"] == 1200


def test_le_moteur_transmet_le_plafond_de_la_config_au_pilote(monkeypatch):
    vu = {}

    def espion(cfg, timeout=3.0):
        vu["cfg"] = cfg
        return PiloteIllisible()

    monkeypatch.setattr("packages.nlp.moteur.pilote_pour", espion)
    m = MoteurNLP(cfg=ConfigNLP(modele="x", max_jetons=999), pilote=None)
    m._pilote_resolu = False
    m.pilote()
    # La config ENTIÈRE est passée : plus aucun champ à recopier, donc plus aucun à
    # perdre.
    assert vu["cfg"].max_jetons == 999


# ─── Un repli ne doit jamais être compté comme une réponse juste
# ───────────────────────

def test_un_repli_NEUTRAL_ne_compte_pas_comme_un_accord(monkeypatch):
    """Le repli rend NEUTRAL par convention. Sur un cas dont la réponse attendue EST
    NEUTRAL, l'ancien comptage créditait un point — et affichait « 1/3 » là où la chaîne
    n'avait rien classé du tout. Un chiffre qui flatte au moment exact de la panne."""
    import scripts.nlp_check as N

    class ToutEnPanne:
        nom = "factice"
        dernier_incident = "contenu VIDE"

        def disponible(self, timeout=3.0):
            return True

        def classer(self, systeme, utilisateur, timeout):
            return None

    m = MoteurNLP(cfg=ConfigNLP(modele="test"), pilote=ToutEnPanne())
    justes = asyncio.run(N._essais(m))
    assert justes == 0, "aucun cas n'a été classé : le score doit être 0, pas 1"


# ─── Un réglage qui n'a aucun effet est pire qu'un réglage absent
# ──────────────────────

def test_nlp_check_honore_TOUS_les_reglages_de_l_environnement(monkeypatch):
    """Le défaut réel : `main()` reconstruisait la config champ par champ et avait perdu
    `max_jetons` à l'ajout du champ. `QUANT_NLP_MAX_JETONS=1200` restait sans effet,
    et le
    résumé affichait 400 — un réglage muet, que rien ne signale."""
    import scripts.nlp_check as N
    monkeypatch.setenv("QUANT_NLP_MAX_JETONS", "1200")
    monkeypatch.setenv("QUANT_NLP_TIMEOUT_S", "25")
    monkeypatch.setenv("QUANT_NLP_CONCURRENCE", "1")
    cfg = N.config_depuis(None, None)
    assert cfg.max_jetons == 1200
    assert cfg.timeout_s == 25.0 and cfg.concurrence == 1


def test_les_surcharges_de_ligne_de_commande_priment_sans_ecraser_le_reste(monkeypatch):
    import scripts.nlp_check as N
    monkeypatch.setenv("QUANT_NLP_MAX_JETONS", "900")
    cfg = N.config_depuis("un-modele", "ollama")
    assert cfg.modele == "un-modele" and cfg.pilote == "ollama"
    assert cfg.max_jetons == 900          # le reste de l'environnement survit


def test_AUCUN_appelant_ne_reconstruit_un_pilote_champ_par_champ():
    """L'invariant qui referme le défaut pour de bon.

    Trois appelants sur six avaient recopié `choisir(cfg.modele, cfg.pilote,
    cfg.base)` et
    perdu `max_jetons` à son ajout. Tant que `choisir` reste appelable de partout, le
    quatrième oubli n'attend qu'un nouveau champ. `pilote_pour(cfg)` passe la config
    entière : il n'y a plus rien à recopier, donc plus rien à perdre.
    """
    import ast
    import pathlib

    racine = pathlib.Path(__file__).resolve().parents[2]
    fichiers = [*(racine / "packages" / "nlp").glob("*.py"),
                *(racine / "scripts").glob("*nlp*.py"),
                racine / "scripts" / "benchmark_nlp.py"]
    coupables = []
    for f in fichiers:
        if f.name == "pilotes.py":       # le seul endroit où `choisir` a sa place
            continue
        for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "choisir":
                coupables.append(f"{f.name}:{n.lineno}")
    assert not coupables, ("ces appelants reconstruisent un pilote à la main et "
                           f"perdront le prochain champ ajouté : {coupables}")


# ─── Le raisonnement : mesuré nuisible, donc éteint par défaut
# ─────────────────────────

def test_lmstudio_demande_EXPLICITEMENT_de_ne_pas_raisonner(monkeypatch):
    """Mesuré le 16/09 : 3 cas sur 3 rendent un raisonnement et un contenu VIDE.
    Sur une classification à cinq champs, réfléchir ne gagne rien et coûte tout."""
    vu = {}

    def faux(url, charge, timeout):
        vu["charge"] = charge
        return None, ""

    monkeypatch.setattr(P, "_poster", faux)
    PiloteLMStudio("m").classer("s", "u", 1.0)
    assert vu["charge"]["chat_template_kwargs"]["enable_thinking"] is False


def test_le_raisonnement_se_rallume_pour_qui_veut_comparer(monkeypatch):
    vu = {}
    monkeypatch.setattr(P, "_poster",
                        lambda u, charge, t: (vu.update(charge), (None, ""))[1])
    PiloteLMStudio("m", raisonnement=True).classer("s", "u", 1.0)
    assert vu["chat_template_kwargs"]["enable_thinking"] is True


def test_ollama_utilise_sa_propre_cle_pour_le_meme_reglage(monkeypatch):
    from packages.nlp.pilotes import PiloteOllama
    vu = {}
    monkeypatch.setattr(P, "_poster",
                        lambda u, charge, t: (vu.update(charge), (None, ""))[1])
    PiloteOllama("m").classer("s", "u", 1.0)
    assert vu["think"] is False
    assert vu["options"]["num_predict"] == 400     # le plafond non plus ne s'oublie pas


def test_un_bloc_de_raisonnement_EN_LIGNE_ne_masque_plus_le_JSON():
    """Tous les fournisseurs ne séparent pas le raisonnement dans un champ dédié.
    Retirer un bloc délimité n'est pas deviner : on le fait déjà pour « ``` »."""
    from packages.nlp.pilotes import _json_dans
    assert _json_dans('<think>Réfléchissons…</think>{"a": 1}') == {"a": 1}
    assert _json_dans('<thinking>x</thinking>\n{"a": 2}') == {"a": 2}


def test_un_bloc_de_raisonnement_NON_FERME_reste_illisible():
    """Sans balise fermante, on ne sait pas où finit le raisonnement. Couper au jugé
    accepterait un JSON tronqué en croyant l'avoir compris."""
    from packages.nlp.pilotes import _json_dans
    assert _json_dans('<think>Réfléchissons… {"a": 1}') is None


def test_le_banc_mesure_sous_les_REGLAGES_DE_PRODUCTION(monkeypatch):
    """Le banc reconstruisait sa config champ par champ, perdant chaque nouveau réglage.
    Il classerait des modèles sous des conditions qu'on ne fait pas tourner."""
    import packages.nlp.banc as B
    monkeypatch.setenv("QUANT_NLP_MAX_JETONS", "1500")
    monkeypatch.setenv("QUANT_NLP_RAISONNEMENT", "1")
    monkeypatch.setenv("QUANT_NLP_TIMEOUT_S", "30")
    vu = {}
    monkeypatch.setattr(B, "pilote_pour", lambda cfg, **k: vu.update(cfg=cfg) or None)
    assert B.eprouver("un-modele") is None
    assert vu["cfg"].max_jetons == 1500
    assert vu["cfg"].raisonnement is True
    assert vu["cfg"].timeout_s == 30.0
    assert vu["cfg"].cache_max == 0      # la seule surcharge voulue par le banc
