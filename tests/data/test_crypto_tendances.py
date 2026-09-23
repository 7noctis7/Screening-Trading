"""Une carte qui énonce une thèse sans donner de quoi la réfuter est un slogan.

Le panneau « Ce que tout le monde cherche » affirmait depuis l'origine que « quand une
crypto arrive ici, le mouvement a souvent déjà eu lieu » — sans jamais montrer le
mouvement. Et le même appel `/search/trending` rendait TROIS listes dont deux étaient
téléchargées puis jetées : mesuré le 23/09 sur l'API réelle, `coins` 15, `nfts` 7,
`categories` 6.

Ce que ces tests épinglent :
  1. la variation 24 h vient du bloc `data`, sinon du top 100, sinon `None` — jamais 0 ;
  2. les catégories et les NFT ne sont plus perdus ;
  3. un champ rendu tantôt nu tantôt par devise est lu dans les deux formes ;
  4. le volume répond à une AUTRE question et reste une liste distincte.
"""
from __future__ import annotations

from packages.data.crypto_tendances import (
    parse_trending,
    parse_trending_autres,
    parse_volume,
)


def _coin(cid, sym, nom, rank=None, data=None):
    it = {"id": cid, "symbol": sym, "name": nom, "market_cap_rank": rank}
    if data is not None:
        it["data"] = data
    return {"item": it}


# --- 1. la variation 24 h, et ses trois sources ------------------------------

def test_la_variation_vient_du_bloc_data_quand_il_existe():
    d = {"coins": [_coin("bitcoin", "btc", "Bitcoin", 1,
                         {"price_change_percentage_24h": {"usd": -3.214}})]}
    assert parse_trending(d)[0]["chg24h"] == -3.21


def test_un_pourcentage_NU_est_lu_aussi():
    """CoinGecko rend ce champ tantôt par devise, tantôt nu. Ne lire qu'une forme
    produirait des None partout au premier changement d'API — la panne la plus
    discrète, puisqu'une carte vide ressemble à une carte sans actualité."""
    d = {"coins": [_coin("x", "x", "X", 2, {"price_change_percentage_24h": 5.5})]}
    assert parse_trending(d)[0]["chg24h"] == 5.5


def test_a_defaut_on_joint_sur_le_top_100():
    d = {"coins": [_coin("solana", "sol", "Solana", 5)]}
    marches = [{"id": "solana", "chg24h": 2.5}]
    assert parse_trending(d, marches)[0]["chg24h"] == 2.5


def test_une_ligne_HORS_top_100_et_sans_data_rend_None_et_jamais_zero():
    """La moitié des lignes tendance sont des rangs au-delà du 500ᵉ. Écrire 0 % y serait
    une invention — et c'est sur ces lignes que le chiffre importerait le plus."""
    d = {"coins": [_coin("astronaut", "astro", "astronaut", 617)]}
    assert parse_trending(d, [{"id": "bitcoin", "chg24h": 1.0}])[0]["chg24h"] is None


def test_le_bloc_data_PRIME_sur_la_jointure():
    """Deux sources, un ordre : la plus directe gagne, sinon on ne saurait pas laquelle
    on lit."""
    d = {"coins": [_coin("solana", "sol", "Solana", 5,
                         {"price_change_percentage_24h": {"usd": 9.9}})]}
    assert parse_trending(d, [{"id": "solana", "chg24h": 2.5}])[0]["chg24h"] == 9.9


def test_le_reste_de_la_ligne_est_inchange():
    """Garde-fou de non-régression : l'enrichissement ne doit rien casser."""
    r = parse_trending({"coins": [_coin("bitcoin", "btc", "Bitcoin", 1)]})[0]
    assert r["id"] == "bitcoin" and r["sym"] == "BTC" and r["rank"] == 1


# --- 2. ce qui était téléchargé puis jeté ------------------------------------

def test_les_categories_et_les_NFT_ne_sont_plus_perdus():
    d = {"coins": [],
         "categories": [{"id": "ai", "name": "Artificial Intelligence",
                         "data": {"market_cap_change_percentage_24h": {"usd": 4.2}}}],
         "nfts": [{"name": "Punks", "symbol": "punk",
                   "floor_price_in_native_currency": 32.5,
                   "native_currency_symbol": "eth",
                   "floor_price_24h_percentage_change": -1.5}]}
    r = parse_trending_autres(d)
    assert r["categories"] == [{"id": "ai", "name": "Artificial Intelligence",
                                "chg24h": 4.2}]
    assert r["nfts"][0]["sym"] == "PUNK" and r["nfts"][0]["plancher"] == 32.5


def test_un_pourcentage_de_categorie_NU_est_lu_aussi():
    d = {"categories": [{"id": "rwa", "name": "RWA",
                         "data": {"market_cap_change_percentage_24h": -2.0}}]}
    assert parse_trending_autres(d)["categories"][0]["chg24h"] == -2.0


def test_une_reponse_vide_ne_plante_pas():
    for vide in (None, {}, {"coins": None, "categories": None, "nfts": None}):
        r = parse_trending_autres(vide)
        assert r == {"categories": [], "nfts": []}
        assert parse_trending(vide) == []


# --- 3. le volume est une AUTRE question ------------------------------------

def test_le_volume_est_trie_et_borne():
    data = [{"id": f"c{i}", "symbol": f"s{i}", "name": f"N{i}",
             "total_volume": i * 1000, "market_cap": 10_000,
             "current_price": 1.0, "price_change_percentage_24h": 0.5}
            for i in range(1, 31)]
    r = parse_volume(data, n=20)
    assert len(r) == 20
    assert [x["volume"] for x in r] == sorted((x["volume"] for x in r), reverse=True)


def test_la_rotation_est_rendue_sans_etre_qualifiee():
    """Aucun seuil mesuré sur ces données : on publie le ratio, pas un verdict."""
    r = parse_volume([{"id": "a", "symbol": "a", "name": "A",
                       "total_volume": 30_000, "market_cap": 10_000}])
    assert r[0]["rotation"] == 3.0


def test_une_capitalisation_absente_rend_une_rotation_None():
    r = parse_volume([{"id": "a", "symbol": "a", "name": "A",
                       "total_volume": 30_000, "market_cap": None}])
    assert r[0]["rotation"] is None and r[0]["volume"] == 30_000


def test_une_ligne_sans_volume_est_ecartee():
    """Sans volume, la ligne ne répond pas à la question posée par cette carte."""
    r = parse_volume([{"id": "a", "symbol": "a", "name": "A", "total_volume": None},
                      {"id": "b", "symbol": "b", "name": "B", "total_volume": 5}])
    assert [x["sym"] for x in r] == ["B"]


def test_les_trois_listes_viennent_du_MEME_instantane(monkeypatch):
    """Deux fetches de /search/trending = deux instantanés, donc deux cartes fausses.

    Les coins et les catégories s'affichent l'un sous l'autre et prétendent décrire le
    même moment. Les lire à deux secondes d'intervalle suffit à ce que la liste du haut
    ne corresponde plus à celle du bas — un décalage invisible à l'écran, donc jamais
    remarqué. Un seul appel supprime la question.
    """
    from packages.data import crypto_market as M

    appels: list[str] = []

    listes = {M._MARKETS, M._CATEGORIES, M._VOLUME, M._LLAMA_CHAINS}

    def faux(url, *a, **k):
        appels.append(url)
        if url == M._TRENDING:
            return {"coins": [], "categories": [], "nfts": []}
        return [] if url in listes else {}

    monkeypatch.setattr(M, "_get_json", faux)
    M.cockpit()
    assert appels.count(M._TRENDING) == 1, appels
