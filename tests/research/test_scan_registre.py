"""Un scan est un essai : ce qui se compte, et ce qui ne doit pas se compter deux fois.

Un scanner en langage naturel balaie 200 titres en une minute — et produit vingt
variantes d'une même idée en autant de questions légitimes. Sans enregistrement, le `N`
du Deflated Sharpe ne les voit pas et le DSR déflate trop peu. C'est le p-hacking
dans sa forme la plus confortable : rien ne le signale.
"""

from __future__ import annotations

import pytest

from packages.research.scan_registre import (
    FACTEUR,
    CritereInvalide,
    deja_enregistre,
    empreinte,
    enregistrement,
    executer,
    valider,
)

RSI30 = {"champ": "rsi", "op": "<", "valeur": 30}
VOL200 = {"champ": "volume_pct", "op": ">", "valeur": 200}


def test_le_scan_filtre_ce_qu_on_lui_demande():
    lignes = [{"symbol": "A", "rsi": 25, "volume_pct": 300},
              {"symbol": "B", "rsi": 25, "volume_pct": 100},
              {"symbol": "C", "rsi": 45, "volume_pct": 300}]
    assert [r["symbol"] for r in executer(lignes, [RSI30, VOL200])] == ["A"]


def test_un_champ_absent_ECARTE_la_ligne_il_ne_la_laisse_pas_passer():
    """« Je ne sais pas » ne vaut pas « ça passe ». Sinon un scan sur un champ mal
    orthographié renverrait l'univers entier et paraîtrait fructueux."""
    lignes = [{"symbol": "A", "rsi": 25}, {"symbol": "B", "rsi": 25, "volume_pct": 300}]
    assert [r["symbol"] for r in executer(lignes, [RSI30, VOL200])] == ["B"]


def test_un_champ_non_numerique_ou_NaN_ecarte_aussi():
    lignes = [{"symbol": "A", "rsi": "faible"}, {"symbol": "B", "rsi": float("nan")},
              {"symbol": "C", "rsi": True}, {"symbol": "D", "rsi": 25}]
    assert [r["symbol"] for r in executer(lignes, [RSI30])] == ["D"]


def test_l_ordre_des_criteres_ne_change_pas_l_essai():
    """« RSI puis volume » et « volume puis RSI » sont la MÊME question. Deux empreintes
    en feraient deux essais, et gonfleraient le N pour rien."""
    assert empreinte([RSI30, VOL200]) == empreinte([VOL200, RSI30])


def test_deux_seuils_differents_sont_deux_essais_DISTINCTS():
    """C'est tout le sujet : « RSI < 30 » puis « RSI < 25 » sont deux tests, et les
    compter pour un seul est exactement ce qui laisse passer du bruit."""
    autre = {"champ": "rsi", "op": "<", "valeur": 25}
    assert empreinte([RSI30]) != empreinte([autre])


def test_rejouer_le_meme_scan_ne_le_recompte_pas():
    """Sur-déflater est l'erreur symétrique de sous-déflater, et tout aussi fausse."""
    deja = [enregistrement([RSI30], 3, 200)]
    assert deja_enregistre([RSI30], deja) is True
    assert deja_enregistre([VOL200], deja) is False


def test_un_scan_sans_critere_est_refuse():
    """Balayer l'univers entier n'est pas une hypothèse — et l'enregistrer comme telle
    polluerait le compte d'essais avec une question vide."""
    with pytest.raises(CritereInvalide):
        valider([])


def test_un_operateur_hors_liste_est_refuse_AVANT_execution():
    """La liste est fermée pour que tout scan soit rejouable et vérifiable."""
    with pytest.raises(CritereInvalide):
        valider([{"champ": "rsi", "op": "~=", "valeur": 30}])


def test_une_valeur_non_numerique_est_refusee():
    with pytest.raises(CritereInvalide):
        valider([{"champ": "rsi", "op": "<", "valeur": "trente"}])
    with pytest.raises(CritereInvalide):
        valider([{"champ": "rsi", "op": "<", "valeur": True}])


def test_un_critere_mal_forme_ne_passe_pas_en_silence():
    """L'ignorer exécuterait un scan DIFFÉRENT de celui demandé, puis l'enregistrerait
    sous l'empreinte du scan demandé : deux mensonges d'un coup."""
    with pytest.raises(CritereInvalide):
        executer([{"rsi": 10}], [{"op": "<", "valeur": 30}])


def test_l_enregistrement_porte_de_quoi_recompter_et_relire():
    rec = enregistrement([RSI30, VOL200], 6, 200, question="futures BTC survendus")
    assert rec["facteur"] == FACTEUR
    assert rec["classe"] == ["scan"]
    assert rec["empreinte"] == empreinte([RSI30, VOL200])
    assert rec["n_resultats"] == 6 and rec["n_univers"] == 200
    assert "rsi < 30" in rec["these"] and "volume_pct > 200" in rec["these"]
    assert "futures BTC survendus" in rec["these"]
    assert rec["statut"] == "exploratoire"          # jamais « validé » par un scan


def test_le_ledger_compte_bien_ces_essais(tmp_path):
    """Le câble qui manquait : un scan doit faire monter le N du DSR."""
    from packages.research.ledger import append_record, trial_count
    p = tmp_path / "h.jsonl"
    assert trial_count(p) == 0
    append_record(enregistrement([RSI30], 3, 200), p)
    append_record(enregistrement([VOL200], 9, 200), p)
    assert trial_count(p) == 2
    assert trial_count(p, facteur=FACTEUR) == 2
