"""SFP / BOS / CHoCH / OTE / order block : géométrie exacte et absence de look-ahead.

Ces fonctions décident d'entrées. Deux façons de les faire mentir, testées ici :
lire une barre postérieure à `i`, et confondre une mèche (SFP) avec une clôture (BOS).
"""

from dataclasses import dataclass

from packages.indicators.liquidite_ict import (
    bos,
    choch,
    continuation_ote,
    impulsion,
    liquidite,
    order_block,
    sfp,
    zone_ote,
)


@dataclass
class B:
    open: float
    high: float
    low: float
    close: float
    volume: float


def _plat(n: int, prix: float = 100.0, vol: float = 1000.0) -> list[B]:
    return [B(prix, prix + 0.5, prix - 0.5, prix, vol) for _ in range(n)]


def _zigzag(n: int, base: float = 100.0, pente: float = 0.0,
            amplitude: float = 3.0, vol: float = 1000.0) -> list[B]:
    """Série oscillante : des pivots BIEN DÉFINIS, contrairement à une série plate.

    Une série plate n'a aucun extremum strict — donc aucun pivot, donc aucune structure.
    Ce n'est pas un défaut du code : c'est ce qu'une série plate est.
    """
    out = []
    for i in range(n):
        phase = i % 10                       # sommet UNIQUE en phase 5, creux en phase 0
        p = base + pente * i + amplitude * (phase if phase <= 5 else 10 - phase)
        out.append(B(p, p + 1.0, p - 1.0, p, vol))
    return out


def test_liquidite_exclut_la_barre_testee():
    """Inclure `i` dans sa propre référence rendrait tout franchissement impossible."""
    bars = _plat(60)  # noqa: F841 — série neutre : seuls les deux extrêmes posés comptent
    bars[30] = B(100, 108, 99, 107, 1000)          # sommet majeur
    bars[59] = B(100, 120, 99, 119, 1000)          # la barre testée dépasse tout
    bsl, ssl = liquidite(bars, 59, fenetre=50)
    assert bsl.prix == 108 and bsl.index == 30     # pas 120
    assert ssl is not None


def test_sfp_exige_le_retour_sous_le_niveau_et_le_volume():
    bars = _plat(60)
    bars[30] = B(100, 108, 99, 107, 1000)
    # mèche au-dessus de 108, clôture EN DESSOUS, volume 3x : SFP short
    bars[59] = B(105, 112, 104, 106, 3000)
    r = sfp(bars, 59, fenetre=50)
    assert r["sfp"] and r["sens"] == "short" and r["niveau"] == 108

    # même géométrie SANS volume : ce n'est plus un SFP
    bars[59] = B(105, 112, 104, 106, 900)
    assert sfp(bars, 59, fenetre=50)["sfp"] is False

    # volume mais clôture AU-DESSUS : cassure, pas échec
    bars[59] = B(105, 112, 104, 111, 3000)
    assert sfp(bars, 59, fenetre=50)["sfp"] is False


def test_bos_se_lit_sur_la_cloture_pas_sur_la_meche():
    """Confondre les deux fait prendre chaque chasse aux stops pour une continuation."""
    bars = _zigzag(60)
    plafond = max(float(b.high) for b in bars[:55])
    bars[59] = B(100, plafond + 5, 99, plafond - 1, 1000)   # mèche dessus, clôture dessous
    assert bos(bars, 59)["bos"] is False
    bars[59] = B(100, plafond + 5, 99, plafond + 2, 1000)   # clôture au-dessus
    r = bos(bars, 59)
    assert r["bos"] and r["sens"] == "haussier"


def test_bos_ne_lit_aucune_barre_posterieure_a_i():
    """LE test de look-ahead : réécrire l'après ne doit rien changer à la décision."""
    bars = _zigzag(80)
    plafond = max(float(b.high) for b in bars[:55])
    bars[59] = B(100, plafond + 5, 99, plafond + 2, 1000)
    avant = bos(bars, 59)
    for k in range(60, 80):
        bars[k] = B(500, 900, 400, 800, 99999)
    assert bos(bars, 59) == avant


def test_choch_est_un_bos_a_contre_tendance():
    """Même géométrie, contexte opposé — sans le contexte la distinction n'existe pas."""
    # tendance baissière EN ZIGZAG : une pente monotone n'a aucun pivot, donc
    # aucune structure à casser — l'absence de signal y serait correcte, pas probante.
    bars = _zigzag(60, base=200.0, pente=-2.0)
    plafond = max(float(b.high) for b in bars[:55])
    bars.append(B(80, plafond + 10, 79, plafond + 8, 1000))   # cassure haussière
    r = choch(bars, len(bars) - 1)
    assert r["tendance_precedente"] == "baissier"
    assert r["choch"] and r["sens"] == "haussier"


def test_zone_ote_encadre_618_et_786_de_l_impulsion():
    imp = {"disponible": True, "sens": "haussier", "bas": 100.0, "haut": 200.0,
           "amplitude": 100.0, "index_debut": 0, "index_fin": 10}
    z = zone_ote(imp)
    assert abs(z["haut_zone"] - 138.2) < 1e-9      # 200 - 0.618*100
    assert abs(z["bas_zone"] - 121.4) < 1e-9       # 200 - 0.786*100


def test_order_block_est_la_derniere_bougie_opposee_avant_l_impulsion():
    bars = [B(100, 101, 99, 100, 1000)] * 3
    bars = list(bars)
    bars.append(B(100, 101, 96, 97, 1000))          # bougie BAISSIÈRE (l'OB)
    for p in (100, 110, 120, 130):                  # impulsion haussière
        bars.append(B(p, p + 5, p - 1, p + 4, 1000))
    imp = {"disponible": True, "sens": "haussier", "index_debut": 3,
           "index_fin": len(bars) - 1, "bas": 96.0, "haut": 135.0, "amplitude": 39.0}
    ob = order_block(bars, imp)
    assert ob["disponible"] and ob["index"] == 3 and ob["bas"] == 96


def test_impulsion_indisponible_sans_pivot_confirme():
    assert impulsion(_plat(10), 9)["disponible"] is False


def test_continuation_refuse_quand_il_n_y_a_pas_de_bos():
    r = continuation_ote(_plat(60), 59)
    assert r["autorise"] is False and r["motif"] == "pas de BOS"
