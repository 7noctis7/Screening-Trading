"""Constantes partagées par les morceaux du snapshot.

Extrait TEL QUEL de `apps/api/snapshot.py` le 31/10 (règle des 400 lignes par fichier) : le
texte des définitions n'a pas changé. `apps/api/snapshot.py` reste la façade et ré-exporte
chaque nom, donc `from apps.api.snapshot import X` fonctionne comme avant.
"""

from __future__ import annotations

import os as _os_hist
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
_NETWORK_KINDS = {"wikipedia", "ishares_holdings", "nasdaq_trader", "coingecko"}

# Profondeur d'historique (jours calendaires). Défaut ≈ depuis 2015 (~11 ans) si ta base le permet ;
# sinon la fenêtre est tronquée à l'historique réel disponible. Surchargeable : QUANT_HISTORY_DAYS.
_HISTORY_DAYS = int(_os_hist.environ.get("QUANT_HISTORY_DAYS", "4015"))
