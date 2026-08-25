"""Courtier Interactive Brokers — VERROUILLÉ SUR COMPTE DÉMO (paper).

Ce module ne peut pas passer d'ordre sur un compte IBKR réel. Ce n'est pas une consigne, c'est
une contrainte de code : trois verrous indépendants, et il suffit qu'UN SEUL refuse pour que la
connexion soit rompue avant le premier ordre.

  1. LE PORT. TWS et IB Gateway écoutent sur des ports différents selon le compte : 7497/4002
     pour le papier, 7496/4001 pour le réel. Un port réel est refusé d'emblée.

  2. L'IDENTIFIANT DE COMPTE — et c'est LE verrou qui compte. IBKR préfixe les comptes papier
     par `DU` (`DF` pour un conseiller papier) et les comptes réels par `U` ou `F`. Le port est
     un INDICE : il se reconfigure dans les réglages de TWS, et se fier à lui seul donnerait un
     garde-fou qu'on croit armé. L'identifiant renvoyé par la passerelle, lui, ne se falsifie
     pas depuis le poste client. On le lit APRÈS connexion, et on se déconnecte si ce n'est pas
     un compte démo.

  3. L'OPT-IN EXPLICITE. `QUANT_IBKR_ENABLE=1` est requis. Une clé oubliée ne doit pas suffire à
     brancher un courtier.

CE QUE CE MODULE NE FAIT PAS, et n'est pas destiné à faire : il n'y a aucun paramètre, aucune
variable d'environnement, aucun argument qui autorise un compte réel. Pour passer en réel, il
faudrait modifier ce fichier — c'est-à-dire un geste visible, revu, tracé dans l'historique git.

Dépendance OPTIONNELLE : `ib_insync` (pip install ib_insync) et une instance TWS/IB Gateway
lancée en mode papier. Absente → le courtier se déclare non configuré, rien ne casse.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from packages.core.models import Side

# Ports d'écoute standards d'IBKR. Le mapping est celui de la documentation TWS/Gateway.
PORTS_DEMO: dict[int, str] = {7497: "TWS (papier)", 4002: "IB Gateway (papier)"}
PORTS_REELS: dict[int, str] = {7496: "TWS (RÉEL)", 4001: "IB Gateway (RÉEL)"}

# Préfixes de comptes IBKR. `DU`/`DF` = démo ; `U`/`F` = réel. L'ordre du test compte : « DU »
# commence par « D », pas par « U » — tester `startswith("U")` en premier laisserait passer.
PREFIXES_DEMO = ("DU", "DF")

PORT_DEFAUT = 7497
HOTE_DEFAUT = "127.0.0.1"


class CompteReelRefuse(RuntimeError):
    """Levée dès qu'un élément indique un compte réel. Jamais rattrapée silencieusement."""


@dataclass(frozen=True)
class Verdict:
    """Résultat d'un contrôle, avec son motif — un refus doit toujours dire pourquoi."""
    demo: bool
    motif: str


def verifier_port(port: int) -> Verdict:
    """Premier verrou, et le plus faible : le port n'est qu'un indice de configuration."""
    p = int(port)
    if p in PORTS_REELS:
        return Verdict(False, f"port {p} = {PORTS_REELS[p]} — ce module ne parle qu'au papier")
    if p in PORTS_DEMO:
        return Verdict(True, f"port {p} = {PORTS_DEMO[p]}")
    # Un port inconnu n'est PAS présumé sûr : il n'est simplement pas disqualifiant. Le verrou
    # décisif reste l'identifiant de compte, contrôlé après connexion.
    return Verdict(True, f"port {p} non standard — l'identifiant de compte tranchera")


def verifier_compte(identifiant: str) -> Verdict:
    """Verrou décisif. `DU…`/`DF…` = démo. Tout le reste est refusé, y compris l'inconnu.

    L'inconnu est refusé délibérément : un identifiant vide ou illisible signifie qu'on n'a pas
    su lire à quel compte on parle. Passer un ordre dans ce cas serait parier sur une inconnue.
    """
    ident = (identifiant or "").strip().upper()
    if not ident:
        return Verdict(False, "identifiant de compte vide — impossible de savoir à quel compte "
                              "on parle, donc aucun ordre")
    if ident.startswith(PREFIXES_DEMO):
        return Verdict(True, f"compte {ident} — préfixe démo")
    return Verdict(False, f"compte {ident} — ce n'est PAS un compte démo IBKR "
                          f"(les comptes papier commencent par {' ou '.join(PREFIXES_DEMO)})")


def configuree() -> bool:
    """IBKR est-il activé ? Opt-in explicite, jamais déduit de la présence d'une dépendance."""
    return os.environ.get("QUANT_IBKR_ENABLE", "") == "1"


def _env_port() -> int:
    try:
        return int(os.environ.get("QUANT_IBKR_PORT", "") or PORT_DEFAUT)
    except ValueError:
        return PORT_DEFAUT


class IBKRBroker:
    """Même interface que `AlpacaBroker` et `SimBroker` — parité backtest ↔ papier.

    `connecteur` est injectable pour les tests : il doit exposer `connect`, `managedAccounts`,
    `accountSummary`, `positions`, `placeOrder`, `disconnect`. En production c'est `ib_insync.IB`.
    """

    nom = "IBKR"
    is_paper = True          # invariant de classe : ce courtier n'a pas d'autre mode

    def __init__(self, hote: str | None = None, port: int | None = None,
                 client_id: int = 17, connecteur=None, dry_run: bool = False) -> None:
        self.hote = hote or os.environ.get("QUANT_IBKR_HOST", HOTE_DEFAUT)
        self.port = int(port if port is not None else _env_port())
        self.dry_run = dry_run
        self.compte = ""

        v_port = verifier_port(self.port)
        if not v_port.demo:
            raise CompteReelRefuse(v_port.motif)
        self.motifs = [v_port.motif]

        self._ib = connecteur if connecteur is not None else self._connecteur_reel()
        self._ib.connect(self.hote, self.port, clientId=client_id)

        comptes = list(self._ib.managedAccounts() or [])
        self.compte = comptes[0] if comptes else ""
        v_compte = verifier_compte(self.compte)
        self.motifs.append(v_compte.motif)
        if not v_compte.demo:
            # Se déconnecter AVANT de lever : une session laissée ouverte sur un compte réel
            # serait précisément ce qu'on cherche à empêcher.
            try:
                self._ib.disconnect()
            finally:
                raise CompteReelRefuse(v_compte.motif)

    @staticmethod
    def _connecteur_reel():
        try:
            from ib_insync import IB
        except ImportError as e:  # noqa: BLE001
            raise RuntimeError("ib_insync absent — `pip install ib_insync`, puis lancer TWS ou "
                               "IB Gateway en mode PAPIER (port 7497 ou 4002)") from e
        return IB()

    # --- lecture ------------------------------------------------------------------------

    def equity(self) -> float:
        for ligne in self._ib.accountSummary(self.compte) or []:
            if getattr(ligne, "tag", "") == "NetLiquidation":
                try:
                    return float(getattr(ligne, "value", 0) or 0)
                except (TypeError, ValueError):
                    return 0.0
        return 0.0

    def positions_detailed(self) -> list[dict]:
        """Positions enrichies pour l'interface. Même forme que les autres courtiers."""
        out = []
        for p in self._ib.positions(self.compte) or []:
            contrat = getattr(p, "contract", None)
            qte = float(getattr(p, "position", 0) or 0)
            pru = float(getattr(p, "avgCost", 0) or 0)
            out.append({"symbol": getattr(contrat, "symbol", "") or "",
                        "broker": self.nom,
                        "side": "long" if qte >= 0 else "short",
                        "qty": abs(qte), "avg_price": pru,
                        "price": 0.0, "market_value": abs(qte) * pru,
                        "pnl": 0.0, "pnl_pct": 0.0})
        return out

    def orders(self, limit: int = 100) -> list[dict]:
        """Ordres exécutés. Vide plutôt qu'une exception : l'absence d'historique ne doit pas
        priver le site de la poche IBKR."""
        try:
            return [{"symbol": getattr(getattr(t, "contract", None), "symbol", ""),
                     "broker": self.nom,
                     "side": str(getattr(getattr(t, "order", None), "action", "")).lower(),
                     "qty": float(getattr(getattr(t, "order", None), "totalQuantity", 0) or 0)}
                    for t in (self._ib.trades() or [])][:limit]
        except Exception:  # noqa: BLE001
            return []

    def open_orders(self, limit: int = 100) -> list[dict]:
        try:
            return [{"symbol": getattr(getattr(o, "contract", None), "symbol", ""),
                     "broker": self.nom}
                    for o in (self._ib.openOrders() or [])][:limit]
        except Exception:  # noqa: BLE001
            return []

    # --- écriture -----------------------------------------------------------------------

    def _garde(self) -> None:
        """Re-contrôle AVANT chaque ordre. La vérification à la connexion ne suffit pas : une
        passerelle peut être relancée sur un autre compte pendant que le processus tourne."""
        v = verifier_compte(self.compte)
        if not v.demo:
            raise CompteReelRefuse(v.motif)

    def submit_notional(self, symbol: str, side: Side, notional: float):
        """Ordre marché par montant. IBKR raisonne en QUANTITÉ : la conversion exige un prix,
        que ce module ne récupère pas encore. Il refuse donc explicitement plutôt que d'envoyer
        une quantité approximative — un ordre faux est pire qu'un ordre absent."""
        self._garde()
        raise NotImplementedError(
            "IBKR raisonne en quantité, pas en montant. La conversion notionnel → quantité "
            "exige un prix de référence : à brancher sur le flux de cotation avant d'exécuter. "
            "Le courtier est LISIBLE (equity, positions) mais pas encore ÉMETTEUR.")

    def close_position(self, symbol: str) -> bool:
        self._garde()
        raise NotImplementedError(
            "sortie IBKR non branchée — voir `submit_notional`. Ne pas contourner : une sortie "
            "partielle laisserait un résidu que la bande d'inaction rendrait immortel.")

    def deconnecter(self) -> None:
        try:
            self._ib.disconnect()
        except Exception:  # noqa: BLE001
            pass

    # --- diagnostic ---------------------------------------------------------------------

    def diagnostic(self) -> dict:
        """État lisible pour l'interface et les journaux. Ne renvoie jamais d'identifiant complet."""
        masque = (self.compte[:4] + "…") if len(self.compte) > 4 else self.compte
        return {"broker": self.nom, "demo": True, "compte": masque,
                "hote": self.hote, "port": self.port,
                "verrous": list(self.motifs),
                "emetteur": False,
                "note": "lecture seule : equity et positions. L'émission d'ordres est refusée "
                        "tant que la conversion notionnel → quantité n'est pas branchée."}
