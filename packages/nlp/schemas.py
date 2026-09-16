"""Le contrat de sortie du LLM — un schéma, pas une expression régulière.

POURQUOI PAS DE PARSING ARTISANAL. Un LLM à qui l'on demande « réponds en JSON » répond en
JSON la plupart du temps, puis un jour ajoute « Voici l'analyse : » devant, ou une virgule
finale, ou du texte après l'accolade. Une expression régulière qui marche neuf fois sur dix
produit un signal faux une fois sur dix, et RIEN ne le signale — le pire régime possible
pour une donnée qui entre dans une décision. On impose donc le schéma au modèle (sortie
structurée) ET on le revalide à l'arrivée.

DEUX OBJETS DISTINCTS, ET LA DISTINCTION COMPTE
  · `SCHEMA` — ce qu'on DEMANDE au modèle. Cinq champs, et rien de plus.
  · `SignalNLP` — ce qu'on CONSERVE. Les cinq champs, plus une provenance que nous seuls
    connaissons : quel modèle, quelle version d'invite, était-ce un repli.
Laisser le modèle renseigner sa propre provenance serait lui demander de se noter lui-même.

PYDANTIC EST OPTIONNEL. Le cœur du dépôt ne déclare aucune dépendance et la CI installe un
environnement allégé. La validation est donc en bibliothèque standard ; `modele_pydantic()`
n'existe que pour l'API, quand pydantic est là. Un test vérifie que les deux définitions ne
divergent pas — c'est le seul garde-fou qui tienne contre une duplication.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

SENTIMENTS = ("BULLISH", "BEARISH", "NEUTRAL")
HORIZONS = ("IMMEDIATE", "INTRADAY", "SWING")
RESUME_MAX = 240

# Ce qu'on demande au modèle. `additionalProperties: false` n'est pas cosmétique : sans lui,
# un modèle bavard ajoute des champs qu'on accepterait sans les avoir demandés.
SCHEMA: dict = {
    "type": "object",
    "properties": {
        "ticker": {"type": "string", "minLength": 1, "maxLength": 16},
        "sentiment": {"type": "string", "enum": list(SENTIMENTS)},
        "confidence_score": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "impact_horizon": {"type": "string", "enum": list(HORIZONS)},
        "catalyst_summary": {"type": "string", "maxLength": RESUME_MAX},
    },
    "required": ["ticker", "sentiment", "confidence_score", "impact_horizon",
                 "catalyst_summary"],
    "additionalProperties": False,
}

MOTIF_REPLI = "FALLBACK_ERROR_OR_TIMEOUT"


@dataclass(frozen=True)
class SignalNLP:
    """Un signal classé. `confiance` n'est PAS une probabilité — cf. `calibree`."""

    ticker: str
    sentiment: str = "NEUTRAL"
    confiance: float = 0.0
    horizon: str = "IMMEDIATE"
    resume: str = ""
    # Provenance — renseignée par NOUS, jamais par le modèle.
    modele: str = ""
    version_invite: str = ""
    repli: bool = False
    latence_ms: float | None = None
    # La confiance d'un LLM n'est pas calibrée tant qu'on ne l'a pas mesurée (Brier,
    # courbe de fiabilité). Tant que c'est faux, l'afficher comme « 85 % de chances »
    # serait une affirmation que rien n'appuie.
    calibree: bool = False
    incidents: tuple[str, ...] = field(default_factory=tuple)

    @property
    def neutre(self) -> bool:
        return self.sentiment == "NEUTRAL"

    def en_dict(self) -> dict:
        return asdict(self)


def repli(ticker: str, motif: str = MOTIF_REPLI, *, modele: str = "",
          version_invite: str = "") -> SignalNLP:
    """Le signal rendu quand rien n'a marché. NEUTRE, confiance NULLE, et il le DIT.

    Un repli silencieux qui ressemblerait à un vrai signal neutre serait indistinguable
    d'une classification légitime — et un taux de neutres anormal ne voudrait plus rien dire.
    """
    return SignalNLP(ticker=ticker, sentiment="NEUTRAL", confiance=0.0,
                     horizon="IMMEDIATE", resume=motif, modele=modele,
                     version_invite=version_invite, repli=True)


def valider(brut: object, ticker: str, *, modele: str = "",
            version_invite: str = "") -> SignalNLP:
    """Transforme la réponse du modèle en signal, ou rend un repli EXPLIQUÉ.

    Toute anomalie est collectée dans `incidents` plutôt que levée : un signal presque
    correct (ticker en minuscules, confiance à 1.2) vaut mieux qu'une exception qui fait
    tomber l'analyse d'une ligne — mais on garde la trace de ce qu'on a dû corriger.
    """
    if not isinstance(brut, dict):
        return repli(ticker, "REPONSE_NON_OBJET", modele=modele,
                     version_invite=version_invite)
    incidents: list[str] = []
    manquants = [c for c in SCHEMA["required"] if c not in brut]
    if manquants:
        return repli(ticker, f"CHAMPS_MANQUANTS:{','.join(manquants)}", modele=modele,
                     version_invite=version_invite)

    sentiment = str(brut.get("sentiment", "")).strip().upper()
    if sentiment not in SENTIMENTS:
        incidents.append(f"sentiment inconnu « {sentiment} » → NEUTRAL")
        sentiment = "NEUTRAL"
    horizon = str(brut.get("impact_horizon", "")).strip().upper()
    if horizon not in HORIZONS:
        incidents.append(f"horizon inconnu « {horizon} » → IMMEDIATE")
        horizon = "IMMEDIATE"

    conf, incident = _confiance(brut.get("confidence_score"))
    if incident:
        incidents.append(incident)
    # Un sentiment forcé à NEUTRE ne peut pas garder une confiance élevée : elle
    # porterait sur une classification qui n'est plus celle du modèle.
    if sentiment == "NEUTRAL" and any("sentiment inconnu" in i for i in incidents):
        conf = 0.0

    resume = str(brut.get("catalyst_summary", "")).strip()
    if len(resume) > RESUME_MAX:
        incidents.append(f"résumé tronqué ({len(resume)} → {RESUME_MAX})")
        resume = resume[:RESUME_MAX]

    dit = str(brut.get("ticker", "")).strip().upper()
    if dit and dit != ticker.upper():
        # Le modèle a nommé un AUTRE titre : on garde le nôtre et on le signale. Accepter
        # le sien attribuerait une nouvelle à une valeur qu'on n'analysait pas.
        incidents.append(f"ticker renvoyé « {dit} » ≠ demandé « {ticker.upper()} »")

    return SignalNLP(ticker=ticker.upper(), sentiment=sentiment, confiance=conf,
                     horizon=horizon, resume=resume, modele=modele,
                     version_invite=version_invite, incidents=tuple(incidents))


def _confiance(valeur: object) -> tuple[float, str | None]:
    """Borne la confiance à [0,1] en DISANT qu'on a borné."""
    try:
        c = float(valeur)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0, f"confiance illisible « {valeur!r} » → 0.0"
    if c != c:                                        # NaN
        return 0.0, "confiance NaN → 0.0"
    if c < 0.0 or c > 1.0:
        return min(1.0, max(0.0, c)), f"confiance hors bornes ({c}) → bornée"
    return c, None


def modele_pydantic():
    """Vue Pydantic du MÊME contrat, pour l'API. `None` si pydantic est absent."""
    try:
        from pydantic import BaseModel, Field
    except Exception:  # noqa: BLE001 — cœur sans dépendance, CI allégée
        return None
    from typing import Literal

    class MarketSignalNLP(BaseModel):
        ticker: str = Field(min_length=1, max_length=16)
        sentiment: Literal["BULLISH", "BEARISH", "NEUTRAL"]
        confidence_score: float = Field(ge=0.0, le=1.0)
        impact_horizon: Literal["IMMEDIATE", "INTRADAY", "SWING"]
        catalyst_summary: str = Field(max_length=RESUME_MAX)

    return MarketSignalNLP
