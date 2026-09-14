"""Un prix négatif sur un contrat à terme est un FAIT, pas une corruption.

CE QUE CE TEST PROTÈGE. L'audit appliquait `val <= 0 → critique` à toute série, sans
distinction. Sur `CL=F` il criait donc au rouge quatre fois pour le 20 et le 21 avril
2020 — les jours où le contrat WTI de mai s'est réglé sous zéro, un événement de marché
documenté : quand stocker coûte plus cher que le baril ne vaut, le détenteur paie pour
se défaire de la livraison.

Quatre faux positifs sur dix criticals suffisent à apprendre au lecteur à ignorer le
rouge. Un cri-au-loup ne coûte pas seulement son propre bruit : il coûte la crédibilité
des vrais, et les vrais sont ici les six zéros exacts d'AAVE, ICP et DYDX.

La frontière tient en une phrase : un prix peut être NÉGATIF, jamais ABSENT.
"""
from dataclasses import dataclass
from datetime import date, timedelta

from packages.data.audit import audit_series


@dataclass
class B:
    ts: date
    open: float = 10.0
    high: float = 11.0
    low: float = 9.0
    close: float = 10.0
    volume: float = 1000.0


def _serie(n: int = 80):
    fin = date(2020, 4, 30)
    return [B(fin - timedelta(days=n - 1 - i)) for i in range(n)]


def _accuracy(symbole, barres, severite):
    return [a for a in audit_series(symbole, barres, now=date(2020, 5, 1))
            if a.kind == "accuracy" and a.severity == severite]


def test_le_wti_a_moins_37_dollars_n_est_plus_une_anomalie_critique():
    """20 avril 2020 : le contrat WTI de mai s'est réglé à −37,63 $. C'est arrivé."""
    barres = _serie()
    barres[-1] = B(date(2020, 4, 30), open=-14.0, high=1.0, low=-40.32, close=-37.63)
    assert _accuracy("CL=F", barres, "critical") == []


def test_mais_le_prix_negatif_reste_VISIBLE_en_avertissement():
    """Plausible n'est pas invisible : l'audit doit continuer à le montrer."""
    barres = _serie()
    barres[-1] = B(date(2020, 4, 30), open=-14.0, high=1.0, low=-40.32, close=-37.63)
    avertissements = _accuracy("CL=F", barres, "warning")
    assert any("négatif" in a.detail for a in avertissements)


def test_un_zero_exact_reste_critique_MEME_sur_un_terme():
    """Un prix peut être négatif, pas absent. `0.0` pile = valeur manquante."""
    barres = _serie()
    barres[-1] = B(date(2020, 4, 30), open=0.0, high=11.0, low=0.0, close=10.0)
    critiques = _accuracy("CL=F", barres, "critical")
    assert len(critiques) == 2                       # open et low
    assert all("≤ 0" in a.detail for a in critiques)


def test_une_action_ne_peut_pas_coter_negatif():
    """Aucune action ne vaut moins que rien : là, c'est bien de la donnée cassée."""
    barres = _serie()
    barres[-1] = B(date(2020, 4, 30), open=-5.0, high=11.0, low=-6.0, close=10.0)
    assert len(_accuracy("AAPL", barres, "critical")) == 2


def test_un_jeton_crypto_non_plus():
    """Le cas réel : AAVE, ICP et DYDX ont un open et un low à 0.0 le jour de leur
    introduction — le fournisseur n'avait pas la donnée et l'a rendue en zéro."""
    barres = _serie()
    barres[-1] = B(date(2020, 4, 30), open=0.0, high=55.0, low=0.0, close=52.0)
    critiques = _accuracy("AAVE-USD", barres, "critical")
    assert len(critiques) == 2
    assert {"open", "low"} == {a.detail.split()[0] for a in critiques}


def test_le_suffixe_terme_ne_se_confond_pas_avec_un_ticker_ordinaire():
    """`=F` est la convention du dépôt (snapshot.py:91). Pas de faux positif dessus."""
    from packages.data.audit import _peut_coter_negatif
    assert _peut_coter_negatif("CL=F") and _peut_coter_negatif("gc=f")
    assert not _peut_coter_negatif("AAPL")
    assert not _peut_coter_negatif("AAVE-USD")
    assert not _peut_coter_negatif("EURUSD=X")       # paire de change, pas un terme


def test_une_serie_saine_ne_declenche_rien():
    assert _accuracy("CL=F", _serie(), "critical") == []
    assert _accuracy("AAPL", _serie(), "critical") == []
