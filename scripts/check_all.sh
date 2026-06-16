#!/usr/bin/env bash
# Vérification complète du système (offline). Usage : bash scripts/check_all.sh
set -e
echo "== 1/4 Tests =="
pytest -q
echo "== 2/4 Démos offline =="
for d in backtest walkforward macro_regime ml paper_loop alerts ops; do
  echo "--- demo_$d ---"; python scripts/demo_$d.py >/dev/null && echo "OK"
done
echo "== 3/4 Aperçus HTML =="
python apps/web/preview/build_preview.py
python apps/web/preview/build_interactive.py
echo "== 4/4 Terminé : ouvre apps/web/preview/interactive.html =="
