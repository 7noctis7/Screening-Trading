"""Le mandat — définition déclarative de stratégie, indépendante du moteur.

    from packages.mandate import Mandat, exiger_valide, auditer

Trois briques :
  * `spec`      — le mandat, son identité (hash canonique), sa validation
  * `canonical` — la forme canonique qui rend ce hash stable
  * `purete`    — vérifie mécaniquement que le moteur est une fonction pure du mandat
"""

from packages.mandate.canonical import canoniser, hacher, hacher_court
from packages.mandate.purete import (
    auditer,
    verifier_determinisme,
    verifier_equivalence,
    verifier_independance_environnement,
)
from packages.mandate.spec import (
    CONTRAINTES_CONNUES,
    METRIQUES_DE_RESULTAT,
    SCHEMA_VERSION,
    Mandat,
    depuis_dict,
    exiger_valide,
    valider,
)

__all__ = [
    "CONTRAINTES_CONNUES", "METRIQUES_DE_RESULTAT", "SCHEMA_VERSION", "Mandat",
    "auditer", "canoniser", "depuis_dict", "exiger_valide", "hacher",
    "hacher_court", "valider", "verifier_determinisme", "verifier_equivalence",
    "verifier_independance_environnement",
]
