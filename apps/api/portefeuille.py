"""Le portefeuille RÉEL, lu MAINTENANT — sans reconstruire le snapshot.

POURQUOI (22/09). Le bandeau du site affiche « LIVE · il y a 15min ». Ces quinze minutes
ne sont pas un retard de la donnée : c'est la période de reconstruction du snapshot
(`_TTL_S`). Or ce snapshot mélange deux natures qui n'ont pas du tout le même rythme :

  · le SCREENING lit des barres QUOTIDIENNES, et sa fenêtre s'arrête à minuit
    (`snapshot.py`, `end = now().replace(hour=0, …)`). Le reconstruire toutes les deux
    minutes relirait exactement les mêmes chiffres — pour rien ;
  · le PORTEFEUILLE vient du courtier, en direct. Lui bouge à chaque seconde de séance,
    et c'est celui qu'on regarde quand on se demande où on en est.

Raccourcir le TTL aurait donc payé un recalcul complet du screening pour rafraîchir la
moitié qui en a besoin. Cette route fait l'inverse : deux appels courtier (`equity` et
`positions_detailed`), rien d'autre, et surtout **jamais** de construction de snapshot.

TROIS RÈGLES D'HONNÊTETÉ, et elles sont le cœur du module.

1. **ABSENT N'EST PAS ZÉRO.** Un compte injoignable ne vaut pas 0 $ : il vaut « on ne
   sait pas ». Le total est alors marqué INCOMPLET et le compte manquant est NOMMÉ. Un
   total qui rétrécit en silence parce qu'un courtier ne répond plus est le pire des
   chiffres : il a l'air d'une perte.
2. **Une position sans valeur ne disparaît pas.** Elle est listée, exclue du total, et
   comptée à part. Sans ça, une ligne dont le prix manque s'évaporerait du portefeuille.
3. **Rien n'est estimé.** Aucun repli sur un prix de la veille, aucune extrapolation.
"""

from __future__ import annotations

# Cache serveur PARTAGÉ : plusieurs onglets ouverts ne martèlent pas l'API du courtier.
FRAICHEUR_S = 20.0


def _ligne(p: dict, compte: str) -> dict:
    """Une position à plat. `valeur` vaut None quand le courtier ne la chiffre pas."""
    v = p.get("market_value")
    return {"symbole": p.get("symbol"), "compte": compte,
            "qty": p.get("qty"), "prix": p.get("last") or p.get("price"),
            "valeur": float(v) if isinstance(v, (int, float)) else None,
            "pnl": p.get("pnl"), "pnl_pct": p.get("pnl_pct")}


def _somme(valeurs: list) -> float | None:
    """Somme des valeurs connues, ou None s'il n'y en a aucune.

    Jamais 0.0 par défaut : un zéro se lit comme une mesure, une absence non.
    """
    connues = [v for v in valeurs if isinstance(v, (int, float))]
    return round(sum(connues), 2) if connues else None


def _compte(c: dict) -> dict:
    """Le bilan d'UN courtier. Muet → `equity` et le décompte valent None, pas 0."""
    return {"nom": c.get("nom"), "ok": bool(c.get("ok")),
            "equity": c.get("equity") if c.get("ok") else None,
            "n_positions": len(c.get("positions") or []) if c.get("ok") else None,
            "motif": None if c.get("ok") else (c.get("error") or "sans réponse")}


def agreger(comptes: list[dict]) -> dict:
    """Agrège les lectures courtier. Fonction PURE : aucune E/S, aucune horloge.

    `comptes` : `{"nom", "configure", "ok", "equity", "positions", "error"}` par
    courtier. Un compte NON CONFIGURÉ (pas de clés) n'est pas un incident : il est hors
    périmètre, et ne rend donc pas le total incomplet. Un compte configuré qui ne répond
    PAS, si.
    """
    vus = [c for c in (comptes or []) if c.get("configure")]
    ok = [c for c in vus if c.get("ok")]
    muets = [c for c in vus if not c.get("ok")]
    lignes = [_ligne(p, c.get("nom") or "?")
              for c in ok for p in (c.get("positions") or [])]
    lignes.sort(key=lambda r: -(r["valeur"] or 0.0))
    sans_valeur = [r["symbole"] for r in lignes if r["valeur"] is None]
    return {
        "disponible": bool(ok),
        "complet": bool(ok) and not muets,
        "equity_total": _somme([c.get("equity") for c in ok]),
        "valeur_positions": _somme([r["valeur"] for r in lignes]),
        "latent_total": _somme([r["pnl"] for r in lignes]),
        "n_positions": len(lignes),
        "positions": lignes,
        "sans_valeur": sans_valeur,
        "comptes": [_compte(c) for c in vus],
        "incidents": [f"{c.get('nom')} : {c.get('error') or 'sans réponse'}"
                      for c in muets],
    }


def message(p: dict) -> str:
    """Ce que le total vaut, et ce qu'il NE COUVRE PAS. Jamais un chiffre nu.

    Un total partiel présenté comme un total est un mensonge par omission : il ressemble
    trait pour trait à une perte.
    """
    if not p.get("disponible"):
        motifs = "; ".join(p.get("incidents") or []) or "aucun courtier configuré"
        return f"Portefeuille indisponible — {motifs}."
    base = (f"{p['n_positions']} position(s)"
            + (f" · {p['equity_total']:,.2f} $".replace(",", " ")
               if p.get("equity_total") is not None else " · equity inconnue"))
    if not p["complet"]:
        base += (" · TOTAL INCOMPLET, il manque " + ", ".join(p["incidents"]))
    if p["sans_valeur"]:
        base += (f" · {len(p['sans_valeur'])} ligne(s) non chiffrée(s), exclues du "
                 "total : " + ", ".join(p["sans_valeur"][:6]))
    return base + "."
