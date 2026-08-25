"""Taux de change : un taux périmé ne fait pas échouer une valorisation, il la FAUSSE.

Module à 0 % de couverture avant le 25/08, et il porte la conversion des comptes d'un ADR
(TWD, JPY…) vers la devise de son cours. Un taux faux ne lève rien : il produit un P/E, un DCF
et une marge de sécurité crédibles et erronés — le pire des deux mondes.

Défaut trouvé en écrivant ces tests : le TTL portait sur le FICHIER, pas sur l'entrée. Comme
`_save` réécrit tout le fichier, récupérer une paire quelconque remettait le compteur de
fraîcheur à zéro pour TOUTES les autres.
"""

import json
import time

import packages.data.fx as fx


def _cache(tmp_path, contenu=None):
    fx._CACHE = tmp_path / "rates.json"
    if contenu is not None:
        fx._save(contenu)
    return fx._CACHE


def _entree(valeur, age_h):
    return {"v": valeur, "t": time.time() - age_h * 3600}


# --- LE DÉFAUT CORRIGÉ ------------------------------------------------------------------------

def test_ecrire_une_paire_ne_rajeunit_pas_les_autres(tmp_path):
    """LE défaut : `_save` réécrit le fichier, donc son mtime. Avec un TTL au fichier, une
    paire peu utilisée pouvait être servie indéfiniment avec un taux de plusieurs mois."""
    _cache(tmp_path, {"TWDUSD": _entree(0.031, age_h=20)})
    assert fx.age_heures("TWD") == 20.0

    c = fx._load()
    c["EURUSD"] = _entree(1.09, age_h=0)
    fx._save(c)

    assert fx.age_heures("TWD") == 20.0, "l'âge du TWD ne doit pas dépendre du EUR"
    assert fx.age_heures("EUR") == 0.0


def test_une_entree_dans_le_TTL_est_servie_sans_reseau(tmp_path):
    _cache(tmp_path, {"TWDUSD": _entree(0.031, age_h=23)})
    assert fx.rate("TWD", "USD") == 0.031


def test_une_entree_perimee_n_est_pas_servie_depuis_le_cache(tmp_path, monkeypatch):
    """Au-delà du TTL on re-récupère. Réseau indisponible ici → None, jamais la vieille valeur :
    « pas de taux » est une information exploitable, un taux périmé ne l'est pas."""
    _cache(tmp_path, {"TWDUSD": _entree(0.031, age_h=30)})
    monkeypatch.setitem(__import__("sys").modules, "yfinance", None)
    assert fx.rate("TWD", "USD") is None


def test_l_ancien_format_sans_date_est_traite_comme_perime(tmp_path, monkeypatch):
    """Une valeur nue n'a pas d'âge connu. Lui accorder le bénéfice du doute conserverait
    exactement le défaut qu'on corrige."""
    _cache(tmp_path, {"TWDUSD": 0.031})
    assert fx._lire_entree(0.031) is None
    assert fx.age_heures("TWD") is None
    monkeypatch.setitem(__import__("sys").modules, "yfinance", None)
    assert fx.rate("TWD", "USD") is None


def test_l_age_est_publie_pour_pouvoir_le_DIRE(tmp_path):
    """L'appelant doit pouvoir écrire « taux de 3 jours » plutôt que de supposer qu'il est frais."""
    _cache(tmp_path, {"JPYUSD": _entree(0.0067, age_h=72)})
    assert fx.age_heures("JPY") == 72.0
    assert fx.age_heures("XXX") is None


# --- CAS LIMITES ------------------------------------------------------------------------------

def test_identite_sans_appel_reseau(tmp_path, monkeypatch):
    _cache(tmp_path, {})
    monkeypatch.setitem(__import__("sys").modules, "yfinance", None)
    assert fx.rate("USD", "USD") == 1.0
    assert fx.rate("eur", "EUR") == 1.0


def test_devise_vide_renvoie_None_jamais_1(tmp_path):
    """Renvoyer 1.0 pour une devise inconnue convertirait au taux identité — donc pas du tout,
    en le prétendant. `None` laisse l'appelant masquer la valorisation."""
    _cache(tmp_path, {})
    assert fx.rate("", "USD") is None
    assert fx.rate("TWD", "") is None
    assert fx.rate("", "") is None


def test_cache_illisible_ne_leve_pas(tmp_path):
    p = _cache(tmp_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{ pas du json", encoding="utf-8")
    assert fx._load() == {}
    p.write_text(json.dumps(["une", "liste"]), encoding="utf-8")
    assert fx._load() == {}


def test_entree_corrompue_est_ignoree_pas_servie(tmp_path):
    _cache(tmp_path, {"TWDUSD": {"v": "pas un nombre", "t": time.time()},
                      "JPYUSD": {"t": time.time()},
                      "EURUSD": _entree(1.09, age_h=1)})
    assert fx._lire_entree(fx._load()["TWDUSD"]) is None
    assert fx._lire_entree(fx._load()["JPYUSD"]) is None
    assert fx.rate("EUR", "USD") == 1.09


def test_casse_et_espaces_normalises(tmp_path):
    _cache(tmp_path, {"TWDUSD": _entree(0.031, age_h=1)})
    assert fx.rate(" twd ", " usd ") == 0.031
    assert fx.age_heures(" twd ") == 1.0
