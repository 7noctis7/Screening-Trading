from types import SimpleNamespace
import pytest
from packages.portfolio import user_analysis


def _bars(scale: float):
    return [SimpleNamespace(ts=f"2025-{i // 28 + 1:02d}-{i % 28 + 1:02d}", close=100 + scale * i) for i in range(70)]


def test_analyse_reelle_alignee_et_scenarios(monkeypatch):
    monkeypatch.setattr(user_analysis, "_load", lambda symbol, years, classe=None: (symbol, _bars(1 if symbol == "AAA" else .5)))
    result = user_analysis.analyze([{"symbol": "AAA", "weight": .6}, {"symbol": "BBB", "weight": .4}])
    assert result["available"] is True
    assert result["n_observations"] == 69
    assert result["alignment"] == "intersection de dates, aucun remplissage"
    assert sum(result["scenarios"]["prudent"]) == pytest.approx(1)


def test_refuse_si_un_historique_manque(monkeypatch):
    monkeypatch.setattr(user_analysis, "_load", lambda symbol, years, classe=None: (None, []))
    result = user_analysis.analyze([{"symbol": "ABSENT", "weight": 1.0}])
    assert result["available"] is False
    assert result["missing"] == ["ABSENT"]


def test_utilise_les_series_du_snapshot_et_gere_le_cash(monkeypatch):
    monkeypatch.setattr(user_analysis, "_load", lambda symbol, years, classe=None: (None, []))
    supplied = [{"t": bar.ts, "c": bar.close} for bar in _bars(1)]
    result = user_analysis.analyze([{"symbol": "AAA", "weight": .8},
                                    {"symbol": "CASH:USD", "weight": .2}],
                                   series_by_symbol={"AAA": supplied})
    assert result["available"] is True
    assert result["aliases"]["CASH:USD"] == "CASH:USD"


# ── Régressions du 06/09 : l'étape 4 restait vide sur un univers mixte actions+crypto ──


def test_ticker_crypto_nu_produit_la_variante_usd():
    """`ETH` doit tenter `ETH-USD` : c'est la forme stockée dans data/crypto.db."""
    assert "ETH-USD" in user_analysis._aliases("ETH")
    assert "BTC-USD" in user_analysis._aliases("BTC")
    assert user_analysis._aliases("ETHUSDT")[:2] == ["ETHUSDT", "ETH-USD"]


def test_action_ne_paie_pas_la_variante_crypto(monkeypatch):
    """L'alias nu répond en premier : `-USD` n'est jamais essayé pour une action."""
    essais = []
    monkeypatch.setattr(user_analysis, "load_bars",
                        lambda alias, years=5: essais.append(alias) or _bars(1))
    monkeypatch.setattr(user_analysis, "_bars_crypto", lambda symbole, years: [])
    alias, bars = user_analysis._load("AAPL", 5)
    assert alias == "AAPL" and essais == ["AAPL"]


def test_univers_mixte_actions_et_crypto_nue(monkeypatch):
    """Le cas de la capture : AAPL/NVDA/AMD + ETH nu. ETH ne répond que sous ETH-USD."""
    monkeypatch.setattr(user_analysis, "load_bars", lambda alias, years=5:
                        _bars(1) if alias in {"AAPL", "NVDA", "AMD", "ETH-USD"} else [])
    monkeypatch.setattr(user_analysis, "_bars_crypto", lambda symbole, years: [])
    result = user_analysis.analyze([{"symbol": "AAPL", "weight": 10}, {"symbol": "NVDA", "weight": 40},
                                    {"symbol": "AMD", "weight": 40}, {"symbol": "ETH", "weight": 10}])
    assert result["available"] is True
    assert result["aliases"]["ETH"] == "ETH-USD"


def test_les_trois_scenarios_sont_publies_sous_les_cles_du_front(monkeypatch):
    """Le front lit `dynamique` ; publier `hrp` le rendait introuvable, donc « indisponible »."""
    monkeypatch.setattr(user_analysis, "_load", lambda symbol, years, classe=None: (symbol, _bars(1 if symbol == "AAA" else .5)))
    result = user_analysis.analyze([{"symbol": "AAA", "weight": .6}, {"symbol": "BBB", "weight": .4}])
    assert set(result["scenarios"]) == {"prudent", "neutre", "dynamique"}
    for poids in result["scenarios"].values():
        assert sum(poids) == pytest.approx(1)


def test_alignement_sans_remplissage_et_etiquette_conforme():
    """Un ffill inventerait des rendements nuls le week-end pour les actions : la
    covariance mixte actions/crypto en sortirait faussée. L'étiquette doit dire le vrai."""
    series = {"ACTION": {"2025-01-01": 10.0, "2025-01-02": 11.0},
              "CRYPTO": {"2025-01-01": 5.0, "2025-01-02": 6.0, "2025-01-03": 7.0}}
    dates, matrix = user_analysis._align(series)
    assert dates == ["2025-01-01", "2025-01-02"]          # le 03 n'est pas comblé
    assert matrix.shape == (2, 2)
    assert user_analysis.ALIGNEMENT == "intersection de dates, aucun remplissage"


def test_paires_en_usdc_mènent_a_la_variante_usd():
    """Le screening publie `TRX/USDC`, `BTC/USDC`… La base stocke `{base}-USD`.

    MESURÉ le 07/09 : 7 des 15 candidats du jour partaient en « sans historique
    exploitable » parce que seul le suffixe `USDT` était reconnu. Normalisées, ces paires
    contenaient un tiret, et la variante `-USD` n'était jamais tentée."""
    from packages.portfolio.user_analysis import _aliases
    for paire, base in [("TRX/USDC", "TRX"), ("BTC/USDC", "BTC"), ("SOL/USDC", "SOL"),
                        ("ETH/USDT", "ETH"), ("BNB-BUSD", "BNB"), ("LINK/FDUSD", "LINK")]:
        assert f"{base}-USD" in _aliases(paire), paire


def test_la_devise_la_plus_longue_est_testee_en_premier():
    """Tester « USD » avant « USDC » amputerait `TRX-USDC` en `TRX-C`."""
    from packages.portfolio.user_analysis import _aliases
    assert "TRX-USD" in _aliases("TRX/USDC") and "TRX-C-USD" not in _aliases("TRX/USDC")


def test_une_classe_d_action_n_est_pas_prise_pour_une_paire():
    """`BRK-B` contient un tiret mais n'est pas coté en dollar : aucune variante inventée."""
    from packages.portfolio.user_analysis import _aliases
    assert _aliases("BRK-B") == ["BRK-B"]


def test_une_action_connue_ne_tombe_JAMAIS_sur_un_alias_crypto():
    """Le repli `-USD` sert à retrouver `ETH-USD` depuis `ETH`. Appliqué à une action, il
    valoriserait un titre avec la série d'un jeton — mesuré le 07/09 : `ABC`
    (AmerisourceBergen, sans barres locales car délistée) trouvait « Abell Coin USD »."""
    from packages.portfolio.user_analysis import _aliases
    for ticker in ("ABC", "BK", "EA", "NDX"):
        for classe in ("equity", "etf", "commodity", "forex"):
            assert _aliases(ticker, classe) == [ticker], (ticker, classe)


def test_une_crypto_conserve_son_repli_usd():
    """Le garde-fou ne doit pas casser le cas qu'il protège."""
    from packages.portfolio.user_analysis import _aliases
    assert "ETH-USD" in _aliases("ETH", "crypto")
    assert "AAVE-USD" in _aliases("AAVE/USDC", "crypto")


def test_classe_inconnue_garde_le_repli_mais_l_alias_reste_publie():
    """Un portefeuille importé à la main n'a pas de classe : le repli reste utile pour
    « ETH ». L'ambiguïté résiduelle est rendue VISIBLE par l'alias publié dans la ligne."""
    from packages.portfolio.user_analysis import _aliases
    assert _aliases("ETH", None) == ["ETH", "ETH-USD"]


# --- Expliquer un poids : volatilité par ligne et séries arrêtées ------------------------

def test_le_diagnostic_par_actif_donne_la_volatilite_de_chaque_ligne():
    """Sans elles, un min-variance à 99 % sur une ligne ne se distingue pas d'un bug."""
    import numpy as np
    from packages.portfolio.user_analysis import diagnostic_par_actif
    loaded = {"CALME": {"2026-09-04": 1.0}, "AGITE": {"2026-09-04": 1.0}}
    rendements = np.array([[0.001, -0.001, 0.001, -0.001],
                           [0.05, -0.05, 0.05, -0.05]])
    out = diagnostic_par_actif(loaded, ["CALME", "AGITE"], rendements)
    assert out[0]["vol_annuelle"] < out[1]["vol_annuelle"] / 10
    assert all(d["arretee"] is False for d in out)


def test_une_serie_arretee_est_SIGNALEE_mais_pas_retiree():
    """On ne peut pas écarter une ligne du portefeuille de l'utilisateur : il la détient.
    On l'avertit — une série figée n'a plus de variance et paraît sans risque."""
    import numpy as np
    from packages.portfolio.user_analysis import diagnostic_par_actif
    loaded = {"VIF": {"2026-09-04": 1.0}, "MORT": {"2026-06-18": 1.0}}
    out = diagnostic_par_actif(loaded, ["VIF", "MORT"], np.array([[0.01, -0.01], [0.0, 0.0]]))
    assert [d["symbol"] for d in out] == ["VIF", "MORT"]      # aucune ligne retirée
    assert out[1]["arretee"] is True and out[0]["arretee"] is False
    assert out[1]["derniere_barre"] == "2026-06-18"


def test_une_serie_figee_affiche_une_volatilite_NULLE():
    """C'est le mécanisme complet : plus de variance mesurée → l'optimiseur la croit sûre."""
    import numpy as np
    from packages.portfolio.user_analysis import diagnostic_par_actif
    out = diagnostic_par_actif({"FIGE": {"2026-09-04": 1.0}}, ["FIGE"],
                               np.array([[0.0, 0.0, 0.0]]))
    assert out[0]["vol_annuelle"] == 0.0
