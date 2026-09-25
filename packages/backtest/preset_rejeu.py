"""REJEU de la production — le seul backtest qui mesure ce que `make live` envoie (QML-001).

CE QUE ÇA CORRIGE. Trois implémentations du « preset » coexistaient, et aucune n'était celle
qui trade :

    preset_backtest                  univers momentum figé en 2015, 30 noms, pas de 21 j,
                                     bande de 3 points de poids, blackout toujours appliqué
    preset_equity_daily / ledger     idem sans portes ni tilt, fill au close du signal
    preset_latest_weights_explique   PRODUCTION : 12 noms re-sélectionnés à chaque passage,
                                     portes, plafond adaptatif, concentration, bande de
                                     0,5 % du capital, plancher de ligne, portail de risque

Le vault mesure en paper une détention médiane d'un jour et 41 clôtures par semaine, face à
un turnover backtest de 1,5×/an : on réglait un moteur et l'on en conduisait un autre.

LA MÉTHODE, et elle n'a qu'une règle : ne RIEN réimplémenter de la décision. À chaque date
`d`, on tronque les données à `d` inclus et l'on appelle `preset_latest_weights_explique`
elle-même — la fonction que `build_snapshot` appelle pour `make live`. Les ordres suivent
ensuite les briques de `run_live` : `rebalance_plan.decider` (bande et plancher) puis
`risk.order_gate.evaluer` (limites), ventes d'abord.

CE QUE LE REJEU NE REPRODUIT PAS — à lire avant tout chiffre :
  * la SÉLECTION PAR QUALITÉ. Le score fondamental n'existe qu'au présent : l'appliquer au
    passé serait une fuite. Le rejeu passe donc `quality={}`, soit la branche momentum
    que la production emprunte elle-même quand les fondamentaux manquent. Tant que la
    production sélectionne par qualité, CETTE branche reste UNCALIBRATED ;
  * l'EXÉCUTION : décision au close `d`, ordre au close suivant (la production, elle,
    traite vers 15 h ET sur une barre partielle) — hypothèse volontairement prudente ;
  * la poche CRYPTO et la renormalisation commune du compte (QML-023, non corrigé ici) ;
  * l'univers : listes d'AUJOURD'HUI (biais du survivant, QML-002, non corrigé ici).
"""

from __future__ import annotations

from bisect import bisect_right
from collections import Counter

from packages.backtest.panel import COUVERTURE_DEFAUT, _jour

PAS_DEFAUT = 5            # la production décide à chaque passage ; 1 = fidèle, mais lent
DEBUT_DEFAUT = 252        # la production exige > 200 barres (MM200) + la fenêtre de covariance
CAPITAL_DEFAUT = 100_000.0
BANDE_RELATIVE = 0.005    # run_live._broker_targets : max(0,5 % du capital, 5 $)
BANDE_MIN = 5.0

# Porté par les TROIS sorties historiques (métriques, courbe du tableau de bord, ledger) :
# elles décrivent une règle voisine de celle qui trade, et doivent le dire elles-mêmes.
NE_MESURE_PAS_LA_PRODUCTION = {
    "mesure_la_production": False,
    "mesure_production": "make preset-replay (packages/backtest/preset_rejeu.py)",
}

ECARTS_CONNUS = (
    "sélection par qualité remplacée par la branche momentum (fondamentaux non point-in-time)",
    "exécution au close suivant la décision (production : ~15 h ET, barre partielle)",
    "poche crypto et renormalisation commune du compte non rejouées (QML-023)",
    "univers = listes actuelles, délistés absents (QML-002)",
)


def tronquer(data: dict, jour: str) -> dict:
    """Ce que la production savait le jour `jour` : chaque série coupée APRÈS ce jour.

    Les barres sont supposées triées (c'est ce que rendent les chargeurs). Une série sans
    aucune barre connue disparaît, comme un titre pas encore introduit."""
    out = {}
    for sym, barres in data.items():
        cles = [_jour(b) for b in barres]
        n = bisect_right(cles, jour)
        if n:
            out[sym] = barres[:n]
    return out


def calendrier(data: dict, couverture: float = COUVERTURE_DEFAUT) -> list[str]:
    """Jours cotés par au moins `couverture` des séries — même convention que le panel."""
    compte = Counter(j for barres in data.values() for j in {_jour(b) for b in barres})
    seuil = max(1, int(round(couverture * len(data))))
    return sorted(j for j, n in compte.items() if n >= seuil)


def decisions(data: dict, jours: list[str], params: dict | None = None) -> list:
    """[(jour, poids)] — la fonction de PRODUCTION, appelée telle quelle à chaque date."""
    from packages.backtest.preset_weights import preset_latest_weights_explique

    return [(j, preset_latest_weights_explique(tronquer(data, j), {}, **(params or {}))[0])
            for j in jours]


def avec_coeur(poids: dict, coeur: dict | None) -> dict:
    """Mélange du cœur indiciel, à l'identique de `build_snapshot` (QUANT_CORE_SPEC)."""
    if not coeur:
        return dict(poids)
    part = sum(coeur.values())
    out = {s: w * (1.0 - part) for s, w in poids.items()}
    for s, w in coeur.items():
        out[s] = out.get(s, 0.0) + w
    return out


class _Cours:
    """Dernier cours CONNU à une date — le passé seulement, jamais une interpolation."""

    def __init__(self, prix: dict) -> None:
        self._jours = {s: sorted(p) for s, p in prix.items()}
        self._prix = prix

    def __call__(self, sym: str, jour: str) -> float | None:
        jours = self._jours.get(sym) or []
        i = bisect_right(jours, jour)
        return self._prix[sym][jours[i - 1]] if i else None


class _Compte:
    """Cash + valeur par ligne, marquée au cours du jour. Aucun levier possible."""

    def __init__(self, capital: float) -> None:
        self.cash, self.lignes, self.frais, self.n_ordres = float(capital), {}, 0.0, 0
        self._marque: dict[str, float] = {}

    def marquer(self, cours: _Cours, jour: str) -> None:
        for sym in list(self.lignes):
            px = cours(sym, jour)
            if px and self._marque.get(sym):
                self.lignes[sym] *= px / self._marque[sym]
            if px:
                self._marque[sym] = px

    def equity(self) -> float:
        return self.cash + sum(self.lignes.values())

    def ecrire(self, sym: str, montant: float, px: float, cout: float) -> None:
        """Achat si `montant` > 0, vente sinon ; `cout` en fraction du notionnel."""
        self.lignes[sym] = self.lignes.get(sym, 0.0) + montant
        self._marque[sym] = px
        self.cash -= montant + abs(montant) * cout
        self.frais += abs(montant) * cout
        self.n_ordres += 1
        if self.lignes[sym] <= 1e-9:
            self.lignes.pop(sym)
            self._marque.pop(sym, None)


def _cout(classe: str, frais: bool) -> float:
    from packages.execution.costs import CostModel
    return CostModel.for_asset_class(classe).round_trip_bps / 2e4 if frais else 0.0


def _executer(compte: _Compte, cible: dict, cours: _Cours, jour: str,
              classes: dict, frais: bool) -> None:
    """Un passage de `run_live._reconcile` : ventes d'abord, `decider`, puis portail."""
    from packages.execution.rebalance_plan import decider
    from packages.risk.order_gate import EtatCompte, evaluer

    eq = compte.equity()
    bande = max(BANDE_RELATIVE * eq, BANDE_MIN)
    vals = {s: cible.get(s, 0.0) * eq for s in set(cible) | set(compte.lignes)}
    ordre = sorted(vals, key=lambda s: (vals[s] >= compte.lignes.get(s, 0.0), s))
    for sym in ordre:
        px, detenu = cours(sym, jour), compte.lignes.get(sym, 0.0)
        if not px:
            continue
        intention = decider(vals[sym], detenu, bande)
        if not intention.agit:
            continue
        expo = sum(abs(v) for v in compte.lignes.values())
        etat = EtatCompte(equity=eq, exposition_brute=expo, n_positions=len(compte.lignes),
                          detenu_ligne=detenu, panier=classes.get(sym) == "etf")
        v = evaluer(intention.action, intention.montant, etat,
                    liquidation=intention.liquidation)
        if not v.autorise:
            continue
        if intention.action == "acheter":
            montant = v.montant
        elif intention.liquidation:
            montant = -detenu                   # close_position : sortie en QUANTITÉ, totale
        else:
            montant = -min(v.montant, detenu)
        compte.ecrire(sym, montant, px, _cout(classes.get(sym, "equity"), frais))


def simuler(cibles: list, prix: dict, jours: list[str], *, capital: float = CAPITAL_DEFAUT,
            classes: dict | None = None, frais: bool = True, lag: int = 1) -> dict:
    """Déroule les cibles datées : chaque cible décidée le jour `d` s'exécute `lag` jours
    de cotation PLUS TARD, au cours de clôture de ce jour-là. Equity marquée chaque jour."""
    cours, compte = _Cours(prix), _Compte(capital)
    a_executer: dict[str, dict] = {}
    for d, cible in cibles:
        i = bisect_right(jours, d) - 1 + lag
        if 0 <= i < len(jours) and jours[i] > d:
            a_executer[jours[i]] = cible            # la plus récente décision l'emporte
    if not a_executer:
        return {"available": False, "raison": "aucune exécution dans le calendrier"}
    premier = min(a_executer)
    dates, equity = [], []
    for jour in jours[jours.index(premier):]:
        compte.marquer(cours, jour)
        if jour in a_executer:
            _executer(compte, a_executer[jour], cours, jour, classes or {}, frais)
        dates.append(jour)
        equity.append(compte.equity())
    eq = compte.equity()
    return {"available": True, "dates": dates, "equity": equity,
            "frais": round(compte.frais, 6), "n_ordres": compte.n_ordres,
            "n_executions": len(a_executer),
            "poids_final": {s: v / eq for s, v in compte.lignes.items()} if eq > 0 else {}}


def _prix_par_jour(data: dict) -> dict:
    return {s: {_jour(b): float(b.close) for b in barres if b.close}
            for s, barres in data.items()}


def rejouer(data: dict, *, pas: int = PAS_DEFAUT, debut: str | None = None,
            params: dict | None = None, coeur: dict | None = None,
            classes: dict | None = None, capital: float = CAPITAL_DEFAUT,
            frais: bool = True) -> dict:
    """Rejeu complet : décisions de PRODUCTION tous les `pas` jours, exécution à J+1."""
    from packages.backtest.conviction_backtest import _stats

    cal = calendrier(data)
    i0 = bisect_right(cal, debut) - 1 if debut else DEBUT_DEFAUT
    jours = cal[max(0, i0)::max(1, pas)]
    if len(jours) < 3:
        return {"available": False, "raison": "historique trop court pour rejouer"}
    brutes = decisions(data, jours, params)
    cibles = [(j, avec_coeur(w, coeur)) for j, w in brutes]
    res = simuler(cibles, _prix_par_jour(data), cal, capital=capital,
                  classes=classes, frais=frais)
    if not res["available"]:
        return res
    eq = res["equity"]
    rend = [eq[k + 1] / eq[k] - 1.0 for k in range(len(eq) - 1) if eq[k] > 0]
    return {**res, "stats": _stats(rend, 252.0),
            "n_decisions": len(brutes),
            "n_decisions_vides": sum(1 for _, w in brutes if not w),
            "pas": pas, "coeur": coeur or {},
            "regle": "preset_latest_weights_explique (production), rejouée date par date",
            "mesure_la_production": True, "ecarts_connus": list(ECARTS_CONNUS)}


def _stats_courbe(courbe: list[float]) -> dict:
    from packages.backtest.conviction_backtest import _stats
    rend = [courbe[k + 1] / courbe[k] - 1.0 for k in range(len(courbe) - 1) if courbe[k] > 0]
    return _stats(rend, 252.0)


def references(prix: dict, dates: list[str]) -> dict:
    """Références calculées sur les MÊMES `dates` que le rejeu (base 1,0).

    `QQQ` : acheté-conservé (absent si QQQ n'est pas dans `prix`). `équipondéré` : moyenne
    quotidienne des rendements des titres cotés la veille ET le jour même — rééquilibrage
    quotidien, sans frais : une borne haute de ce qu'un panier naïf aurait fait."""
    out: dict = {}
    if "QQQ" in prix:
        px = prix["QQQ"]
        base = next((px[d] for d in dates if d in px), None)
        if base:
            dernier, courbe = base, []
            for d in dates:
                dernier = px.get(d, dernier)
                courbe.append(dernier / base)
            out["QQQ"] = {"courbe": courbe, "stats": _stats_courbe(courbe)}
    courbe = [1.0]
    for d0, d1 in zip(dates[:-1], dates[1:], strict=True):
        r = [p[d1] / p[d0] - 1.0 for p in prix.values() if p.get(d0) and p.get(d1)]
        courbe.append(courbe[-1] * (1.0 + (sum(r) / len(r) if r else 0.0)))
    out["équipondéré"] = {"courbe": courbe, "stats": _stats_courbe(courbe)}
    return out


def _rendements(courbe: list[float]) -> list[float]:
    return [courbe[k + 1] / courbe[k] - 1.0 for k in range(len(courbe) - 1) if courbe[k] > 0]


def meme_volatilite(courbe_ref: list[float], courbe_cible: list[float]) -> list[float]:
    """`courbe_ref` diluée en cash (ou levée) jusqu'à la volatilité de `courbe_cible`.

    Référence juste pour une stratégie partiellement investie : à volatilité égale, seul
    le Sharpe distingue deux portefeuilles. Exposition CONSTANTE fixée ex post sur tout
    l'échantillon — c'est un étalon de comparaison, pas une stratégie tradable."""
    import numpy as np
    rr, rc = np.asarray(_rendements(courbe_ref)), np.asarray(_rendements(courbe_cible))
    k = float(rc.std() / rr.std()) if rr.std() > 0 else 0.0
    return [1.0] + list(np.cumprod(1.0 + k * rr))


def comparer_sharpe(courbe_ref: list[float], courbe_cible: list[float]) -> dict:
    """ΔSharpe cible − référence, APPARIÉ par date (Jobson-Korkie/Memmel)."""
    from packages.research.sharpe_diff import comparer
    return comparer(_rendements(courbe_ref), _rendements(courbe_cible), periodes_par_an=252.0)
