"""Serveur **MCP TradingView** — expose des outils graphiques/quant à l'agent IA.

Deux modes, MÊME registre d'outils (DRY) :
  • SDK officiel `mcp` si installé (`pip install mcp`) → transport stdio standard.
  • Sinon REPLI JSON-RPC 2.0 sur stdio (messages délimités par newline) — compatible MCP de base
    (initialize / tools/list / tools/call), aucune dépendance externe.

Outils exposés :
  - plot_signal_on_chart   : marqueurs ▲▼ (journal trades réel/paper, net de frais) sur le chart.
  - overlay_risk_bands     : cônes VaR/EVT / no-trade bands (bornes haute/basse).
  - set_blackout_zones     : zones verticales de blackout (résultats SEC EDGAR / FMP).
  - generate_pine_script   : preset YAML → Pine Script v5 (cross-validation).
  - fetch_tv_technical_alerts : alertes TV (webhook) → veto/kill-switch risk-engine.

Gestion d'erreurs : chaque handler est encapsulé ; toute exception → {"error": "..."} (jamais de
crash du serveur). Repli synthétique documenté côté `fetch_tv_technical_alerts` (drop vide → []).
"""

from __future__ import annotations

import json
import sys
from typing import Any, Callable

from packages.mcp_tradingview.alerts import fetch_tv_technical_alerts, to_risk_veto
from packages.mcp_tradingview.models import BlackoutZone, ChartMarker, RiskBand
from packages.mcp_tradingview.pine import generate_pine_script
from packages.mcp_tradingview.store import OverlayStore

_STORE = OverlayStore()
_PROTOCOL = "2024-11-05"
_SERVER_INFO = {"name": "quant-tradingview", "version": "0.1.0"}


# ─────────────────────────── Handlers (purs, testables) ───────────────────────────
def _markers_from_args(args: dict) -> list[ChartMarker]:
    """Construit les marqueurs depuis `markers=[{time,side,price,text}]` OU des listes parallèles
    `timestamps`/`prices`/`sides`."""
    if args.get("markers"):
        return [ChartMarker(time=m.get("time", ""), side=str(m.get("side", "")).lower(),
                            price=m.get("price"), text=m.get("text", "")) for m in args["markers"]]
    ts = args.get("timestamps") or []
    px = args.get("prices") or []
    sides = args.get("sides") or []
    out: list[ChartMarker] = []
    for i, t in enumerate(ts):
        out.append(ChartMarker(time=t, side=str(sides[i]).lower() if i < len(sides) else "buy",
                               price=px[i] if i < len(px) else None))
    return out


def _h_plot_signal(args: dict) -> dict:
    ticker = args.get("ticker", "")
    markers = _markers_from_args(args)
    if not markers:
        return {"error": "aucun marqueur (fournir 'markers' ou 'timestamps'+'sides')"}
    saved = _STORE.set_markers(ticker, markers, source=args.get("source", "mcp"))
    return {"ok": True, "ticker": saved["ticker"], "n_markers": len(saved.get("markers", []))}


def _h_overlay_bands(args: dict) -> dict:
    ticker = args.get("ticker", "")
    times = args.get("timestamps") or args.get("times") or []
    up = args.get("upper_band") or args.get("upper") or []
    lo = args.get("lower_band") or args.get("lower") or []
    n = min(len(times), len(up), len(lo))
    if n == 0:
        return {"error": "fournir des listes parallèles timestamps/upper_band/lower_band non vides"}
    bands = [RiskBand(time=times[i], upper=up[i], lower=lo[i]) for i in range(n)]
    saved = _STORE.set_bands(ticker, bands, source=args.get("source", "mcp"))
    return {"ok": True, "ticker": saved["ticker"], "n_bands": len(saved.get("bands", []))}


def _h_set_blackouts(args: dict) -> dict:
    ticker = args.get("ticker", "")
    zones = [BlackoutZone(start=z.get("start", ""), end=z.get("end", ""), label=z.get("label", "blackout"))
             for z in (args.get("zones") or [])]
    if not zones:
        return {"error": "fournir 'zones'=[{start,end,label}]"}
    saved = _STORE.set_blackouts(ticker, zones, source=args.get("source", "mcp"))
    return {"ok": True, "ticker": saved["ticker"], "n_zones": len(saved.get("blackouts", []))}


def _h_generate_pine(args: dict) -> dict:
    pine = generate_pine_script(args.get("strategy_name", "preset"), args.get("yaml_config"))
    return {"ok": True, "language": "pine_v5", "pine": pine}


def _h_fetch_alerts(args: dict) -> dict:
    alerts = fetch_tv_technical_alerts()
    veto = to_risk_veto(alerts)
    return {"ok": True, "alerts": [a.to_dict() for a in alerts], "risk": veto}


def _h_auto_risk_bands(args: dict) -> dict:
    """Calcule le cône VaR/EVT depuis les prix RÉELS (via l'API) et l'écrit comme overlay.
    Sans ticker → traite tous les titres détenus. Découplé : lit l'API, n'importe pas le cœur."""
    from packages.mcp_tradingview.risk_overlays import Z_VAR95, Z_VAR99, populate_from_api
    z = Z_VAR99 if str(args.get("var", "95")) in ("99", "var99") else Z_VAR95
    res = populate_from_api(
        base_url=args.get("base_url", "http://localhost:8000"),
        tickers=[args["ticker"]] if args.get("ticker") else None,
        z=z, lookback=int(args.get("lookback", 21)), evt_mult=float(args.get("evt_mult", 1.15)))
    return res


# ─────────────────────────── Registre d'outils ───────────────────────────
TOOLS: dict[str, dict[str, Any]] = {
    "plot_signal_on_chart": {
        "description": "Projette des marqueurs achat/vente ▲▼ (journal de trades réel/paper, net de "
                       "frais) sur le graphique d'un ticker.",
        "inputSchema": {"type": "object", "required": ["ticker"], "properties": {
            "ticker": {"type": "string"},
            "markers": {"type": "array", "items": {"type": "object"}},
            "timestamps": {"type": "array", "items": {"type": "string"}},
            "prices": {"type": "array", "items": {"type": "number"}},
            "sides": {"type": "array", "items": {"type": "string", "enum": ["buy", "sell"]}}}},
        "handler": _h_plot_signal,
    },
    "overlay_risk_bands": {
        "description": "Trace un cône de risque (VaR/EVT dynamique, no-trade band, vol cone) : bornes "
                       "haute et basse par date.",
        "inputSchema": {"type": "object", "required": ["ticker", "timestamps", "upper_band", "lower_band"],
                        "properties": {
            "ticker": {"type": "string"},
            "timestamps": {"type": "array", "items": {"type": "string"}},
            "upper_band": {"type": "array", "items": {"type": "number"}},
            "lower_band": {"type": "array", "items": {"type": "number"}}}},
        "handler": _h_overlay_bands,
    },
    "set_blackout_zones": {
        "description": "Trace des zones verticales de blackout (fenêtres de résultats trimestriels "
                       "SEC EDGAR / FMP) sur le graphique.",
        "inputSchema": {"type": "object", "required": ["ticker", "zones"], "properties": {
            "ticker": {"type": "string"},
            "zones": {"type": "array", "items": {"type": "object"}}}},
        "handler": _h_set_blackouts,
    },
    "generate_pine_script": {
        "description": "Traduit un preset YAML (qualité, risk-parity ERC, DD-target, no-trade band) en "
                       "Pine Script v5 pour cross-validation sur TradingView.",
        "inputSchema": {"type": "object", "required": ["strategy_name"], "properties": {
            "strategy_name": {"type": "string"},
            "yaml_config": {"type": ["object", "string"]}}},
        "handler": _h_generate_pine,
    },
    "fetch_tv_technical_alerts": {
        "description": "Remonte les alertes de marché TradingView (webhook) et les mappe en décision "
                       "risk-engine (veto/kill-switch, facteur de réduction d'exposition).",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": _h_fetch_alerts,
    },
    "auto_risk_bands": {
        "description": "Calcule AUTOMATIQUEMENT le cône de VaR/EVT depuis les prix réels (via l'API du "
                       "terminal) et le projette sur le(s) graphique(s). Sans 'ticker' → tous les titres détenus.",
        "inputSchema": {"type": "object", "properties": {
            "ticker": {"type": "string"},
            "var": {"type": "string", "enum": ["95", "99"]},
            "lookback": {"type": "integer"},
            "evt_mult": {"type": "number"}}},
        "handler": _h_auto_risk_bands,
    },
}


def call_tool(name: str, args: dict | None = None) -> dict:
    """Appelle un outil par son nom, avec encapsulation des erreurs (jamais de crash)."""
    spec = TOOLS.get(name)
    if spec is None:
        return {"error": f"outil inconnu: {name}"}
    try:
        return spec["handler"](args or {})
    except ValueError as e:                              # validation métier → message clair
        return {"error": f"validation: {e}"}
    except Exception as e:  # noqa: BLE001 — robustesse : aucun outil ne doit tuer le serveur
        return {"error": f"erreur interne: {type(e).__name__}: {e}"}


def list_tools() -> list[dict]:
    return [{"name": n, "description": s["description"], "inputSchema": s["inputSchema"]}
            for n, s in TOOLS.items()]


# ─────────────────────────── Transport ───────────────────────────
def _run_with_sdk() -> bool:
    """Lance le serveur via le SDK `mcp` officiel si présent. Retourne False si indisponible."""
    try:
        import anyio
        import mcp.types as types
        from mcp.server import Server
        from mcp.server.stdio import stdio_server
    except Exception:  # noqa: BLE001
        return False

    server: Server = Server(_SERVER_INFO["name"])

    @server.list_tools()
    async def _lt() -> list[types.Tool]:  # type: ignore[name-defined]
        return [types.Tool(name=t["name"], description=t["description"], inputSchema=t["inputSchema"])
                for t in list_tools()]

    @server.call_tool()
    async def _ct(name: str, arguments: dict) -> list[types.TextContent]:  # type: ignore[name-defined]
        res = call_tool(name, arguments)
        return [types.TextContent(type="text", text=json.dumps(res, ensure_ascii=False))]

    async def _main() -> None:
        async with stdio_server() as (read, write):
            await server.run(read, write, server.create_initialization_options())

    anyio.run(_main)
    return True


def _run_fallback() -> None:
    """Repli JSON-RPC 2.0 sur stdio (1 message JSON par ligne) — sans dépendance externe."""
    def _send(obj: dict) -> None:
        sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
        sys.stdout.flush()

    sys.stderr.write("[mcp_tradingview] SDK 'mcp' absent → repli JSON-RPC stdio.\n")
    sys.stderr.flush()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        rid, method, params = req.get("id"), req.get("method"), req.get("params") or {}
        if method == "initialize":
            _send({"jsonrpc": "2.0", "id": rid, "result": {
                "protocolVersion": _PROTOCOL, "serverInfo": _SERVER_INFO,
                "capabilities": {"tools": {}}}})
        elif method in ("notifications/initialized", "initialized"):
            continue                                      # notification : pas de réponse
        elif method == "ping":
            _send({"jsonrpc": "2.0", "id": rid, "result": {}})
        elif method == "tools/list":
            _send({"jsonrpc": "2.0", "id": rid, "result": {"tools": list_tools()}})
        elif method == "tools/call":
            res = call_tool(params.get("name", ""), params.get("arguments") or {})
            _send({"jsonrpc": "2.0", "id": rid, "result": {
                "content": [{"type": "text", "text": json.dumps(res, ensure_ascii=False)}],
                "isError": "error" in res}})
        elif rid is not None:
            _send({"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": f"method introuvable: {method}"}})


def main() -> None:
    if not _run_with_sdk():
        _run_fallback()


if __name__ == "__main__":
    main()
