"""Morceaux de `apps/api/snapshot.py` (découpage du 31/10, texte inchangé).

Importer un morceau charge d'abord ce paquet : `.env` est lu ici aussi, comme le faisait
l'en-tête de snapshot.py « au plus tôt ».
"""

from packages.common.env import load_env as _load_env

_load_env()
