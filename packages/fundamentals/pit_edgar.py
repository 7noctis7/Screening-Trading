"""Faits SEC visibles à une date : `acceptanceDateTime`, sinon `filed`.

`period` / `end` est la fin d'exercice, pas le moment où le marché a su.
L'utiliser comme date de connaissance avance le score de 30 à 90 jours.

- `acceptanceDateTime` (fait, ou index par numéro d'accession) → `EXACT` ;
- `filed` seul → `INFERRED_LAG` (jour de dépôt, pas l'heure) ;
- rien → `UNKNOWN`, exclu dès qu'un `as_of` est demandé.
"""

from __future__ import annotations

_ANNUELS = ("10-K", "20-F")


def horodatage(fact: dict, acceptance: dict | None = None) -> tuple[str | None, str]:
    """(knowledge_time, kt_quality) d'une observation XBRL."""
    accn = str(fact.get("accn") or "")
    if acceptance and accn and accn in acceptance:
        return str(acceptance[accn])[:19], "EXACT"
    brut = fact.get("acceptanceDateTime")
    if isinstance(brut, str) and len(brut) >= 10:
        return brut[:19], "EXACT"
    filed = fact.get("filed")
    if isinstance(filed, str) and len(filed) >= 10:
        return filed[:10], "INFERRED_LAG"
    return None, "UNKNOWN"


def visible(fact: dict, as_of: str | None, acceptance: dict | None = None) -> bool:
    """Sans `as_of`, on ne filtre pas. Avec, un fait UNKNOWN ou trop tardif sort."""
    if as_of is None:
        return True
    kt, qualite = horodatage(fact, acceptance)
    if qualite == "UNKNOWN" or kt is None:
        return False
    return kt[:10] <= as_of[:10]


def _unites(facts: dict, concept: str) -> list[dict]:
    node = (facts.get("us-gaap", {}).get(concept)
            or facts.get("dei", {}).get(concept) or {})
    units = node.get("units", {})
    return (units.get("USD") or units.get("USD/shares") or units.get("shares")
            or next(iter(units.values()), []))


def choisir(facts: dict, concepts: tuple[str, ...], *, as_of: str | None = None,
            acceptance: dict | None = None) -> tuple[float | None, str | None, str]:
    """(valeur, knowledge_time, kt_quality). Annuel d'abord, sinon le plus récent."""
    for concept in concepts:
        pool = [x for x in _unites(facts, concept)
                if x.get("val") is not None and visible(x, as_of, acceptance)]
        if not pool:
            continue
        annuel = [x for x in pool if x.get("form") in _ANNUELS and x.get("fp") == "FY"]
        pris = max(annuel or pool,
                   key=lambda x: (x.get("end") or "", x.get("filed") or ""))
        kt, qualite = horodatage(pris, acceptance)
        return float(pris["val"]), kt, qualite
    return None, None, "UNKNOWN"


def mesures(facts: dict, as_of: str | None = None,
           acceptance: dict | None = None) -> dict:
    """Valeurs connues à `as_of`, plus l'horodatage du CA ou du résultat."""
    specs = {
        "revenue": ("RevenueFromContractWithCustomerExcludingAssessedTax",
                    "Revenues", "SalesRevenueNet"),
        "net_income": ("NetIncomeLoss",),
        "ebit": ("OperatingIncomeLoss",),
        "dep": ("DepreciationDepletionAndAmortization",
                "DepreciationAmortizationAndAccretionNet"),
        "equity": ("StockholdersEquity",
                   "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"),
        "debt": ("LongTermDebtNoncurrent", "LongTermDebt"),
        "cash": ("CashAndCashEquivalentsAtCarryingValue",
                 "CashCashEquivalentsAndShortTermInvestments"),
        "gross": ("GrossProfit",),
        "shares": ("CommonStockSharesOutstanding",
                   "EntityCommonStockSharesOutstanding"),
    }
    out: dict = {}
    kts: list[str] = []
    quals: list[str] = []
    for nom, concepts in specs.items():
        val, kt, qual = choisir(facts, concepts, as_of=as_of, acceptance=acceptance)
        out[nom] = val
        if nom in ("revenue", "net_income") and kt:
            kts.append(kt)
            quals.append(qual)
    out["knowledge_time"] = max(kts) if kts else None
    if "EXACT" in quals:
        out["kt_quality"] = "EXACT"
    elif quals:
        out["kt_quality"] = quals[0]
    else:
        out["kt_quality"] = "UNKNOWN"
    return out
