---
description: Audit de sécurité du dépôt public — détecte secrets, clés, PII et fichiers sensibles traqués, dans l'arbre courant ET l'historique git.
---

Audit de fuite de données (à exécuter périodiquement, surtout avant de rendre public ou après un gros changement). Reproduire ces vérifications puis produire un rapport par sévérité (CRITIQUE / ÉLEVÉ / MODÉRÉ / FAIBLE) :

1. **Fichiers sensibles traqués** :
   `git ls-files | grep -iE '\.(env|db|sqlite|pem|key|p12|pfx)$|secret|credential|token'`
   (seul `.env.example` est toléré, et il ne doit contenir que des placeholders vides).
2. **Secrets en dur** :
   `git grep -nIiE "(api[_-]?key|secret|password|token|bearer|private[_-]?key)[\"' ]*[:=]"` —
   tout doit venir de `os.environ`/`.env`, jamais de littéral.
3. **Clés au format connu** : préfixes type OpenAI (`sk` + tiret), AWS (`AKIA` + 16), GitHub
   (`ghp`/`gho`/…), Google (`AIza`…), et blocs PEM de clé privée (en-tête `BEGIN …`).
   Construire les motifs regex dynamiquement plutôt que d'écrire des littéraux dans ce fichier.
4. **PII** : emails, identifiants persos, nom d'utilisateur machine dans les chemins. Le dépôt doit
   rester **anonyme** (aucune occurrence de données personnelles ; cf. la règle d'anonymisation).
5. **Historique git** :
   `git log --all --diff-filter=A --name-only --pretty=format: | grep -iE '\.env$|\.db$|secret|\.pem$|\.key$'`
   — un secret committé puis retiré reste dans l'historique (→ rotation de clé obligatoire).
6. **Couverture `.gitignore`** : confirmer que `.env`, `*.db`, `.cache/`, `site/`,
   `apps/web/public/{data,reports}` sont bien ignorés (`git check-ignore -v <path>`).
7. **Surface publiée** : rappeler que le build CI n'a pas les clés courtier → les positions réelles
   ne doivent jamais apparaître sur le site public.

Le garde-fou automatisé existe déjà (`.github/workflows/gitleaks.yml` + `.pre-commit-config.yaml`) ;
ce skill sert à l'audit manuel approfondi et au rapport.
