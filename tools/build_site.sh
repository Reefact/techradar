#!/usr/bin/env bash
# Assemble le site publiable dans dist/ (seul dist/ est déployé sur Cloudflare).
# Le contenu est GÉNÉRÉ depuis data/days/*.json par tools/render.py : rapports publiés,
# dossiers du jour, flux Atom. S'y ajoutent l'interface (index, page /dossier/, assets/).
# Variable optionnelle SITE_URL : liens absolus dans feed.xml.
set -euo pipefail
cd "$(dirname "$0")/.."
command -v python3 >/dev/null 2>&1 || { echo "python3 est nécessaire au rendu" >&2; exit 1; }
rm -rf dist && mkdir -p dist
python3 tools/check_config.py                     # configuration cohérente, sinon pas de déploiement
python3 tools/render.py dist "${SITE_URL:-}"      # reports/, dossier/AAAA/, dossier/dossier.json, feed.xml
cp index.html dist/
cp -r assets dist/
cp dossier/index.html dist/dossier/
# Le dossier du jour ne doit pas être indexé ; les anciennes adresses /drafts mènent au dossier.
cat > dist/_headers <<'H'
/dossier
  X-Robots-Tag: noindex, nofollow
/dossier/*
  X-Robots-Tag: noindex, nofollow
H
cat > dist/_redirects <<'R'
/drafts /dossier/ 301
/drafts/ /dossier/ 301
/drafts/* /dossier/ 301
R
echo "dist/ : $(find dist -type f | wc -l) fichier(s)"
