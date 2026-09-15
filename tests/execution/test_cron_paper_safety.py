from pathlib import Path


def test_cron_neutralise_toutes_les_cles_crypto_sans_rechargement_env():
    script = Path("scripts/cron_live.sh").read_text(encoding="utf-8")
    guard = script.split('if [ "${QUANT_NO_CRYPTO_LIVE:-1}" = "1" ]; then', 1)[1]
    guard = guard.split("fi", 1)[0]

    for key in (
        "BITMART_API_KEY",
        "BITMART_API_SECRET",
        "BITMART_API_MEMO",
        "BINANCE_API_KEY",
        "BINANCE_API_SECRET",
    ):
        assert f'{key}=""' in guard
    assert 'QUANT_BINANCE_TESTNET="1"' in guard
    assert "unset " not in guard


def test_un_seul_planificateur_envoie_des_ordres():
    """UN seul déclencheur automatique vers le courtier — le VPS et rien d'autre.

    Le 15/09, deux planificateurs visaient le même compte Alpaca paper : le crontab du
    VPS (19:05 UTC, via la fenêtre avant-clôture) et `paper.yml`, dont la planification
    à 14:35 UTC était livrée par GitHub avec 201 minutes de retard MÉDIAN — donc en
    plein dans la fenêtre du VPS. Résultat mesuré : treize lignes ouvertes à 18:32,
    sept soldées à la quantité près à 19:04, −60,79 $ pour rien.

    Ce test ne juge pas du choix (le VPS plutôt que le cloud) : il interdit qu'on se
    retrouve à DEUX sans s'en apercevoir. Un second planificateur ne s'ajoute qu'en
    supprimant d'abord l'autre — et en venant lire ici pourquoi.
    """
    paper = Path(".github/workflows/paper.yml").read_text(encoding="utf-8")
    declencheurs = paper.split("\njobs:", 1)[0]
    assert "workflow_dispatch:" in declencheurs        # le lancement manuel reste
    assert "schedule:" not in declencheurs, (
        "paper.yml a retrouvé une planification : il y a de nouveau DEUX robots sur le "
        "même compte. Retirer d'abord le cron du VPS (make live-cron-uninstall)."
    )


def test_le_garde_journalier_est_dans_le_chemin_du_cron():
    """`cron_live.sh` appelle bien le script qui porte le garde-fou, sans le désarmer."""
    script = Path("scripts/cron_live.sh").read_text(encoding="utf-8")
    assert "scripts/run_live.py --live --yes" in script
    assert "--forcer" not in script                    # un cron ne force JAMAIS
    assert "QUANT_REBAL_MULTI" not in script           # ni ne désarme le garde
