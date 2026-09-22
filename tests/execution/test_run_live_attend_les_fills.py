"""Le CÂBLAGE de l'attente des fills — une règle correcte mais non branchée ne protège rien.

Le 22/09, six achats envoyés ont donné deux ouvertures au journal, dont deux tronquées.
La logique de l'attente est couverte par `test_attente_fills.py` ; ici on vérifie qu'elle
est réellement dans le chemin, que l'identité des ordres y arrive, et qu'elle ne peut
pas coûter un run.
"""

import importlib.util
import pathlib

import pytest

RACINE = pathlib.Path(__file__).resolve().parents[2]
SOURCE = (RACINE / "scripts" / "run_live.py").read_text(encoding="utf-8")


def _run_live():
    spec = importlib.util.spec_from_file_location(
        "run_live_attente", RACINE / "scripts" / "run_live.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class _Ordre:
    """Réponse courtier : un ordre accepté PORTE une identité."""

    def __init__(self, oid="ord-1", status="accepted"):
        self.id, self.status = oid, status


class Courtier:
    def __init__(self, oid="ord-1"):
        self.oid, self.ordres, self.lectures = oid, [], 0

    def submit_notional(self, sym, side, montant):
        self.ordres.append((sym, montant))
        return _Ordre(self.oid)

    def close_position(self, sym):
        self.ordres.append((sym, None))
        return True                       # un booléen : aucune identité à porter

    def orders(self, limit=100):
        self.lectures += 1
        return [{"id": self.oid}]


@pytest.fixture
def rl():
    return _run_live()


@pytest.fixture(autouse=True)
def _marche_ouvert(monkeypatch):
    monkeypatch.delenv("QUANT_IGNORE_SESSION", raising=False)
    # Aucun test ne doit DORMIR. `0` fait une lecture puis rend la main : le contrat
    # « borné » est éprouvé par `test_attente_fills.py` sur une horloge simulée.
    monkeypatch.setenv("QUANT_ATTENTE_FILLS_S", "0")
    import packages.execution.market_calendar as mc
    monkeypatch.setattr(mc, "is_open", lambda ts=None, asset_class="equity": True)


def _cible(sym, poids, classe="equity"):
    return {"symbol": sym, "broker_symbol": sym, "weight_pct": poids,
            "capital": "alpaca", "asset_class": classe, "tradeable": True}


# --- l'identité de l'ordre voyage avec lui ----------------------------------

def test_un_achat_emporte_l_identite_de_son_ordre(rl):
    b = Courtier("ord-achat")
    _, opened, _ = rl._reconcile([_cible("AAA", 0.50)],
                                 [("Alpaca", b, 100_000.0, {})], 1.0, None, dry=False)
    assert len(opened) == 1 and opened[0]["order_id"] == "ord-achat"


def test_une_vente_emporte_aussi_l_identite(rl):
    """La vente en a besoin autant : sans fill lisible, `_journal_sells` n'a pas de prix
    de sortie et laisse le lot ouvert — c'est la ligne « vente(s) sans prix broker »."""
    b = Courtier("ord-vente")
    _, _, sold = rl._reconcile([_cible("AAA", 0.10)],
                               [("Alpaca", b, 100_000.0, {"AAA": 50_000.0})],
                               1.0, None, dry=False)
    assert sold and all(s["order_id"] == "ord-vente" for s in sold)


def test_une_liquidation_sans_identite_vaut_None_et_non_une_chaine_vide(rl):
    """`close_position` rend un booléen. `None` DIT qu'il n'y a rien à attendre ;
    une chaîne vide se serait glissée dans l'ensemble des ordres à attendre."""
    b = Courtier()
    _, _, sold = rl._reconcile([_cible("AAA", 0.0)],
                               [("Alpaca", b, 100_000.0, {"AAA": 50_000.0})],
                               1.0, None, dry=False)
    assert sold and sold[0]["order_id"] is None


# --- l'attente est branchée, et ne peut pas coûter un run -------------------

def test_l_attente_est_appelee_AVANT_la_journalisation_et_hors_dry_run():
    corps = SOURCE[SOURCE.index("def main()"):SOURCE.index("def _disjoncteur")]
    i_attente = corps.index("_attendre_les_fills(")
    i_opens = corps.index("_journal_opens(")
    i_dry = corps.index("if not dry:\n        _attendre_les_fills(")
    assert i_attente < i_opens, "attendre APRÈS avoir journalisé ne sert à rien"
    assert i_dry >= 0, "un dry-run n'envoie rien : il ne doit rien attendre"


def test_l_attente_interroge_le_courtier_avec_les_ids_envoyes(rl, capsys):
    b = Courtier("ord-1")
    rl._attendre_les_fills([{"order_id": "ord-1", "broker_symbol": "AAA"}], [], b, None)
    assert b.lectures == 1                              # tout lisible : une seule lecture
    assert "1 ordre(s) lisible(s)" in capsys.readouterr().out


def test_le_delai_est_reglable_et_zero_le_desarme(rl, monkeypatch, capsys):
    """`QUANT_ATTENTE_FILLS_S=0` rend l'ancien comportement — une porte de sortie
    explicite si l'attente gênait un jour, plutôt qu'un patch dans l'urgence."""
    class Jamais:
        def orders(self, limit=100):
            return []
    monkeypatch.setenv("QUANT_ATTENTE_FILLS_S", "0")
    rl._attendre_les_fills([{"order_id": "x", "broker_symbol": "TTEK"}], [], Jamais(), None)
    sortie = capsys.readouterr().out
    assert "TOUJOURS ILLISIBLE" in sortie and "TTEK" in sortie   # dit, sans attendre


def test_un_delai_illisible_retombe_sur_le_defaut(rl, monkeypatch, capsys):
    """Une valeur absurde dans l'environnement ne doit ni planter le run ni le figer :
    on retombe sur le défaut, et comme l'ordre est déjà lisible l'attente rend la main
    au premier tour — le test ne dort donc pas."""
    monkeypatch.setenv("QUANT_ATTENTE_FILLS_S", "beaucoup")

    class Sonde:
        def orders(self, limit=100):
            return [{"id": "x"}]
    rl._attendre_les_fills([{"order_id": "x", "broker_symbol": "A"}], [], Sonde(), None)
    sortie = capsys.readouterr().out
    assert "1 ordre(s) lisible(s)" in sortie and "TOUJOURS ILLISIBLE" not in sortie


def test_un_courtier_qui_explose_ne_casse_pas_le_run(rl, capsys):
    class Casse:
        def orders(self, limit=100):
            raise RuntimeError("API down")
    rl._attendre_les_fills([{"order_id": "x", "broker_symbol": "AAA"}], [], Casse(), None)
    assert "Attente des fills" in capsys.readouterr().out   # dit, jamais levé


def test_aucun_ordre_identifie_n_attend_rien(rl, capsys):
    b = Courtier()
    rl._attendre_les_fills([{"order_id": None, "broker_symbol": "AAA"}], [], b, None)
    assert b.lectures == 0
    assert "aucun ordre à attendre" in capsys.readouterr().out


# --- ce qui manque est NOMMÉ ------------------------------------------------

def test_les_ouvertures_manquantes_sont_nommees_et_le_rattrapage_cite(rl, capsys):
    """Le 22/09 la ligne disait « 4 sans achat exécuté LISIBLE » — un nombre, sans un
    nom. On ne pouvait ni vérifier, ni rattraper."""
    opens = [{"symbol": "TTEK", "fill": None}, {"symbol": "DUOL", "fill": None},
             {"symbol": "HIMS", "fill": {"qty": 1, "avg_price": 2}}]
    rl._dire_les_ouvertures(1, 2, opens)
    sortie = capsys.readouterr().out
    assert "TTEK" in sortie and "DUOL" in sortie and "HIMS" not in sortie
    assert "completer-ouvertures" in sortie


def test_sans_manquant_la_ligne_reste_breve(rl, capsys):
    rl._dire_les_ouvertures(3, 0, [{"symbol": "AAA", "fill": {"qty": 1}}])
    sortie = capsys.readouterr().out
    assert "3 ouverture(s) enregistrée(s)" in sortie
    assert "completer-ouvertures" not in sortie
