#!/usr/bin/env python3
"""Le journal et le compte disent-ils la même chose ? On MESURE, on ne déduit pas.

D'OÙ VIENT CE SCRIPT. Le 03/09 j'ai AFFIRMÉ que les lots ouverts portaient « environ
-5 600 $ de latent », en rapprochant l'espérance affichée (39 × 149,27 $) du rendement
du compte (+0,2 %). Les positions réelles disaient **+614,53 $**, donc positif. La
déduction était fausse. Ce script existe pour que la question suivante ne subisse pas
le même sort.

LA QUESTION, ET SA RÉPONSE ARITHMÉTIQUE. L'identité comptable d'une période s'écrit

    Δequity = réalisé + latent(fin) − latent(DÉBUT) + flux − frais

Ce script compare `réalisé + latent(fin)` à `Δequity`. Il OMET donc `latent(début)` — le
gain ou la perte non réalisé que portaient déjà les positions au premier point de la
courbe. L'écart affiché vaut essentiellement ce terme-là. Ce n'est pas une anomalie à
effacer : c'est la part du P&L qui précède la fenêtre de mesure.

Quatre causes possibles, séparées par la MESURE plutôt que par l'opinion :

1. LES ORDRES NON EXÉCUTÉS. Écartés en amont — `AlpacaBroker.orders` saute tout ordre
     dont `filled_qty` vaut zéro. Piste fermée par le code, pas par une opinion.
2. LE FILTRE `legacy`. `/api/journal` lit `all(legacy=False)` : les fills importés sont
     hors du panneau mais subis par le compte.
3. LA FENÊTRE. Les aller-retours tombent-ils dans la période couverte par
     `equity_history` ? Sinon on compare un cumul long à un rendement court.
4. LE PRIX DE REVIENT IMPORTÉ. Une position déjà détenue, journalisée au coût moyen
     du courtier, porte une date d'entrée récente et un prix ancien. Son P&L à la vente
     contient alors du gain ANTÉRIEUR à la courbe. C'est `latent(début)`, et le bloc
     « PRIX D'ENTRÉE vs COURS DU JOUR » le mesure.

CE QU'IL NE FAIT PAS : conclure à votre place quand les chiffres ne tranchent pas. Un
résidu inexpliqué est imprimé comme tel.

python scripts/diag_journal_compte.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _jour(ts) -> str:
    return ts.date().isoformat() if hasattr(ts, "date") else str(ts)[:10]


def _bilan(trades: list) -> dict:
    """Réalisé, compte de fermés/ouverts et bornes de dates d'un lot de trades."""
    fermes = [t for t in trades if t.exit_ts]
    ouverts = [t for t in trades if not t.exit_ts]
    dates = sorted(_jour(t.exit_ts) for t in fermes)
    return {"n": len(trades), "n_fermes": len(fermes), "n_ouverts": len(ouverts),
            "realise": round(sum(float(t.pnl_net or 0.0) for t in fermes), 2),
            "gagnants": sum(1 for t in fermes if t.is_win),
            "premier": dates[0] if dates else None,
            "dernier": dates[-1] if dates else None}


def _ligne(nom: str, b: dict) -> None:
    wr = f"{b['gagnants']/b['n_fermes']:.0%}" if b["n_fermes"] else "  —"
    esp = f"{b['realise']/b['n_fermes']:+8.2f}" if b["n_fermes"] else "       —"
    print(f"  {nom:<22} {b['n']:>5} {b['n_fermes']:>7} {b['n_ouverts']:>8} "
          f"{wr:>6} {b['realise']:>11.2f} {esp} "
          f"  {b['premier'] or '—'} → {b['dernier'] or '—'}")


def _journal() -> None:
    from packages.storage import SqliteTradeJournal
    j = SqliteTradeJournal()
    tous = j.all()
    non_legacy = j.all(legacy=False)
    ids = {t.id for t in non_legacy}
    legacy = [t for t in tous if t.id not in ids]
    print("  JOURNAL — ce que le panneau montre, et ce qu'il n'affiche pas\n")
    print(f"  {'périmètre':<22} {'lots':>5} {'fermés':>7} {'ouverts':>8} "
          f"{'win':>6} {'réalisé $':>11} {'esp./tr':>8}   fenêtre des sorties")
    print("  " + "-" * 100)
    b_nl, b_l, b_t = _bilan(non_legacy), _bilan(legacy), _bilan(tous)
    _ligne("legacy=0 (AFFICHÉ)", b_nl)
    _ligne("legacy=1 (MASQUÉ)", b_l)
    _ligne("TOTAL (subi par le compte)", b_t)
    if b_l["n"] == 0:
        print("\n  → Aucun fill legacy. Le filtre n'explique RIEN de l'écart : chercher"
              " ailleurs.")
    else:
        ecart = b_t["realise"] - b_nl["realise"]
        print(f"\n  → Le filtre `legacy` masque {b_l['n']} lots et {ecart:+.2f} $ de "
              "réalisé.")
        if ecart < 0:
            print("    Le journal montre donc un sous-ensemble FAVORABLE — non voulu, "
                  "mais réel.")


BROKERS = ("alpaca", "crypto", "binance", "bitmart")


def _courbes() -> dict[str, list]:
    """Les courbes lues UNE SEULE FOIS.

    Elles étaient relues après `build_snapshot()`, qui ENREGISTRE le point du jour :
    les deux lectures ne portaient donc pas sur la même série et le total ne
    correspondait plus à la somme des lignes (3,39 $ d'écart le 03/09). Une mesure qui
    ne se recoupe pas avec elle-même ne vaut rien, si petit que soit l'écart.
    """
    from packages.execution.equity_history import series
    return {b: series(b) for b in BROKERS}


def _compte(courbes: dict, bilan_total: dict) -> None:
    print("\n  COMPTE — courbe d'equity réelle enregistrée\n")
    trouve = False
    for broker, pts in courbes.items():
        if len(pts) < 2:
            continue
        trouve = True
        v0, v1 = float(pts[0]["v"]), float(pts[-1]["v"])
        print(f"  {broker:<10} {len(pts):>4} points · {pts[0]['t']} → {pts[-1]['t']} · "
              f"{v0:,.2f} $ → {v1:,.2f} $ · variation BRUTE {v1 - v0:+,.2f} $")
        _fenetre(pts, bilan_total)
        _mouvements(pts)
    if not trouve:
        print("  Aucune courbe enregistrée (equity_history vide) — la comparaison")
        print("  est impossible, et c'est la réponse : rien à réconcilier encore.")


def _fenetre(pts: list, b: dict) -> None:
    """Les sorties du journal tombent-elles DANS la fenêtre de la courbe ?"""
    if not b["premier"]:
        return
    debut, fin = pts[0]["t"], pts[-1]["t"]
    dedans = debut <= b["premier"] and b["dernier"] <= fin
    etat = "DANS la fenêtre" if dedans else "⚠ DÉBORDE la fenêtre de la courbe"
    print(f"    sorties du journal : {b['premier']} → {b['dernier']} · {etat}")
    if not dedans:
        print("    → on compare un cumul de trades à un rendement calculé sur")
        print("      une AUTRE période. À corriger avant toute autre lecture.")


def _mouvements(pts: list, k: float = 6.0) -> None:
    """Sauts journaliers hors norme = versements ou retraits, pas des gains.

    On ne compare pas à un seuil en dollars, qui dépendrait de la taille du compte, mais
    à la dispersion OBSERVÉE de la série : `k` fois l'écart absolu médian. Un compte
    calme rend le filtre plus sensible, un compte agité moins — ce qui est le
    comportement voulu.
    """
    ecarts = [float(pts[i]["v"]) - float(pts[i - 1]["v"]) for i in range(1, len(pts))]
    if len(ecarts) < 5:
        return
    medabs = sorted(abs(x) for x in ecarts)[len(ecarts) // 2]
    seuil = max(k * medabs, 1.0)
    gros = [(pts[i + 1]["t"], e) for i, e in enumerate(ecarts) if abs(e) > seuil]
    if not gros:
        print(f"    aucun mouvement suspect (seuil {seuil:,.2f} $/jour) — "
              "la variation est du P&L")
        return
    total = sum(e for _, e in gros)
    print(f"    {len(gros)} saut(s) hors norme (> {seuil:,.2f} $/jour), total "
          f"{total:+,.2f} $ — candidats VERSEMENT/RETRAIT :")
    for t, e in gros[:6]:
        print(f"      {t}  {e:+,.2f} $")


def _lots_vs_courtier(ouverts: list, positions: dict) -> None:
    """Les lots OUVERTS du journal correspondent-ils aux positions RÉELLES ?

    C'est la mesure qui tranche si le réalisé est surévalué. Le P&L réalisé s'obtient
    en appariant les ventes à des lots ouverts : si le journal porte des lots que le
    courtier ne détient pas, ces appariements produisent des gains qui n'ont jamais
    existé. On compare donc les QUANTITÉS, symbole par symbole, sans rien supposer.
    """
    from packages.research.biais_fermeture import symbole_canonique
    par_sym: dict[str, float] = {}
    for lot in ouverts:
        c = symbole_canonique(lot.instrument)
        par_sym[c] = par_sym.get(c, 0.0) + float(lot.qty or 0)
    positions = {symbole_canonique(k): v for k, v in (positions or {}).items()}
    print("\n  LOTS OUVERTS DU JOURNAL vs POSITIONS RÉELLES\n")
    if not positions:
        print("    positions courtier indisponibles — comparaison impossible, "
              "rien n'est conclu.")
        return
    print(f"    {'symbole':<12} {'journal':>14} {'courtier':>14} {'écart':>14}")
    print("    " + "-" * 58)
    ecart_total = 0.0
    for sym in sorted(set(par_sym) | set(positions)):
        qj, qc = par_sym.get(sym, 0.0), positions.get(sym, 0.0)
        d = qj - qc
        ecart_total += abs(d)
        marque = "  ←" if abs(d) > 1e-6 * max(1.0, abs(qc)) else ""
        print(f"    {sym:<12} {qj:>14.6f} {qc:>14.6f} {d:>+14.6f}{marque}")
    _age_fantomes(ouverts, positions)
    _doublons(ouverts)
    if ecart_total < 1e-6:
        print("\n    → Journal et courtier sont d'accord. Le réalisé n'est PAS gonflé "
              "par des lots fantômes : chercher le résidu ailleurs.")
    else:
        print("\n    → ÉCART. Le journal porte des quantités que le courtier ne "
              "confirme pas.\n      Les ventes appariées à ces lots produisent un "
              "réalisé sans contrepartie réelle.")


def _age_fantomes(ouverts: list, positions: dict) -> None:
    """Depuis QUAND les lots que le courtier ne détient plus sont-ils « ouverts » ?

    C'est le dernier maillon. Si ces lots datent d'avant un réaménagement du
    portefeuille, la conclusion est mécanique : les ventes qui les ont soldés n'ont
    jamais été enregistrées, donc ils restent ouverts pour toujours — et les ventes
    RÉCENTES viennent s'apparier à eux en FIFO, produisant un réalisé calculé sur un
    prix de revient qui n'a plus rien à voir avec le compte.
    """
    from packages.research.biais_fermeture import symbole_canonique
    detenus = {symbole_canonique(k) for k, v in (positions or {}).items() if v}
    fantomes = [t for t in ouverts if symbole_canonique(t.instrument) not in detenus]
    if not fantomes:
        return
    dates = sorted(_jour(t.entry_ts) for t in fantomes)
    print(f"\n    {len(fantomes)} lots ouverts sur des titres que le courtier ne "
          f"détient PLUS\n    entrés entre {dates[0]} et {dates[-1]} — les ventes qui "
          "les ont soldés\n    n'ont jamais été journalisées, donc ils ne se "
          "fermeront jamais.")


def _ordres_courtier(limite: int = 5000) -> list[dict]:
    """Tous les ordres EXÉCUTÉS du courtier.

    Les ordres NON REMPLIS sont déjà écartés en amont (`AlpacaBroker.orders` saute
    `filled_qty <= 0`) : un ordre passé mais jamais exécuté n'entre nulle part dans ces
    chiffres. C'était une hypothèse naturelle sur l'origine du résidu ; elle est écartée
    par le code, pas par une opinion.
    """
    try:
        from packages.execution.alpaca_broker import AlpacaBroker
        return AlpacaBroker().orders(limit=limite)
    except Exception as e:  # noqa: BLE001
        print(f"  (courtier injoignable : {str(e)[:60]})")
        return []


def _couverture_achats(journal, ordres: list[dict]) -> None:
    """Le journal connaît-il TOUS les achats que le courtier a exécutés ?

    C'EST LA QUESTION QUI EXPLIQUE LE RÉSIDU, et elle n'avait pas été posée.
    L'identité comptable d'une période est :

        Δequity = réalisé + latent(fin) − latent(début) + flux − frais

    Le script compare `réalisé + latent(fin)` à `Δequity`. Le résidu vaut donc, pour
    l'essentiel, `latent(début)` — le gain NON RÉALISÉ que portaient déjà les positions
    au premier point de la courbe — plus tout ce que le journal ne couvre pas.

    Un achat exécuté chez le courtier SANS lot correspondant au journal est exactement
    ce trou-là : quand la position est vendue, le compte encaisse le résultat, mais le
    journal n'a aucun prix de revient à opposer. Le réalisé du journal et la variation
    du compte ne peuvent alors PAS coïncider, et aucune réparation de lots orphelins n'y
    changera quoi que ce soit.

    On compare donc, symbole par symbole, la quantité ACHETÉE chez le courtier à la
    quantité du journal (lots fermés compris — un lot fermé a bien été ouvert).
    """
    from packages.research.biais_fermeture import symbole_canonique
    achats: dict[str, float] = {}
    for o in ordres:
        if o.get("side") == "buy" and float(o.get("qty") or 0) > 0:
            c = symbole_canonique(o["symbol"])
            achats[c] = achats.get(c, 0.0) + float(o["qty"])
    ouverts: dict[str, float] = {}
    for t in journal.all():
        c = symbole_canonique(t.instrument)
        ouverts[c] = ouverts.get(c, 0.0) + float(t.qty or 0)
    print("\n  COUVERTURE DES ACHATS — le journal connaît-il les achats du compte ?\n")
    if not achats:
        print("    aucun achat récupéré chez le courtier — comparaison impossible.")
        return
    manquants = {s: q for s, q in achats.items()
                 if q - ouverts.get(s, 0.0) > 0.01 * max(1.0, q)}
    couverts = len(achats) - len(manquants)
    print(f"    {len(achats)} symbole(s) achetés · {couverts} couvert(s) par le "
          f"journal · {len(manquants)} INCOMPLET(S)")
    for s, q in sorted(manquants.items(), key=lambda kv: -kv[1])[:10]:
        au_j = ouverts.get(s, 0.0)
        print(f"      {s:<12} acheté {q:>12.4f}  ·  journal {au_j:>12.4f}")
    if len(manquants) > 10:
        print(f"      … et {len(manquants) - 10} autres")
    if manquants:
        print("\n    → Ces achats n'ont PAS de prix de revient au journal. Quand ils")
        print("      sont vendus, le compte encaisse le résultat mais le journal n'a")
        print("      rien à opposer : le résidu est là, et il ne se refermera pas en")
        print("      réparant des lots — le journal ne couvre pas tout le compte.")
    else:
        print("\n    → Tous les achats sont couverts. Le résidu vient d'ailleurs :")
        print("      chercher du côté du latent au PREMIER point de la courbe.")


def _origine_du_double(journal, ordres: list[dict]) -> None:
    """D'OÙ vient la seconde copie, quand le journal porte DEUX FOIS l'achat ?

    Mesuré le 03/09, après la complétion des ouvertures : sur 40 symboles, la quantité
    du journal vaut 2,000000 fois celle achetée chez le courtier — AAPL 47,2824 contre
    23,6412, BXP 212,6200 contre 106,3100, FOX 317,8576 contre 158,9288. Dix ratios
    calculés, dix fois 2,000000 : ce n'est pas du bruit d'arrondi, c'est un achat
    enregistré deux fois.

    `_doublons` ne pouvait pas le voir : il ne compare que des lots OUVERTS de mêmes
    titre, quantité, prix et jour. Ici les deux copies ont des IDENTIFIANTS différents,
    l'une peut être fermée et l'autre non, et elles peuvent ne pas porter le même
    drapeau `legacy`. Un test trop étroit avait donc répondu « aucun doublon » à une
    question qu'il ne posait pas.

    Ce bloc ne conclut pas : il VENTILE la quantité du journal par drapeau et par
    préfixe d'identifiant. Si les deux moitiés se répartissent legacy=0 / legacy=1, la
    cause est le recouvrement entre l'import historique et la journalisation live. Si
    elles portent le même drapeau et deux préfixes différents, c'est le chemin
    d'écriture qui a produit deux identités pour un même achat. Le chiffre tranche.
    """
    from packages.research.biais_fermeture import symbole_canonique
    achete: dict[str, float] = {}
    for o in ordres:
        if o.get("side") == "buy" and float(o.get("qty") or 0) > 0:
            c = symbole_canonique(o["symbol"])
            achete[c] = achete.get(c, 0.0) + float(o["qty"])
    # `legacy` n'est pas un champ de TradeRecord : il vit dans la table. On le
    # RÉCUPÈRE par deux requêtes plutôt que par un getattr qui vaudrait toujours None.
    vivants = {t.id for t in journal.all(legacy=False)}
    par_sym: dict[str, list] = {}
    for t in journal.all():
        par_sym.setdefault(symbole_canonique(t.instrument), []).append(t)
    doubles = {s: q for s, q in achete.items()
               if sum(float(t.qty or 0) for t in par_sym.get(s, [])) > 1.5 * q}
    print("\n  ORIGINE DU DOUBLE COMPTAGE — 2× l'achat au journal : sur quels ids ?")
    print()
    if not doubles:
        print("    aucun symbole au-dessus de 1,5× la quantité achetée.")
        return
    print(f"    {len(doubles)} symbole(s) concerné(s). Ventilation des 8 plus gros :\n")
    for sym in sorted(doubles, key=lambda s: -doubles[s])[:8]:
        lots = par_sym.get(sym, [])
        par_prefixe: dict[str, float] = {}
        ids_par_prefixe: dict[str, int] = {}
        q0 = q1 = 0.0
        for t in lots:
            qt = float(t.qty or 0)
            pref = str(t.id).split("-")[0]
            par_prefixe[pref] = par_prefixe.get(pref, 0.0) + qt
            ids_par_prefixe[pref] = ids_par_prefixe.get(pref, 0) + 1
            if t.id in vivants:
                q0 += qt
            else:
                q1 += qt
        total = q0 + q1
        print(f"    {sym:<8} acheté {doubles[sym]:>12.4f} · journal {total:>12.4f} "
              f"({total / doubles[sym]:.4f}×) · {len(lots)} enregistrement(s)")
        print(f"        legacy=0 {q0:>12.4f}   ·   legacy=1 {q1:>12.4f}")
        for pref, q in sorted(par_prefixe.items(), key=lambda kv: -kv[1])[:4]:
            print(f"        id « {pref}… » {q:>12.4f}  "
                  f"sur {ids_par_prefixe[pref]} identifiant(s)")
    print("\n    LECTURE. Deux préfixes portant chacun ~1× la quantité achetée =")
    print("    un même achat écrit par DEUX chemins (import historique et live).")
    print("    Un seul préfixe portant 2× = le chemin d'écriture crée deux identités.")
    print("    Aucune ligne n'est supprimée ici : on mesure d'abord.")


def _base_de_cout(tous: list) -> None:
    """Le prix d'entrée d'un lot est-il celui du MARCHÉ à sa date d'entrée ?

    C'EST LA MESURE QUI EXPLIQUE LE RÉSIDU. Quand la journalisation a démarré, la boucle
    de réconciliation a inscrit les positions DÉJÀ DÉTENUES comme des lots, avec le prix
    de revient moyen du courtier — c'est-à-dire un prix parfois bien antérieur. Le lot
    porte alors une date d'entrée récente et un prix ancien.

    Conséquence exacte sur le résidu : à la vente, le journal calcule le P&L depuis ce
    prix ancien, donc il INCLUT un gain ou une perte acquis AVANT le premier point de la
    courbe d'equity. Or ce gain-là n'est pas dans la variation du compte sur la période.
    L'identité est `Δequity = réalisé + latent(fin) − latent(début) + flux`, et le
    terme `latent(début)` est précisément ce que la comparaison omet.

    On compare donc le prix d'entrée de chaque lot à la CLÔTURE de ce jour-là dans la
    base de prix. Un écart massif et systématique signe l'import ; un écart nul dit que
    les lots ont bien été ouverts au prix du jour, et qu'il faut chercher ailleurs.
    """
    from apps.api.snapshot import _price_db_path
    from packages.data.providers.db_provider import DBPriceProvider
    chemin = _price_db_path()
    print("\n  PRIX D'ENTRÉE vs COURS DU JOUR D'ENTRÉE\n")
    if chemin is None or not Path(chemin).exists():
        print("    base de prix indisponible — comparaison impossible.")
        return
    prov = DBPriceProvider(chemin)
    ecarts, testes, exemples = [], 0, []
    for t in tous[:400]:
        px = _cours_du_jour(prov, t.instrument, t.entry_ts)
        if px is None or not t.entry_price:
            continue
        testes += 1
        rel = float(t.entry_price) / px - 1.0
        ecarts.append(abs(rel))
        if abs(rel) > 0.02 and len(exemples) < 8:
            exemples.append((t.instrument, _jour(t.entry_ts), float(t.entry_price), px,
                             rel))
    if testes < 20:
        print(f"    {testes} lot(s) comparables seulement — rien de concluant.")
        return
    median = sorted(ecarts)[len(ecarts) // 2]
    hors = sum(1 for e in ecarts if e > 0.02)
    print(f"    {testes} lots comparés · écart médian {median:.2%} · "
          f"{hors} au-delà de 2 % ({hors/testes:.0%})")
    for sym, jour, pe, px, rel in exemples:
        print(f"      {sym:<10} le {jour}  entrée {pe:>10.2f}  cours {px:>10.2f}  "
              f"{rel:+7.1%}")
    if hors / testes > 0.25:
        print("\n    → PRIX DE REVIENT IMPORTÉ. Une part notable des lots porte un")
        print("      prix d'entrée étranger au cours du jour inscrit : ce sont des")
        print("      positions déjà détenues, journalisées à leur coût d'origine.")
        print("      Leur P&L à la vente contient donc du gain ANTÉRIEUR à la courbe —")
        print("      c'est le résidu, et il n'y a rien à « réparer » : il faut le")
        print("      SOUSTRAIRE, pas le supprimer.")
    else:
        print("\n    → Les prix d'entrée correspondent aux cours du jour. Le résidu ne")
        print("      vient pas de là : chercher ailleurs, et ne rien conclure ici.")


def _cours_du_jour(prov, symbole: str, ts):
    """Clôture du titre à la date d'entrée du lot, ou None."""
    from datetime import timedelta
    try:
        barres = prov.fetch_ohlcv(symbole, "1d", ts - timedelta(days=6),
                                  ts + timedelta(days=1))
    except Exception:  # noqa: BLE001
        return None
    jour = _jour(ts)
    for b in reversed(barres or []):
        # `_jour` attend un HORODATAGE, pas une barre. Lui passer la barre rendait le
        # repr de l'objet, jamais une date : la comparaison échouait toujours et la
        # mesure annonçait « 0 lot comparable » — un zéro qui ressemblait à une absence
        # de données alors qu'il signalait mon propre bug.
        if _jour(b.ts) <= jour and float(b.close) > 0:
            return float(b.close)
    return None


def _doublons(ouverts: list) -> None:
    """Le même lot est-il enregistré PLUSIEURS FOIS ?

    Constaté le 03/09 : après réparation, les quantités restantes valaient exactement
    la MOITIÉ des quantités initiales, symbole après symbole — AAPL 47,28 → 23,64, BXP
    212,62 → 106,31, CNC 228,81 → 114,40. Les ventes du courtier ont soldé une copie et
    laissé l'autre. Une moitié exacte répétée sur des dizaines de titres n'est pas un
    hasard de marché.

    Deux lots sont tenus pour identiques s'ils partagent symbole, quantité, prix
    d'entrée et JOUR d'entrée. Deux achats réels du même titre, au même prix au centième
    près et pour la même quantité au millionième, le même jour, sont possibles mais
    rares ; on COMPTE donc les groupes au lieu d'affirmer, et on montre l'échantillon.
    """
    groupes: dict[tuple, list] = {}
    for t in ouverts:
        cle = (t.instrument, round(float(t.qty), 6),
               round(float(t.entry_price or 0), 6), _jour(t.entry_ts))
        groupes.setdefault(cle, []).append(t)
    multiples = {k: v for k, v in groupes.items() if len(v) > 1}
    print("\n  LOTS ENREGISTRÉS EN DOUBLE (même titre, quantité, prix ET jour)\n")
    if not multiples:
        print("    aucun — les lots ouverts sont tous distincts.")
        return
    total = sum(len(v) - 1 for v in multiples.values())
    print(f"    {len(multiples)} groupe(s), soit {total} enregistrement(s) "
          f"EXCÉDENTAIRE(S) sur {len(ouverts)} lots ouverts.")
    for (sym, qte, prix, jour), v in sorted(multiples.items())[:10]:
        print(f"      {sym:<12} ×{len(v)}  {qte:>12.6f} @ {prix:>10.4f}  le {jour}")
    if len(multiples) > 10:
        print(f"      … et {len(multiples) - 10} autres groupes")
    print("\n    → Chaque doublon gonfle la quantité au journal et fournit un lot de")
    print("      plus à apparier : c'est du réalisé sans contrepartie réelle.")
    print("      À corriger EN AMONT (l'écriture), pas en supprimant des lignes ici.")


def _positions_courtier() -> dict:
    """Quantités RÉELLEMENT détenues par symbole, telles que le courtier les dit."""
    try:
        from apps.api.snapshot import build_snapshot
        real = (build_snapshot().get("live") or {}).get("real") or {}
        out: dict[str, float] = {}
        for compte in ("alpaca", "crypto"):
            for pos in (real.get(compte) or {}).get("positions", []) or []:
                if pos.get("symbol"):
                    out[pos["symbol"]] = float(pos.get("qty") or 0.0)
        return out
    except Exception as e:  # noqa: BLE001
        print(f"  (positions courtier indisponibles : {str(e)[:60]})")
        return {}


def _residu(b_total: dict, latent: float, variation: float | None) -> None:
    print("\n  RÉCONCILIATION\n")
    print(f"    réalisé (tous lots, legacy compris) : {b_total['realise']:+12,.2f} $")
    print(f"    latent des positions ouvertes       : {latent:+12,.2f} $")
    attendu = b_total["realise"] + latent
    print("    ─────────────────────────────────────────────────")
    print(f"    attendu sur le compte               : {attendu:+12,.2f} $")
    if variation is None:
        print("    variation constatée                 :          n/d")
        print("\n  → Sans courbe d'equity, le résidu ne peut pas être calculé. Rien "
              "n'est conclu.")
        return
    print(f"    variation constatée (brute)         : {variation:+12,.2f} $")
    residu = variation - attendu
    print(f"    ÉCART                               : {residu:+12,.2f} $")
    print("\n  CE QUE CET ÉCART EST, et il n'est pas une anomalie. L'identité d'une")
    print("  période s'écrit  Δequity = réalisé + latent(fin) − latent(DÉBUT) + flux.")
    print("  La comparaison ci-dessus omet `latent(début)` : l'écart vaut donc, pour")
    print("  l'essentiel, le gain ou la perte NON RÉALISÉ que portaient déjà les")
    print("  positions au premier point de la courbe. Les versements ayant été")
    print("  mesurés à zéro, il ne reste que ce terme et les frais hors P&L.")
    print("  Le bloc « PRIX D'ENTRÉE » ci-dessus dit si c'est bien le cas.")


def _latent() -> float:
    """Latent RÉEL, lu chez le courtier — jamais estimé à partir d'un prix d'entrée."""
    try:
        from apps.api.snapshot import build_snapshot
        real = (build_snapshot().get("live") or {}).get("real") or {}
        total = 0.0
        for compte in ("alpaca", "crypto"):
            for pos in (real.get(compte) or {}).get("positions", []) or []:
                total += float(pos.get("pnl") or 0.0)
        return round(total, 2)
    except Exception as e:  # noqa: BLE001
        print(f"  (latent indisponible : {str(e)[:60]})")
        return 0.0


def _cle_fill(sym: str, qty: float, prix: float) -> tuple:
    """Signature d'un fill, arrondie à ce que les deux sources savent porter."""
    return (sym, round(float(qty), 4), round(float(prix), 4))


def _excedent_dans_les_ouverts(journal, ordres: list[dict]) -> None:
    """L'excédent du journal est-il dans les FERMÉS ou dans les OUVERTS ?

    La question précédente (« deux chemins ou deux identités ? ») a reçu une réponse que
    ni l'une ni l'autre de mes hypothèses ne prévoyait. Le dump de deux titres dit :

      ICLN — fermés 301,600106 pour 301,6001 acheté (écart +0,0000) ; OUVERT 301,600106.
      NWL  — fermés 1 554,626507 pour 1 554,6265 acheté ; OUVERTS 1 306,379607.

    Autrement dit : **la partie FERMÉE du registre est exacte au dix-millième**, et tout
    l'excédent tient dans des lots ouverts. Et ces lots portent la date et le prix
    de VENTES : le lot ICLN ouvert entre le 23/06 à 20,83 — jour et prix exacts de la
    vente qui a soldé les deux lots précédents ; le lot NWL de 155,375433 entre le 25/06
    à 5,78 — quantité au millionième, jour et prix de la sortie `-R1`.

    Ce bloc teste cette lecture sur TOUS les symboles au lieu de deux, et sur chaque lot
    ouvert : existe-t-il, chez le courtier, une VENTE de même symbole, même quantité et
    même prix ? Si oui, le lot n'est pas un achat — c'est une vente écrite à l'envers.

    L'appariement est VOLONTAIREMENT strict : un fill de vente, une quantité, un prix.
    Une vente exécutée en plusieurs fills n'a pas de fill unique de même quantité et ne
    sera donc PAS appariée. Le compte renvoyé est un PLANCHER : il sous-estime le nombre
    de ventes écrites à l'envers, il ne peut pas le surestimer. C'est le sens qu'on veut
    pour un chiffre qui servira à décider d'un retrait de lignes.

    Rien n'est supprimé. Le nombre décide de ce qu'on fera, et il doit être lu d'abord.
    """
    from packages.research.biais_fermeture import symbole_canonique
    achats, ventes = {}, set()
    for o in ordres:
        sym = symbole_canonique(o.get("symbol", ""))
        q, px = float(o.get("qty") or 0), float(o.get("price") or 0)
        if q <= 0 or px <= 0:
            continue
        if o.get("side") == "buy":
            achats[sym] = achats.get(sym, 0.0) + q
        elif o.get("side") == "sell":
            ventes.add(_cle_fill(sym, q, px))
    fermes, ouverts = {}, {}
    for t in journal.all():
        sym = symbole_canonique(t.instrument)
        cible = fermes if t.exit_ts else ouverts
        cible[sym] = cible.get(sym, 0.0) + float(t.qty or 0)
    _rapport_excedent(achats, fermes, ouverts)
    lots_ouverts = [t for t in journal.all() if not t.exit_ts]
    apparies = [t for t in lots_ouverts
                if _cle_fill(symbole_canonique(t.instrument), t.qty,
                             t.entry_price or 0) in ventes]
    print(f"\n    LOTS OUVERTS APPARIÉS À UNE VENTE DU COURTIER : "
          f"{len(apparies)} / {len(lots_ouverts)}")
    for t in sorted(apparies, key=lambda x: -float(x.qty or 0))[:8]:
        print(f"      {symbole_canonique(t.instrument):<8} {float(t.qty):>12.6f} @ "
              f"{float(t.entry_price or 0):>9.4f}  entré le {str(t.entry_ts)[:10]}")
    if apparies:
        print("\n      Même symbole, même quantité et même prix qu'une VENTE exécutée.")
        print("      Ces enregistrements décrivent une sortie, pas une entrée.")


def _rapport_excedent(achats: dict, fermes: dict, ouverts: dict) -> None:
    """Les fermetures collent-elles aux achats ? que pèsent les lots ouverts ?"""
    print("\n  OÙ EST L'EXCÉDENT — dans les fermetures, ou dans les lots ouverts ?\n")
    exacts, decales, exces = 0, [], 0.0
    for sym, ach in achats.items():
        f, o = fermes.get(sym, 0.0), ouverts.get(sym, 0.0)
        if abs(f - ach) <= 0.0001 * max(1.0, ach):
            exacts += 1
        else:
            decales.append((sym, ach, f))
        exces += max(0.0, f + o - ach)
    print(f"    {exacts}/{len(achats)} symbole(s) dont les FERMETURES égalent la "
          "quantité achetée (à 0,01 %).")
    for sym, ach, f in sorted(decales, key=lambda x: -abs(x[1] - x[2]))[:6]:
        print(f"      ⚠ {sym:<8} acheté {ach:>12.4f} · fermé {f:>12.4f} "
              f"({f - ach:+.4f})")
    print(f"    Excédent total du journal sur les achats : {exces:,.4f} unité(s)"
          .replace(",", " "))
    print(f"    Quantité en lots OUVERTS : {sum(ouverts.values()):,.4f} unité(s)"
          .replace(",", " "))


def _dump_symbole(journal, symbole: str) -> None:
    """Tous les enregistrements d'un symbole, à plat. Aucune interprétation.

    Le 03/09, `_origine_du_double` a réfuté l'hypothèse que j'avais posée : la seconde
    copie n'est PAS le recouvrement entre l'import historique et la journalisation live.
    Tout est `legacy=1`, tout porte le préfixe `LEG`, et la quantité se répartit sur
    plusieurs identifiants — ICLN 603,2002 sur 3 ids pour 301,6001 acheté, NWL
    2 861,0061 sur 8 ids pour 1 554,6265 acheté.

    Aucun script du dépôt n'écrit d'identifiant `LEG-` : l'import qui les a produits
    n'est plus dans l'arbre. On ne peut donc pas lire son mécanisme — il faut lire ses
    TRACES. Ce bloc les imprime telles quelles : identifiant, quantité, entrée, sortie,
    motif. Ce sont ces lignes, et non une lecture de code, qui diront si le même achat a
    été importé plusieurs fois sous des identités différentes, ou si un lot a été scindé
    sans que le reste soit réduit.

        python scripts/diag_journal_compte.py --symbole ICLN
    """
    from packages.research.biais_fermeture import symbole_canonique
    cible = symbole_canonique(symbole)
    vivants = {t.id for t in journal.all(legacy=False)}
    lots = [t for t in journal.all() if symbole_canonique(t.instrument) == cible]
    print(f"\n  TOUS LES ENREGISTREMENTS DE « {cible} » — {len(lots)} ligne(s)\n")
    if not lots:
        print("    aucun. Vérifier l'orthographe du symbole.")
        return
    print(f"    {'identifiant':<34} {'lg':>2} {'quantité':>13} "
          f"{'entrée':>10} {'prix ent.':>11} {'sortie':>10} {'prix sor.':>11}")
    print("    " + "-" * 96)
    total = 0.0
    for t in sorted(lots, key=lambda x: (str(x.entry_ts), str(x.id))):
        q = float(t.qty or 0.0)
        total += q
        print(f"    {str(t.id)[:34]:<34} {0 if t.id in vivants else 1:>2} {q:>13.6f} "
              f"{str(t.entry_ts)[:10]:>10} {float(t.entry_price or 0):>11.4f} "
              f"{(str(t.exit_ts)[:10] if t.exit_ts else '—'):>10} "
              f"{float(t.exit_price or 0):>11.4f}")
        if t.exit_reason:
            print(f"        motif : {str(t.exit_reason)[:80]}")
    print(f"\n    quantité TOTALE au journal : {total:.6f}")
    print("    (à comparer à la quantité ACHETÉE du bloc COUVERTURE DES ACHATS)")


def main() -> None:
    print(__doc__.split("    python")[0].rstrip())
    print()
    try:
        from packages.storage import SqliteTradeJournal
        j = SqliteTradeJournal()
        tous = j.all()
        b_total = _bilan(tous)
    except Exception as e:  # noqa: BLE001
        print(f"Journal illisible : {str(e)[:80]}")
        return
    if "--symbole" in sys.argv:
        i = sys.argv.index("--symbole")
        if i + 1 >= len(sys.argv):
            print("  --symbole attend un ticker (ex. --symbole ICLN).")
            return
        _dump_symbole(j, sys.argv[i + 1])       # dump SEUL : pas de snapshot, immédiat
        return
    _journal()
    # La courbe est lue AVANT le snapshot : `build_snapshot` enregistre le point du jour
    # et modifierait la série entre deux lectures.
    courbes = _courbes()
    _compte(courbes, b_total)
    print("\n  Construction du snapshot pour lire le courtier… ~30-60 s")
    positions = _positions_courtier()
    _lots_vs_courtier([t for t in tous if not t.exit_ts], positions)
    _ordres = _ordres_courtier()
    _couverture_achats(j, _ordres)
    _origine_du_double(j, _ordres)
    _excedent_dans_les_ouverts(j, _ordres)
    _base_de_cout(tous)
    latent = _latent()
    variation = None
    for pts in courbes.values():
        if len(pts) >= 2:
            variation = (variation or 0.0) + float(pts[-1]["v"]) - float(pts[0]["v"])
    _residu(b_total, latent, variation)


if __name__ == "__main__":
    main()
