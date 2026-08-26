"""Le marché est-il OUVERT ? — la question que l'exécution ne posait jamais.

DÉFAUT CONSTATÉ SUR LE COMPTE RÉEL (26/08). Le compte paper contenait le cœur QQQ,
huit lignes crypto, et **zéro action du satellite** — les 28 % de cash correspondant
exactement à la part actions manquante.

Cause : `alpaca_broker` envoie les actions en `TimeInForce.DAY` sans `extended_hours`,
et la crypto en `GTC` (24/7). Un rebalancement lancé depuis l'Europe tombe à 03 h à
New York : la crypto se remplit, les actions ne peuvent pas.

Aucun contrôle d'horaires n'existait dans `run_live`, `alpaca_broker` ni `live_guards`.
Le système envoyait donc des ordres actions à n'importe quelle heure, et un ordre qui
ne peut pas se remplir ne laissait aucune trace lisible. C'est ce SILENCE qui a rendu
le défaut invisible, bien plus que le défaut lui-même.

PÉRIMÈTRE ASSUMÉ. Ceci n'est PAS le `MarketCalendar` complet du F11 : ni demi-séances,
ni enchères, ni `session_minutes`, une seule place. C'est le strict nécessaire pour
répondre « peut-on envoyer cet ordre maintenant ? » — XNYS régulier 09:30-16:00 ET,
week-ends, jours fériés, et 24/7 pour le crypto. L'intraday reste hors sujet ici.

stdlib pure, testable hors-ligne, aucune dépendance réseau : un garde-fou d'exécution
ne doit pas dépendre d'un appel qui peut échouer.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

# Fériés NYSE observés. Liste EXPLICITE plutôt que calculée : une règle de calcul
# fausse est silencieuse, une date manquante est visible. À compléter chaque année
# (cf. `test_table_des_feries_couvre_l_annee_en_cours`).
FERIES_NYSE: frozenset[date] = frozenset({
    date(2024, 1, 1), date(2024, 1, 15), date(2024, 2, 19), date(2024, 3, 29),
    date(2024, 5, 27), date(2024, 6, 19), date(2024, 7, 4), date(2024, 9, 2),
    date(2024, 11, 28), date(2024, 12, 25),
    date(2025, 1, 1), date(2025, 1, 9), date(2025, 1, 20), date(2025, 2, 17),
    date(2025, 4, 18), date(2025, 5, 26), date(2025, 6, 19), date(2025, 7, 4),
    date(2025, 9, 1), date(2025, 11, 27), date(2025, 12, 25),
    date(2026, 1, 1), date(2026, 1, 19), date(2026, 2, 16), date(2026, 4, 3),
    date(2026, 5, 25), date(2026, 6, 19), date(2026, 7, 3), date(2026, 9, 7),
    date(2026, 11, 26), date(2026, 12, 25),
})

# Dernière année couverte par `FERIES_NYSE`. Au-delà, `is_open` reste prudent : une
# liste périmée ne doit pas faire croire à une séance ouverte un jour férié.
DERNIERE_ANNEE_FERIES = 2026

_OUVERTURE, _FERMETURE = time(9, 30), time(16, 0)


def _et(ts: datetime) -> datetime:
    """UTC → heure de New York.

    L'offset DST est déduit des bornes US (2e dimanche de mars → 1er dimanche de
    novembre), sans dépendre de `zoneinfo`, absent de certains conteneurs.
    """
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    u = ts.astimezone(UTC)
    an = u.year
    mars = date(an, 3, 8)
    debut = mars + timedelta(days=(6 - mars.weekday()) % 7)      # 2e dimanche de mars
    nov = date(an, 11, 1)
    fin = nov + timedelta(days=(6 - nov.weekday()) % 7)          # 1er dim. novembre
    dst = debut <= u.date() < fin
    return u + timedelta(hours=-4 if dst else -5)


def est_ferie(j: date) -> bool:
    return j in FERIES_NYSE


def feries_a_jour(ts: datetime | None = None) -> bool:
    """La table des fériés couvre-t-elle encore l'année en cours ?

    Un garde-fou qui se périme en silence est pire que pas de garde-fou : il rassure
    sans protéger.
    """
    an = _et(ts or datetime.now(UTC)).year
    return an <= DERNIERE_ANNEE_FERIES


def is_open(ts: datetime | None = None, asset_class: str = "equity") -> bool:
    """Peut-on envoyer un ordre au marché MAINTENANT pour cette classe d'actifs ?

    Crypto : toujours (24/7). Actions/ETF : séance régulière XNYS uniquement —
    l'exécution n'active pas `extended_hours`, donc le pré/post-marché ne compte
    pas comme ouvert.
    """
    if (asset_class or "").lower() == "crypto":
        return True
    n = _et(ts or datetime.now(UTC))
    if n.weekday() >= 5 or est_ferie(n.date()):
        return False
    return _OUVERTURE <= n.time() < _FERMETURE


def raison_fermeture(ts: datetime | None = None, asset_class: str = "equity") -> str:
    """Pourquoi c'est fermé, en une ligne lisible dans un journal. Vide si ouvert."""
    if is_open(ts, asset_class):
        return ""
    n = _et(ts or datetime.now(UTC))
    if n.weekday() >= 5:
        return f"week-end à New York ({n:%a %d/%m %H:%M} ET)"
    if est_ferie(n.date()):
        return f"férié NYSE ({n:%d/%m})"
    quand = "avant l'ouverture" if n.time() < _OUVERTURE else "après la clôture"
    return f"hors séance — {quand} ({n:%H:%M} ET ; séance 09:30–16:00)"


def prochaine_ouverture(ts: datetime | None = None) -> datetime:
    """Prochaine ouverture XNYS, heure de New York — pour dire QUAND l'ordre partira."""
    n = _et(ts or datetime.now(UTC))
    j = n.date() if n.time() < _OUVERTURE else n.date() + timedelta(days=1)
    while j.weekday() >= 5 or est_ferie(j):
        j += timedelta(days=1)
    return datetime.combine(j, _OUVERTURE)
