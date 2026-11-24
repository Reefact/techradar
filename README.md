# techradar
Veille quotidienne : un brief HTML publié chaque matin (alertes de sécurité, .NET, IA, API et architecture, outils, distribution, conférences et CFP), généré automatiquement et déployé sur Cloudflare.

## Structure
- `index.html` : page d'accueil (bandeau, barre latérale par date, rapport affiché dans une iframe ; le dernier rapport par défaut, `#AAAA-MM-JJ` pour un jour précis).
- `reports/AAAA/AAAAMMJJ.html` : un rapport par jour. Chaque rapport doit contenir `<meta name="date" content="AAAA-MM-JJ">`, un `<title>`, et (pour le flux) un bloc `<div class="card tldr">` avec une liste `<li>`.
- `assets/report.css` : feuille de style partagée par les rapports.
- `feed.xml` : flux Atom, **généré**. Il sert aussi à l'index pour découvrir les rapports.
- `tools/build_feed.py` : régénère `feed.xml` (fait automatiquement par `.github/workflows/feed.yml` à chaque push dans `reports/`).
- `tools/report-template.html` : gabarit à suivre pour un rapport.
- `data/` : mémoire de la veille côté dépôt — `memory.json` (dérivé des rapports par `tools/build_memory.py`, ne pas éditer) et `notes.md` (notes manuelles). Voir `docs/generation.md`.
- `drafts/` : versions régénérées d'un rapport déjà publié (jamais listées) ; `.github/workflows/promote.yml` en promeut une vers `reports/`.

## Publier un rapport
1. Ajouter `reports/AAAA/AAAAMMJJ.html`, avec `<link rel="stylesheet" href="../../assets/report.css">`.
2. Lancer `python3 tools/build_feed.py [URL_DU_SITE]` (avec l'URL, les liens du flux sont absolus).
3. Déployer.

Pour tester en local : `python3 -m http.server` (l'index lit `feed.xml` via `fetch`, ce qui ne fonctionne pas en `file://`).

## Déploiement (Cloudflare Workers)
Site statique déployé par Workers Builds sur le Worker `techradar` : `tools/build_site.sh` assemble `dist/` (index, flux, `assets/`, `reports/` ; jamais `drafts/`, `tools/`, etc.), puis `npx wrangler deploy` (config dans `wrangler.jsonc`).
Réglages dans Cloudflare (Workers & Pages > techradar > Settings > Build) : build command `bash tools/build_site.sh`, deploy command `npx wrangler deploy`, branche `main`. Variable de build optionnelle `SITE_URL` (liens absolus du flux).
