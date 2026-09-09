"""Le script de validation ne doit pas casser au moment où on en a besoin.

Il tourne UNE fois, un matin, sur la machine qui détient les bases — pas ici. Un
plantage à ce moment-là coûte la séance. On vérifie donc la PLOMBERIE de chaque étape
sur un panneau fabriqué : que les fonctions acceptent la forme attendue, produisent une
sortie, et ne modifient rien.

Le panneau est synthétique et le reste : il sert à exercer le code, pas à mesurer un
marché. C'est précisément la distinction que le garde-fou du script impose au vrai
lancement — et qui est testée en premier ici.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import numpy as np
import pytest

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))

_spec = importlib.util.spec_from_file_location(
    "valider_nouveautes", RACINE / "scripts" / "valider_nouveautes.py")
valider = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(valider)


@pytest.fixture
def panneau():
    g = np.random.default_rng(0)
    t, n = 420, 14
    close = 100.0 * np.exp(np.cumsum(g.normal(0, 0.015, (t, n)), axis=0))
    champs = {
        "open": close * (1 + g.normal(0, 0.002, (t, n))),
        "high": close * (1 + np.abs(g.normal(0, 0.006, (t, n)))),
        "low": close * (1 - np.abs(g.normal(0, 0.006, (t, n)))),
        "close": close,
        "volume": np.abs(g.lognormal(10, 0.5, (t, n))),
    }
    return champs, [f"ACT{i:02d}" for i in range(n)]


def test_le_script_refuse_de_mesurer_sur_du_synthetique() -> None:
    """LE garde-fou. Sans base réelle, il doit s'arrêter — pas produire des chiffres
    d'apparence sérieuse qui ne voudraient rien dire."""
    with pytest.raises(SystemExit) as e:
        valider.charger_panel(jours=60)
    assert "RÉELLE" in str(e.value)


def test_l_etape_anomalies_tourne_et_ne_modifie_rien(panneau, capsys) -> None:
    champs, symboles = panneau
    avant = {k: v.copy() for k, v in champs.items()}
    valider.etape_anomalies(champs, symboles)
    assert all(np.array_equal(avant[k], champs[k]) for k in champs), (
        "l'étape a modifié le panneau : un audit ne corrige jamais en silence"
    )
    assert "ANOMALIES CROISÉES" in capsys.readouterr().out


def test_l_etape_cvar_compare_bien_les_allocateurs(panneau, capsys) -> None:
    valider.etape_cvar(*panneau)
    sortie = capsys.readouterr().out
    for attendu in ("Mean-CVaR", "min-variance", "risk parity", "HRP", "équipondéré"):
        assert attendu in sortie, f"« {attendu} » absent de la comparaison"


def test_l_etape_generateur_n_ecrit_pas_sans_appliquer(panneau, capsys) -> None:
    """Par défaut le registre RÉEL ne doit pas bouger : sinon lancer le script « pour
    voir » gonflerait le compte d'essais, donc resserrerait la déflation de tous les
    travaux passés."""
    from packages.research.ledger import trial_count
    avant = trial_count()
    valider.etape_generateur(panneau[0], appliquer=False)
    assert trial_count() == avant, "le registre réel a été modifié sans --appliquer"
    assert "TEMPORAIRE" in capsys.readouterr().out


def test_l_etape_explicabilite_tourne(panneau, capsys) -> None:
    valider.etape_explication(*panneau)
    assert "EXPLICABILITÉ" in capsys.readouterr().out


def test_une_etape_en_echec_n_emporte_pas_les_suivantes(monkeypatch, capsys) -> None:
    """LE défaut vu en production le 08/09 : scikit-learn absent du VPS a fait planter
    l'étape 2, qui a emporté les étapes 3 et 4. Or l'ordre du script sert justement à
    obtenir les mesures SANS RISQUE d'abord — les perdre à cause d'une dépendance
    optionnelle manquante plus loin est l'inverse du but recherché."""
    g = np.random.default_rng(1)
    t, n = 300, 10
    close = 100.0 * np.exp(np.cumsum(g.normal(0, 0.015, (t, n)), axis=0))
    champs = {c: close.copy() for c in ("open", "high", "low", "close", "volume")}

    noms = [f"A{i}" for i in range(n)]
    from datetime import date, timedelta
    dates = [date(2024, 1, 1) + timedelta(days=i) for i in range(t)]
    panneau_stub = (champs, noms, "réel", ["equity"] * n, dates)
    monkeypatch.setattr(valider, "charger_panel", lambda jours=1500: panneau_stub)

    def _explose(*a, **k):
        raise ModuleNotFoundError("No module named 'sklearn'", name="sklearn")

    monkeypatch.setattr(valider, "etape_explication", _explose)
    monkeypatch.setattr(sys, "argv", ["valider_nouveautes.py"])

    assert valider.main() == 0, "le script s'arrête au lieu de continuer"
    sortie = capsys.readouterr().out
    assert "sklearn" in sortie and "ignorée" in sortie
    assert "MEAN-CVaR" in sortie, "l'étape 3 n'a pas tourné après l'échec de l'étape 2"
    assert "GÉNÉRATEUR" in sortie, "l'étape 4 n'a pas tourné"
    assert "ÉTAPES NON ABOUTIES" in sortie, "l'échec n'est pas récapitulé à la fin"


def test_une_serie_figee_annonce_sa_vraie_duree() -> None:
    """Vu sur données réelles : une série figée annonçait « 5 séances » quelle que soit
    sa durée, parce que l'entrée était publiée au moment où le compteur ATTEIGNAIT le
    seuil. Le chiffre était faux dans le sens qui minimise le problème."""
    from packages.storage.anomalies_panel import series_figees
    g = np.random.default_rng(2)
    p = 100.0 * np.exp(np.cumsum(g.normal(0, 0.01, (120, 6)), axis=0))
    p[40:100, 2] = p[39, 2]                     # 60 séances figées
    trouve = [f for f in series_figees(p) if f["actif_index"] == 2]
    assert trouve, "série figée non détectée"
    assert trouve[0]["jours"] >= 55, (
        f"durée annoncée {trouve[0]['jours']} pour 60 séances figées : le chiffre "
        "minimise le problème."
    )


def test_l_etape_cvar_survit_a_des_calendriers_differents(capsys) -> None:
    """Actions et crypto ne cotent pas les mêmes jours. Exiger un historique fini sur
    TOUTES les dates rend la grille commune vide par construction : mesuré sur le VPS,
    « moins de 5 actifs » et l'étape ne mesurait rien.

    Ici CHAQUE actif a des trous, à des dates décalées — la situation réelle d'un
    univers mêlant places et fuseaux. L'ancien filtre n'aurait retenu AUCUN actif ;
    c'est ce qui rend ce test capable d'échouer."""
    g = np.random.default_rng(4)
    t, n = 900, 12
    close = 100.0 * np.exp(np.cumsum(g.normal(0, 0.015, (t, n)), axis=0))
    for j in range(n):
        close[j + 5 :: 40, j] = np.nan      # trous décalés, ~2,5 % des séances
    assert not np.isfinite(np.diff(close, axis=0)).all(axis=0).any(), (
        "le scénario doit être tel qu'AUCUN actif n'a d'historique parfait, sinon "
        "l'ancien filtre s'en sortirait et le test ne prouverait rien"
    )
    champs = {c: close.copy() for c in ("open", "high", "low", "close", "volume")}
    valider.etape_cvar(champs, [f"A{i}" for i in range(n)])
    sortie = capsys.readouterr().out
    assert "comparaison impossible" not in sortie, (
        "des calendriers décalés suffisent encore à vider la comparaison"
    )
    assert "Mean-CVaR" in sortie and "min-variance" in sortie


def test_le_decoupage_en_blocs_ecrit_dans_les_bonnes_colonnes() -> None:
    """Le processus a été TUÉ par le système au premier lancement réel : la vue
    glissante d'un panneau 1499 × 774 sur 126 jours pèse 1,07 Go, et les réductions qui
    ignorent les NaN y ajoutent leur masque. Le découpage borne le pic.

    Le risque d'un découpage est de décaler les colonnes — un bloc écrit à la mauvaise
    place, et chaque actif hérite du signal d'un autre. Rien ne le signalerait : les
    chiffres restent plausibles. On donne donc à chaque actif une valeur RECONNAISSABLE
    et on vérifie qu'il la retrouve."""
    from packages.research import operateurs_signaux as ops
    n = 3 * ops.BLOC_ACTIFS + 7            # plusieurs blocs, dont un incomplet
    t = 120
    # Actif j : cours strictement constant à (j+1)·100 → sa volatilité vaut 0 et son
    # écart à la moyenne aussi. Un décalage de colonnes ne changerait pas ces deux-là,
    # d'où le troisième contrôle sur `position_dans_la_bande`, qui dépend du NIVEAU.
    c = np.tile(np.arange(1, n + 1, dtype=float) * 100.0, (t, 1))
    p = {"open": c, "close": c, "volume": c,
         "high": c * 1.10, "low": c * 0.90}
    bande = ops.OPERATEURS_TEMPORELS["position_dans_la_bande"](p, 21)
    attendu = (1.0 - 0.90) / (1.10 - 0.90)      # identique pour tout actif constant
    assert np.allclose(bande[-1], attendu), "valeur inattendue sur un cours constant"

    # Puis un panneau où chaque actif a une DYNAMIQUE propre : le momentum de l'actif j
    # vaut j/1000. Un bloc mal placé ferait apparaître le momentum du voisin.
    croissance = 1.0 + np.arange(n) / 1000.0
    c2 = np.cumprod(np.tile(croissance, (t, 1)), axis=0)
    p2 = {k: c2.copy() for k in ("open", "high", "low", "close", "volume")}
    mom = ops.OPERATEURS_TEMPORELS["momentum"](p2, 21)
    theorique = croissance ** 21 - 1.0
    assert np.allclose(mom[-1], theorique, rtol=1e-9), (
        "un actif ne retrouve pas SON propre momentum : les blocs écrivent dans les "
        "mauvaises colonnes, et chaque actif hérite du signal d'un autre."
    )


def test_le_decoupage_ne_change_aucun_chiffre() -> None:
    """Corriger une panne mémoire en changeant les résultats serait pire qu'elle."""
    from packages.research import operateurs_signaux as ops
    g = np.random.default_rng(0)
    c = 100 * np.exp(np.cumsum(g.normal(0, 0.015, (300, 130)), axis=0))
    p = {"open": c.copy(), "close": c.copy(), "volume": c.copy(),
         "high": c * 1.01, "low": c * 0.99}
    assert ops.BLOC_ACTIFS < 130, "le panneau de test doit couvrir plusieurs blocs"
    for nom_op, fn in ops.OPERATEURS_TEMPORELS.items():
        decoupe = fn(p, 63)
        ancien = ops.BLOC_ACTIFS
        try:
            ops.BLOC_ACTIFS = 10_000          # un seul bloc = comportement d'avant
            entier = fn(p, 63)
        finally:
            ops.BLOC_ACTIFS = ancien
        assert np.allclose(decoupe, entier, equal_nan=True), (
            f"{nom_op} ne rend pas la même chose par blocs qu'en une fois"
        )


def test_les_series_signalees_sont_ecartees_de_la_comparaison(capsys) -> None:
    """LE défaut du premier lancement complet (08/09) : Mean-CVaR proposait TRX/USDC
    56,2 %, BTC/USDC 42,4 % et TON/USDC 1,3 % — or TON/USDC figurait dans la liste des
    DONNÉES CASSÉES établie par l'étape 1, trois cadres plus haut.

    Le CVaR de 4,61 % était donc mesuré sur des prix faux, et le « gain » face à
    min-variance ne prouvait rien. Un audit qui trouve des séries corrompues et laisse
    l'étape suivante les utiliser ne sert à rien : pire, il fabrique un résultat
    flatteur, donc convaincant."""
    g = np.random.default_rng(9)
    t, n = 800, 10
    close = 100.0 * np.exp(np.cumsum(g.normal(0, 0.015, (t, n)), axis=0))
    close[300:, 0] = close[299, 0]          # actif 0 : figé, donc « sans risque »
    champs = {c: close.copy() for c in ("open", "high", "low", "close", "volume")}
    noms = [f"A{i}" for i in range(n)]

    valider.etape_cvar(champs, noms, ecarter={"A0"})
    sortie = capsys.readouterr().out
    assert "1 actif(s) écarté(s)" in sortie, "l'exclusion n'est pas appliquée"
    debut = sortie.index("Mean-CVaR sans plafond")
    assert "A0 " not in sortie[debut:], (
        "l'actif figé est encore proposé : il paraît sans risque à l'optimiseur et "
        "hérite d'un poids qu'il ne mérite pas"
    )


def test_l_audit_transmet_bien_les_actifs_a_ecarter(capsys) -> None:
    """Contrôle négatif du test précédent : si l'étape 1 ne rendait rien, l'exclusion
    ne pourrait pas s'appliquer et le chaînage serait décoratif."""
    g = np.random.default_rng(10)
    t, n = 400, 8
    close = 100.0 * np.exp(np.cumsum(g.normal(0, 0.015, (t, n)), axis=0))
    close[100:200, 3] = close[99, 3]        # série figée franche
    champs = {c: close.copy() for c in ("open", "high", "low", "close", "volume")}
    ecarter = valider.etape_anomalies(champs, [f"A{i}" for i in range(n)])
    assert isinstance(ecarter, set)
    assert "A3" in ecarter, f"la série figée n'est pas transmise : {ecarter}"


def test_les_actions_ne_sont_plus_eliminees_par_le_calendrier(capsys) -> None:
    """LE défaut du run du 08/09 : le filtre de couverture portait sur une grille
    CALENDAIRE. Une action cote 5 jours sur 7, donc sa couverture plafonne à 71 % — sous
    n'importe quel seuil raisonnable. Résultat : 36 actifs retenus, tous du crypto,
    c'est-à-dire la famille dont l'étape 1 venait de dire que les données étaient
    abîmées. La comparaison d'allocateurs portait sur un univers qui ne ressemble à
    aucun portefeuille réel.

    On identifie donc d'abord les vrais JOURS DE BOURSE (ceux où une large majorité
    cote), et on mesure la couverture SUR CES JOURS."""
    g = np.random.default_rng(11)
    t, n_act, n_cry = 1000, 14, 6
    prix = 100.0 * np.exp(np.cumsum(g.normal(0, 0.015, (t, n_act + n_cry)), axis=0))
    # deux jours sur sept, seules les « cryptos » cotent — comme un week-end
    week_end = (np.arange(t) % 7) >= 5
    prix[np.ix_(week_end, np.arange(n_act))] = np.nan
    champs = {c: prix.copy() for c in ("open", "high", "low", "close", "volume")}
    noms = [f"ACT{i}" for i in range(n_act)] + [f"CRY{i}" for i in range(n_cry)]

    valider.etape_cvar(champs, noms)
    sortie = capsys.readouterr().out
    assert "comparaison impossible" not in sortie, sortie[-400:]
    assert "jours de bourse identifiés" in sortie
    # 14 actions + 6 cryptos doivent TOUTES entrer : c'est le cœur du correctif.
    assert f"{n_act + n_cry} actifs couverts" in sortie, (
        "des actions sont encore éliminées par le calendrier : la comparaison ne "
        f"porterait que sur du crypto.\n{sortie}"
    )


def test_la_variante_plafonnee_est_publiee(capsys) -> None:
    """Mean-CVaR posait 54,6 % sur une ligne — PLUS concentré que min-variance (39,3 %),
    l'allocateur qu'on lui reproche justement de concentrer. Réduire la perte extrême en
    misant tout sur deux actifs n'est pas un progrès, c'est un autre risque : celui que
    la mesure ne voit pas. Les deux versions doivent être publiées côte à côte."""
    g = np.random.default_rng(12)
    t, n = 700, 15
    prix = 100.0 * np.exp(np.cumsum(g.normal(0, 0.015, (t, n)), axis=0))
    champs = {c: prix.copy() for c in ("open", "high", "low", "close", "volume")}
    valider.etape_cvar(champs, [f"A{i}" for i in range(n)])
    sortie = capsys.readouterr().out
    # La ligne du TABLEAU comparatif, pas seulement la liste des poids : c'est là que
    # se lit l'arbitraire — combien de perte extrême coûte le fait de se diversifier.
    ligne = re.search(r"Mean-CVaR plafonné \d+%\s+(\d+\.\d+)%\s+(\d+\.\d+)%"
                      r"\s+(\d+\.\d+)%", sortie)
    assert ligne, f"la variante plafonnée n'est pas dans le tableau :\n{sortie}"
    poids_max = float(ligne.group(3))
    assert poids_max <= valider.PLAFOND_LIGNE * 100 + 0.11, (
        f"poids max {poids_max:.1f}% au-delà du plafond demandé"
    )
    assert "Mean-CVaR sans plafond" in sortie


def test_les_actifs_non_negociables_sont_ecartes(capsys) -> None:
    """LE défaut du run du 08/09 : Mean-CVaR proposait USD/HKD 41,7 %, AUD/USD 12,9 %,
    USD/SGD 12,1 %… soit CENT POUR CENT de forex — alors que le TODO du projet dit noir
    sur blanc que le forex est en base mais NON NÉGOCIABLE, faute de courtier branché.

    Un allocateur qui propose ce qu'on ne peut pas acheter ne se compare à rien. Et
    USD/HKD est un cours ANCRÉ par sa banque centrale : sa volatilité est proche de zéro
    par construction, pas par qualité — le détecteur de séries figées ne l'attrape pas,
    il bouge à peine, mais il joue le même rôle."""
    g = np.random.default_rng(13)
    t, n_fx, n_eq = 700, 6, 12
    # le forex, calme par construction, écrase tout minimiseur de risque
    fx = 100.0 * np.exp(np.cumsum(g.normal(0, 0.0004, (t, n_fx)), axis=0))
    eq = 100.0 * np.exp(np.cumsum(g.normal(0, 0.018, (t, n_eq)), axis=0))
    prix = np.column_stack([fx, eq])
    champs = {c: prix.copy() for c in ("open", "high", "low", "close", "volume")}
    noms = [f"FX{i}" for i in range(n_fx)] + [f"EQ{i}" for i in range(n_eq)]
    classes = ["forex"] * n_fx + ["equity"] * n_eq

    valider.etape_cvar(champs, noms, classes=classes)
    sortie = capsys.readouterr().out
    assert "non négociables" in sortie, "le filtre d'investabilité ne s'applique pas"
    debut = sortie.index("Mean-CVaR sans plafond")
    assert "FX" not in sortie[debut:], (
        f"du forex est encore proposé alors qu'aucun courtier ne le dessert :\n"
        f"{sortie[debut:debut + 300]}"
    )


def test_la_repartition_par_classe_est_publiee(capsys) -> None:
    """Un minimiseur sur un univers mêlant des classes à volatilités très différentes
    ne fait pas une allocation : il choisit la moins agitée et y reste. Le CVaR obtenu
    est alors imbattable et ne veut rien dire. La répartition rend ce piège VISIBLE —
    la dissimuler ferait passer une dégénérescence pour une performance."""
    g = np.random.default_rng(14)
    t, n_a, n_b = 700, 8, 8
    calme = 100.0 * np.exp(np.cumsum(g.normal(0, 0.004, (t, n_a)), axis=0))
    agite = 100.0 * np.exp(np.cumsum(g.normal(0, 0.040, (t, n_b)), axis=0))
    prix = np.column_stack([calme, agite])
    champs = {c: prix.copy() for c in ("open", "high", "low", "close", "volume")}
    noms = [f"ETF{i}" for i in range(n_a)] + [f"CRY{i}" for i in range(n_b)]
    classes = ["etf"] * n_a + ["crypto"] * n_b

    valider.etape_cvar(champs, noms, classes=classes)
    sortie = capsys.readouterr().out
    assert "répartition par classe" in sortie, "la répartition n'est pas publiée"
    assert "etf" in sortie and "crypto" in sortie


def test_le_hors_echantillon_est_publie(capsys) -> None:
    """LE défaut qui restait après cinq lancements : tout était mesuré EN ÉCHANTILLON.
    Mean-CVaR minimise exactement le nombre rapporté — il ne peut pas perdre ce
    concours, c'est sa fonction objectif. Et min-variance perd sur le CVaR par
    construction, pas par infériorité. « 0,58 % contre 1,65 % » ne prouvait donc rien
    d'autre que « l'optimiseur a bien optimisé ce qu'on lui a demandé ».

    Les poids doivent être ajustés sur une fenêtre PASSÉE et notés sur la SUIVANTE."""
    g = np.random.default_rng(15)
    t, n = 900, 12
    prix = 100.0 * np.exp(np.cumsum(g.normal(0.0004, 0.015, (t, n)), axis=0))
    champs = {c: prix.copy() for c in ("open", "high", "low", "close", "volume")}
    valider.etape_cvar(champs, [f"A{i}" for i in range(n)])
    sortie = capsys.readouterr().out
    assert "HORS ÉCHANTILLON" in sortie, "le test hors échantillon n'est pas lancé"
    assert "rendement" in sortie, (
        "le rendement n'est pas publié : un allocateur qui divise la perte extrême "
        "par trois en divisant aussi le rendement par trois n'a rien amélioré"
    )


def test_un_allocateur_en_echec_n_emporte_pas_les_autres(capsys, monkeypatch) -> None:
    """Le hors échantillon réajuste six allocateurs sur chaque fenêtre. Si l'un lève
    sur une fenêtre dégénérée, les cinq autres doivent tout de même être notés."""
    import packages.portfolio.optimize as opt

    def _explose(*a, **k):
        raise RuntimeError("matrice singulière")

    monkeypatch.setattr(opt, "hrp_weights", _explose)
    g = np.random.default_rng(16)
    t, n = 900, 10
    prix = 100.0 * np.exp(np.cumsum(g.normal(0.0004, 0.015, (t, n)), axis=0))
    champs = {c: prix.copy() for c in ("open", "high", "low", "close", "volume")}
    valider.etape_cvar(champs, [f"A{i}" for i in range(n)])
    sortie = capsys.readouterr().out
    assert "HORS ÉCHANTILLON" in sortie
    assert "Mean-CVaR (nouveau)" in sortie.split("HORS ÉCHANTILLON")[1], (
        "un allocateur en échec a emporté les autres"
    )


def test_le_panneau_rend_aussi_ses_dates() -> None:
    """Sans les dates, on ne peut pas dire sur QUELLE période le test hors échantillon
    a porté — et une performance d'allocateur sans sa période ne veut rien dire : une
    poche obligataire brille de 2024 à 2026 et s'effondre en 2022, le chiffre est le
    même et la conclusion inverse. Le contrat est vérifié ici parce que trois appelants
    en dépendent et qu'un dépaquetage muet casserait tout le script."""
    import inspect

    source = inspect.getsource(valider.charger_panel)
    assert "return champs, symboles, mode," in source and "dates" in source.split(
        "return champs, symboles, mode,")[1].split("\n")[0], source[-300:]


def test_la_periode_hors_echantillon_affichee_est_la_bonne(capsys) -> None:
    """Un décalage d'un cran afficherait une PÉRIODE FAUSSE sous des chiffres justes —
    l'erreur la plus difficile à voir, parce que rien n'a l'air anormal.

    Les dates subissent exactement les mêmes filtres que les rendements : le premier
    jour saute (une différence en consomme un), puis les jours de bourse, puis les dates
    pleines. Le test reconstruit l'attendu à la main et le compare à l'affichage.
    """
    from datetime import date, timedelta

    g = np.random.default_rng(7)
    t, n = 400, 8
    close = 100.0 * np.exp(np.cumsum(g.normal(0, 0.015, (t, n)), axis=0))
    champs = {c: close.copy() for c in ("open", "high", "low", "close", "volume")}
    dates = [date(2024, 1, 1) + timedelta(days=i) for i in range(t)]

    valider.etape_cvar(champs, [f"A{i}" for i in range(n)], fenetre=252, pas=21,
                       dates=dates)
    sortie = capsys.readouterr().out

    # r perd le premier jour : la ligne i des rendements porte la date dates[i + 1].
    debut = dates[1 + 252]
    assert f"{debut}" in sortie, (
        f"période attendue à partir de {debut}, absente de :\n{sortie[-800:]}")
    assert "Période RÉELLEMENT mesurée" in sortie


def test_sans_dates_le_test_hors_echantillon_n_invente_pas_de_periode(capsys) -> None:
    """Contrôle négatif : appelé sans dates — le cas de plusieurs tests et de tout
    appelant tiers — le script se tait plutôt que d'afficher une période fausse."""
    g = np.random.default_rng(8)
    close = 100.0 * np.exp(np.cumsum(g.normal(0, 0.015, (400, 8)), axis=0))
    champs = {c: close.copy() for c in ("open", "high", "low", "close", "volume")}

    valider.etape_cvar(champs, [f"A{i}" for i in range(8)], fenetre=252, pas=21)
    assert "Période RÉELLEMENT mesurée" not in capsys.readouterr().out


def test_le_plafond_par_ligne_a_une_seule_definition() -> None:
    """Le tableau EN échantillon et le tableau HORS échantillon doivent plafonner au
    même niveau. Deux constantes jumelles qui divergent feraient comparer deux
    allocateurs différents sous le même nom, sans que rien ne le signale."""
    from scripts import comparaison_allocateurs

    assert valider.PLAFOND_LIGNE is comparaison_allocateurs.PLAFOND_LIGNE
    fichier = (RACINE / "scripts" / "valider_nouveautes.py").read_text(encoding="utf-8")
    assert "PLAFOND_LIGNE = " not in fichier, (
        "le plafond est redéfini dans le script au lieu d'être importé"
    )


def test_un_vrai_split_est_confirme_et_un_krach_ne_l_est_pas() -> None:
    """« 33 actifs à vérifier » n'est pas un rapport, c'est une corvée qu'on saute.

    Un split se distingue d'un krach par DEUX signaux qui doivent concorder : le ratio
    de prix tombe sur une fraction usuelle, ET le volume change d'échelle en sens
    inverse. Confondre les deux coûte cher dans les deux sens : ajuster un vrai krach
    invente un rendement, laisser un vrai split corrompt tous ceux qui le traversent.
    """
    g = np.random.default_rng(11)
    t = 300
    base = 100.0 * np.exp(np.cumsum(g.normal(0, 0.01, t)))
    volume = np.full(t, 1_000_000.0)

    split, vol_split = base.copy(), volume.copy()
    split[150:] /= 4.0                       # split 4:1
    vol_split[150:] *= 4.0                   # … et le volume suit, en sens inverse

    krach, vol_krach = base.copy(), volume.copy()
    krach[150:] *= 0.42                  # −58 % : brutal, hors des fractions usuelles
    vol_krach[150:] *= 6.0               # volume qui explose, sans lien avec le ratio

    champs = {"close": np.column_stack([split, krach]),
              "volume": np.column_stack([vol_split, vol_krach])}
    verdicts = valider._qualifier_splits(
        champs, ["SPLIT", "KRACH"],
        [{"symbole": "SPLIT", "pire": -0.75}, {"symbole": "KRACH", "pire": -0.58}])

    assert verdicts["SPLIT"]["certain"], verdicts["SPLIT"]
    assert not verdicts["KRACH"]["certain"], verdicts["KRACH"]
    assert "inexpliqué" in verdicts["KRACH"]["libelle"], verdicts["KRACH"]


def test_sans_volume_le_split_n_est_pas_tranche() -> None:
    """La règle du module : sans volume exploitable, on NE TRANCHE PAS. Annoncer
    « confirmé » sur le seul ratio ferait ajuster des krachs tombés par hasard sur une
    fraction ronde."""
    g = np.random.default_rng(12)
    close = 100.0 * np.exp(np.cumsum(g.normal(0, 0.01, 300)))
    close[150:] /= 4.0
    champs = {"close": close[:, None], "volume": np.zeros((300, 1))}

    v = valider._qualifier_splits(champs, ["X"], [{"symbole": "X", "pire": -0.75}])["X"]
    assert not v["certain"]
    assert "volume indisponible" in v["libelle"], v["libelle"]
