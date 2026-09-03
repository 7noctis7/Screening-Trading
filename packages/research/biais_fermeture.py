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


# ─────────────────── Réconciliation journal ↔ courtier (03/09) ───────────────────
# Mesuré ce jour-là : le journal portait ~80 actions que le compte ne détient PAS,
# deux fois trop de QQQ, et ses cryptos sous une convention de nommage différente de
# celle du courtier. Une statistique tirée d'un tel registre ne décrit pas le compte.

QUOTES = ("USDC", "USDT", "USD")
TOLERANCE_QTE = 0.01            # 1 % d'écart de quantité toléré (arrondis de fills)


def symbole_canonique(sym: str) -> str:
    """« AVAX/USDC », « AVAX-USD » et « AVAXUSD » désignent le MÊME actif.

    Le dépôt connaît déjà ce piège : `execution/routing` le documente avec un incident
    de production du 27/08 (une liquidation crypto bloquée par le calendrier NYSE parce
    que `AAVEUSD` n'était pas reconnu comme crypto). Comparer sans canoniser produirait
    des écarts entièrement fictifs, et ferait passer un vrai problème pour du bruit.
    """
    su = (sym or "").upper().replace("-", "/")
    if "/" in su:
        return su.split("/")[0]
    for q in QUOTES:
        if su.endswith(q) and len(su) > len(q):
            return su[: -len(q)]
    return su


def reconcilier(lots_ouverts: list[dict], positions: dict[str, float]) -> dict:
    """Les lots OUVERTS correspondent-ils aux quantités RÉELLEMENT détenues ?

    C'est la condition de validité de tout ce que le panneau publie. Le P&L réalisé
    s'obtient en appariant des ventes à des lots ouverts : si ces lots ne correspondent
    à rien, les appariements produisent des gains sans contrepartie, et le taux de
    réussite porte sur des trades qui n'ont pas eu lieu tels quels.
    """
    j: dict[str, float] = {}
    for lot in lots_ouverts or []:
        c = symbole_canonique(lot.get("symbol", ""))
        if c:
            j[c] = j.get(c, 0.0) + float(lot.get("qty") or 0.0)
    c_pos: dict[str, float] = {}
    for sym, q in (positions or {}).items():
        c = symbole_canonique(sym)
        if c:
            c_pos[c] = c_pos.get(c, 0.0) + float(q or 0.0)
    ecarts = []
    for sym in sorted(set(j) | set(c_pos)):
        qj, qc = j.get(sym, 0.0), c_pos.get(sym, 0.0)
        if abs(qj - qc) > TOLERANCE_QTE * max(1.0, abs(qc)):
            ecarts.append({"symbole": sym, "journal": round(qj, 6),
                           "courtier": round(qc, 6), "ecart": round(qj - qc, 6)})
    fantomes = [e for e in ecarts if e["courtier"] == 0.0]
    return {"reconcilie": not ecarts, "n_ecarts": len(ecarts),
            "n_fantomes": len(fantomes), "ecarts": ecarts[:50],
            "motif": "" if not ecarts else
                     (f"{len(ecarts)} symbole(s) en désaccord, dont {len(fantomes)} "
                      "que le courtier ne détient PAS. Le journal ne décrit pas ce "
                      "compte : win rate et espérance n'en sont pas des mesures.")}


def perimetre_affiche(tous: list[dict], affiches: list[dict]) -> dict:
    """Le panneau montre-t-il le COMPTE, ou un sous-ensemble favorable de celui-ci ?

    Mesuré le 03/09, après réparation des entrées et des sorties : le périmètre
    `legacy=0` affichait +6 260,82 $ de réalisé et 70 % de réussite, quand le TOTAL
    subi par le compte valait +569,31 $ et 56 %. Le filtre masquait 266 lots et
    −5 691,51 $. Aucun des deux chiffres n'est faux ; c'est leur présentation qui l'est,
    puisque seul le premier est publié et qu'il est lu comme la performance du compte.

    On ne fait PAS entrer les lots `legacy` dans la statistique affichée : ce sont des
    fills importés sans features de décision, et les y verser rendrait le chiffre
    inutilisable pour la calibration ML qu'il sert. On publie l'écart À CÔTÉ, chiffré —
    de sorte que le sous-ensemble reste lisible comme un sous-ensemble.
    """
    def _bilan(rows: list[dict]) -> dict:
        fermes = [r for r in rows if r.get("exit_ts")]
        realise = sum(float(r.get("pnl_net") or 0.0) for r in fermes)
        d = {"n": len(rows), "n_fermes": len(fermes), "pnl_realise": round(realise, 2)}
        if fermes:
            d["win_rate"] = round(
                sum(1 for r in fermes if r.get("is_win")) / len(fermes), 3)
        return d
    total, vu = _bilan(tous), _bilan(affiches)
    masques = total["n"] - vu["n"]
    ecart = round(total["pnl_realise"] - vu["pnl_realise"], 2)
    # L'espace fine ne remplace que le séparateur de MILLIERS : appliquer `replace`
    # à la phrase entière effacerait aussi ses virgules de ponctuation.
    montant = f"{ecart:+,.2f}".replace(",", " ")
    return {
        "affiche": vu, "compte": total,
        "lots_masques": masques, "realise_masque": ecart,
        "avertissement": (
            f"Le panneau affiche un SOUS-ENSEMBLE du compte : {masques} lot(s) et "
            f"{montant} $ de réalisé sont hors périmètre (fills importés, sans "
            "features de décision). Le chiffre affiché décrit les trades pilotés par "
            "le système, pas la performance du compte."
        ) if masques > 0 else None,
    }
