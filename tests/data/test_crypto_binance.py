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
