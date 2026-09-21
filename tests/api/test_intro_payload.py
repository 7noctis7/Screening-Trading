"""Les chiffres de l'intro sont DÉRIVÉS. Aucun n'est saisi, aucun n'est deviné.

CE QUE CES TESTS PROTÈGENT. La landing affichait « −9 % » de drawdown, issu d'un run
`backtest-preset` du 23/06 sur le PRESET SEUL et une fenêtre courte — son indice de
comparaison y montre 180 % de CAGR — pas un chiffre décennal. Le même dépôt
enregistre, pour l'allocation de PRODUCTION sur 2016→2026, un maxDD de −25,3 %.

Les deux sont vrais. Ils ne décrivent pas la même chose, et rien à l'écran ne le disait.
Un nombre recopié dans un composant se détache de ce qu'il mesure — d'autant plus vite
comparaison y montre 180 % de CAGR — pas un chiffre décennal. Le dépôt enregistre,
lui, un maxDD de −25,3 % pour l'allocation de PRODUCTION sur 2016→2026.
"""

from __future__ import annotations

from datetime import date, timedelta

from apps.api.intro_payload import MIN_POINTS_CAGR, construire, periode, trades

AUJ = date(2026, 9, 15)


def _serie(n: int, taux: float, fin: date = AUJ) -> list[dict]:
    """`n` points quotidiens finissant à `fin`, croissant de `taux` par point."""
    return [{"t": (fin - timedelta(days=n - 1 - i)).isoformat(),
             "v": 100 * (1 + taux) ** i} for i in range(n)]


# ── ce qui manque est DIT, jamais comblé ──────────────────────────────────────

def test_une_fenetre_sans_donnee_le_dit():
    p = periode(_serie(5, 0.001), "10a", "10 ANS", 10, AUJ)
    # Cinq points existent, donc la fenêtre est « disponible » — mais pas annualisable.
    assert p["disponible"] and p["cagr"] is None
    assert "trop courte" in p["cagr_motif"]


def test_une_courbe_vide_ne_produit_aucun_chiffre():
    p = periode([], "tout", "DEPUIS LE DÉBUT", None, AUJ)
    assert p["disponible"] is False and p["motif"]


def test_sans_trade_cloture_on_ne_calcule_pas_d_esperance():
    assert trades({"count": 0})["disponible"] is False
    assert trades({})["disponible"] is False


def test_une_perte_moyenne_nulle_rend_le_ratio_indefini_pas_infini():
    """Diviser par zéro produirait `inf`, que le front afficherait comme un chiffre."""
    t = trades({"count": 3, "avg_win": 10.0, "avg_loss": 0.0, "pnl_total": 30.0})
    assert t["ratio_gain_perte"] is None


# ── l'annualisation refuse les fenêtres courtes ───────────────────────────────

def test_trois_mois_de_hausse_ne_deviennent_pas_un_taux_annuel():
    """+20 % en trois mois annualisés feraient +107 % — aucune année ne fait ça."""
    p = periode(_serie(60, 0.003), "ytd", "YTD", 0, AUJ)
    assert p["croissance"] > 0.15
    assert p["cagr"] is None


def test_une_fenetre_assez_longue_annualise():
    """Deux conditions, et les deux comptent : assez de POINTS et assez d'ANNÉES.

    250 points quotidiens font 0,68 an — sous le seuil de 0,75. Il faut donc une série
    plus longue que `MIN_POINTS_CAGR` seul ne le laisse croire.
    """
    p = periode(_serie(400, 0.0005), "3a", "3 ANS", 3, AUJ)
    assert p["cagr"] is not None and 0 < p["cagr"] < 0.5
    assert p["annees"] >= 0.75


def test_assez_de_points_mais_pas_assez_d_annees_ne_suffit_pas():
    """Un pas horaire ferait 300 points en deux semaines : annualiser resterait faux."""
    dense = [{"t": (AUJ - timedelta(days=13 - i // 24)).isoformat(), "v": 100 + i}
             for i in range(MIN_POINTS_CAGR + 120)]
    assert periode(dense, "tout", "T", None, AUJ)["cagr"] is None


# ── le drawdown est un vrai pire-recul, pas un min ────────────────────────────

def test_le_drawdown_mesure_le_recul_DEPUIS_UN_SOMMET():
    courbe = [{"t": f"2026-01-{d:02d}", "v": v}
              for d, v in enumerate([100, 120, 90, 130], start=1)]
    p = periode(courbe, "tout", "T", None, AUJ)
    assert abs(p["max_drawdown"] - (90 / 120 - 1)) < 1e-9   # −25 %, pas −10 %


def test_une_courbe_qui_ne_recule_jamais_a_un_drawdown_nul():
    assert periode(_serie(40, 0.002), "tout", "T", None, AUJ)["max_drawdown"] == 0.0


# ── la comparaison part du MÊME jour ──────────────────────────────────────────

def test_les_deux_courbes_sont_en_base_100_au_meme_depart():
    nous, ref = _serie(300, 0.001), _serie(300, 0.0004)
    p = periode(nous, "tout", "T", None, AUJ, reference=ref)
    assert p["courbe"][0] == 100.0 and p["reference"][0] == 100.0
    assert p["courbe"][-1] > p["reference"][-1]      # la nôtre monte plus vite


def test_la_reference_est_tranchee_au_depart_REEL_de_notre_serie():
    """Si le backtest commence après l'indice, comparer depuis la borne théorique
    donnerait à l'indice une avance qu'il n'a pas eue face à nous."""
    nous = _serie(200, 0.001)                     # 200 jours seulement
    ref = _serie(900, 0.001)                      # l'indice remonte bien plus loin
    p = periode(nous, "3a", "3 ANS", 3, AUJ, reference=ref)
    assert len(p["reference"]) == len(p["courbe"])
    assert abs(p["reference_croissance"] - p["croissance"]) < 1e-6


def test_une_reference_absente_est_NOMMEE_pas_silencieuse():
    p = periode(_serie(50, 0.001), "tout", "T", None, AUJ, reference=None)
    assert p["reference"] is None and p["reference_motif"]


def test_le_reechantillonnage_garde_le_DERNIER_point():
    """C'est lui qui porte la performance finale : l'amputer fausserait la courbe."""
    p = periode(_serie(1000, 0.001), "tout", "T", None, AUJ)
    attendu = round(100 * (1.001 ** 999) / 100 * 100, 2)
    assert abs(p["courbe"][-1] - attendu) < 0.05


# ── la nature de la série est écrite, pas sous-entendue ───────────────────────

def test_le_payload_dit_que_c_est_un_BACKTEST():
    r = construire({"equity": _serie(50, 0.001)}, {"count": 0}, {"total": 929}, AUJ)
    assert "Backtest" in r["avertissement"]
    assert "paper" in r["avertissement"].lower()
    assert r["source"]


def test_les_cinq_fenetres_sont_toujours_rendues_meme_vides():
    """Une fenêtre absente doit apparaître avec son motif — sinon on croit qu'elle
    n'a jamais été demandée."""
    r = construire({"equity": _serie(10, 0.001)}, {"count": 0}, {"total": 929}, AUJ)
    assert [p["cle"] for p in r["periodes"]] == ["ytd", "3a", "5a", "10a", "tout"]
    assert all("libelle" in p for p in r["periodes"])


def test_une_exception_interne_ne_casse_pas_le_snapshot():
    r = construire({"equity": [{"t": "pas-une-date", "v": 10}]}, {}, {}, AUJ)
    assert r["periodes"][0]["disponible"] is False


# ─── La référence doit être RÉELLE ou absente (15/09) ─────────────────────────────────

def test_le_snapshot_n_envoie_jamais_une_reference_synthetique():
    """`sp` retombe sur une série SYNTHÉTIQUE quand l'indice n'est pas en base. Comparer la
    courbe du robot à un S&P 500 inventé serait le mensonge le plus efficace du site : une
    légende crédible, une courbe crédible, et rien derrière.

    Le reste du dashboard fait déjà ce tri avec `_sp_real` ; l'intro le faisait PAS.
    """
    import pathlib
    import re

    src = (pathlib.Path(__file__).resolve().parents[2]
           / "apps" / "api" / "snapshot.py").read_text(encoding="utf-8")
    # Découpage par ÉQUILIBRE DES PARENTHÈSES. La version d'avant coupait à la chaîne
    # « instruments) » et s'est cassée à l'ajout d'un argument — un test qui dépend de
    # la
    # forme exacte d'un appel tombe à la première évolution légitime.
    apres = src.split('"intro": _intro_section(', 1)[1]
    profondeur, fin = 1, 0
    for i, ch in enumerate(apres):
        profondeur += (ch == "(") - (ch == ")")
        if profondeur == 0:
            fin = i
            break
    appel = apres[:fin]

    # CHAQUE indice, pas seulement le S&P : dates ET valeurs conditionnées au même
    # drapeau de réalité. En conditionner une seule produirait un désalignement
    # silencieux — des cours vrais posés sur un calendrier inventé.
    drapeaux = set(re.findall(r"_(\w+)_real", appel))
    assert drapeaux, "aucune série n'est conditionnée à sa réalité"
    for d in sorted(drapeaux):
        assert appel.count(f"_{d}_real") == 2, (
            f"« _{d}_real » doit apparaître DEUX fois (dates et valeurs), "
            f"trouvé {appel.count(f'_{d}_real')}")


def test_sans_reference_l_intro_reste_disponible_et_le_dit():
    """Pas d'indice réel ⇒ on affiche NOTRE courbe seule, on n'invente pas de comparaison."""
    courbe = [{"t": f"2024-{m:02d}-01", "v": 100.0 + m} for m in range(1, 13)]
    out = construire({"equity": courbe}, {"count": 0}, {"total": 929}, reference=None)
    assert out["disponible"] is True
    p0 = out["periodes"][-1]                      # « depuis le début »
    assert p0["disponible"] is True
    assert p0["courbe"]                            # la nôtre est bien là
    assert p0["reference"] is None
    assert "aucune série de référence" in p0["reference_motif"]


# ── les BORNES de chaque fenêtre : l'intro les affiche, donc elles sont un contrat ──

def test_chaque_fenetre_disponible_porte_SES_deux_bornes():
    """« +142 % sur 10 ans » ne dit pas DE QUAND À QUAND. Deux fenêtres décennales
    qui ne commencent pas la même année ne se comparent pas, et rien à l'écran ne le
    signalerait. L'intro dessine ces deux dates : c'est un contrat, pas un détail
    interne du calcul."""
    for cle, libelle, ans in (("ytd", "YTD", 0), ("3a", "3 ANS", 3),
                              ("10a", "10 ANS", 10), ("tout", "DEPUIS LE DÉBUT", None)):
        p = periode(_serie(400, 0.001), cle, libelle, ans, AUJ)
        assert p["disponible"], cle
        assert p["debut"] and p["fin"], f"bornes manquantes pour {cle}"


def test_les_bornes_sont_des_dates_ISO_lisibles_sans_fuseau():
    """Le front les découpe à la main plutôt que de passer par `Date` : minuit UTC
    reculerait d'un jour dans un fuseau négatif, et la période mesurée changerait selon
    l'endroit d'où on regarde le site."""
    import re
    p = periode(_serie(400, 0.001), "3a", "3 ANS", 3, AUJ)
    for borne in ("debut", "fin"):
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", p[borne]), p[borne]


def test_les_bornes_sont_celles_de_la_serie_REELLE_pas_du_calendrier_demande():
    """Demander dix ans sur une série qui en compte un ne doit pas afficher un départ
    vieux de dix ans : la borne annonce ce qui a été MESURÉ."""
    p = periode(_serie(30, 0.001), "10a", "10 ANS", 10, AUJ)
    assert p["debut"] == (AUJ - timedelta(days=29)).isoformat()
    assert p["fin"] == AUJ.isoformat()


# ── PLUSIEURS références : comparer à un seul indice cache le choix de l'indice ───────

def _serie(n: int, taux: float, fin: date = AUJ) -> list[dict]:
    return [{"t": (fin - timedelta(days=n - 1 - i)).isoformat(),
             "v": 100 * (1 + taux) ** i} for i in range(n)]


def test_chaque_reference_a_sa_courbe_et_sa_croissance():
    """Un robot qui bat le S&P 500 et perd contre le CAC 40 ne raconte pas la même
    histoire selon celui qu'on affiche. Les deux doivent être calculés."""
    p = periode(_serie(400, 0.001), "3a", "3 ANS", 3, AUJ,
                references={"S&P 500": _serie(400, 0.0005),
                            "CAC 40": _serie(400, 0.0003)})
    noms = [r["nom"] for r in p["references"]]
    assert noms == ["S&P 500", "CAC 40"]
    for r in p["references"]:
        assert r["courbe"] and len(r["courbe"]) > 1
        assert r["croissance"] is not None and not r["motif"]


def test_une_reference_ABSENTE_est_dite_et_non_comblee():
    """Une série manquante n'est ni remplacée par celle d'à côté, ni inventée."""
    p = periode(_serie(400, 0.001), "3a", "3 ANS", 3, AUJ,
                references={"S&P 500": _serie(400, 0.0005), "CAC 40": []})
    cac = next(r for r in p["references"] if r["nom"] == "CAC 40")
    assert cac["courbe"] is None and cac["croissance"] is None
    assert "aucune série" in cac["motif"]


def test_une_reference_TROP_COURTE_sur_la_fenetre_le_dit():
    p = periode(_serie(400, 0.001), "10a", "10 ANS", 10, AUJ,
                references={"CAC 40": _serie(1, 0.0)})
    cac = p["references"][0]
    assert cac["courbe"] is None and "trop courte" in cac["motif"]


def test_les_cles_HISTORIQUES_restent_servies_pour_le_site_deja_deploye():
    """Le site statique en ligne lit encore `reference` / `reference_croissance`. Les
    retirer d'un coup casserait la page jusqu'à sa prochaine reconstruction — un
    déploiement ne doit jamais dépendre de la simultanéité de deux artefacts."""
    p = periode(_serie(400, 0.001), "3a", "3 ANS", 3, AUJ,
                references={"S&P 500": _serie(400, 0.0005),
                            "CAC 40": _serie(400, 0.0003)})
    assert p["reference"] == p["references"][0]["courbe"]
    assert p["reference_croissance"] == p["references"][0]["croissance"]


def test_les_cles_historiques_prennent_la_PREMIERE_reference_TRACABLE():
    """Si la première série manque, les clés héritées doivent porter la suivante — sinon
    le site déployé afficherait « pas de référence » alors qu'il en existe une."""
    p = periode(_serie(400, 0.001), "3a", "3 ANS", 3, AUJ,
                references={"S&P 500": [], "CAC 40": _serie(400, 0.0003)})
    assert p["reference"] is not None
    assert p["reference"] == p["references"][1]["courbe"]


def test_l_appel_a_UNE_seule_reference_continue_de_marcher():
    """L'ancienne signature reste servie : un appelant non migré ne doit pas casser."""
    p = periode(_serie(400, 0.001), "3a", "3 ANS", 3, AUJ,
                reference=_serie(400, 0.0005))
    assert p["reference"] and len(p["references"]) == 1


def test_construire_publie_les_NOMS_des_references():
    """Le front en tire ses couleurs et sa légende : il ne les devine pas."""
    from apps.api.intro_payload import construire
    d = construire({"equity": _serie(400, 0.001)}, {}, {"total": 1},
                   aujourdhui=AUJ,
                   references={"S&P 500": _serie(400, 0.0005),
                               "CAC 40": _serie(400, 0.0003)})
    assert d["references_noms"] == ["S&P 500", "CAC 40"]
