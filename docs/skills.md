# Les skills Claude Code du dépôt

Un **skill** est une procédure rangée dans `.claude/skills/<nom>/SKILL.md`. Dans une session Claude Code ouverte sur ce dépôt, on l'appelle en tapant `/<nom>`, ou simplement en le demandant en langage courant (« publie le sujet n4 ») : Claude reconnaît le skill adapté. Les skills ne servent que dans une session qui a le dépôt ; la tâche planifiée ne les utilise pas.

## Vue d'ensemble

| Skill | Quand l'utiliser | Ce qu'il modifie |
|---|---|---|
| [`veille-publier`](#veille-publier) | Ajouter au rapport un sujet du dossier, en retirer un, écarter | statuts dans le fichier du jour |
| [`veille-regenerer`](#veille-regenerer) | Relancer la veille d'un jour, avec des consignes | `data/demande.json` (puis la tâche) |
| [`veille-sujets`](#veille-sujets) | Changer ce que la veille cherche | `config/` |
| [`veille-relecture`](#veille-relecture) | Vérifier ou corriger le français | textes du fichier du jour |
| [`veille-test`](#veille-test) | Vérifier une exécution de la tâche | rien (il observe) |
| [`veille-noter`](#veille-noter) | Noter un sujet (bouton « ⭐ Noter » du site) pour que la veille apprenne tes goûts | `data/avis/notes.json`, `data/avis/preferences.md` |
| [`veille-memoire`](#veille-memoire) | Savoir si un sujet est déjà paru, quels rappels de CFP sont dus | rien (sauf `data/notes.md` sur demande) |

Tous commitent directement sur `main` (pas de branche ni de PR) après ton accord, et le site se redéploie tout seul.

**Limite commune** : la tâche « Tech Radar (Reefact) » a été créée depuis l'interface ; un agent ne peut pas la lancer, et « Run now » ne transmet pas de consigne. Les skills qui en dépendent te demandent de cliquer sur « Run now », et la consigne passe par `data/demande.json`.

## veille-publier

**But** : choisir ce qui est publié. Le rapport d'un jour = ses sujets au statut `publie`.

**Déroulé** : liste les sujets par statut (`tools/statut.py list`) ; applique ta demande (`set … publie|candidat|ecarte`) ; refuse un changement qui casserait une règle (plafond ou minimum d'une catégorie, dépôt inconnu, sujet sans résumé) ; propose d'ajuster « À retenir » ; valide, commite, vérifie en ligne.

**Raccourci** : sur https://techradar.reefact.net/dossier/, le bouton « Demander la publication » d'un sujet non publié, ou « Demander le retrait » d'un sujet publié, ouvre une session Claude Code avec la demande pré-remplie ; la session enchaîne avec la notation du sujet (`veille-noter`).

**Exemples** : « publie n4 et i6 du 24 novembre », « retire t3 du rapport », « écarte a8, c'est un doublon ».

## veille-regenerer

**But** : relancer la veille d'un jour (aujourd'hui, ou une date passée pour rattraper un jour manqué), avec des consignes.

**Déroulé** : demande la date et les consignes ; écrit `data/demande.json` et le pousse ; te fait cliquer sur « Run now » ; vérifie le résultat. Si le jour existe déjà, la tâche ajoute des **candidats** sans toucher aux sujets publiés ; sinon elle crée le jour.

**Exemple** : « relance la veille d'aujourd'hui en creusant l'IA et le DDD ».

## veille-sujets

**But** : modifier le périmètre de la veille sans toucher au processus.

**Déroulé** : identifie le bon fichier de `config/` (catégories, tags, priorités, sources, consignes de recherche, projets, conférences) ; le modifie ; vérifie avec `check_config.py` ; montre le diff ; commite après accord. Effet dès la prochaine exécution.

**Exemples** : « ajoute Verify aux concurrents surveillés pour unified-assertions », « suis toujours NDC Oslo », « exclus les conférences blockchain », « mets la catégorie Distribution en pause ».

## veille-relecture

**But** : un français idiomatique et compréhensible seul.

**Déroulé** : signaux automatiques (`check_day.py` : anglais résiduel, calques, phrases trop longues) ; relecture par un sous-agent indépendant sur les champs de texte du jour ; tableau avant/après et points factuellement douteux (non corrigés) ; applique ce que tu acceptes ; valide ; commite.

**Exemple** : « relis le français du rapport du 24 novembre ».

## veille-test

**But** : vérifier de bout en bout une exécution de la tâche.

**Déroulé** : note l'état de `main` ; te fait lancer la tâche ; attend sa fin ; lit sa notification ; contrôle le commit (directement sur `main`, seulement le fichier du jour), la validation (`check_day.py --contre <avant>`, immuabilité comprise), le journal, la relecture, puis le site en ligne ; rend un tableau.

**Exemple** : « teste la tâche de veille ».

## veille-noter

**Quand** : depuis le bouton « ⭐ Noter » d'un sujet (rapport ou dossier), qui ouvre une session Claude Code sur ce dépôt avec la demande pré-remplie, ou en demandant « note le sujet s3 du 2026-11-24 ».

**Déroulé** : rappelle le sujet ; pose en un message les questions rapides de `config/notation.json` (échelle de 1 à 5, oui/non : réponse attendue sous la forme `5 4 5 3 3 4 o o n`), puis les questions conditionnelles et le commentaire facultatif ; enregistre l'avis dans `data/avis/notes.json` ; réécrit la synthèse `data/avis/preferences.md` à partir de tous les avis ; commite et pousse.

**Effet** : la tâche de veille lit cette synthèse et les avis pour choisir les sujets ; dans le dossier, chaque sujet explique « Pourquoi ce choix » et affiche ta note s'il en a une.

## veille-memoire

**But** : interroger ce qui a déjà été vu.

**Commandes** : `tools/build_memory.py --seen <URL>` (avec statut : publié, écarté et pourquoi…), `--due <date>` (rappels de CFP dus), `--reconsiderer` (candidats non publiés).

**Exemples** : « est-ce qu'on a déjà parlé de cet article ? », « quels rappels de CFP demain ? ».
