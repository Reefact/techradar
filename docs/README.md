# Documentation TechRadar

Aide-mémoire du fonctionnement du site. Dernière mise à jour : 24 novembre 2026.

| Fichier | Contenu |
|---|---|
| [architecture.md](architecture.md) | Vue d'ensemble, structure du dépôt, le site (index, rapports, radar, flux) |
| [generation.md](generation.md) | La tâche planifiée, une exécution pas à pas, publier, relancer, contrôles, mémoire |
| [deploiement.md](deploiement.md) | Cloudflare Workers, GitHub Actions, outils locaux |
| [exploitation.md](exploitation.md) | Opérations courantes, dépannage, **état actuel et points ouverts** |
| [skills.md](skills.md) | Les skills Claude Code du dépôt : à quoi sert chacun, quand l'utiliser, exemples de demandes |
| [conception-v2.md](conception-v2.md) | Le raisonnement de la v2 (réalisée) : une source de données par jour, dossier du jour, configuration en fichiers |

En une phrase : une tâche planifiée Claude écrit chaque matin le fichier de données du jour (tous les sujets analysés, avec leur statut) et le pousse sur `main` ; Cloudflare en rend le site statique (rapport publié, dossier du jour, flux) ; l'index affiche le dernier rapport avec un radar animé.
