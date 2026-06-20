"""Calendrier d'ÉVÉNEMENTS RÉELS : résultats trimestriels (BPA/revenu estimés & annoncés) et
IPOs US (S-1/S-1/A via SEC EDGAR + enrichissement FMP). Aucune donnée synthétique : sources
publiques (yfinance, Financial Modeling Prep si clé, SEC EDGAR). Réseau isolé → renvoie [] proprement."""

from packages.events.earnings import earnings_for
from packages.events.ipos import upcoming_ipos

__all__ = ["earnings_for", "upcoming_ipos"]
