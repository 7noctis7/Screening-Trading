"""Une vente réelle doit fermer le lot du robot, QUELLE QUE SOIT sa capture de features.

POURQUOI CE FICHIER (22/09). `open_lots` sélectionnait les lots ouverts par
`all(legacy=False)`. Or `legacy` ne dit pas « ce lot est-il au robot ? » mais « porte-t-il
les features de la décision ? ». Les lots rejoués depuis l'historique des ordres du
courtier (`reconstruire_journal`, préfixe `R-`) n'ont pas de features, valent donc
`legacy=1`, et étaient INVISIBLES à l'appariement des ventes.

Mesuré sur le compte réel ce jour-là : 5 ventes envoyées et exécutées chez le courtier,
UN SEUL aller-retour au journal — celui dont le lot venait d'une décision journalisée
(`P-`). Les quatre autres lots sont restés ouverts alors que le compte ne les détenait
plus : du réalisé perdu d'un côté, des positions fantômes de l'autre.

Les contrats épinglés ici :
  1. un lot `R-` (legacy=1) est fermé par sa vente — la régression du 22/09 ;
  2. fermer un lot ne RÉÉCRIT PAS son drapeau `legacy` (l'échantillon ML reste propre) ;
  3. un lot `LEG-` (import de provenance inconnue) n'est PAS apparié — son prix d'entrée
     n'est rattachable à aucun fill, l'apparier publierait un réalisé fabriqué ;
  4. ce qui n'a pas été fermé est NOMMÉ, jamais tu.
"""
from __future__ import annotations

from datetime import datetime, timezone

from packages.core.models import AssetClass, Side, TradeRecord
from packages.execution.live_roundtrip import close_sells, open_lots
from packages.storage import SqliteTradeJournal

TS = datetime(2026, 9, 18, tzinfo=timezone.utc)


def _journal(tmp_path):
    return SqliteTradeJournal(tmp_path / "journal.db")


def _lot(id: str, sym: str, qty: float = 10.0, price: float = 100.0) -> TradeRecord:
    return TradeRecord(
        id=id, instrument=sym, asset_class=AssetClass.EQUITY, venue="Alpaca",
        side=Side.LONG, qty=qty, entry_ts=TS, entry_price=price, avg_price=price,
        entry_reason="fill courtier")


def _vente(sym: str, qty: float = 10.0, prix: float = 120.0) -> dict:
    return {"symbol": sym, "venue": "Alpaca", "exit_price": prix, "qty_reelle": qty}


def test_un_lot_rejoue_du_courtier_est_ferme_par_sa_vente(tmp_path):
    """LA RÉGRESSION DU 22/09. `R-…` vaut `legacy=1` et doit pourtant se fermer."""
    j = _journal(tmp_path)
    j.append(_lot("R-20260918-Alpaca-CRM-3", "CRM"), legacy=True)
    assert [t.id for t in open_lots(j, instrument="CRM")] == ["R-20260918-Alpaca-CRM-3"]
    assert close_sells(j, [_vente("CRM")]) == 1
    assert open_lots(j, instrument="CRM") == []
    ferme = [t for t in j.all() if t.exit_ts][0]
    assert ferme.exit_price == 120.0 and ferme.pnl_gross == 200.0


def test_les_quatre_origines_robot_ferment_leur_lot(tmp_path):
    """`P-` (décision), `C-` (ouverture reconstituée) et `R-` (rejeu) : même périmètre."""
    j = _journal(tmp_path)
    j.append(_lot("P-20260921-Alpaca-BBY", "BBY"), legacy=False)
    j.append(_lot("C-NWS-a1b2c3", "NWS"), legacy=True)
    j.append(_lot("R-20260701-Alpaca-HPQ-7", "HPQ"), legacy=True)
    n = close_sells(j, [_vente("BBY"), _vente("NWS"), _vente("HPQ")])
    assert n == 3
    assert open_lots(j) == []


def test_fermer_un_lot_ne_reecrit_pas_son_drapeau_legacy(tmp_path):
    """`append` fait un UPSERT où `legacy` est mis à jour : le repasser à 0 en fermant
    un lot rejoué ferait entrer dans l'échantillon de calibration ML un enregistrement
    SANS features. Le drapeau du lot survit donc à sa fermeture."""
    j = _journal(tmp_path)
    j.append(_lot("R-20260918-Alpaca-TRV-1", "TRV"), legacy=True)
    j.append(_lot("P-20260921-Alpaca-BBY", "BBY"), legacy=False)
    close_sells(j, [_vente("TRV"), _vente("BBY")])
    assert j.legacy_ids() == {"R-20260918-Alpaca-TRV-1"}


def test_une_vente_partielle_conserve_aussi_le_drapeau(tmp_path):
    """La scission écrit DEUX lignes (fraction fermée + reste) : les deux héritent."""
    j = _journal(tmp_path)
    j.append(_lot("R-20260918-Alpaca-PSX-2", "PSX", qty=10.0), legacy=True)
    assert close_sells(j, [_vente("PSX", qty=4.0)]) == 1
    assert j.legacy_ids() == {"R-20260918-Alpaca-PSX-2", "R-20260918-Alpaca-PSX-2-X1"}
    reste = open_lots(j, instrument="PSX")
    assert len(reste) == 1 and abs(reste[0].qty - 6.0) < 1e-9


def test_un_import_de_provenance_inconnue_n_est_PAS_apparie(tmp_path):
    """`LEG-` : aucun script du dépôt ne l'écrit, deux symboles y portent jusqu'à 1,9 ×
    leur achat. Apparier une vente RÉELLE à ce prix d'entrée publierait un réalisé
    fabriqué — exactement l'invention que le mandat données-réelles interdit."""
    j = _journal(tmp_path)
    j.append(_lot("LEG-0042", "ICLN"), legacy=True)
    orphelines: list[dict] = []
    assert close_sells(j, [_vente("ICLN")], orphelines=orphelines) == 0
    assert [t.id for t in j.all() if t.exit_ts] == []            # rien d'inventé
    assert orphelines == [{"symbol": "ICLN", "venue": "Alpaca",
                           "qty_demandee": 10.0, "qty_fermee": 0.0}]


def test_un_prefixe_inconnu_est_ecarte_mais_NOMME(tmp_path):
    """« Ni inclus ni ignoré » (`perimetre_journal`) : écarté de l'appariement, et cité
    dans les orphelines pour qu'un préfixe nouveau se voie le jour où il apparaît."""
    j = _journal(tmp_path)
    j.append(_lot("X-9000", "ZZZ"), legacy=False)
    orphelines: list[dict] = []
    assert close_sells(j, [_vente("ZZZ")], orphelines=orphelines) == 0
    assert [o["symbol"] for o in orphelines] == ["ZZZ"]


def test_une_vente_qui_excede_les_lots_dit_le_residu(tmp_path):
    """Position antérieure au journal : l'excédent n'est pas fermé, et il est CHIFFRÉ."""
    j = _journal(tmp_path)
    j.append(_lot("P-20260921-Alpaca-NEM", "NEM", qty=3.0), legacy=False)
    orphelines: list[dict] = []
    assert close_sells(j, [_vente("NEM", qty=10.0)], orphelines=orphelines) == 1
    assert orphelines == [{"symbol": "NEM", "venue": "Alpaca",
                           "qty_demandee": 10.0, "qty_fermee": 3.0}]


def test_une_vente_entierement_appariee_ne_produit_aucune_orpheline(tmp_path):
    """Le témoin ne parle que quand il a quelque chose à dire."""
    j = _journal(tmp_path)
    j.append(_lot("P-20260921-Alpaca-DUOL", "DUOL", qty=10.0), legacy=False)
    orphelines: list[dict] = []
    assert close_sells(j, [_vente("DUOL", qty=10.0)], orphelines=orphelines) == 1
    assert orphelines == []


def test_une_vente_sans_prix_broker_reste_hors_orphelines(tmp_path):
    """Sans prix, la vente n'est pas un échec d'APPARIEMENT : le lot est laissé ouvert
    à dessein, et `_journal_sells` la compte déjà sous « sans prix broker ». La faire
    apparaître ici la compterait deux fois."""
    j = _journal(tmp_path)
    j.append(_lot("P-20260921-Alpaca-TTEK", "TTEK"), legacy=False)
    orphelines: list[dict] = []
    assert close_sells(j, [{"symbol": "TTEK", "venue": "Alpaca",
                            "exit_price": 0.0, "qty_reelle": 10.0}],
                       orphelines=orphelines) == 0
    assert orphelines == [] and len(open_lots(j)) == 1
