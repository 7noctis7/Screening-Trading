"""L'intro publiait un profit factor sans jamais dire combien il avait rapporté.

`apps/api/intro_payload.trades` calcule et expose `pnl_total` — le réalisé des
aller-retours clôturés, en dollars — depuis l'origine. `IntroBeats` ne le lisait pas :
le battement « trades » affichait « PROFIT FACTOR 1,34 · R:R … · espérance … », c'est-à-
dire trois ratios et aucun montant. Un facteur de profit ne dit pas si le robot a gagné
dix dollars ou dix mille, et c'est pourtant la première chose qu'on veut savoir.

La donnée était produite, transportée, et jetée à l'affichage.
"""

from __future__ import annotations

import ast
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
BEATS = (RACINE / "apps" / "web" / "components" / "intro" / "IntroBeats.tsx").read_text(
    encoding="utf-8")
PAYLOAD = RACINE / "apps" / "api" / "intro_payload.py"


def test_l_api_publie_bien_le_realise():
    """Si l'API cessait de l'exposer, le front afficherait « n/d » sans qu'on sache
    lequel des deux a lâché. On vérifie la source."""
    arbre = ast.parse(PAYLOAD.read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(arbre)
              if isinstance(n, ast.FunctionDef) and n.name == "trades")
    cles = {k.value for n in ast.walk(fn) if isinstance(n, ast.Dict)
            for k in n.keys if isinstance(k, ast.Constant)}
    assert "pnl_total" in cles


def test_le_battement_trades_AFFICHE_le_realise():
    bloc = BEATS.split('if (b.genre === "trades")', 1)[1].split("}", 1)[0] \
        if 'if (b.genre === "trades")' in BEATS else BEATS
    assert "pnl_total" in BEATS
    assert "usd(t.pnl_total)" in BEATS
    assert "réalisé" in BEATS


def test_le_realise_est_dit_BRUT_de_frais():
    """Chez ce courtier les frais sont des activités séparées, absentes du flux
    d'ordres : un réalisé reconstruit depuis les fills est brut, et l'afficher sans le
    dire en ferait un net qu'il n'est pas."""
    assert "BRUT" in BEATS


def test_un_realise_ABSENT_dit_n_d_jamais_zero():
    """Zéro se lirait « le robot n'a rien gagné » là où il faut lire « on ne sait pas »
    — la même distinction que `age_s`, que `effet_usd` et que tout le reste ici."""
    assert 'v == null ? "n/d"' in BEATS
