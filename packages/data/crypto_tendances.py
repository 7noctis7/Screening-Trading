"""Ce que le public CHERCHE et ce qui s'ÉCHANGE — deux questions, deux listes.

Séparé de `crypto_market` parce que ces parseurs répondent à une question distincte
de l'état du marché (capitalisation, dominance, régime) : ils décrivent l'ATTENTION
et le CAPITAL ENGAGÉ. Les garder ensemble poussait le module au-delà de 400 lignes.

Ne renvoie jamais 0 à la place d'une absence : une variation inconnue vaut `None`,
rendue « n/d » à l'écran. Un 0 % inventé est indiscernable d'un actif immobile.
"""

from __future__ import annotations

from typing import Any


def _num(x: Any) -> float | None:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _usd(bloc: Any, cle: str) -> float | None:
    """Valeur en dollars d'un champ que CoinGecko rend tantôt nu, tantôt par devise.

    Le même endpoint publie `market_cap_change_percentage_24h` comme un nombre sur
    certaines listes et comme `{"usd": …, "eur": …}` sur d'autres. Lire les deux formes
    ici évite qu'un changement d'API rende silencieusement des `None` partout — la panne
    la plus discrète, puisqu'une carte vide ressemble à une carte sans actualité.
    """
    v = (bloc or {}).get(cle)
    return _num(v.get("usd")) if isinstance(v, dict) else _num(v)


def _chg_trending(item: dict, par_id: dict) -> float | None:
    """Variation 24 h d'une ligne tendance, ou None. TROIS SOURCES, DANS CET ORDRE.

    1. le bloc `data` que l'endpoint joint parfois à chaque item — la plus directe ;
    2. à défaut, la jointure sur `/coins/markets`, qui ne couvre QUE le top 100 ;
    3. sinon None, rendu « n/d » à l'écran.

    Le troisième cas n'est pas un échec : la moitié des lignes tendance sont des rangs
    au-delà du 500ᵉ, absentes du top 100 et sans bloc `data`. Écrire 0 % y serait une
    invention — et c'est sur ces lignes que le chiffre importerait le plus.
    """
    d = item.get("data") or {}
    pct = d.get("price_change_percentage_24h")
    if isinstance(pct, dict):
        v = _num(pct.get("usd"))
        if v is not None:
            return round(v, 2)
    elif (v := _num(pct)) is not None:
        return round(v, 2)
    m = par_id.get(item.get("id"))
    return m.get("chg24h") if m else None


def parse_trending(data: Any, markets: list[dict] | None = None) -> list[dict]:
    """/search/trending → [{id, name, sym, rank, chg24h}].

    LA VARIATION 24 H REND LA CARTE FALSIFIABLE. Le panneau affirme depuis l'origine
    que « quand une crypto arrive ici, le mouvement a souvent déjà eu lieu » — sans
    jamais le montrer. Avec la variation à côté, l'affirmation devient une mesure que
    le lecteur peut contredire. Une carte qui énonce une thèse sans donner de quoi la
    réfuter n'est pas un thermomètre, c'est un slogan.
    """
    par_id = {m["id"]: m for m in (markets or []) if m.get("id")}
    out = []
    for c in ((data or {}).get("coins") or []):
        it = c.get("item") or {}
        if it.get("name"):
            out.append({"id": it.get("id"), "name": it["name"],
                        "sym": str(it.get("symbol") or "").upper(),
                        "rank": it.get("market_cap_rank"),
                        "chg24h": _chg_trending(it, par_id)})
    return out


def parse_trending_autres(data: Any) -> dict:
    """Les deux listes du MÊME appel que le parseur jetait : catégories et NFT.

    `/search/trending` rend trois ensembles — `coins`, `categories`, `nfts` — et seul le
    premier était lu. Les deux autres étaient téléchargés puis perdus à chaque build.

    Les CATÉGORIES valent souvent mieux qu'un jeton isolé : elles disent quel THÈME le
    public cherche (IA, RWA, memecoins), ce qui bouge moins vite qu'un ticker de rang
    900 et se prête mieux à une lecture de régime.
    """
    d = data or {}
    cats = [{"id": c.get("id"), "name": c.get("name"),
             "chg24h": _usd(c.get("data"), "market_cap_change_percentage_24h")}
            for c in (d.get("categories") or []) if c.get("name")]
    nfts = [{"name": n.get("name"), "sym": str(n.get("symbol") or "").upper(),
             "plancher": n.get("floor_price_in_native_currency"),
             "devise": n.get("native_currency_symbol"),
             "chg24h": _num(n.get("floor_price_24h_percentage_change"))}
            for n in (d.get("nfts") or []) if n.get("name")]
    return {"categories": cats, "nfts": nfts}


def parse_volume(data: Any, n: int = 20) -> list[dict]:
    """/coins/markets?order=volume_desc → ce qui s'ÉCHANGE le plus, top `n`.

    AUTRE QUESTION QUE « CE QUI EST RECHERCHÉ ». Le volume mesure du capital engagé,
    la recherche mesure de l'attention. Les deux listes se recoupent parfois et
    divergent souvent — et c'est leur divergence qui est informative. Les fondre en
    une seule carte détruirait cette information.

    Le ratio volume / capitalisation est rendu tel quel : au-delà de 1, un actif
    change de mains plus vite que sa valeur totale en une journée. On ne le qualifie
    pas ici — aucun seuil n'a été mesuré sur ces données.
    """
    out = []
    for m in data or []:
        vol, mcap = _num(m.get("total_volume")), _num(m.get("market_cap"))
        if not (m.get("name") and vol):
            continue
        out.append({"id": m.get("id"), "sym": str(m.get("symbol") or "").upper(),
                    "name": m["name"], "volume": vol, "mcap": mcap,
                    "prix": _num(m.get("current_price")),
                    "chg24h": _num(m.get("price_change_percentage_24h")),
                    "rotation": round(vol / mcap, 3) if mcap else None})
    out.sort(key=lambda r: -r["volume"])
    return out[:n]
