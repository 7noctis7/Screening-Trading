"""Reconstitue les OUVERTURES que le journal n'a jamais enregistrées, depuis les fills.

LE TROU. `run_live._journal_opens` prenait le prix et la quantité d'entrée dans la
POSITION du courtier lue juste après l'envoi de l'ordre. Quand la position n'était pas
encore rafraîchie, l'achat n'était journalisé NULLE PART — et rien ne le rattrapait.
Mesuré le 03/09 sur le compte réel : 87 symboles achetés, 57 couverts par le journal,
30 INCOMPLETS (AVAX 626 unités au journal contre 1 239 achetées, PATH 9 contre 139).

CE QUE ÇA CASSE. Un achat sans lot au journal n'a pas de prix de revient. Quand la
position est vendue, le compte encaisse le résultat mais le journal n'a rien à opposer :
le « réalisé » du registre et la variation du compte ne peuvent pas coïncider, et aucune
réparation des SORTIES n'y change quoi que ce soit. La cause est en amont, à l'entrée.

CE QU'ON RECONSTITUE, ET COMMENT. Symbole par symbole, on compare la quantité ACHETÉE
chez le courtier à celle que le journal connaît (lots fermés compris — un lot fermé a
bien été ouvert). L'écart est la quantité manquante. Son prix de revient n'est PAS le
VWAP de tous les achats du symbole : ce serait mélanger les fills déjà couverts avec
ceux qui manquent. On consomme donc les fills en FIFO à hauteur de ce que le journal
couvre déjà, et le prix retenu est le VWAP des fills QUI RESTENT — c'est-à-dire
précisément ceux que le registre ignore.

CE QUE CES LOTS SONT, ET POURQUOI ILS SONT `legacy`. Ce sont des fills importés APRÈS
COUP : les features de décision de ces achats n'ont jamais été capturées et ne peuvent
plus l'être. C'est la définition exacte de `legacy=1` dans ce dépôt. Les faire entrer en
`legacy=0` gonflerait la statistique AFFICHÉE de trades sans features — soit polluer le
chiffre qu'on cherche à rendre fiable.

CE QU'ON NE FAIT PAS. Aucun lot n'est créé pour un symbole que le courtier ne rapporte
pas : un courtier muet ne produit pas de correction, il produit un silence. Et un écart
NÉGATIF (le journal en sait plus que le courtier) n'est jamais « corrigé » en retirant
des lots — il est signalé, parce qu'il dit autre chose (historique tronqué, ou lots
fantômes) et qu'un outil qui supprime pour faire coller les chiffres ne répare rien.
"""

from __future__ import annotations

from packages.research.biais_fermeture import symbole_canonique

TOLERANCE = 0.01                 # 1 % de la quantité achetée — arrondis de fills
MOTIF = "completion-ouvertures"


def achats_par_symbole(ordres: list[dict]) -> dict[str, list[dict]]:
    """Fills d'ACHAT exploitables, groupés par symbole canonique et triés par DATE.

    L'ordre chronologique n'est pas cosmétique : c'est lui qui rend le FIFO possible.
    Un fill sans quantité, sans prix ou sans date n'entre pas — on ne complète pas un
    registre avec des lignes qu'on serait incapable de dater."""
    par_sym: dict[str, list[dict]] = {}
    for o in ordres or []:
        if o.get("side") != "buy":
            continue
        q, px = float(o.get("qty") or 0.0), float(o.get("price") or 0.0)
        d = o.get("date")
        if q <= 0 or px <= 0 or not d:
            continue
        par_sym.setdefault(symbole_canonique(o.get("symbol", "")), []).append(
            {"qty": q, "price": px, "date": str(d),
             "venue": o.get("broker") or o.get("venue") or ""})
    for fills in par_sym.values():
        fills.sort(key=lambda f: f["date"])
    return par_sym


def quantites_journalisees(records) -> dict[str, float]:
    """Quantité que le journal connaît par symbole canonique, lots FERMÉS COMPRIS.

    Un lot fermé a bien été ouvert : l'exclure ferait apparaître comme « manquant »
    tout achat déjà soldé, et l'outil recréerait sans fin des lots déjà connus."""
    out: dict[str, float] = {}
    for t in records:
        c = symbole_canonique(t.instrument)
        out[c] = out.get(c, 0.0) + float(t.qty or 0.0)
    return out


def _reste_fifo(fills: list[dict], deja: float) -> list[dict]:
    """Fills restants après consommation FIFO de `deja` unités (dernier fill scindé)."""
    reste, a_consommer = [], max(0.0, deja)
    for f in fills:
        if a_consommer <= 1e-12:
            reste.append(f)
            continue
        if f["qty"] <= a_consommer + 1e-12:
            a_consommer -= f["qty"]
            continue
        reste.append({**f, "qty": f["qty"] - a_consommer})     # fill coupé en deux
        a_consommer = 0.0
    return reste


def _vwap(fills: list[dict]) -> tuple[float, float]:
    q = sum(f["qty"] for f in fills)
    return (q, sum(f["qty"] * f["price"] for f in fills) / q) if q > 0 else (0.0, 0.0)


def ouvertures_manquantes(
        ordres: list[dict], journalise: dict[str, float],
        tolerance: float = TOLERANCE) -> tuple[list[dict], list[dict]]:
    """(lots à créer, écarts NÉGATIFS signalés). Aucune écriture — c'est un PLAN.

    Le lot proposé porte la quantité manquante, le VWAP des fills non couverts, et la
    date du PREMIER d'entre eux : c'est la date à laquelle l'exposition a réellement
    commencé, pas celle où l'on répare."""
    a_creer, en_trop = [], []
    for sym, fills in sorted(achats_par_symbole(ordres).items()):
        achete = sum(f["qty"] for f in fills)
        connu = journalise.get(sym, 0.0)
        ecart = achete - connu
        if ecart < -tolerance * max(1.0, achete):
            en_trop.append({"symbole": sym, "achete": achete, "journal": connu})
            continue
        if ecart <= tolerance * max(1.0, achete):
            continue
        reste = _reste_fifo(fills, connu)
        qty, prix = _vwap(reste)
        if qty <= 0 or prix <= 0:
            continue
        a_creer.append({"symbole": sym, "qty": round(min(qty, ecart), 10), "prix": prix,
                        "date": reste[0]["date"], "venue": reste[0]["venue"],
                        "achete": achete, "journal": connu})
    return a_creer, en_trop
