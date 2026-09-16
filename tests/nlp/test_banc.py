"""Le comparatif de modèles — et la limite qu'il doit annoncer lui-même.

Il mesure des qualités OPÉRATIONNELLES. Il n'établit AUCUNE valeur prédictive : un modèle
peut être rapide, stable, d'accord avec ses pairs, et parfaitement inutile.
"""

import pathlib

from packages.nlp.banc import CAS, Resultat, accord

RACINE = pathlib.Path(__file__).resolve().parents[2]


class PiloteScripte:
    """Répond selon une table ticker → sentiment. Aucune connexion."""

    nom = "factice"

    def __init__(self, table=None, instable=False, jetons=40):
        # `table or {...}` transformerait un dictionnaire VIDE — qui est le cas de test le
        # plus utile, « ce modèle ne sait rien » — en table par défaut. Le piège classique
        # du `or` sur une valeur falsy mais légitime.
        self.table = {t: a for t, _, a in CAS} if table is None else table
        self.instable = instable
        self.appels = 0
        self.dernier_usage = {"completion_tokens": jetons}

    def disponible(self, timeout=3.0):
        return True

    def modeles(self, timeout=3.0):
        return ["factice-1", "factice-2"]

    def classer(self, systeme, utilisateur, timeout):
        self.appels += 1
        ticker = utilisateur.split("Titre : ", 1)[1].split("\n", 1)[0].strip()
        s = self.table.get(ticker, "NEUTRAL")
        if self.instable and self.appels % 2 == 0:
            s = "NEUTRAL" if s != "NEUTRAL" else "BULLISH"
        return {"ticker": ticker, "sentiment": s, "confidence_score": 0.8,
                "impact_horizon": "SWING", "catalyst_summary": "x"}


def _eprouver(pilote, **kw):
    import packages.nlp.banc as B
    original = B.choisir
    B.choisir = lambda *a, **k: pilote
    try:
        return B.eprouver("factice", **kw)
    finally:
        B.choisir = original


# ─── Le jeu commun ─────────────────────────────────────────────────────────────────────

def test_les_trois_sentiments_sont_representes():
    """Un jeu qui n'aurait que des cas haussiers récompenserait un modèle qui dit toujours
    BULLISH."""
    attendus = {a for _, _, a in CAS}
    assert attendus == {"BULLISH", "BEARISH", "NEUTRAL"}
    for s in attendus:
        assert sum(1 for _, _, a in CAS if a == s) >= 2


def test_un_modele_parfait_passe_le_bon_sens():
    r = _eprouver(PiloteScripte())
    assert r.n == len(CAS) and r.taux_bon_sens == 1.0
    assert r.replis == 0 and r.conformes == len(CAS)


def test_un_modele_qui_dit_toujours_neutre_echoue():
    """C'est exactement le mode d'échec qu'un jeu déséquilibré laisserait passer."""
    r = _eprouver(PiloteScripte(table={}))
    assert r.taux_bon_sens < 0.5


# ─── Le cache doit être DÉSACTIVÉ ──────────────────────────────────────────────────────

def test_le_cache_est_desactive_pendant_le_banc():
    """Avec le cache, la deuxième mesure d'un même titre serait instantanée et toujours
    identique : latence ET stabilité seraient toutes deux faussées, dans le sens flatteur."""
    p = PiloteScripte()
    r = _eprouver(p, repetitions=3)
    # 6 cas + 3 répétitions de stabilité = 9 appels RÉELS, aucun servi par le cache.
    assert p.appels == len(CAS) + 3
    assert r.stable is True


# ─── Stabilité ─────────────────────────────────────────────────────────────────────────

def test_un_modele_instable_est_detecte():
    """À température nulle un modèle devrait être déterministe ; les modèles quantifiés ne
    le sont pas toujours, et l'ignorer rendrait irreproductible tout ce qui s'appuie dessus."""
    r = _eprouver(PiloteScripte(instable=True), repetitions=4)
    assert r.stable is False
    assert any("reproductibles" in i for i in r.incidents)


def test_la_stabilite_exige_au_moins_deux_appels():
    p = PiloteScripte()
    _eprouver(p, repetitions=1)
    assert p.appels >= len(CAS) + 2, "une seule répétition ne teste rien"


# ─── Mesures ───────────────────────────────────────────────────────────────────────────

def test_les_jetons_viennent_du_FOURNISSEUR():
    """Les estimer depuis la longueur du texte donnerait un chiffre faux de 20 à 40 %
    selon le tokeniseur — un comparatif bâti dessus ne comparerait rien."""
    r = _eprouver(PiloteScripte(jetons=50))
    assert r.jetons and all(j == 50 for j in r.jetons)
    assert r.jetons_par_s is not None and r.jetons_par_s > 0


def test_sans_jetons_rendus_le_debit_est_None_pas_zero():
    """« 0 jeton/s » se lirait comme une mesure ; l'absence doit rester une absence."""
    r = Resultat(modele="x", pilote="y", latences_ms=[100.0])
    assert r.jetons_par_s is None


def test_les_latences_absentes_ne_fabriquent_pas_de_mediane():
    r = Resultat(modele="x", pilote="y")
    assert r.latence_mediane is None and r.latence_p90 is None


def test_un_repli_n_est_pas_compte_comme_conforme():
    class PiloteMort(PiloteScripte):
        def classer(self, systeme, utilisateur, timeout):
            return None

    r = _eprouver(PiloteMort())
    assert r.replis == len(CAS) and r.conformes == 0
    assert any("repli" in i for i in r.incidents)


def test_aucun_fournisseur_rend_None():
    import packages.nlp.banc as B
    original = B.choisir
    B.choisir = lambda *a, **k: None
    try:
        assert B.eprouver("absent") is None
    finally:
        B.choisir = original


# ─── Accord ────────────────────────────────────────────────────────────────────────────

def test_deux_modeles_identiques_sont_d_accord_a_cent_pour_cent():
    a = Resultat(modele="A", pilote="p", sentiments=["BULLISH", "BEARISH", "NEUTRAL"])
    b = Resultat(modele="B", pilote="p", sentiments=["BULLISH", "BEARISH", "NEUTRAL"])
    assert accord([a, b])[0]["accord"] == 1.0


def test_deux_modeles_opposes_ne_sont_d_accord_sur_rien():
    a = Resultat(modele="A", pilote="p", sentiments=["BULLISH", "BULLISH"])
    b = Resultat(modele="B", pilote="p", sentiments=["BEARISH", "BEARISH"])
    assert accord([a, b])[0]["accord"] == 0.0


def test_l_accord_se_calcule_sur_la_longueur_COMMUNE():
    a = Resultat(modele="A", pilote="p", sentiments=["BULLISH", "BEARISH", "NEUTRAL"])
    b = Resultat(modele="B", pilote="p", sentiments=["BULLISH"])
    x = accord([a, b])[0]
    assert x["n"] == 1 and x["accord"] == 1.0


def test_trois_modeles_donnent_trois_paires():
    rs = [Resultat(modele=n, pilote="p", sentiments=["BULLISH"]) for n in "ABC"]
    assert len(accord(rs)) == 3


# ─── La limite doit être ÉCRITE, pas sous-entendue ─────────────────────────────────────

def test_le_banc_annonce_qu_il_ne_mesure_PAS_la_valeur_predictive():
    """Un comparatif de modèles qui ne dit pas cela sera lu comme un classement de
    rentabilité — et ce serait faux."""
    module = (RACINE / "packages" / "nlp" / "banc.py").read_text(encoding="utf-8")
    cli = (RACINE / "scripts" / "benchmark_nlp.py").read_text(encoding="utf-8")
    for src in (module, cli):
        assert "valeur PRÉDICTIVE" in src or "valeur prédictive" in src
        assert "alpha-nlp" in src, "il doit renvoyer vers le banc qui tranche vraiment"


def test_l_accord_est_explicitement_distingue_de_la_justesse():
    """Deux modèles entraînés sur le même web se ressemblent par construction."""
    cli = (RACINE / "scripts" / "benchmark_nlp.py").read_text(encoding="utf-8")
    assert "RESSEMBLANCE, pas la justesse" in cli


def test_la_ram_non_mesurable_est_DITE_pas_inventee():
    """Le modèle est chargé par LM Studio, pas par nous : sans psutil ce processus est
    invisible, et un chiffre plausible obtenu sur le mauvais processus serait pire que rien."""
    cli = (RACINE / "scripts" / "benchmark_nlp.py").read_text(encoding="utf-8")
    assert "n/d" in cli and "psutil" in cli


def test_les_modeles_sont_eprouves_EN_SERIE():
    """Alterner entre deux modèles chargés fait payer un rechargement à chaque bascule :
    les latences décriraient l'ordre des appels, pas les modèles."""
    cli = (RACINE / "scripts" / "benchmark_nlp.py").read_text(encoding="utf-8")
    assert "EN SÉRIE" in cli
    assert "asyncio.gather" not in cli and "ThreadPool" not in cli
