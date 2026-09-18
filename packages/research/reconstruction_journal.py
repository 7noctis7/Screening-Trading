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
#
# LE DÉNOMINATEUR EST LE VOLUME ACHETÉ, PAS LA POSITION RESTANTE (18/09). Rapporter
# l'écart à la position en cours ne peut pas marcher : une poche entièrement soldée
# laisse un résidu quand le courtier détient ZÉRO, et un rapport à zéro est infini.
# Les frais sont prélevés à CHAQUE transaction — ils se mesurent donc contre ce qui a
# été brassé. Vérification sur neuf actifs indépendants le 18/09, après rejeu complet :
#
#     AAVE 0,221 %   AVAX 0,223 %   BCH 0,220 %   BTC 0,220 %   ETH 0,220 %
#     LINK 0,220 %   LTC  0,220 %   SOL 0,220 %   UNI 0,220 %
#
# Neuf actifs, un seul chiffre : ce n'est pas une tolérance qu'on choisit, c'est le
# barème du courtier qu'on RETROUVE. La borne est posée à plus du double, assez large
# pour couvrir un barème qui bougerait, assez serrée pour qu'une vraie erreur ressorte.
PART_FRAIS_NATURE = 0.005


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
    # Quantité CUMULÉE achetée par symbole normalisé. C'est le dénominateur des frais
    # prélevés en nature : une poche soldée n'a plus de position, elle a eu un volume.
    achete: dict[str, float] = field(default_factory=dict)

    @property
    def realise(self) -> float:
        """BRUT DE FRAIS, et le nom le dit. L'historique des ORDRES ne porte pas les
        frais : la crypto est prélevée en nature (`CFEE`), les actions en dollars
        (`TAF`/`REG`/`CAT`). Appeler « net » une somme qui ne l'est pas serait le
        genre d'étiquette qui survit des mois et fausse tout ce qui la lit."""
        return round(sum(float(t["pnl_brut"]) for t in self.fermes), 2)

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
            "pnl_brut": round(brut, 6),
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
            cle = normaliser(sym)
            r.achete[cle] = round(r.achete.get(cle, 0.0) + q, 10)
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
    un excédent du journal borné à `PART_FRAIS_NATURE` DU VOLUME ACHETÉ s'explique par
    les frais prélevés EN JETONS, que l'historique des ORDRES ne porte pas. Ce n'est pas
    une marge de confort : le sens est imposé (le journal ne peut qu'être EN EXCÈS,
    jamais en défaut), la borne vaut le double du barème RETROUVÉ sur neuf actifs, et
    ces écarts sont rendus à part — avec leur taux, pour que l'uniformité se VOIE.
    """
    calcule = rejeu.quantites_ouvertes()
    reel = {normaliser(k): float(v) for k, v in (positions or {}).items()}
    ecarts, frais_nature = [], []
    for sym in sorted(set(calcule) | set(reel)):
        a, b = calcule.get(sym, 0.0), reel.get(sym, 0.0)
        d = a - b
        if abs(d) <= tolerance:
            continue
        volume = float(rejeu.achete.get(sym, 0.0))
        ligne = {"symbole": sym, "journal": round(a, 8), "courtier": round(b, 8),
                 "ecart": round(d, 8), "volume_achete": round(volume, 8)}
        if _crypto(sym) and volume > 0 and 0 < d <= PART_FRAIS_NATURE * volume:
            ligne["part"] = round(d / volume, 6)
            frais_nature.append(ligne)
        else:
            ecarts.append(ligne)
    return {"conforme": not ecarts, "ecarts": ecarts, "frais_nature": frais_nature,
            "n_symboles": len(set(calcule) | set(reel))}
