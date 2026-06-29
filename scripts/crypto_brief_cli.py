#!/usr/bin/env python3
"""Note de marché crypto → Obsidian (vault/11_Crypto/). Contexte, pas un signal.

Réseau best-effort (CoinGecko, DefiLlama, alternative.me — gratuit, sans clé). Écrit une
note du jour + une note stable "Cockpit.md" (toujours la dernière), indexables par
`make vault-search`. Champs absents → "n/d" (jamais de chiffre inventé).
"""
from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packages.data.crypto_market import cockpit  # noqa: E402
from packages.research.crypto_brief import render  # noqa: E402


def main() -> int:
    today = datetime.now(UTC).date().isoformat()
    print("Construction du cockpit crypto (gratuit, sans clé)…")
    ck = cockpit()
    md = render(ck, today)
    d = ROOT / "vault" / "11_Crypto"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"Cockpit_{today}.md").write_text(md, encoding="utf-8")
    (d / "Cockpit.md").write_text(md, encoding="utf-8")
    se = ck.get("sentiment") or {}
    humeur = se.get("label", "n/d") if se.get("available") else "n/d"
    print(f"✅ note → vault/11_Crypto/Cockpit.md (humeur {humeur})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
