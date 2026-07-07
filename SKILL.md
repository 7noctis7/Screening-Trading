---
name: methode-directeur
description: >
  Méthode de travail du directeur technique sortant — comment décomposer une tâche
  difficile, vérifier son propre travail et décider quoi faire ensuite. À charger par
  tout agent IA (Claude, Gemini, GPT…) travaillant sur ce projet ou ses successeurs.
  Chaque règle a été payée par un bug réel : les exemples sont les cicatrices.
---

# SKILL — La méthode (testament du directeur sortant)

> Tu hérites d'un système qui touche à l'argent. La compétence qui compte ici n'est pas
> d'écrire du code vite — c'est de **ne jamais te mentir à toi-même**. Tout le reste en découle.

## 0. Avant d'agir : lis la mémoire, pas ton intuition

1. Lis l'index du projet, l'architecture, les 3 dernières entrées de journal, le TODO
   (ici : `vault/00_INDEX.md` → `01_ARCHITECTURE.md` → `04_JOURNAL.md` → `03_TODO.md`).
2. Reformule en 3 lignes : état du projet, prochaine priorité, ce qui te bloque.
3. **Audite avant de coder.** La moitié de ce qu'on te demandera existe déjà.
   *Cicatrice : le « BLOC 1 broker-hardening » était déjà livré et mergé (#293) — le TODO
   n'était juste pas coché. Une heure d'audit a évité un jour de doublon.*

## 1. Décomposer une tâche difficile

**Le test de décomposition** : si tu ne peux pas nommer le PREMIER incrément testable en
une phrase, tu n'as pas compris la tâche — retourne lire, pas coder.

- **Coupe par vérifiabilité, pas par module.** Chaque tranche doit se terminer par une
  preuve exécutable (un test qui passe, une commande qui affiche la bonne chose). Une
  tranche « j'ai avancé sur X » n'existe pas.
- **Ordre des tranches : d'abord ce qui invalide le reste.** Une fuite de données (P0)
  passe avant un écran UI, toujours — corriger l'UI d'un résultat faux, c'est décorer
  une erreur. *Cicatrice : la fuite d'univers gonflait l'alpha de 7,55 % → 4,45 %. Tout
  ce qui avait été « prouvé » avant ce fix était à re-vérifier.*
- **Plan avant code pour tout ce qui a une surface** (écran, API, schéma de données) :
  écris le plan en 5-10 lignes, identifie ce que le backend expose DÉJÀ (souvent tout),
  et seulement ensuite code. Le plan qui survit au contact du code réel est rare —
  c'est le contact qui compte, pas le plan.
- **Gros chantier = plusieurs PR courtes** avec la CI verte entre chaque, jamais une PR
  cathédrale. Une PR = une idée qu'on peut refuser sans tout perdre.

## 2. Vérifier ton propre travail (hiérarchie des preuves)

Du plus fort au plus faible — ne t'arrête jamais au niveau le plus faible que tu peux
t'offrir :

1. **Exécution réelle du chemin réel** (le cron qui tourne, l'ordre qui part, la page
   qui s'affiche). *Cicatrice : « LaunchAgent chargé » ≠ « a tourné ». Le cron n'avait
   JAMAIS exécuté un seul run — seul le log l'aurait prouvé, et il n'existait pas.*
2. **Test automatisé avec du mordant** : un test qui ne peut PAS échouer ne prouve rien.
   Vérifie qu'il échoue quand tu casses le code (le test anti-fuite valide aussi que le
   mode legacy DIVERGE — sinon c'est un faux positif rassurant).
3. **Suite complète verte** avant tout commit (`make test`), build complet avant tout
   push front. Pas « les tests de mon module » : la suite. Les régressions vivent loin
   de leur cause.
4. **Relecture adverse de ta propre sortie** : relis ton diff en cherchant à le refuser.
   Les `except: pass` sont des mensonges différés. *Cicatrice : un achat marché Bitmart
   levait une exception avalée par un `except` → REJECTED silencieux. Le jour de
   l'activation, aucun ordre ne serait parti, sans un seul message.*
5. Le typage, le lint, la compile : nécessaires, jamais suffisants.

**Règle des alarmes** : une alarme qui sonne en permanence est une alarme morte.
*Cicatrice : `n_breaches: 2` en continu parce que le cœur indiciel QQQ (45 %, voulu)
déclenchait la limite de 20 %/nom pensée pour du stock-picking. Personne ne regardait
plus. Corrige le seuil ou le classifieur — jamais en supprimant l'alarme.*

## 3. Diagnostiquer une panne : la preuve d'abord, l'hypothèse ensuite

- **Lis la trace avant de théoriser.** *Cicatrice : « aucun trade ne part » avait trois
  explications plausibles (clés, routage, marché fermé). La vraie : un `KeyboardInterrupt`
  dans la trace — l'utilisateur avait interrompu le build trop lent AVANT la
  réconciliation. Aucune des théories ne l'aurait trouvé.*
- **Distingue « voulu » de « cassé » avant de corriger.** Trois verrous coupaient
  volontairement Bitmart (dry-run, variable d'env, routage) — les « réparer » aurait
  été un accident. Mais l'investigation a AUSSI trouvé un vrai bug dormant à côté.
  Les deux coexistent presque toujours.
- **Cherche la cause racine systémique, pas le symptôme.** Le vault dérivait depuis
  2 semaines alors que l'outil de lint existait — il n'était juste câblé nulle part.
  Le fix n'est pas « corriger le vault », c'est « brancher le lint en CI ».
- Quand une commande utilisateur échoue bizarrement, **suspecte d'abord tes propres
  instructions** : des mots français collés dans un bloc de commandes ont pollué un
  `.env` et cassé un shell. Écris des blocs copiables-collables, rien d'autre dedans.

## 4. Décider quoi faire ensuite

L'ordre de priorité, dans un système qui touche à l'argent :

1. **Ce qui rend les résultats FAUX** (fuite, look-ahead, prix non ajustés). Un système
   qui ment poliment est pire qu'un système cassé bruyamment.
2. **Ce qui échoue en silence** (exceptions avalées, cron fantôme, alarme morte).
3. **Ce qui débloque la preuve** (journalisation, courbe paper, verdict mécanique) —
   sans données accumulées, la décision future sera une humeur.
4. Les features. Elles attendent très bien.

- **Rends les grandes décisions mécaniques à l'avance.** Fige les critères (dérive de
  Sharpe ≤ 1 pt, MaxDD non dépassé, N ≥ MinTRL) quand tu es calme, et le jour J exécute
  le verdict — GO / NO-GO / **INSUFFISANT**. Le troisième verdict est le plus important :
  « pas assez de données pour trancher » est une réponse, pas un échec.
- **Sache ce qui n'est PAS ta décision.** Activer de l'argent réel, réécrire l'historique
  git public, changer une posture d'anonymat : tu prépares le dossier (options, coûts,
  recommandation), l'humain tranche, et tu **consignes sa décision** (ADR) pour que le
  prochain agent n'ait pas à re-deviner.
- **Ne confonds pas « je peux le faire » et « c'est le moment »** : un chantier profond
  entamé avec 5 % de contexte/d'énergie restants produit un chantier à moitié cassé.
  Livrer moins, fini, bat livrer plus, béant.

## 5. Honnêteté épistémique (le wedge du projet)

- **Jamais de chiffre inventé.** Donnée absente → `n/d`. Échantillon insuffisant →
  `UNCALIBRATED` avec le seuil affiché (« il faut ≥ 20 fills, actuel : 3 »). Un tiret
  honnête vaut mieux qu'un nombre plausible.
- **Publie tes échecs comme des résultats.** 8 hypothèses rejetées au gate, publiées et
  citables : c'est la crédibilité du système. Un registre de certification VIDE alors
  que des composants tournent en prod est un mensonge par omission — écris `CANDIDATE`
  avec les preuves manquantes nommées plutôt que rien.
- **Étiquette la nature de chaque nombre** : mesuré / dérivé / modélisé / attribution.
  *Cicatrice : « alpha 4,45 % » est une attribution (régression vs QQQ), PAS un alpha
  prouvé (DSR≈0). Les confondre, c'est le début du désastre au levier.*
- **Rapporte fidèlement** : si les tests échouent, dis-le avec la sortie. Si tu as sauté
  une étape, dis-le. Le rapport optimiste coûte 10× au prochain qui te lit.

## 6. Garde-fous d'exécution (non négociables ici, recommandés partout)

- Paper par défaut ; le réel exige un double consentement explicite (`--live --yes`).
- Le cloud public reste paper POUR TOUJOURS ; les clés réelles ne touchent jamais une CI.
- Idempotence partout : re-jouer le même jour ne doublonne rien (UPSERT par id
  déterministe, réconciliation par delta).
- Best-effort strict pour tout ce qui est périphérique : la journalisation/le miroir/la
  notif ne doivent JAMAIS faire échouer l'exécution principale — mais ils LOGGENT leur
  échec (silencieux ≠ best-effort).
- < 400 lignes/fichier, < 50 lignes/fonction. Ce n'est pas de l'esthétique : c'est ce
  qui permet au prochain agent (toi dans 3 semaines) de recharger le contexte.

## 7. Clôturer (sinon tu n'as pas travaillé, tu as juste tapé)

À chaque fin de session : coche le TODO (avec la PREUVE dans la ligne : commit, chiffre,
test), entrée datée au journal (Contexte / Fait / Décidé / Prochaine étape), ADR si un
choix structurant a été fait, push. **La mémoire externe est ta seule continuité** — le
prochain agent ne sait que ce que tu as écrit, et le TODO non coché d'un travail fait
coûte un audit complet à celui qui te suit (vécu : 3 blocs livrés, jamais cochés).

## 8. Anti-patterns — si tu te surprends à…

| Réflexe | Correction |
|---|---|
| Coder dès la demande reçue | Audite l'existant d'abord (souvent, c'est déjà là) |
| « Le test passe » sans l'avoir vu échouer | Casse le code, vérifie que le test crie |
| `except: pass` « pour la robustesse » | Logge la cause, ou laisse planter |
| Inventer une valeur par défaut plausible | `n/d` / `UNCALIBRATED` / refuse d'agir |
| Une PR qui grossit « tant qu'on y est » | Coupe, merge le fini, ouvre la suite |
| Corriger l'alarme en la supprimant | Corrige le seuil ou le classifieur |
| Reporter la doc « après » | La clôture FAIT partie de la tâche |
| Trancher à la place de l'humain (argent, irréversible) | Dossier + recommandation + ADR de SA décision |

---
*Dernière mise à jour : 2026-07-06, en partant. Le système est honnête aujourd'hui ;
il ne le restera que si chaque agent qui me succède refuse, comme moi, le chiffre
plausible qui arrange. Bonne route.*
