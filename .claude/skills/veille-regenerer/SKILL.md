---
name: veille-regenerer
description: Relance la veille d'un jour (le jour courant ou une date passée) avec d'éventuelles consignes, via une demande écrite dans data/demande.json ; la relance ajoute des candidats au dossier du jour sans toucher aux sujets publiés. À utiliser pour compléter ou refaire la veille d'un jour, ou rattraper un jour manqué.
---

# Relancer la veille d'un jour

« Run now » ne transmet aucune consigne à la tâche, et un agent ne peut pas la lancer (elle a été créée depuis l'interface). La consigne passe donc par un fichier : `data/demande.json`, que la tâche lit au démarrage, applique, puis supprime dans son commit.

## 1. Cadrer

Demander (en une question) : la **date** (défaut : aujourd'hui, heure de Paris ; jamais une date future) et les **consignes** éventuelles (« creuse l'IA », « cherche des sujets DDD »…). Expliquer l'effet :
- **le fichier du jour existe** : la relance ajoute ses trouvailles en `candidat` dans le dossier du jour ; les sujets publiés ne bougent pas ; l'utilisateur publie ensuite ce qu'il veut (skill `veille-publier`) ;
- **il n'existe pas** (jour manqué) : la tâche crée le jour et publie sa sélection.
Pour une date passée, la recherche web est approximative (les moteurs favorisent le récent) : le dire.

## 2. Écrire la demande

```json
{
  "date_cible": "2026-11-24",
  "consignes": "Texte libre de l'utilisateur, recopié tel quel.",
  "creee_le": "<ISO>",
  "par": "utilisateur (skill veille-regenerer)"
}
```
Commit sur `main` : « Demande de relance AAAA-MM-JJ » ; push. Puis demander à l'utilisateur de cliquer sur **Run now** : https://claude.ai/code/routines/trig_01LAptLYqsefHr97oCdi9AiY

## 3. Vérifier

Quand l'utilisateur dit l'avoir lancée : suivre le skill `veille-test` (étapes « attendre » et « vérifier ») ; en plus, contrôler que `data/demande.json` a été supprimé par le commit de la tâche, et lister les nouveaux candidats (`python3 tools/statut.py list AAAA-MM-JJ`). Proposer ensuite `veille-publier`.

## Règles

- Une seule demande à la fois : si `data/demande.json` existe déjà, montrer son contenu et demander quoi en faire.
- Ne jamais modifier soi-même les sujets publiés d'un jour pour « régénérer ».
