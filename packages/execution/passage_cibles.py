"""Cibles d'UN compte : clé normalisée, carte cible, ordre de passage, identifiants.

Extrait tel quel de `scripts/run_live.py` (audit du 06/10 : `run_live` faisait
1 343 lignes pour une règle de 400). Fonctions pures, sans I/O ; le comportement du
chemin d'ordres est figé par `tests/execution/test_reconcile_golden.py`.
"""

from __future__ import annotations


def nsym(s: str) -> str:
    """Clé de matching : Alpaca renvoie les POSITIONS sans slash (BTCUSD) mais les
    CIBLES sont en BTC/USD → sans normalisation, le même actif compte 2 fois (fix
    07/07 : la réconciliation RACHETAIT BTC chaque jour tout en échouant à vendre
    « l'autre »)."""
    return (s or "").replace("/", "").replace("-", "").upper()


def broker_targets(targets, bname: str, cap: float, reduce: float, cur: dict, *,
                   proteger=None, liquider_hors_cible: bool = True
                   ) -> tuple[dict, float]:
    """Carte cible {clé normalisée: {o, val, sym}} d'UN broker + bande d'inaction.

    ANTI-LEVIER : Σ cibles plafonnée à 100 % du capital du broker. Le détenu hors-cible
    est ajouté avec val=0 (liquidation) sauf si `proteger` (HOLD = val=détenu) —
    Capital A : le preset ne doit pas solder les holdings sleeve. Si
    `liquider_hors_cible=False` (pass sleeve) : aucun hors-cible ajouté.
    `sym` = symbole à ENVOYER au broker (format cible « BTC/USD » si connue, sinon
    le format position).
    Protection multi-jour : `proteger` alimenté par snap ∪ journal (PR4).
    """
    tgs = [o for o in targets
           if (o.get("capital") == "bitmart") == (bname == "Bitmart")]
    sw = sum(o["weight_pct"] for o in tgs)
    scale = min(1.0, 1.0 / sw) if sw > 1.0 else 1.0
    detenu: dict[str, float] = {}
    for k, v in cur.items():
        detenu[nsym(k)] = detenu.get(nsym(k), 0.0) + v
    tgt: dict[str, dict] = {}
    for o in tgs:
        bsym = o.get("broker_symbol", o["symbol"])
        pleine = o["weight_pct"] * cap * scale
        val = cible_sous_garde(pleine, detenu.get(nsym(bsym), 0.0), reduce)
        tgt[nsym(bsym)] = {"o": o, "val": val, "sym": bsym}
    if liquider_hors_cible:
        prot = {nsym(s) for s in (proteger or ())}
        for bsym in cur:                                  # détenu hors-cible
            nkey = nsym(bsym)
            if nkey in tgt:
                continue
            if nkey in prot:                      # HOLD sleeve — ne pas liquider
                tgt[nkey] = {"o": None, "val": detenu.get(nkey, 0.0), "sym": bsym}
            else:
                tgt[nkey] = {"o": None, "val": 0.0, "sym": bsym}
    return tgt, max(0.005 * cap, 5.0)        # bande : 0,5 % du capital, min 5 $


def id_client(run_id: str, bsym: str, action: str) -> str:
    """Identifiant client d'UN ordre de CE passage — le même à chaque retry (QML-006).

    Le passage entre dans l'identifiant : un second rebalancement le même jour
    (`--forcer`) est un autre ordre, pas un doublon à refuser. 48 caractères au plus
    (Alpaca en accepte 128, Bitmart et Binance moins)."""
    import hashlib
    brut = f"{run_id}|{nsym(bsym)}|{action}"
    return f"qt-{hashlib.sha1(brut.encode()).hexdigest()[:24]}-{nsym(bsym)[:16]}"[:48]


def cible_sous_garde(pleine: float, detenu: float, reduce: float) -> float:
    """Cible d'UNE ligne sous garde-fou : achats plafonnés, jamais une vente (QML-007).

    `reduce` ∈ [0, 1] vient des kill-switches (TV, drawdown réel, disjoncteur). Il ne
    fait que BORNER les achats à `pleine × reduce`. Il ne descend jamais la cible sous
    le détenu : un garde-fou qui vend serait un moteur de liquidation, et l'ancien code
    en était un seulement pour les alertes les MOINS graves (`0 < reduce < 1`), tandis
    que la rupture de drawdown gelait tout. Les allègements décidés par la STRATÉGIE
    (`pleine < detenu`) passent inchangés : ils réduisent le risque.
    """
    r = max(0.0, min(1.0, float(reduce)))
    if r >= 1.0:
        return pleine
    return max(pleine * r, min(pleine, detenu))


def ordre_de_traitement(tgt: dict, detenu: dict) -> list:
    """Les VENTES d'abord. L'ordre de passage décide de ce que le portail accepte.

    Le tri d'origine allait par cible décroissante. Or une ligne à SOLDER a une cible de
    zéro : elle partait donc en dernier. Le portail de risque évaluait les achats en
    voyant encore, dans l'exposition brute, tout ce que le même lot allait vendre.
    Il refusait ainsi des achats financés par ces ventes.

    MESURÉ le 14/09 sur le compte paper. Brut 80 785 $ pour un plafond de 100 194 $ ;
    19 408 $ d'achats acceptés saturent le plafond ; SEPT achats sont alors refusés pour
    9 961 $ — puis sept lignes sont soldées, libérant 13 720 $. Soit 3 759 $ de plus que
    le total des refus. Dans l'autre sens, les sept passaient.

    Pourquoi c'est sûr : une vente n'est JAMAIS bloquée par le portail
    (« désengagement — jamais bloqué »). Les passer d'abord ne peut donc rien
    refuser de plus qu'avant. Cet
    ordre est strictement plus permissif, à décisions de stratégie inchangées — il ne
    choisit rien, il cesse seulement de compter deux fois le capital.
    """
    def cle(kv):
        nkey, info = kv
        delta = info["val"] - detenu.get(nkey, 0.0)
        # 0 = vente (libère l'exposition) · 1 = achat (la consomme). Puis, dans
        # chaque groupe du plus gros au plus petit : l'ordre entre achats est
        # celui d'avant.
        return (1 if delta >= 0 else 0,
                -abs(delta) if delta < 0 else -info["val"])

    return sorted(tgt.items(), key=cle)


def sleeve_geometry_missing(o: dict | None) -> list[str]:
    """Clés manquantes TA#8 pour un ordre sleeve swing. [] = OK ou guard inactive.

    Guard active ssi `strategy=="swing"` ou `sleeve=="swing"`. Preset / strategy
    absente → [] (aucune géométrie exigée). Phase 1 : pas de gate `accept` (PR5).
    """
    if not o:
        return []
    if o.get("strategy") != "swing" and o.get("sleeve") != "swing":
        return []
    miss: list[str] = []

    def _fin(v) -> bool:
        return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v

    def _str(v) -> bool:
        return isinstance(v, str) and bool(v.strip())

    if not _fin(o.get("entry")):
        miss.append("entry")
    if not _fin(o.get("stop")):
        miss.append("stop")
    if not (_fin(o.get("target")) or _fin(o.get("rr"))):
        miss.append("target|rr")
    if not _str(o.get("setup_id")):
        miss.append("setup_id")
    if not _str(o.get("ts_decision")):
        miss.append("ts_decision")
    return miss
