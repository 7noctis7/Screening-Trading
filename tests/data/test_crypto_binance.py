"""La pagination est la seule partie qui peut mentir sans le réseau.

Une source qui rend 1000 barres à la fois se lit page par page. Deux façons d'échouer
en silence : boucler sur la même page jusqu'au plafond, ou perdre les barres au-delà de
la première. Les deux donnent une série d'apparence normale.
"""

from __future__ import annotations

from packages.data.crypto_binance import historique, parse_ohlcv, url_klines

JOUR_MS = 86_400_000
DEBUT = 1_420_070_400_000          # 2015-01-01, en millisecondes


def _klines(n: int, depuis_ms: int = DEBUT) -> list[list]:
    """n barres quotidiennes au format Binance, prix croissants."""
    return [[depuis_ms + i * JOUR_MS, 10 + i, 11 + i, 9 + i, 10.5 + i, 100 + i,
             depuis_ms + (i + 1) * JOUR_MS - 1] for i in range(n)]


def test_une_ligne_malformee_est_ignoree_pas_devinee() -> None:
    """Une barre inventée vaut moins qu'une barre absente."""
    barres = parse_ohlcv(_klines(2) + [["x"], None, [1, 2, 3]])
    assert len(barres) == 2
    assert barres[0][0] == "2015-01-01"
    assert barres[0][4] == 10.5


def test_la_pagination_recupere_au_dela_de_la_premiere_page() -> None:
    """LE test. Sans enchaînement, on garde 1000 barres en croyant tout avoir."""
    total = _klines(2300)
    appels: list[str] = []

    def faux_get(url: str):
        appels.append(url)
        depuis = int(url.split("startTime=")[1].split("&")[0])
        return [k for k in total if k[0] >= depuis][:1000]

    barres = historique("UNI", get_json=faux_get)
    assert len(barres) == 2300, f"{len(barres)} barres au lieu de 2300"
    assert len(appels) == 3, appels
    assert [b[0] for b in barres] == sorted(b[0] for b in barres)


def test_une_source_qui_repete_la_meme_page_ne_boucle_pas() -> None:
    """Sans garde-fou, une source figée tournerait jusqu'au plafond de pages en
    empilant les mêmes jours — un historique gonflé de doublons."""
    appels = []

    def faux_get(url: str):
        appels.append(url)
        return _klines(1000)              # toujours la MÊME page

    barres = historique("ARB", get_json=faux_get)
    assert len(barres) == 1000
    assert len(appels) == 2, "la boucle ne s'est pas arrêtée sur une page sans progrès"


def test_une_source_muette_rend_une_liste_vide() -> None:
    assert historique("XXX", get_json=lambda _u: None) == []


def test_l_url_cible_la_paire_usdt_quotidienne() -> None:
    url = url_klines("uni", DEBUT)
    assert "symbol=UNIUSDT" in url and "interval=1d" in url
    assert f"startTime={DEBUT}" in url and "limit=1000" in url


# ─── Intraday 1h / 4h (18/09) ──────────────────────────────────────────────────────

def test_l_intervalle_change_l_URL_et_rien_d_autre():
    from packages.data.crypto_binance import url_klines

    assert "interval=1h" in url_klines("BTC", 0, 10, "1h")
    assert "interval=4h" in url_klines("BTC", 0, 10, "4h")
    assert "interval=1d" in url_klines("BTC", 0, 10)          # défaut inchangé


def test_un_intervalle_INCONNU_est_refuse_pas_remplace_par_le_defaut():
    """Un `.get(tf, "1d")` silencieux rendrait du quotidien à qui demande du 15m, et
    l'étiquetterait 15m — le défaut trouvé le même jour chez yfinance."""
    import pytest

    from packages.data.crypto_binance import historique, url_klines
    with pytest.raises(ValueError, match="non géré"):
        url_klines("BTC", 0, 10, "15m")
    with pytest.raises(ValueError, match="non géré"):
        historique("BTC", interval="15m", get_json=lambda _u: [])


def test_la_cle_intraday_est_un_INSTANT_pas_un_jour():
    """Garder la clé au jour en 1h écraserait 24 barres sur 24 et n'en laisserait qu'une
    — une perte massive et parfaitement silencieuse."""
    from packages.data.crypto_binance import parse_ohlcv

    h = 3_600_000
    klines = [[k * h, 1, 2, 0.5, 1.0 + k, 5, (k + 1) * h - 1] for k in range(3)]
    b = parse_ohlcv(klines, "1h", maintenant_ms=10 * h)
    assert len(b) == 3, "trois heures distinctes doivent rester trois barres"
    assert b[0][0].startswith("1970-01-01T00:00")
    jour = parse_ohlcv(klines, "1d", maintenant_ms=10 * h)
    assert len(jour) == 1 and jour[0][0] == "1970-01-01", "en 1d, la clé reste le jour"


def test_la_bougie_EN_COURS_n_est_jamais_ingeree():
    """Son plus-haut et sa clôture bougent encore : l'écrire produit une barre qui se
    contredira à la lecture suivante, et une décision qui la lirait ferait du look-ahead
    à l'échelle de la période. Binance donne `closeTime` — le filtre est exact."""
    from packages.data.crypto_binance import parse_ohlcv

    h, now = 3_600_000, 5 * 3_600_000
    klines = [[3 * h, 1, 2, 0.5, 1.5, 5, 4 * h - 1],      # close < now → gardée
              [4 * h, 1, 2, 0.5, 1.6, 5, 5 * h - 1],      # close == now-1 → gardée
              [5 * h, 1, 9, 0.1, 1.7, 5, 6 * h - 1]]      # close > now → EN COURS
    b = parse_ohlcv(klines, "1h", maintenant_ms=now)
    assert len(b) == 2
    assert all(not x[0].startswith("1970-01-01T05") for x in b)


def test_le_curseur_avance_de_L_INTERVALLE_pas_d_un_jour():
    """Réutiliser JOUR_MS en 1h sauterait 23 barres sur 24, en silence."""
    from packages.data.crypto_binance import LIMITE, historique

    h, vues = 3_600_000, []

    def faux(url: str):
        from urllib.parse import parse_qs, urlparse
        d = int(parse_qs(urlparse(url).query)["startTime"][0])
        vues.append(d)
        return [[d + k * h, 1, 2, 0.5, 1.0, 5, d + (k + 1) * h - 1]
                for k in range(LIMITE)]

    barres = historique("BTC", "2020-01-01", get_json=faux, plafond_pages=3,
                        interval="1h")
    pas = [vues[i + 1] - vues[i] for i in range(len(vues) - 1)]
    assert pas == [LIMITE * h] * (len(vues) - 1)
    assert len(barres) == 3 * LIMITE, "aucune barre perdue ni dupliquée entre les pages"


def test_le_plafond_de_pages_suit_l_INTERVALLE():
    """20 pages couvrent 55 ans en quotidien et à peine trois ans en 1h. Un plafond trop
    bas tronque l'historique SANS ERREUR — la pire façon de perdre des données."""
    from packages.data.crypto_binance import PLAFOND_PAGES_PAR_INTERVALLE as P

    assert P["1h"] > P["4h"] > P["1d"]
    assert P["1h"] * 1000 / (24 * 365) > 10, "moins de 10 ans d'historique en 1h"
