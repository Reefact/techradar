# techradar

Veille technologique quotidienne (Reefact) : sécurité, .NET, IA, API et architecture, outils, distribution, conférences et CFP. Publiée sur **https://techradar.reefact.net/**.

- Chaque matin, une tâche planifiée Claude écrit le **fichier du jour** `data/days/AAAA/AAAAMMJJ.json` : tous les sujets analysés, avec leur statut (publié, candidat, mis de côté, écarté).
- Cloudflare **rend** le site à partir de ces fichiers : le rapport publié, le **dossier du jour** (`/dossier/`) et le flux Atom (`feed.xml`).
- Ce que la veille cherche est dans **`config/`** ; la façon de travailler dans **`tools/veille-prompt.md`**.
- Des **skills** Claude Code servent à publier, relancer, relire, tester et faire évoluer la veille.

Documentation : [`docs/`](docs/README.md) — architecture, génération, déploiement, exploitation, skills.

Pour tester en local :

```bash
bash tools/build_site.sh && python3 -m http.server -d dist
```
