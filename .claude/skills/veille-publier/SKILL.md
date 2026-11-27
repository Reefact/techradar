---
name: veille-publier
description: Change le statut des sujets d'un jour de veille (publier un candidat, retirer un sujet publié, écarter avec un motif), puis valide, commite et déploie. À utiliser quand l'utilisateur veut ajouter au rapport un sujet du dossier du jour, en retirer un, ou réviser la sélection.
---

# Publier ou retirer des sujets

Le rapport publié d'un jour = les sujets `publie` de `data/days/AAAA/AAAAMMJJ.json`. Changer un statut suffit : le site est rendu au déploiement. Les modifications passent par `tools/statut.py` (déterministe, avec historique et validation).

## 1. Montrer l'état du jour

`git pull`, puis :
```bash
python3 tools/statut.py list AAAA-MM-JJ
```
(par défaut le jour le plus récent de `data/days/`). Présenter à l'utilisateur, en clair, les candidats (titre, catégorie), et ce qu'il a demandé. La page https://techradar.reefact.net/dossier/ montre la même chose avec les résumés ; ses boutons « Demander la publication » et « Demander le retrait » ouvrent une session avec une demande du type « Publie dans le rapport le sujet n4 du 2026-11-24 (« … ») avec le skill veille-publier, puis fais-moi noter ce sujet avec le skill veille-noter ».

## 2. Vérifier les affirmations avant de publier

Avant de publier un candidat, applique `tools/veille-verification.md` : s'il contient une affirmation qui pourrait être fausse, portée ni par l'auteur du fait ni par une source de référence (`config/sujets/sources.json`), et qu'il n'a pas de `verification` au verdict `vrai`, lance d'abord le sous-agent vérificateur (brief du fichier, sans ton avis). Puis :
- `vrai` : écris le bloc `verification`, rebase le sujet sur la source fiable trouvée (en tête des sources, résumé réécrit à partir d'elle, seulement les affirmations prouvées ; titre qui dit « revendiqué » pour un incident seulement revendiqué), montre le résultat à l'utilisateur et publie ;
- `faux` : ne publie pas ; propose d'écarter le sujet (`--motif infirme`) ;
- `indetermine` : ne publie pas ; il reste candidat, avec une raison de choix qui dit qu'il attend une vérification, et il sera revérifié à la prochaine exécution.

Le validateur refuse un sujet publié dans une catégorie à risque sans source de référence ni vérification `vrai`, et tout sujet publié dont le verdict n'est pas `vrai`.

## 3. Appliquer

```bash
python3 tools/statut.py set AAAA-MM-JJ n4,i6 publie [--note "pourquoi"]
python3 tools/statut.py set AAAA-MM-JJ t3 candidat              # retirer du rapport
python3 tools/statut.py set AAAA-MM-JJ a8 ecarte --motif doublon
```
Le script refuse un changement qui rendrait le jour invalide (plafond ou minimum d'une catégorie, sujet sans résumé, dépôt inconnu…) : rapporter le refus tel quel et proposer une solution (retirer un autre sujet de la catégorie, par exemple), sans contourner.

Plafonds (15 publiés, maximum d'une catégorie) : par défaut, le refus s'applique et tu le rapportes à l'utilisateur. N'utilise `--force` que s'il demande **explicitement** de forcer : le sujet est alors marqué « force_utilisateur » et le quota ne bloque plus, mais le dépassement reste affiché (« CONTRÔLES DÉPASSÉS ») et signalé par `check_day.py` ; rapporte-le à l'utilisateur. Les autres contrôles (résumé, vérification…) restent bloquants, même forcés.
```bash
python3 tools/statut.py set AAAA-MM-JJ p5 publie --force --note "pourquoi"
```

**Retirer un sujet publié** change le rapport en ligne : demander une confirmation explicite.

## 3 bis. Faire noter le sujet

Après une publication ou un retrait, enchaîne avec le skill `veille-noter` sur ce sujet (le bouton du dossier le demande déjà) : c'est le meilleur moment pour savoir ce qui a motivé la décision. Pour un retrait, la question ouverte demande en priorité pourquoi le sujet n'avait pas sa place. Si l'utilisateur ne veut pas noter, n'insiste pas.

## 4. « À retenir »

Si un sujet publié ou retiré change ce qui compte le plus ce jour-là, proposer la modification de `a_retenir` (sections rédigées, voir `tools/veille-prompt.md` §4, avec les `sujets` cités) ; l'appliquer seulement après accord, en éditant le fichier JSON.

## 5. Valider, publier, vérifier

1. `python3 tools/check_day.py data/days/AAAA/AAAAMMJJ.json --partiel` : aucune erreur.
2. Aperçu facultatif : `python3 tools/render.py /tmp/apercu`, puis ouvrir `/tmp/apercu/reports/AAAA/AAAAMMJJ.html`.
3. Commit sur `main` (pas de branche ni de PR) : « Veille AAAA-MM-JJ : publication de n4, i6 » ; push.
4. Après le déploiement (1 à 3 minutes), vérifier en ligne que le sujet apparaît dans la liste des sujets du rapport.

## Règles

- L'historique Git du fichier du jour garde toutes les versions : un retour en arrière se fait par `git revert`.
- Ne jamais modifier le texte d'un sujet dans ce skill (c'est le rôle de `veille-relecture`), sauf pour l'aligner sur sa vérification (§2) : bloc `verification` et retrait des affirmations non prouvées.
