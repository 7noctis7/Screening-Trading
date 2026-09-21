"""L'historique d'ordres RÉEL, lu au courtier — un seul endroit pour le demander.

POURQUOI UN MODULE ET PAS UNE FONCTION DE SCRIPT. `scripts/cout_churn.py` la portait
d'abord ; `scripts/daily_brief.py` a voulu la même chose et ne pouvait pas l'importer —
`scripts/` n'est pas un paquet, et le brief tournait avec « No module named 'scripts' ».
Une fonction dont deux appelants ont besoin n'est plus un détail de script.

IL NE FABRIQUE RIEN. Sans clé, sans courtier ou sur une lecture ratée, il rend une liste
VIDE et un MOTIF. Un historique absent n'est pas un historique nul : confondre les deux
ferait dire « aucun doublon » à un outil qui n'a simplement rien pu lire.
"""

from __future__ import annotations

PAGES = 2000          # l'historique complet ; la pagination est gérée par l'adaptateur


def ordres_reels(limite: int = PAGES) -> tuple[list[dict], str]:
    """(ordres remplis, motif d'échec). Motif non vide ⇒ la liste ne veut rien dire."""
    try:
        from scripts.run_live import _alpaca_ou_rien  # noqa: PLC0415
    except Exception:  # noqa: BLE001 — `scripts/` n'est pas toujours importable
        courtier, motif = _alpaca_par_chemin()
        if motif:
            return [], motif
    else:
        try:
            courtier = _alpaca_ou_rien()
        except Exception as e:  # noqa: BLE001
            return [], f"courtier indisponible ({str(e)[:80]})"
    if courtier is None:
        return [], "aucune clé Alpaca dans l'environnement — rien à lire"
    try:
        return courtier.orders(limit=limite) or [], ""
    except Exception as e:  # noqa: BLE001
        return [], f"lecture de l'historique échouée ({str(e)[:80]})"


def _alpaca_par_chemin():
    """Repli : construire l'adaptateur sans passer par `scripts/`.

    Mêmes garde-fous que `run_live._alpaca_ou_rien` — sans clés, pas de courtier ; et
    `AlpacaBroker` force `paper=True` de toute façon. On ne lit QUE l'historique ici :
    aucun ordre ne part de ce module.
    """
    import os
    if not (os.environ.get("ALPACA_API_KEY") and os.environ.get("ALPACA_API_SECRET")):
        return None, "aucune clé Alpaca dans l'environnement — rien à lire"
    try:
        from packages.execution.alpaca_broker import AlpacaBroker
        return AlpacaBroker(), ""
    except Exception as e:  # noqa: BLE001
        return None, f"adaptateur Alpaca indisponible ({str(e)[:80]})"
