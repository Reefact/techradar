# Documentation TechRadar

Aide-mémoire du fonctionnement du site. Dernière mise à jour : 24 novembre 2026.

| Fichier | Contenu |
|---|---|
| [architecture.md](architecture.md) | Vue d'ensemble, structure du dépôt, le site (index, rapports, radar, flux) |
| [generation.md](generation.md) | La tâche planifiée de veille, la publication, les brouillons et leur promotion |
| [deploiement.md](deploiement.md) | Cloudflare Workers, GitHub Actions, outils locaux |
| [exploitation.md](exploitation.md) | Opérations courantes, dépannage, **état actuel et points ouverts** |

En une phrase : une tâche planifiée Claude rédige chaque matin un rapport HTML et le pousse sur `main` ; GitHub Actions régénère le flux ; Cloudflare déploie le site statique ; l'index affiche le dernier rapport avec un radar animé.
