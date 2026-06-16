from datetime import datetime, timedelta, timezone
from packages.core.models import Bar

def mkbars(prices, symbol="X", tf="1d"):
    t0 = datetime(2024, 1, 1, tzinfo=timezone.utc)
    return [Bar(symbol, tf, t0 + timedelta(days=i),
                p, p * 1.01, p * 0.99, p, 1000.0) for i, p in enumerate(prices)]
