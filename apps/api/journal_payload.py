"""Le panneau « Historique des positions » : quoi montrer, et quoi dire du reste.

PÉRIMÈTRE, ET IL A CHANGÉ LE 17/09. La route lisait `all(legacy=False)`. Mais `legacy`
répond à une AUTRE question — « ce trade porte-t-il les features de décision ? », celle
de la calibration ML. Un ordre que le robot a réellement passé, journalisé après coup
depuis le fill du courtier (`completer_ouvertures`), vaut `legacy=1` : le filtre
l'écartait. Résultat mesuré après `make reparer-journal` : le panneau affichait
**+139,75 $ sur 62 trades** quand le robot avait fait **−23,15 $ sur 112**. Le chiffre
n'était pas faux, il décrivait un sous-ensemble — et ce sous-ensemble était favorable
parce que les pertes non appariées en étaient absentes. Le périmètre se lit désormais
sur l'ORIGINE de l'enregistrement (`packages.execution.perimetre_journal`).

CE QUE LA TABLE CONTIENT : les aller-retours du robot réellement OUVERTS PUIS
CLÔTURÉS. Un lot encore ouvert n'est pas un trade, c'est une position.

CE QU'ON NE FAIT SURTOUT PAS : les effacer. Ne montrer que les fermés SANS DIRE ce
qu'on laisse dehors, c'est fabriquer le palmarès de trades soldés que cette page
dénonce dans son propre chapeau — le rééquilibrage ferme ce qui a monté et conserve ce
qui a baissé. Les lots ouverts sortent donc par `ouverts`, avec leur latent chiffré, et
l'import historique reste ventilé dans `stats.origines`.

Ce module est SANS FastAPI, pour être éprouvable sans lui — la route n'en est que
l'emballage HTTP.
"""

from __future__ import annotations

MIN_FERMES = 20      # même seuil que `biais_fermeture` : sous 20, on ne publie rien


def _ligne(t) -> dict:
    return {
        "id": t.id, "symbol": t.instrument, "venue": t.venue, "qty": t.qty,
        "entry_ts": t.entry_ts.isoformat(), "entry_price": t.entry_price,
        "exit_ts": t.exit_ts.isoformat() if t.exit_ts else None,
        "exit_price": t.exit_price, "pnl_net": t.pnl_net, "pnl_pct": t.pnl_pct,
        "mfe": t.mfe, "mae": t.mae, "is_win": t.is_win,
        "duration_d": round(t.duration_s / 86400, 1) if t.duration_s else None,
        "regime": t.regime,
        "decision_price": (t.features_snapshot or {}).get("decision_price"),
    }


def _plat(t) -> dict:
    """La forme minimale que demandent les ventilations : identité, sortie, P&L."""
    return {"id": t.id, "exit_ts": t.exit_ts.isoformat() if t.exit_ts else None,
            "pnl_net": t.pnl_net, "is_win": t.is_win}


def _agregats(closed: list[dict]) -> dict:
    """Win rate et espérance, ou le motif de leur absence.

    Jamais un chiffre tiré d'un échantillon trop petit pour le porter.
    """
    if len(closed) < MIN_FERMES:
        return {"status": (f"UNCALIBRATED (expectancy à N≥{MIN_FERMES} fermés ; "
                           f"actuel {len(closed)})")}
    gagnants = [r for r in closed if r["is_win"]]
    realise = sum(r["pnl_net"] or 0 for r in closed)
    return {"win_rate": round(len(gagnants) / len(closed), 3),
            "expectancy": round(realise / len(closed), 2)}


def _stats(tous: list, rows: list[dict], closed: list[dict], ouverts: list[dict],
           prix: dict, positions: dict) -> dict:
    from packages.execution.perimetre_journal import ventiler
    from packages.research import biais_fermeture as _bf

    stats: dict = {"n_open": len(ouverts), "n_closed": len(closed)}
    stats.update(_agregats(closed))
    # LE WIN RATE DES FERMÉS EST UN ÉCHANTILLON CHOISI : le rééquilibrage ferme ce qui
    # a monté et conserve ce qui a baissé. On publie donc le latent des lots ouverts À
    # CÔTÉ, jamais à la place — les trades fermés ont bien été gagnants.
    stats["honnete"] = _bf.statistiques_honnetes(
        closed, _bf.marquer_lots(ouverts, prix or {}))
    # RÉCONCILIATION D'ABORD : mesuré le 03/09, le journal portait ~80 actions que le
    # compte ne détient pas. Un win rate tiré d'un registre qui ne décrit pas le compte
    # n'est pas un chiffre prudent, c'est un chiffre faux. On le MARQUE plutôt que de
    # le retirer : le retirer ferait disparaître le problème de la vue.
    stats["reconciliation"] = _bf.reconcilier(ouverts, positions or {})
    # PÉRIMÈTRE. Le panneau décrit les trades du ROBOT, pas la performance du compte :
    # celui-ci subit aussi l'import historique. On publie les deux, chiffrés, plutôt
    # que de laisser lire le premier comme le second.
    plats = [_plat(t) for t in tous]
    stats["perimetre"] = _bf.perimetre_affiche(plats, rows)
    # VENTILATION PAR ORIGINE : la seule façon qu'un lecteur ait de juger ce qu'il ne
    # voit pas — y compris un préfixe d'identifiant que personne n'a encore prévu.
    stats["origines"] = ventiler(plats)
    if not stats["reconciliation"]["reconcilie"]:
        stats["fiable"] = False
        stats["motif_non_fiable"] = stats["reconciliation"]["motif"]
    return stats


def construire(journal, prix: dict[str, float], positions: dict[str, float]) -> dict:
    """Payload de `/api/journal`. `prix` et `positions` viennent du courtier RÉEL.

    Les deux peuvent être vides — snapshot indisponible, clés absentes en CI publique.
    Le latent est alors non calculable, et `marquer_lots` le DIT (`lots_sans_prix`)
    plutôt que de compter ces lots à zéro : un lot dont on ignore le cours ne vaut pas
    son prix d'entrée, et le supposer fabriquerait un gagnant neutre.
    """
    from packages.execution.perimetre_journal import pris_par_le_robot
    from packages.research.exec_costs import measured_slippage

    tous = journal.all()
    rows = [_ligne(t) for t in tous if pris_par_le_robot(t.id)]
    closed = [r for r in rows if r["exit_ts"]]
    ouverts = [r for r in rows if not r["exit_ts"]]
    return {"available": True, "rows": closed, "ouverts": ouverts,
            "stats": _stats(tous, rows, closed, ouverts, prix, positions),
            "slippage": measured_slippage(journal)}


def realise_compte(journal) -> dict:
    """Le gain/perte RÉALISÉ, à côté du latent — et les deux périmètres nommés.

    CE QUI REMPLACE LE RAPPROCHEMENT (18/09). La page portait une identité comptable
    complète (capital initial, résidu, fenêtres). Elle était juste et personne n'en
    voulait : la question posée devant un compte est « combien j'ai gagné », pas
    « l'identité boucle-t-elle ». Le diagnostic reste entier au terminal
    (`make diag-journal`), là où on le lit quand on le cherche.

    Ce qui reste ici est le strict complément du latent déjà affiché : ce qui est
    ENCAISSÉ. Les deux périmètres sont rendus parce qu'ils diffèrent d'un ordre de
    grandeur — le robot a fait +74 $ quand le compte en a subi −1 888 $ — et qu'afficher
    le plus flatteur des deux sans le dire serait le mensonge le plus facile du site.
    """
    from packages.execution.frais_store import dernier
    from packages.execution.perimetre_journal import pris_par_le_robot
    fermes = [t for t in journal.all() if t.exit_ts]
    total = sum(float(t.pnl_net or 0.0) for t in fermes)
    robot = sum(float(t.pnl_net or 0.0) for t in fermes if pris_par_le_robot(t.id))
    # LE RÉALISÉ EST BRUT, ET LES FRAIS SONT À CÔTÉ. Ils ne sont pas attribuables au
    # trade : le courtier les publie en agrégats journaliers (« TAF fee for proceed of
    # 389,9 shares (25 trades) »). Les répartir par aller-retour serait une invention ;
    # les taire ferait perdre 810,30 $ à l'identité du compte, mesurés le 18/09.
    f = dernier()
    return {"total": round(total, 2), "robot": round(robot, 2),
            "hors_robot": round(total - robot, 2),
            "n_total": len(fermes),
            "n_robot": sum(1 for t in fermes if pris_par_le_robot(t.id)),
            "frais": (round(abs(float(f.get("total_usd") or 0.0)), 2)
                      if f.get("disponible") else None),
            "frais_motif": None if f.get("disponible") else f.get("motif"),
            "net": (round(total - abs(float(f.get("total_usd") or 0.0)), 2)
                    if f.get("disponible") else None)}
