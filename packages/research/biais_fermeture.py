"""Le win rate des trades FERMÉS est un échantillon CHOISI, pas un échantillon.

LE MÉCANISME, ET IL EST STRUCTUREL. Un système qui rééquilibre ALLÈGE ce qui a monté
et CONSERVE ce qui a baissé. Les positions gagnantes se referment donc — et entrent
dans la statistique ; les perdantes restent ouvertes — et n'y entrent pas. Le taux de
réussite des trades fermés mesure alors la règle de sortie autant que la qualité des
décisions, et plus la part de lots ouverts est grande, plus le chiffre est flatteur.

CE MODULE EST PRÉVENTIF, PAS LE DIAGNOSTIC D'UN BIAIS CONSTATÉ. Vérifié sur le compte
réel le 03/09 : 39 fermés à 87 % de réussite, 26 lots ouverts — et un latent de
**+614,53 $**, donc POSITIF. Le biais ne s'est PAS matérialisé ici. Une première
lecture l'avait déduit d'un rapprochement entre l'espérance affichée et le rendement
du compte ; la déduction était fausse et le chiffre mesuré l'a corrigée. C'est
précisément pour ça que le module publie une mesure au lieu de laisser faire
l'inférence.

CE QU'IL RESTE À EXPLIQUER, ET QUI N'EST PAS CE MODULE. 39 fermés × 149,27 $ = 5 821 $
de gains réalisés, plus 614 $ de latent, sur un compte d'environ 100 000 $ — soit ~6,4
% — tandis que le tableau de bord affiche le portefeuille RÉEL à +0,2 % sur deux mois.
Ces deux chiffres ne se réconcilient pas. Première piste à VÉRIFIER (pas à supposer) :
`/api/journal` lit `all(legacy=False)`, ce qui EXCLUT les fills importés sans features
; le compte, lui, les subit. Second point à contrôler : les aller-retours tombent-ils
tous dans la fenêtre de deux mois de `equity_history` ?

CE QUI N'EST PAS AFFECTÉ, VÉRIFIÉ DANS LE CODE. Le verdict GO/NO-GO
(`packages/research/rdv_paper.compare`) lit la COURBE D'EQUITY du compte, laquelle
intègre le latent par construction. Il ne lit ni le win rate ni l'espérance des
fermés. Le verdict n'est donc pas contaminé — c'est le texte du panneau qui laisse
croire le contraire.
"""

from __future__ import annotations

PART_OUVERTE_ALERTE = 0.20      # au-delà, les fermés ne représentent plus l'ensemble
MIN_FERMES = 20                 # même seuil que le panneau : sous 20, on ne publie rien


def marquer_lots(lots: list[dict], prix: dict[str, float]) -> dict:
    """Lots ouverts valorisés au dernier prix connu. Sans prix → EXCLU, jamais estimé.

    Un lot dont on ignore le prix ne vaut pas son prix d'entrée : le compter à zéro
    de latent fabriquerait un gagnant neutre là où il n'y a qu'une absence de donnée.
    On le met de côté et on dit combien il y en a.
    """
    marques, sans_prix = [], []
    for lot in lots or []:
        sym, qte = lot.get("symbol"), lot.get("qty")
        entree, px = lot.get("entry_price"), prix.get(sym)
        if not sym or not qte or not entree or not px or px <= 0:
            sans_prix.append(sym)
            continue
        latent = (float(px) - float(entree)) * float(qte)
        marques.append({"symbol": sym, "qty": float(qte), "entry_price": float(entree),
                        "prix": float(px), "pnl_latent": round(latent, 2),
                        "is_win": latent > 0})
    return {"marques": marques, "sans_prix": sans_prix,
            "pnl_latent": round(sum(m["pnl_latent"] for m in marques), 2)}


def _pnl(rows: list[dict]) -> float:
    return sum(float(r.get("pnl_net") or 0.0) for r in rows)


def statistiques_honnetes(fermes: list[dict], marques: dict) -> dict:
    """Les deux lectures côte à côte : les fermés seuls, puis TOUTES les positions.

    On garde la première parce qu'elle est vraie — ces trades ont bien été gagnants. On
    ajoute la seconde parce que c'est elle qui répond à « le système gagne-t-il ? ».
    """
    ouverts = marques.get("marques", [])
    n_f, n_o = len(fermes), len(ouverts)
    total = n_f + n_o
    realise, latent = _pnl(fermes), float(marques.get("pnl_latent", 0.0))
    out: dict = {
        "n_fermes": n_f, "n_ouverts": n_o,
        "part_ouverte": round(n_o / total, 3) if total else 0.0,
        "pnl_realise": round(realise, 2), "pnl_latent": round(latent, 2),
        "pnl_total": round(realise + latent, 2),
        "lots_sans_prix": len(marques.get("sans_prix", [])),
    }
    if n_f >= MIN_FERMES:
        gagnants = [r for r in fermes if r.get("is_win")]
        out["win_rate_ferme"] = round(len(gagnants) / n_f, 3)
        out["expectancy_ferme"] = round(realise / n_f, 2)
    else:
        out["statut_ferme"] = f"UNCALIBRATED (N≥{MIN_FERMES} fermés ; actuel {n_f})"
    if total >= MIN_FERMES:
        gagnants_tous = len([r for r in fermes if r.get("is_win")]) + \
            len([m for m in ouverts if m["is_win"]])
        out["win_rate_toutes_positions"] = round(gagnants_tous / total, 3)
        out["expectancy_toutes_positions"] = round((realise + latent) / total, 2)
    out["avertissement"] = _avertissement(out)
    return out


def _avertissement(s: dict) -> str:
    """Le texte n'est émis QUE si les deux conditions du biais sont réunies.

    Un avertissement affiché en permanence cesse d'être lu. Celui-ci n'apparaît que
    lorsqu'une part notable des positions est ouverte ET que leur latent est négatif :
    c'est précisément la configuration où le win rate des fermés est trompeur.
    """
    if s["part_ouverte"] < PART_OUVERTE_ALERTE or s["pnl_latent"] >= 0:
        return ""
    ecart = s.get("expectancy_ferme")
    toutes = s.get("expectancy_toutes_positions")
    detail = (f" — espérance {ecart:+.2f} $ sur les fermés contre {toutes:+.2f} $ "
              "sur toutes les positions" if ecart is not None and toutes is not None
              else "")
    return (f"{s['n_ouverts']} lots ouverts ({s['part_ouverte']:.0%}) portent "
            f"{s['pnl_latent']:+.2f} $ de latent. Le rééquilibrage ferme ce qui a "
            f"monté et conserve ce qui a baissé : le taux de réussite des trades "
            f"FERMÉS est donc biaisé vers le haut{detail}. Lire « toutes positions ».")
