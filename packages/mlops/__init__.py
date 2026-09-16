"""MLOps — traçabilité, registre et transport des modèles.

CE PAQUET NE PEUT PAS EXÉCUTER. Il ne doit JAMAIS importer `packages.execution` ni aucun
chemin menant à un ordre courtier. Un entraînement — local ou distant — produit de
l'information et des artefacts, rien d'autre. Un test d'isolation le vérifie sur le graphe
d'imports (`tests/mlops/test_isolation.py`) : c'est une contrainte de code, pas une
convention, parce qu'une convention se contourne sans bruit.
"""
