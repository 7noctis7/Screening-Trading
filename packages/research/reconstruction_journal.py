"""Rejouer les fills du COURTIER en FIFO — le seul registre qui n'invente rien.

D'OÙ VIENT CE MODULE (18/09). Le journal accumulait trois mois de dégâts qu'aucune
réparation ne pouvait plus atteindre : 167 lots importés dont la provenance est
illisible, 88 lots ouverts qu'aucune vente ne solde, 29 symboles que le compte ne
détient plus, NWL et MAS portant ~2× leur achat. Tous ces défauts ont la même cause —
des écritures produites AILLEURS que chez le courtier — et la même conséquence : les
refermer demanderait d'inventer un prix ou une date.

LA SOURCE UNIQUE. L'historique des ordres EXÉCUTÉS d'Alpaca contient tout : symbole,
sens, quantité, prix, horodatage, identifiant de fill. Rejoué en FIFO, il produit
mécaniquement les lots ouverts ET les aller-retours fermés. Rien n'est supposé, rien
n'est complété : ce qui n'est pas dans l'historique n'entre pas au registre.

LE FIFO N'EST PAS UN DÉTAIL DE MISE EN ŒUVRE. Une vente partielle doit consommer les
lots dans l'ordre d'achat, sinon le prix de revient — donc le réalisé — dépend de
l'ordre arbitraire dans lequel on parcourt la liste. Une vente qui déborde les lots
disponibles est NOMMÉE (`ventes_orphelines`), jamais absorbée : c'est le signe que
l'historique récupéré est tronqué, et le taire produirait un réalisé faux.

CE QU'ON NE FAIT PAS. Aucune fusion avec l'ancien journal. Mélanger une source sûre et
une source illisible donne une source illisible — c'est exactement comment on en est
arrivé là.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Un fill dont le prix est nul ne dit rien d'exploitable : l'écrire fabriquerait un
# prix de revient de zéro, donc un réalisé égal au produit de la vente.
MIN_PRIX = 1e-12

# LES FRAIS CRYPTO SE PRÉLÈVENT EN NATURE, et l'historique des ORDRES ne les porte pas
# (ce sont des `CFEE`, des mouvements de compte). Un rejeu d'achats et de ventes
# surestime donc TOUJOURS une quantité crypto, de la somme des frais retenus en jetons.
# Mesuré le 18/09 : UNI journal 287,856 contre 287,223 chez le courtier, soit 0,22 %.
# On ne corrige pas la quantité — ce serait inventer une écriture — on NOMME l'écart et
# on borne ce qu'on accepte d'appeler ainsi.
PART_FRAIS_NATURE = 0.01


def normaliser(symbole: str) -> str:
    """« UNI/USD » et « UNIUSD » sont le même instrument, et le courtier emploie les
    DEUX : la barre oblique dans l'historique des ordres, la forme collée dans les
    positions. Comparer les chaînes brutes faisait donc apparaître une position
    fantôme d'un côté et une absence de l'autre — pour un seul et même jeton.
    """
    return str(symbole or "").upper().replace("/", "")


@dataclass
class Lot:
    """Un achat, éventuellement entamé par des ventes successives."""

    symbole: str
    qty: float
    reste: float
    prix: float
    ts: str
    ordre: str


@dataclass
class Rejeu:
    """Le registre reconstruit, et ce qui n'a pas pu l'être."""

    ouverts: list[dict] = field(default_factory=list)
    fermes: list[dict] = field(default_factory=list)
    ventes_orphelines: list[dict] = field(default_factory=list)
    ignores: list[dict] = field(default_factory=list)

    @property
    def realise(self) -> float:
        return round(sum(float(t["pnl_net"]) for t in self.fermes), 2)

    def quantites_ouvertes(self) -> dict[str, float]:
        """Clés NORMALISÉES : c'est le seul niveau où deux graphies doivent se
        rejoindre. Le lot, lui, garde la graphie du fill — c'est la vérité du
        courtier pour cette écriture-là."""
        out: dict[str, float] = {}
        for lot in self.ouverts:
            k = normaliser(lot["symbole"])
            out[k] = round(out.get(k, 0.0) + lot["qty"], 10)
        return out


def _exploitable(f: dict) -> bool:
    return (float(f.get("qty") or 0) > 0 and float(f.get("price") or 0) > MIN_PRIX
            and f.get("symbol") and f.get("side") in ("buy", "sell"))


def _vendre(lots: list[Lot], f: dict, fermes: list[dict]) -> float:
    """Consomme les lots du plus ANCIEN au plus récent, et renvoie le NON COUVERT.

    Chaque tranche consommée produit son propre aller-retour : une vente qui solde trois
    achats est trois trades, pas un — leurs prix d'entrée diffèrent, et les moyenner
    effacerait la seule information que ce registre existe pour porter.
    """
    reste = float(f["qty"])
    prix_sortie = float(f["price"])
    for lot in lots:
        if reste <= 0:
            break
        if lot.reste <= 0:
            continue
        pris = min(lot.reste, reste)
        lot.reste -= pris
        reste -= pris
        brut = (prix_sortie - lot.prix) * pris
        fermes.append({
            "symbole": lot.symbole, "qty": round(pris, 10),
            "entree_ts": lot.ts, "entree_prix": lot.prix,
            "sortie_ts": f.get("date", ""), "sortie_prix": prix_sortie,
            "pnl_net": round(brut, 6),
            "pnl_pct": round((prix_sortie / lot.prix - 1.0), 6) if lot.prix else None,
            "ordre_entree": lot.ordre, "ordre_sortie": str(f.get("id", "")),
        })
    return round(reste, 10)


def rejouer(fills: list[dict]) -> Rejeu:
    """Les fills du courtier, en ORDRE CHRONOLOGIQUE, rejoués en FIFO par symbole.

    L'ordre est imposé ici et pas laissé à l'appelant : `AlpacaBroker.orders` rend les
    plus RÉCENTS d'abord, et rejouer à l'envers apparierait une vente à un achat
    postérieur — une chronologie impossible, le défaut que `annuler_chronologie` existe
    déjà pour nettoyer.
    """
    r = Rejeu()
    par_symbole: dict[str, list[Lot]] = {}
    def _cle(x: dict) -> tuple:
        return (str(x.get("date") or ""), str(x.get("id") or ""))

    for f in sorted(fills or [], key=_cle):
        if not _exploitable(f):
            r.ignores.append({"ordre": str(f.get("id", "")), "motif": "fill illisible",
                              "symbole": f.get("symbol"), "qty": f.get("qty"),
                              "prix": f.get("price")})
            continue
        sym = str(f["symbol"])
        lots = par_symbole.setdefault(normaliser(sym), [])
        if f["side"] == "buy":
            q = float(f["qty"])
            lots.append(Lot(sym, q, q, float(f["price"]), str(f.get("date", "")),
                            str(f.get("id", ""))))
        else:
            decouvert = _vendre(lots, f, r.fermes)
            if decouvert > 0:
                r.ventes_orphelines.append({
                    "symbole": sym, "qty": decouvert, "prix": float(f["price"]),
                    "ts": str(f.get("date", "")), "ordre": str(f.get("id", ""))})
    for sym, lots in sorted(par_symbole.items()):
        for lot in lots:
            if lot.reste > 0:
                r.ouverts.append({"symbole": sym, "qty": round(lot.reste, 10),
                                  "entree_ts": lot.ts, "entree_prix": lot.prix,
                                  "ordre_entree": lot.ordre})
    return r


def _crypto(symbole: str) -> bool:
    return normaliser(symbole).endswith(("USD", "USDT", "USDC")) and len(symbole) > 4


def confronter(rejeu: Rejeu, positions: dict[str, float],
               tolerance: float = 1e-4) -> dict:
    """LA SEULE VALIDATION QUI COMPTE : les lots ouverts reconstruits égalent-ils ce que
    le courtier DÉTIENT ?

    Un rejeu qui ne retombe pas sur l'inventaire réel est faux, et le publier serait
    refaire l'erreur qu'on corrige. On compare symbole par symbole, dans les deux sens —
    un symbole présent d'un seul côté est le défaut le plus parlant — après
    NORMALISATION, sans quoi « UNI/USD » et « UNIUSD » se lisent comme deux instruments.

    UNE SEULE CATÉGORIE D'ÉCART EST TOLÉRÉE, et elle est nommée : sur un actif CRYPTO,
    un excédent du journal borné à `PART_FRAIS_NATURE` s'explique par les frais prélevés
    EN JETONS, que l'historique des ORDRES ne porte pas. Ce n'est pas une marge de
    confort : le sens est imposé (le journal ne peut qu'être EN EXCÈS, jamais en
    défaut), la borne est mesurée, et ces écarts sont rendus à part — pas absorbés.
    """
    calcule = rejeu.quantites_ouvertes()
    reel = {normaliser(k): float(v) for k, v in (positions or {}).items()}
    ecarts, frais_nature = [], []
    for sym in sorted(set(calcule) | set(reel)):
        a, b = calcule.get(sym, 0.0), reel.get(sym, 0.0)
        d = a - b
        if abs(d) <= tolerance:
            continue
        ligne = {"symbole": sym, "journal": round(a, 8), "courtier": round(b, 8),
                 "ecart": round(d, 8)}
        if _crypto(sym) and 0 < d <= PART_FRAIS_NATURE * max(a, b):
            ligne["part"] = round(d / max(a, b), 6)
            frais_nature.append(ligne)
        else:
            ecarts.append(ligne)
    return {"conforme": not ecarts, "ecarts": ecarts, "frais_nature": frais_nature,
            "n_symboles": len(set(calcule) | set(reel))}
