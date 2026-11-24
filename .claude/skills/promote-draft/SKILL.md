---
name: promote-draft
description: Promeut un brouillon de rapport TechRadar (drafts/AAAA/AAAAMMJJ-HHMM.html) en rapport officiel du jour en lançant le workflow GitHub "Promote a draft report". À utiliser quand l'utilisateur veut remplacer le rapport d'un jour par une version régénérée, ou choisir un brouillon.
---

# Promouvoir un brouillon de rapport

Les brouillons sont les versions régénérées d'un rapport déjà publié (`drafts/`). Les promouvoir remplace `reports/AAAA/AAAAMMJJ.html`, régénère `feed.xml` et pousse sur `main` : c'est visible publiquement après le déploiement. L'ancienne version reste dans l'historique git.

## Étapes

1. **Lister les brouillons** du dépôt `Reefact/techradar` : contenu de `drafts/` et de ses sous-dossiers (outil GitHub `get_file_contents` sur `drafts/AAAA`, ou `ls drafts/*/` dans un clone). Ignorer `README.md`.
2. **Choisir le brouillon** : celui que l'utilisateur nomme ; sinon, s'il y en a plusieurs pour le jour demandé, les lister (date, heure) et demander lequel. Le chemin doit avoir exactement la forme `drafts/AAAA/AAAAMMJJ-HHMM.html`.
3. **Montrer la différence** avant d'agir : jour concerné, brouillon retenu, et le fait que `reports/AAAA/AAAAMMJJ.html` sera remplacé. Obtenir un accord explicite de l'utilisateur (l'action écrase un rapport publié).
4. **Lancer le workflow** `promote.yml` sur `main` avec l'entrée `draft` :
   - outil GitHub `actions_run_trigger` (workflow `promote.yml`, ref `main`, inputs `{"draft": "<chemin>"}`) ;
   - ou, si `gh` est disponible : `gh workflow run promote.yml --repo Reefact/techradar -f draft=<chemin>`.
5. **Vérifier** : suivre le run (`actions_list` / `actions_get`) jusqu'à la fin, puis confirmer qu'un commit « Promote <chemin> to reports/... » est apparu sur `main` et que `feed.xml` a été mis à jour. Si le run échoue, lire ses logs (`get_job_logs`) et rapporter la cause ; ne rien contourner.

## Règles

- Ne jamais écrire dans `reports/` à la main pour faire la promotion : passer par le workflow.
- Ne jamais promouvoir sans l'accord de l'utilisateur pour ce jour et ce brouillon.
- Pas de branche, pas de PR : le workflow pousse directement sur `main`.
