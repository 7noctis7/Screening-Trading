"""Connecteur **MCP TradingView** (plug-and-play) — synergie bidirectionnelle IA ↔ terminal.

Package INDÉPENDANT : il n'importe RIEN du cœur de trading et n'est importé par aucun module du
cœur (aucune pollution). Le pont vers le navigateur est un *overlay store* (JSON local) lu par
l'API/front ; les alertes TV arrivent par webhook et n'alimentent QUE le risk-engine en live.

⚠️ POINT-IN-TIME : overlays et alertes sont **affichage / live uniquement**. Ils ne sont JAMAIS
lus par le moteur de backtest ni par l'entraînement ML (CV purgée + embargo) → aucune fuite.

Sous-modules :
- models   : dataclasses typées (ChartMarker, RiskBand, BlackoutZone, Overlay) + validation.
- store    : OverlayStore (écriture atomique JSON) — pont MCP → API/front.
- pine     : génération Pine Script v5 depuis un preset YAML (cross-validation).
- alerts   : lecture des alertes TV (webhook/polling) → veto risk-engine.
- server   : serveur MCP (SDK `mcp` si présent, sinon repli JSON-RPC stdio).
"""

from packages.mcp_tradingview.models import BlackoutZone, ChartMarker, Overlay, RiskBand
from packages.mcp_tradingview.pine import generate_pine_script
from packages.mcp_tradingview.store import OverlayStore

__all__ = ["BlackoutZone", "ChartMarker", "Overlay", "RiskBand", "OverlayStore", "generate_pine_script"]
