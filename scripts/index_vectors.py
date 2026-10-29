#!/usr/bin/env python3
"""Indexe les enregistrements du journal en vecteurs."""

from packages.storage.vector_store import VectorStore

def main():
    vs = VectorStore()
    n = vs.index_journal()
    print(f"{n} enregistrements indexés dans data/vectors.db")
    vs.close()

if __name__ == "__main__":
    main()
