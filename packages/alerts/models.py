"""Modèles d'alerte — sévérité hiérarchisée + clé de déduplication (anti-spam)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import IntEnum


class Severity(IntEnum):
    INFO = 10
    WARNING = 20
    CRITICAL = 30


@dataclass(frozen=True, slots=True)
class Alert:
    kind: str                 # signal | risk | regime | data | execution
    severity: Severity
    message: str
    ts: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    dedup_key: str = ""       # même clé dans la fenêtre → throttlé
    data: dict = field(default_factory=dict)

    def key(self) -> str:
        return self.dedup_key or f"{self.kind}:{self.message}"
