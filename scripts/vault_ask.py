#!/usr/bin/env python3
"""Assistant RAG ancré sur le vault — réponse EXTRACTIVE citée (zéro hallucination).

Usage : python scripts/vault_ask.py "quelle est la règle du gate de promotion ?"
Chaque phrase de la réponse est une citation verbatim [n] → fichier › section.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packages.research.vault_rag import grounded_answer  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="RAG ancré sur le vault (citations).")
    ap.add_argument("query", help="question en langage naturel")
    ap.add_argument("-k", type=int, default=4, help="sections récupérées")
    a = ap.parse_args()
    res = grounded_answer(a.query, k=a.k)
    print(f"\nQ : {res['query']}\n")
    print(res["answer"], "\n")
    if res["citations"]:
        print("Sources :")
        for c in res["citations"]:
            print(f"  [{c['n']}] {c['file']} › {c['heading']}  ({c['score']:.3f})")
    if not res["grounded"]:
        print("(non ancré : aucune source pertinente — rien inventé.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
