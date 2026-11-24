# Les skills Claude Code du dépôt

Un **skill** est une procédure rangée dans `.claude/skills/<nom>/SKILL.md`. Dans une session Claude Code ouverte sur ce dépôt, on l'appelle en tapant `/<nom>`, ou simplement en le demandant en langage courant (« relis le rapport d'aujourd'hui ») : Claude reconnaît le skill adapté.

Les skills ne s'exécutent que dans une session qui a le dépôt ; la tâche planifiée ne les utilise pas.

## Vue d'ensemble

| Skill | Quand l'utiliser | Ce qu'il modifie |
|---|---|---|
| [`veille-test`](#veille-test) | Après un changement du prompt, de la configuration ou des accès | rien (il observe) |
| [`veille-relecture`](#veille-relecture) | Pour vérifier ou corriger le français d'un rapport | le rapport, après accord |
| [`veille-copier-sujet`](#veille-copier-sujet) | Pour reprendre quelques sujets d'un brouillon dans le rapport du jour | le rapport, après accord |
| [`promote-draft`](#promote-draft) | Pour remplacer le rapport d'un jour par un brouillon entier | le rapport, après accord |
| [`veille-regenerer`](#veille-regenerer) | Pour refaire le rapport d'un jour | crée un brouillon (via la tâche) |
| [`veille-memoire`](#veille-memoire) | Pour savoir si un sujet est déjà paru, ou quels rappels de CFP sont dus | rien, sauf `data/notes.md` sur demande |

**Limite commune.** La tâche « Tech Radar (Reefact) » a été créée depuis l'interface : un agent ne peut ni la lancer ni lui transmettre une consigne. Les skills qui en dépendent (`veille-test`, `veille-regenerer`) te demandent donc de cliquer sur « Run now » ; la consigne ne passe pas encore (prévu avec `data/demande.json`, voir [conception-v2.md](conception-v2.md)).

## veille-test

**But** : vérifier de bout en bout qu'une exécution de la tâche fonctionne.

**Déroulé** : vérifie si le rapport du jour existe (si oui, la tâche écrira un brouillon et ne touchera à rien) ; te demande de lancer la tâche ; attend sa fin ; lit sa notification finale ; contrôle dans le dépôt que le commit est arrivé directement sur `main`, qu'il ne touche que le bon fichier, que `reports/` est intact, que `check_report.py` passe, et qu'il n'y a ni branche ni pull request.

**Résultat** : un tableau (accès au dépôt, push, mode annoncé et constaté, conformité, écarts au prompt).

**Exemple** : « teste la tâche de veille ».

## veille-relecture

**But** : un français idiomatique et compréhensible seul.

**Déroulé** : lance les signaux automatiques (`check_report.py` : anglais résiduel, calques, phrases trop longues) ; confie le texte à un relecteur indépendant (sous-agent) avec des critères explicites ; te présente un tableau avant/après et ce qui est factuellement douteux, sans le corriger ; applique ce que tu acceptes ; vérifie la structure ; commite.

**Règles** : ne modifie jamais un fait, un chiffre, une date ni un lien ; rien n'est écrit sans ton accord.

**Exemple** : « relis le français du rapport du 24 novembre ».

## veille-copier-sujet

**But** : reprendre quelques sujets d'un brouillon dans le rapport publié du **même jour**, sans remplacer tout le rapport.

**Déroulé** : `tools/merge_topic.py list` classe les sujets du brouillon (nouveaux, différents, identiques) et les lignes « En bref » nouvelles ; tu choisis ; essai à blanc avec aperçu ; après accord, la carte est insérée dans la bonne catégorie (créée si besoin), reçoit un identifiant libre, et le sommaire est mis à jour ; une copie qui introduirait une erreur de structure est refusée.

**Limites** : même jour uniquement ; les cartes de conférence, « À retenir » et le pied de page ne sont pas gérés.

**Exemple** : « reprends les sujets Blazor et Shirudo du brouillon de 16h44 ».

## promote-draft

**But** : remplacer le rapport d'un jour par un brouillon entier.

**Déroulé** : liste les brouillons ; te demande lequel et ton accord (le rapport est publié) ; lance le workflow GitHub « Promote a draft report », qui copie le brouillon vers `reports/`, régénère le flux et la mémoire, et commite ; vérifie le résultat.

**Exemple** : « promeus le brouillon de 16h44 ».

## veille-regenerer

**But** : refaire le rapport d'une date, en brouillon (par défaut) ou en remplaçant le rapport publié (brouillon puis promotion, après accord).

**Déroulé** : demande la date, le mode et d'éventuelles consignes ; te fait lancer la tâche ; contrôle le brouillon (`check_report.py`), le compare à l'ancien ; en mode « écraser », te redemande ton accord sur le contenu produit puis suit `promote-draft`.

**Limites** : pour une date passée, la recherche est approximative ; tant que les consignes ne peuvent pas être transmises à la tâche, seul le mode brouillon du jour courant fonctionne sans intervention.

**Exemple** : « régénère le rapport d'aujourd'hui en brouillon ».

## veille-memoire

**But** : interroger la mémoire de la veille, dérivée des rapports (`data/memory.json`) et complétée par `data/notes.md`.

**Commandes** : `python3 tools/build_memory.py --seen <URL>` (déjà publiée ?) ; `--due <date>` (rappels de CFP dus ce jour-là) ; sans argument, régénère la mémoire.

**Exemple** : « est-ce qu'on a déjà parlé de cet article ? », « quels rappels de CFP demain ? ».

## Évolution prévue

La [conception v2](conception-v2.md) remplace `promote-draft` et `veille-copier-sujet` par **`veille-publier`** (changer le statut d'un sujet), ajoute **`veille-sujets`** (modifier la configuration de la veille en langage courant) et adapte les autres skills au fichier de données du jour.
