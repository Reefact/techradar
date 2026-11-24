---
name: veille-sujets
description: Modifie la configuration de la veille (quoi chercher) à partir d'une demande en langage courant : catégories, tags, exclusions, sources, consignes de recherche, tes projets (dépôts et thèmes), conférences toujours suivies ou exclues. Choisit le bon fichier de config/, montre le diff, valide, commite. À utiliser pour tout changement de périmètre de la veille.
---

# Modifier ce que la veille cherche

La configuration vit dans `config/` ; la tâche planifiée la relit à chaque exécution, donc un changement poussé sur `main` s'applique dès le lendemain matin.

## Quel fichier pour quelle demande

| Demande | Fichier |
|---|---|
| Ajouter, renommer, rééquilibrer une catégorie (libellé, ordre, minimum, plafond) | `config/categories.json` (+ un fichier `config/sujets/recherche/<clé>.json` et une entrée dans l'index pour une nouvelle catégorie) |
| Ajouter ou redéfinir un badge | `config/tags.json` |
| Mettre en pause ou réactiver un domaine | `config/sujets.json` (champ `actif`) |
| Exclusions globales, fenêtre de dates, volumes | `config/sujets/perimetre.json` |
| Sources à privilégier, à toujours consulter, à ignorer | `config/sujets/sources.json` |
| Sources de référence (dispensent de vérification), catégories à risque, règle de vérification des affirmations | `config/sujets/sources.json`, bloc `verification` (voir `tools/veille-verification.md`) |
| Consigne, sources, « toujours suivre », « exclure » d'une catégorie | `config/sujets/recherche/<catégorie>.json` |
| Outils (sources de découverte, composition) | `config/sujets/outils.json` |
| Tes projets (dépôt, thème, concurrents à surveiller), projets exclus ; ce sont eux qui donnent le badge 📦 et les thèmes prioritaires | `config/sujets/projets.json` |
| Conférences toujours suivies ou exclues, déclencheurs, seuils de rappel | `config/sujets/conferences.json` |

Principes : un bloc affiche **exactement** les libellés déclarés ici (catégorie, tags, projets) : le build échoue sinon (`tools/check_front.py`, `tests/`). une **clé** de catégorie ou de tag ne se renomme pas (les fichiers du jour la référencent) ; on change son `label`. « Toujours suivre » ≠ « afficher » : l'élément est vérifié à chaque exécution, mais n'apparaît que s'il y a du nouveau. Les conférences s'écrivent par **série** (« Devoxx France »), pas par édition.

## Déroulé

1. Reformuler la demande et indiquer le ou les fichiers concernés.
2. Modifier le JSON (indentation de 2 espaces, `ensure_ascii` faux), sans toucher au reste.
3. `python3 tools/check_config.py` : aucune erreur.
4. Montrer le diff (`git diff config/`) et demander l'accord.
5. Commit sur `main` : « Configuration : <résumé> » ; push. Le changement vaut dès la prochaine exécution de la tâche.

## Règles

- Ne jamais modifier `tools/veille-prompt.md` pour un changement de périmètre : le processus et la configuration sont séparés.
- Supprimer une catégorie utilisée par des jours passés casse leur rendu : la mettre plutôt à `min` 0 et rendre son fichier de recherche inactif dans l'index.
