"""`/api/journal` : les trades du ROBOT réellement ouverts PUIS clôturés, et eux seuls.

Ce test ne lit pas le code de la route : il lui donne un journal, et regarde ce qu'elle
en fait. Le journal contient les quatre cas qui se sont réellement présentés le 17/09 —
une décision journalisée fermée, un ordre reconstitué du fill réel fermé, un lot du
robot encore ouvert, et un lot d'import historique fermé au P&L énorme.

Le piège que ce test ferme : c'est exactement le lot d'import (`LEG-`) qui portait
−1 647,58 $ de réalisé, et c'est le lot reconstitué (`C-`, `legacy=1`) que l'ancien
filtre `all(legacy=False)` jetait alors qu'il vient d'un ordre du robot. Les deux
erreurs allaient dans le sens flatteur.

Le calcul vit dans `apps.api.journal_payload`, sans FastAPI : le contrat est donc
éprouvé ICI, pas seulement là où la dépendance est installée.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from apps.api.journal_payload import construire
from packages.core.models import AssetClass, Side, TradeRecord


def _lot(ident: str, *, ferme: bool, pnl: float = 0.0,
         symbole: str = "VZ") -> TradeRecord:
    entree = datetime(2026, 9, 10, 19, 8, tzinfo=UTC)
    sortie = datetime(2026, 9, 16, 19, 8, tzinfo=UTC) if ferme else None
    return TradeRecord(
        id=ident, instrument=symbole, asset_class=AssetClass.EQUITY, venue="Alpaca",
        side=Side.LONG, qty=10.0, entry_ts=entree, entry_price=50.0, avg_price=50.0,
        exit_ts=sortie, exit_price=51.0 if ferme else None,
        pnl_net=pnl if ferme else None, is_win=(pnl > 0) if ferme else None,
        duration_s=518400.0 if ferme else None,
        features_snapshot={"decision_price": 50.0})


@pytest.fixture
def reponse(tmp_path) -> dict:
    """Un journal jetable portant les quatre cas, passé tel quel au constructeur."""
    from packages.storage import SqliteTradeJournal

    j = SqliteTradeJournal(tmp_path / "journal.db")
    j.append(_lot("P-20260910-Alpaca-VZ", ferme=True, pnl=120.0), legacy=False)
    j.append(_lot("C-OSCR-4dfb61cb", ferme=True, pnl=-80.0, symbole="OSCR"),
             legacy=True)
    j.append(_lot("P-20260915-Alpaca-THC", ferme=False, symbole="THC"), legacy=False)
    j.append(_lot("LEG-ad4ac9fa7f59", ferme=True, pnl=-900.0, symbole="NWL"),
             legacy=True)
    d = construire(j, {"THC": 262.0}, {"THC": 10.0})
    assert d["available"]
    return d


def test_la_table_ne_porte_que_des_aller_retours_CLOTURES(reponse):
    """« Réellement ouvert PUIS clôturé » : un lot encore ouvert n'est pas un trade."""
    d = reponse
    assert all(r["exit_ts"] for r in d["rows"]), d["rows"]
    assert {r["symbol"] for r in d["rows"]} == {"VZ", "OSCR"}


def test_l_ordre_RECONSTITUE_du_fill_reel_est_dans_le_perimetre(reponse):
    """`C-OSCR` porte `legacy=1` faute de features, et vient pourtant d'un ordre que le
    robot a bel et bien passé. L'ancien filtre l'écartait — et il était PERDANT."""
    d = reponse
    assert "OSCR" in {r["symbol"] for r in d["rows"]}
    assert d["stats"]["n_closed"] == 2
    # Sa perte ENTRE dans le réalisé : c'est tout l'enjeu, pas la présence d'une ligne.
    assert d["stats"]["honnete"]["pnl_realise"] == 40.0        # +120 et −80
    # Deux fermés, donc sous le seuil : aucune espérance publiée, et le motif est dit.
    assert "expectancy" not in d["stats"]
    assert "UNCALIBRATED" in d["stats"]["status"]


def test_l_import_historique_reste_DEHORS_mais_reste_CHIFFRE(reponse):
    """Hors périmètre n'est pas « effacé » : ses 900 $ de perte doivent rester lisibles,
    sinon le panneau redevient un sous-ensemble muet sur ce qu'il omet."""
    d = reponse
    assert "NWL" not in {r["symbol"] for r in d["rows"]}
    origines = d["stats"]["origines"]
    assert origines["import"]["n"] == 1
    assert origines["import"]["pnl_realise"] == -900.0
    assert origines["robot"]["n"] == 3        # 2 fermés + 1 ouvert
    assert origines["inconnu"]["n"] == 0


def test_les_lots_ouverts_sont_PUBLIES_A_PART_jamais_supprimes(reponse):
    """Retirer les ouverts de la TABLE est la demande ; les faire disparaître de la PAGE
    en ferait le palmarès de trades soldés que cette page dénonce. Ils sortent donc par
    `ouverts`, et alimentent le contrepoids « toutes positions »."""
    d = reponse
    assert [r["symbol"] for r in d["ouverts"]] == ["THC"]
    assert d["stats"]["n_open"] == 1
    assert d["stats"]["honnete"]["n_ouverts"] >= 0   # calculé, jamais absent


# ─── Le capital réel se déduit-il du registre ? (18/09) ─────────────────────────────

def test_le_REALISE_du_compte_nomme_ses_DEUX_perimetres(tmp_path):
    """Le panneau des positions affiche le latent ; sans son pendant encaissé, une page
    de positions laisse croire que tout le chemin parcouru tient dans les lignes encore
    ouvertes. Et les deux périmètres diffèrent d'un ordre de grandeur — afficher le plus
    flatteur sans le dire serait le mensonge le plus facile du site."""
    from apps.api.journal_payload import realise_compte
    from packages.storage import SqliteTradeJournal

    j = SqliteTradeJournal(tmp_path / "journal.db")
    j.append(_lot("P-20260910-Alpaca-VZ", ferme=True, pnl=120.0), legacy=False)
    j.append(_lot("C-OSCR-4dfb61cb", ferme=True, pnl=-80.0, symbole="OSCR"),
             legacy=True)
    j.append(_lot("LEG-ad4ac9fa7f59", ferme=True, pnl=-900.0, symbole="NWL"),
             legacy=True)
    j.append(_lot("P-20260915-Alpaca-THC", ferme=False, symbole="THC"), legacy=False)

    r = realise_compte(j)
    assert r["total"] == -860.0          # 120 − 80 − 900 : ce que le COMPTE subit
    assert r["robot"] == 40.0            # 120 − 80 : décision + reconstitution
    assert r["hors_robot"] == -900.0     # l'import, nommé plutôt que fondu
    assert r["n_total"] == 3 and r["n_robot"] == 2, "les lots OUVERTS ne comptent pas"


def test_un_registre_VIDE_rend_zero_sans_rien_inventer(tmp_path):
    """Zéro trade soldé est une réponse ; elle ne doit pas ressembler à une panne, ni
    une panne ressembler à zéro (l'API distingue les deux avec `disponible`)."""
    from apps.api.journal_payload import realise_compte
    from packages.storage import SqliteTradeJournal

    r = realise_compte(SqliteTradeJournal(tmp_path / "vide.db"))
    assert r == {"total": 0.0, "robot": 0.0, "hors_robot": 0.0,
                 "n_total": 0, "n_robot": 0}
