"""Le garde-fou de séance est-il RÉELLEMENT dans le chemin des ordres ?

Constat du 26/08 sur le compte paper : cœur QQQ + huit lignes crypto + ZÉRO action,
et 28 % de cash exactement à la place du satellite actions. Les actions partent en
`TimeInForce.DAY` sans `extended_hours` ; hors séance elles ne peuvent pas se remplir.
La crypto (`GTC`, 24/7) passe toujours. Aucun contrôle d'horaires n'existait, et un
ordre qui ne peut pas se remplir ne laissait AUCUNE trace lisible.

Ces tests vérifient le CÂBLAGE, pas la logique du calendrier (couverte par
`test_market_calendar.py`) — c'est la distinction qui manquait la première fois :
une règle correcte mais non branchée ne protège rien.
"""

import importlib.util
import pathlib

import pytest

RACINE = pathlib.Path(__file__).resolve().parents[2]


def _run_live():
    spec = importlib.util.spec_from_file_location(
        "run_live_seance", RACINE / "scripts" / "run_live.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class _Reponse:
    """Réponse courtier minimale. Depuis le 26/08 `run_live` LIT le statut renvoyé : une
    doublure qui renvoie None est classée « issue inconnue » et l'ordre n'est pas
    compté —
    ce qui est le comportement voulu, mais rendrait ces tests trompeurs."""

    def __init__(self, status):
        self.status = status


class CourtierFactice:
    def __init__(self):
        self.ordres = []

    def submit_notional(self, sym, side, montant):
        self.ordres.append(("notional", sym, montant))
        return _Reponse("accepted")     # un courtier RÉPOND toujours quelque chose

    def close_position(self, sym):
        self.ordres.append(("close", sym, None))
        return True                     # AlpacaBroker.close_position renvoie un booléen


def _cible(sym, poids, classe="equity"):
    return {"symbol": sym, "broker_symbol": sym, "weight_pct": poids,
            "capital": "alpaca", "asset_class": classe, "tradeable": True}


@pytest.fixture
def rl():
    return _run_live()


def _brokers(b):
    return [("Alpaca", b, 100_000.0, {})]


def test_action_reportee_quand_le_marche_est_ferme(rl, monkeypatch, capsys):
    """LE cas observé : hors séance, l'ordre action n'est PAS envoyé — et c'est dit."""
    monkeypatch.delenv("QUANT_IGNORE_SESSION", raising=False)
    monkeypatch.setattr(rl, "_reconcile", rl._reconcile)      # module réellement chargé
    import packages.execution.market_calendar as mc
    monkeypatch.setattr(mc, "is_open", lambda ts=None, asset_class="equity":
                        asset_class == "crypto")
    b = CourtierFactice()
    sent, _, _ = rl._reconcile([_cible("AAA", 0.50)], _brokers(b), 1.0, None, dry=False)
    assert sent == 0 and b.ordres == []
    sortie = capsys.readouterr().out
    assert "REPORTÉ" in sortie
    assert "REPORTÉ(S) hors séance" in sortie      # le récapitulatif chiffré


def test_crypto_passe_meme_marche_actions_ferme(rl, monkeypatch):
    """La crypto se traite 24/7 : elle ne doit JAMAIS être reportée."""
    monkeypatch.delenv("QUANT_IGNORE_SESSION", raising=False)
    import packages.execution.market_calendar as mc
    monkeypatch.setattr(mc, "is_open", lambda ts=None, asset_class="equity":
                        asset_class == "crypto")
    b = CourtierFactice()
    sent, _, _ = rl._reconcile([_cible("BTC/USD", 0.50, "crypto")],
                               _brokers(b), 1.0, None, dry=False)
    assert sent == 1 and b.ordres


def test_action_passe_quand_le_marche_est_ouvert(rl, monkeypatch):
    monkeypatch.delenv("QUANT_IGNORE_SESSION", raising=False)
    import packages.execution.market_calendar as mc
    monkeypatch.setattr(mc, "is_open", lambda ts=None, asset_class="equity": True)
    b = CourtierFactice()
    sent, _, _ = rl._reconcile([_cible("AAA", 0.50)], _brokers(b), 1.0, None, dry=False)
    assert sent == 1 and b.ordres


def test_echappatoire_explicite(rl, monkeypatch):
    """`QUANT_IGNORE_SESSION=1` envoie quand même — en connaissance de cause."""
    monkeypatch.setenv("QUANT_IGNORE_SESSION", "1")
    import packages.execution.market_calendar as mc
    monkeypatch.setattr(mc, "is_open", lambda ts=None, asset_class="equity": False)
    b = CourtierFactice()
    sent, _, _ = rl._reconcile([_cible("AAA", 0.50)], _brokers(b), 1.0, None, dry=False)
    assert sent == 1 and b.ordres


# --- issue de l'ordre : un rejet ne compte pas ------------------------------

class CourtierQuiRefuse(CourtierFactice):
    """Le courtier ACCEPTE l'appel (aucune exception) puis REJETTE l'ordre.

    C'est le cas réel qui était invisible : `sent += 1` dès l'absence d'exception
    comptait comme réussi un ordre que le courtier venait de refuser.
    """

    def submit_notional(self, sym, side, montant):
        self.ordres.append(("notional", sym, montant))
        return _Reponse("rejected")


def test_un_rejet_courtier_ne_compte_pas_comme_envoye(rl, monkeypatch, capsys):
    monkeypatch.setenv("QUANT_IGNORE_SESSION", "1")
    b = CourtierQuiRefuse()
    sent, opened, _ = rl._reconcile([_cible("AAA", 0.10)], _brokers(b), 1.0, None,
                                    dry=False)
    assert b.ordres, "l'ordre a bien été tenté"
    assert sent == 0, "un ordre REJETÉ ne doit pas être compté comme envoyé"
    assert opened == [], "un rejet ne doit pas être journalisé comme une ouverture"
    sortie = capsys.readouterr().out
    assert "REJETÉ" in sortie and "REFUSÉ(S) par le courtier" in sortie


def test_une_reponse_inexploitable_ne_compte_pas(rl, monkeypatch):
    """Un courtier qui ne répond rien ne prouve pas que l'ordre est parti."""
    monkeypatch.setenv("QUANT_IGNORE_SESSION", "1")

    class Muet(CourtierFactice):
        def submit_notional(self, sym, side, montant):
            self.ordres.append(("notional", sym, montant))
            return None

    sent, _, _ = rl._reconcile([_cible("AAA", 0.10)], _brokers(Muet()), 1.0, None,
                               dry=False)
    assert sent == 0


# --- diagnostic du satellite : le cœur indiciel ne doit pas le masquer -------

def _snap(etapes, bloque=False, arret="", racine=False):
    """Le diagnostic est publié sous `dashboard`. Le lire à la racine renvoyait
    toujours {} — et affichait « aucun diagnostic publié » alors qu'il existait."""
    d = {"etapes": etapes, "portes": {}, "arret": arret, "bloque": bloque}
    if racine:
        return {"preset_diagnostic": d}
    return {"dashboard": {"preset_diagnostic": d}}


def test_le_coeur_indiciel_ne_masque_pas_un_satellite_vide(rl, capsys):
    """LE défaut du 26/08 : le filtre comptait les cibles par CLASSE D'ACTIFS, or QQQ
    (le cœur indiciel) est une action. Un satellite vide passait donc pour rempli et le
    diagnostic se taisait — exactement ce qu'il devait révéler. Le signal correct est
    l'étage « poids retenus », que le preset n'inscrit que s'il produit une ligne."""
    targets = [{"symbol": "QQQ", "asset_class": "equity", "weight_pct": 0.5}]
    snap = _snap([{"etape": "éligibles", "detail": "788 titres"},
                  {"etape": "score qualité", "detail": "0 scoré → REPLI"}])
    rl._diag_preset(snap, targets)
    sortie = capsys.readouterr().out
    assert "DIAGNOSTIC DU SATELLITE ACTIONS" in sortie
    assert "REPLI" in sortie


def test_diagnostic_muet_quand_le_satellite_produit_des_poids(rl, capsys):
    """Un diagnostic permanent serait du bruit : il ne parle qu'en cas de souci."""
    targets = [{"symbol": "AAPL", "asset_class": "equity", "weight_pct": 0.1}]
    snap = _snap([{"etape": "éligibles", "detail": "788 titres"},
                  {"etape": "poids retenus", "detail": "12 lignes, somme 48%"}])
    rl._diag_preset(snap, targets)
    assert capsys.readouterr().out == ""


def test_diagnostic_parle_meme_avec_des_poids_si_un_etage_bloque(rl, capsys):
    snap = _snap([{"etape": "poids retenus", "detail": "1 ligne"}],
                 bloque=True, arret="exposition brute NULLE")
    rl._diag_preset(snap, [{"symbol": "AAPL", "asset_class": "equity"}])
    assert "ARRÊT" in capsys.readouterr().out


def test_diagnostic_absent_ne_leve_pas(rl, capsys):
    """Un snapshot ancien (sans la clé) ne doit pas casser l'exécution."""
    rl._diag_preset({}, [])
    assert "DIAGNOSTIC" in capsys.readouterr().out     # rien à cacher : il le dit


def test_le_diagnostic_est_lu_sous_dashboard(rl, capsys):
    """LE défaut : `preset_diagnostic` est publié sous `dashboard`, pas à la racine.
    Le lire à la racine renvoyait {} et affichait « aucun diagnostic publié » alors
    que le diagnostic existait — un faux négatif dans l'outil de diagnostic."""
    snap = _snap([{"etape": "score qualité", "detail": "0 scoré → REPLI"}])
    assert "preset_diagnostic" not in snap          # bien nulle part à la racine
    rl._diag_preset(snap, [{"symbol": "QQQ", "asset_class": "equity"}])
    sortie = capsys.readouterr().out
    assert "REPLI" in sortie
    assert "aucun diagnostic publié" not in sortie


def test_repli_sur_la_racine_si_le_schema_evolue(rl, capsys):
    snap = _snap([{"etape": "éligibles", "detail": "788 titres"}], racine=True)
    rl._diag_preset(snap, [])
    assert "788 titres" in capsys.readouterr().out


# --------------------------------------------------------------------------
# LE REPORT NE DOIT PAS ÊTRE SUBI (2026-08-27)
#
# L'utilisateur planifie le rebalancement à 22h05 heure de Paris — soit APRÈS la
# clôture NYSE (22h00 pile). Les ordres actions y seront donc reportés chaque jour.
# L'ancien message affirmait « ils partiront à la prochaine séance » : faux, puisque
# la prochaine exécution sera elle aussi hors séance. Rien ne les met en file
# d'attente. Un message rassurant et faux est pire que pas de message.
# --------------------------------------------------------------------------
def _differes():
    return [
        {"symbol": "AAPL", "asset_class": "equity", "montant": 1200.0},
        {"symbol": "MSFT", "asset_class": "equity", "montant": -800.0},
    ]


def test_le_recap_ne_promet_PAS_un_envoi_automatique(capsys):
    """Le cœur du correctif : ne plus affirmer ce qui est faux."""
    from scripts.run_live import _recap_differes
    _recap_differes(_differes())
    sortie = capsys.readouterr().out
    assert "prochaine séance" not in sortie or "ne part que" in sortie
    assert "PAS mis en file d'attente" in sortie


def test_le_recap_donne_les_DEUX_issues_actionnables(capsys):
    """Un diagnostic qui ne dit pas quoi faire laisse l'utilisateur devant le même
    écran le lendemain."""
    from scripts.run_live import _recap_differes
    _recap_differes(_differes())
    sortie = capsys.readouterr().out
    assert "make live-go" in sortie
    assert "QUANT_LIVE_HOUR" in sortie


def test_le_recap_ventile_par_classe_d_actifs(capsys):
    """Distinguer actions et crypto est le fait qui compte : le crypto tourne 24/7
    et n'est JAMAIS reporté — voir un « 2 equity » confirme que le report est bien
    circonscrit, et non un blocage général."""
    from scripts.run_live import _recap_differes
    _recap_differes(_differes())
    sortie = capsys.readouterr().out
    assert "2 equity" in sortie
    assert "24/7" in sortie


def test_le_recap_totalise_les_montants_en_valeur_absolue(capsys):
    """Un achat de 1200 et une vente de 800 font 2000 $ d'exposition non traitée,
    pas 400 : les signes ne doivent pas se compenser."""
    from scripts.run_live import _recap_differes
    _recap_differes(_differes())
    assert "2 000$" in capsys.readouterr().out


# APERÇU : Alpaca construit en LECTURE (05/09). `_make_brokers(dry)` renvoyait toujours
# (None, None), donc l'aperçu n'avait aucun compte à lire — d'abord « détenu 0 $ »
# sur un compte plein, puis « cible 0 $ » partout une fois l'equity demandée à un
# broker absent.
# Aucun ordre ne peut partir pour autant : `_reconcile` sort sur `dry` AVANT tout envoi.


def test_simulation_ne_construit_aucun_broker(monkeypatch):
    from scripts.run_live import _make_brokers
    monkeypatch.setattr("scripts.run_live._alpaca_ou_rien",
                        lambda: (_ for _ in ()).throw(AssertionError("ne doit pas")))
    assert _make_brokers(dry=True, apercu=False) == (None, None)


def test_apercu_construit_alpaca_seul(monkeypatch):
    """La place crypto reste absente : `cron_live.sh` la neutralise de toute façon."""
    monkeypatch.setattr("scripts.run_live._alpaca_ou_rien", lambda: "alpaca-lecture")
    assert _make_brokers_apercu() == ("alpaca-lecture", None)


def _make_brokers_apercu():
    from scripts.run_live import _make_brokers
    return _make_brokers(dry=True, apercu=True)


# FILL RÉEL vs DELTA PLANIFIÉ (05/09) — cf. `packages/execution/live_roundtrip.py` et
# `packages/research/sur_fermeture.py`. `_journal_sells` doit lire la QUANTITÉ du fill
# réel quand un ordre du jour le permet, pas seulement son prix — sinon `close_sells`
# retombe sur le delta planifié et ferme plus que ce qui a vraiment été vendu.


class _CourtierAvecFill:
    """Un ordre de vente réel du jour, plus petit que le delta planifié (cas OSCR)."""
    name = "test"

    def orders(self, limit=50):
        return [{"symbol": "OSCR", "side": "sell", "price": 29.65,
                 "qty": 14.0, "date": "2026-09-05T12:00:00+00:00"}]


class _CourtierSansOrdre:
    name = "test"

    def orders(self, limit=50):
        return []

    def last_price(self, sym):
        return 30.0

    def positions_detailed(self):
        return []


def test_fill_vente_jour_lit_prix_ET_quantite(monkeypatch):
    from scripts.run_live import _fill_vente_jour
    monkeypatch.setattr("scripts.run_live.datetime", _horodatage_fixe())
    fait = _fill_vente_jour(_CourtierAvecFill(), "OSCR")
    assert fait == {"price": 29.65, "qty": 14.0}


def test_fill_vente_jour_absent_rend_none(monkeypatch):
    from scripts.run_live import _fill_vente_jour
    monkeypatch.setattr("scripts.run_live.datetime", _horodatage_fixe())
    assert _fill_vente_jour(_CourtierSansOrdre(), "OSCR") is None


def test_exit_price_seul_repli_sans_ordre_du_jour(monkeypatch):
    """Repli inchangé : sans ordre citable, `_exit_price` retombe sur `last_price`."""
    from scripts.run_live import _exit_price
    monkeypatch.setattr("scripts.run_live.datetime", _horodatage_fixe())
    assert _exit_price(_CourtierSansOrdre(), "OSCR") == 30.0


def _horodatage_fixe():
    import datetime as _dt

    class _Fixe(_dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return _dt.datetime(2026, 9, 5, 12, 0, tzinfo=tz)
    return _Fixe
