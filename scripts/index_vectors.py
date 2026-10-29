#!/usr/bin/env python3
"""Indexe journal en vecteurs et ontologie."""

from packages.storage.vector_store import VectorStore
from packages.storage.ontology import Ontology

def main():
    vs = VectorStore()
    n = vs.index_journal()
    vs.close()
    onto = Ontology()
    onto.index_from_journal()
    onto.close()
    print(f"{n} enregistrements vectorisés ; ontologie mise à jour dans data/")

if __name__ == "__main__":
    main()
