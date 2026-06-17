---
title: Quant Terminal
emoji: 📈
colorFrom: blue
colorTo: indigo
sdk: gradio
sdk_version: 4.44.0
app_file: app.py
pinned: false
license: mit
---

# Quant Terminal — démo HuggingFace Space (gratuit)

Démo publique du terminal quant (screening + trading systématique multi-actifs). Tourne en
**données synthétiques** par défaut — **ne committez jamais** votre `YAHOO.db` (4+ Go) sur le Space.

## Déployer (gratuit)
1. Crée un Space `Gradio` sur https://huggingface.co/new-space
2. Pousse `app.py` + `requirements.txt` (et ce `README.md`) à la racine du Space.
3. Le Space build et sert l'app automatiquement.

## Local
```bash
pip install -r deploy/hf_space/requirements.txt
python deploy/hf_space/app.py
```

> Aide à la décision — pas un conseil en investissement. Paper trading par défaut.
