"""Leak-sentinel AUTOMATISÉ — le chemin vintage réel (MacroStore) ne fuite pas le futur.

C'est LA garantie programmatique anti-look-ahead sur la source vintage utilisée par le ML :
`as_of(t)` ne doit JAMAIS retourner une observation publiée après t (realtime_start > t).
"""

from datetime import datetime, timezone

from packages.core.models import MacroObservation
from packages.storage.macro_store import MacroStore


def _d(s: str) -> datetime:
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


def test_as_of_excludes_future_vintage():
    st = MacroStore(":memory:")
    # même période observée (jan), DEUX vintages : connu en févr. (3.4) puis révisé en mars (3.6)
    st.upsert([
        MacroObservation("UNRATE", _d("2020-01-01"), 3.4, _d("2020-02-05")),
        MacroObservation("UNRATE", _d("2020-01-01"), 3.6, _d("2020-03-10")),
    ])
    # au 2020-02-20, SEULE la révision de févr. (3.4) est connue → pas de fuite du futur
    r = st.as_of("UNRATE", _d("2020-02-20"))
    assert r is not None and r[1] == 3.4
    # au 2020-03-15, la révision de mars (3.6) est connue
    r2 = st.as_of("UNRATE", _d("2020-03-15"))
    assert r2 is not None and r2[1] == 3.6
    st.close()


def test_as_of_none_before_publication():
    st = MacroStore(":memory:")
    st.upsert([MacroObservation("T10Y2Y", _d("2021-06-01"), 1.2, _d("2021-06-02"))])
    # requête AVANT publication → rien (jamais de valeur « du futur »)
    assert st.as_of("T10Y2Y", _d("2021-05-01")) is None
    st.close()
