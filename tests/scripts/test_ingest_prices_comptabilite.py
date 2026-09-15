"""Ce que le log du VPS du 15/09 a révélé — et qui ne doit plus jamais être muet.

Deux défauts mesurés sur le run de 19:05:02 UTC :
  · « Terminé : 736 OK · 0 échecs · 102 crypto ignorées » sur un univers de 929. Quatre-
    vingt-onze symboles ne rendaient AUCUNE donnée et n'apparaissaient nulle part, parce
    qu'un `history()` vide ne lève pas d'exception.
  · Dix-sept contrats à terme et paires de devises re-backfillés sur onze ans, chaque
    jour, au motif d'un « split/dividende » — qu'aucun d'entre eux ne peut subir.
"""

import importlib.util
import pathlib
import sqlite3

import pytest

RACINE = pathlib.Path(__file__).resolve().parents[2]


def _mod():
    spec = importlib.util.spec_from_file_location(
        "ingest_prices", RACINE / "scripts" / "ingest_prices.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ─── Le roulement des futures n'est pas un split ───────────────────────────────────────

def test_seuls_actions_et_etf_peuvent_splitter():
    m = _mod()
    assert set(m.PEUT_SPLITTER) == {"equity", "etf", ""}
    for ac in ("commodity", "commodite", "forex", "index", "indice", "crypto"):
        assert ac not in m.PEUT_SPLITTER


def test_le_garde_est_bien_devant_lappel_au_detecteur():
    """La classe d'actif doit être testée AVANT `_split_drift`, sinon le re-backfill
    reste déclenché par un détecteur qui a raison sur le fait et tort sur la cause."""
    src = (RACINE / "scripts" / "ingest_prices.py").read_text(encoding="utf-8")
    ligne = next(l for l in src.splitlines() if "_split_drift(conn, sym, rows)" in l)
    assert "ac in PEUT_SPLITTER" in ligne
    assert ligne.index("PEUT_SPLITTER") < ligne.index("_split_drift")


def test_le_detecteur_lui_meme_reste_intact():
    """On ne touche PAS à sa logique : sur une action, un split doit toujours déclencher
    le re-backfill. Seul son PÉRIMÈTRE d'application change."""
    m = _mod()
    conn = sqlite3.connect(":memory:")
    conn.executescript(m._DDL)
    conn.execute("INSERT INTO prices VALUES('AAPL','2026-09-14',1,1,1,100.0,100.0,1)")
    conn.commit()
    # Même date, close divisé par 10 → dérive massive, bien au-delà de la tolérance.
    apres = [("AAPL", "2026-09-14", 1, 1, 1, 10.0, 10.0, 1)]
    assert m._split_drift(conn, "AAPL", apres) is True
    # Même close → aucune dérive.
    assert m._split_drift(conn, "AAPL", [("AAPL", "2026-09-14", 1, 1, 1, 100.0, 100.0, 1)]) is False


def test_les_symboles_du_15_09_sont_tous_hors_perimetre():
    """Les dix-sept séries qui se re-backfillaient tous les jours, vérifiées une à une."""
    m = _mod()
    from apps.api.snapshot import _seed_universe
    classes = {s["symbol"]: s.get("asset_class", "equity") for s in _seed_universe()}
    coupables = ["CL=F", "BZ=F", "HO=F", "RB=F", "GC=F", "HG=F", "ALI=F", "ZC=F", "ZW=F",
                 "ZS=F", "SB=F", "KC=F", "CC=F", "CT=F", "LE=F", "USD/JPY", "USD/MXN"]
    connus = [s for s in coupables if s in classes]
    assert connus, "aucun des symboles du 15/09 n'est dans les seeds — test à revoir"
    for s in connus:
        assert classes[s] not in m.PEUT_SPLITTER, (
            f"{s} ({classes[s]}) est encore traité comme capable de splitter")


# ─── La comptabilité se referme ────────────────────────────────────────────────────────

def test_le_resume_nomme_les_symboles_sans_donnee():
    src = (RACINE / "scripts" / "ingest_prices.py").read_text(encoding="utf-8")
    assert "sans donnée" in src
    assert "vides.append(sym)" in src
    assert "make audit-univers" in src            # la suite à donner est écrite


def test_les_compteurs_couvrent_tous_les_chemins_de_sortie():
    """Chaque `continue` de la boucle doit incrémenter un compteur — sinon un symbole
    ressort du total sans qu'aucune ligne ne le porte, et c'est exactement le trou du
    15/09 : « 0 échecs » avec 91 symboles muets."""
    src = (RACINE / "scripts" / "ingest_prices.py").read_text(encoding="utf-8")
    boucle = src.split("for i, (sym, ac) in enumerate(symbols, 1):", 1)[1]
    boucle = boucle.split("    print(f\"Terminé", 1)[0]
    # Trois sorties anticipées : crypto ignorée, déjà à jour, échec de fetch.
    assert boucle.count("continue") == 3
    for compteur in ("skip += 1", "ajour.append(sym)", "fail += 1", "vides.append(sym)"):
        assert compteur in boucle, f"chemin non comptabilisé : {compteur} absent"
    # …et le script VÉRIFIE lui-même que la somme se referme.
    assert "chemin non comptabilisé" in src


# ─── Le bruit devient lisible ──────────────────────────────────────────────────────────

def test_yfinance_est_mis_en_sourdine_avec_une_porte_de_sortie(monkeypatch):
    m = _mod()
    import logging
    for nom in ("yfinance", "urllib3", "peewee"):
        logging.getLogger(nom).setLevel(logging.INFO)
    m._silence_yfinance()
    assert logging.getLogger("yfinance").level == logging.CRITICAL

    logging.getLogger("yfinance").setLevel(logging.INFO)
    monkeypatch.setenv("QUANT_VERBOSE_YF", "1")
    m._silence_yfinance()
    assert logging.getLogger("yfinance").level == logging.INFO


def test_la_sourdine_ne_sapplique_qua_lexecution_directe():
    """Importé comme module (tests, autres scripts), `ingest_prices` ne doit pas
    reconfigurer les loggers du processus hôte dans son dos."""
    src = (RACINE / "scripts" / "ingest_prices.py").read_text(encoding="utf-8")
    apres_main = src.split('if __name__ == "__main__":', 1)[1]
    assert "_silence_yfinance()" in apres_main
    # UN seul APPEL (la définition porte le même texte : on l'exclut du compte).
    assert src.count("_silence_yfinance()") - src.count("def _silence_yfinance()") == 1


@pytest.mark.parametrize("ac", ["commodity", "forex", "index"])
def test_aucune_classe_non_splittable_ne_passe(ac):
    assert ac not in _mod().PEUT_SPLITTER
