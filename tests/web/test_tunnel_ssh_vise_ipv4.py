"""Aucune commande de tunnel proposée par le dépôt ne doit viser « localhost ».

CE QUI S'EST PASSÉ LE 21/09. « Aucune page de mon site ne fonctionne. » Les services
tournaient, `make up` affichait front prêt, API 200 et snapshot prêt. Côté Mac, le tunnel
crachait en boucle :

    channel 5: open failed: connect failed: Connection refused

`ssh -L 3000:localhost:3000` résout « localhost » SUR LE VPS. Là-bas il peut valoir `::1`,
que les services n'écoutent pas (`uvicorn --host 127.0.0.1`). SSH tente donc une adresse
où personne ne répond, pendant que le site fonctionne parfaitement. Les deux constats sont
vrais en même temps, et rien ne les reliait.

Le dépôt RECOMMANDAIT lui-même la forme piégée, à deux endroits. C'est ce que ce test
interdit de réintroduire. Les COMMENTAIRES sont exemptés : nommer la forme fautive pour
l'expliquer est utile ; la proposer à la copie ne l'est pas.
"""

from __future__ import annotations

import re
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
# Le journal garde la trace des commandes historiques : on n'y touche pas.
FICHIERS = [p for p in (list(RACINE.glob("scripts/*.sh")) + [RACINE / "CLAUDE.md"]
                        + list(RACINE.glob("docs/*.md")) + [RACINE / "Makefile"])
            if p.exists()]


def _lignes_de_recommandation() -> list[tuple[Path, str]]:
    out: list[tuple[Path, str]] = []
    for f in FICHIERS:
        for ligne in f.read_text(encoding="utf-8").splitlines():
            if "ssh -L" not in ligne:
                continue
            if ligne.strip().startswith("#"):        # commentaire : il EXPLIQUE, il ne propose pas
                continue
            out.append((f, ligne))
    return out


def test_aucune_recommandation_de_tunnel_ne_vise_localhost():
    fautifs = [(f.name, li.strip()) for f, li in _lignes_de_recommandation()
               if re.search(r"-L\s*\d+:localhost:", li)]
    assert not fautifs, (
        "Tunnel proposé vers « localhost », résolu sur le VPS et possiblement ::1 : "
        f"{fautifs}. Viser 127.0.0.1.")


def test_le_controle_de_service_MESURE_la_pile_avant_de_parler():
    """Il ne suppose pas que rien n'écoute en IPv6 : il essaie `[::1]` et ne dit quelque
    chose que si ça refuse. Un conseil donné sans mesure serait du bruit sur une machine
    correctement configurée en double pile."""
    src = (RACINE / "scripts" / "verifier_service.sh").read_text(encoding="utf-8")
    assert "[::1]" in src
    assert "127.0.0.1:$PORT" in src
    assert "Connection refused" in src      # le symptôme est NOMMÉ, pas seulement le remède
