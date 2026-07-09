"""Données de référence pures du snapshot (secteurs/thèmes/GICS) — extraites de `snapshot.py`.

Tranche 1 du dé-god-objectage (`snapshot.py` 2536 l → modules). AUCUNE logique ici : uniquement
des constantes reproductibles (paniers thématiques + biais drift/vol synthétiques, mapping GICS).
Importées telles quelles par `snapshot.py` → comportement strictement inchangé.
"""

from __future__ import annotations

# Thèmes structurels (4ᵉ révolution industrielle, K. Schwab) + secteurs classiques.
# Chaque thème : panier de proxies + biais de drift/vol thématique (synthétique, reproductible).
SECTORS = {
    # --- 4ᵉ révolution industrielle --- (drifts ANNUELS modérés → réalistes sur ~4,6 ans)
    "Intelligence artificielle":     {"tickers": ["NVDA", "MSFT", "GOOGL", "PLTR", "SNOW"], "drift": 0.16, "vol": 0.24},
    "Semi-conducteurs":              {"tickers": ["NVDA", "TSM", "AVGO", "AMD", "ASML"],    "drift": 0.15, "vol": 0.26},
    "Crypto & Blockchain":           {"tickers": ["COIN", "MSTR", "MARA", "RIOT", "HUT"],   "drift": 0.14, "vol": 0.45},
    "Cloud & Datacenters":           {"tickers": ["MSFT", "AMZN", "GOOGL", "EQIX", "DLR"],  "drift": 0.12, "vol": 0.18},
    "Cybersécurité":                 {"tickers": ["CRWD", "PANW", "ZS", "FTNT", "S"],       "drift": 0.11, "vol": 0.22},
    "Espace & Défense":              {"tickers": ["LMT", "RTX", "BA", "NOC", "RKLB"],       "drift": 0.08, "vol": 0.20},
    "Robotique & Automatisation":    {"tickers": ["ABB", "ISRG", "ROK", "TER", "FANUY"],    "drift": 0.07, "vol": 0.18},
    "Véhicules électriques":         {"tickers": ["TSLA", "RIVN", "LCID", "BYDDY", "NIO"],  "drift": 0.02, "vol": 0.40},
    "Fintech & Paiements":           {"tickers": ["V", "MA", "PYPL", "SQ", "ADYEY"],        "drift": 0.05, "vol": 0.20},
    "Biotech & Génomique":           {"tickers": ["LLY", "VRTX", "REGN", "CRSP", "MRNA"],   "drift": 0.02, "vol": 0.24},
    "Énergie propre & Transition":   {"tickers": ["ENPH", "FSLR", "NEE", "PLUG", "BE"],     "drift": -0.04, "vol": 0.30},
    # --- secteurs GICS classiques ---
    "Énergie (fossile)":             {"tickers": ["XOM", "CVX", "COP", "SLB", "EOG"],       "drift": 0.06, "vol": 0.18},
    "Industrie":                     {"tickers": ["CAT", "GE", "HON", "UPS", "DE"],         "drift": 0.05, "vol": 0.16},
    "Conso. de base":                {"tickers": ["PG", "KO", "PEP", "COST", "WMT"],        "drift": 0.04, "vol": 0.12},
    "Finance":                       {"tickers": ["JPM", "BAC", "GS", "MS", "BLK"],         "drift": 0.03, "vol": 0.18},
    "Services publics":              {"tickers": ["DUK", "SO", "AEP", "D", "EXC"],          "drift": 0.01, "vol": 0.12},
}

# drift/vol par secteur (sert à générer les trajectoires synthétiques cohérentes)
SECTOR_DV = {name: (cfg["drift"], cfg.get("vol", 0.18)) for name, cfg in SECTORS.items()}
SECTOR_DV.update({
    "Santé": (0.08, 0.16), "Conso. discrétionnaire": (0.10, 0.20),
    "Communication": (0.09, 0.18), "Matériaux": (0.05, 0.20), "Immobilier": (0.02, 0.18),
    "Actions diverses": (0.06, 0.20), "ETF": (0.07, 0.13), "Indices": (0.07, 0.12),
    "Forex": (0.00, 0.07), "Commodités": (0.05, 0.20),
})
# ticker → thème (4ᵉ révolution) pour étiqueter les actions des seeds européens/US
THEME_TICKERS = {t: name for name, cfg in SECTORS.items() for t in cfg["tickers"]}
# GICS (anglais, seeds CAC40/AEX) → bucket interne
GICS_MAP = {
    "Information Technology": "Cloud & Datacenters", "Health Care": "Santé",
    "Financials": "Finance", "Consumer Discretionary": "Conso. discrétionnaire",
    "Consumer Staples": "Conso. de base", "Industrials": "Industrie",
    "Energy": "Énergie (fossile)", "Utilities": "Services publics",
    "Materials": "Matériaux", "Communication Services": "Communication",
    "Real Estate": "Immobilier",
}
