"""Un cœur indiciel à 50 % était interdit par un plafond conçu pour les titres uniques.

CE QUE CE TEST PROTÈGE. Le portail bornait TOUTE ligne à 20 % du compte. L'allocation de
production vise pourtant « 50 % QQQ + 50 % preset ». Résultat, mesuré le 14/09 sur le
compte paper :

    QQQ  cible 46087$  détenu 43028$  ⛔ REFUSÉ [poids_ligne] ligne plafonnée à 20%

Le refus tombait à chaque passage. Et comme une VENTE n'est jamais bloquée, la ligne ne
pouvait que décroître : l'allocation affichée sur la page était inatteignable par
construction, et aucune interface ne le disait.

La distinction qui manquait : le plafond de ligne borne le risque IDIOSYNCRATIQUE — ce
qu'on perd si un émetteur s'effondre. Un panier de cent lignes ne porte pas ce risque-là.
Lui appliquer le même nombre confond « une position » et « un risque ».

Ce que ces tests NE valident pas : que 0,60 soit le bon chiffre. C'est une politique, pas
une mesure. Ils valident qu'un panier et un titre unique ne partagent plus le même plafond,
et que le panier reste borné.
"""

from packages.risk.order_gate import Limites, evaluer

CAP = 100_000.0


def _etat(detenu: float, panier: bool, brut: float = 0.0):
    from packages.risk.order_gate import EtatCompte
    return EtatCompte(equity=CAP, exposition_brute=brut, n_positions=5,
                      detenu_ligne=detenu, panier=panier)


def test_le_cas_QQQ_du_14_09_passe_desormais():
    """43 028 $ détenus, 3 059 $ demandés : refusé à 20 %, accepté comme panier."""
    lim = Limites()
    titre = evaluer("acheter", 3059.0, _etat(43028.0, panier=False), lim)
    panier = evaluer("acheter", 3059.0, _etat(43028.0, panier=True), lim)
    assert not titre.autorise and titre.regle == "poids_ligne"
    assert panier.autorise and panier.montant == 3059.0


def test_un_titre_unique_reste_borne_a_son_plafond():
    lim = Limites()
    v = evaluer("acheter", 5000.0, _etat(19_500.0, panier=False), lim)
    assert v.montant == 500.0          # 20 % de 100 000 − 19 500 déjà détenus


def test_un_panier_reste_BORNÉ_lui_aussi():
    """Plafond séparé ne veut pas dire exemption : 60 % reste une limite."""
    lim = Limites()
    v = evaluer("acheter", 50_000.0, _etat(59_000.0, panier=True), lim)
    assert v.montant == 1000.0         # 60 % de 100 000 − 59 000
    plein = evaluer("acheter", 5000.0, _etat(60_000.0, panier=True), lim)
    assert not plein.autorise


def test_les_deux_plafonds_sont_distincts_par_defaut():
    lim = Limites()
    assert lim.max_poids_ligne < lim.max_poids_ligne_panier
    assert lim.max_poids_ligne_panier <= 1.0     # jamais de levier par ce biais


def test_le_motif_dit_lequel_des_deux_a_mordu():
    """Un refus doit être lisible sans ouvrir le code."""
    lim = Limites()
    v = evaluer("acheter", 9e9, _etat(60_000.0, panier=True), lim)
    assert "60%" in v.motif and "diversifié" in v.motif


def test_le_defaut_ne_change_rien_pour_un_appelant_qui_se_tait():
    """`panier` vaut False par défaut : aucun appelant existant ne voit son plafond bouger."""
    from packages.risk.order_gate import EtatCompte
    muet = EtatCompte(equity=CAP, exposition_brute=0.0, n_positions=5, detenu_ligne=19_500.0)
    assert evaluer("acheter", 5000.0, muet, Limites()).montant == 500.0


def test_une_vente_n_est_jamais_bloquee_par_le_plafond_de_ligne():
    """Le désengagement reste inconditionnel — le correctif ne doit pas l'entamer."""
    v = evaluer("solder", 43_000.0, _etat(43_000.0, panier=False), Limites(), liquidation=True)
    assert v.autorise


def test_le_resume_affiche_les_deux_plafonds():
    assert "panier" in Limites().resume()
