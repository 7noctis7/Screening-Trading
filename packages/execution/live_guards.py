"""Garde-fous du run d'exécution (audit 07/15) — fail-loud, brokers vétés, kill-switch DD réel.

Trois principes, chacun né d'un finding CRITIQUE du comité :
  1. **Inconnu ≠ zéro** : positions/equity illisibles ⇒ le broker est ÉCARTÉ du run
     (l'ancien « détenu=0 prudent » faisait RACHETER tout le portefeuille par-dessus
     l'existant quand l'API positions toussait).
  2. **Fail-loud** : plus jamais de run vert-fantôme — broker mort, clé invalide ou
     lecture KO ⇒ alerte CRITICAL + exit ≠ 0 (le job Actions/launchd devient ROUGE).
  3. **Kill-switch sur l'équité RÉELLE** : le drawdown du compte coupe l'exposition,
     pas seulement les alertes TradingView.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

# Témoin d'observabilité. Import au NIVEAU MODULE, et c'est délibéré : le faire à
# l'intérieur du `try` de `dd_kill_switch` ferait retomber une simple erreur d'import
# dans la branche « check indisponible — non appliqué », c'est-à-dire qu'un défaut
# d'OBSERVATION désarmerait le garde-fou OBSERVÉ. `garde_fous` n'importe que la
# bibliothèque standard : aucun cycle, aucun coût.
from packages.execution.garde_fous import (
    ACTIVE,
    ERREUR,
    KILL_DD,
    UNCALIBRATED,
    noter,
)


def current_values(alpaca, bitmart) -> tuple[dict | None, dict | None]:
    """Valeurs de marché détenues PAR broker. Lecture en échec → **None** (inconnu),
    JAMAIS {} (zéro détenu) — cf. principe 1."""
    def _read(br):
        if not br:
            return {}
        try:
            return {p["symbol"]: float(p.get("market_value", 0) or 0)
                    for p in br.positions_detailed()}
        except Exception as e:  # noqa: BLE001
            print(f"⚠️  lecture des positions {getattr(br, 'name', '?')} échouée "
                  f"({str(e)[:50]}) → broker ÉCARTÉ de ce run (aucun ordre).")
            return None
    return _read(alpaca), _read(bitmart)


APERCU_DEFAUT = 10_000.0


def simule(dry: bool, cli_equity: float | None) -> bool:
    """L'aperçu simule-t-il un portefeuille NEUF, ou décrit-il le compte réel ?

    `--equity` en dry-run veut dire « montre-moi ce que ferait un portefeuille neuf
    de ce capital » : le détenu est alors ignoré à dessein. Sans lui, l'aperçu doit
    lire le compte — afficher « détenu 0 $ » sur un compte plein annonce des achats
    que le run réel ne fera pas, et c'est exactement le mode de défaillance contre
    lequel le principe 1 de ce module a été écrit."""
    return dry and cli_equity is not None


def _apercu(alpaca, bitmart, alp_cap: float, bit_cap: float):
    """Dry-run sur equity réelle : une lecture ratée se replie, ANNONCÉE, jamais
    fatale. Un aperçu n'envoie aucun ordre — le sanctionner comme un run live
    n'aurait pas de sens.

    Le repli couvre AUSSI le broker absent (`alpaca is None`) : sans lui, un capital
    de 0 produit des cibles à 0 et un tableau entier de lignes vides, qui se lit comme
    « le système ne veut rien faire » alors qu'il n'a rien pu lire. Un aperçu qui ne
    décrit pas le compte doit le DIRE, pas le montrer sous forme de zéros."""
    if alp_cap <= 0:
        quoi = "illisible" if alpaca else "non lue (broker non construit)"
        print(f"⚠️  equity Alpaca {quoi} → aperçu sur {APERCU_DEFAUT:,.0f} $ SIMULÉS. "
              "Ce n'est PAS votre compte : ni le capital, ni le détenu.")
        alp_cap = APERCU_DEFAUT
    return alpaca, bitmart, alp_cap, max(bit_cap, 0.0), []


def vet_brokers(alpaca, bitmart, dry: bool, cli_equity: float | None):
    """(alpaca, bitmart, alp_cap, bit_cap, fatal) — équity par compte, brokers morts écartés.

    En LIVE : equity nulle/illisible = broker MORT → écarté + motif `fatal` (l'ancien
    repli 10 000 $ faisait « trader » un broker à clé invalide, run vert à jamais).
    Bitmart sans clés = simple inactivité (normal en cloud), pas une erreur.

    En DRY-RUN : capital IMPOSÉ si `--equity` est donné (simulation), sinon equity
    RÉELLE du compte — cf. `simule`."""
    fatal: list[str] = []
    if simule(dry, cli_equity):
        return alpaca, bitmart, float(cli_equity), 0.0, fatal
    if dry:
        return _apercu(alpaca, bitmart,
                       alpaca.equity() if alpaca else 0.0,
                       bitmart.equity() if bitmart else 0.0)
    alp_cap = alpaca.equity() if alpaca else 0.0
    if alpaca and alp_cap <= 0:
        fatal.append("equity Alpaca nulle/illisible (clé invalide ?) → broker écarté")
        alpaca, alp_cap = None, 0.0
    bit_cap = bitmart.equity() if bitmart else 0.0
    if bitmart and bit_cap <= 0:
        if getattr(bitmart, "_live", lambda: False)():         # clés présentes, equity inconnue
            fatal.append("equity Bitmart nulle/illisible → broker écarté (aucune vente)")
        bitmart, bit_cap = None, 0.0
    return alpaca, bitmart, alp_cap, bit_cap, fatal



# SEUIL ET FENÊTRE DU KILL-SWITCH DRAWDOWN (17/11).
#
# DEUX NOTIONS ÉTAIENT CONFONDUES. Le 01/10 (#425), le regroupement des réglages dans
# `risk.yaml` a branché ce kill-switch sur `max_daily_drawdown_pct: 0.05` — une limite de
# perte JOURNALIÈRE, que la politique de risque (`vault/07_RISK_POLICY.md`) décrit avec un
# « reset quotidien ». Le code, lui, l'appliquait à la baisse depuis le plus haut de TOUT
# l'historique, sans reset. Le seuil effectif est passé de −15 % à −5 % sans que personne
# l'ait décidé. Constaté le 16/11 : drawdown −8,6 %, aucun achat possible.
#
# POURQUOI C'EST UN PIÈGE ET PAS SEULEMENT UN SEUIL STRICT. Le kill-switch bloque les
# achats ; seul ce qui est déjà détenu peut donc faire remonter le compte. Avec 50 % de
# QQQ et le reste en espèces, sortir du blocage exigeait que QQQ remonte d'environ 8 % —
# en marché latéral, le robot pouvait rester figé indéfiniment.
#
# CE QUI EST FAIT. Un paramètre DÉDIÉ (`max_drawdown_pct`, 15 % — la valeur que le code
# portait avant le 01/10 et que `vault/17_UPGRADE/AXE5_EXECUTION.md` documente pour le
# livre) et un plus haut mesuré sur une FENÊTRE GLISSANTE (`drawdown_window_sessions`,
# 63 séances ≈ 3 mois) : un blocage ne peut plus durer plus longtemps que la fenêtre.
# La perte du JOUR reste surveillée par le disjoncteur (`packages/risk/disjoncteur.py`).
DD_LIMIT_DEFAUT = -0.15     # repli si YAML absent/illisible
FENETRE_DD_DEFAUT = 63      # séances (un point d'equity par date)
_FENETRE_MIN = 2


def _chemin_risk_yaml() -> Path:
    """Racine dépôt / config/risk.yaml (packages/execution → parents[2])."""
    return Path(__file__).resolve().parents[2] / "config" / "risk.yaml"


def _portefeuille_yaml(path: Path | None = None) -> dict[str, Any]:
    """Section `portfolio` de risk.yaml, ou {} si absente/illisible."""
    chemin = path if path is not None else _chemin_risk_yaml()
    try:
        from packages.common.config import load_yaml
        data = load_yaml(chemin)
    except Exception:
        try:
            import yaml  # type: ignore
            with chemin.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except Exception:
            return {}
    portfolio = data.get("portfolio") if isinstance(data, dict) else None
    return portfolio if isinstance(portfolio, dict) else {}


def _dd_limit_depuis_yaml(path: Path | None = None) -> float:
    """Lit `max_drawdown_pct` (fraction positive) → seuil négatif pour breach.

    Ex. yaml 0.15 → −0.15. Absent/illisible/≤ 0 → `DD_LIMIT_DEFAUT` (−0.15)."""
    raw = _portefeuille_yaml(path).get("max_drawdown_pct", -DD_LIMIT_DEFAUT)
    try:
        mag = float(raw)
    except (TypeError, ValueError):
        return DD_LIMIT_DEFAUT
    return -abs(mag) if mag > 0 else DD_LIMIT_DEFAUT


def resolve_intraday_dd_limit() -> float:
    """Seuil kill-switch DD : `QUANT_INTRADAY_DD` override si set/non vide, sinon YAML.

    Valeur ENV = fraction de peak-drawdown (négative, ex. −0.15). Défaut sans ENV =
    `config/risk.yaml` `max_drawdown_pct` mappé en négatif (0.15 → −0.15)."""
    raw = os.environ.get("QUANT_INTRADAY_DD")
    if raw is not None and str(raw).strip() != "":
        try:
            return float(raw)
        except (TypeError, ValueError):
            pass
    return _dd_limit_depuis_yaml()


def resolve_dd_window(path: Path | None = None) -> int:
    """Fenêtre du plus haut, en séances : `QUANT_DD_WINDOW`, sinon YAML, sinon 63.

    Une valeur illisible ou < 2 retombe sur le défaut : une faute de frappe ne doit
    ni désarmer le garde-fou ni le rendre permanent."""
    for raw in (os.environ.get("QUANT_DD_WINDOW"),
                _portefeuille_yaml(path).get("drawdown_window_sessions")):
        if raw is None or str(raw).strip() == "":
            continue
        try:
            n = int(raw)
        except (TypeError, ValueError):
            continue
        if n >= _FENETRE_MIN:
            return n
    return FENETRE_DD_DEFAUT


def etat_kill_switch(curve: list[float], limit: float, fenetre: int) -> dict[str, Any]:
    """Décision PURE : drawdown depuis le plus haut des `fenetre` derniers points.

    Ajoute au verdict de `drawdown_breach` la fenêtre, le seuil et `reprise` : la valeur
    du compte au-dessus de laquelle les achats reprennent. Sert au run ET à l'affichage —
    une seule règle, pour que l'écran ne puisse pas dire autre chose que le robot."""
    from packages.portfolio.stress import drawdown_breach
    pts = [float(x) for x in curve if isinstance(x, (int, float)) and x > 0]
    out = drawdown_breach(pts[-max(_FENETRE_MIN, int(fenetre)):], dd_limit=limit)
    out["fenetre"] = int(fenetre)
    out["limit"] = limit
    if out.get("available"):
        out["reprise"] = round(out["peak"] * (1.0 + limit), 2)
    return out


def _courbe(cles: set[str] | None) -> list[float]:
    from packages.execution.equity_history import _load, courbe_comparable
    # `cles` = le périmètre de `total_equity` (QML-024). Sans lui, on somme tout ce que
    # l'historique contient — y compris un solde testnet ou une place absente du jour.
    if cles:
        return courbe_comparable(_load(), set(cles))
    return [sum(v for k, v in h.items() if k != "date" and isinstance(v, (int, float)))
            for h in _load()]


def etat_courant() -> dict[str, Any]:
    """État du kill-switch pour l'AFFICHAGE, sans réseau : historique d'equity seul.

    Le périmètre est celui du dernier point enregistré. Le run, lui, ajoute le relevé
    courtier du moment : les deux peuvent différer de quelques heures de séance."""
    try:
        from packages.execution.equity_history import _load
        hist = _load()
        dernier = hist[-1] if hist else {}
        cles = {k for k, v in dernier.items()
                if k != "date" and isinstance(v, (int, float)) and v > 0}
        out = etat_kill_switch(_courbe(cles), resolve_intraday_dd_limit(), resolve_dd_window())
    except Exception as e:  # noqa: BLE001 — un affichage ne doit jamais casser la page
        # Le message reste dans le journal du serveur : un texte d'exception renvoyé par
        # l'API peut exposer des chemins ou une trace (alerte CodeQL, PR #467).
        print(f"· kill-switch (affichage) : état indisponible ({type(e).__name__})")
        return {"available": False, "raison": "état indisponible"}
    out["depuis"] = dernier.get("date")
    return out


def dd_kill_switch(total_equity: float, bus, alert_engine,
                   observateur: object | None = None, cles: set[str] | None = None) -> float:
    """Kill-switch sur le DRAWDOWN RÉEL du compte (principe 3). Lit l'historique
    d'equity persisté + le point du jour ; baisse depuis le plus haut des
    `resolve_dd_window()` dernières séances ≤ seuil (`QUANT_INTRADAY_DD` override, sinon
    risk.yaml `max_drawdown_pct` 15 % → −0.15) → 0.0 = AUCUN ACHAT (rien n'est vendu
    d'office : `run_live.cible_sous_garde`, QML-007). Historique court/indispo → 1.0.

    `observateur` ne change RIEN à la décision : il reçoit l'état pour que le rapport
    des garde-fous distingue les trois 1.0 que cette fonction rend — « rien à couper »,
    « historique trop court » et « le contrôle a planté ». Ces trois-là se ressemblent
    à l'écran et n'ont pas du tout le même sens."""
    limit = resolve_intraday_dd_limit()
    try:
        curve = _courbe(cles)
        if total_equity > 0:
            curve.append(total_equity)
        out = etat_kill_switch(curve, limit, resolve_dd_window())
        if not out.get("available"):
            noter(observateur, KILL_DD, etat=UNCALIBRATED, motif="historique_insuffisant")
            return 1.0
        if not out.get("breach"):
            noter(observateur, KILL_DD, etat=ACTIVE)
            return 1.0
        _signaler(out, limit, bus, alert_engine)
        noter(observateur, KILL_DD, etat=ACTIVE, declenche=True, motif="drawdown")
        return 0.0
    except Exception as e:  # noqa: BLE001 — le check ne doit jamais BLOQUER un run sain
        print(f"· kill-switch DD réel : check indisponible ({str(e)[:50]}) — non appliqué.")
        noter(observateur, KILL_DD, etat=ERREUR, motif="check_indisponible")
        return 1.0


def _signaler(out: dict[str, Any], limit: float, bus: Any, alert_engine: Any) -> None:
    msg = (f"drawdown réel {out['drawdown']*100:.1f}% ≤ seuil {limit*100:.0f}% "
           f"(pic {out['peak']} sur {out['fenetre']} séances, dernier {out['last']} ; "
           f"reprise des achats au-dessus de {out['reprise']})")
    print(f"⛔ KILL-SWITCH DRAWDOWN RÉEL : {msg} → achats BLOQUÉS "
          "(aucune vente forcée, cf. QML-007).")
    if bus:
        from packages.common.event_bus import Topic
        bus.publish(Topic.KILL_SWITCH, {"drawdown": out["drawdown"]})
    if alert_engine:
        from packages.alerts import Alert, Severity
        alert_engine.emit(Alert("risk", Severity.CRITICAL,
                                f"Kill-switch drawdown réel déclenché : {msg}",
                                dedup_key="risk:dd_kill_switch"))


def fail_loud(reasons: list[str], alert_engine, code: int) -> None:
    """Échec BRUYANT (principe 2) : alerte CRITICAL + exit ≠ 0."""
    for m in reasons:
        print(f"⛔ {m}")
    if alert_engine:
        try:
            from packages.alerts import Alert, Severity
            alert_engine.emit(Alert("execution", Severity.CRITICAL,
                                    "run_live en échec : " + " · ".join(reasons)[:180],
                                    dedup_key="execution:fail_loud"))
        except Exception:  # noqa: BLE001
            pass
    raise SystemExit(code)
